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
CFB_WINDOWS = ["FOX Big Noon", "CBS B1G Time", "NBC Saturday Night",
               "ABC Saturday", "FOX Friday"]
CBB_WINDOWS = ["FOX Weekend", "CBS Weekend", "NBC Weekend", "ABC Weekend",
               "ESPN Saturday", "B1G Peacock", "Big Monday", "Super Tuesday"]
CFB_TYPES = ["Top 10 Upsets", "Ranked Upsets", "Ranked Games"]
# the last two are the shared championship fallbacks -- see title_fallback
CBB_TYPES = ["Top 5 Upsets", "Top 10 Games", "Ranked Big Ten"]

ORDER = {"CFB": {"types": CFB_TYPES, "windows": CFB_WINDOWS},
         "CBB": {"types": CBB_TYPES, "windows": CBB_WINDOWS}}

# The "Marquee Windows" shortcut -- the networks he actually plans a Saturday
# around. One button selects all three at once, which is why the app's TV
# window filter holds a LIST rather than a single value.
MARQUEE = {"CFB": ["FOX Big Noon", "CBS B1G Time", "NBC Saturday Night"],
           "CBB": ["FOX Weekend", "CBS Weekend", "NBC Weekend"]}

# Which network paints each window's chip. Explicit rather than parsed from the
# name: "Big Monday", "Super Tuesday" and "B1G Peacock" carry no network in
# their names at all. Peacock mirrors NBC; ESPN is red.
WINDOW_NET = {
    "FOX Big Noon": "fox", "FOX Friday": "fox", "FOX Weekend": "fox",
    "CBS B1G Time": "cbs", "CBS Weekend": "cbs",
    "NBC Saturday Night": "nbc", "NBC Weekend": "nbc", "B1G Peacock": "nbc",
    "ABC Saturday": "abc", "ABC Weekend": "abc",
    "Big Monday": "espn", "Super Tuesday": "espn", "ESPN Saturday": "espn",
}

# The header line is tinted by the window it belongs to -- his hexes,
# 2026-09-09. Anything not listed keeps the muted default.
# ABC Saturday and FOX Friday are deliberately absent: he wants those headers
# plain. A window with no tint here keeps the muted default.
HEADER_TINT = {
    "FOX Big Noon": "#ffcb05",
    "CBS B1G Time": "#005ae4", "NBC Saturday Night": "#0b85c8",
    "FOX Weekend": "#ffcb05", "CBS Weekend": "#005ae4",
    "NBC Weekend": "#0b85c8",
}

# Sorting a tie: when two games kick at the same minute, the bigger network
# leads. His order, and it differs by sport only in length.
NET_PRIORITY = {"CFB": ["FOX", "CBS", "NBC", "ABC"],
                "CBB": ["FOX", "CBS", "NBC", "ABC", "ESPN", "Peacock"]}

# CBS's college package was the SEC through 2023 and the Big Ten from 2024 --
# "CBS B1G Time" means whichever it was, so both conferences qualify. Without
# this the window was a narrow 3:30 clock check and missed USC at Purdue
# (6:45pm on CBS, 2025), which he spotted.
CBS_CFB_CONF = {"5", "8"}                  # Big Ten, SEC


def thanksgiving(year):
    """US Thanksgiving: the fourth Thursday of November."""
    import datetime as _dt
    d = _dt.date(year, 11, 1)
    d += _dt.timedelta(days=(3 - d.weekday()) % 7)   # first Thursday
    return d + _dt.timedelta(days=21)


def is_black_friday(d):
    return d.date() == thanksgiving(d.year) + __import__("datetime").timedelta(days=1)

# The Army-Navy game is played on a December Saturday afternoon on CBS, which
# makes it a false match for the CBS window every single year (five for five).
# It is the last game of the season and belongs to neither package.
ARMY, NAVY = "349", "2426"

# NOTE: "Power Four/Five" scopes which CONFERENCE CHAMPIONSHIP games count
# (see POWER5 and power5_title). It is deliberately NOT a condition on TV
# windows -- a window is a time slot on a network, whoever is playing. An
# earlier version gated windows on it too and he corrected that on 2026-09-09.
# If a narrower rule is ever wanted, note that conference ids differ per sport
# (4 is the Big 12 in football and the BIG EAST in basketball) and that Notre
# Dame is an INDEPENDENT, conference 18, despite being NBC's entire package.


def cfb_slots(nets, d, season, team_ids=(), conf_ids=(), fox_friday_dates=()):
    """Football's windows. Several are era-dependent, because the packages
    moved: no CBS or NBC window before 2023, ABC is primetime-only in 2021-22,
    and FOX Friday does not start until 2024.
    """
    day, t = DOW[d.weekday()], _mins(d)
    out = set()
    if ARMY in team_ids and NAVY in team_ids:
        return out                       # see ARMY, NAVY above
    early = season < 2023
    b1g = "5" in conf_ids

    # FOX Friday is a 2024 package. FS1 deputises only when FOX itself has no
    # Friday game that night and a Big Ten team is playing.
    if season >= 2024 and day == "Fri" and t >= 18 * 60:
        if "FOX" in nets:
            out.add("FOX Friday")
        elif "FS1" in nets and b1g and d.date() not in fox_friday_dates:
            out.add("FOX Friday")

    if "FOX" in nets and day == "Sat" and abs(t - 12 * 60) <= 40:
        out.add("FOX Big Noon")
    # CBS: whichever conference its package held that year, any Saturday time
    if not early and "CBS" in nets and day == "Sat" and (conf_ids & CBS_CFB_CONF):
        out.add("CBS B1G Time")
    if (not early and "NBC" in nets and day == "Sat"
            and abs(t - (19 * 60 + 30)) <= 45):
        out.add("NBC Saturday Night")
    if "ABC" in nets and day == "Sat" and (not early or t >= 19 * 60):
        out.add("ABC Saturday")
    return out


