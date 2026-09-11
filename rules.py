"""The rule set that decides which past games enter the archive.

Kyle's definitions, settled 2026-09-09. Two dimensions that may overlap:
TV SLOTS (a recurring broadcast window) and BIG GAMES (ranking-driven), plus
Power Five conference championships. Postseason (bowls, CFP, NCAA tournament)
is excluded everywhere -- that is ESPN season type 3.
"""

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday"]

# ESPN conferenceId, verified historical: ESPN returns the conference the team
# was IN at the time of the game (USC reads Pac-12 in 2021, Big Ten in 2025).
BIG_TEN = {"CFB": "5", "CBB": "7"}
# Football has five power conferences; basketball has SIX -- the Big East is
# a major basketball conference with no football to speak of. His "Power
# Five/Six", 2026-09-09.
POWER5 = ["ACC", "Big Ten", "Big 12", "SEC", "Pac-12"]
POWER6 = POWER5 + ["Big East"]


def power_conferences(sport):
    return POWER6 if sport == "CBB" else POWER5


def _mins(d):
    return d.hour * 60 + d.minute


# ESPN abbreviates these schools; he wants them spelled out. UNLV and UConn go
# the other way -- ESPN's all-caps forms become ordinary words.
NAME_OVERRIDES = {
    "BYU": "Brigham Young", "LSU": "Louisiana State",
    "SMU": "Southern Methodist", "TCU": "Texas Christian",
    "UCF": "Central Florida", "USF": "South Florida",
    "USC": "Southern California", "UNLV": "Unlv", "UConn": "Connecticut",
}


# Names that depend on the SEASON. UCLA reads "Ucla" before 2023, in the same
# spirit as Unlv -- an all-caps acronym only earns its capitals once the team
# is Big Ten, where caps carry meaning. UCLA joined for 2024, so 2023 and
# earlier read "Ucla".
SEASON_NAMES = {"26": {"before": 2024, "name": "Ucla"}}


def display_name(location):
    return NAME_OVERRIDES.get(location, location)


# In the New York and Los Angeles metros the VENUE is what people say, not the
# municipality -- nobody calls it a Bronx game or an Inglewood game. ESPN files
# those under the borough or suburb, so a game in one of these cities shows its
# venue instead: Madison Square Garden, Yankee Stadium, MetLife Stadium,
# Barclays Center, Intuit Dome.
VENUE_METROS = {
    # New York
    "New York", "Bronx", "Brooklyn", "Queens", "East Rutherford", "Newark",
    "Uniondale", "Harrison", "Elmont",
    # Los Angeles
    "Los Angeles", "Inglewood", "Pasadena", "Carson", "Anaheim",
    # Chicago
    "Chicago", "Evanston", "Rosemont",
}


# Cities ESPN names in a way he does not want read back.
CITY_OVERRIDES = {"Washington": "Washington DC"}


def display_city(city, venue=None):
    if city in VENUE_METROS and venue:
        return venue
    return CITY_OVERRIDES.get(city, city)


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

# The "Marquee Windows" shortcut -- the games he actually plans a weekend
# around. It used to be a LIST OF WINDOWS the button selected together, with
# Black Friday and show broadcasts riding along on the side; his call
# 2026-09-10 made it a set of rules of its own, so `is_marquee` below is now
# the single definition and the button is a plain on/off.
CFB_MARQUEE = ["FOX Big Noon", "CBS B1G Time", "NBC Saturday Night"]


def is_marquee(sport, nets, d, slots, big_ten=False, tourney=False):
    """Is this one of the games the Marquee button keeps?

    Football is exactly its three windows -- nothing rides along any more.

    Basketball is not a window list at all, because "FOX Weekend" admits any
    FOX game in the January-March stretch, weeknights included. His rule: a
    FOX, CBS or NBC game on a WEEKEND with a Big Ten team, plus FOX Friday and
    FOX Primetime whether or not a Big Ten team is in them.
    """
    if tourney:
        return False          # a conference tournament belongs to no package
    if sport == "CFB":
        return any(w in CFB_MARQUEE for w in slots)
    if d.month not in (1, 2, 3):
        return False          # basketball Marquee stays January-March (his call)
    day, t = DOW[d.weekday()], _mins(d)
    if "FOX" in nets and (day == "Fri" or (day == "Sat" and t >= 19 * 60)):
        return True           # FOX Friday and FOX Primetime, Big Ten or not
    return big_ten and day in ("Sat", "Sun")         and bool(nets & {"FOX", "CBS", "NBC"})

