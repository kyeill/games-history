"""Series tags: home & home, neutral & neutral, home & neutral, and annual.

His tags, 2026-09-11, merged into docs/tags.json the way seed_tags.py merges
the show tags -- added, never overwritten, so a tag saved from his phone
survives a re-run.

  H&H     home & home: each school hosts once, in consecutive seasons
  N&N     neutral & neutral: each school's "home" leg is in a neutral city
          (Michigan-Wake Forest basketball: Greensboro, then Detroit)
  H&N     one campus meeting and one neutral one (Auburn-Baylor: Waco, then
          the Aflac Kickoff in Atlanta)
  Annual  a perpetual series (Notre Dame-USC)

SERIES lists every H&H, N&N and H&N game BY ID. They came from a scan of the
2019-2026 ESPN schedules -- non-conference, regular season, consecutive
seasons, different sites, and neither meeting part of a LARGER event (a
tournament, a conference challenge, or a recurring event like the Champions
Classic) -- and he then ruled on every borderline case. So this is a record
of decisions, not a rule to re-run: a new season's series need the same
review. NOTES.md has the scan's traps.

ANNUAL is by PAIR instead, because an annual series keeps producing games:
every regular-season meeting in the archive gets the tag, including ones that
arrive in a later harvest. Notre Dame-Stanford has none in the archive yet.

    python seed_series.py            merge into docs/tags.json
    python seed_series.py --dry-run  report only
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GAMES = os.path.join(HERE, "output", "games.json")
TAGS = os.path.join(HERE, "docs", "tags.json")
SERIES_TAGS = ("H&H", "N&N", "H&N", "Annual")

SERIES = [
    # ESPN game id, tag, the game
    # --- home & home
    ("401371253", "H&H", "CBB 2021-22 Texas at Gonzaga"),
    ("401488384", "H&H", "CBB 2022-23 Alabama at Houston"),
    ("401482989", "H&H", "CBB 2022-23 Houston at Virginia"),
    ("401483279", "H&H", "CBB 2022-23 Indiana at Kansas"),
    ("401497506", "H&H", "CBB 2022-23 Kentucky at Gonzaga"),
    ("401483227", "H&H", "CBB 2022-23 Tennessee at Arizona"),
    ("401483362", "H&H", "CBB 2022-23 UCLA at Maryland"),
    ("401575521", "H&H", "CBB 2023-24 Illinois at Tennessee"),
    ("401584414", "H&H", "CBB 2023-24 Wisconsin at Arizona"),
    ("401707979", "H&H", "CBB 2024-25 Alabama at Purdue"),
    ("401715358", "H&H", "CBB 2024-25 Ohio State at Texas A&M"),
    ("401707980", "H&H", "CBB 2024-25 Purdue at Marquette"),
    ("401812789", "H&H", "CBB 2025-26 Arizona at Connecticut"),
    ("401819877", "H&H", "CBB 2025-26 Iowa State at Purdue"),
    ("401812262", "H&H", "CBB 2025-26 Purdue at Alabama"),
    ("401811097", "H&H", "CBB 2025-26 Texas Tech at Illinois"),
    ("401282070", "H&H", "CFB 2021    Auburn at Penn State"),
    ("401309913", "H&H", "CFB 2021    Boise State at Brigham Young"),
    ("401282059", "H&H", "CFB 2021    Florida at South Florida"),
    ("401282798", "H&H", "CFB 2021    Nebraska at Oklahoma"),
    ("401403868", "H&H", "CFB 2022    Alabama at Texas"),
    ("401404130", "H&H", "CFB 2022    Clemson at Notre Dame"),
    ("401403994", "H&H", "CFB 2022    Michigan State at Washington"),
    ("401404126", "H&H", "CFB 2022    Notre Dame at North Carolina"),
    ("401404124", "H&H", "CFB 2022    Notre Dame at Ohio State"),
    ("401404070", "H&H", "CFB 2022    Oklahoma at Nebraska"),
    ("401403886", "H&H", "CFB 2022    Ole Miss at Georgia Tech"),
    ("401403877", "H&H", "CFB 2022    Tennessee at Pittsburgh"),
    ("401403857", "H&H", "CFB 2022    Utah at Florida"),
    ("401520244", "H&H", "CFB 2023    Alabama at South Florida"),
    ("401520200", "H&H", "CFB 2023    Charlotte at Maryland"),
    ("401524007", "H&H", "CFB 2023    Colorado State at Colorado"),
    ("401523994", "H&H", "CFB 2023    Colorado at Texas Christian"),
    ("401520188", "H&H", "CFB 2023    Nebraska at Colorado"),
    ("401525441", "H&H", "CFB 2023    Notre Dame at Clemson"),
    ("401525439", "H&H", "CFB 2023    Notre Dame at Louisville"),
    ("401521330", "H&H", "CFB 2023    Ohio State at Notre Dame"),
    ("401520242", "H&H", "CFB 2023    Syracuse at Purdue"),
    ("401520201", "H&H", "CFB 2023    Texas A&M at Miami"),
    ("401520183", "H&H", "CFB 2023    Texas at Alabama"),
    ("401520169", "H&H", "CFB 2023    West Virginia at Penn State"),
    ("401520217", "H&H", "CFB 2023    Wisconsin at Washington State"),
    ("401628350", "H&H", "CFB 2024    Alabama at Wisconsin"),
    ("401628467", "H&H", "CFB 2024    Colorado at Nebraska"),
    ("401635533", "H&H", "CFB 2024    Duke at Northwestern"),
    ("401628322", "H&H", "CFB 2024    Miami at Florida"),
    ("401628978", "H&H", "CFB 2024    Notre Dame at Purdue"),
    ("401628332", "H&H", "CFB 2024    Notre Dame at Texas A&M"),
    ("401628457", "H&H", "CFB 2024    Penn State at West Virginia"),
    ("401752665", "H&H", "CFB 2025    Alabama at Florida State"),
    ("401752816", "H&H", "CFB 2025    Boston College at Michigan State"),
    ("401752709", "H&H", "CFB 2025    Florida at Miami"),
    ("401752671", "H&H", "CFB 2025    Louisiana State at Clemson"),
    ("401752690", "H&H", "CFB 2025    Michigan at Oklahoma"),
    ("401754522", "H&H", "CFB 2025    Notre Dame at Miami"),
    ("401752824", "H&H", "CFB 2025    Oklahoma State at Oregon"),
    ("401752707", "H&H", "CFB 2025    Texas A&M at Notre Dame"),
    ("401752677", "H&H", "CFB 2025    Texas at Ohio State"),
    ("401752696", "H&H", "CFB 2025    Wisconsin at Alabama"),
    ("401856660", "H&H", "CFB 2026    Clemson at Louisiana State"),
    # --- neutral & neutral
    ("401591373", "N&N", "CBB 2023-24 Connecticut at Gonzaga"),
    ("401710007", "N&N", "CBB 2024-25 Gonzaga at UCLA"),
    ("401707850", "N&N", "CBB 2024-25 Illinois at Alabama"),
    ("401714913", "N&N", "CBB 2024-25 Kentucky at Gonzaga"),
    ("401707982", "N&N", "CBB 2024-25 Purdue at Auburn"),
    ("401811098", "N&N", "CBB 2025-26 Alabama at Illinois"),
    ("401813759", "N&N", "CBB 2025-26 Arizona at UCLA"),
    ("401823482", "N&N", "CBB 2025-26 Auburn at Purdue"),
    ("401811096", "N&N", "CBB 2025-26 Illinois at Connecticut"),
    ("401811099", "N&N", "CBB 2025-26 Illinois at Tennessee"),
    ("401813763", "N&N", "CBB 2025-26 UCLA at Gonzaga"),
    ("401819836", "N&N", "CBB 2025-26 Wisconsin at Brigham Young"),
    ("401520182", "N&N", "CFB 2023    Louisiana State at Florida State"),
    # --- home & neutral
    ("401826785", "H&N", "CBB 2025-26 Arkansas at Michigan State"),
    ("401752667", "H&N", "CFB 2025    Auburn at Baylor"),
    ("401856636", "H&N", "CFB 2026    Baylor at Auburn"),
]

ANNUAL = [
    # sport, ESPN team id, ESPN team id, the series
    ("CFB", "30", "87", "Southern California / Notre Dame"),
    ("CFB", "87", "2426", "Notre Dame / Navy"),
    ("CFB", "24", "87", "Stanford / Notre Dame"),
    ("CFB", "66", "2294", "Iowa State / Iowa"),
    ("CFB", "59", "61", "Georgia Tech / Georgia"),
    ("CFB", "52", "57", "Florida State / Florida"),
    ("CFB", "228", "2579", "Clemson / South Carolina"),
    ("CFB", "96", "97", "Kentucky / Louisville"),
    ("CFB", "221", "277", "Pittsburgh / West Virginia"),
    ("CBB", "269", "275", "Marquette / Wisconsin"),
    ("CBB", "142", "2305", "Missouri / Kansas"),
]


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

    pairs = {(s, frozenset((a, b))): name for s, a, b, name in ANNUAL}
    annual = dict.fromkeys(pairs.values(), 0)
    for g in data["games"]:
        name = pairs.get((g["sport"], frozenset(t["id"] for t in g["teams"])))
        if name and not g["champ"]:
            want.setdefault(g["id"], set()).add("Annual")
            annual[name] += 1

    print("%d series rows: %d tagged, %d not" % (len(SERIES), len(SERIES) - len(misses), len(misses)))
    for label, tag, why in misses:
        print("   NOT TAGGED  %-4s %-50s [%s]" % (tag, label, why))
    print("annual pairs:")
    for name, n in annual.items():
        print("   %-36s %d game%s" % (name, n, "" if n == 1 else "s"))
    if dry:
        return

    tags = {}
    if os.path.exists(TAGS):
        tags = json.load(open(TAGS, encoding="utf-8")) or {}

    # take series tags back off a game that has left the archive or is
    # postseason -- unless he added the game by hand, which carries its own
    # game payload
    stripped = 0
    for gid, entry in list(tags.items()):
        g = games.get(gid)
        gone = g is None and not entry.get("game")
        if not gone and (not g or not g["champ"]):
            continue
        cur = [t for t in (entry.get("tags") or []) if t not in SERIES_TAGS]
        if cur != (entry.get("tags") or []):
            stripped += 1
            if cur:
                entry["tags"] = cur
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
    print("%d tags added, %d stripped, %d games in tags.json" % (added, stripped, len(tags)))


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
