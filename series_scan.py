"""Scan for home & home, neutral & neutral and annual series candidates.

A REVIEW TOOL, not part of the build. It writes output/series_review.txt for
him to rule on; his rulings then go into seed_series.py by hand, and
`python seed_series.py` applies them. Run it after a season finishes, or once
next season's schedule is out.

    python series_scan.py

What it reads:
  * the archive (output/games.json) -- only games on his tabs get a verdict
  * every game for both sports from TWO seasons before the archive starts
    through its newest season, so the archive's first year can find the first
    legs it is the return of
  * the whole published schedule of any unfinished season, because a future
    game is how this season's first leg finds its return
  * docs/tags.json, so a pair he has already ruled on is marked as such

harvest.py never keeps the pre-archive seasons or unfinished schedules, so
those are cached in the system temp folder rather than cache/ (which lives in
a synced Drive folder), and unfinished schedules are re-fetched each day.

The rule, and the five ways its first version was wrong, are in NOTES.md
under "The series scan".
"""
import collections
import datetime as dt
import io
import json
import os
import tempfile

import harvest
import rules
import seed_series

HERE = os.path.dirname(os.path.abspath(__file__))
GAMES = os.path.join(HERE, "output", "games.json")
TAGS = os.path.join(HERE, "docs", "tags.json")
OUT = os.path.join(HERE, "output", "series_review.txt")
SIDE_CACHE = os.path.join(tempfile.gettempdir(), "games-history-scan")
SERIES_TAGS = ("Home & Home", "Neutral & Neutral", "Home & Neutral", "Annual")
DEAD = ("STATUS_CANCELED", "STATUS_POSTPONED")
NL = chr(10)

FIRST = min(harvest.SEASONS) - 2        # two seasons of look-back
LAST = max(harvest.SEASONS)
ANNUAL_MIN = 5                          # meetings in the seasons FIRST..LAST-1

# A conference challenge names two conferences and a "challenge"-type word.
CHALLENGE_WORDS = ("challenge", "battle", "legacy series")
CONF_NAMES = ("acc", "sec", "big ten", "big 12", "big east", "pac-12", "big sky",
              "summit", "mac", "sbc", "socon", "asun", "wac", "cusa", "maac", "swac")
# Recurring events whose teams each play once, so the tournament test misses them.
KNOWN_EVENTS = ("champions classic", "cbs sports classic", "jimmy v",
                "crossroads classic", "big 5 classic")


# ---------------------------------------------------------------- loading

def _side(fn):
    old = harvest.CACHE
    harvest.CACHE = SIDE_CACHE
    try:
        return fn()
    finally:
        harvest.CACHE = old


def _schedule(code, y):
    """An unfinished season's whole published schedule, cached for today."""
    sport, grp = harvest.SPORTS[code]
    today = dt.date.today().strftime("%Y%m%d")
    ev = []
    if code == "CFB":
        for rng, tag in ((str(y) + "0801-" + str(y) + "1231", "a"),
                         (str(y + 1) + "0101-" + str(y + 1) + "0131", "b")):
            ev += harvest.fetch(sport, {"dates": rng, "groups": grp, "limit": 1000},
                                "scan-cfb-%d-%s-%s" % (y, tag, today), True).get("events", [])
        return ev
    d, end = dt.date(y, 11, 1), dt.date(y + 1, 4, 10)
    while d < end:
        e = min(d + dt.timedelta(days=6), end)
        # same empty-opening-week trap as harvest, same fallback
        ev += harvest.cbb_range(d, e, True, tag="-scan-" + today)
        d = e + dt.timedelta(days=1)
    return ev


def load_season(code, y):
    if y < min(harvest.SEASONS):
        return _side(lambda: harvest.events(code, y))
    if harvest.season_over(code, y):
        return harvest.events(code, y)          # already in the project cache
    return _side(lambda: _schedule(code, y))


def stem_of(c):
    for n in (c.get("notes") or []):
        h = (n.get("headline") or "").split(" - ")[0].strip()
        if h:
            return h
    return ""


