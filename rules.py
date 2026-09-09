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


def cfb_slots(nets, d):
    day, t = DOW[d.weekday()], _mins(d)
    out = set()
    if "FOX" in nets and day == "Fri" and t >= 18 * 60:
        out.add("FOX Friday night")
    if "FOX" in nets and day == "Sat" and abs(t - 12 * 60) <= 40:
        out.add("FOX Big Noon")
    if "CBS" in nets and day == "Sat" and abs(t - (15 * 60 + 30)) <= 45:
        out.add("CBS 3:30")
    if "NBC" in nets and day == "Sat" and abs(t - (19 * 60 + 30)) <= 45:
        out.add("NBC 7:30")
    if "ABC" in nets and day == "Sat":
        out.add("ABC Saturday")
    return out


def cbb_slots(nets, d, both_big_ten, any_ranked):
    day, t = DOW[d.weekday()], _mins(d)
    out = set()
    if "ESPN" in nets and day in ("Mon", "Tue") and t >= 18 * 60:
        out.add(f"ESPN {day} night")
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
        out.add("Peacock B1G")
    return out


def big_games(rank_win, rank_lose, has_big_ten):
    """Ranking-driven. rank_* are None when unranked."""
    out = set()
    if rank_lose == 1:
        out.add("#1 loses")
    if rank_win and rank_lose and rank_win <= 10 and rank_lose <= 10:
        out.add("top-10 vs top-10")
    if rank_win and rank_lose and has_big_ten:
        out.add("ranked vs ranked (B1G)")
    if rank_lose and rank_lose <= 10 and rank_win is None:
        out.add("top-10 upset")
    return out


def game_type(rank_win, rank_lose):
    """Kyle's three filter categories, 2026-09-09. A partition of the
    ranking-involved outcomes -- a game returns at most one.

      Ranked Win     both ranked, the better-ranked team won (chalk)
      Ranked Upset   both ranked, the worse-ranked team won
      Upset          the loser was ranked and the winner was not

    A ranked team beating an unranked one is none of these, which is the
    point: it is the unremarkable case.
    """
    if rank_win and rank_lose:
        return "Ranked Win" if rank_win < rank_lose else "Ranked Upset"
    if rank_lose and not rank_win:
        return "Upset"
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
