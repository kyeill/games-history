"""Fetch every past CFB/CBB game matching rules.py and freeze it to JSON.

Past games never change, so this runs once per new week of games -- there is
no daily build and nothing goes stale. `cache/` holds raw ESPN responses so a
re-run is free.
"""
import collections, datetime as dt, json, os, re, sys
from zoneinfo import ZoneInfo
import requests
import rules
import seed_series

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
OUT = os.path.join(HERE, "output")
ET = ZoneInfo("America/New_York")
BASE = "https://site.api.espn.com/apis/site/v2/sports"
SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
# Rivals reaches further back (his call 2026-09-11), for his rivals only --
# see rival_events
RIVAL_SEASONS = list(range(2014, 2021))


def season_over(code, y):
    """Has this season finished? Football runs Aug y to mid-Jan y+1;
    basketball Nov y to mid-April y+1. A season still in progress must NOT be
    cached -- the cache is keyed on a date RANGE, so a partial week-one answer
    would be served for the rest of the year."""
    today = dt.date.today()
    end = dt.date(y + 1, 2, 1) if code == "CFB" else dt.date(y + 1, 5, 1)
    return today >= end

# CFB is groups=80 (FBS). CBB is groups=50 (D-I).
SPORTS = {"CFB": ("football/college-football", "80"),
          "CBB": ("basketball/mens-college-basketball", "50")}


def fetch(sport, params, key, cacheable=True):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, key + ".json")
    if cacheable and os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    r = requests.get(f"{BASE}/{sport}/scoreboard", params=params, timeout=60)
    r.raise_for_status()
    d = r.json()
    if cacheable:
        json.dump(d, open(p, "w", encoding="utf-8"))
    return d


def cbb_range(d, e, keep, tag=""):
    """One week of basketball, d to e inclusive.

    ESPN answers a week that STARTS before the season's first game day with
    nothing at all -- not the games later in that week. The walk starts on
    1 November, so the opening week of 2023-24 (games from 11/6) and of 2025-26
    (from 11/3) came back empty, were cached empty, and ~550 games including
    James Madison's upset at Michigan State never reached the archive. So an
    empty week is re-asked one day at a time. A cached empty week from before
    this fix takes the same path, so no cache file needs deleting.
    `tag` keeps another caller's files apart (series_scan.py's daily schedule).
    """
    sport, grp = SPORTS["CBB"]
    got = fetch(sport, {"dates": "%s-%s" % (d.strftime("%Y%m%d"), e.strftime("%Y%m%d")),
                        "groups": grp, "limit": 1000},
                "cbb-%s%s" % (d.strftime("%Y%m%d"), tag), keep).get("events", [])
    # A week that CROSSES from regular season into postseason is cut short the
    # same way: ESPN returns only its regular-season days (the seasontype
    # parameter does not change that), which lost every NCAA game in the week
    # of 13 March 2016 and 14 March 2021. So when the newest game returned is
    # earlier than the last day asked for, the rest is asked one day at a time.
    if got:
        last = max(dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ")
                   .replace(tzinfo=dt.timezone.utc).astimezone(ET).date()
                   for x in got if x.get("date"))
        if last >= e:
            return got
        start = last
    else:
        start = d
    out, seen, day = list(got), {x.get("id") for x in got}, start
    while day <= e:
        for x in fetch(sport, {"dates": day.strftime("%Y%m%d"), "groups": grp, "limit": 1000},
                       "cbb-day-%s%s" % (day.strftime("%Y%m%d"), tag), keep).get("events", []):
            if x.get("id") not in seen:
                seen.add(x.get("id"))
                out.append(x)
        day += dt.timedelta(days=1)
    return out