def load_all():
    recs, by_pair = {}, collections.defaultdict(list)
    banner_games = collections.defaultdict(list)
    for code in ("CFB", "CBB"):
        for y in range(FIRST, LAST + 1):
            for x in load_season(code, y):
                if (code, x["id"]) in recs:
                    continue
                c = (x.get("competitions") or [{}])[0]
                cs = c.get("competitors") or []
                if len(cs) != 2:
                    continue
                st = (c.get("status") or {}).get("type") or {}
                home = next((k for k in cs if k.get("homeAway") == "home"), cs[0])
                away = next((k for k in cs if k.get("homeAway") == "away"), cs[1])
                d = dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ").replace(
                    tzinfo=dt.timezone.utc).astimezone(harvest.ET)
                v = c.get("venue") or {}
                heads = [n.get("headline") or "" for n in (c.get("notes") or [])]
                r = dict(sport=code, season=y, id=x["id"], date=d.date(),
                         type=(x.get("season") or {}).get("type"), state=st.get("name"),
                         home=home["team"]["id"], away=away["team"]["id"],
                         hloc=home["team"].get("location") or home["team"].get("displayName") or "?",
                         aloc=away["team"].get("location") or away["team"].get("displayName") or "?",
                         confs=(str(home["team"].get("conferenceId")),
                                str(away["team"].get("conferenceId"))),
                         confgame=c.get("conferenceCompetition"),
                         neutral=bool(c.get("neutralSite")), venue=v.get("fullName") or "",
                         city=(v.get("address") or {}).get("city") or "",
                         stem=stem_of(c), champ=rules.is_championship(heads))
                recs[(code, x["id"])] = r
                by_pair[(code, frozenset((r["home"], r["away"])))].append(r)
                if r["stem"]:
                    banner_games[(code, y, r["stem"])].append(r)
    return recs, by_pair, banner_games


# ---------------------------------------------------------------- the rule

class Rule:
    def __init__(self, recs, banner_games):
        self.banners = {}
        for k, gl in banner_games.items():
            days = collections.defaultdict(list)
            for r in gl:
                days[r["home"]].append(r["date"])
                days[r["away"]].append(r["date"])
            # a TOURNAMENT: somebody plays twice under the banner within four
            # days (Maui) -- not merely twice in a season (Hall of Fame Series)
            tourn = any(any((ds[i + 1] - ds[i]).days <= 4 for i in range(len(ds) - 1))
                        for ds in (sorted(v) for v in days.values()))
            self.banners[k] = dict(games=len(gl), teams=len(days), tourn=tourn)
        cities = collections.defaultdict(collections.Counter)
        for r in recs.values():
            if not r["neutral"] and r["city"]:
                cities[(r["sport"], r["home"])][r["city"]] += 1
        self.home_city = {k: c.most_common(1)[0][0] for k, c in cities.items()}

    def banner(self, r):
        return self.banners[(r["sport"], r["season"], r["stem"])] if r["stem"] else None

    @staticmethod
    def is_challenge(stem):
        s = stem.lower()
        if "gavitt" in s:
            return True
        return (any(w in s for w in CHALLENGE_WORDS) and any(c in s for c in CONF_NAMES)
                and ("/" in s or "-" in s))

    def is_event(self, r):
        """A LARGER event. A one-off showcase whose teams each play once is not
        -- that is how neutral & neutral series get packaged."""
        if not r["stem"]:
            return False
        b = self.banner(r)
        s = r["stem"].lower()
        return (b["tourn"] or self.is_challenge(r["stem"]) or b["games"] >= 6
                or any(e in s for e in KNOWN_EVENTS))

    @staticmethod
    def nonconf(r):
        if r["confgame"] is not None:
            return not r["confgame"]
        return r["confs"][0] != r["confs"][1]

    @staticmethod
    def confmates(r):
        # same conference on paper, though ESPN may call the game non-conference
        return r["confs"][0] == r["confs"][1]

    def plain(self, r):
        return (r["type"] == 2 and not r["champ"] and not self.is_event(r)
                and self.nonconf(r) and r["state"] not in DEAD)

    def host(self, r):
        # whose game it really is: None for a true neutral site
        if r["neutral"] and r["city"] != self.home_city.get((r["sport"], r["home"])):
            return None
        return r["home"]

    @staticmethod
    def site(r):
        return ("N", r["city"]) if r["neutral"] else ("H", r["home"])