# Windows that stay OUT of the TV Window dropdown (his call 2026-09-10). The
# games keep the window and still appear under "All TV Windows" -- it is the
# filter option that goes, not the games.
HIDDEN_WINDOWS = {"CFB": ["ABC Saturday"],
                  "CBB": ["ABC Weekend", "ESPN Saturday",
                          "Big Monday", "Super Tuesday"]}

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
# FOOTBALL header tints. ABC Saturday and FOX Friday are deliberately absent:
# he wants those headers plain, and an untinted window keeps the muted default.
# Basketball does NOT tint its header -- it colours the NETWORK text instead,
# see NET_TINT.
HEADER_TINT = {
    "FOX Big Noon": "#ffcb05",
    "CBS B1G Time": "#4b8dff", "NBC Saturday Night": "#0b85c8",
}

# The network text in the meta column, coloured on basketball cards.
NET_TINT = {"FOX": "#ffcb05", "CBS": "#4b8dff", "NBC": "#0b85c8",
            "ABC": "#e52534"}

# Sorting a tie: when two games kick at the same minute, the bigger network
# leads. His order, and it differs by sport only in length.
NET_PRIORITY = {"CFB": ["FOX", "CBS", "NBC", "ABC"],
                "CBB": ["FOX", "CBS", "NBC", "ABC", "ESPN", "Peacock"]}

# CBS B1G Time is the 3:30 window and ONLY that. A wider "any Saturday CBS
# game" rule pulled in Washington-Washington State, UCLA-Hawai'i and a dozen
# 2023 fixtures, which he rejected. USC at Purdue reads 6:45pm in ESPN's data
# because it was WEATHER DELAYED -- that is an override, not a rule.


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
NOTRE_DAME = "87"

# The RIVALS view (his call 2026-09-11) shows games these teams LOST -- Notre
# Dame in football only.
RIVALS_BY_SPORT = {"CFB": {"194", "127", "87"},   # Ohio State, Michigan State, Notre Dame
                   "CBB": {"194", "127"}}         # Ohio State, Michigan State
# ...and a team that counts ONLY for its NCAA Tournament losses (his call
# 2026-09-11): Notre Dame in basketball. It is no rival in any other game, so an
# Ohio State loss to Notre Dame in December still counts as it always did.
RIVALS_NCAA_ONLY = {"CBB": {"87"}}


def is_ncaa_tournament(season_type, headlines):
    return (season_type == 3
            and "basketball championship" in " ".join(h or "" for h in headlines).lower())
# Two of them playing each other stays OUT of that view unless the ESPN game id
# is named here -- "I will have to tell you when to include".
RIVALS_INCLUDE = {
    "401282786",    # 2021 football: Ohio State 56, Michigan State 7 (his call 2026-09-11)
}

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
    if (not early and "CBS" in nets and day == "Sat"
            and abs(t - (15 * 60 + 30)) <= 45):
        out.add("CBS B1G Time")
    if (not early and "NBC" in nets and day == "Sat"
            and abs(t - (19 * 60 + 30)) <= 45):
        out.add("NBC Saturday Night")
    # EVERY Saturday ABC game is in the window. Restricting it to 7-8pm was a
    # misreading -- what he wanted narrowed was the header LABEL, not the
    # window. See cfb_header().
    if "ABC" in nets and day == "Sat":
        out.add("ABC Saturday")
    return out


def cfb_header(slots, d, forced=False):
    """The label after the date on a football card.

    It is USUALLY the window's own name, but ABC is the exception: the window
    holds every Saturday ABC game while the label reads "ABC Primetime" only
    for a 7-8pm kick, and nothing at all otherwise. `forced` covers a game
    placed by hand in window-overrides.json -- the Clemson-LSU weather delay
    is recorded at its 9:40pm restart but was scheduled in primetime.
    """
    named = [w for w in CFB_WINDOWS if w in slots and w != "ABC Saturday"]
    if named:
        return named[0]
    if "ABC Saturday" not in slots:
        return None
    t = _mins(d)
    return "ABC Primetime" if (forced or 19 * 60 <= t <= 20 * 60) else None


BROADCAST = {"FOX", "CBS", "NBC", "ABC"}