def rival_events(code, y):
    """Every game Ohio State, Michigan State or Notre Dame (football) played in a
    season BEFORE the archive, for the Rivals view.

    The whole scoreboard is fetched but only those games are cached, as
    cache/rivals-SPORT-SEASON.json, so seven old seasons cost kilobytes in the
    Drive-synced cache rather than gigabytes. Football is fetched in three
    ranges, because a whole season runs close to the 1,000-event cap. ESPN
    occasionally returns an event with no id; those are skipped.
    """
    path = os.path.join(CACHE, "rivals-%s-%d.json" % (code.lower(), y))
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))["events"]
    sport, grp = SPORTS[code]
    wanted = rules.RIVALS_BY_SPORT[code] | rules.RIVALS_NCAA_ONLY.get(code, set())
    ev = []
    if code == "CFB":
        for rng in ("%d0801-%d0930" % (y, y), "%d1001-%d1130" % (y, y),
                    "%d1201-%d0131" % (y, y + 1)):
            got = fetch(sport, {"dates": rng, "groups": grp, "limit": 1000}, "x",
                        cacheable=False).get("events", [])
            if len(got) >= 1000:
                print("  WARN: %s hit the 1000 cap" % rng, file=sys.stderr)
            ev += got
    else:
        d, end = dt.date(y, 11, 1), dt.date(y + 1, 4, 10)
        while d < end:
            e = min(d + dt.timedelta(days=6), end)
            ev += cbb_range(d, e, False)
            d = e + dt.timedelta(days=1)
    seen, keep = set(), []
    for x in ev:
        cs = (x.get("competitions") or [{}])[0].get("competitors") or []
        if not x.get("id") or x["id"] in seen:
            continue
        if any((k.get("team") or {}).get("id") in wanted for k in cs):
            seen.add(x["id"])
            keep.append(x)
    if season_over(code, y):
        json.dump({"events": keep}, open(path, "w", encoding="utf-8"))
    return keep


def events(code, y):
    """CFB accepts a wide date range; CBB 404s on one and silently caps at
    limit=1000, so it is walked a week at a time."""
    sport, grp = SPORTS[code]
    keep = season_over(code, y)
    ev = []
    if code == "CFB":
        for rng, tag in ((f"{y}0801-{y}1231", "a"), (f"{y+1}0101-{y+1}0131", "b")):
            ev += fetch(sport, {"dates": rng, "groups": grp, "limit": 1000},
                        f"cfb-{y}-{grp}-{tag}", keep).get("events", [])
    else:
        d, end = dt.date(y, 11, 1), dt.date(y + 1, 4, 10)
        while d < end:
            e = min(d + dt.timedelta(days=6), end)
            if d > dt.date.today():
                break                      # nothing played yet this season
            got = cbb_range(d, e, keep)
            if len(got) >= 1000:
                print(f"  WARN: week of {d} hit the 1000 cap", file=sys.stderr)
            ev += got
            d = e + dt.timedelta(days=1)
        seen = set()
        ev = [x for x in ev if not (x["id"] in seen or seen.add(x["id"]))]
    return ev


POLLS = os.path.join(CACHE, "polls")
CORE = "https://sports.core.api.espn.com/v2/sports"
POLL_PATHS = {"CFB": "football/leagues/college-football",
              "CBB": "basketball/leagues/mens-college-basketball"}


def ap_ranks(code, y, week):
    """That week's AP poll as {team id: rank}, cached under cache/polls/.

    ESPN's scoreboard sometimes forgets a ranking on an old game -- Oklahoma #5
    at Ohio State #2 in 2017 reads unranked on both sides -- and the core API's
    week-by-week AP poll does not. Basketball polls are filed under the year
    the season ends. A poll is cached once it has ranks or its season is over.
    """
    season = y if code == "CFB" else y + 1
    path = os.path.join(POLLS, "%s-%d-w%02d.json" % (code.lower(), season, week))
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    ranks = {}
    try:
        r = requests.get("%s/%s/seasons/%d/types/2/weeks/%d/rankings/1"
                         % (CORE, POLL_PATHS[code], season, week), timeout=30)
        if r.status_code == 200:
            for t in r.json().get("ranks") or []:
                m = re.search(r"/teams/([0-9]+)", (t.get("team") or {}).get("$ref", ""))
                if m:
                    ranks[m.group(1)] = t.get("current")
    except requests.RequestException:
        return {}
    if ranks or season_over(code, y):
        os.makedirs(POLLS, exist_ok=True)
        json.dump(ranks, open(path, "w", encoding="utf-8"))
    return ranks