def classify(arch, recs, by_pair, rule):
    res = collections.OrderedDict()
    excluded = []

    def put(cls, sport, pair, runkey, legs):
        res.setdefault((cls, sport, pair, runkey), legs)

    for g in arch:
        r = recs.get((g["sport"], g["id"]))
        if not r or not rule.nonconf(r):
            continue
        pair = frozenset((r["home"], r["away"]))
        allg = sorted(by_pair[(g["sport"], pair)], key=lambda q: q["date"])
        if not rule.plain(r):
            adj = [q for q in allg if rule.plain(q) and abs(q["season"] - r["season"]) == 1]
            if adj:
                excluded.append([r] + adj)
            continue
        P = collections.defaultdict(list)
        for q in allg:
            if rule.plain(q):
                P[q["season"]].append(q)

        if len([s for s in P if FIRST <= s < LAST]) >= ANNUAL_MIN:
            legs = [q for q in allg if rule.plain(q) or q["state"] in DEAD]
            if any(rule.confmates(q) for q in legs if rule.plain(q)):
                put("UNSURE: annual, but conference-mates in some seasons", g["sport"], pair, None, legs)
            else:
                put("ANNUAL", g["sport"], pair, None, legs)
            continue

        run = [r["season"]]
        s = r["season"] - 1
        while s in P:
            run.insert(0, s)
            s -= 1
        s = r["season"] + 1
        while s in P:
            run.append(s)
            s += 1
        legs = [q for s in run for q in P[s]]
        if any(len(P[s]) > 1 for s in run):
            put("UNSURE: two plain meetings in one season", g["sport"], pair, tuple(run), legs)
            continue
        if len(run) >= 3:
            put("UNSURE: %d straight seasons (a longer series, or annual?)" % len(run),
                g["sport"], pair, tuple(run), legs)
            continue
        if len(run) == 2:
            a, b = legs
            ha, hb = rule.host(a), rule.host(b)
            if any(rule.confmates(q) for q in legs):
                put("UNSURE: same conference, ESPN lists it non-conference", g["sport"], pair, tuple(run), legs)
            elif rule.site(a) == rule.site(b):
                put("UNSURE: consecutive seasons at the SAME site", g["sport"], pair, tuple(run), legs)
            elif ha is not None and ha == hb:
                put("UNSURE: the same team hosts both meetings", g["sport"], pair, tuple(run), legs)
            elif (ha is None) != (hb is None):
                put("Home & Neutral?: one neutral-site meeting, one campus meeting", g["sport"], pair, tuple(run), legs)
            elif ha is None and hb is None:
                put("Neutral & Neutral?: both meetings at neutral sites", g["sport"], pair, tuple(run), legs)
            else:
                put("Home & Home", g["sport"], pair, tuple(run), legs)
            continue

        # a run of one: no plain meeting in an adjacent season
        if rule.confmates(r):
            continue
        # ...but a home & home can be stretched over a gap year: Villanova-UCLA
        # basketball played 2021-22 and 2023-24 (his call 2026-09-11)
        gap = [q for s in (r["season"] - 2, r["season"] + 2) for q in P.get(s, [])
               if rule.site(q) != rule.site(r)]
        if gap:
            legs = sorted([r, gap[0]], key=lambda q: q["date"])
            put("Home & Home?: a season apart", g["sport"], pair,
                tuple(q["season"] for q in legs), legs)
            continue
        nxt = [q for q in allg if q["season"] == r["season"] + 1]
        if g["sport"] == "CBB" and not nxt and not harvest.season_over("CBB", r["season"] + 1):
            put("UNSURE: next season's schedule is only partly published (possible first leg)",
                g["sport"], pair, (r["season"],), [r])
        elif g["sport"] == "CFB" and r["season"] == LAST:
            put("UNSURE: next season's schedule is not loaded (possible first leg)",
                g["sport"], pair, (r["season"],), [r])
    return res, excluded


# ---------------------------------------------------------------- report