def cfb_opener(nets, d, week, week0=False, big_ten=False, ranked=False,
               notre_dame=False):
    """Week 0, and the non-Saturday games of Week 1, on a broadcast network.

    His call 2026-09-11. These go on the TV tab under their week alone --
    "WEEK 0" or "WEEK 1" -- and in NO window: a Week 0 noon kick on FOX is not
    FOX Big Noon, and the Week 1 Friday game is not FOX Friday. Harvest clears
    the slots of any game this returns True for, which also keeps it out of
    Marquee.

    Two recurring slots are in whoever plays: the Labor Day weekend Sunday
    night game on ABC, and FOX's Week 1 Thursday or Friday night game. Anything
    else needs a Big Ten team, a ranked team or Notre Dame -- which is what
    leaves out Fresno State-Kansas and Stanford-Hawai'i (both 2025 Week 0).
    """
    if not (week0 or (week == 1 and d.weekday() != 5)):
        return False
    hit = set(nets) & BROADCAST
    if not hit:
        return False
    day = DOW[d.weekday()]
    if day == "Sun" and "ABC" in hit:
        return True
    if day in ("Thu", "Fri") and "FOX" in hit:
        return True
    return big_ten or ranked or notre_dame


CFB_POWER = {"1", "4", "5", "8", "9"}    # ACC, Big 12, Big Ten, SEC, Pac-12


def cfb_neutral_kickoff(d, season, neutral, teams):
    """An August or September neutral-site football game between two power
    teams, or with a Big Ten team against anyone (his call 2026-09-11).

    `teams` is [(team id, conference id), ...]. Power is the Power Five through
    2023 and the Power Four from 2024, when the Pac-12 stopped counting; Notre
    Dame counts as power. A conference game qualifies too -- Arkansas-Texas A&M
    in Arlington is exactly this kind of game.
    """
    if not neutral or d.month not in (8, 9):
        return False
    power = CFB_POWER if season <= 2023 else CFB_POWER - {"9"}
    return (all(tid == NOTRE_DAME or conf in power for tid, conf in teams)
            or any(conf == BIG_TEN["CFB"] for _tid, conf in teams))


# Basketball events he wants every year, whatever the network or tip time (his
# call 2026-09-11). Matched inside ESPN's note headline, so a sponsor around the
# name ("State Farm Champions Classic") does not matter. Diamond Cup is a future
# event, listed ahead of its first edition.
CBB_SHOWCASE_EVENTS = ("Champions Classic", "Jimmy V Classic", "CBS Sports Classic",
                       "Jumpman Invitational", "Indy Classic", "Diamond Cup")


def cbb_showcase(headlines):
    text = " ".join(headlines).lower()
    return any(e.lower() in text for e in CBB_SHOWCASE_EVENTS)


# ---------------------------------------------------------------- stage labels
# His header patterns for games that are an EVENT rather than a week
# (2026-09-11), names spelled out: "FIESTA BOWL (SAT)", "CFP | QUARTERS (WED)", "NCAA TOURNAMENT | ROUND 1 (THU)", "BIG TEN
# TOURNAMENT | QUARTERS (FRI)" -- and a football title game with no round to
# show, "BIG TEN CHAMPIONSHIP (SAT)". stage_label returns the part before the
# day; the app adds the day.

# checked in order: "final four" before "final", "semifinal" before "final"
ROUND_NAMES = (("first four", "First Four"), ("1st round", "Round 1"),
               ("first round", "Round 1"), ("2nd round", "Round 2"),
               ("second round", "Round 2"), ("3rd round", "Round 3"),
               ("sweet 16", "Sweet Sixteen"), ("elite 8", "Elite Eight"),
               ("final four", "Final Four"), ("quarterfinal", "Quarters"),
               ("semifinal", "Semis"), ("championship", "Championship"),
               ("final", "Championship"))

# Bowls whose own name survives the sponsor ("Vrbo Fiesta Bowl" -> "Fiesta
# Bowl"). A bowl NAMED for its sponsor ("Guaranteed Rate Bowl") is kept whole.
BOWL_NAMES = ("Rose", "Sugar", "Orange", "Cotton", "Fiesta", "Peach", "Citrus",
              "Gator", "Pinstripe", "Music City", "Las Vegas", "Sun", "Alamo",
              "LA", "Holiday", "Liberty", "Texas", "Armed Forces", "Birmingham",
              "Military", "Independence", "First Responder", "Hawaii",
              "Boca Raton", "New Mexico", "Frisco", "Camellia", "Myrtle Beach",
              "Fenway", "Arizona", "Gasparilla", "Potato", "Motor City",
              "Heart of Dallas", "Poinsettia", "Belk", "New Orleans", "Cure",
              "Celebration", "Bahamas", "St. Petersburg", "Russell Athletic",
              "Foster Farms")


def _round(text):
    for part in reversed([p.strip() for p in text.split(" - ")]):
        low = part.lower()
        for key, name in ROUND_NAMES:
            if key in low:
                return name
    return None