def rank_of(c):
    v = (c.get("curatedRank") or {}).get("current")
    return None if v in (None, 0, 99) else v


def networks(comp):
    out = []
    for b in comp.get("broadcasts") or []:
        out += b.get("names") or []
    return sorted(set(out))


def fox_friday_dates(evs):
    """Dates that already have a FOX Friday night game. FS1 only deputises for
    the Big Ten on a Friday when FOX itself is not carrying one."""
    out = set()
    for x in evs:
        comps = x.get("competitions") or []
        if not comps:
            continue
        nets = set(networks(comps[0]))
        if "FOX" not in nets:
            continue
        d = dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ")               .replace(tzinfo=dt.timezone.utc).astimezone(ET)
        if d.weekday() == 4 and d.hour >= 18:
            out.add(d.date())
    return out


def week_zero_ids(evs):
    """Football games played in WEEK 0.

    ESPN has no week 0: it numbers those games week 1, so they are found by
    date instead -- the week-1 games played before the main Week 1 weekend,
    whose Saturday is the one carrying the most week-1 games. Measured
    2021-2025 it is one early Saturday a year: 8/28, 8/27, 8/26, 8/24, 8/23.
    Bowls are numbered week 1 as well, so only the regular season counts.
    """
    wk1 = []
    for x in evs:
        if ((x.get("week") or {}).get("number") != 1
                or (x.get("season") or {}).get("type") != 2):
            continue
        d = dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ").replace(
            tzinfo=dt.timezone.utc).astimezone(ET)
        wk1.append((d, x["id"]))
    sats = collections.Counter(d.date() for d, _ in wk1 if d.weekday() == 5)
    if not sats:
        return set()
    main = sats.most_common(1)[0][0]
    return {gid for d, gid in wk1 if d.date() < main - dt.timedelta(days=5)}


def load_overrides():
    """Manual window assignments for games ESPN records with no network.

    A weather-delayed game can end up with only its streaming feed listed --
    Texas A&M at Florida (2024) reads "ESPN+, ESPN3" and nothing else -- and no
    rule can recover a network that is not in the data. This is the escape
    hatch. Keys are ESPN game ids; keys starting with "_" are ignored.
    """
    path = os.path.join(HERE, "window-overrides.json")
    if not os.path.exists(path):
        return {}
    raw = json.load(open(path, encoding="utf-8"))
    return {k: v for k, v in raw.items()
            if not k.startswith("_") and isinstance(v, list)}


def load_network_overrides():
    """Networks for games ESPN records with NO broadcast at all -- see
    network-overrides.json. Seven games, checked 2026-09-11: the scoreboard's
    broadcasts and the game summary are both empty, so he supplied them."""
    path = os.path.join(HERE, "network-overrides.json")
    if not os.path.exists(path):
        return {}
    raw = json.load(open(path, encoding="utf-8"))
    return {k: v for k, v in raw.items()
            if not k.startswith("_") and isinstance(v, list)}


def load_extras():
    """Extra windows that only FILTER -- see window-extras.json.

    Penn State at Michigan State, Black Friday 2023, is the case: an NBC
    primetime game he wants under NBC Saturday Night and Marquee without its
    card changing. The extra window joins `slots` (which drives the filter and
    Marquee) after the header has already been decided from the rule's own.
    """
    path = os.path.join(HERE, "window-extras.json")
    if not os.path.exists(path):
        return {}
    raw = json.load(open(path, encoding="utf-8"))
    return {k: v for k, v in raw.items()
            if not k.startswith("_") and isinstance(v, list)}