def cfb_black_friday(nets, d, season):
    """Black Friday football, which he wants in the archive and in Marquee but
    WITHOUT a window label -- CBS and NBC from 2023, FOX and ABC throughout."""
    if not is_black_friday(d):
        return False
    if nets & {"FOX", "ABC"}:
        return True
    return season >= 2023 and bool(nets & {"CBS", "NBC"})


def cbb_slots(nets, d, both_big_ten, any_ranked, any_big_ten=False):
    """Basketball's windows -- **January to March only** (his call: the
    November-December non-conference slate is not what he is browsing for).

    The four broadcast networks are "Weekend" windows. A FOX or CBS Saturday
    game before 7pm needs a Big Ten team, since those early slots are
    otherwise filler.
    """
    if d.month not in (1, 2, 3):
        return set()
    day, t = DOW[d.weekday()], _mins(d)
    out = set()
    if "ESPN" in nets and day == "Mon" and t >= 18 * 60:
        out.add("Big Monday")
    if "ESPN" in nets and day == "Tue" and t >= 18 * 60:
        out.add("Super Tuesday")
    if "ESPN" in nets and day == "Sat" and t >= 18 * 60 + 30:
        out.add("ESPN Saturday")
    for n in ("FOX", "CBS", "NBC", "ABC"):
        if n not in nets:
            continue
        if (n in ("FOX", "CBS") and day == "Sat" and t < 19 * 60
                and not any_big_ten):
            continue
        out.add(n + " Weekend")
    # Peacock is a firehose on its own (it carries every Big Ten home
    # non-conference game), so it is narrowed to the conference weeknight
    # window with a ranked team. Nothing before 2023-24: the package is new.
    if (any("Peacock" in n for n in nets) and both_big_ten
            and day in ("Tue", "Thu") and any_ranked):
        out.add("B1G Peacock")
    return out


def cbb_header_suffix(nets, d):
    """The label that follows the date on a basketball card. Not a window --
    the cards carry no window chips at all -- just a name for the slot."""
    if d.month not in (1, 2, 3):
        return None
    day, t = DOW[d.weekday()], _mins(d)
    if "FOX" in nets and day == "Fri":
        return "FOX Friday"
    if "FOX" in nets and day == "Sat" and t >= 19 * 60:
        return "FOX Primetime"
    if "ESPN" in nets and day == "Sat" and t >= 19 * 60:
        return "ESPN Primetime"
    return None


# Kyle's teams, 2026-09-09. ESPN gives a school ONE id across both sports.
MICHIGAN = "130"
# Rivals whose WINS he does not want on the Big Games tab
RIVALS = {"194": "Ohio State", "127": "Michigan State", "87": "Notre Dame"}

def game_type(sport, rank_win, rank_lose, has_big_ten, p5_title=False):
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
        if not p5_title:
            return None
        return (title_fallback(rank_win, rank_lose) if sport == "CFB"
                else "Top 10 Games")

    if sport == "CFB":
        top10 = rank_win <= 10 and rank_lose <= 10
        if not (top10 or has_big_ten):
            return title_fallback(rank_win, rank_lose) if p5_title else None
        return "Ranked Upsets" if rank_win > rank_lose else "Ranked Games"

    if rank_win <= 10 and rank_lose <= 10:
        return "Top 10 Games"
    if has_big_ten:
        return "Ranked Big Ten"
    # a basketball final matching nothing is a Top 10 Game (his call)
    return "Top 10 Games" if p5_title else None


def is_title_game(sport, conf, headline):
    """A CHAMPIONSHIP game, as Kyle means it: a Power Five football title game,
    or a Power Five basketball conference tournament FINAL -- "finals only, not
    the rest of the tournaments" (2026-09-09). 23 of each, 46 in all.

    These get two privileges: a category even when no ranking rule fits, and a
    guaranteed place on the TV Windows view even with no broadcast window.
    """
    if not conf:
        return False
    if sport == "CFB":
        return True
    return (headline or "").endswith("- Final")


def title_fallback(rank_win, rank_lose):
    """A championship game belongs in Big Games, but plenty match none of the
    ranking rules -- an unranked pair, or a ranked favourite beating an
    unranked team. Those are filed by RESULT: an upset is a Ranked Upset,
    anything else a Ranked Game.

    FOOTBALL ONLY. A basketball final that matches nothing becomes a Top 10
    Game instead -- his call, rather than borrowing football's labels.
    """
    upset = ((rank_lose and not rank_win)
             or (rank_win and rank_lose and rank_win > rank_lose))
    return "Ranked Upsets" if upset else "Ranked Games"


def is_championship(headlines):
    """Any conference title game or playoff round, Power Five or not.

    The Power Four/Five restriction applies to CHAMPIONSHIP GAMES ONLY (his
    correction, 2026-09-09) -- not to TV windows generally. So this catches
    the ones that are NOT Power Five and lets harvest.py strip their window:
    the Mountain West Championship kicks off on a December Friday night and
    lands squarely in FOX Friday, the American Athletic Championship sits in
    ABC Saturday, and the FCS playoff quarterfinals do the same. None of them
    belong to those packages.

    Ordinary regular-season games between the same teams are untouched --
    Boise State at BYU on ABC in September is a real ABC Saturday game.
    """
    for h in headlines:
        base = (h or "").split(" - ")[0]
        if "hampionship" in base or "Tournament" in base or "Playoff" in base:
            return True
    return False


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