def bowl_name(text):
    head = text.split(" - ")[0]
    low = head.lower()
    for b in sorted(BOWL_NAMES, key=len, reverse=True):
        if (b + " bowl").lower() in low:
            return b + " Bowl"
    i = head.find(" Bowl")
    return head[:i + 5] if i >= 0 else head


def _cbb_postseason_event(part):
    low = part.lower()
    if "basketball championship" in low:
        return "NCAA"
    if low.startswith("nit"):
        return "NIT"
    if "cbi" in low:
        return "CBI"
    if "crown" in low:
        return "Crown"
    if low == "cit" or low.startswith("cit "):
        return "CIT"
    if "basketball classic" in low:
        return "Basketball Classic"
    return part


# Before the 12-team CFP, a semifinal was played in a bowl and ESPN headlined
# it as that bowl alone ("Goodyear Cotton Bowl Classic"), so it would read as an
# ordinary bowl. The semifinal hosts rotated on a fixed schedule, by season.
CFP_SEMIFINAL_BOWLS = {2014: ("Rose", "Sugar"), 2015: ("Orange", "Cotton"),
                       2016: ("Fiesta", "Peach"), 2017: ("Rose", "Sugar"),
                       2018: ("Orange", "Cotton"), 2019: ("Fiesta", "Peach"),
                       2020: ("Rose", "Sugar"), 2021: ("Orange", "Cotton"),
                       2022: ("Fiesta", "Peach"), 2023: ("Rose", "Sugar")}

# Until 2016 the NCAA tournament called the First Four the 1st round, so the
# rounds read one higher than they do now. The 2014-15 season is the only one
# in the data that used those names.
NCAA_OLD_ROUNDS = {"Round 1": "First Four", "Round 2": "Round 1", "Round 3": "Round 2"}


def stage_label(sport, season_type, headlines, conf=None, month=None, season=None):
    """The event and round of a postseason, conference-championship or
    conference-tournament game: "Fiesta Bowl", "College Football Playoff |
    Quarters", "NCAA Tournament | Round 1", "Big Ten Tournament | Semis", "Big
    Ten Championship". None for any other game."""
    heads = [h for h in headlines if h]
    if not heads:
        return None
    text = heads[0]
    rnd = _round(text)
    if sport == "CFB":
        if season_type == 3:
            low = text.lower()
            if "college football playoff" in low or low.startswith("cfp"):
                return "CFP" + (" | " + rnd if rnd else "")
            bowl = bowl_name(text)
            if bowl in [b + " Bowl" for b in CFP_SEMIFINAL_BOWLS.get(season, ())]:
                return "CFP | Semis"
            return bowl
        if conf and is_championship(heads):
            return conf + " Championship"
        return None
    if season_type == 3:
        event = _cbb_postseason_event(text.split(" - ")[0])
        if event == "NCAA":
            if season is not None and season <= 2014:
                rnd = NCAA_OLD_ROUNDS.get(rnd, rnd)
            event = "NCAA Tournament"
        return event + (" | " + rnd if rnd else "")
    if conf and is_championship(heads) and month in (3, 4):
        return conf + " Tournament | " + (rnd or "Championship")
    return None


# The six bowls that host CFP games short of the final (his call 2026-09-11).
# Such a game names its bowl in the location chip rather than the city --
# Rose Bowl, not Arlington or Pasadena.
CFP_BOWLS = ("Rose Bowl", "Cotton Bowl", "Peach Bowl", "Fiesta Bowl",
             "Orange Bowl", "Sugar Bowl")


def cfp_bowl(season_type, headlines, season=None):
    label = stage_label("CFB", season_type, headlines, season=season)
    if not label or not label.startswith("CFP") or label.endswith("Championship"):
        return None
    bowl = bowl_name([h for h in headlines if h][0])
    return bowl if bowl in CFP_BOWLS else None


def cfb_black_friday(nets, d, season, big_ten=False):
    """Black Friday football -- in the archive and in Marquee, but with NO
    window label.

    Narrowed 2026-09-09 to **ABC in primetime, plus FOX/CBS/NBC games with a
    Big Ten team**; CBS and NBC still only from 2023. That takes the Friday
    slate from 30 games to 10 and drops the Group of Five and afternoon
    filler.
    """
    if not is_black_friday(d):
        return False
    if "ABC" in nets and _mins(d) >= 19 * 60:
        return True
    if not big_ten:
        return False
    if "FOX" in nets:
        return True
    return season >= 2023 and bool(nets & {"CBS", "NBC"})