def show_games():
    """(sport, date, {team names}) for every game College GameDay or Big Noon
    Kickoff broadcast from. He wants all of them in the archive even when no
    window rule reaches them -- 24 of the 50 stragglers are ESPN games, and
    neither sport has a general ESPN window.

    The tables live in seed_tags.py, which is also what writes the tags, so
    there is one list rather than two that can drift.
    """
    import seed_tags
    out = set()
    for _tag, sport, rows in seed_tags.TABLES:
        for date, visitor, host in rows:
            out.add((sport, date,
                     frozenset({seed_tags.norm(visitor), seed_tags.norm(host)})))
    return out


def event_sizes(evs):
    """How many distinct TEAMS play under each event name this season.

    His principle: keep the event name when it is a tournament or a multi-team
    event, otherwise show the neutral-site city instead. That is derivable --
    a tournament fields more than two teams. Maui runs 8 teams over 12 games;
    the Aer Lingus College Football Classic is one game between two.

    Counted PER SEASON, because the same name can be either: there were two
    Duke's Mayo Classic games in 2021 (4 teams) and one in every other year.
    """
    out = collections.defaultdict(set)
    for x in evs:
        comps = x.get("competitions") or []
        if not comps:
            continue
        for n in (comps[0].get("notes") or []):
            base = (n.get("headline") or "").split(" - ")[0].strip()
            if not base:
                continue
            out[base] |= {k["team"]["id"] for k in (comps[0].get("competitors") or [])}
            break
    return {k: len(v) for k, v in out.items()}


def load_event_overrides():
    """Manual corrections to the automatic event/city choice."""
    path = os.path.join(HERE, "event-overrides.json")
    if not os.path.exists(path):
        return {}
    raw = json.load(open(path, encoding="utf-8"))
    # keyed case-blind: ESPN wrote "BATTLE 4 ATLANTIS" before 2021 and
    # "Presented by" / "presented by" in different years
    return {k.lower(): v for k, v in raw.items() if not k.startswith("_")}


def offsite_games(evs):
    """Home games played somewhere that is NOT the home team's own building.

    Northwestern hosted Michigan at Wrigley Field in 2025 and Michigan State
    hosted Penn State at Ford Field in 2023. ESPN calls neither a neutral site
    -- there IS a home team -- so nothing in the payload says the venue is
    remarkable. It is derivable: count each home team's venues this season and
    flag the rare one.

    "Rare" is at most TWO games, not a percentage. Several teams keep a real
    second home floor -- UConn splits Gampel and Hartford almost evenly,
    St John's plays a quarter of its home games at Madison Square Garden --
    and a percentage cutoff either admits all of those or loses Wrigley, which
    was 2 of Northwestern's 7. The absolute cutoff separates them cleanly:
    measured across the archive it keeps the six one-offs and drops every
    second home floor.

    Counted PER SEASON, because "usual" moves: Northwestern's usual venue was
    the temporary lakefront stadium in 2025 and Ryan Field again in 2026.
    """
    venues = collections.defaultdict(collections.Counter)
    rows = []
    for x in evs:
        comps = x.get("competitions") or []
        if not comps or comps[0].get("neutralSite"):
            continue
        c = comps[0]
        name = ((c.get("venue") or {}).get("fullName") or "").strip()
        home = next((k for k in (c.get("competitors") or [])
                     if k.get("homeAway") == "home"), None)
        if not name or not home:
            continue
        venues[home["team"]["id"]][name] += 1
        rows.append((x["id"], home["team"]["id"], name))

    out = {}
    for gid, tid, name in rows:
        seen = venues[tid]
        usual, times = seen.most_common(1)[0]
        # The last two guards protect an IN-PROGRESS season, where a team may
        # have played too few home games for "usual" to mean anything yet.
        if name != usual and seen[name] <= 2 and times > seen[name]                 and sum(seen.values()) >= 4:
            out[gid] = name
    return out


