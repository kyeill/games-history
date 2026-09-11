"""Series and scheduling tags: Home & Home, Neutral & Neutral, Home & Neutral,
Annual, and Buy Game.

His tags (2026-09-11), merged into docs/tags.json the way seed_tags.py merges
the show tags -- added, never overwritten, so a tag saved from his phone
survives a re-run.

  Home & Home        each school hosts once, in consecutive seasons
  Neutral & Neutral  each school's "home" leg is in a neutral city
                     (Michigan-Wake Forest basketball: Greensboro, then Detroit)
  Home & Neutral     one campus meeting and one neutral one (Auburn-Baylor:
                     Waco, then the Aflac Kickoff in Atlanta)
  Annual             a perpetual non-conference series (Notre Dame-USC)
  Buy Game           a one-way paid visit (Marshall at Notre Dame, 2022)

The names are spelled out. They began as H&H / N&N / H&N, and RENAMED rewrites
any of those still in tags.json -- an old cached copy of the app could write one.

SERIES lists every Home & Home, Neutral & Neutral and Home & Neutral game BY
ID. They came from series_scan.py -- non-conference, regular season,
consecutive seasons, different sites, and neither meeting part of a LARGER
event (a tournament, a conference challenge, or a recurring event like the
Champions Classic) -- and he then ruled on every borderline case. So this is a
record of decisions, not a rule to re-run. NOTES.md has the scan's traps.

ANNUAL is by PAIR instead, because an annual series keeps producing games:
every regular-season NON-CONFERENCE meeting in the archive gets the tag,
including ones a later harvest brings in. Non-conference matters for
Oregon-Oregon State and Washington-Washington State, which only became
non-conference series when Oregon and Washington left the Pac-12 in 2024 --
and ANNUAL_SINCE starts both at 2024, his call.

NOT_SERIES records the pairs he ruled OUT: a run strips any series tag from
their games, and series_scan.py stops asking about them.

BUY_GAMES is by id, from him.

    python seed_series.py            merge into docs/tags.json
    python seed_series.py --dry-run  report only
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GAMES = os.path.join(HERE, "output", "games.json")
TAGS = os.path.join(HERE, "docs", "tags.json")
SERIES_TAGS = ("Home & Home", "Neutral & Neutral", "Home & Neutral", "Annual")
BUY_TAG = "Buy Game"
MANAGED = SERIES_TAGS + (BUY_TAG,)
RENAMED = {"H&H": "Home & Home", "N&N": "Neutral & Neutral", "H&N": "Home & Neutral"}

SERIES = [
    # ESPN game id, tag, the game
    # --- Home & Home
    ("401371253", "Home & Home", "CBB 2021-22 Texas at Gonzaga"),
    ("401488384", "Home & Home", "CBB 2022-23 Alabama at Houston"),
    ("401482989", "Home & Home", "CBB 2022-23 Houston at Virginia"),
    ("401483279", "Home & Home", "CBB 2022-23 Indiana at Kansas"),
    ("401497506", "Home & Home", "CBB 2022-23 Kentucky at Gonzaga"),
    ("401483227", "Home & Home", "CBB 2022-23 Tennessee at Arizona"),
    ("401483362", "Home & Home", "CBB 2022-23 UCLA at Maryland"),
    ("401575521", "Home & Home", "CBB 2023-24 Illinois at Tennessee"),
    ("401584414", "Home & Home", "CBB 2023-24 Wisconsin at Arizona"),
    ("401707979", "Home & Home", "CBB 2024-25 Alabama at Purdue"),
    ("401715358", "Home & Home", "CBB 2024-25 Ohio State at Texas A&M"),
    ("401707980", "Home & Home", "CBB 2024-25 Purdue at Marquette"),
    ("401812789", "Home & Home", "CBB 2025-26 Arizona at Connecticut"),
    ("401819877", "Home & Home", "CBB 2025-26 Iowa State at Purdue"),
    ("401812262", "Home & Home", "CBB 2025-26 Purdue at Alabama"),
    ("401811097", "Home & Home", "CBB 2025-26 Texas Tech at Illinois"),
    ("401282070", "Home & Home", "CFB 2021    Auburn at Penn State"),
    ("401309913", "Home & Home", "CFB 2021    Boise State at Brigham Young"),
    ("401282059", "Home & Home", "CFB 2021    Florida at South Florida"),
    ("401282798", "Home & Home", "CFB 2021    Nebraska at Oklahoma"),
    ("401403868", "Home & Home", "CFB 2022    Alabama at Texas"),
    ("401404130", "Home & Home", "CFB 2022    Clemson at Notre Dame"),
    ("401403994", "Home & Home", "CFB 2022    Michigan State at Washington"),
    ("401404126", "Home & Home", "CFB 2022    Notre Dame at North Carolina"),
    ("401404124", "Home & Home", "CFB 2022    Notre Dame at Ohio State"),
    ("401404070", "Home & Home", "CFB 2022    Oklahoma at Nebraska"),
    ("401403886", "Home & Home", "CFB 2022    Ole Miss at Georgia Tech"),
    ("401403877", "Home & Home", "CFB 2022    Tennessee at Pittsburgh"),
    ("401403857", "Home & Home", "CFB 2022    Utah at Florida"),
    ("401520244", "Home & Home", "CFB 2023    Alabama at South Florida"),
    ("401520200", "Home & Home", "CFB 2023    Charlotte at Maryland"),
    ("401524007", "Home & Home", "CFB 2023    Colorado State at Colorado"),
    ("401523994", "Home & Home", "CFB 2023    Colorado at Texas Christian"),
    ("401520188", "Home & Home", "CFB 2023    Nebraska at Colorado"),
    ("401525441", "Home & Home", "CFB 2023    Notre Dame at Clemson"),
    ("401525439", "Home & Home", "CFB 2023    Notre Dame at Louisville"),
    ("401521330", "Home & Home", "CFB 2023    Ohio State at Notre Dame"),
    ("401532573", "Home & Home", "CFB 2023    Oregon State at San José State"),
    ("401520242", "Home & Home", "CFB 2023    Syracuse at Purdue"),
    ("401520201", "Home & Home", "CFB 2023    Texas A&M at Miami"),
    ("401520183", "Home & Home", "CFB 2023    Texas at Alabama"),
    ("401520169", "Home & Home", "CFB 2023    West Virginia at Penn State"),
    ("401520217", "Home & Home", "CFB 2023    Wisconsin at Washington State"),
    ("401628350", "Home & Home", "CFB 2024    Alabama at Wisconsin"),
    ("401628467", "Home & Home", "CFB 2024    Colorado at Nebraska"),
    ("401635533", "Home & Home", "CFB 2024    Duke at Northwestern"),
    ("401628322", "Home & Home", "CFB 2024    Miami at Florida"),
    ("401628448", "Home & Home", "CFB 2024    North Carolina at Minnesota"),
    ("401628978", "Home & Home", "CFB 2024    Notre Dame at Purdue"),
    ("401628332", "Home & Home", "CFB 2024    Notre Dame at Texas A&M"),
    ("401628457", "Home & Home", "CFB 2024    Penn State at West Virginia"),
    ("401752665", "Home & Home", "CFB 2025    Alabama at Florida State"),
    ("401752816", "Home & Home", "CFB 2025    Boston College at Michigan State"),
    ("401752709", "Home & Home", "CFB 2025    Florida at Miami"),
    ("401752671", "Home & Home", "CFB 2025    Louisiana State at Clemson"),
    ("401752690", "Home & Home", "CFB 2025    Michigan at Oklahoma"),
    ("401754522", "Home & Home", "CFB 2025    Notre Dame at Miami"),
    ("401752824", "Home & Home", "CFB 2025    Oklahoma State at Oregon"),
    ("401752707", "Home & Home", "CFB 2025    Texas A&M at Notre Dame"),
    ("401752677", "Home & Home", "CFB 2025    Texas at Ohio State"),
    ("401752696", "Home & Home", "CFB 2025    Wisconsin at Alabama"),
    ("401856660", "Home & Home", "CFB 2026    Clemson at Louisiana State"),
    # its 2025-26 return (Kansas at North Carolina) sat in the empty opening
    # week harvest used to drop, so the scan never saw it (his call 2026-09-11)
    ("401700435", "Home & Home", "CBB 2024-25 North Carolina at Kansas"),
    # a season apart rather than back to back (his call 2026-09-11)
    ("401372032", "Home & Home", "CBB 2021-22 Villanova at UCLA"),
    # the other leg of a series he ruled, brought in by the new TV rules (2026-09-11)
    ("401575457", "Home & Home", "CBB 2023-24 Kansas at Indiana"),
    ("401575804", "Home & Home", "CBB 2023-24 UCLA at Villanova"),
    ("401707854", "Home & Home", "CBB 2024-25 Tennessee at Illinois"),
    # his rulings on the games the new TV rules brought in (2026-09-11)
    ("401577603", "Home & Home", "CBB 2023-24 Notre Dame at Marquette"),
    ("401577597", "Home & Home", "CBB 2023-24 Alabama at Creighton"),
    ("401715468", "Home & Home", "CBB 2024-25 Notre Dame at Georgetown"),
    ("401812794", "Home & Home", "CBB 2025-26 Texas at Connecticut"),
    ("401817514", "Home & Home", "CBB 2025-26 Maryland at Virginia"),
    ("401372112", "Home & Home", "CBB 2021-22 Arizona at Illinois"),
    # the other leg of a series he ruled, brought in by Rivals (2026-09-11)
    ("401520233", "Home & Home", "CFB 2023    Washington at Michigan State"),
    ("401575510", "Home & Home", "CBB 2023-24 Texas A&M at Ohio State"),
    # Rivals losses before 2021, from a scan of every rival loss since 2014 (2026-09-11)
    ("400816805", "Home & Home", "CBB 2015-16 Ohio State at Connecticut"),
    ("400915070", "Home & Home", "CBB 2016-17 Northeastern at Michigan State"),
    ("400547953", "Home & Home", "CFB 2014    Michigan State at Oregon"),
    ("400547826", "Home & Home", "CFB 2014    Virginia Tech at Ohio State"),
    ("400868946", "Home & Home", "CFB 2016    Notre Dame at Texas"),
    ("400934502", "Home & Home", "CFB 2017    Oklahoma at Ohio State"),
    ("400934581", "Home & Home", "CFB 2017    Notre Dame at Miami"),
    ("400868955", "Home & Home", "CFB 2016    Virginia Tech at Notre Dame"),
    ("400933845", "Home & Home", "CFB 2017    Georgia at Notre Dame"),
    ("401012727", "Home & Home", "CFB 2018    Michigan State at Arizona State"),
    # rival losses from 2019 on that the first Rivals scan missed (2026-09-11)
    ("401715410", "Home & Home", "CBB 2024-25 Pittsburgh at Ohio State"),
    ("401817447", "Home & Home", "CBB 2025-26 Ohio State at Pittsburgh"),
    ("401110800", "Home & Home", "CFB 2019    Notre Dame at Georgia"),
    ("401112227", "Home & Home", "CFB 2019    Notre Dame at Michigan"),
    ("401112214", "Home & Home", "CFB 2019    Arizona State at Michigan State"),
    ("401628490", "Home & Home", "CFB 2024    Michigan State at Boston College"),
    # --- Neutral & Neutral
    ("401591373", "Neutral & Neutral", "CBB 2023-24 Connecticut at Gonzaga"),
    ("401710007", "Neutral & Neutral", "CBB 2024-25 Gonzaga at UCLA"),
    ("401707850", "Neutral & Neutral", "CBB 2024-25 Illinois at Alabama"),
    ("401714913", "Neutral & Neutral", "CBB 2024-25 Kentucky at Gonzaga"),
    ("401707982", "Neutral & Neutral", "CBB 2024-25 Purdue at Auburn"),
    ("401811098", "Neutral & Neutral", "CBB 2025-26 Alabama at Illinois"),
    ("401813759", "Neutral & Neutral", "CBB 2025-26 Arizona at UCLA"),
    ("401823482", "Neutral & Neutral", "CBB 2025-26 Auburn at Purdue"),
    ("401811096", "Neutral & Neutral", "CBB 2025-26 Illinois at Connecticut"),
    ("401811099", "Neutral & Neutral", "CBB 2025-26 Illinois at Tennessee"),
    ("401813763", "Neutral & Neutral", "CBB 2025-26 UCLA at Gonzaga"),
    ("401819836", "Neutral & Neutral", "CBB 2025-26 Wisconsin at Brigham Young"),
    ("401403867", "Neutral & Neutral", "CFB 2022    Florida State at Louisiana State"),
    ("401520182", "Neutral & Neutral", "CFB 2023    Louisiana State at Florida State"),
    # the other leg of a series he ruled, brought in by the new TV rules (2026-09-11)
    ("401715614", "Neutral & Neutral", "CBB 2024-25 Gonzaga at Connecticut"),
    # his rulings on the games the new TV rules brought in (2026-09-11)
    ("401812266", "Neutral & Neutral", "CBB 2025-26 Arizona at Alabama"),
    ("401823567", "Neutral & Neutral", "CBB 2025-26 Wisconsin at Villanova"),
    # --- Home & Neutral
    ("401826785", "Home & Neutral", "CBB 2025-26 Arkansas at Michigan State"),
    ("401752667", "Home & Neutral", "CFB 2025    Auburn at Baylor"),
    ("401856636", "Home & Neutral", "CFB 2026    Baylor at Auburn"),
    # his rulings on the games the new TV rules brought in (2026-09-11)
    ("401827208", "Home & Neutral", "CBB 2025-26 Indiana at Kentucky"),
    ("401856766", "Home & Neutral", "CFB 2026    North Carolina at Texas Christian"),
    # Rivals losses before 2021, from a scan of every rival loss since 2014 (2026-09-11)
    ("400548302", "Home & Neutral", "CFB 2014    Notre Dame at Arizona State"),
]

ANNUAL = [
    # sport, ESPN team id, ESPN team id, the series
    ("CFB", "30", "87", "Southern California / Notre Dame"),
    ("CFB", "24", "87", "Stanford / Notre Dame"),
    ("CFB", "66", "2294", "Iowa State / Iowa"),
    ("CFB", "59", "61", "Georgia Tech / Georgia"),
    ("CFB", "52", "57", "Florida State / Florida"),
    ("CFB", "228", "2579", "Clemson / South Carolina"),
    ("CFB", "96", "97", "Kentucky / Louisville"),
    ("CFB", "221", "277", "Pittsburgh / West Virginia"),
    ("CBB", "269", "275", "Marquette / Wisconsin"),
    ("CBB", "142", "2305", "Missouri / Kansas"),
    ("CFB", "264", "265", "Washington / Washington State"),
    ("CFB", "204", "2483", "Oregon State / Oregon"),
    ("CBB", "183", "46", "Syracuse / Georgetown"),
    ("CBB", "164", "2550", "Rutgers / Seton Hall"),
]

# An annual series that only began in a given season (his call 2026-09-11).
ANNUAL_SINCE = {
    ("CFB", "264", "265"): 2024,     # Washington / Washington State
    ("CFB", "204", "2483"): 2024,    # Oregon State / Oregon
}

NOT_SERIES = [
    # sport, ESPN team id, ESPN team id, the pair, why he ruled it out
    ("CFB", "12", "2306", "Arizona / Kansas State", "same conference when played"),
    ("CFB", "258", "87", "Virginia / Notre Dame", "2019 and 2021 are not consecutive seasons"),
    ("CFB", "87", "2426", "Notre Dame / Navy", "he does not count it as an annual series"),
    ("CFB", "23", "30", "San José State / Southern California", "no return game (2026 Week 0)"),
    ("CFB", "275", "87", "Wisconsin / Notre Dame", "no return game (2026, Lambeau Field)"),
    ("CFB", "97", "145", "Louisville / Ole Miss", "no return game (2026 Music City Kickoff)"),
    ("CFB", "152", "87", "NC State / Notre Dame", "a season apart; he ignores it"),
    ("CFB", "221", "87", "Pittsburgh / Notre Dame", "a season apart; he ignores it"),
    ("CBB", "239", "2250", "Baylor / Gonzaga", "a season apart; he ignores it"),
    ("CBB", "150", "356", "Duke / Illinois", "a season apart; he ignores it"),
    ("CBB", "57", "201", "Florida / Oklahoma", "he rejects the home & neutral reading"),
    ("CBB", "2050", "282", "Ball State / Indiana State", "he does not count it as annual"),
    ("CBB", "2287", "2050", "Illinois State / Ball State", "three straight; skipped"),
    ("CBB", "2641", "150", "Texas Tech / Duke", "the same neutral site both years; skipped"),
]

BUY_GAMES = [
    # ESPN game id, the game
    ("401404125", "CFB 2022    Marshall at Notre Dame"),
    ("401403878", "CFB 2022    Appalachian State at Texas A&M"),
    ("401628977", "CFB 2024    Northern Illinois at Notre Dame"),
    ("401581835", "CBB 2023-24 James Madison at Michigan State"),
]


def pair_of(g):
    return (g["sport"], frozenset(t["id"] for t in g["teams"]))


def main(dry):
    data = json.load(open(GAMES, encoding="utf-8"))
    games = {g["id"]: g for g in data["games"]}

    want, misses = {}, []
    for gid, tag, label in SERIES:
        g = games.get(gid)
        if g is None:
            misses.append((label, tag, "not in archive"))
        elif g["champ"]:
            misses.append((label, tag, "postseason"))
        else:
            want.setdefault(gid, set()).add(tag)
    for gid, label in BUY_GAMES:
        if gid in games:
            want.setdefault(gid, set()).add(BUY_TAG)
        else:
            misses.append((label, BUY_TAG, "not in archive"))

    annual_pairs = {(s, frozenset((a, b))): name for s, a, b, name in ANNUAL}
    since = {(s, frozenset((a, b))): y for (s, a, b), y in ANNUAL_SINCE.items()}
    ruled_out = {(s, frozenset((a, b))) for s, a, b, _pair, _why in NOT_SERIES}
    annual = dict.fromkeys(annual_pairs.values(), 0)
    for g in data["games"]:
        key = pair_of(g)
        name = annual_pairs.get(key)
        non_conference = len({t["conf"] for t in g["teams"]}) == 2
        if (name and not g["champ"] and non_conference
                and g["season"] >= since.get(key, 0)):
            want.setdefault(g["id"], set()).add("Annual")
            annual[name] += 1

    print("%d series rows + %d buy games: %d not tagged"
          % (len(SERIES), len(BUY_GAMES), len(misses)))
    for label, tag, why in misses:
        print("   NOT TAGGED  %-18s %-48s [%s]" % (tag, label, why))
    print("annual pairs (non-conference meetings in the archive):")
    for name, n in annual.items():
        print("   %-36s %d" % (name, n))
    if dry:
        return

    tags = {}
    if os.path.exists(TAGS):
        tags = json.load(open(TAGS, encoding="utf-8")) or {}

    renamed = stripped = 0
    for gid, entry in list(tags.items()):
        cur = list(entry.get("tags") or [])
        new = []
        for t in cur:
            if t in RENAMED:
                t = RENAMED[t]
                renamed += 1
            if t not in new:
                new.append(t)
        g = games.get(gid)
        # a game that left the archive (unless he added it by hand, which
        # carries its own payload) or is postseason loses the tags managed
        # here; a game from a pair he ruled out loses its series tags
        if (g is None and not entry.get("game")) or (g and g["champ"]):
            kept = [t for t in new if t not in MANAGED]
        elif g and pair_of(g) in ruled_out:
            kept = [t for t in new if t not in SERIES_TAGS]
        else:
            kept = new
        stripped += len(new) - len(kept)
        if kept != cur:
            if kept:
                entry["tags"] = kept
            else:
                entry.pop("tags", None)
                if not entry:
                    tags.pop(gid)

    added = 0
    for gid, ts in want.items():
        entry = tags.setdefault(gid, {})
        cur = entry.get("tags") or []
        for t in sorted(ts):
            if t not in cur:
                cur.append(t)
                added += 1
        entry["tags"] = cur

    open(TAGS, "w", encoding="utf-8").write(json.dumps(tags, indent=1) + chr(10))
    print("%d tags added, %d renamed, %d stripped, %d games in tags.json"
          % (added, renamed, stripped, len(tags)))


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
