"""The rule set that decides which past games enter the archive.

Kyle's definitions, settled 2026-09-09. Two dimensions that may overlap:
TV SLOTS (a recurring broadcast window) and BIG GAMES (ranking-driven), plus
Power Five conference championships. Postseason (bowls, CFP, NCAA tournament)
is excluded everywhere -- that is ESPN season type 3.
"""

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ESPN conferenceId, verified historical: ESPN returns the conference the team
# was IN at the time of the game (USC reads Pac-12 in 2021, Big Ten in 2025).
BIG_TEN = {"CFB": "5", "CBB": "7"}
POWER5 = ["ACC", "Big Ten", "Big 12", "SEC", "Pac-12"]


def _mins(d):
    return d.hour * 60 + d.minute


# The order the app lists these in -- his, 2026-09-09, and NOT alphabetical.
# These lists are the display order AND the full vocabulary; harvest.py copies
# them into games.json so the page has one source of truth.
CFB_WINDOWS = ["FOX Friday", "FOX Big Noon", "CBS B1G Time",
               "NBC Saturday Night", "ABC"]
CBB_WINDOWS = ["FOX", "CBS", "NBC", "ABC", "B1G Peacock", "Big Monday",
               "Super Tuesday",
               # Not in the order he gave, but it WAS in his original slot
               # list, so it is kept and parked last rather than dropped.
               "ESPN Sat night"]
CFB_TYPES = ["Top 10 Upsets", "Ranked Upsets", "Ranked Games"]
CBB_TYPES = ["Top 5 Upsets", "Top 10 Games", "Ranked Big Ten"]

ORDER = {"CFB": {"types": CFB_TYPES, "windows": CFB_WINDOWS},
         "CBB": {"types": CBB_TYPES, "windows": CBB_WINDOWS}}

# The "Marquee Windows" shortcut -- the networks he actually plans a Saturday
# around. One button selects all three at once, which is why the app's TV
# window filter holds a LIST rather than a single value.
MARQUEE = {"CFB": ["FOX Big Noon", "CBS B1G Time", "NBC Saturday Night"],
           "CBB": ["FOX", "CBS", "NBC"]}


def cfb_slots(nets, d):
    day, t = DOW[d.weekday()], _mins(d)
    out = set()
    if "FOX" in nets and day == "Fri" and t >= 18 * 60:
        out.add("FOX Friday")
    if "FOX" in nets and day == "Sat" and abs(t - 12 * 60) <= 40:
        out.add("FOX Big Noon")
    if "CBS" in nets and day == "Sat" and abs(t - (15 * 60 + 30)) <= 45:
        out.add("CBS B1G Time")
    if "NBC" in nets and day == "Sat" and abs(t - (19 * 60 + 30)) <= 45:
        out.add("NBC Saturday Night")
    if "ABC" in nets and day == "Sat":
        out.add("ABC")
    return out


def cbb_slots(nets, d, both_big_ten, any_ranked):
    day, t = DOW[d.weekday()], _mins(d)
    out = set()
    # ESPN's own brands for the weeknight showcases
    if "ESPN" in nets and day == "Mon" and t >= 18 * 60:
        out.add("Big Monday")
    if "ESPN" in nets and day == "Tue" and t >= 18 * 60:
        out.add("Super Tuesday")
    if "ESPN" in nets and day == "Sat" and t >= 18 * 60 + 30:
        out.add("ESPN Sat night")
    for n in ("FOX", "CBS", "NBC", "ABC"):
        if n in nets:
            out.add(n)
    # Peacock is a firehose on its own (it carries every Big Ten home
    # non-conference game), so it is narrowed to the conference weeknight
    # window with a ranked team. Nothing before 2023-24: the package is new.
    if (any("Peacock" in n for n in nets) and both_big_ten
            and day in ("Tue", "Thu") and any_ranked):
        out.add("B1G Peacock")
    return out


# Kyle's teams, 2026-09-09. ESPN gives a school ONE id across both sports.
MICHIGAN = "130"
# Rivals whose WINS he does not want on the Big Games tab
RIVALS = {"194": "Ohio State", "127": "Michigan State", "87": "Notre Dame"}

CFB_TYPES = ["Top 10 Upsets", "Ranked Upsets", "Ranked Games"]
CBB_TYPES = ["Top 5 Upsets", "Top 10 Games", "Ranked Big Ten"]


def game_type(sport, rank_win, rank_lose, has_big_ten):
    """The game's category, or None. Kyle's definitions, 2026-09-09 -- and
    they DIFFER by sport, which is why the app's dropdown follows the sport
    toggle. `rank_*` are None when unranked. A game gets at most one category,
    and membership of the Big Games tab is exactly "has one".

    CFB
      Top 10 Upsets   unranked beats a top-10 team, OR anyone beats #1
      Ranked Upsets   the worse-ranked team won, in top-10 v top-10
                      or in ranked v ranked with a Big Ten team
      Ranked Games    the same two scopes, better-ranked team won

    CBB (a tighter net -- college basketball is far the bigger slate)
      Top 5 Upsets    unranked beats a top-5 team, OR anyone beats #1
      Top 10 Games    top-10 v top-10, either winner
      Ranked Big Ten  any OTHER ranked v ranked with a Big Ten team

    The upset categories are tested first on purpose: "anyone beats #1" would
    otherwise be swallowed by the ranked-v-ranked cases, and beating #1 is the
    reading he wants.
    """
    top = 10 if sport == "CFB" else 5
    upset_label = "Top %d Upsets" % top
    if rank_lose == 1:                                  # anyone beats #1
        return upset_label
    if rank_lose and rank_lose <= top and rank_win is None:
        return upset_label

    both = rank_win and rank_lose
    if not both:
        return None

    if sport == "CFB":
        top10 = rank_win <= 10 and rank_lose <= 10
        if not (top10 or has_big_ten):
            return None
        return "Ranked Upsets" if rank_win > rank_lose else "Ranked Games"

    if rank_win <= 10 and rank_lose <= 10:
        return "Top 10 Games"
    if has_big_ten:
        return "Ranked Big Ten"
    return None


def power5_title(headlines):
    """Conference championship / tournament game, Power Five only.

    TRAP: ESPN prefixes a sponsor and changes the suffix year to year --
    'Subway ACC Championship Game' -> 'Subway ACC Championship' -> 'ACC
    Championship'; 'New York Life ACC Tournament' -> 'T. Rowe Price ACC
    Tournament'. Matching on a prefix reports ZERO championship games for
    2021 and 2022. Substring on the conference name is the only thing that
    holds. 'FCS Championship' must be excluded explicitly.
    """
    for h in headlines:
        base = h.split(" - ")[0]
        if "Tournament" not in base and "hampionship" not in base:
            continue
        if "FCS" in base:
            continue
        for p in POWER5:
            if p in base:
                return p, h
    return None, None