def espn_saturday_ids(evs):
    """One ESPN game per Saturday: the LATEST tip between 6pm and 9:30pm ET.

    His rule, 2026-09-09, replacing a 6:30pm cutoff that cut through the 6pm
    block and admitted up to three games a night. Measured across the archive
    it selects 46 Saturdays with no ties at all, and lands on the late marquee
    game -- North Carolina at Duke, Kentucky at Tennessee, Duke at Virginia.

    Since 2026-09-10 this no longer decides the WINDOW -- `cbb_slots` admits
    every 6:00-9:30pm ESPN Saturday game -- only which of them is labelled
    "ESPN Primetime". The bracket was widened to 9:30pm to match, so "the
    latest" means the latest of the games actually in the window.
    """
    best = {}
    for x in evs:
        comps = x.get("competitions") or []
        if not comps:
            continue
        if "ESPN" not in set(networks(comps[0])):
            continue
        d = dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ")               .replace(tzinfo=dt.timezone.utc).astimezone(ET)
        if d.weekday() != 5 or d.month not in (1, 2, 3):
            continue
        mins = d.hour * 60 + d.minute
        if not (18 * 60 <= mins <= 21 * 60 + 30):
            continue
        cur = best.get(d.date())
        if cur is None or mins > cur[0]:
            best[d.date()] = (mins, x["id"])
    return {v[1] for v in best.values()}


