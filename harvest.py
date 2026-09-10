"""Fetch every past CFB/CBB game matching rules.py and freeze it to JSON.

Past games never change, so this runs once per new week of games -- there is
no daily build and nothing goes stale. `cache/` holds raw ESPN responses so a
re-run is free.
"""
import collections, datetime as dt, json, os, sys
from zoneinfo import ZoneInfo
import requests
import rules

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
OUT = os.path.join(HERE, "output")
ET = ZoneInfo("America/New_York")
BASE = "https://site.api.espn.com/apis/site/v2/sports"
SEASONS = [2021, 2022, 2023, 2024, 2025]

# CFB is groups=80 (FBS). CBB is groups=50 (D-I).
SPORTS = {"CFB": ("football/college-football", "80"),
          "CBB": ("basketball/mens-college-basketball", "50")}


def fetch(sport, params, key):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, key + ".json")
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    r = requests.get(f"{BASE}/{sport}/scoreboard", params=params, timeout=60)
    r.raise_for_status()
    d = r.json()
    json.dump(d, open(p, "w", encoding="utf-8"))
    return d


def events(code, y):
    """CFB accepts a wide date range; CBB 404s on one and silently caps at
    limit=1000, so it is walked a week at a time."""
    sport, grp = SPORTS[code]
    ev = []
    if code == "CFB":
        for rng, tag in ((f"{y}0801-{y}1231", "a"), (f"{y+1}0101-{y+1}0131", "b")):
            ev += fetch(sport, {"dates": rng, "groups": grp, "limit": 1000},
                        f"cfb-{y}-{grp}-{tag}").get("events", [])
    else:
        d, end = dt.date(y, 11, 1), dt.date(y + 1, 4, 10)
        while d < end:
            e = min(d + dt.timedelta(days=6), end)
            got = fetch(sport, {"dates": f"{d:%Y%m%d}-{e:%Y%m%d}", "groups": grp,
                                "limit": 1000}, f"cbb-{d:%Y%m%d}").get("events", [])
            if len(got) >= 1000:
                print(f"  WARN: week of {d} hit the 1000 cap", file=sys.stderr)
            ev += got
            d = e + dt.timedelta(days=1)
    return ev


def rank_of(c):
    v = (c.get("curatedRank") or {}).get("current")
    return None if v in (None, 0, 99) else v


def networks(comp):
    out = []
    for b in comp.get("broadcasts") or []:
        out += b.get("names") or []
    return sorted(set(out))


def fox_friday_dates(evs):
    """Dates that already have a FOX Friday night game. FS1 only deputises for
    the Big Ten on a Friday when FOX itself is not carrying one."""
    out = set()
    for x in evs:
        comps = x.get("competitions") or []
        if not comps:
            continue
        nets = set(networks(comps[0]))
        if "FOX" not in nets:
            continue
        d = dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ")               .replace(tzinfo=dt.timezone.utc).astimezone(ET)
        if d.weekday() == 4 and d.hour >= 18:
            out.add(d.date())
    return out


def load_overrides():
    """Manual window assignments for games ESPN records with no network.

    A weather-delayed game can end up with only its streaming feed listed --
    Texas A&M at Florida (2024) reads "ESPN+, ESPN3" and nothing else -- and no
    rule can recover a network that is not in the data. This is the escape
    hatch. Keys are ESPN game ids; keys starting with "_" are ignored.
    """
    path = os.path.join(HERE, "window-overrides.json")
    if not os.path.exists(path):
        return {}
    raw = json.load(open(path, encoding="utf-8"))
    return {k: v for k, v in raw.items()
            if not k.startswith("_") and isinstance(v, list)}


