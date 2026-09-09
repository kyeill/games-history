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


def harvest():
    keep, teams = [], {}
    for code in ("CFB", "CBB"):
        bt = rules.BIG_TEN[code]
        for y in SEASONS:
            for x in events(code, y):
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

                if code == "CFB":
                    slots = rules.cfb_slots(nets, d)
                else:
                    slots = rules.cbb_slots(nets, d, all(q == bt for q in confs),
                                            any(ranks))
                gtype = None
                if len(win) == 1 and len(lose) == 1:
                    gtype = rules.game_type(code, rank_of(win[0]),
                                            rank_of(lose[0]), bt in confs)
                heads = [n.get("headline") or "" for n in (c.get("notes") or [])]
                conf, head = rules.power5_title(heads)
                if not slots and not gtype and not conf:
                    continue

                side = []
                for k in cs:
                    t = k["team"]
                    teams[t["id"]] = {"name": t["displayName"],
                                      "short": t.get("location") or t["displayName"],
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
                    "venue": v.get("fullName"),
                    "city": (v.get("address") or {}).get("city"),
                    "nets": sorted(nets), "teams": side,
                    "slots": sorted(slots), "type": gtype,
                    "champ": conf, "round": head,
                })
    keep.sort(key=lambda g: (g["date"], g["time"]))
    os.makedirs(OUT, exist_ok=True)
    json.dump({"games": keep, "teams": teams, "order": rules.ORDER,
               "marquee": rules.MARQUEE,
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