def harvest():
    keep, teams = [], {}
    latest_conf = {}          # (sport, team id) -> (date, conference id)
    overrides = load_overrides()
    extras = load_extras()
    net_overrides = load_network_overrides()
    # A rival loss in a series he ruled (seed_series.SERIES) or tagged from his
    # phone reaches Rivals whatever else is true of it -- before this, a plain
    # home and home loss such as Oklahoma at Ohio State (2017) never did.
    series_ids = {gid for gid, _tag, _label in seed_series.SERIES}
    try:
        for gid, entry in json.load(open(os.path.join(HERE, "docs", "tags.json"),
                                         encoding="utf-8")).items():
            if set(entry.get("tags") or []) & {"Home & Home", "Neutral & Neutral",
                                               "Home & Neutral"}:
                series_ids.add(gid)
    except (OSError, ValueError):
        pass
    shows = show_games()
    ev_overrides = load_event_overrides()
    for code in ("CFB", "CBB"):
        bt = rules.BIG_TEN[code]
        for y in RIVAL_SEASONS + SEASONS:
            # before the archive, only games his rivals played -- for Rivals alone
            archive_era = y in SEASONS
            evs = events(code, y) if archive_era else rival_events(code, y)
            fox_fri = fox_friday_dates(evs) if code == "CFB" else set()
            wk0 = week_zero_ids(evs) if code == "CFB" else set()
            espn_sat = espn_saturday_ids(evs) if code == "CBB" else set()
            sizes = event_sizes(evs)
            offsite = offsite_games(evs)
            for x in evs:
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
                # RIVALS (his call 2026-09-11): a game Ohio State or Michigan
                # State (both sports) or Notre Dame (football) LOST. Two of them
                # meeting only counts when rules.RIVALS_INCLUDE names the game.
                stype = (x.get("season") or {}).get("type")
                rivals_here = rules.RIVALS_BY_SPORT[code]
                # Notre Dame basketball counts only in the NCAA Tournament --
                # or against Michigan, whose every win over a rival counts
                michigan_won = any(k["team"]["id"] == "130" and k.get("winner") for k in cs)
                if michigan_won or rules.is_ncaa_tournament(
                        stype, [n.get("headline") for n in (c.get("notes") or [])]):
                    rivals_here = rivals_here | rules.RIVALS_NCAA_ONLY.get(code, set())
                rival_loss = (
                    any(k["team"]["id"] in rivals_here and not k.get("winner") for k in cs)
                    and (not all(k["team"]["id"] in rivals_here for k in cs)
                         or x["id"] in rules.RIVALS_INCLUDE))
                postseason = stype == 3
                # bowls / CFP / NCAA are dropped -- unless a rival lost one
                if stype != 2 and not (postseason and rival_loss):
                    continue

                d = dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ") \
                      .replace(tzinfo=dt.timezone.utc).astimezone(ET)
                # Regulation is 4 quarters of football, 2 halves of
                # basketball; any period beyond that is overtime.
                period = (c.get("status") or {}).get("period") or 0
                overtime = period > (4 if code == "CFB" else 2)
                # every team's conference AS OF its latest game, archive or
                # not: the Team filter sorts by current membership, and a
                # team's latest ARCHIVE game can predate a move (Stanford's is
                # a 2023 Pac-12 game)
                for k in cs:
                    prev = latest_conf.get((code, k["team"]["id"]))
                    if prev is None or d >= prev[0]:
                        latest_conf[(code, k["team"]["id"])] = (
                            d, str(k["team"].get("conferenceId")))
                # ESPN's networks, or his when ESPN has none at all -- filled
                # before the window rules, so they judge the real network
                nets = set(networks(c)) or set(net_overrides.get(x["id"], ()))
                ranks = [rank_of(k) for k in cs]
                # a rival loss with no ranking on either side asks that week's
                # AP poll, because ESPN drops some old rankings (see ap_ranks)
                ap = {}
                if rival_loss and stype == 2 and not any(ranks):
                    wk_no = (x.get("week") or {}).get("number")
                    if wk_no:
                        ap = ap_ranks(code, y, wk_no)
                confs = [str(k["team"].get("conferenceId")) for k in cs]
                win = [k for k in cs if k.get("winner")]
                lose = [k for k in cs if not k.get("winner")]

                team_ids = [k["team"]["id"] for k in cs]
                # Read BEFORE the branch below: the CBB suffix needs it, and
                # assigning it after meant every basketball game was tested
                # against the PREVIOUS game's headlines.
                heads = [n.get("headline") or "" for n in (c.get("notes") or [])]
                black_friday = False
                opener = False
                suffix = None
                # A conference tournament belongs to no broadcast package, so
                # it is never Marquee and never carries a slot label.
                tourney = (rules.is_championship(heads)
                           and d.month in (3, 4) and code == "CBB")
                if code == "CFB":
                    slots = rules.cfb_slots(nets, d, y, team_ids, set(confs),
                                            fox_fri)
                    black_friday = rules.cfb_black_friday(
                        nets, d, y, big_ten=(bt in confs))
                    # Week 0 and the non-Saturday Week 1 games read their week
                    # and nothing else -- no window, so no header and no Marquee.
                    opener = rules.cfb_opener(
                        nets, d, (x.get("week") or {}).get("number"),
                        week0=x["id"] in wk0, big_ten=(bt in confs),
                        ranked=any(ranks), notre_dame=rules.NOTRE_DAME in team_ids)
                    if opener:
                        slots = set()
                else:
                    slots = rules.cbb_slots(nets, d, all(q == bt for q in confs),
                                            any(ranks), bt in confs)
                    suffix = rules.cbb_header_suffix(
                        nets, d, tourney=tourney, big_ten=(bt in confs),
                        espn_sat=x["id"] in espn_sat)
                conf, head = rules.power5_title(heads, code)
                title = rules.is_title_game(code, conf, head)
                # a show broadcast from this game? match either side of the
                # date, since a late kickoff shifts the Eastern one
                import seed_tags as _st
                names = frozenset(_st.norm(k["team"].get("location") or "")
                                  for k in cs)
                show = any((code, dd, names) in shows for dd in (
                    d.date().isoformat(),
                    (d.date() - dt.timedelta(days=1)).isoformat(),
                    (d.date() + dt.timedelta(days=1)).isoformat()))
                # A championship game outside the Power Four/Five keeps no TV
                # window -- the Mountain West title game is not "FOX Friday".
                # Football only: a Big East tournament game on FOX genuinely is
                # a FOX basketball game.
                if code == "CFB" and not conf and rules.is_championship(heads):
                    slots = set()
                gtype = None
                if len(win) == 1 and len(lose) == 1:
                    # a championship game with no category of its own is filed
                    # by result rather than left uncategorised
                    # a Big Ten Tournament game before the Final
                    b1g_run = (code == "CBB" and conf == "Big Ten"
                               and not title)
                    gtype = rules.game_type(code, rank_of(win[0]),
                                            rank_of(lose[0]), bt in confs,
                                            p5_title=title,
                                            b1g_tourney_run=b1g_run)
                # a named event (Battle 4 Atlantis, SEC Quarterfinals) for the
                # blue chip, when it is not already a Power Five title
                # An event name is kept only when more than two teams played
                # under it this season -- otherwise it is one neutral-site game
                # and the CITY is the more useful label. `ev_overrides` can
                # force either answer: a name to use, or null to force the city.
                # FOOTBALL never shows an event name: he wants the city every
                # time, so the Aflac and Chick-fil-A Kickoffs read Atlanta and
                # Charlotte. Basketball keeps its tournaments.
                event = None
                for h in (heads if code == "CBB" else []):
                    base = h.split(" - ")[0].strip()
                    if not base or conf:
                        break
                    if base.lower() in ev_overrides:
                        event = ev_overrides[base.lower()]
                    elif sizes.get(base, 0) > 2:
                        event = base
                    break
                # Being a conference-tournament game is NOT a qualification on
                # its own: it took in 265 early-round basketball games nothing
                # could reach. A championship game always has a type.
                # Basketball events he wants every year, and football
                # neutral-site kickoffs in August and September (his calls
                # 2026-09-11): on TV Windows whatever the network or time
                showcase = (code == "CBB" and stype == 2
                            and rules.cbb_showcase(heads))
                kickoff = (code == "CFB" and stype == 2 and rules.cfb_neutral_kickoff(
                    d, y, bool(c.get("neutralSite")),
                    [(k["team"]["id"], str(k["team"].get("conferenceId"))) for k in cs]))
                normal = bool(slots or gtype or title or black_friday or show
                              or opener or showcase or kickoff
                              or x["id"] in overrides or x["id"] in extras)
                # A conference tournament or playoff round that is NOT the
                # final is out of the archive entirely, both tabs (his call
                # 2026-09-09). ESPN publishes no rankings for tournament games
                # in the early seasons anyway -- 0 of 600 in 2021-22 -- so the
                # ranking rules could never judge them fairly. That also drops
                # non-Power-Six conference titles and the FCS playoff rounds.
                # ...but "Championship" in an early-season showcase name is not
                # a conference tournament -- the Baha Mar Championship is a
                # November event, and Purdue v Texas Tech there is a real game.
                # Conference tournaments are a MARCH thing in basketball.
                tourney_round = rules.is_championship(heads) and (
                    code == "CFB" or d.month in (3, 4))
                # A conference championship or playoff round stays out even
                # when a show broadcast from it -- he does not want postseason
                # under Big Noon or GameDay, and the 2024 Mountain West
                # Championship is the case that tests it.
                if (tourney_round and not title) or postseason or not archive_era:
                    normal = False
                # A rival's loss counts for Rivals when it was postseason or a
                # conference tournament, had a ranked team, was at a neutral
                # site, or sat in a Marquee window. (The home & home family is
                # checked in the app, since those tags live in tags.json.)
                rivals = rival_loss and bool(
                    michigan_won                         # every loss to Michigan (his call)
                    or x["id"] in series_ids             # a home and home, and the like
                    or postseason or tourney_round or any(ranks) or c.get("neutralSite")
                    or any(ap.get(k["team"]["id"]) for k in cs)
                    or rules.is_marquee(code, nets, d, slots, big_ten=(bt in confs),
                                        tourney=tourney))
                if not normal and not rivals:
                    continue
                # kept ONLY for Rivals (a bowl, an early tournament round): strip
                # whatever would put it on TV Windows or Key Games
                rivals_only = not normal
                if rivals_only:
                    slots, gtype, black_friday, show, opener = set(), None, False, False, False
                    showcase = kickoff = False
                # A championship game carries NO TV window chip (his call): it
                # is admitted to that view by the `title` flag instead.
                if title:
                    slots = set()
                forced = x["id"] in overrides
                if forced:
                    slots = set(overrides[x["id"]])
                # the card is drawn from the slots as the rules left them; an
                # extra window only adds the game to a filter and to Marquee
                card_slots = set(slots)
                slots |= set(extras.get(x["id"], ()))

                side = []
                for k in cs:
                    t = k["team"]
                    teams[t["id"]] = {"name": t["displayName"],
                                      "short": rules.display_name(
                                          t.get("location") or t["displayName"]),
                                      "abbr": t.get("abbreviation"),
                                      "color": t.get("color"),
                                      "alt": t.get("alternateColor")}
                    side.append({"id": t["id"], "score": int(k["score"]),
                                 "rank": rank_of(k) or (ap.get(t["id"]) if rivals_only else None),
                                 "win": bool(k.get("winner")),
                                 "home": k.get("homeAway") == "home",
                                 "conf": str(t.get("conferenceId"))})
                v = c.get("venue") or {}
                keep.append({
                    "id": x["id"], "sport": code, "season": y,
                    "date": d.strftime("%Y-%m-%d"), "dow": rules.DOW[d.weekday()],
                    "time": d.strftime("%H:%M"),
                    "neutral": bool(c.get("neutralSite")), "ot": overtime,
                    "show": show,
                    # ESPN carries week.number on every CFB event; basketball
                    # has one too but it means nothing to a viewer, so only
                    # football displays it.
                    # ...and ESPN numbers Week 0 as week 1; see week_zero_ids
                    "week": (None if postseason
                             else 0 if x["id"] in wk0
                             else (x.get("week") or {}).get("number")),
                    "venue": v.get("fullName"),
                    "mq": (not rivals_only) and rules.is_marquee(code, nets, d, slots,
                                           big_ten=(bt in confs),
                                           tourney=tourney),
                    "offsite": offsite.get(x["id"]),
                    "city": rules.display_city(
                        (v.get("address") or {}).get("city"), v.get("fullName")),
                    "nets": sorted(nets), "teams": side,
                    "header": (rules.cfb_header(card_slots, d, forced)
                               if code == "CFB" else suffix),
                    "slots": sorted(slots), "type": gtype,
                    "champ": conf, "round": head, "title": title,
                    "event": event, "bfri": black_friday, "suffix": suffix,
                    "opener": opener,
                    "rival_loss": rival_loss, "rivals": rivals, "post": postseason,
                    "rivals_only": rivals_only,
                    # a CFP game short of the final is located by its bowl
                    "bowl": (rules.cfp_bowl(stype, heads, season=y)
                             if code == "CFB" else None),
                    "showcase": showcase, "kickoff": kickoff,
                    # the header of a game that is an EVENT: "Fiesta Bowl",
                    # "College Football Playoff | Quarters", "NCAA Tournament |
                    # Round 1", "Big Ten Tournament | Semis", "Big Ten Championship"
                    "stage": rules.stage_label(code, stype, heads, conf=conf,
                                               month=d.month, season=y),
                })
    keep.sort(key=lambda g: (g["date"], g["time"]))
    for (code, tid), (_, conf) in latest_conf.items():
        if tid in teams:
            teams[tid].setdefault("conf", {})[code] = conf
    os.makedirs(OUT, exist_ok=True)
    json.dump({"games": keep, "teams": teams, "order": rules.ORDER,
               "window_net": rules.WINDOW_NET,
               "hidden_windows": rules.HIDDEN_WINDOWS,
               "header_tint": rules.HEADER_TINT, "net_tint": rules.NET_TINT,
               "big_ten": rules.BIG_TEN, "season_names": rules.SEASON_NAMES,
               "net_priority": rules.NET_PRIORITY,
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