def espn_saturday_ids(evs):
    """One ESPN game per Saturday: the LATEST tip between 6pm and 9pm ET.

    His rule, 2026-09-09, replacing a 6:30pm cutoff that cut through the 6pm
    block and admitted up to three games a night. Measured across the archive
    it selects 46 Saturdays with no ties at all, and lands on the late marquee
    game -- North Carolina at Duke, Kentucky at Tennessee, Duke at Virginia.
    """
    best = {}
    for x in evs:
        comps = x.get("competitions") or []
        if not comps:
            continue
        if "ESPN" not in set(networks(comps[0])):
            continue
        d = dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ")               .replace(tzinfo=dt.timezone.utc).astimezone(ET)
        if d.weekday() != 5 or d.month not in (1, 2, 3):
            continue
        mins = d.hour * 60 + d.minute
        if not (18 * 60 <= mins <= 21 * 60):
            continue
        cur = best.get(d.date())
        if cur is None or mins > cur[0]:
            best[d.date()] = (mins, x["id"])
    return {v[1] for v in best.values()}


def harvest():
    keep, teams = [], {}
    overrides = load_overrides()
    for code in ("CFB", "CBB"):
        bt = rules.BIG_TEN[code]
        for y in SEASONS:
            evs = events(code, y)
            fox_fri = fox_friday_dates(evs) if code == "CFB" else set()
            espn_sat = espn_saturday_ids(evs) if code == "CBB" else set()
            for x in evs:
                comps = x.get("competitions") or []
                if not comps:
                    continue                      # older payloads omit it
                c = comps[0]
                cs = c.get("competitors") or []
                if len(cs) != 2:
                    continue
                if not (c.get("status") or {}).get("type", {}).get("completed"):
                    continue
                if any(k.get("score") in (None, "") for k in cs):
                    continue
                if (x.get("season") or {}).get("type") != 2:
                    continue                      # drop bowls / CFP / NCAA

                d = dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ") \
                      .replace(tzinfo=dt.timezone.utc).astimezone(ET)
                # Regulation is 4 quarters of football, 2 halves of
                # basketball; any period beyond that is overtime.
                period = (c.get("status") or {}).get("period") or 0
                overtime = period > (4 if code == "CFB" else 2)
                nets = set(networks(c))
                ranks = [rank_of(k) for k in cs]
                confs = [str(k["team"].get("conferenceId")) for k in cs]
                win = [k for k in cs if k.get("winner")]
                lose = [k for k in cs if not k.get("winner")]

                team_ids = [k["team"]["id"] for k in cs]
                black_friday = False
                suffix = None
                if code == "CFB":
                    slots = rules.cfb_slots(nets, d, y, team_ids, set(confs),
                                            fox_fri)
                    black_friday = rules.cfb_black_friday(
                        nets, d, y, big_ten=(bt in confs))
                else:
                    slots = rules.cbb_slots(nets, d, all(q == bt for q in confs),
                                            any(ranks), bt in confs,
                                            espn_sat=x["id"] in espn_sat)
                    suffix = rules.cbb_header_suffix(
                        nets, d,
                        tourney=(rules.is_championship(heads)
                                 and d.month in (3, 4)))
                heads = [n.get("headline") or "" for n in (c.get("notes") or [])]
                conf, head = rules.power5_title(heads, code)
                title = rules.is_title_game(code, conf, head)
                # A championship game outside the Power Four/Five keeps no TV
                # window -- the Mountain West title game is not "FOX Friday".
                # Football only: a Big East tournament game on FOX genuinely is
                # a FOX basketball game.
                if code == "CFB" and not conf and rules.is_championship(heads):
                    slots = set()
                gtype = None
                if len(win) == 1 and len(lose) == 1:
                    # a championship game with no category of its own is filed
                    # by result rather than left uncategorised
                    # a Big Ten Tournament game before the Final
                    b1g_run = (code == "CBB" and conf == "Big Ten"
                               and not title)
                    gtype = rules.game_type(code, rank_of(win[0]),
                                            rank_of(lose[0]), bt in confs,
                                            p5_title=title,
                                            b1g_tourney_run=b1g_run)
                # a named event (Battle 4 Atlantis, SEC Quarterfinals) for the
                # blue chip, when it is not already a Power Five title
                event = None
                for h in heads:
                    base = h.split(" - ")[0]
                    if base and not conf:
                        event = h.replace(" - ", " ")
                        break
                # Being a conference-tournament game is NOT a qualification on
                # its own: it took in 265 early-round basketball games nothing
                # could reach. A championship game always has a type.
                if (not slots and not gtype and not title and not black_friday
                        and x["id"] not in overrides):
                    continue
                # A conference tournament or playoff round that is NOT the
                # final is out of the archive entirely, both tabs (his call
                # 2026-09-09). ESPN publishes no rankings for tournament games
                # in the early seasons anyway -- 0 of 600 in 2021-22 -- so the
                # ranking rules could never judge them fairly. That also drops
                # non-Power-Six conference titles and the FCS playoff rounds.
                # ...but "Championship" in an early-season showcase name is not
                # a conference tournament -- the Baha Mar Championship is a
                # November event, and Purdue v Texas Tech there is a real game.
                # Conference tournaments are a MARCH thing in basketball.
                tourney_round = rules.is_championship(heads) and (
                    code == "CFB" or d.month in (3, 4))
                if tourney_round and not title:
                    continue
                # A championship game carries NO TV window chip (his call): it
                # is admitted to that view by the `title` flag instead.
                if title:
                    slots = set()
                if x["id"] in overrides:
                    slots = set(overrides[x["id"]])

                side = []
                for k in cs:
                    t = k["team"]
                    teams[t["id"]] = {"name": t["displayName"],
                                      "short": rules.display_name(
                                          t.get("location") or t["displayName"]),
                                      "abbr": t.get("abbreviation"),
                                      "color": t.get("color"),
                                      "alt": t.get("alternateColor")}
                    side.append({"id": t["id"], "score": int(k["score"]),
                                 "rank": rank_of(k), "win": bool(k.get("winner")),
                                 "home": k.get("homeAway") == "home",
                                 "conf": str(t.get("conferenceId"))})
                v = c.get("venue") or {}
                keep.append({
                    "id": x["id"], "sport": code, "season": y,
                    "date": d.strftime("%Y-%m-%d"), "dow": rules.DOW[d.weekday()],
                    "time": d.strftime("%H:%M"),
                    "neutral": bool(c.get("neutralSite")), "ot": overtime,
                    # ESPN carries week.number on every CFB event; basketball
                    # has one too but it means nothing to a viewer, so only
                    # football displays it.
                    "week": (x.get("week") or {}).get("number"),
                    "venue": v.get("fullName"),
                    "city": (v.get("address") or {}).get("city"),
                    "nets": sorted(nets), "teams": side,
                    "slots": sorted(slots), "type": gtype,
                    "champ": conf, "round": head, "title": title,
                    "event": event, "bfri": black_friday, "suffix": suffix,
                })
    keep.sort(key=lambda g: (g["date"], g["time"]))
    os.makedirs(OUT, exist_ok=True)
    json.dump({"games": keep, "teams": teams, "order": rules.ORDER,
               "marquee": rules.MARQUEE, "window_net": rules.WINDOW_NET,
               "header_tint": rules.HEADER_TINT, "net_tint": rules.NET_TINT,
               "big_ten": rules.BIG_TEN, "season_names": rules.SEASON_NAMES,
               "net_priority": rules.NET_PRIORITY,
               "seasons": sorted({g["season"] for g in keep})},
              open(os.path.join(OUT, "games.json"), "w", encoding="utf-8"),
              separators=(",", ":"))
    return keep, teams


if __name__ == "__main__":
    g, t = harvest()
    print(f"{len(g)} games, {len(t)} teams -> output/games.json")
    per = collections.Counter(x["sport"] for x in g)
    print("  ", dict(per))
    tags = collections.Counter()
    for x in g:
        for s in x["slots"]: tags["slot: " + s] += 1
        if x["type"]:        tags["type: " + x["type"]] += 1
        if x["champ"]:       tags["champ: " + x["champ"]] += 1
    for k, v in sorted(tags.items()):
        print(f"   {v:5d}  {k}")
