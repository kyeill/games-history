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

TAG = "Big Noon Kickoff"

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

# the source table's names against ESPN's `location`
ALIAS = {
    "USC": "Southern Cal", "BYU": "Brigham Young", "TCU": "Texas Christian",
    "UCF": "Central Florida", "UNLV": "Unlv", "UCLA": "Ucla",
    "LSU": "Louisiana State", "SMU": "Southern Methodist",
    "USF": "South Florida",
}


def norm(n):
    return ALIAS.get(n, n).lower().replace(".", "").strip()


def main(dry):
    data = json.load(open(GAMES, encoding="utf-8"))
    teams = data["teams"]
    by_date = {}
    for g in data["games"]:
        if g["sport"] != "CFB":
            continue
        by_date.setdefault(g["date"], []).append(g)

    hits, misses = [], []
    for date, visitor, host in BIG_NOON:
        want = {norm(visitor), norm(host)}
        found = None
        # the show's date and the game's Eastern date can differ by one for a
        # late kickoff, so look either side
        for d in (date, _shift(date, -1), _shift(date, 1)):
            for g in by_date.get(d, []):
                got = {norm(teams[t["id"]]["short"]) for t in g["teams"]}
                if got == want:
                    found = g
                    break
            if found:
                break
        (hits if found else misses).append((date, visitor, host, found))

    print("%d rows: %d matched, %d not in the archive"
          % (len(BIG_NOON), len(hits), len(misses)))
    if misses:
        print("\nNOT MATCHED (game is not in the archive):")
        for date, v, h, _ in misses:
            print("   %s  %s at %s" % (date, v, h))
    if dry:
        return

    tags = {}
    if os.path.exists(TAGS):
        tags = json.load(open(TAGS, encoding="utf-8")) or {}
    added = 0
    for _, _, _, g in hits:
        entry = tags.setdefault(g["id"], {})
        cur = entry.get("tags") or []
        if TAG not in cur:
            cur.append(TAG)
            entry["tags"] = cur
            added += 1
    open(TAGS, "w", encoding="utf-8").write(json.dumps(tags, indent=1) + "\n")
    print("\n%s: %d tags added, %d games in tags.json" % (TAG, added, len(tags)))


def _shift(d, days):
    import datetime as dt
    return (dt.date.fromisoformat(d) + dt.timedelta(days=days)).isoformat()


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
