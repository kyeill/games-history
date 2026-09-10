"""Match a list of show locations to games and write them into docs/tags.json.

ESPN publishes nothing about where College GameDay or Big Noon Kickoff
broadcast from, so those tags are hand-supplied. This takes a table of
(date, visitor, host) rows -- Kyle's, from Wikipedia -- resolves each to an
ESPN game id, and MERGES the tag into the tags file the app writes.

Merging matters: `docs/tags.json` is live shared state. Anything already in it
(his own tagging, from any device) is preserved.

    python seed_tags.py --dry-run     show what would match
    python seed_tags.py               write it
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GAMES = os.path.join(HERE, "output", "games.json")
TAGS = os.path.join(HERE, "docs", "tags.json")

SHOW_TAGS = {"Big Noon Kickoff", "College GameDay"}

# (date, visitor, host) as the source table lists them. Names are matched
# loosely against ESPN's, so "USC" and "Southern Cal" both resolve.
BIG_NOON = [
    # 2021
    ("2021-09-02", "Ohio State", "Minnesota"),
    ("2021-09-04", "Penn State", "Wisconsin"),
    ("2021-09-11", "Oregon", "Ohio State"),
    ("2021-09-18", "Nebraska", "Oklahoma"),
    ("2021-09-25", "Wisconsin", "Notre Dame"),
    ("2021-10-02", "Michigan", "Wisconsin"),
    ("2021-10-09", "Penn State", "Iowa"),
    ("2021-10-30", "Michigan", "Michigan State"),
    ("2021-11-13", "Oklahoma", "Baylor"),
    ("2021-11-20", "Iowa State", "Oklahoma"),
    ("2021-11-27", "Ohio State", "Michigan"),
    ("2021-12-04", "Michigan", "Iowa"),
    # 2022
    ("2022-09-01", "Penn State", "Purdue"),
    ("2022-09-10", "Alabama", "Texas"),
    ("2022-09-17", "Oklahoma", "Nebraska"),
    ("2022-09-24", "Maryland", "Michigan"),
    ("2022-10-01", "Michigan", "Iowa"),
    ("2022-10-08", "Michigan", "Indiana"),
    ("2022-10-15", "Penn State", "Michigan"),
    ("2022-10-22", "Iowa", "Ohio State"),
    ("2022-10-29", "Ohio State", "Penn State"),
    ("2022-11-05", "Texas Tech", "TCU"),
    ("2022-11-12", "Indiana", "Ohio State"),
    ("2022-11-19", "TCU", "Baylor"),
    ("2022-11-26", "Michigan", "Ohio State"),
    ("2022-12-02", "Utah", "USC"),
    ("2022-12-03", "Purdue", "Michigan"),
    # 2023
    ("2023-08-31", "Nebraska", "Minnesota"),
    ("2023-09-02", "Colorado", "TCU"),
    ("2023-09-09", "Nebraska", "Colorado"),
    ("2023-09-16", "Colorado State", "Colorado"),
    ("2023-09-23", "Oklahoma", "Cincinnati"),
    ("2023-09-30", "USC", "Colorado"),
    ("2023-10-07", "Maryland", "Ohio State"),
    ("2023-10-14", "USC", "Notre Dame"),
    ("2023-10-21", "Penn State", "Ohio State"),
    ("2023-10-28", "Oklahoma", "Kansas"),
    ("2023-11-04", "Kansas State", "Texas"),
    ("2023-11-11", "Michigan", "Penn State"),
    ("2023-11-18", "Michigan", "Maryland"),
    ("2023-11-25", "Ohio State", "Michigan"),
    ("2023-12-02", "Michigan", "Iowa"),
    # 2024
    ("2024-08-31", "Penn State", "West Virginia"),
    ("2024-09-07", "Texas", "Michigan"),
    ("2024-09-14", "Alabama", "Wisconsin"),
    ("2024-09-21", "Marshall", "Ohio State"),
    ("2024-09-28", "Colorado", "UCF"),
    ("2024-10-05", "UCLA", "Penn State"),
    ("2024-10-12", "Arizona", "BYU"),
    ("2024-10-19", "Nebraska", "Indiana"),
    ("2024-10-26", "Nebraska", "Ohio State"),
    ("2024-11-02", "Ohio State", "Penn State"),
    ("2024-11-09", "Colorado", "Texas Tech"),
    ("2024-11-16", "Utah", "Colorado"),
    ("2024-11-23", "Indiana", "Ohio State"),
    ("2024-11-30", "Michigan", "Ohio State"),
    ("2024-12-06", "UNLV", "Boise State"),
    # 2025
    ("2025-08-30", "Texas", "Ohio State"),
    ("2025-09-06", "Iowa", "Iowa State"),
    ("2025-09-13", "Oregon", "Northwestern"),
    ("2025-09-20", "Texas Tech", "Utah"),
    ("2025-09-27", "USC", "Illinois"),
    ("2025-10-04", "Wisconsin", "Michigan"),
    ("2025-10-11", "Ohio State", "Illinois"),
    ("2025-10-18", "Utah", "BYU"),
    ("2025-10-25", "UCLA", "Indiana"),
    ("2025-11-01", "Penn State", "Ohio State"),
    ("2025-11-08", "Oregon", "Iowa"),
    ("2025-11-15", "Michigan", "Northwestern"),
    ("2025-11-22", "BYU", "Cincinnati"),
    ("2025-11-29", "Ohio State", "Michigan"),
    ("2025-12-06", "Indiana", "Ohio State"),
    # 2026 -- only games already played
    ("2026-09-05", "North Texas", "Indiana"),
]

GAMEDAY_CFB = [
    # Regular season only -- conference championship games, bowls, the CFP,
    # FCS games, studio shows and the NFL draft are all left out.
    ("2021-09-04", "Georgia", "Clemson"), ("2021-09-11", "Iowa", "Iowa State"),
    ("2021-09-18", "Auburn", "Penn State"), ("2021-09-25", "Notre Dame", "Wisconsin"),
    ("2021-10-02", "Arkansas", "Georgia"), ("2021-10-09", "Oklahoma", "Texas"),
    ("2021-10-16", "Kentucky", "Georgia"), ("2021-10-23", "Oregon", "UCLA"),
    ("2021-10-30", "Michigan", "Michigan State"), ("2021-11-06", "Tulsa", "Cincinnati"),
    ("2021-11-13", "Texas A&M", "Ole Miss"), ("2021-11-20", "Michigan State", "Ohio State"),
    ("2021-11-27", "Ohio State", "Michigan"),
    ("2022-09-01", "West Virginia", "Pittsburgh"), ("2022-09-03", "Notre Dame", "Ohio State"),
    ("2022-09-10", "Alabama", "Texas"), ("2022-09-17", "Troy", "Appalachian State"),
    ("2022-09-24", "Florida", "Tennessee"), ("2022-10-01", "NC State", "Clemson"),
    ("2022-10-08", "TCU", "Kansas"), ("2022-10-15", "Alabama", "Tennessee"),
    ("2022-10-22", "UCLA", "Oregon"), ("2022-11-05", "Tennessee", "Georgia"),
    ("2022-11-12", "TCU", "Texas"), ("2022-11-26", "Michigan", "Ohio State"),
    ("2023-09-02", "North Carolina", "South Carolina"), ("2023-09-09", "Texas", "Alabama"),
    ("2023-09-16", "Colorado State", "Colorado"), ("2023-09-23", "Ohio State", "Notre Dame"),
    ("2023-09-30", "Notre Dame", "Duke"), ("2023-10-07", "Oklahoma", "Texas"),
    ("2023-10-14", "Oregon", "Washington"), ("2023-10-21", "Penn State", "Ohio State"),
    ("2023-10-28", "Oregon", "Utah"), ("2023-11-04", "LSU", "Alabama"),
    ("2023-11-11", "Ole Miss", "Georgia"), ("2023-11-18", "Appalachian State", "James Madison"),
    ("2023-11-25", "Ohio State", "Michigan"),
    ("2024-08-24", "Florida State", "Georgia Tech"), ("2024-08-31", "Notre Dame", "Texas A&M"),
    ("2024-09-07", "Texas", "Michigan"), ("2024-09-14", "LSU", "South Carolina"),
    ("2024-09-21", "Tennessee", "Oklahoma"), ("2024-09-28", "Georgia", "Alabama"),
    ("2024-10-05", "Miami", "California"), ("2024-10-12", "Ohio State", "Oregon"),
    ("2024-10-19", "Georgia", "Texas"), ("2024-10-26", "Washington", "Indiana"),
    ("2024-11-02", "Ohio State", "Penn State"), ("2024-11-09", "Alabama", "LSU"),
    ("2024-11-16", "Tennessee", "Georgia"), ("2024-11-23", "Indiana", "Ohio State"),
    ("2024-11-30", "Texas", "Texas A&M"),
    ("2025-08-30", "Texas", "Ohio State"), ("2025-09-06", "Michigan", "Oklahoma"),
    ("2025-09-13", "Georgia", "Tennessee"), ("2025-09-20", "Florida", "Miami"),
    ("2025-09-27", "Oregon", "Penn State"), ("2025-10-04", "Vanderbilt", "Alabama"),
    ("2025-10-11", "Indiana", "Oregon"), ("2025-10-18", "Ole Miss", "Georgia"),
    ("2025-10-25", "Missouri", "Vanderbilt"), ("2025-11-01", "Cincinnati", "Utah"),
    ("2025-11-08", "BYU", "Texas Tech"), ("2025-11-15", "Notre Dame", "Pittsburgh"),
    ("2025-11-22", "USC", "Oregon"), ("2025-11-29", "Ohio State", "Michigan"),
    ("2026-09-05", "Clemson", "LSU"),
]

GAMEDAY_CBB = [
    # Regular season only -- conference tournaments and the Final Four are out.
    ("2022-01-29", "Kentucky", "Kansas"), ("2022-02-05", "Duke", "North Carolina"),
    ("2022-02-12", "Texas A&M", "Auburn"), ("2022-02-19", "Oregon", "Arizona"),
    ("2022-02-26", "Kansas", "Baylor"), ("2022-03-05", "North Carolina", "Duke"),
    ("2023-01-28", "Texas", "Tennessee"), ("2023-02-04", "North Carolina", "Duke"),
    ("2023-02-11", "Alabama", "Auburn"), ("2023-02-18", "Baylor", "Kansas"),
    ("2023-02-25", "Saint Mary's", "Gonzaga"), ("2023-03-04", "Duke", "North Carolina"),
    ("2024-01-27", "Kentucky", "Arkansas"), ("2024-02-03", "Duke", "North Carolina"),
    ("2024-02-10", "Baylor", "Kansas"), ("2024-02-17", "Kentucky", "Auburn"),
    ("2024-02-24", "Villanova", "UConn"), ("2024-03-02", "Tennessee", "Alabama"),
    ("2024-03-09", "North Carolina", "Duke"),
    ("2025-01-25", "Tennessee", "Auburn"), ("2025-02-01", "North Carolina", "Duke"),
    ("2025-02-08", "TCU", "Iowa State"), ("2025-02-15", "Auburn", "Alabama"),
    ("2025-02-22", "Iowa State", "Houston"), ("2025-03-01", "Texas A&M", "Florida"),
    ("2025-03-08", "Duke", "North Carolina"),
    ("2025-11-19", "Michigan State", "Kentucky"), ("2025-11-19", "Kansas", "Duke"),
    ("2026-01-24", "Houston", "Texas Tech"), ("2026-01-31", "BYU", "Kansas"),
    ("2026-02-07", "Duke", "North Carolina"), ("2026-02-14", "Texas Tech", "Arizona"),
    ("2026-02-21", "Michigan", "Duke"), ("2026-02-28", "Arkansas", "Florida"),
    ("2026-03-07", "North Carolina", "Duke"),
]

TABLES = [("Big Noon Kickoff", "CFB", BIG_NOON),
          ("College GameDay", "CFB", GAMEDAY_CFB),
          ("College GameDay", "CBB", GAMEDAY_CBB)]

# Names are normalised through rules.display_name, so the source table's
# "UConn" and the archive's "Connecticut" resolve to the same thing -- and so
# do BYU/Brigham Young, TCU/Texas Christian, USC/Southern Cal and the rest.
import rules


def norm(n):
    return rules.display_name(n).lower().replace(".", "").strip()


def main(dry):
    data = json.load(open(GAMES, encoding="utf-8"))
    teams = data["teams"]
    by_date = {}
    for g in data["games"]:
        by_date.setdefault((g["sport"], g["date"]), []).append(g)

    resolved, misses = {}, []
    for tag, sport, rows in TABLES:
        for date, visitor, host in rows:
            want = {norm(visitor), norm(host)}
            found = None
            # a late kickoff shifts the Eastern date, so look either side
            for d in (date, _shift(date, -1), _shift(date, 1)):
                for g in by_date.get((sport, d), []):
                    if {norm(teams[t["id"]]["short"]) for t in g["teams"]} == want:
                        found = g
                        break
                if found:
                    break
            if found is None:
                misses.append((tag, sport, date, visitor, host, "not in archive"))
            elif found["champ"]:
                # he does not want the shows tagged on postseason games
                misses.append((tag, sport, date, visitor, host, "postseason"))
            else:
                resolved.setdefault(found["id"], set()).add(tag)

    total = sum(len(r) for _, _, r in TABLES)
    print("%d rows: %d games resolved, %d not tagged"
          % (total, len(resolved), len(misses)))
    if misses:
        print("")
        print("NOT TAGGED")
        for tag, sport, date, v, h, why in sorted(misses, key=lambda m: m[2]):
            print("   %-4s %s  %-20s at %-20s  %-14s [%s]"
                  % (sport, date, v, h, why, tag))
    if dry:
        return

    tags = {}
    if os.path.exists(TAGS):
        tags = json.load(open(TAGS, encoding="utf-8")) or {}

    # an earlier run tagged conference championship games; take those back off
    ids = {g["id"]: g for g in data["games"]}
    stripped = 0
    for gid, entry in list(tags.items()):
        g = ids.get(gid)
        # strip a show tag from a postseason game, and from any game that has
        # since left the archive -- unless he added it by hand, which carries
        # its own game payload
        gone = g is None and not entry.get("game")
        if not gone and (not g or not g["champ"]):
            continue
        cur = [t for t in (entry.get("tags") or []) if t not in SHOW_TAGS]
        if cur != (entry.get("tags") or []):
            stripped += 1
            if cur:
                entry["tags"] = cur
            else:
                entry.pop("tags", None)
                if not entry:
                    tags.pop(gid)

    added = 0
    for gid, want in resolved.items():
        entry = tags.setdefault(gid, {})
        cur = entry.get("tags") or []
        for t in sorted(want):
            if t not in cur:
                cur.append(t)
                added += 1
        entry["tags"] = cur

    out = json.dumps(tags, indent=1) + chr(10)
    open(TAGS, "w", encoding="utf-8").write(out)
    print("")
    print("%d tags added, %d postseason tags stripped, %d games in tags.json"
          % (added, stripped, len(tags)))


def _shift(d, days):
    import datetime as dt
    return (dt.date.fromisoformat(d) + dt.timedelta(days=days)).isoformat()


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