def cbb_slots(nets, d, both_big_ten, any_ranked, any_big_ten=False):
    """Basketball's windows -- **November through March** (his call
    2026-09-11, widening January-March). Big Monday and Super Tuesday stay
    January to March: they are conference-season slots, and he left the
    November and December Tuesdays out.

    The four broadcast networks are "Weekend" windows. A FOX or CBS Saturday
    game before 7pm needs a Big Ten team, since those early slots are
    otherwise filler.
    """
    if d.month not in (11, 12, 1, 2, 3):
        return set()
    conference_season = d.month in (1, 2, 3)
    day, t = DOW[d.weekday()], _mins(d)
    out = set()
    # Big Monday and Super Tuesday may carry SEVERAL games a night, unlike
    # ESPN Saturday -- his call. The bracket is 6:00 to 9:30pm.
    if (conference_season and "ESPN" in nets and day in ("Mon", "Tue")
            and 18 * 60 <= t <= 21 * 60 + 30):
        out.add("Big Monday" if day == "Mon" else "Super Tuesday")
    # ESPN Saturday is every ESPN game tipping between 6:00 and 9:30pm (his
    # call 2026-09-10, widening it from the single latest game). Only the
    # latest still carries the "ESPN Primetime" label -- see
    # cbb_header_suffix -- so the window and the label part company here.
    if "ESPN" in nets and day == "Sat" and 18 * 60 <= t <= 21 * 60 + 30:
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


def cbb_header_suffix(nets, d, tourney=False, big_ten=False, espn_sat=False):
    """The label on a basketball card. Not a window -- the cards carry no
    window chips at all -- just a name for the slot.

    The FOX and ESPN labels are open to anyone. The broadcast-network labels
    added 2026-09-10 are NOT: they need a Big Ten team, because that is what
    he is browsing for and ABC will put any two teams on a Saturday.
    """
    if d.month not in (1, 2, 3):
        return None
    day, t = DOW[d.weekday()], _mins(d)
    if tourney:
        return None          # a conference tournament is not a TV slot
    if "FOX" in nets and day == "Fri":
        return "FOX Friday"
    if "FOX" in nets and day == "Sat" and t >= 19 * 60:
        return "FOX Primetime"
    # --- his additions 2026-09-10, all of them Big Ten only ---------------
    if big_ten:
        # FOX's Saturday afternoon game, the half of Saturday that Primetime
        # above does not cover.
        if "FOX" in nets and day == "Sat":
            return "FOX Saturday"
        if "CBS" in nets and day == "Sun":
            return "CBS Sunday"
        # ABC and NBC get a label on ANY day, named for the day itself.
        for n in ("NBC", "ABC"):
            if n in nets:
                return n + " " + DAY_FULL[d.weekday()]
    # the same brackets the windows use, so a card's label and its window
    # can never disagree
    # The ESPN Saturday WINDOW takes every 6:00-9:30pm game; this LABEL goes
    # to the latest of them alone (espn_saturday_ids picks it), so the rest
    # fall through to the plain weekday.
    if espn_sat:
        return "ESPN Primetime"
    if "ESPN" in nets and day == "Mon" and 18 * 60 <= t <= 21 * 60 + 30:
        return "Big Monday"
    if "ESPN" in nets and day == "Tue" and 18 * 60 <= t <= 21 * 60 + 30:
        return "Super Tuesday"
    return None


def game_type(sport, rank_win, rank_lose, has_big_ten, p5_title=False,
              b1g_tourney_run=False):
    """The game's category, or None. Kyle's definitions, 2026-09-09 -- and
    they DIFFER by sport, which is why the app's dropdown follows the sport
    toggle. `rank_*` are None when unranked. A game gets at most one category,
    and membership of the Key Games tab is exactly "has one".

    CFB
      Top 10 Upsets   unranked beats a top-10 team, OR anyone beats #1
      Ranked Upsets   the worse-ranked team won, in top-10 v top-10
                      or in ranked v ranked with a Big Ten team
      Ranked Games    the same two scopes, better-ranked team won

    CBB (a tighter net -- college basketball is far the bigger slate)
      Top 5 Upsets    unranked beats a top-5 team, OR anyone beats #1
      Top 10 Games    top-10 v top-10, either winner
      Ranked Big Ten  any OTHER ranked v ranked with a Big Ten team, EXCEPT
                      the Big Ten Tournament before its Final -- those are
                      tournament games, not regular-season meetings, and he
                      does not want the quarters and semis in that category
                      (`b1g_tourney_run`). They stay in the archive on their
                      conference-tournament billing.

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
    if has_big_ten and not b1g_tourney_run:
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
    """A championship game belongs in Key Games, but plenty match none of the
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


def power5_title(headlines, sport="CFB"):
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
        for p in power_conferences(sport):
            if p in base:
                return p, h
    return None, None