def main():
    data = json.load(io.open(GAMES, encoding="utf-8"))
    arch, teams = data["games"], data["teams"]
    arch_ids = {(g["sport"], g["id"]) for g in arch}
    tags = {}
    if os.path.exists(TAGS):
        tags = json.load(io.open(TAGS, encoding="utf-8")) or {}

    recs, by_pair, banner_games = load_all()
    rule = Rule(recs, banner_games)
    res, excluded = classify(arch, recs, by_pair, rule)

    def nm(tid, loc):
        return teams[tid]["short"] if tid in teams else rules.display_name(loc)

    def slabel(sport, y):
        return str(y) if sport == "CFB" else "%d-%s" % (y, str(y + 1)[2:])

    def series_tags(r):
        return [t for t in (tags.get(r["id"], {}).get("tags") or []) if t in SERIES_TAGS]

    def leg(r):
        where = r["venue"] + ", " + r["city"] + (" [neutral]" if r["neutral"] else "")
        mark = ""
        if (r["sport"], r["id"]) in arch_ids:
            done = series_tags(r)
            mark = "  <ARCHIVE" + (": tagged " + "/".join(done) if done else "") + ">"
        elif r["state"] == "STATUS_SCHEDULED":
            mark = "  (scheduled)"
        elif r["state"] in DEAD:
            mark = "  (" + r["state"].replace("STATUS_", "").lower() + ")"
        note = ("  note: " + r["stem"]) if r["stem"] else ""
        return "    %-8s %s  %s at %s  @ %s%s%s" % (
            slabel(r["sport"], r["season"]), r["date"].strftime("%m/%d/%y"),
            nm(r["away"], r["aloc"]), nm(r["home"], r["hloc"]), where, note, mark)

    def untagged(legs):
        return [q for q in legs if (q["sport"], q["id"]) in arch_ids and not series_tags(q)]

    # a pair he ruled OUT (seed_series.NOT_SERIES) carries no tag on purpose
    ruled_out = {(s, frozenset((a, b))) for s, a, b, _pair, _why in seed_series.NOT_SERIES}

    def needs_ruling(k, legs):
        return (k[1], k[2]) not in ruled_out and bool(untagged(legs))

    order = ["Home & Home", "Neutral & Neutral?: both meetings at neutral sites",
             "Home & Neutral?: one neutral-site meeting, one campus meeting",
             "Home & Home?: a season apart", "ANNUAL"]
    classes = order + sorted({k[0] for k in res} - set(order))
    lines = [
        "SERIES REVIEW  --  generated " + dt.date.today().isoformat(),
        "",
        "Rule: non-conference, regular season, consecutive seasons, different sites, and neither",
        "meeting part of a LARGER event (a tournament, a conference challenge, or a recurring event",
        "like the Champions Classic). Annual = %d+ plain meetings in %d-%d." % (ANNUAL_MIN, FIRST, LAST - 1),
        "<ARCHIVE> marks the games on your tabs; 'tagged' means seed_series.py already covers it.",
        "Rulings go into seed_series.py (SERIES by game id, ANNUAL by team pair).",
        "",
        "SUMMARY  (pairs; 'new' = an archive game with no series tag, in a pair not ruled out)",
    ]
    for cls in classes:
        items = [(k, v) for k, v in res.items() if k[0] == cls]
        new = sum(1 for k, v in items if needs_ruling(k, v))
        lines.append("  %-80s %3d  (%d new)" % (cls, len(items), new))
    lines.append("  NOT a series because one meeting was a larger event: %d" % len(excluded))

    for sport in ("CFB", "CBB"):
        lines += ["", "#" * 100, "#  " + sport, "#" * 100]
        for cls in classes:
            items = [(k, v) for k, v in res.items() if k[0] == cls and k[1] == sport]
            if not items:
                continue
            # pairs still needing a ruling first
            items.sort(key=lambda kv: (not needs_ruling(kv[0], kv[1]), min(q["date"] for q in kv[1])))
            lines += ["", "== %s  (%d) ==" % (cls, len(items))]
            for k, v in items:
                legs = sorted(v, key=lambda q: q["date"])
                done = ("   (ruled out)" if (k[1], k[2]) in ruled_out
                        else "" if untagged(legs) else "   (already tagged)")
                lines.append("  %s / %s%s" % (nm(legs[0]["away"], legs[0]["aloc"]),
                                              nm(legs[0]["home"], legs[0]["hloc"]), done))
                lines += [leg(q) for q in legs]
        ex = [e for e in excluded if e[0]["sport"] == sport]
        if ex:
            lines += ["", "== NOT a series: one meeting was a larger event  (%d, to check the rule) ==" % len(ex)]
            for e in sorted(ex, key=lambda e: e[0]["date"]):
                lines += [leg(q) for q in sorted(e, key=lambda q: q["date"])]
                lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(NL.join(lines) + NL)
    print(NL.join(lines[8:9 + len(classes) + 1]))
    print("-> " + OUT)


if __name__ == "__main__":
    main()
