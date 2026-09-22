"""Fetch every past CFB/CBB game matching rules.py and freeze it to JSON.

Past games never change, so this runs once per new week of games -- there is
no daily build and nothing goes stale. `cache/` holds raw ESPN responses so a
re-run is free.
"""
import collections, csv, datetime as dt, io, json, os, re, sys, time
import html as html_lib
import unicodedata
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

# FLOORS FOR THE GOOGLE SHEET (2026-09-14). A row group COLLAPSED in the
# browser is omitted from the gviz export, so a tab can shrink to nothing
# without being edited. These are set well under the real counts -- 302
# show-days and 733 Michigan rows at the time of writing -- so ordinary
# editing never trips them, but a collapse does.
LOCATIONS_FLOOR = 150
SHEET_FLOOR = 600
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
          "CBB": ("basketball/mens-college-basketball", "50"),
          # hockey is read team by team, never off the scoreboard
          "CHK": ("hockey/mens-college-hockey", None)}


def get_json(url, params=None, timeout=60, tries=4):
    """ESPN, with RETRIES. A single flaky answer must not end a run: the first
    cloud build died on one 504 out of ~300 requests, four minutes in, with a
    cold cache (2026-09-13). Only transient failures are retried -- a 5xx, a
    timeout, a dropped connection -- and the wait doubles each time. A 404 is
    real and raises at once."""
    wait = 2
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code >= 500:
                raise requests.HTTPError("%d from ESPN" % r.status_code, response=r)
            r.raise_for_status()
            return r.json()
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            last = attempt == tries - 1
            if last or (status is not None and status < 500):
                raise
            print("  retry %d/%d after %s" % (attempt + 1, tries - 1, e),
                  file=sys.stderr)
            time.sleep(wait)
            wait *= 2


# ESPN CHANGED THE SCOREBOARD OVERNIGHT (found 2026-09-16, when the 6am build
# died): a date RANGE ("20260801-20261231") now answers 400 "Failed to get
# events endpoint", for both sports, and a limit of ~1000 is silently IGNORED --
# the default 25 games come back, with no error. A single day with limit=500
# still returns the full slate. So a range is walked one day at a time here,
# under the old call signature, and every limit is held to 500.
SCOREBOARD_LIMIT = 500


def scoreboard(sport, params):
    params = dict(params or {})
    if "limit" in params:
        params["limit"] = min(int(params["limit"]), SCOREBOARD_LIMIT)
    rng = str(params.get("dates") or "")
    if "-" not in rng:
        return get_json(f"{BASE}/{sport}/scoreboard", params=params)
    a, b = rng.split("-", 1)
    day = dt.datetime.strptime(a, "%Y%m%d").date()
    end = dt.datetime.strptime(b, "%Y%m%d").date()
    out, seen = {"events": []}, set()
    while day <= end:
        params["dates"] = day.strftime("%Y%m%d")
        got = get_json(f"{BASE}/{sport}/scoreboard", params=params)
        for x in got.get("events") or []:
            if x.get("id") not in seen:
                seen.add(x.get("id"))
                out["events"].append(x)
        if len(got.get("events") or []) >= SCOREBOARD_LIMIT:
            print("  WARN: %s %s hit the %d cap" % (sport, day, SCOREBOARD_LIMIT),
                  file=sys.stderr)
        day += dt.timedelta(days=1)
    return out


def fetch(sport, params, key, cacheable=True):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, key + ".json")
    if cacheable and os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    d = scoreboard(sport, params)
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


def old_season_events(code, y):
    """Every game of a season before the archive, straight from the scoreboard.
    Nothing is cached whole -- those seasons would cost gigabytes in the
    Drive-synced cache -- so the callers keep only what they need."""
    sport, grp = SPORTS[code]
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
    seen, out = set(), []
    for x in ev:
        if x.get("id") and x["id"] not in seen:
            seen.add(x["id"])
            out.append(x)
    return out


def michigan_events(code, y):
    """Every Michigan game in a season before the archive, for the Michigan
    view, cached as cache/michigan-SPORT-SEASON.json. The same walk keeps that
    season's postseason for EVERY team as cache/post-SPORT-SEASON.json -- an
    opponent's CFP or NCAA finish, and last season's champion, need them."""
    path = os.path.join(CACHE, "michigan-%s-%d.json" % (code.lower(), y))
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))["events"]
    ev = old_season_events(code, y)
    keep = [x for x in ev
            if any((k.get("team") or {}).get("id") == rules.MICHIGAN
                   for k in (x.get("competitions") or [{}])[0].get("competitors") or [])]
    post = [x for x in ev if (x.get("season") or {}).get("type") == 3]
    if season_over(code, y):
        json.dump({"events": keep}, open(path, "w", encoding="utf-8"))
        json.dump({"events": post}, open(os.path.join(
            CACHE, "post-%s-%d.json" % (code.lower(), y)), "w", encoding="utf-8"))
    return keep


# ---------------------------------------------------------------------------
# COLLEGE HOCKEY (his plan, 2026-09-16). A team view only -- no TV Windows, Key
# Games or coverage rules -- so it is harvested on its own, TEAM BY TEAM from
# ESPN's schedule endpoint, into the same card records the basketball Michigan
# view uses. It never passes through the football/basketball loop above.
# ---------------------------------------------------------------------------

def hockey_schedule(team_id, y):
    """One team's season y (y-(y+1)): the regular season and the postseason,
    from ESPN's team schedule. ESPN names a hockey season for the year it ENDS.
    Cached once the season is over."""
    path = os.path.join(CACHE, "hockey-%s-%d.json" % (team_id, y))
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))["events"]
    sport = SPORTS["CHK"][0]
    out, seen = [], set()
    for stype in (2, 3):
        try:
            got = get_json("%s/%s/teams/%s/schedule" % (BASE, sport, team_id),
                           params={"season": y + 1, "seasontype": stype})
        except requests.HTTPError:
            continue
        for x in got.get("events") or []:
            if x.get("id") and x["id"] not in seen:
                seen.add(x["id"])
                x["_stype"] = stype
                out.append(x)
    if season_over("CHK", y):
        json.dump({"events": out}, open(path, "w", encoding="utf-8"))
    return out


def hockey_team_info(team_id):
    """Name and colours for a hockey team, which the schedule payload leaves
    out. Cached for good in cache/hockey-teams.json."""
    path = os.path.join(CACHE, "hockey-teams.json")
    known = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    if team_id not in known:
        t = {}
        # ESPN's HOCKEY team record often has no colour at all; the same school's
        # basketball record usually does (same id), so that is tried next
        for sport in (SPORTS["CHK"][0], SPORTS["CBB"][0], SPORTS["CFB"][0]):
            try:
                got = get_json("%s/%s/teams/%s" % (BASE, sport, team_id)).get("team") or {}
            except requests.HTTPError:
                continue
            for k, v in got.items():
                if v and not t.get(k):
                    t[k] = v
            # "000000" is ESPN's placeholder for no colour, not a real black
            if t.get("color") and t["color"].lower() != "000000":
                break
            t.pop("color", None)
        known[team_id] = {"color": t.get("color"), "alt": t.get("alternateColor"),
                          "location": t.get("location"), "name": t.get("displayName"),
                          "abbr": t.get("abbreviation")}
        os.makedirs(CACHE, exist_ok=True)
        json.dump(known, open(path, "w", encoding="utf-8"))
    return known[team_id]


# USCHO names a few schools differently from ESPN's `location`: USCHO's
# flattened name -> ESPN's. Extend as the harvest reports misses.
USCHO_ALIAS = {"aic": "americaninternational", "lakesuperior": "lakesuperiorstate",
               "miami": "miamioh", "nebraskaomaha": "omaha"}


def uscho_polls(y):
    """Every USCHO Division I men's poll of season y, oldest first, as
    [(poll date, {flattened school name: rank})] -- top 20 only.

    ESPN carries college hockey polls only from about 2021-22, so USCHO is the
    source for every season (his call 2026-09-16), which also keeps one poll
    throughout. A USCHO poll page for ANY date answers with the poll in force
    that day, the whole poll embedded as JSON, so the season is walked a week at
    a time and de-duplicated by the poll's own date.
    """
    # FINISHED SEASONS LIVE IN THE REPO, not the cache (2026-09-16): the 6am
    # cloud build starts from its own cache and would otherwise have to reach
    # USCHO from GitHub's servers, which a site like that may well refuse. Only
    # the season in progress is fetched live.
    path = os.path.join(HERE, "data", "uscho", "uscho-%d.json" % y)
    if os.path.exists(path):
        return [tuple(p) for p in json.load(open(path, encoding="utf-8"))]
    polls = {}
    d, end = dt.date(y, 9, 22), min(dt.date(y + 1, 4, 20), dt.date.today())
    season = "%d%d" % (y, y + 1)
    while d <= end:
        try:
            r = requests.get("https://www.uscho.com/rankings/d-i-mens-poll/%s/" % d.isoformat(),
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            body = html_lib.unescape(r.text) if r.status_code == 200 else ""
        except requests.RequestException:
            body = ""
        for row in re.findall(r'\{[^{}]*"rnk":\d+[^{}]*\}', body):
            try:
                j = json.loads(row)
            except ValueError:
                continue
            if j.get("season") != season or j.get("gender") != "m":
                continue
            polls.setdefault(j["PollDate"], {})[flat(j.get("shortname") or "")] = j["rnk"]
        d += dt.timedelta(days=7)
    out = sorted(polls.items())
    if season_over("CHK", y) and out:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(out, open(path, "w", encoding="utf-8"), separators=(",", ":"))
    return out


def uscho_rank(polls, day, location, misses):
    """A team's USCHO rank in the poll in force on `day`, or None."""
    best = {}
    for date, ranks in polls:
        if date <= day:
            best = ranks
        else:
            break
    key = flat(location or "")
    for k, v in best.items():
        if USCHO_ALIAS.get(k, k) == key:
            return v
    return None


# The Big Ten's hockey members, by season: the league began in 2013-14 and
# Notre Dame joined in 2017-18.
B1G_HOCKEY = {"130", "127", "194", "135", "275", "213"}
B1G_HOCKEY_ND_FROM = 2017
# The Big Ten Tournament was played at a NEUTRAL arena in its first four years
# (St. Paul, Detroit, St. Paul, Detroit: 2014-2017) and on campus since.
B1G_HOCKEY_NEUTRAL_UNTIL = 2016


def hockey_conf(team_id, y):
    if team_id in B1G_HOCKEY or (team_id == rules.NOTRE_DAME and y >= B1G_HOCKEY_ND_FROM):
        return rules.BIG_TEN["CHK"]
    if (hockey_team_info(team_id).get("location") or "") in rules.ECAC_HOCKEY:
        return "ECAC"
    return "0"


def hockey_stage(heads):
    """ESPN's note, in the stage vocabulary the basketball cards already use:
    "Big Ten - Semifinal" -> "Big Ten Tournament | Semis", and "NCAA Men's
    Hockey Championship - Allentown Regional Final" -> "NCAA Tournament |
    Regional Final"."""
    for h in heads:
        part = h.split(" - ", 1)[1] if " - " in h else ""
        low = part.lower()
        if h.startswith("Big Ten"):
            rnd = ("Quarters" if "quarter" in low else "Semis" if "semi" in low
                   else "Championship" if ("final" in low or "champ" in low)
                   else "First Round" if "first" in low else part or "Tournament")
            return "Big Ten Tournament | " + rnd
        if h.startswith("ECAC"):
            rnd = ("Quarters" if "quarter" in low else "Semis" if "semi" in low
                   else "Third Place" if "third" in low or "consol" in low
                   else "Championship" if ("final" in low or "champ" in low)
                   else "First Round" if "first" in low or "1st" in low
                   else part or "Tournament")
            return "ECAC Tournament | " + rnd
        if "NCAA" in h and "Hockey" in h:
            rnd = ("Frozen Four" if "frozen" in low
                   else "First Round" if "regional semi" in low
                   else "Second Round" if "regional final" in low
                   else "Championship" if "champ" in low
                   else part or "Round")
            return "NCAA Tournament | " + rnd
    return None


# ESPN LABELS NO HOCKEY TOURNAMENT GAME BEFORE 2022-23 -- no note, no venue,
# and the postseason filed as regular season -- on the schedule, the scoreboard
# and the game summary alike (checked 2026-09-16). Those games are recognised by
# DATE instead, from Michigan's own schedules:
#   the Big Ten Tournament's first day, and whether its rounds were a DAY apart
#   (the neutral-site years and the 2021 bubble) or a WEEK apart (on campus);
#   the NCAA Tournament's opening day, after which a team's games run Regional
#   Semifinal, Regional Final, Frozen Four, Championship.
B1G_HOCKEY_TOURNEY = {          # season: (first day, days between rounds)
    2013: ("2014-03-20", 1), 2014: ("2015-03-19", 1), 2015: ("2016-03-17", 1),
    2016: ("2017-03-16", 1), 2017: ("2018-03-02", 7), 2018: ("2019-03-08", 7),
    2019: ("2020-03-06", 7), 2020: ("2021-03-13", 1), 2021: ("2022-03-04", 7)}
# the neutral years -- and the 2021 bubble in South Bend (his catch 2026-09-16)
B1G_HOCKEY_CITY = {2013: "St. Paul", 2014: "Detroit", 2015: "St. Paul", 2016: "Detroit",
                   2020: "South Bend"}
NCAA_HOCKEY_START = {           # the Wednesday before the regional weekend
    2008: "2009-03-25", 2009: "2010-03-24", 2010: "2011-03-23", 2011: "2012-03-21", 2012: "2013-03-27",
    2013: "2014-03-26", 2014: "2015-03-25", 2015: "2016-03-23", 2016: "2017-03-22",
    2017: "2018-03-21", 2018: "2019-03-27", 2020: "2021-03-24", 2021: "2022-03-23"}
FROZEN_FOUR_CITY = {2009: "Detroit", 2010: "St. Paul", 2011: "Tampa", 2012: "Pittsburgh",
                    2013: "Philadelphia", 2014: "Boston", 2015: "Tampa", 2016: "Chicago",
                    2017: "St. Paul", 2018: "Buffalo", 2020: "Pittsburgh", 2021: "Boston"}
# his names (2026-09-16): the regional games are the FIRST and SECOND ROUND
NCAA_ROUNDS = ["First Round", "Second Round", "Frozen Four", "Championship"]
# regional cities, per team and season, where ESPN has no venue
NCAA_REGIONAL_CITY = {("130", 2015): "Cincinnati", ("130", 2017): "Worcester",
                      ("130", 2021): "Allentown",
                      ("172", 2011): "Green Bay", ("172", 2018): "Providence",
                      ("172", 2009): "Albany", ("172", 2016): "Manchester",
                      ("172", 2017): "Worcester"}
# THE ECAC TOURNAMENT, before ESPN labels it: its weekends are fixed to the
# NCAA regionals -- the championship weekend (semifinals, final, and a
# third-place game in the early years) is the week before, the quarterfinals
# two weeks before, the first round three. Checked on Cornell's 2010, 2012,
# 2018 and 2019 (2026-09-16). 2019-20 had no NCAA Tournament, so its reference
# date is the one it would have had.
ECAC_REFERENCE = {2019: "2020-03-25"}
ECAC_CITY = {2009: "Albany", 2010: "Atlantic City", 2011: "Atlantic City",
             2012: "Atlantic City"}          # Lake Placid from 2013-14 on


# REGULAR-SEASON EVENTS, per team (his list, 2026-09-16) -- ESPN gives these
# no venue or name either. The Great Lakes Invitational is a neutral-site
# event like basketball's CBS Sports Classic; the Ice Breaker is an MTE, with
# the MTE card and its rounds.
HOCKEY_EVENTS = {
    "130": [
        {"event": "Great Lakes Invitational", "city": "Detroit",
         "seasons": range(2013, 2020), "window": ("12-26", "01-03")},
        {"event": "Ice Breaker", "city": "Duluth", "mte": True,
         "dates": ("2021-10-15", "2021-10-16")},
    ],
}


def hockey_event(team_id, y, day):
    """The regular-season event a game belongs to, or None."""
    md = day[5:]
    for e in HOCKEY_EVENTS.get(team_id, ()):
        if "dates" in e and day in e["dates"]:
            return e
        if "seasons" in e and y in e["seasons"]:
            lo, hi = e["window"]
            if md >= lo or md <= hi:
                return e
    return None


def hockey_old_stage(team_id, y, day, conf_team_ids, ncaa_seen, earlier=()):
    """The stage of a pre-2022-23 game, from its date alone. `ncaa_seen` counts
    the team's NCAA games so far this season, oldest first; `earlier` is the
    team's records so far, for the ECAC's semifinal-then-final order."""
    ncaa = NCAA_HOCKEY_START.get(y)
    if ncaa and day >= ncaa:
        rnd = NCAA_ROUNDS[min(ncaa_seen, 3)]
        city = (FROZEN_FOUR_CITY.get(y) if ncaa_seen >= 2
                else NCAA_REGIONAL_CITY.get((team_id, y)))
        return "NCAA Tournament | " + rnd, city, True
    if hockey_conf(team_id, y) == "ECAC":
        ref = NCAA_HOCKEY_START.get(y) or ECAC_REFERENCE.get(y)
        if not ref or len(conf_team_ids) != 2:
            return None, None, False
        friday = dt.date.fromisoformat(ref) + dt.timedelta(days=2)
        before = (friday - dt.date.fromisoformat(day)).days
        if 5 <= before <= 7:
            done = [g for g in earlier if g["season"] == y and (g.get("stage") or "")
                    .startswith("ECAC Tournament | ") and g["stage"].split(" | ")[1]
                    in ("Semis", "Championship", "Third Place")]
            if not done:
                rnd = "Semis"
            else:
                won = any(t["win"] and t["id"] == team_id for t in done[-1]["teams"])
                rnd = "Championship" if won else "Third Place"
            return "ECAC Tournament | " + rnd, ECAC_CITY.get(y, "Lake Placid"), False
        if 8 <= before <= 14:
            return "ECAC Tournament | Quarters", None, False
        if 15 <= before <= 21:
            return "ECAC Tournament | First Round", None, False
        return None, None, False
    first = B1G_HOCKEY_TOURNEY.get(y)
    if first and day >= first[0] and len(conf_team_ids) == 2:
        gap = (dt.date.fromisoformat(day) - dt.date.fromisoformat(first[0])).days // first[1]
        rnd = ["Quarters", "Semis", "Championship"][min(gap, 2)]
        return "Big Ten Tournament | " + rnd, B1G_HOCKEY_CITY.get(y), False
    return None, None, False


# ---------------------------------------------------------------------------
# USCHO'S TEAM SCHEDULES (2026-09-16): the arena, a neutral flag, the event and
# a note naming the round and the city -- "Big Ten Semifinal (St. Paul, MN)",
# "NCAA E Reg Champ (Providence, RI)", "Red Hot Hockey (Madison Square Garden,
# New York, NY)" -- for every game of every season, which ESPN has none of.
# Matched to ESPN's games by date and opponent. Finished seasons are committed
# in data/uscho/, so the cloud build never needs USCHO for them.
# ---------------------------------------------------------------------------
USCHO_SLUG = {"130": "michigan", "172": "cornell",
              # the three rivals, for Hockey Rivals (2026-09-18)
              "127": "michigan-state", "194": "ohio-state", "87": "notre-dame"}
USCHO_SCHED = {}
USCHO_KEEP = ("gdate", "visitor", "home", "vis_name", "home_name", "vscore", "hscore",
              "ots", "arena_name", "neutral", "type", "tourn_shortname", "note",
              "sho_notes", "tv", "hconf", "vconf", "complete", "starttime", "gameid")


def uscho_schedule(team_id, y):
    slug = USCHO_SLUG.get(team_id)
    if not slug:
        return []
    if (slug, y) in USCHO_SCHED:
        return USCHO_SCHED[(slug, y)]
    path = os.path.join(HERE, "data", "uscho", "sched-%s-%d.json" % (slug, y))
    if os.path.exists(path):
        out = json.load(open(path, encoding="utf-8"))
    else:
        out, body = [], ""
        try:
            r = requests.get("https://www.uscho.com/scoreboard/%s/mens-hockey/%d-%d/"
                             % (slug, y, y + 1), headers={"User-Agent": "Mozilla/5.0"},
                             timeout=40)
            body = html_lib.unescape(r.text) if r.status_code == 200 else ""
        except requests.RequestException:
            pass
        seen = set()
        for m in re.finditer(r'\{"visitor":', body):
            depth, i = 0, m.start()
            for j in range(i, min(len(body), i + 8000)):
                if body[j] == "{":
                    depth += 1
                elif body[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
            try:
                g = json.loads(body[i:j + 1])
            except ValueError:
                continue
            key = (g.get("gdate"), g.get("visitor"), g.get("home"))
            if key not in seen:
                seen.add(key)
                out.append({k: g.get(k) for k in USCHO_KEEP})
        if out and season_over("CHK", y):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            json.dump(out, open(path, "w", encoding="utf-8"), separators=(",", ":"))
    USCHO_SCHED[(slug, y)] = out
    return out


def uscho_match(sched, day, opp_loc):
    """USCHO's record of an ESPN game: the same date (or the day before, for a
    late western game ESPN files on the next Eastern day), against the same
    opponent."""
    want = flat(opp_loc)

    def named(g):
        for n in (flat(g.get("vis_name") or ""), flat(g.get("home_name") or "")):
            n = USCHO_ALIAS.get(n, n)
            if n and (n == want or (len(want) > 4 and (want in n or n in want))):
                return True
        return False
    d0 = dt.date.fromisoformat(day)
    for dd in (d0, d0 - dt.timedelta(days=1)):
        for g in sched:
            if str(g.get("gdate")) == dd.strftime("%Y%m%d") and g.get("type") != "ex" and named(g):
                return g
    return None


ARENA_WORDS = ("arena", "center", "centre", "garden", "field", "stadium", "coliseum",
               "fieldhouse", "rink", "pavilion", "forum", "auditorium")
# his MTEs (2026-09-16): Michigan's 2021-22 Ice Breaker; Cornell's Florida
# College Classic (2009-17) and its 2019-20, 2023-24 and 2024-25 events
HOCKEY_MTES = {"icebreaker": "Ice Breaker", "ice breaker": "Ice Breaker",
               "florida college classic": "Florida College Classic",
               "desert hockey classic": "Desert Hockey Classic",
               "adirondack winter invitational": "Adirondack Winter Invitational",
               "fortress inv": "Fortress Invitational"}


HOCKEY_NO_EVENT = {"Frozen Confines"}          # his call 2026-09-16
# HIS CORRECTIONS to single games (2026-09-17), by focus team and date: a key
# present replaces what USCHO gave; "labels" adds to the footer
HOCKEY_GAME_FIX = {
    ("130", "2015-02-07"): {"event": None, "city": "Soldier Field"},   # MSU, outdoors
    # 2026-27 WESTERN MICHIGAN is a home and away, the return leg outdoors at
    # Waldo Stadium (his call 2026-09-22)
    ("130", "2026-10-23"): {"series": "Home & Away"},
    ("130", "2027-01-30"): {"series": "Home & Away", "offsite": "Waldo Stadium"},
    ("130", "2016-11-04"): {"offsite": None},                          # at Arizona State
}
# THE NAMED EVENTS that show their VENUE after the name and their DATE in the
# header (his call 2026-09-17) -- the venue is USCHO's arena for the game, so
# the 2013 GLI reads Comerica Park without being told
VENUE_EVENTS = {"Great Lakes Invitational", "Duel in the D", "Red Hot Hockey",
                "The Frozen Apple"}
# USCHO's code for each focus team, to read its score from a USCHO record
USCHO_CODE = {"130": "um", "172": "cor", "127": "msu", "194": "osu", "87": "nd"}
# MTE rounds USCHO leaves unnamed and a tied opener cannot settle (his word)
HOCKEY_MTE_ROUND = {("172", "2023-12-30"): "Final"}    # Adirondack: ASU was the final


def uscho_details(g, team_id, opp_loc):
    """What a USCHO record says about a game: its stage or event, its city or
    venue, and whether it was a neutral site or a conference game."""
    note = (g.get("note") or "").strip()
    tn = (g.get("tourn_shortname") or "").strip()
    arena = (g.get("arena_name") or "").strip()
    nlow, low = note.lower(), (tn + " | " + note).lower()
    m = re.search(r"\(([^()]*)\)", note)
    parts = [p.strip() for p in m.group(1).split(",")] if m else []
    note_city = parts[-2] if len(parts) >= 2 else None
    head = note[:m.start()].strip() if m else note
    res = {"neutral": (g.get("neutral") or "").lower() == "yes",
           "conf_game": (g.get("type") or "").lower() in ("b10", "ec", "ecac") and not tn,
           "tv": g.get("tv") or ""}
    if tn.startswith("NCAA") or nlow.startswith("ncaa") or "regional" in nlow:
        rnd = ("Frozen Four" if ("national semi" in low or "frozen four" in low)
               else "Championship" if "national champ" in low
               else "First Round" if "semi" in low else "Second Round")
        city = note_city
        mm = re.search(r"NCAA ([A-Z][A-Za-z. ]+?) Regional", note)
        if not city and mm and mm.group(1).strip() not in (
                "East", "West", "Midwest", "Northeast", "E", "W", "NE", "MW"):
            city = mm.group(1).strip()
        res.update(stage="NCAA Tournament | " + rnd, city=city, neutral=True, post=True)
    elif tn == "Big Ten Tournament" or re.match(r"big (ten|10) (qtr|quarter|semi|champ|first)", nlow):
        rnd = ("First Round" if "first round" in nlow else "Quarters" if ("qtr" in nlow or "quarter" in nlow)
               else "Semis" if "semi" in nlow else "Championship")
        res.update(stage="Big Ten Tournament | " + rnd, city=note_city)
    elif tn == "ECAC Tournament" or re.match(r"ecac( hockey)? (qtr|quarter|semi|champ|first|opening|third)", nlow):
        rnd = ("First Round" if ("first round" in nlow or "opening" in nlow)
               else "Quarters" if ("qtr" in nlow or "quarter" in nlow)
               else "Semis" if "semi" in nlow else "Third Place" if "third" in nlow
               else "Championship")
        res.update(stage="ECAC Tournament | " + rnd, city=note_city)
    elif "great lakes" in low or nlow.startswith("gli"):
        # a neutral-site event with the MTE's grey frame, not its card
        # no city: the GLI is always Detroit (his call 2026-09-16)
        res.update(event="Great Lakes Invitational", frame=True, city=None, neutral=True)
    elif any(k in low for k in HOCKEY_MTES):
        name = next(v for k, v in HOCKEY_MTES.items() if k in low)
        # USCHO names the final and the third-place game; an unnamed game is the
        # semifinal only if it is the event's first -- decided in hockey_games
        rnd = ("Final" if "champ" in nlow else "Third Place" if ("third" in nlow or "3rd" in nlow)
               else None)
        res.update(event=name, mte=True, mte_round=rnd, city=note_city, neutral=True)
    # CORNELL'S THANKSGIVING GAMES AT THE GARDEN name only the event (his call
    # 2026-09-16) -- no "MSG" beside it
    elif "red hot" in low:
        res.update(event="Red Hot Hockey", city=None, neutral=True)
    elif "frozen apple" in low:
        res.update(event="The Frozen Apple", city=None, neutral=True)
    elif "madison square" in (arena + " " + note).lower() or "mad sq" in nlow:
        # CORNELL AT THE GARDEN is Red Hot Hockey against Boston University and
        # The Frozen Apple against anyone else (his call 2026-09-16)
        ev = None
        if team_id == rules.CORNELL:
            ev = "Red Hot Hockey" if flat(opp_loc) == "bostonuniversity" else "The Frozen Apple"
        res.update(event=ev, city=None if ev else "Madison Square Garden", neutral=True)
    elif (team_id == rules.MICHIGAN and flat(opp_loc) == "michiganstate"
          and any(a in (arena + " " + note).lower() for a in ("joe louis", "little caesars", "detroit"))):
        # DUEL IN THE D: Michigan-Michigan State in Detroit, every season but the
        # COVID one -- a neutral site, so the card reads "vs." (his call)
        res.update(event="Duel in the D", neutral=True, city=None)
    elif note and not re.match(r"(resched|cancel|at suny)", nlow) and arena and arena != "NA":
        # an outdoor game or a borrowed building: an event name when the note
        # carries one, otherwise the venue
        if m and head and not any(w in head.lower() for w in ARENA_WORDS):
            # an outdoor-game billing he does not want shown -- the city stays
            res.update(event=None if head in HOCKEY_NO_EVENT else head,
                       city=note_city or (parts[0] if parts else None))
        elif res["neutral"]:
            res.update(city=arena)
        else:
            res.update(offsite=arena)
    return res


# ---------------------------------------------------------------------------
# SEEDS for the Big Ten, ECAC and NCAA tournaments (2026-09-16), from each
# tournament's Wikipedia page -- its bracket template, or for the NCAA its
# qualifying-teams table. Kept in data/hockey-seeds.json by tournament year.
# ---------------------------------------------------------------------------
SEED_TITLES = {"B1G": ("%d Big Ten men's ice hockey tournament", "%d Big Ten men's hockey tournament"),
               "ECAC": ("%d ECAC Hockey men's ice hockey tournament", "%d ECAC Hockey men's tournament"),
               "NCAA": ("%d NCAA Division I men's ice hockey tournament",
                        "%d NCAA Division I men's hockey tournament")}
# both sides of a name comparison pass through this, so it maps to one spelling
SEED_ALIAS = {"massachusettslowell": "umasslowell", "nebraskaomaha": "omaha",
              "miami": "miamioh", "uconn": "connecticut", "aic": "americaninternational",
              "alabamahuntsville": "alabamahuntsville"}
_SEEDS = None


def _wiki_clean(v):
    v = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", v, flags=re.S)
    # {{nowrap|Name}} keeps its name; every other template goes
    v = re.sub(r"\{\{\s*nowrap\s*\|([^}]*)\}\}", r"\1", v, flags=re.I)
    v = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", v)
    v = re.sub(r"\{\{[^}]*\}\}", "", v)
    v = re.sub(r"\(\d+\)", "", v)
    return v.replace("'''", "").replace("''", "").replace("&nbsp;", " ").replace("*", "").strip()


def _wiki_seeds(year, key):
    for title in SEED_TITLES[key]:
        w = _wikitext(title % year)
        if not w:
            continue
        seeds = {}
        if key == "NCAA":
            for s, team in re.findall(r"\|\s*align=\"?center\"?\s*\|\s*(\d)\s*\n\s*\|\s*([^\n]+)", w):
                t = _wiki_clean(team)
                if t and t not in seeds:
                    seeds[t] = int(s)
        else:
            slots = collections.defaultdict(dict)
            # a value may hold a [[link|label]]: its pipe does not end the value
            for rd, kind, n, v in re.findall(r"\|\s*RD(\d+)-(seed|team)(\d+)\s*=\s*((?:\[\[[^\]]*\]\]|\{\{[^}]*\}\}|[^|\n}])*)", w):
                slots[(int(rd), int(n))][kind] = v
            for _, d in sorted(slots.items()):
                team = _wiki_clean(d.get("team", ""))
                s = re.sub(r"\D", "", _wiki_clean(d.get("seed", "")))
                if team and s and team not in seeds:
                    seeds[team] = int(s)
        if seeds:
            return seeds
    return {}


def hockey_seed(y, stage, location):
    """A team's seed in a tournament of season y, or None."""
    global _SEEDS
    path = os.path.join(HERE, "data", "hockey-seeds.json")
    if _SEEDS is None:
        _SEEDS = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    key = ("B1G" if stage.startswith("Big Ten") else "ECAC" if stage.startswith("ECAC")
           else "NCAA" if stage.startswith("NCAA") else None)
    if not key:
        return None
    year = str(y + 1)
    if key not in _SEEDS.get(year, {}) and y + 1 <= dt.date.today().year:
        got = _wiki_seeds(y + 1, key)
        if got:
            _SEEDS.setdefault(year, {})[key] = got
            json.dump(_SEEDS, open(path, "w", encoding="utf-8"), indent=1, sort_keys=True)
    want = SEED_ALIAS.get(flat(location), flat(location))
    for name, seed in _SEEDS.get(year, {}).get(key, {}).items():
        n = flat(name)
        if SEED_ALIAS.get(n, n) == want:
            return seed
    return None


# ---------------------------------------------------------------------------
# HOW EVERY TEAM'S SEASON ENDED (2026-09-16), and each season's champion for
# the "^": from the NCAA Tournament's Wikipedia bracket. ESPN's scoreboard was
# tried first and is MISSING GAMES in seven seasons -- 2023-24's final among
# them, which made Boston College the champion. One 16-team bracket a year,
# except 2013's four regional brackets and a Frozen Four bracket. Kept in
# data/hockey-ncaa.json by season, names flattened.
# ---------------------------------------------------------------------------
_NCAA = None
HOCKEY_FINISH = {1: "Rd 1", 2: "Rd 2", 3: "Frozen Four", 4: "Final"}   # spelled out (his call 2026-09-17)


def _wikitext(title):
    """A Wikipedia page's wikitext, cached under cache/wiki/. Wikipedia answers
    a burst of requests with a non-JSON throttle page, so a failure is retried
    with a growing wait; a page that does not exist comes back empty."""
    path = os.path.join(CACHE, "wiki", re.sub(r"[^A-Za-z0-9]+", "_", title) + ".txt")
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    for attempt in range(5):
        try:
            r = requests.get("https://en.wikipedia.org/w/api.php",
                             params={"action": "parse", "page": title, "prop": "wikitext",
                                     "format": "json", "redirects": 1},
                             headers={"User-Agent": "games-history/1.0 (personal sports archive)"},
                             timeout=30)
            j = r.json()
        except (requests.RequestException, ValueError):
            time.sleep(5 * (attempt + 1))
            continue
        w = ((j.get("parse") or {}).get("wikitext") or {}).get("*", "")
        if w:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w", encoding="utf-8").write(w)
        return w
    return ""


def hockey_ncaa(y):
    global _NCAA
    path = os.path.join(HERE, "data", "hockey-ncaa.json")
    if _NCAA is None:
        _NCAA = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    if str(y) in _NCAA:
        return _NCAA[str(y)]
    empty = {"finish": {}, "champ": None}
    if y == 2019 or dt.date(y + 1, 4, 20) > dt.date.today():
        return empty                    # 2020 was cancelled; or not finished yet
    w = ""
    for title in SEED_TITLES["NCAA"]:
        w = _wikitext(title % (y + 1))
        if w:
            break
    if not w:
        return empty
    reach, finals = {}, []
    brackets = re.split(r"\{\{\s*\d+TeamBracket", w)[1:]
    for i, br in enumerate(brackets):
        br = br.split("\n}}")[0]
        # a 4-team bracket is a regional (rounds 1-2) unless it is the last,
        # the Frozen Four (rounds 3-4); a 16-team bracket is the whole thing
        offset = 2 if (len(brackets) > 1 and i == len(brackets) - 1) else 0
        slots = collections.defaultdict(dict)
        for rd, kind, n, v in re.findall(r"\|\s*RD(\d+)-(team|score)(\d+)\s*=\s*((?:\[\[[^\]]*\]\]|\{\{[^}]*\}\}|[^|\n}])*)", br):
            slots[(int(rd) + offset, int(n))][kind] = v
        for (rd, n), d in slots.items():
            team = _wiki_clean(d.get("team", ""))
            if team and team.lower() not in ("tbd", "bye"):
                key = flat(team)
                key = SEED_ALIAS.get(key, key)
                reach[key] = max(reach.get(key, 0), rd)
                if rd == 4:
                    sc = re.sub(r"[^0-9]", "", _wiki_clean(d.get("score", "")).split("(")[0])
                    finals.append((int(sc) if sc else -1, key))
    champ = max(finals)[1] if len(finals) == 2 and finals[0][0] != finals[1][0] else None
    finish = {k: ("Champs" if k == champ else HOCKEY_FINISH.get(r, "Rd %d" % r))
              for k, r in reach.items()}
    res = {"finish": finish, "champ": champ}
    if len(reach) >= 14 and champ:
        _NCAA[str(y)] = res
        json.dump(_NCAA, open(path, "w", encoding="utf-8"), indent=1, sort_keys=True)
    else:
        print("  WARN: hockey NCAA %d-%d bracket unreadable (%d teams)" % (y, y + 1, len(reach)),
              file=sys.stderr)
    return res


def uscho_final_rank(y, location):
    polls = uscho_polls(y)
    if not polls:
        return None
    key = flat(location or "")
    for k, v in polls[-1][1].items():
        if USCHO_ALIAS.get(k, k) == key:
            return v
    return None


# his capitals on the top-left number (2026-09-16): a non-conference opponent
# from these leagues reads "NC", every other "nc"
HOCKEY_EAST = {"bostoncollege", "bostonuniversity", "maine", "massachusetts", "umasslowell",
               "merrimack", "newhampshire", "northeastern", "providence", "vermont", "connecticut"}
NCHC = {"coloradocollege", "denver", "miami", "miamioh", "minnesotaduluth", "omaha",
        "northdakota", "stcloudstate", "westernmichigan"}


def hockey_nc_big(focus, opp_id, opp_loc, y):
    f = flat(opp_loc or "")
    if f in HOCKEY_EAST or (f == "notredame" and 2013 <= y <= 2016):
        return True
    if y >= 2013 and (f in NCHC or (f == "arizonastate" and y >= 2024)):
        return True
    return focus == rules.CORNELL and hockey_conf(opp_id, y) == rules.BIG_TEN["CHK"]


def hockey_numbers(keep, teams):
    """The top-left numbers on the hockey cards (his rules, 2026-09-16).
    Non-conference games number by WEEK -- games within two days share one.
    Conference games take "w": Michigan's pair by OPPONENT, the second game of a
    series reusing the first's number however the schedule splits them;
    Cornell's ECAC weekends share one number whoever the opponents."""
    by = collections.defaultdict(list)
    for g in keep:
        if g["sport"] == "CHK" and g.get("focus") and not g.get("stage"):
            by[(g["focus"], g["season"])].append(g)
    for (focus, y), gs in by.items():
        gs.sort(key=lambda g: (g["date"], g["time"]))
        nc_n = w_n = 0
        last_nc = last_w = None
        open_series = {}
        for g in gs:
            opp = next((t for t in g["teams"] if t["id"] != focus), None)
            if not opp:
                continue
            day = dt.date.fromisoformat(g["date"])
            conf_game = g.get("conf_game")
            if conf_game is None:
                conf_game = opp["conf"] == hockey_conf(focus, y) and opp["conf"] != "0" \
                    and not g.get("event")
            if conf_game:
                if focus == rules.MICHIGAN:
                    if opp["id"] in open_series:
                        n = open_series.pop(opp["id"])
                    else:
                        w_n += 1
                        n = open_series[opp["id"]] = w_n
                else:
                    if last_w is None or (day - last_w).days > 2:
                        w_n += 1
                    last_w, n = day, w_n
                g["mx"]["num"] = "w%d" % n
            else:
                if last_nc is None or (day - last_nc).days > 2:
                    nc_n += 1
                last_nc = day
                loc = (teams.get(opp["id"]) or {}).get("short")
                # an MTE game always reads "NC" (his call 2026-09-16)
                big = bool(g.get("preseason")) or hockey_nc_big(focus, opp["id"], loc, y)
                g["mx"]["num"] = ("NC%d" if big else "nc%d") % nc_n


def hockey_games(team_id, seasons, teams, latest_conf, start, end):
    """Every game of one team's hockey seasons as card records, plus its games
    in the upcoming window."""
    out = []
    misses = set()
    for y in seasons:
        evs = hockey_schedule(team_id, y)
        if not evs:
            continue
        polls = uscho_polls(y)
        ncaa_seen = 0
        evs = sorted(evs, key=lambda x: x.get("date") or "")
        for x in evs:
            comps = x.get("competitions") or []
            if not comps:
                continue
            c = comps[0]
            cs = c.get("competitors") or []
            if len(cs) != 2:
                continue
            try:
                d = (dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ")
                     .replace(tzinfo=dt.timezone.utc).astimezone(ET))
            except (KeyError, ValueError):
                continue
            status = c.get("status") or {}
            done = (status.get("type") or {}).get("completed")
            # every game still to come this season, not just the coming week
            # (his call 2026-09-18)
            upcoming = not done and d.date() >= start
            if not done and not upcoming:
                continue
            heads = [n.get("headline") or "" for n in (c.get("notes") or [])]
            side = []
            for k in cs:
                t = k.get("team") or {}
                tid = t.get("id")
                if not tid:
                    break
                info = hockey_team_info(tid)
                loc = info.get("location") or t.get("location") or t.get("displayName")
                if tid not in teams:
                    teams[tid] = {"name": info.get("name") or t.get("displayName"),
                                  "short": rules.display_name(loc),
                                  "abbr": info.get("abbr") or t.get("abbreviation"),
                                  "color": info.get("color"), "alt": info.get("alt")}
                else:
                    teams[tid].setdefault("color", info.get("color"))
                sc = k.get("score")
                score = (sc.get("value") if isinstance(sc, dict) else sc)
                conf = hockey_conf(tid, y)
                prev = latest_conf.get(("CHK", tid))
                if prev is None or d >= prev[0]:
                    latest_conf[("CHK", tid)] = (d, conf)
                side.append({"id": tid,
                             "score": None if upcoming or score is None else int(score),
                             "rank": uscho_rank(polls, d.date().isoformat(), loc, misses),
                             "win": bool(k.get("winner")) and not upcoming,
                             "home": k.get("homeAway") == "home",
                             "conf": conf, "seed": None})
            if len(side) != 2:
                continue
            tie = (not upcoming and side[0]["score"] is not None
                   and side[0]["score"] == side[1]["score"])
            # A 0-0 "FINAL" WAS NEVER PLAYED: ESPN keeps a cancelled game that
            # way, with no box score and no plays -- the 2021 Great Lakes
            # Invitational game with Michigan Tech, and 12/5/2025 at Michigan
            # State (found 2026-09-16)
            day = d.strftime("%Y-%m-%d")
            opp = next((q for q in side if q["id"] != team_id), side[0])
            opp_loc = teams[opp["id"]]["short"]
            us = uscho_match(uscho_schedule(team_id, y), day, opp_loc)
            if tie and side[0]["score"] == 0:
                # ...UNLESS USCHO has the result: ESPN lists 12/5/2025 at
                # Michigan State as 0-0, and it was a 3-0 Michigan win (his
                # catch 2026-09-17)
                code = USCHO_CODE.get(team_id)
                try:
                    mine = int(us["hscore"] if us["home"] == code else us["vscore"])
                    theirs = int(us["vscore"] if us["home"] == code else us["hscore"])
                except (TypeError, ValueError, KeyError):
                    continue
                me = next(q for q in side if q["id"] == team_id)
                me["score"], opp["score"] = mine, theirs
                me["win"], opp["win"] = mine > theirs, theirs > mine
                tie = mine == theirs
                if tie and mine == 0:
                    continue
            det = uscho_details(us, team_id, opp_loc) if us else {}
            fix = HOCKEY_GAME_FIX.get((team_id, day), {})
            for k in ("event", "city", "offsite", "series"):
                if k in fix:
                    det[k] = fix[k]
            post = x.get("_stype") == 3
            old_city, ev = None, None
            if det.get("stage"):
                stage, old_city = det["stage"], det.get("city")
                post = post or bool(det.get("post"))
            else:
                stage = hockey_stage(heads)
                if not stage and y <= 2021:
                    ids = [q["id"] for q in side]
                    own = hockey_conf(team_id, y)
                    in_conf = [i for i in ids if hockey_conf(i, y) == own]
                    stage, old_city, is_ncaa = hockey_old_stage(
                        team_id, y, day, in_conf, ncaa_seen, out)
                    post = post or is_ncaa
                elif stage and stage.startswith("NCAA") and y <= 2021:
                    post = True
            if stage and stage.startswith("NCAA"):
                if not old_city:
                    old_city = (FROZEN_FOUR_CITY.get(y) if ncaa_seen >= 2
                                else NCAA_REGIONAL_CITY.get((team_id, y)))
                ncaa_seen += 1
            if not stage:
                if us:
                    if det.get("event") or det.get("city") or det.get("offsite"):
                        ev = {"event": det.get("event"), "city": det.get("city"),
                              "mte": det.get("mte"), "mte_round": det.get("mte_round"),
                              "frame": det.get("frame")}
                else:
                    ev = hockey_event(team_id, y, day)
            v = c.get("venue") or {}
            city = (v.get("address") or {}).get("city")
            if ev and ev.get("city"):
                old_city = ev["city"]
            # the ECAC championship weekend is in Lake Placid (Atlantic City and
            # Albany before it) whatever ESPN's venue says -- it names Ithaca
            # for Cornell's 2023 semifinal
            ecac_final_weekend = bool(stage and stage.startswith("ECAC") and
                                      stage.split(" | ")[1] in
                                      ("Semis", "Championship", "Third Place"))
            if ecac_final_weekend and not old_city:
                old_city = ECAC_CITY.get(y, "Lake Placid")
            b1g_tourney = bool(stage and stage.startswith("Big Ten"))
            if us:
                neutral = bool(det.get("neutral")) or bool(post and stage)
            else:
                neutral = bool(c.get("neutralSite")) or (post and bool(stage)) or (
                    b1g_tourney and y in B1G_HOCKEY_CITY) or bool(ev) or ecac_final_weekend
            # seeds, in every tournament (his call 2026-09-16)
            if stage:
                for q in side:
                    q["seed"] = hockey_seed(y, stage, teams[q["id"]]["short"])
            # how the opponent's season ended, its final USCHO rank, and whether
            # it was last season's champion -- on every hockey card
            ncaa_now, ncaa_before = hockey_ncaa(y), hockey_ncaa(y - 1)
            okey = SEED_ALIAS.get(flat(opp_loc), flat(opp_loc))
            hmx = {"finish": ncaa_now.get("finish", {}).get(okey),
                   "final": uscho_final_rank(y, opp_loc),
                   "reigning": bool(okey) and okey == ncaa_before.get("champ")}
            # WHO WON THE SHOOTOUT (his call 2026-09-22): almost every college
            # shootout goes down as a TIE, so the card cannot tell a shootout
            # won from one lost without USCHO's note -- "Clarkson wins
            # shootout, 3-2", "COR wins SO 2-1". The name before "win" is
            # matched against both teams, by full name and by the first three
            # letters, and anything it cannot place is left unknown.
            sho_win = None
            sho_note = (us or {}).get("sho_notes") or ""
            # HIS OWN ANSWERS for the shootouts USCHO never named (2026-09-22)
            hand_sho = x["id"] in rules.SHOOTOUT_FIX
            m_sho = re.match(r"\s*([A-Za-z .'&-]+?)\s+wins?\b", sho_note, re.I)
            if m_sho:
                who = flat(m_sho.group(1))
                def _match(q):
                    names = [flat(teams[q["id"]]["short"]),
                             flat(teams[q["id"]]["name"] or "")]
                    return who in [n for n in names if n] or (
                        len(who) >= 3 and any(n.startswith(who) for n in names if n))
                me_q = next((q for q in side if q["id"] == team_id), None)
                if me_q and _match(me_q):
                    sho_win = True
                elif _match(opp):
                    sho_win = False
            if hand_sho:
                sho_win = rules.SHOOTOUT_FIX[x["id"]]
            labels = list(fix.get("labels", []))
            named = bool(ev and ev.get("event") in VENUE_EVENTS)
            arena = (us or {}).get("arena_name") or ""
            if named and arena and arena != "NA" and arena not in labels:
                labels.append(arena)
            # CORNELL'S IVY GAMES (his call 2026-09-16): the regular season
            # against the other five hockey-playing Ivies
            conference = det.get("conf_game") if us else (hockey_conf(opp["id"], y) == "ECAC")
            # WHEN A SHOOTOUT COUNTS (his rule 2026-09-22): from 2025-26 every
            # one has a winner. Before that it settled nothing outside a
            # CONFERENCE game, a tournament (MTE) or the postseason -- those
            # games are simply ties, with no winner and no brackets. His own
            # answers in SHOOTOUT_FIX always win.
            shootout = ("SO" in ((status.get("type") or {}).get("shortDetail") or "")
                        or bool(us and (us.get("sho_notes") or
                                        re.search(r"shootout|\bSO\b",
                                                  us.get("note") or "", re.I))))
            if hand_sho:
                shootout = rules.SHOOTOUT_FIX[x["id"]] is not None
            elif shootout and y < 2025 and not (stage or ev or conference):
                shootout, sho_win = False, None
            if (team_id == rules.CORNELL and not stage and opp_loc in rules.IVY
                    and opp_loc != "Cornell" and conference):
                labels.append("Ivy League")
            out.append({
                "id": x["id"], "sport": "CHK", "season": y,
                "date": d.strftime("%Y-%m-%d"), "dow": rules.DOW[d.weekday()],
                "time": ("TBD" if upcoming and (x.get("timeValid") is False or
                                                c.get("timeValid") is False)
                         else d.strftime("%H:%M")), "neutral": neutral,
                "ot": (status.get("period") or 0) > 3,
                # a SHOOTOUT: ESPN marks almost none, USCHO names every one
                # ("Clarkson wins shootout, 3-2") in its shootout notes
                "so": shootout,
                "tie": tie, "sho_win": sho_win, "show": False, "week": None,
                "venue": v.get("fullName"), "mq": False,
                "offsite": det.get("offsite") if not stage else None,
                # a series he has named by hand (2026-09-22); the Michigan pass
                # that derives them leaves a game that already has one alone
                **({"series": det["series"]} if det.get("series") else {}),
                # USCHO has the last word on where a regular-season game was:
                # ESPN's venue named Little Caesars Arena, and once East
                # Lansing, for Duel in the D, which wants no venue at all
                "city": (rules.CITY_OVERRIDES.get(old_city, old_city) if old_city else
                         None if (us and not stage) else
                         rules.tourney_city(city, v.get("fullName"), stage, y)
                         if stage else rules.display_city(city, v.get("fullName"))),
                # TV only for the postseason (his call 2026-09-16)
                "nets": sorted(set(networks(c))) if stage else [],
                "teams": side, "header": None, "slots": [], "type": None,
                # a Big Ten Tournament game carries the conference, as the
                # basketball ones do -- which is also what keeps it out of
                # Michigan's game numbers
                "champ": ("Big Ten" if b1g_tourney else "ECAC"
                          if stage and stage.startswith("ECAC") else None),
                "round": heads[0] if heads else None,
                "title": False, "event": ev.get("event") if ev else None,
                "standin": False,
                "bfri": False, "suffix": None, "opener": False,
                "rival_loss": False, "rivals": False, "post": post,
                "rivals_only": True, "bowl": None, "showcase": False,
                "kickoff": False, "stage": stage,
                "upcoming": upcoming or None,
                "michigan": team_id == rules.MICHIGAN, "focus": team_id,
                "mx": {k: v for k, v in hmx.items() if v},
                "conf_game": det.get("conf_game") if us else None,
                "frame": bool(ev and ev.get("frame")),
                "labels": labels,
                "dated": named,
            })
            if not out[-1]["upcoming"]:
                out[-1].pop("upcoming")
            if ev and ev.get("mte"):
                # an MTE's rounds: USCHO's note names them; failing that, a
                # two-day four-team event -- the semifinal, then the final or
                # the third-place game by the first result
                out[-1]["preseason"] = True
                first = [g for g in out[:-1] if g.get("preseason")
                         and g["season"] == y and g.get("event") == ev["event"]]
                fixed = HOCKEY_MTE_ROUND.get((team_id, out[-1]["date"]))
                if fixed:
                    out[-1]["mte_round"] = fixed
                elif ev.get("mte_round"):
                    out[-1]["mte_round"] = ev["mte_round"]
                elif first and first[-1].get("tie"):
                    pass        # after a tied first game the round cannot be told
                elif not first:
                    out[-1]["mte_round"] = "Semifinals"
                else:
                    won = any(t["win"] and t["id"] == team_id for t in first[-1]["teams"])
                    out[-1]["mte_round"] = "Final" if won else "Third Place"
    return out, misses


def hockey_rival_games(seasons, teams, latest_conf, start, end):
    """HOCKEY RIVALS (his call 2026-09-18): every NCAA Tournament game Michigan
    State, Ohio State or Notre Dame LOST -- to anyone but another of the three
    (a rival beating a rival stays out unless he asks). Built with the same
    per-team builder as Michigan's and Cornell's cards, from each rival's side,
    then stripped of the team-view extras."""
    out, seen = [], set()
    for rid in ("127", "194", "87"):
        games, _ = hockey_games(rid, seasons, teams, latest_conf, start, end)
        for g in games:
            if not (g.get("stage") or "").startswith("NCAA Tournament") or g.get("upcoming"):
                continue
            me = next(t for t in g["teams"] if t["id"] == rid)
            opp = next(t for t in g["teams"] if t["id"] != rid)
            if me["win"] or g.get("tie") or opp["id"] in ("127", "194", "87"):
                continue
            if g["id"] in seen:
                continue
            seen.add(g["id"])
            # michigan=False even against Michigan: the flag makes a record a
            # MICHIGAN-VIEW card (it is given focus 130 below), and this is not one
            g.update(focus=None, rivals=True, rival_loss=True, labels=[], dated=False,
                     michigan=False)
            for k in ("mx", "conf_game", "frame", "num"):
                g.pop(k, None)
            # ESPN names no network for the older ones; USCHO usually does
            if not g["nets"]:
                u = uscho_match(uscho_schedule(rid, g["season"]), g["date"],
                                teams[opp["id"]]["short"])
                if u and re.search(r"[A-Za-z]", u.get("tv") or ""):   # "0" is none
                    g["nets"] = [u["tv"]]
            out.append(g)
        # ...and the NCAA games ESPN's team schedule LEAVES OUT, from USCHO:
        # Ohio State's 2019 regional loss to Denver is the case (found 2026-09-18)
        code = USCHO_CODE[rid]
        have = {(g["date"], t["id"]) for g in out for t in g["teams"] if t["id"] == rid}
        by_name = {flat(v["short"]): k for k, v in teams.items()}
        for y in seasons:
            polls = None
            for u in uscho_schedule(rid, y):
                if not (u.get("tourn_shortname") or "").startswith("NCAA") or u.get("complete") != "Y":
                    continue
                day = "%s-%s-%s" % (str(u["gdate"])[:4], str(u["gdate"])[4:6], str(u["gdate"])[6:])
                if (day, rid) in have:
                    continue
                home = u["home"] == code
                try:
                    mine, theirs = ((int(u["hscore"]), int(u["vscore"])) if home
                                    else (int(u["vscore"]), int(u["hscore"])))
                except (TypeError, ValueError):
                    continue
                oname = u["vis_name"] if home else u["home_name"]
                okey = USCHO_ALIAS.get(flat(oname), flat(oname))
                oid = by_name.get(okey)
                if mine >= theirs or not oid or oid in ("127", "194", "87"):
                    if not oid and mine < theirs:
                        print("  WARN: hockey rival opponent %r not known" % oname, file=sys.stderr)
                    continue
                det = uscho_details(u, rid, teams[oid]["short"])
                polls = polls or uscho_polls(y)
                # USCHO's start time is local ("4:00 CT"); the cards read Eastern
                tm = re.match(r"(\d+):(\d+)\s*([ECMP])T", u.get("starttime") or "")
                hh = ((int(tm.group(1)) % 12 + 12 + {"E": 0, "C": 1, "M": 2, "P": 3}[tm.group(3)])
                      if tm else 19)
                side = []
                for tid, sc, w in ((rid, mine, False), (oid, theirs, True)):
                    side.append({"id": tid, "score": sc, "win": w,
                                 "rank": uscho_rank(polls, day, teams[tid]["short"], set()),
                                 "home": (tid == rid) == home, "conf": hockey_conf(tid, y),
                                 "seed": hockey_seed(y, det.get("stage"), teams[tid]["short"])})
                out.append({
                    "id": "uscho-%s" % (u.get("gameid") or day + rid), "sport": "CHK", "season": y,
                    "date": day, "dow": rules.DOW[dt.date.fromisoformat(day).weekday()],
                    "time": "%02d:%s" % (hh % 24, tm.group(2) if tm else "00"),
                    "neutral": True, "ot": bool(u.get("ots")), "so": False, "tie": False,
                    "show": False, "week": None, "venue": u.get("arena_name"), "mq": False,
                    "offsite": None, "city": rules.CITY_OVERRIDES.get(det.get("city"), det.get("city")),
                    "nets": [u["tv"]] if re.search(r"[A-Za-z]", u.get("tv") or "") else [],
                    "teams": side, "header": None,
                    "slots": [], "type": None, "champ": None, "round": None, "title": False,
                    "event": None, "standin": False, "bfri": False, "suffix": None,
                    "opener": False, "rival_loss": True, "rivals": True, "post": True,
                    "rivals_only": True, "bowl": None, "showcase": False, "kickoff": False,
                    "stage": det.get("stage"), "michigan": False, "focus": None,
                    "labels": [], "dated": False})
    return out


# ------------------------------------------------------------------ DETROIT
# THE LIONS (his spec 2026-09-16, built 2026-09-18): every game from 2011, with
# TV. Pro ids clash with college ones (NFL 8 is the Lions, college 8 Arkansas),
# so every pro team id carries its league: "nfl-8".
NFL = "football/nfl"
LIONS = "nfl-8"
LIONS_FROM = 2011
NFL_ROUND = {"Wild Card": "NFC Wild Card", "Divisional Round": "NFC Divisional Round",
             "Conference Championship": "NFC Championship", "Super Bowl": "Super Bowl"}


def nfl_place(t):
    """HIS NAME FOR AN NFL TEAM is its PLACE (his call 2026-09-18) -- "at Green
    Bay" -- with the two shared cities told apart: NY Giants, NY Jets, LA Rams,
    LA Chargers."""
    loc = t.get("location") or t.get("displayName") or ""
    short = {"New York": "NY", "Los Angeles": "LA"}.get(loc)
    return short + " " + (t.get("name") or t.get("shortDisplayName") or "") if short else loc


def nfl_teams():
    """Every NFL team's names, colours and logo, keyed "nfl-<id>"."""
    out = {}
    try:
        got = get_json("%s/%s/teams" % (BASE, NFL), params={"limit": 50})
    except requests.RequestException:
        return out
    for lg in got.get("sports", [{}])[0].get("leagues", []):
        for w in lg.get("teams", []):
            t = w.get("team") or {}
            logos = t.get("logos") or []
            logo = next((l["href"] for l in logos if "dark" in (l.get("rel") or [])), None)
            if not logo and logos:
                logo = logos[0].get("href")
            out["nfl-" + t["id"]] = {"name": t.get("displayName"),
                                     "short": nfl_place(t),
                                     "abbr": t.get("abbreviation"),
                                     "color": t.get("color"), "alt": t.get("alternateColor"),
                                     "logo": logo}
    return out


def nfl_key(event_id, winner_side):
    """KEY GAMES (his rule): a WIN decided in the final 2:00 or in overtime --
    the scoring play that put the winner ahead FOR GOOD came in the last two
    minutes of the fourth quarter, or later. Kept for good in
    data/nfl-key.json once worked out, so the cloud build never re-reads a
    finished game."""
    path = os.path.join(HERE, "data", "nfl-key.json")
    known = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    if event_id in known:
        return known[event_id]
    try:
        plays = get_json("%s/%s/summary" % (BASE, NFL),
                         params={"event": event_id}).get("scoringPlays") or []
    except requests.RequestException:
        return False
    if not plays:
        return False
    lead_at = None
    prev = (0, 0)
    for sp in plays:
        now = (sp.get("homeScore") or 0, sp.get("awayScore") or 0)
        mine = now[0] - now[1] if winner_side == "home" else now[1] - now[0]
        was = prev[0] - prev[1] if winner_side == "home" else prev[1] - prev[0]
        if mine > 0 and was <= 0:
            lead_at = sp
        prev = now
    key = False
    if lead_at:
        per = (lead_at.get("period") or {}).get("number") or 0
        clock = (lead_at.get("clock") or {}).get("value")
        key = per >= 5 or (per == 4 and clock is not None and clock <= 120)
    known[event_id] = key
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(known, open(path, "w", encoding="utf-8"), indent=0, sort_keys=True)
    return key


_NFL_SEEDS = None
# ESPN's 2011 standings carry only the Giants' seed (found 2026-09-18); the NFC
# as it finished that year
NFL_SEED_FIX = {2011: {"nfl-9": 1, "nfl-25": 2, "nfl-18": 3, "nfl-19": 4,
                       "nfl-1": 5, "nfl-8": 6}}


def nfl_seeds(y):
    """Each team's PLAYOFF SEED in season y, {"nfl-8": 3}, from ESPN's final
    standings. Kept in data/nfl-seeds.json once the season is done."""
    global _NFL_SEEDS
    path = os.path.join(HERE, "data", "nfl-seeds.json")
    if _NFL_SEEDS is None:
        _NFL_SEEDS = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    if str(y) in _NFL_SEEDS:
        return _NFL_SEEDS[str(y)]
    out = {}
    try:
        got = get_json("https://site.api.espn.com/apis/v2/sports/football/nfl/standings",
                       params={"season": y})
    except requests.RequestException:
        return out

    def walk(o):
        for ch in o.get("children") or []:
            for e in (ch.get("standings") or {}).get("entries") or []:
                st = {x.get("name"): x.get("value") for x in e.get("stats") or []}
                if st.get("playoffSeed") and st["playoffSeed"] <= 7:
                    out["nfl-" + e["team"]["id"]] = int(st["playoffSeed"])
            walk(ch)
    walk(got)
    out.update(NFL_SEED_FIX.get(y, {}))
    if out and dt.date.today() > dt.date(y + 1, 3, 1):
        _NFL_SEEDS[str(y)] = out
        json.dump(_NFL_SEEDS, open(path, "w", encoding="utf-8"), indent=1, sort_keys=True)
    return out


def lions_games(teams, start):
    """Every Lions game, 2011 on, as team-card records (focus "nfl-8")."""
    for k, v in nfl_teams().items():
        teams[k] = v
    out = []
    last_y = upcoming_season("CFB", start)
    for y in range(LIONS_FROM, last_y + 1):
        for stype in (2, 3):
            try:
                got = get_json("%s/%s/teams/8/schedule" % (BASE, NFL),
                               params={"season": y, "seasontype": stype})
            except requests.RequestException:
                continue
            for x in got.get("events") or []:
                comps = x.get("competitions") or []
                if not comps:
                    continue
                c = comps[0]
                cs = c.get("competitors") or []
                if len(cs) != 2:
                    continue
                try:
                    d = (dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ")
                         .replace(tzinfo=dt.timezone.utc).astimezone(ET))
                except (KeyError, ValueError):
                    continue
                status = c.get("status") or {}
                done = (status.get("type") or {}).get("completed")
                if not done and d.date() < start:
                    continue             # postponed or never played
                side, rec = [], None
                for k in cs:
                    t = k.get("team") or {}
                    tid = "nfl-" + t["id"]
                    teams.setdefault(tid, {"name": t.get("displayName"),
                                           "short": nfl_place(t),
                                           "abbr": t.get("abbreviation")})
                    sc = k.get("score")
                    score = sc.get("value") if isinstance(sc, dict) else sc
                    if tid == LIONS:
                        rec = next((r.get("displayValue") for r in k.get("record") or []
                                    if r.get("type") == "total"), None)
                    was = nfl_place(t)
                    side.append({"id": tid,
                                 **({"place": was} if was and was != teams[tid]["short"] else {}),
                                 "score": int(score) if done and score is not None else None,
                                 "rank": None, "win": bool(k.get("winner")) and bool(done),
                                 "home": k.get("homeAway") == "home", "conf": "NFL",
                                 "seed": None})
                if not any(q["id"] == LIONS for q in side):
                    continue
                me = next(q for q in side if q["id"] == LIONS)
                tie = bool(done) and side[0]["score"] == side[1]["score"]
                wk = x.get("week") or {}
                stage = NFL_ROUND.get(wk.get("text")) if stype == 3 else None
                if stype == 3 and not stage:
                    continue             # the Pro Bowl
                if stage:
                    seeds = nfl_seeds(y)
                    for q in side:
                        q["seed"] = seeds.get(q["id"])
                v = c.get("venue") or {}
                neutral = bool(c.get("neutralSite"))
                mx = {}
                if rec:
                    mx["rec"] = rec
                if done and me["win"]:
                    if nfl_key(x["id"], "home" if me["home"] else "away"):
                        mx["key"] = True
                valid = not (x.get("timeValid") is False or c.get("timeValid") is False)
                g = {"id": x["id"], "sport": "NFL", "season": y,
                     "date": d.strftime("%Y-%m-%d"), "dow": rules.DOW[d.weekday()],
                     "time": d.strftime("%H:%M") if (done or valid) else "TBD",
                     "neutral": neutral, "ot": (status.get("period") or 0) > 4,
                     "so": False, "tie": tie, "show": False,
                     "week": wk.get("number") if stype == 2 else None,
                     "venue": v.get("fullName"), "mq": False, "offsite": None,
                     "city": ((v.get("address") or {}).get("city") if neutral else None),
                     "nets": sorted(set(networks(c))), "teams": side, "header": None,
                     "slots": [], "type": None, "champ": None, "round": None,
                     "title": False, "event": None, "standin": False, "bfri": False,
                     "suffix": None, "opener": False, "rival_loss": False,
                     "rivals": False, "post": stype == 3, "rivals_only": True,
                     "bowl": None, "showcase": False, "kickoff": False,
                     "stage": stage, "michigan": False, "focus": LIONS, "mx": mx,
                     "labels": [], "dated": False}
                if not done:
                    g["upcoming"] = True
                out.append(g)
    return out


# THE RED WINGS, PISTONS AND CAVALIERS (his spec 2026-09-16, built
# 2026-09-18): playoff games, and for the two NBA teams the NBA Cup. A season
# is filed under the year it STARTS, like college basketball (2025 = 2025-26);
# ESPN names it for the year it ends.
PRO_TEAMS = [
    # (focus id, ESPN league path, ESPN team id, first season, NBA Cup too)
    ("nhl-5", "hockey/nhl", "5", 1996, False),          # Red Wings, 1996-97 on
    ("nba-8", "basketball/nba", "8", 2003, True),        # Pistons, 2003-04 on (2002-03 dropped, his call 2026-09-18)
    ("nba-5", "basketball/nba", "5", 2017, True),        # Cavaliers, 2017-18 on (2016-17 dropped, his call 2026-09-18)
]
# ESPN's NHL standings carry NO seeds before 1999-2000; the Western and
# Eastern Conference seeds as those playoffs were drawn (by hand, 2026-09-18)
PRO_SEED_FIX = {
    ("hockey/nhl", 1996): {"COL": 1, "DAL": 2, "DET": 3, "ANA": 4, "PHX": 5, "STL": 6,
                           "EDM": 7, "CHI": 8, "NJ": 1, "BUF": 2, "PHI": 3, "FLA": 4},
    ("hockey/nhl", 1997): {"DAL": 1, "COL": 2, "DET": 3, "STL": 4, "LA": 5, "PHX": 6,
                           "EDM": 7, "SJ": 8, "NJ": 1, "PIT": 2, "PHI": 3, "WSH": 4},
    ("hockey/nhl", 1998): {"DAL": 1, "COL": 2, "DET": 3, "PHX": 4, "STL": 5, "ANA": 6,
                           "SJ": 7, "EDM": 8},
    # ...and ESPN's 1999-2000 table is scrambled (it has Columbus and Minnesota
    # a year early), so that season is replaced outright too
    ("hockey/nhl", 1999): {"STL": 1, "DAL": 2, "COL": 3, "DET": 4, "LA": 5, "PHX": 6,
                           "EDM": 7, "SJ": 8},
    # ESPN gives the 2021-22 East its seeds AFTER the play-in; the Cavaliers
    # went into it eighth
    ("basketball/nba", 2021): {"BKN": 7, "CLE": 8, "ATL": 9, "CHA": 10},
}
PRO_ROUNDS = {"hockey/nhl": ["First Round", "Second Round", "Conference Final",
                             "Stanley Cup Final"],
              "basketball/nba": ["First Round", "Conference Semifinals",
                                 "Conference Finals", "NBA Finals"]}
PRO_SPORT = {"hockey/nhl": "NHL", "basketball/nba": "NBA"}
_PRO_SEEDS = None


def pro_place(t):
    """A pro team by its PLACE, the shared cities told apart -- NY Rangers,
    LA Lakers -- as the Lions' opponents are."""
    loc = (t.get("location") or t.get("displayName") or "").strip()
    short = {"New York": "NY", "Los Angeles": "LA"}.get(loc)
    return short + " " + (t.get("name") or t.get("shortDisplayName") or "") if short else loc


def pro_teams(league, prefix):
    out = {}
    try:
        got = get_json("%s/%s/teams" % (BASE, league), params={"limit": 50})
    except requests.RequestException:
        return out
    for lg in got.get("sports", [{}])[0].get("leagues", []):
        for w in lg.get("teams", []):
            t = w.get("team") or {}
            logos = t.get("logos") or []
            logo = next((l["href"] for l in logos if "dark" in (l.get("rel") or [])), None)
            if not logo and logos:
                logo = logos[0].get("href")
            out[prefix + t["id"]] = {"name": t.get("displayName"), "short": pro_place(t),
                                     "abbr": t.get("abbreviation"), "color": t.get("color"),
                                     "alt": t.get("alternateColor"), "logo": logo}
    return out


def pro_seeds(league, y):
    """{abbreviation: playoff seed} for the season STARTING in y. Kept in
    data/pro-seeds.json once worked out."""
    global _PRO_SEEDS
    path = os.path.join(HERE, "data", "pro-seeds.json")
    if _PRO_SEEDS is None:
        _PRO_SEEDS = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    key = "%s %d" % (league, y)
    if key in _PRO_SEEDS:
        return _PRO_SEEDS[key]
    out = {}
    try:
        got = get_json("https://site.api.espn.com/apis/v2/sports/%s/standings" % league,
                       params={"season": y if league == "baseball/mlb" else y + 1})
    except requests.RequestException:
        got = {}

    def walk(o):
        for ch in o.get("children") or []:
            for e in (ch.get("standings") or {}).get("entries") or []:
                st = {x.get("name"): x.get("value") for x in e.get("stats") or []}
                if st.get("playoffSeed") and st["playoffSeed"] <= 10:
                    out[e["team"]["abbreviation"]] = int(st["playoffSeed"])
            walk(ch)
    walk(got)
    if (league, y) in PRO_SEED_FIX:
        out = dict(PRO_SEED_FIX[(league, y)])
    if out and dt.date.today() > (dt.date(y, 12, 1) if league == "baseball/mlb"
                                   else dt.date(y + 1, 7, 15)):
        _PRO_SEEDS[key] = out
        json.dump(_PRO_SEEDS, open(path, "w", encoding="utf-8"), indent=1, sort_keys=True)
    return out


def pro_games(teams, start):
    """Every PLAYOFF game of the three, and the NBA Cup games of the two NBA
    teams, as team-card records. The ROUND is the series' place in the run
    (the first opponent is the first round), because ESPN names no round before
    about 2008; the GAME number and the series record through that game are
    counted the same way."""
    out = []
    for fid, league, tid, first, cup in PRO_TEAMS:
        prefix = fid.split("-")[0] + "-"
        for k, v in pro_teams(league, prefix).items():
            teams[k] = v
        last = upcoming_season("CBB", start)
        for y in range(first, last + 1):
            # 5 is the NBA PLAY-IN, counted with the playoffs (his call 2026-09-18)
            nat_from = rules.PRO_NATIONAL_FROM.get(fid)
            want_reg = nat_from is not None and y >= nat_from
            for stype in ((2, 3, 5) if cup else (2, 3) if want_reg else (3,)):
                try:
                    got = get_json("%s/%s/teams/%s/schedule" % (BASE, league, tid),
                                   params={"season": y + 1, "seasontype": stype})
                except requests.RequestException:
                    continue
                series, opp_order = {}, []
                evs = sorted(got.get("events") or [], key=lambda x: x.get("date") or "")
                for x in evs:
                    comps = x.get("competitions") or []
                    if not comps:
                        continue
                    c = comps[0]
                    cs = c.get("competitors") or []
                    heads = [n.get("headline") or "" for n in c.get("notes") or []]
                    cup_note = next((h for h in heads if "NBA Cup" in h or "In-Season" in h), None)
                    # a REGULAR-SEASON game is kept on national TV alone (his
                    # call 2026-09-22) -- the Pistons and the Red Wings, 2013-14 on
                    national = want_reg and bool(set(networks(c)) & set(rules.PRO_NATIONAL))
                    if stype == 2 and not cup_note and not national:
                        continue
                    if len(cs) != 2 or not (c.get("status") or {}).get("type", {}).get("completed"):
                        continue
                    try:
                        d = (dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ")
                             .replace(tzinfo=dt.timezone.utc).astimezone(ET))
                    except (KeyError, ValueError):
                        continue
                    side = []
                    for k in cs:
                        t = k.get("team") or {}
                        sc = k.get("score")
                        score = sc.get("value") if isinstance(sc, dict) else sc
                        # a team since moved or folded is not in ESPN's list
                        # (the Phoenix Coyotes, the Seattle SuperSonics)
                        if prefix + t["id"] not in teams:
                            logos = t.get("logos") or [{}]
                            teams[prefix + t["id"]] = {
                                "name": t.get("displayName"), "short": pro_place(t),
                                "abbr": t.get("abbreviation"), "color": t.get("color"),
                                "alt": t.get("alternateColor"),
                                # a team ESPN no longer lists (the Phoenix
                                # Coyotes) still has its logo under its
                                # abbreviation (found 2026-09-18)
                                "logo": logos[0].get("href") or
                                "https://a.espncdn.com/i/teamlogos/%s/500/%s.png"
                                % (prefix[:-1], (t.get("abbreviation") or "").lower())}
                        was = pro_place(t)
                        side.append({"id": prefix + t["id"], "abbr": t.get("abbreviation"),
                                     # the name it played under THAT season --
                                     # the New Jersey Nets, not Brooklyn
                                     **({"place": was} if was and was != teams[prefix + t["id"]]["short"] else {}),
                                     "score": int(score) if score is not None else None,
                                     "rank": None, "win": bool(k.get("winner")),
                                     "home": k.get("homeAway") == "home",
                                     "conf": PRO_SPORT[league], "seed": None})
                    if not any(q["id"] == fid for q in side):
                        continue
                    me = next(q for q in side if q["id"] == fid)
                    opp = next(q for q in side if q["id"] != fid)
                    mx = {}
                    if stype == 5:
                        stage = "Play-In"
                        seeds = pro_seeds(league, y)
                        for q in side:
                            q["seed"] = seeds.get(q["abbr"])
                    elif stype == 3:
                        if opp["id"] not in opp_order:
                            opp_order.append(opp["id"])
                        rnd_i = opp_order.index(opp["id"])
                        w, l = series.get(opp["id"], (0, 0))
                        w, l = (w + 1, l) if me["win"] else (w, l + 1)
                        series[opp["id"]] = (w, l)
                        stage = PRO_ROUNDS[league][min(rnd_i, 3)]
                        mx.update(game=w + l, series="%d-%d" % (w, l))
                        seeds = pro_seeds(league, y)
                        for q in side:
                            q["seed"] = seeds.get(q["abbr"])
                    elif cup_note:
                        stage = "NBA Cup | " + cup_note.split(" - ")[-1].strip()
                    else:
                        stage = None
                        mx["nat"] = True
                    for q in side:
                        q.pop("abbr", None)
                    v = c.get("venue") or {}
                    out.append({
                        "id": x["id"], "sport": PRO_SPORT[league], "season": y,
                        "date": d.strftime("%Y-%m-%d"), "dow": rules.DOW[d.weekday()],
                        "time": d.strftime("%H:%M"), "neutral": bool(c.get("neutralSite")),
                        "ot": (c.get("status") or {}).get("period", 0) >
                              (3 if league == "hockey/nhl" else 4),
                        "so": False, "tie": False, "show": False, "week": None,
                        "venue": v.get("fullName"), "mq": False, "offsite": None,
                        "city": ((v.get("address") or {}).get("city")
                                 if c.get("neutralSite") else None),
                        "nets": sorted(set(networks(c))), "teams": side, "header": None,
                        "slots": [], "type": None, "champ": None, "round": None,
                        "title": False, "event": None, "standin": False, "bfri": False,
                        "suffix": None, "opener": False, "rival_loss": False,
                        "rivals": False, "post": stype in (3, 5), "rivals_only": True,
                        "bowl": None, "showcase": False, "kickoff": False,
                        "stage": stage, "michigan": False, "focus": fid, "mx": mx,
                        "labels": [], "dated": False})
    return out


# THE TIGERS (his spec 2026-09-16, built 2026-09-18), 2006 on: walk-off wins,
# extra-inning wins, no-hitters thrown by the Tigers, and every playoff game.
TIGERS = "mlb-6"
TIGERS_FROM = 2006
# ESPN's box scores cannot tell a no-hitter (it lists 0 hits for BOTH teams in
# Verlander's), so they are named here -- his list, 2026-09-18
TIGERS_NO_HITTERS = {"2007-06-12", "2011-05-07", "2021-05-18", "2023-07-08"}
MLB_ROUNDS = ["ALDS", "ALCS", "World Series"]


def mlb_lines(event_id):
    """The inning-by-inning line of a Tigers win, {"home": [...], "away": [...]},
    kept for good in data/mlb-lines.json."""
    global _LINES
    path = os.path.join(HERE, "data", "mlb-lines.json")
    if _LINES is None:
        _LINES = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    if event_id in _LINES:
        return _LINES[event_id]
    try:
        s = get_json("%s/baseball/mlb/summary" % BASE, params={"event": event_id})
    except requests.RequestException:
        return None
    cs = ((s.get("header") or {}).get("competitions") or [{}])[0].get("competitors") or []
    out = {}
    for k in cs:
        out[k.get("homeAway")] = [int(l.get("displayValue") or 0) if str(l.get("displayValue") or "0").isdigit()
                                  else 0 for l in k.get("linescores") or []]
    if "home" not in out or "away" not in out:
        return None
    _LINES[event_id] = out
    if len(_LINES) % 100 == 0:
        json.dump(_LINES, open(path, "w", encoding="utf-8"), separators=(",", ":"), sort_keys=True)
    return out


_LINES = None
LATE_ONLY = []


def mlb_walkoff(event_id):
    """Did the home team win in its LAST TURN AT BAT? It did if it batted in
    the final inning at all -- ahead after the top half, it would not have.
    Kept for good in data/mlb-walkoff.json."""
    path = os.path.join(HERE, "data", "mlb-walkoff.json")
    global _WALKOFF
    if _WALKOFF is None:
        _WALKOFF = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    if event_id in _WALKOFF:
        return _WALKOFF[event_id]
    try:
        s = get_json("%s/baseball/mlb/summary" % BASE, params={"event": event_id})
    except requests.RequestException:
        return False
    cs = ((s.get("header") or {}).get("competitions") or [{}])[0].get("competitors") or []
    home = next((k for k in cs if k.get("homeAway") == "home"), None)
    away = next((k for k in cs if k.get("homeAway") == "away"), None)
    if not home or not away or not away.get("linescores"):
        return False
    walk = len(home.get("linescores") or []) >= len(away["linescores"])
    _WALKOFF[event_id] = walk
    if len(_WALKOFF) % 50 == 0:
        json.dump(_WALKOFF, open(path, "w", encoding="utf-8"), indent=0, sort_keys=True)
    return walk


_WALKOFF = None


def tigers_games(teams, start):
    for k, v in pro_teams("baseball/mlb", "mlb-").items():
        teams[k] = v
    out = []
    for y in range(TIGERS_FROM, start.year + 1):
        for stype in (2, 3):
            try:
                got = get_json("%s/baseball/mlb/teams/6/schedule" % BASE,
                               params={"season": y, "seasontype": stype})
            except requests.RequestException:
                continue
            series, opp_order = {}, []
            for x in sorted(got.get("events") or [], key=lambda x: x.get("date") or ""):
                comps = x.get("competitions") or []
                if not comps:
                    continue
                c = comps[0]
                cs = c.get("competitors") or []
                status = c.get("status") or {}
                if len(cs) != 2 or not (status.get("type") or {}).get("completed"):
                    continue
                try:
                    d = (dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ")
                         .replace(tzinfo=dt.timezone.utc).astimezone(ET))
                except (KeyError, ValueError):
                    continue
                side = []
                for k in cs:
                    t = k.get("team") or {}
                    tid = "mlb-" + t["id"]
                    if tid not in teams:
                        logos = t.get("logos") or [{}]
                        teams[tid] = {"name": t.get("displayName"), "short": pro_place(t),
                                      "abbr": t.get("abbreviation"), "color": t.get("color"),
                                      "alt": t.get("alternateColor"),
                                      "logo": logos[0].get("href") or
                                      "https://a.espncdn.com/i/teamlogos/mlb/500/%s.png"
                                      % (t.get("abbreviation") or "").lower()}
                    sc = k.get("score")
                    score = sc.get("value") if isinstance(sc, dict) else sc
                    was = pro_place(t)
                    side.append({"id": tid, "abbr": t.get("abbreviation"),
                                 **({"place": was} if was and was != teams[tid]["short"] else {}),
                                 "score": int(score) if score is not None else None,
                                 "rank": None, "win": bool(k.get("winner")),
                                 "home": k.get("homeAway") == "home", "conf": "MLB",
                                 "seed": None})
                if not any(q["id"] == TIGERS for q in side):
                    continue
                me = next(q for q in side if q["id"] == TIGERS)
                opp = next(q for q in side if q["id"] != TIGERS)
                day = d.strftime("%Y-%m-%d")
                innings = status.get("period") or 9
                mx, stage = {}, None
                if stype == 3:
                    heads = [n.get("headline") or "" for n in c.get("notes") or []]
                    if opp["id"] not in opp_order:
                        opp_order.append(opp["id"])
                    named = heads[0].split(" - ")[0].strip() if heads and " - " in heads[0] else ""
                    stage = {"ALWC": "AL Wild Card", "AL WILD CARD": "AL Wild Card",
                             "ALDS": "ALDS", "ALCS": "ALCS",
                             "WORLD SERIES": "World Series"}.get(named.upper(), named) \
                        if named else MLB_ROUNDS[min(opp_order.index(opp["id"]), 2)]
                    w, l = series.get(opp["id"], (0, 0))
                    w, l = (w + 1, l) if me["win"] else (w, l + 1)
                    series[opp["id"]] = (w, l)
                    mx.update(game=w + l, series="%d-%d" % (w, l))
                    seeds = pro_seeds("baseball/mlb", y)
                    for q in side:
                        q["seed"] = seeds.get(q["abbr"])
                else:
                    if day in TIGERS_NO_HITTERS and me["win"]:
                        mx["nohit"] = True
                    if me["win"] and innings > 9:
                        mx["extra"] = innings
                    if me["win"] and me["home"] and (innings > 9 or mlb_walkoff(x["id"])):
                        mx["walkoff"] = True
                    # A NINTH-INNING COMEBACK (his idea 2026-09-18): a win the
                    # Tigers were tied in or losing after eight innings
                    if me["win"] and innings >= 9:
                        ln = mlb_lines(x["id"])
                        if ln and len(ln["away"]) >= 8:
                            mine = sum((ln["home"] if me["home"] else ln["away"])[:8])
                            theirs = sum((ln["away"] if me["home"] else ln["home"])[:8])
                            if mine <= theirs:
                                mx["late"] = True
                    # ...and every NATIONAL TV game from 2011 (his call
                    # 2026-09-22), whatever the result
                    if (y >= rules.PRO_NATIONAL_FROM[TIGERS]
                            and set(networks(c)) & set(rules.PRO_NATIONAL)):
                        mx["nat"] = True
                    if not mx:
                        continue
                for q in side:
                    q.pop("abbr", None)
                v = c.get("venue") or {}
                out.append({
                    "id": x["id"], "sport": "MLB", "season": y, "date": day,
                    "dow": rules.DOW[d.weekday()], "time": d.strftime("%H:%M"),
                    "neutral": bool(c.get("neutralSite")), "ot": innings > 9,
                    "so": False, "tie": False, "show": False, "week": None,
                    "venue": v.get("fullName"), "mq": False, "offsite": None,
                    "city": ((v.get("address") or {}).get("city") if c.get("neutralSite") else None),
                    "nets": sorted(set(networks(c))), "teams": side, "header": None,
                    "slots": [], "type": None, "champ": None, "round": None, "title": False,
                    "event": None, "standin": False, "bfri": False, "suffix": None,
                    "opener": False, "rival_loss": False, "rivals": False,
                    "post": stype == 3, "rivals_only": True, "bowl": None, "showcase": False,
                    "kickoff": False, "stage": stage, "michigan": False, "focus": TIGERS,
                    "mx": mx, "labels": [], "dated": False})
    if _WALKOFF:
        json.dump(_WALKOFF, open(os.path.join(HERE, "data", "mlb-walkoff.json"), "w",
                                 encoding="utf-8"), indent=0, sort_keys=True)
    if _LINES:
        json.dump(_LINES, open(os.path.join(HERE, "data", "mlb-lines.json"), "w",
                               encoding="utf-8"), separators=(",", ":"), sort_keys=True)
    return out


def cornell_cbb_games(seasons, teams, latest_conf):
    """Cornell's Ivy League Tournament and NCAA Tournament games (his call
    2026-09-16) -- nothing else of its basketball seasons -- from ESPN's team
    schedule, which labels both. The NIT does not count."""
    team_id = rules.CORNELL
    sport = SPORTS["CBB"][0]
    out = []
    for y in seasons:
        path = os.path.join(CACHE, "cornell-cbb-%d.json" % y)
        if os.path.exists(path):
            evs = json.load(open(path, encoding="utf-8"))["events"]
        else:
            evs, seen = [], set()
            for stype in (2, 3):
                try:
                    got = get_json("%s/%s/teams/%s/schedule" % (BASE, sport, team_id),
                                   params={"season": y + 1, "seasontype": stype})
                except requests.HTTPError:
                    continue
                for x in got.get("events") or []:
                    if x.get("id") and x["id"] not in seen:
                        seen.add(x["id"])
                        x["_stype"] = stype
                        evs.append(x)
            if season_over("CBB", y):
                json.dump({"events": evs}, open(path, "w", encoding="utf-8"))
        for x in evs:
            c = (x.get("competitions") or [{}])[0]
            cs = c.get("competitors") or []
            heads = [n.get("headline") or "" for n in (c.get("notes") or [])]
            head = heads[0] if heads else ""
            if not (c.get("status") or {}).get("type", {}).get("completed") or len(cs) != 2:
                continue
            ivy = head.startswith("Ivy League Tournament")
            ncaa = x.get("_stype") == 3 and "CHAMPIONSHIP" in head.upper() and "NIT" not in head
            if not (ivy or ncaa):
                continue
            d = (dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ")
                 .replace(tzinfo=dt.timezone.utc).astimezone(ET))
            if ivy:
                low = head.split(" - ")[-1].lower()
                # named IVY MADNESS on the cards (his call 2026-09-17)
                stage = "Ivy Madness | " + (
                    "Semis" if "semi" in low else "Championship" if "final" in low
                    or "champ" in low else head.split(" - ")[-1])
            else:
                stage = rules.stage_label("CBB", 3, heads, month=d.month, season=y)
            poll = ap_before("CBB", y, d.date()) if not ncaa else {}
            side = []
            for k in cs:
                t = k.get("team") or {}
                tid = t.get("id")
                loc = t.get("location") or t.get("displayName")
                if tid not in teams:
                    info = hockey_team_info(tid)
                    teams[tid] = {"name": t.get("displayName") or info.get("name"),
                                  "short": rules.display_name(loc),
                                  "abbr": t.get("abbreviation"),
                                  "color": info.get("color"), "alt": info.get("alt")}
                sc = k.get("score")
                score = sc.get("value") if isinstance(sc, dict) else sc
                conf = rules.CORNELL_CONF["CBB"] if loc in rules.IVY else "0"
                prev = latest_conf.get(("CBB", tid))
                if prev is None:
                    latest_conf[("CBB", tid)] = (d, conf)
                rank = (k.get("curatedRank") or {}).get("current")
                side.append({"id": tid, "score": int(score) if score is not None else None,
                             "rank": (rank if rank and rank != 99 else None) or poll.get(tid),
                             "win": bool(k.get("winner")),
                             "home": k.get("homeAway") == "home",
                             "conf": conf, "seed": None})
            v = c.get("venue") or {}
            city = (v.get("address") or {}).get("city")
            if not city:
                m = re.search(r" AT ([A-Z .'-]+?) [A-Z]{2}$", head.upper())
                city = (m.group(1).title() if m else
                        {"Levien Gymnasium": "New York"}.get(v.get("fullName")))
            out.append({
                "id": x["id"], "sport": "CBB", "season": y,
                "date": d.strftime("%Y-%m-%d"), "dow": rules.DOW[d.weekday()],
                "time": d.strftime("%H:%M"), "neutral": True, "ot": False,
                "show": False, "week": None, "venue": v.get("fullName"),
                "mq": False, "offsite": None,
                # the Ivy tournament names its CITY plainly; the venue-for-metro
                # rule would turn New York back into Levien Gymnasium
                "city": (rules.tourney_city(city, v.get("fullName"), stage, y)
                         if ncaa else city),
                "nets": sorted(set(networks(c))), "teams": side, "header": None,
                "slots": [], "type": None, "champ": "Ivy" if ivy else None,
                "round": head, "title": False, "event": None, "standin": False,
                "bfri": False, "suffix": None, "opener": False,
                "rival_loss": False, "rivals": False, "post": ncaa,
                "rivals_only": True, "bowl": None, "showcase": False,
                "kickoff": False, "stage": stage, "michigan": False,
                "focus": team_id, "mx": {}})
    return out


def postseason_events(code, y):
    """Every team's postseason games that season: taken from the archive's full
    schedule from 2021, otherwise from cache/post-SPORT-SEASON.json -- fetched on
    its own when no Michigan walk has written it (2010, for 2011's champion)."""
    if y in SEASONS:
        return [x for x in events(code, y) if (x.get("season") or {}).get("type") == 3]
    path = os.path.join(CACHE, "post-%s-%d.json" % (code.lower(), y))
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))["events"]
    sport, grp = SPORTS[code]
    ev = []
    if code == "CFB":
        ev = fetch(sport, {"dates": "%d1201-%d0131" % (y, y + 1), "groups": grp,
                           "limit": 1000}, "x", cacheable=False).get("events", [])
    else:
        d, end = dt.date(y + 1, 3, 10), dt.date(y + 1, 4, 10)
        while d < end:
            e = min(d + dt.timedelta(days=6), end)
            ev += cbb_range(d, e, False)
            d = e + dt.timedelta(days=1)
    seen, post = set(), []
    for x in ev:
        if x.get("id") and x["id"] not in seen and (x.get("season") or {}).get("type") == 3:
            seen.add(x["id"])
            post.append(x)
    if season_over(code, y):
        json.dump({"events": post}, open(path, "w", encoding="utf-8"))
    return post


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


POLL_SERIES = {}      # (code, season, poll) -> [(date, ranks)] in week order


def poll_series(code, season, poll=1):
    """Every week of one poll for one season, each with the DATE it came out,
    cached under cache/polls/. Poll 1 is the AP; 21 is the CFP committee.
    Polls before 2017 carry no date of their own, so the week's start date
    stands in -- a poll is released as its week opens."""
    key = (code, season, poll)
    if key in POLL_SERIES:
        return POLL_SERIES[key]
    y = season if code == "CFB" else season - 1
    tag = "" if poll == 1 else "-p%d" % poll
    out, seen_any, misses = [], False, 0
    for week in range(1, 26):
        path = os.path.join(POLLS, "%s-%d-w%02d%s-dated.json"
                            % (code.lower(), season, week, tag))
        if os.path.exists(path):
            got = json.load(open(path, encoding="utf-8"))
        else:
            got = {"date": None, "ranks": {}}
            try:
                r = requests.get("%s/%s/seasons/%d/types/2/weeks/%d/rankings/%d"
                                 % (CORE, POLL_PATHS[code], season, week, poll),
                                 timeout=30)
            except requests.RequestException:
                break
            if r.status_code == 200:
                j = r.json()
                got["date"] = (j.get("date") or "")[:10] or None
                for t in j.get("ranks") or []:
                    m = re.search(r"/teams/([0-9]+)",
                                  (t.get("team") or {}).get("$ref", ""))
                    if m:
                        got["ranks"][m.group(1)] = t.get("current")
                if got["ranks"] and not got["date"]:
                    try:
                        wk = requests.get("%s/%s/seasons/%d/types/2/weeks/%d"
                                          % (CORE, POLL_PATHS[code], season, week),
                                          timeout=30).json()
                        got["date"] = (wk.get("startDate") or "")[:10] or None
                    except (requests.RequestException, ValueError):
                        pass
            if got["ranks"] or season_over(code, y):
                os.makedirs(POLLS, exist_ok=True)
                json.dump(got, open(path, "w", encoding="utf-8"))
        if got["date"] and got["ranks"]:
            out.append((got["date"], got["ranks"]))
            seen_any, misses = True, 0
        elif seen_any:
            # A SKIPPED WEEK IS NOT THE END (2026-09-16): 2020 football has
            # holes all through the autumn and 2025-26 basketball skips its
            # holiday week, so only a run of three misses ends the season
            misses += 1
            if misses >= 3:
                break
    # ...and ORDER BY DATE, not by week: ESPN files some polls under the wrong
    # week (2025-26's final April poll sits in week 2)
    out.sort(key=lambda p: p[0])
    POLL_SERIES[key] = out
    return out


def ap_before(code, y, day, poll=1):
    """The poll in force on `day` -- the latest one released on or before it
    -- as {team id: rank}.

    ESPN's scoreboard drops rankings on a good share of older games: the Big
    Ten Tournament (his list of 2026-09-16, fourteen games, matched exactly),
    the Champions Classic, North Carolina-Michigan in 2017 and 2018, and the
    2018 and 2019 CFP semifinals. The week number that ap_ranks keys on is
    missing on many of them too, so the poll is found by its DATE instead.
    """
    season = y if code == "CFB" else y + 1
    best = {}
    for date, ranks in poll_series(code, season, poll):
        if date <= day.isoformat():
            best = ranks
        else:
            break
    return best


def final_poll(code, y):
    """The season's FINAL poll as {team id: rank}, cached under cache/polls/.

    ESPN lists a season's polls in order and the final one comes last: football
    2023 ends on "Final Rankings" (types/3/weeks/1), basketball 2025-26 on a
    postseason week 3 -- so take the last entry rather than guessing its week.
    """
    season = y if code == "CFB" else y + 1
    # FOOTBALL TAKES THE AP POLL THROUGH 2013 AND THE CFP COMMITTEE RANKINGS
    # FROM 2014 (his call 2026-09-11). ESPN calls type 21 "Playoff Committee
    # Rankings" and carries it for every season from 2014 on; 2013 and earlier
    # have only the AP poll (type 1), the coaches poll and the BCS standings.
    # Basketball stays on the AP poll throughout. The CFP cache is its own file
    # so an AP final saved earlier is never served in its place.
    kind = 21 if code == "CFB" and y >= 2014 else 1
    path = os.path.join(POLLS, "%s-%d-final%s.json"
                        % (code.lower(), season, "-cfp" if kind == 21 else ""))
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    ranks = {}
    try:
        r = requests.get("%s/%s/seasons/%d/rankings/%d"
                         % (CORE, POLL_PATHS[code], season, kind), timeout=30)
        refs = ([x.get("$ref") for x in (r.json().get("rankings") or [])]
                if r.status_code == 200 else [])
        if refs:
            q = requests.get(refs[-1].replace("http://", "https://"), timeout=30)
            if q.status_code == 200:
                for t in q.json().get("ranks") or []:
                    m = re.search(r"/teams/([0-9]+)", (t.get("team") or {}).get("$ref", ""))
                    if m:
                        ranks[m.group(1)] = t.get("current")
    except (requests.RequestException, ValueError):
        return {}
    if ranks and season_over(code, y):
        os.makedirs(POLLS, exist_ok=True)
        json.dump(ranks, open(path, "w", encoding="utf-8"))
    return ranks


def playoff_finish(code, y, evs):
    """How far each team went in the CFP or the NCAA Tournament that season:
    {team id: "Semis" / "Champs" / ...}, in his sheet's words (rules.FINISH_SHORT).
    A team is filed under the round it LOST; the title-game winner is "Champs".
    """
    out = {}
    for x in evs:
        if (x.get("season") or {}).get("type") != 3:
            continue
        c = (x.get("competitions") or [{}])[0]
        cs = c.get("competitors") or []
        if len(cs) != 2 or not ((c.get("status") or {}).get("type") or {}).get("completed"):
            continue
        heads = [n.get("headline") or "" for n in (c.get("notes") or [])]
        stage = rules.stage_label(code, 3, heads, season=y) or ""
        # before the CFP (2011-2013) the title game was the BCS National
        # Championship, which reads as a bowl
        if (code == "CFB" and not stage.startswith("CFP")
                and "national championship" in " ".join(heads).lower()):
            stage = "CFP | Championship"
        if not (stage.startswith("CFP") or stage.startswith("NCAA Tournament")):
            continue
        rnd = stage.split(" | ")[1] if " | " in stage else ""
        for k in cs:
            if k.get("winner"):
                if rnd == "Championship":
                    out[k["team"]["id"]] = "Champs"
            else:
                fin = rules.FINISH_SHORT.get(rnd, rnd or "Playoff")
                # A TOP-SIX SEED OUT IN THE FIRST WEEKEND says which seed it
                # was -- "Rd 1 | No. 4" (his call 2026-09-18); ESPN's tournament
                # rank IS the seed
                seed = ((k.get("curatedRank") or {}).get("current"))
                if (code == "CBB" and rnd in ("Round 1", "Round 2") and seed
                        and seed <= 6):
                    fin += " | No. %d" % seed
                out[k["team"]["id"]] = fin
    return out


SHEET_ID = "1yLrd2BOhtLqS0YZLGBlBlDiypMhGjNJ5nw8fVs1nZu0"
# (focus team, sport) -> tab
SHEET_TABS = {("130", "CFB"): "Michigan CFB", ("130", "CBB"): "Michigan CBB",
              ("130", "CHK"): "Michigan HKY",       # his tab's name (2026-09-21)
              ("172", "CHK"): "Cornell HKY", ("172", "CBB"): "Cornell CBB",
              ("nfl-8", "NFL"): "Lions", ("mlb-6", "MLB"): "Tigers",
              ("nhl-5", "NHL"): "Red Wings", ("nba-8", "NBA"): "Pistons",
              ("nba-5", "NBA"): "Cavaliers"}


def sheet_season(sport, year):
    """His Year column: "2023" for football, "2011-12" for basketball."""
    year = (year or "").strip()
    if not year:
        return None
    try:
        return int(year.split("-")[0])
    except ValueError:
        return None


def sheet_date(s):
    """His Date column, M/D/YY."""
    try:
        m, d, y = (s or "").strip().split("/")
        y = "20" + y if len(y) == 2 else y
        return "%s-%02d-%02d" % (y, int(m), int(d))
    except (ValueError, AttributeError):
        return None


def load_sheet():
    """His Google Sheet, read straight from its published CSV so the 6am cloud
    build picks up whatever he filled in overnight -- no download, no file.

    Returns {(sport, season, date): row} plus, per (sport, season), which
    COLUMNS he has actually used. That last part matters: a season he has not
    reached yet must keep the rules it has now rather than silently losing its
    capitals and washes, so absence only means "off" once he has marked that
    season at all.
    """
    out, used, bodies = {}, {}, {}
    for (focus, code), tab in SHEET_TABS.items():
        url = ("https://docs.google.com/spreadsheets/d/%s/gviz/tq"
               "?tqx=out:csv&headers=1&sheet=%s"
               % (SHEET_ID, tab.replace(" ", "%20")))
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            body = r.content.decode("utf-8-sig")
        except requests.RequestException as e:
            print("  WARN: could not read the %s tab (%s)" % (tab, e), file=sys.stderr)
            continue
        # A TAB THAT DOES NOT EXIST IS NOT AN ERROR TO GVIZ: it silently answers
        # with the FIRST tab instead (found 2026-09-16, before his Michigan
        # Hockey tab existed). A body identical to one already read is that.
        if body in bodies:
            print("  WARN: no %s tab yet -- Google returned %s instead; skipped"
                  % (tab, bodies[body]), file=sys.stderr)
            continue
        bodies[body] = tab
        rows = list(csv.reader(io.StringIO(body)))
        if not rows:
            continue
        # COLUMNS ARE FOUND BY NAME, never by position (2026-09-13): he adds
        # columns as he goes, and reading G-J by index would silently put box
        # colours in the wrong fields the moment anything shifts. Only the
        # block before the first BLANK header is his -- everything past it is
        # his own working area, which repeats these very names.
        head = rows[0]
        stop = next((i for i, h in enumerate(head) if not (h or "").strip()), len(head))
        col = {}
        for i, h in enumerate(head[:stop]):
            key = (h or "").strip().lower()
            if key and key not in col:          # FIRST wins, never the copy
                col[key] = i
        need = ("year", "date", "opponent")
        if not all(k in col for k in need):
            print("  WARN: %s is missing one of Year/Date/Opponent" % tab, file=sys.stderr)
            continue
        for raw in rows[1:]:
            def cell(label):
                i = col.get(label)
                return (raw[i] or "").strip() if i is not None and i < len(raw) else ""
            season, date = sheet_season(code, cell("year")), sheet_date(cell("date"))
            # A BLANK YEAR takes its season from the date (2026-09-21): his
            # Cornell HKY tab fills the Year in for its first three seasons
            # only. Football is one calendar year from August; the winter
            # sports run July to June.
            if season is None and date:
                y, m = int(date[:4]), int(date[5:7])
                season = ((y if m >= 8 else y - 1) if code in ("CFB", "NFL")
                          else y if code == "MLB" else (y if m >= 7 else y - 1))
            if season is None or date is None:
                continue
            box = {"score_bg": cell("score bg"), "score_font": cell("score font"),
                   "rank_bg": cell("rank bg"), "rank_font": cell("rank font")}
            out[(focus, code, season, date)] = {
                "name": cell("opponent"), "attended": bool(cell("attended")),
                # his CASE column: "UPPER" puts the opponent in capitals
                "case": cell("case"),
                "shade": bool(cell("shade")), "border": cell("border"),
                "note": cell("notes") or cell("note"),
                "footer": cell("footer"), "box": box,
                # THE UNIFORM, Jersey / Pants / Acc. (his columns N-P), for the
                # Jersey filter only -- it paints nothing (2026-09-18)
                "jersey": "/".join(cell(k).title() for k in ("jersey", "pants", "acc."))
                          if all(cell(k) for k in ("jersey", "pants", "acc.")) else "",
            }
            flags = used.setdefault((focus, code, season), set())
            for label, flag in (("case", "case"), ("attended", "attended"), ("shade", "shade"),
                                ("border", "border"), ("notes", "note"),
                                ("note", "note"), ("footer", "footer"),
                                ("jersey", "jersey")):
                if cell(label):
                    flags.add(flag)
            if any(box.values()):
                flags.add("box")
    print("  sheet: %d rows across %d season-sports" % (len(out), len(used)))
    if len(out) < SHEET_FLOOR:
        raise SystemExit(
            "ABORT: his Michigan tabs returned only %d rows, below the floor "
            "of %d. Rows COLLAPSED in the browser are omitted from the gviz "
            "export -- expand them and run again." % (len(out), SHEET_FLOOR))
    return out, used


def load_game_overrides():
    """game-overrides.json -- per-game facts ESPN gets wrong or omits, by game
    id. Understood keys: "city" (the neutral-site chip) and "event" (the
    showcase name). event-overrides.json cannot reach these games: it is keyed
    on the ESPN event NAME, which for them is null (his call 2026-09-11)."""
    path = os.path.join(HERE, "game-overrides.json")
    if not os.path.exists(path):
        return {}
    raw = json.load(open(path, encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def upcoming_window(today=None):
    """Today through the COMING SUNDAY, in Eastern time (his call 2026-09-12).

    Monday gives six days ahead; Sunday gives just Sunday itself. The daily
    6am build is what keeps this moving -- yesterday is gone by the time it
    runs, so the window never holds a game that has already been played.
    """
    today = today or dt.datetime.now(ET).date()
    return today, today + dt.timedelta(days=(6 - today.weekday()) % 7)


def upcoming_season(code, d):
    """Which SEASON a date belongs to. Football is one calendar year from
    August; basketball straddles two, so January to June belongs to the year
    before. Without this an upcoming game lands in the wrong season and the
    Year filter hides it."""
    if code == "CFB":
        return d.year if d.month >= 8 else d.year - 1
    return d.year if d.month >= 7 else d.year - 1


def upcoming_events(code, start, end):
    """Scheduled games in the window, straight from ESPN and NEVER cached --
    kickoff times and networks are announced piecemeal, which is half the
    reason for the daily run."""
    sport, grp = SPORTS[code]
    out, seen = [], set()
    d = start
    while d <= end:
        e = min(d + dt.timedelta(days=6), end)
        try:
            got = fetch(sport, {"dates": "%s-%s" % (d.strftime("%Y%m%d"),
                                                    e.strftime("%Y%m%d")),
                                "groups": grp, "limit": 1000},
                        "upcoming", cacheable=False).get("events", [])
        except requests.RequestException:
            got = []
        for x in got:
            if x.get("id") and x["id"] not in seen:
                seen.add(x["id"])
                out.append(x)
        d = e + dt.timedelta(days=1)
    return out


def michigan_rest_of_season(code, y, after):
    """MICHIGAN'S WHOLE REMAINING SCHEDULE (his call 2026-09-18): every game
    of the current season not yet played and past the coming-week window, from
    ESPN's team schedule -- never cached, like the window itself."""
    sport = SPORTS[code][0]
    out = []
    for stype in (2, 3):
        try:
            got = get_json("%s/%s/teams/%s/schedule" % (BASE, sport, rules.MICHIGAN),
                           params={"season": y if code == "CFB" else y + 1,
                                   "seasontype": stype})
        except requests.RequestException:
            continue
        for x in got.get("events") or []:
            try:
                d = (dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ")
                     .replace(tzinfo=dt.timezone.utc).astimezone(ET)).date()
            except (KeyError, ValueError):
                continue
            if d > after:
                out.append(x)
    return out


def seed_of(seeds, season, team):
    """His seed for that team that season, matched on either the full ESPN
    name or the location -- his tab writes "Michigan State Spartans"."""
    for key in (team.get("displayName"), team.get("location")):
        if key:
            hit = seeds.get((season, flat(key)))
            if hit:
                return hit
    return None


def load_seeds():
    """His BTT tab -- Year, Team, Seed -- as {(season, flat name): seed}.

    ESPN carries no conference-tournament seed (its ranking field there is the
    AP poll), so these are his. The tab names teams in full ("Michigan State
    Spartans"), which is why the lookup tries the display name as well as the
    location.
    """
    url = ("https://docs.google.com/spreadsheets/d/%s/gviz/tq"
           "?tqx=out:csv&headers=1&sheet=BTT" % SHEET_ID)
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    except (requests.RequestException, ValueError) as e:
        print("  WARN: could not read the BTT tab (%s)" % e, file=sys.stderr)
        return {}
    if not rows:
        return {}
    head = [(h or "").strip().lower() for h in rows[0]]
    try:
        yi, ti, si = head.index("year"), head.index("team"), head.index("seed")
    except ValueError:
        print("  WARN: the BTT tab needs Year, Team and Seed", file=sys.stderr)
        return {}
    out = {}
    for raw in rows[1:]:
        cell = lambda i: (raw[i] or "").strip() if i < len(raw) else ""
        year, team, seed = cell(yi), cell(ti), cell(si)
        if not (year and team and seed):
            continue
        try:
            out[(int(year.split("-")[0]), flat(team))] = int(seed)
        except ValueError:
            continue
    print("  BTT: %d seeds" % len(out))
    return out


RATING_TABS = {"CFB": "SP%2B", "CBB": "KP"}
# his spelling on the left, mine on the right, where the two genuinely differ
RATING_ALIAS = {
    "northcarolinastate": "ncstate",
    "mountstatemarys": "mountstmarys",      # his tab reads "Mount State Mary's"
    "iuindy": "iuindianapolis",             # KenPom shortens it; ESPN spells it out
}


def flat(n):
    """A team name with everything but letters and digits stripped, accents
    included -- "San Jose State" and "San Jose State", "Miami OH" and
    "Miami (OH)" both land in the same place."""
    n = unicodedata.normalize("NFKD", n or "")
    n = "".join(c for c in n if not unicodedata.combining(c))
    key = re.sub(r"[^a-z0-9]", "", n.lower())
    return RATING_ALIAS.get(key, key)


def rating_of(code, season, team_id, teams, ratings, rated_teams):
    """His rank for that team that season. A team no rating system covers --
    the Division II and NAIA exhibition opponents -- reads "DII" instead of
    nothing, so the card says why it is blank (his call 2026-09-13)."""
    short = (teams.get(team_id) or {}).get("short") or ""
    # his tabs write a school the way ESPN does -- "VCU", not the "Virginia
    # Commonwealth" the cards spell out -- so the ESPN name is tried too (VCU
    # read "DII", his catch 2026-09-18)
    espn = {v: k for k, v in rules.NAME_OVERRIDES.items()}.get(short)
    keys = [k for k in (flat(short), flat(espn or "")) if k]
    for key in keys:
        hit = ratings.get((code, season, key))
        if hit:
            return hit
    if keys and code in rated_teams and not any(k in rated_teams[code] for k in keys):
        return "DII"
    return None


def load_ratings():
    """{(sport, season, flat team name): rank} from the SP+ and KP tabs, plus
    the set of teams each tab KNOWS -- a team missing from the tab entirely is
    unrated (Division II), which is different from a season he has not filled.
    """
    out, known = {}, {}
    for code, tab in RATING_TABS.items():
        url = ("https://docs.google.com/spreadsheets/d/%s/gviz/tq"
               "?tqx=out:csv&headers=1&sheet=%s" % (SHEET_ID, tab))
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
        except (requests.RequestException, ValueError) as e:
            print("  WARN: could not read the %s tab (%s)" % (tab, e), file=sys.stderr)
            continue
        if not rows:
            continue
        head = rows[0]
        # the season each column holds: "2023" for football, "2011-12" for
        # basketball -- both start with the year the season began
        cols = {}
        for i, h in enumerate(head[1:], start=1):
            h = (h or "").strip()
            if not h:
                continue
            try:
                cols[i] = int(h.split("-")[0])
            except ValueError:
                continue
        seen = set()
        for raw in rows[1:]:
            if not raw or not (raw[0] or "").strip():
                continue
            key = flat(raw[0])
            seen.add(key)
            for i, season in cols.items():
                v = (raw[i] or "").strip() if i < len(raw) else ""
                if v:
                    out[(code, season, key)] = v
        known[code] = seen
        print("  %s: %d teams, %d ratings" % (tab.replace("%2B", "+"), len(seen),
                                              sum(1 for k in out if k[0] == code)))
    return out, known


def rank_of(c):
    v = (c.get("curatedRank") or {}).get("current")
    return None if v in (None, 0, 99) else v


def networks(comp):
    out = []
    for b in comp.get("broadcasts") or []:
        # the scoreboard lists "names"; a TEAM SCHEDULE gives each broadcast as
        # media.shortName instead, and reading only "names" found no TV at all
        # on hockey and Cornell games (2026-09-16)
        names = b.get("names") or []
        if not names and (b.get("media") or {}).get("shortName"):
            names = [b["media"]["shortName"]]
        out += names
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


# POWER FOUR/FIVE COVERAGE (his call 2026-09-15). Every TV Window week, Week 0
# and Conference Championship Week excluded, has to show each power conference.
# The Pac-12 stops after 2023, when it broke up.
COVER_CONFS = {"1": (2021, 2026),      # ACC
               "4": (2021, 2026),      # Big 12
               "5": (2021, 2026),      # Big Ten
               "8": (2021, 2026),      # SEC
               "9": (2021, 2023)}      # Pac-12
# A HOME GAME COVERS ITS CONFERENCE. An away game covers it only in the two
# packages he named: the ACC visiting the SEC on ABC, and the Big 12 visiting
# the Big Ten on FOX.
COVER_AWAY = {("1", "8", "ABC"), ("4", "5", "FOX")}
# His network waterfall for a game that has to be ADDED: each tier is exhausted
# before the next gets a turn.
COVER_TIERS = [["FOX", "CBS", "NBC"], ["ESPN"], ["FS1", "ESPN2"]]
# One conference-week his rules cannot fill: no ACC team hosted on any of the
# six networks in week 2 of 2021. His fix (2026-09-15) is to take Pittsburgh at
# Tennessee -- an ACC visitor, but on ESPN rather than the ABC the away rule
# asks for. A one-off, by game id, not a rule.
COVER_FORCE = {(2021, "1", 2): "401282066"}      # Pittsburgh at Tennessee


def _kick_bucket(d):
    """His kickoff preference when nothing in the game is ranked: primetime,
    then the early window, then the afternoon, then the late night, then
    whatever is left (a morning kick)."""
    m = d.hour * 60 + d.minute
    if 19 * 60 <= m <= 21 * 60:
        return 0
    if 12 * 60 <= m < 15 * 60:
        return 1
    if 15 * 60 <= m < 19 * 60:
        return 2
    if m > 21 * 60:
        return 3
    return 4


def champ_week(evs):
    """The week ESPN files the conference championship games under -- the first
    week TV Windows does NOT have to cover."""
    ws = []
    for x in evs:
        comps = x.get("competitions") or []
        if not comps or (x.get("season") or {}).get("type") != 2:
            continue
        heads = [n.get("headline") or "" for n in (comps[0].get("notes") or [])]
        # "FCS Championship - First Round" is a PLAYOFF game, and it is played
        # on rivalry weekend -- reading it as Championship Week cut week 13 out
        # of 2021-23 entirely (his catch 2026-09-15)
        if any("FCS" in h or "Round" in h for h in heads):
            continue
        if rules.is_championship(heads):
            w = (x.get("week") or {}).get("number")
            if w:
                ws.append(w)
    return min(ws) if ws else None


def covers(conf, home_conf, away_conf, nets):
    """Does this game cover `conf`? Its home conference always; a visitor only
    in the two packages of COVER_AWAY.

    The visitor's own conference has to match -- leaving that out made every
    SEC home game on ABC cover the ACC, and every Big Ten home game on FOX
    cover the Big 12, which is how 2024-25 looked full when it was empty
    (his catch 2026-09-15).
    """
    if home_conf == conf:
        return True
    return any(conf == a and away_conf == a and home_conf == h and n in nets
               for a, h, n in COVER_AWAY)


def cover_ids(evs, season, wk0=(), net_over=None):
    """The best game available to stand in for each (conference, week), by his
    waterfall (2026-09-15). Every slot gets a candidate here; which slots
    actually NEED one is settled after the main loop, when coverage is known.

    A game that has to be ADDED is always a Saturday HOME game of the
    conference -- the away packages above admit an existing game, they do not
    choose a new one."""
    pick = {}
    last = champ_week(evs)
    for x in evs:
        comps = x.get("competitions") or []
        if not comps:
            continue
        c = comps[0]
        cs = c.get("competitors") or []
        if len(cs) != 2 or (x.get("season") or {}).get("type") != 2:
            continue
        week = 0 if x["id"] in wk0 else (x.get("week") or {}).get("number")
        if not week or (last and week >= last):
            continue              # Week 0 and Championship Week are not covered
        try:
            d = (dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ")
                 .replace(tzinfo=dt.timezone.utc).astimezone(ET))
        except (KeyError, ValueError):
            continue
        if d.weekday() not in (3, 4, 5):
            continue              # Saturday, or a Thursday/Friday last resort
        day = 0 if d.weekday() == 5 else 1
        nets = set((net_over or {}).get(x["id"], ())) or set(networks(c))
        tier = next((i for i, tn in enumerate(COVER_TIERS) if nets & set(tn)), None)
        if tier is None:
            continue
        home = next((k for k in cs if k.get("homeAway") == "home"), None)
        if not home:
            continue              # a neutral game names no host
        conf = str((home.get("team") or {}).get("conferenceId"))
        span = COVER_CONFS.get(conf)
        if not span or not (span[0] <= season <= span[1]):
            continue
        ranks = sorted(r for r in (rank_of(k) for k in cs) if r)
        if len(ranks) == 2:
            rest = (0, ranks[0], ranks[1], 0)
        elif ranks:
            rest = (1, ranks[0], 99, 0)
        else:
            order = [n for n in COVER_TIERS[tier] if n in nets]
            rest = (2, _kick_bucket(d), COVER_TIERS[tier].index(order[0]), 0)
        key = (day, tier) + rest
        slot = (conf, week)
        if slot not in pick or key < pick[slot][0]:
            pick[slot] = (key, x["id"])
    out = {v[1]: k for k, v in pick.items()}
    for (yr, cf, wk), gid in COVER_FORCE.items():
        if yr == season:
            out[gid] = (cf, wk)
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


def _shift_day(iso, days):
    y, m, d = (int(v) for v in iso.split("-"))
    return (dt.date(y, m, d) + dt.timedelta(days=days)).isoformat()


def norm(n):
    """A team name flattened for matching, so his sheet and ESPN agree --
    "UConn" and "Connecticut", "USC" and "Southern Cal". Lifted out of the
    retired tag-seeding script (2026-09-13)."""
    return rules.display_name(n or "").lower().replace(".", "").strip()


def load_locations():
    """His Locations tab: where the two shows broadcast from, by date.

    Football sits in the first block (Date, Big Noon Kickoff, College GameDay)
    and basketball in the second, after a blank column (Date, College GameDay).
    Read by HEADER, like every other tab, and the blank column is what
    separates the two blocks.
    """
    url = ("https://docs.google.com/spreadsheets/d/%s/gviz/tq"
           "?tqx=out:csv&headers=1&sheet=Locations" % SHEET_ID)
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    except (requests.RequestException, ValueError) as e:
        print("  WARN: could not read the Locations tab (%s)" % e, file=sys.stderr)
        return {}
    if not rows:
        return {}
    head = [(h or "").strip().lower() for h in rows[0]]
    # the blank column splits football from basketball
    split = next((i for i, h in enumerate(head) if not h), len(head))
    blocks = [("CFB", 0, split), ("CBB", split + 1, len(head))]
    out = {}
    for code, lo, hi in blocks:
        cols = {head[i]: i for i in range(lo, min(hi, len(head))) if head[i]}
        if "date" not in cols:
            continue
        for raw in rows[1:]:
            get = lambda label: ((raw[cols[label]] or "").strip()
                                 if label in cols and cols[label] < len(raw) else "")
            day = sheet_date(get("date"))
            if not day:
                continue
            for label, tag in (("big noon kickoff", "Big Noon Kickoff"),
                               ("college gameday", "College GameDay")):
                who = get(label)
                if who:
                    out.setdefault((code, day), {})[tag] = who
    print("  locations: %d show-days" % len(out))
    # A COLLAPSED ROW GROUP IS INVISIBLE TO gviz (caught 2026-09-14): with his
    # historical rows collapsed in the browser this returned 14 rows instead of
    # 302 and the archive lost 174 show chips, with the sheet never edited.
    # Failing here leaves the last good site up; a quiet build would not.
    if len(out) < LOCATIONS_FLOOR:
        raise SystemExit(
            "ABORT: the Locations tab returned only %d show-days, below the "
            "floor of %d. Rows COLLAPSED in the browser are omitted from the "
            "gviz export -- expand them and run again." % (len(out), LOCATIONS_FLOOR))
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
        if (name not in rules.NOT_OFFSITE and name != usual and seen[name] <= 2
                and times > seen[name] and sum(seen.values()) >= 4):
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
    locs = load_locations()
    ev_overrides = load_event_overrides()
    game_over = load_game_overrides()
    ratings, rated_teams = load_ratings()
    seeds = load_seeds()
    cover_last = {}       # the championship week of each football season
    cover_slot = {}       # game id -> (season, conference, week) it covers
    for code in ("CFB", "CBB"):
        bt = rules.BIG_TEN[code]
        years = set(RIVAL_SEASONS) | set(SEASONS) | rules.MICHIGAN_SEASONS.get(code, set())
        for y in sorted(years):
            # before the archive: his rivals' games from 2014, for Rivals, and
            # every Michigan game from 2011, for the Michigan view -- one list
            archive_era = y in SEASONS
            if archive_era:
                evs = events(code, y)
            else:
                evs, ids = [], set()
                for x in ((rival_events(code, y) if y in RIVAL_SEASONS else []) +
                          (michigan_events(code, y)
                           if y in rules.MICHIGAN_SEASONS.get(code, ()) else [])):
                    if x.get("id") not in ids:
                        ids.add(x.get("id"))
                        evs.append(x)
            fox_fri = fox_friday_dates(evs) if code == "CFB" else set()
            wk0 = week_zero_ids(evs) if code == "CFB" else set()
            # the best candidate to cover each power conference this week; which
            # of them is NEEDED is settled after the loop (his call 2026-09-15)
            cover_pick = set()
            if code == "CFB" and archive_era:
                picks = cover_ids(evs, y, wk0, net_overrides)
                cover_pick = set(picks)
                cover_slot.update({g: (y,) + q for g, q in picks.items()})
                cover_last[y] = champ_week(evs)
            espn_sat = espn_saturday_ids(evs) if code == "CBB" else set()
            sizes = event_sizes(evs)
            offsite = offsite_games(evs)
            # the Michigan view: opponents' playoff finish and final AP rank this
            # season, and last season's national champion (the "^" in his sheet)
            mich_season = y in rules.MICHIGAN_SEASONS.get(code, ())
            # a cancelled game reaches the archive only through the team
            # schedule, so it is merged in here rather than found in evs
            finish = (playoff_finish(code, y, postseason_events(code, y))
                      if mich_season else {})
            final_ap = final_poll(code, y) if mich_season else {}
            reigning = None
            if mich_season:
                last = playoff_finish(code, y - 1, postseason_events(code, y - 1))
                reigning = next((t for t, f in last.items() if f == "Champs"), None)
            for x in evs:
                comps = x.get("competitions") or []
                if not comps:
                    continue                      # older payloads omit it
                c = comps[0]
                cs = c.get("competitors") or []
                if len(cs) != 2:
                    continue
                # cancelled games are deliberately NOT kept (his call
                # 2026-09-13, after seeing them on the cards)
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
                # Rivals reaches back to 2014 only: an older Michigan-view season
                # must not feed it
                if not archive_era and y not in RIVAL_SEASONS:
                    rival_loss = False
                postseason = stype == 3
                # bowls / CFP / NCAA are dropped -- unless a rival lost one
                # a Michigan-view season keeps every Michigan game, bowls and
                # tournaments included
                mich = mich_season and any(k["team"]["id"] == rules.MICHIGAN for k in cs)
                if stype != 2 and not (postseason and (rival_loss or mich)):
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
                # HIS network wins outright (his call 2026-09-13): ESPN had
                # Oregon-Oklahoma State on Disney+/ESPNEWS when it was on ESPN,
                # and a fill-only override could never correct that -- it only
                # applied when ESPN listed nothing at all.
                nets = set(net_overrides.get(x["id"], ())) or set(networks(c))
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
                # THE STAND-INS (his call 2026-09-15): the 2021-22 SEC
                # game on CBS, and any Big Ten home game on a broadcast
                # network from 2021. Neither belongs to a window, so neither
                # is Marquee -- see rules.sec_on_cbs / rules.b1g_host.
                home_conf = next((str((k.get("team") or {}).get("conferenceId"))
                                  for k in cs if k.get("homeAway") == "home"), None)
                sec_cbs = code == "CFB" and rules.sec_on_cbs(y, nets, d, confs)
                standin = code == "CFB" and (
                    sec_cbs or rules.b1g_host(y, nets, home_conf))
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
                        espn_sat=x["id"] in espn_sat,
                        both_big_ten=all(q == bt for q in confs),
                        ranked=any(ranks))
                conf, head = rules.power5_title(heads, code)
                title = rules.is_title_game(code, conf, head)
                # a show broadcast from this game? match either side of the
                # date, since a late kickoff shifts the Eastern one
                names = frozenset(norm(k["team"].get("location") or "")
                                  for k in cs)
                # A show ADMITS a game to TV Windows (it feeds `normal`, and
                # `normal` is what keeps a game out of rivals_only). His tab
                # covers every season back to 2011, but TV Windows must not
                # grow past 2021 (his call 2026-09-13) -- so the flag is held
                # to the archive era. Older show games still get the CHIP.
                show = archive_era and any(
                    names & {norm(v) for v in locs.get((code, dd), {}).values()}
                    for dd in (d.date().isoformat(),
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
                                            b1g_tourney_run=b1g_run,
                                            postseason=postseason)
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
                # a TV WINDOWS claim, which is what a cover has to supply --
                # a game kept for its game TYPE alone is on Key Games and not
                # here, so it can still be the week's cover (his catch
                # 2026-09-15)
                tv_other = bool(slots or title or black_friday
                              or show or opener or showcase or kickoff or standin
                              or x["id"] in overrides or x["id"] in extras)
                normal_other = bool(tv_other or gtype)
                normal = bool(normal_other or x["id"] in cover_pick)
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
                # KEY GAMES WANTS EVERY RIVAL LOSS (his call 2026-09-20):
                # football from 2021 on, so a bad Michigan State season is
                # complete there. These are kept with `rivals` still false, so
                # the Rivals tab is unchanged -- eleven Michigan State losses
                # and one Notre Dame one were simply never stored before.
                key_loss = code == "CFB" and rival_loss and y >= 2021
                # every Michigan game in a Michigan-view season is kept, whatever
                # else is true of it
                if not normal and not rivals and not mich and not key_loss:
                    continue
                # kept ONLY for Rivals or the Michigan view (a bowl, an early
                # tournament round, a Michigan game no rule admits): strip
                # whatever would put it on TV Windows or Key Games
                rivals_only = not normal
                if rivals_only:
                    # FOX Big Noon and ABC Primetime still LABEL these cards
                    # (his call 2026-09-13): a 2019 Michigan game at noon on
                    # FOX reads "FOX BIG NOON" on the Michigan view. Keeping
                    # the window name does not admit the game to TV Windows or
                    # Key Games -- `rivals_only` is what bars it there.
                    slots = slots & {"FOX Big Noon", "ABC Saturday"}
                    gtype, black_friday, show, opener = None, False, False, False
                    showcase = kickoff = False
                    standin = sec_cbs = False
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

                stage_txt = rules.stage_label(code, stype, heads, conf=conf,
                                              month=d.month, season=y)
                # his seeds ride on conference-tournament games only
                seeded = bool(stage_txt and stage_txt.startswith("Big Ten Tournament"))
                # A GAME ESPN LEFT WITH NO RANKING ON EITHER SIDE takes the
                # poll in force that day (his calls 2026-09-16). A game with
                # no ranked team really in it simply finds nothing. The CFP
                # reads the COMMITTEE's rankings, since there the number is
                # the seed; the NCAA Tournament and the NIT are left alone --
                # their number is a seed no poll holds, and ESPN has every one.
                # DISPLAY ONLY: this is read after the game type is settled,
                # so Key Games and Rivals admission are unchanged.
                poll_day = {}
                if not any(ranks):
                    if stage_txt and stage_txt.startswith("CFP"):
                        poll_day = ap_before(code, y, d.date(), poll=21)
                    elif not (stage_txt and stage_txt.startswith(("NCAA Tournament", "NIT"))):
                        poll_day = ap_before(code, y, d.date())
                side = []
                for k in cs:
                    t = k["team"]
                    was = teams.get(t["id"]) or {}
                    teams[t["id"]] = {"name": t["displayName"],
                                      "short": rules.display_name(
                                          t.get("location") or t["displayName"]),
                                      "abbr": t.get("abbreviation"),
                                      # a cancelled game carries no colours;
                                      # keep the ones already known
                                      "color": t.get("color") or was.get("color"),
                                      "alt": t.get("alternateColor") or was.get("alt")}
                    if was.get("conf"):
                        teams[t["id"]]["conf"] = was["conf"]
                    side.append({"id": t["id"], "score": int(k["score"]),
                                 "rank": (rank_of(k) or poll_day.get(t["id"])
                                          or (ap.get(t["id"]) if rivals_only else None)),
                                 "win": bool(k.get("winner")),
                                 "home": k.get("homeAway") == "home",
                                 "conf": str(t.get("conferenceId")),
                                 "seed": (seed_of(seeds, y, t)
                                          if seeded else None)})
                v = c.get("venue") or {}
                # the week this game belongs to -- None in the postseason, 0
                # for a Week 0 game ESPN numbers as 1. Computed ONCE here so
                # the card and the header cannot disagree.
                week_no = (None if postseason
                           else 0 if x["id"] in wk0
                           else (x.get("week") or {}).get("number"))
                head_txt = (rules.cfb_header(card_slots, d, forced, season=y,
                                             week=week_no)
                            if code == "CFB" else None)
                # the 2021-22 SEC game has no window to name it
                if sec_cbs and not head_txt:
                    head_txt = rules.SEC_ON_CBS["label"]
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
                    "week": week_no,
                    "venue": v.get("fullName"),
                    "mq": (not rivals_only) and rules.is_marquee(code, nets, d, slots,
                                           big_ten=(bt in confs),
                                           tourney=tourney),
                    "offsite": offsite.get(x["id"]),
                    # THE NCAA TOURNAMENT SHOWS THE CITY (his call
                    # 2026-09-13): the venue-for-metro rule makes a Sweet
                    # Sixteen read "United Center" when he wants "Chicago".
                    # 2020-21 is the exception -- that whole tournament was in
                    # Indiana, so only the venue tells the rounds apart.
                    "city": (game_over[x["id"]]["city"]
                             if "city" in game_over.get(x["id"], {})
                             else rules.tourney_city(
                                 (v.get("address") or {}).get("city"),
                                 v.get("fullName"), stage_txt, y)),
                    "nets": sorted(nets), "teams": side,
                    "header": (head_txt if code == "CFB" else suffix),
                    "slots": sorted(slots), "type": gtype,
                    "champ": conf, "round": head, "title": title,
                    # an override KEY that is present wins even when empty --
                    # "" means show nothing, which `or` could not express
                    "event": (game_over[x["id"]]["event"]
                              if "event" in game_over.get(x["id"], {}) else event),
                    # admitted to TV Windows without a window of its own
                    "standin": bool(standin),
                    # this week's cover for a power conference, and whether it
                    # had any other reason to be here (see the pass below)
                    "coverpick": x["id"] in cover_pick,
                    "coveronly": (x["id"] in cover_pick and not tv_other),
                    "bfri": black_friday, "suffix": suffix,
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
                    "stage": stage_txt,
                })
                if mich:
                    opp = next(k["team"]["id"] for k in cs
                               if k["team"]["id"] != rules.MICHIGAN)
                    mx = {"finish": finish.get(opp), "final": final_ap.get(opp),
                          "reigning": opp == reigning,
                          "rating": rating_of(code, y, opp, teams,
                                              ratings, rated_teams)}
                    keep[-1]["michigan"] = True
                    keep[-1]["mx"] = {k: v for k, v in mx.items() if v}
    # UPCOMING GAMES (his call 2026-09-12): today through the coming Sunday,
    # on the TV Windows and Michigan views only. They carry no score and no
    # winner, so every result rule in the app has to step around them -- see
    # `upcoming` in app.js. Key Games and Rivals exclude them for free: Key
    # Games needs a game TYPE (an upset cannot be known before kickoff) and
    # Rivals needs a rival LOSS.
    start, end = upcoming_window()
    have = {g["id"] for g in keep}
    added = 0
    for code in ("CFB", "CBB"):
        y = upcoming_season(code, start)
        if y not in rules.MICHIGAN_SEASONS.get(code, ()) and y not in SEASONS:
            continue
        up_evs = upcoming_events(code, start, end)
        seen_up = {x.get("id") for x in up_evs}
        later = [x for x in michigan_rest_of_season(code, y, end) if x.get("id") not in seen_up]
        later_ids = {x["id"] for x in later}
        up_evs = up_evs + later
        # the coming week is covered like any other (his call 2026-09-14)
        up_cover = set()
        if code == "CFB":
            picks = cover_ids(up_evs, y, set(), net_overrides)
            up_cover = set(picks)
            cover_slot.update({g: (y,) + q for g, q in picks.items()})
        for x in up_evs:
            if x.get("id") in have:
                continue
            comps = x.get("competitions") or []
            if not comps:
                continue
            c = comps[0]
            cs = c.get("competitors") or []
            if len(cs) != 2:
                continue
            # anything finished is the archive's business, not this window
            if (c.get("status") or {}).get("type", {}).get("completed"):
                continue
            try:
                d = (dt.datetime.strptime(x["date"], "%Y-%m-%dT%H:%MZ")
                     .replace(tzinfo=dt.timezone.utc).astimezone(ET))
            except (KeyError, ValueError):
                continue
            if not (start <= d.date() <= end) and x["id"] not in later_ids:
                continue
            nets = set(networks(c)) or set(net_overrides.get(x["id"], ()))
            side = []
            for k in cs:
                t = k.get("team") or {}
                if not t.get("id"):
                    break
                r = (k.get("curatedRank") or {}).get("current")
                teams.setdefault(t["id"], {
                    "name": t.get("displayName"),
                    "short": rules.display_name(
                        t.get("location") or t.get("displayName") or t["id"]),
                    "abbr": t.get("abbreviation"),
                    "color": t.get("color"), "alt": t.get("alternateColor")})
                side.append({"id": t["id"], "score": None,
                             "rank": r if r and r != 99 else None,
                             "win": False, "home": k.get("homeAway") == "home",
                             # a team SCHEDULE names no conference; the
                             # archive's latest one for the team stands in
                             "conf": str(t.get("conferenceId") or
                                         (latest_conf.get((code, t["id"])) or (None, None))[1]),
                             "seed": None})
            if len(side) != 2:
                continue
            mich = any(s["id"] == rules.MICHIGAN for s in side)
            heads = [n.get("headline") or "" for n in (c.get("notes") or [])]
            wk = (x.get("week") or {}).get("number")
            bt_code = rules.BIG_TEN[code]
            confs = [s["conf"] for s in side]
            ids = {s["id"] for s in side}
            ranked = any(s["rank"] for s in side)
            # the stand-ins, worked out exactly as the archive does it
            home_conf = next((q["conf"] for q in side if q["home"]), None)
            sec_cbs = code == "CFB" and rules.sec_on_cbs(y, nets, d, confs)
            standin = code == "CFB" and (
                sec_cbs or rules.b1g_host(y, nets, home_conf))
            if code == "CFB":
                slots = rules.cfb_slots(nets, d, y, ids, set(confs))
            else:
                slots = rules.cbb_slots(nets, d, all(q == bt_code for q in confs),
                                        ranked, bt_code in confs)
            # A SHOW IS ITS OWN ADMISSION to TV Windows, the same as in the
            # archive: a game whose only claim is hosting Big Noon Kickoff or
            # College GameDay still belongs there. This has to be worked out
            # HERE, because the Locations matcher runs long after the game
            # would already have been dropped (his catch 2026-09-14).
            names = frozenset(norm((k.get("team") or {}).get("location") or "")
                              for k in cs)
            show = any(names & {norm(v) for v in locs.get((code, dd), {}).values()}
                       for dd in (d.date().isoformat(),
                                  (d.date() - dt.timedelta(days=1)).isoformat(),
                                  (d.date() + dt.timedelta(days=1)).isoformat()))
            if (not slots and not mich and not show and not standin
                    and x["id"] not in up_cover):
                continue          # nothing to show it under on TV Windows
            # MARQUEE, worked out the same way the archive does it -- this was
            # hardcoded False, which hid every upcoming game from the Marquee
            # button (his catch 2026-09-14). A conference tournament belongs to
            # no broadcast package, so it is never Marquee.
            tourney = (rules.is_championship(heads)
                       and d.month in (3, 4) and code == "CBB")
            marquee = rules.is_marquee(code, nets, d, slots,
                                       big_ten=(bt_code in confs),
                                       tourney=tourney)
            # KEY GAMES BEFORE KICKOFF (his call 2026-09-14): only the
            # categories that do NOT depend on the result, which means both
            # teams ranked. Feeding the BETTER rank in as the winner can never
            # return an upset label -- "anyone beats #1" needs the loser to be
            # #1 -- so an upcoming game is never announced as an upset, and the
            # daily rebuild re-files it properly once it has been played.
            ranks = sorted(s["rank"] for s in side if s["rank"])
            gtype = (rules.game_type(code, ranks[0], ranks[1],
                                     has_big_ten=(bt_code in confs))
                     if len(ranks) == 2 else None)
            v = c.get("venue") or {}
            keep.append({
                "id": x["id"], "sport": code, "season": y,
                "date": d.strftime("%Y-%m-%d"), "dow": rules.DOW[d.weekday()],
                # ESPN parks an unset kickoff at midnight and says so
                "time": "TBD" if (x.get("timeValid") is False or c.get("timeValid") is False)
                        else d.strftime("%H:%M"),
                "neutral": bool(c.get("neutralSite")),
                "nets": sorted(nets), "teams": side, "week": wk,
                "slots": sorted(slots), "type": gtype, "champ": None,
                "round": (heads[0] if heads else None), "title": False,
                "header": ((rules.cfb_header(sorted(slots), d, season=y, week=wk)
                            or (rules.SEC_ON_CBS["label"] if sec_cbs else None))
                           if code == "CFB" else None),
                "venue": v.get("fullName"),
                "city": rules.display_city((v.get("address") or {}).get("city"),
                                           v.get("fullName")),
                "post": False, "event": None, "bowl": None, "offsite": None,
                "stage": None, "ot": False, "mq": marquee, "show": show,
                "standin": bool(standin),
                "coverpick": x["id"] in up_cover,
                "coveronly": (x["id"] in up_cover
                              and not (slots or show or standin)),
                "showcase": False, "opener": False, "bfri": False,
                "kickoff": False, "suffix": None, "rivals": False,
                "rivals_only": False, "rival_loss": False, "big": [],
                "upcoming": True,
                "michigan": mich, "mx": {} if mich else None})
            if not mich:
                keep[-1].pop("mx", None)
                keep[-1].pop("michigan", None)
            added += 1
    print("  %d upcoming games (%s to %s)" % (added, start, end))

    # COLLEGE HOCKEY, team by team (2026-09-16)
    hk, hk_miss = hockey_games(rules.MICHIGAN, sorted(rules.MICHIGAN_SEASONS["CHK"]),
                               teams, latest_conf, start, end)
    keep += hk
    print("  hockey: %d Michigan games, %d with a USCHO rank on either side"
          % (len(hk), sum(1 for g in hk if any(t["rank"] for t in g["teams"]))))
    ck, _ = hockey_games(rules.CORNELL, sorted(rules.CORNELL_SEASONS["CHK"]),
                         teams, latest_conf, start, end)
    keep += ck
    rv = hockey_rival_games(sorted(rules.MICHIGAN_SEASONS["CHK"]), teams, latest_conf, start, end)
    keep += rv
    print("  hockey rivals: %d NCAA Tournament losses" % len(rv))
    lg = lions_games(teams, start)
    keep += lg
    pg = pro_games(teams, start)
    keep += pg
    tg = tigers_games(teams, start)
    keep += tg
    print("  Tigers: %d games (%d walk-offs, %d extra innings, %d no-hitters, %d playoff)" % (
        len(tg), sum(1 for g in tg if g["mx"].get("walkoff") or g["mx"].get("late")),
        sum(1 for g in tg if g["mx"].get("extra")), sum(1 for g in tg if g["mx"].get("nohit")),
        sum(1 for g in tg if g["post"])))
    print("  Tigers 9th-inning comebacks: %d already shown, %d more not shown; by year %s" % (
        sum(1 for g in tg if g["mx"].get("late")), len(LATE_ONLY),
        dict(collections.Counter(d[:4] for d in LATE_ONLY))))
    print("  Red Wings / Pistons / Cavaliers: %s games" % collections.Counter(
        g["focus"] for g in pg).most_common())
    print("  Lions: %d games, %d Key Games" % (len(lg), sum(1 for g in lg if g["mx"].get("key"))))
    cb = cornell_cbb_games(sorted(rules.CORNELL_SEASONS["CBB"]), teams, latest_conf)
    keep += cb
    print("  Cornell: %d hockey games, %d basketball tournament games" % (len(ck), len(cb)))
    for g in keep:
        if g.get("michigan") and not g.get("focus"):
            g["focus"] = rules.MICHIGAN

    # ESPN RECORDS A FEW GAMES TWICE, under two event ids -- Michigan-
    # Pittsburgh on 2012-11-21 and Michigan-West Virginia on 2012-12-15, each
    # with identical date, tip and score. They were double-counted and threw
    # the game numbers off by two from that point in 2012-13. The copies carry
    # DIFFERENT details (one has the networks, the other the event or venue),
    # so they are merged rather than dropped, and the id that his tags.json
    # already knows is the one kept (2026-09-13).
    tagged = set()
    tpath = os.path.join(HERE, "docs", "tags.json")
    if os.path.exists(tpath):
        tagged = set(json.load(open(tpath, encoding="utf-8")))
    seen, merged = {}, 0
    deduped = []
    for g in keep:
        sig = (g["sport"], g["date"], g["time"], g.get("focus"),
               frozenset(t["id"] for t in g["teams"]))
        if sig not in seen:
            seen[sig] = g
            deduped.append(g)
            continue
        first = seen[sig]
        # the richer copy of each field wins; a tagged id beats an untagged one
        if g["id"] in tagged and first["id"] not in tagged:
            first["id"], g["id"] = g["id"], first["id"]
        for k, v in g.items():
            if k in ("id", "teams", "mx"):
                continue
            if not first.get(k) and v:
                first[k] = v
        if g.get("nets") and len(g["nets"]) > len(first.get("nets") or []):
            first["nets"] = g["nets"]
        merged += 1
    if merged:
        print("  merged %d duplicate game(s) ESPN listed twice" % merged)
    keep = deduped

    keep.sort(key=lambda g: (g["date"], g["time"]))
    # game numbers for the Michigan view, as his sheet writes them (his call
    # 2026-09-11, both sports): nc1, nc2 ... for non-conference games and g1,
    # g2 ... for conference games, regular season only -- no number for a
    # conference championship or tournament game or the postseason. A
    # non-conference game against a POWER team, or Notre Dame, capitalises its
    # prefix -- NC3 -- so the games that matter stand out from the buy games.
    count = collections.Counter()
    for g in keep:
        focus = g.get("focus")
        if focus and not g["post"] and not g["champ"] and g["sport"] in ("CFB", "CBB"):
            key = (focus, g["sport"], g["season"], len({t["conf"] for t in g["teams"]}) == 1)
            count[key] += 1
            if key[3]:
                g["mx"]["num"] = "g%d" % count[key]
            else:
                opp = next((t for t in g["teams"] if t["id"] != focus), None)
                big = (opp is not None and g["sport"] in rules.POWER_CONF_IDS
                       and rules.nc_power(g["sport"], g["season"], opp["id"],
                                          opp.get("conf")))
                g["mx"]["num"] = ("NC%d" if big else "nc%d") % count[key]
    hockey_numbers(keep, teams)
    # HIS SHEET, laid over the top (2026-09-13). Per FIELD, and per season: a
    # column he has not touched for that season leaves the existing rule alone,
    # so basketball keeps its capitals and washes until he marks them.
    sheet, sheet_used = load_sheet()

    def sheet_case(g):
        """His CASE column, or None where he has not said (2026-09-14).

        This used to INFER the answer from whether his opponent cell was
        written in capitals, which cannot tell "capitalise this" from a school
        whose name IS an acronym -- it broke on UNLV and again on VCU. He now
        says so in a column of its own, so nothing is guessed.
        """
        row = sheet.get((g.get("focus"), g["sport"], g["season"], g["date"]))
        if not row:
            return None
        said = (row.get("case") or "").strip().upper()
        if not said:
            return None                 # blank leaves app.js's own scopes alone
        return "Y" if said == "UPPER" else "N"

    hits = 0
    for g in keep:
        if not g.get("focus"):
            continue
        row = sheet.get((g["focus"], g["sport"], g["season"], g["date"]))
        if not row:
            continue
        hits += 1
        flags = sheet_used.get((g["focus"], g["sport"], g["season"]), set())
        mx = g.setdefault("mx", {})
        case = sheet_case(g)
        if case:
            mx["caps"] = case
        if "attended" in flags:
            mx["attended"] = row["attended"]
        if "shade" in flags:
            mx["shade"] = row["shade"]
        if "border" in flags:
            mx["border"] = row["border"]
        if "note" in flags:
            mx["note"] = row["note"]
        if "footer" in flags:
            mx["footer"] = row["footer"]
        if "jersey" in flags:
            mx["jersey"] = row["jersey"]
        if "box" in flags:
            box = {k: v for k, v in row["box"].items() if v}
            if box:
                mx["box"] = box
        g["mx"] = {k: v for k, v in mx.items() if v not in (None, "", {}, [])}
    print("  sheet matched %d Michigan games" % hits)

    # THE PRESEASON TOURNAMENT (his call 2026-09-13): a NOVEMBER neutral-site
    # event Michigan played more than once. That picks out exactly one per
    # season -- Maui, Battle 4 Atlantis, the Legends Classic and the rest --
    # and leaves the one-off neutral games alone, which is what separates a
    # tournament from a showcase.
    pre = collections.defaultdict(list)
    for g in keep:
        if (g.get("michigan") and g["sport"] == "CBB" and g.get("neutral")
                and g["date"][5:7] == "11"):
            key = (g["season"], g.get("event") or g.get("city")
                   or g.get("venue") or "?")
            pre[key].append(g)
    n = 0
    for key, games in pre.items():
        if len(games) < 2:
            continue
        for g in games:
            g["preseason"] = True
            n += 1
    print("  %d preseason-tournament games across %d seasons"
          % (n, sum(1 for v in pre.values() if len(v) > 1)))

    print("  %d stand-ins (SEC on CBS 2021-22, Big Ten hosts on broadcast)"
          % sum(1 for g in keep if g.get("standin")))

    # POWER FOUR/FIVE COVERAGE (his call 2026-09-15). A cover is added only
    # where the week's ordinary rules left a conference off TV Windows, and
    # that cannot be known until every game in the week has been decided. So
    # each candidate is admitted above and judged here: the ones whose
    # conference turned out to be shown already are withdrawn.
    champ_wk = {y: w for y, w in cover_last.items() if w}
    # a season still being played has no championship week yet: cover only the
    # weeks that have actually been played
    played = {}
    for g in keep:
        if g["sport"] == "CFB" and not g.get("upcoming") and g.get("week"):
            played[g["season"]] = max(played.get(g["season"], 0), g["week"])
    def _on_tv(g):
        """The TV Windows filter of app.js, in Python. A game kept only for its
        game TYPE is on Key Games, NOT here -- counting those as coverage was
        the other half of the 2026-09-15 miss."""
        return not g.get("rivals_only") and bool(
            g.get("slots") or g.get("title") or g.get("bfri") or g.get("show")
            or g.get("opener") or g.get("showcase") or g.get("kickoff")
            or g.get("standin"))

    def _covered_by(g):
        """The conferences this game puts on TV Windows."""
        h = next((k for k in g["teams"] if k.get("home")), None)
        a = next((k for k in g["teams"] if not k.get("home")), None)
        if not h or not a:
            return set()                  # a neutral game covers nobody
        nets = set(g.get("nets") or ())
        return {q for q in COVER_CONFS
                if covers(q, h.get("conf"), a.get("conf"), nets)}
    covered = set()
    for g in keep:
        if (g["sport"] != "CFB" or g.get("coveronly")
                or g.get("week") in (None, 0) or not _on_tv(g)):
            continue
        if g["week"] >= champ_wk.get(g["season"], 99):
            continue
        for q in _covered_by(g):
            covered.add((g["season"], q, g["week"]))
    kept_cover, dropped = [], 0
    for g in sorted((x for x in keep if x.get("coveronly")),
                    key=lambda x: (x["season"], x["week"], x["date"])):
        slot = cover_slot.get(g["id"])
        if not slot or slot in covered:
            dropped += 1
            g["drop_cover"] = True
            continue
        covered |= {(g["season"], q, g["week"]) for q in _covered_by(g)} | {slot}
        g["standin"] = True
        kept_cover.append(g)
    trimmed = []
    for g in keep:
        if g.pop("drop_cover", False):
            # A withdrawn candidate keeps whatever OTHER place it had: Key
            # Games if it has a game type, the Michigan view or Rivals if it
            # is one of those. Only a game with no other claim at all goes.
            if g.get("type"):
                trimmed.append(g)
            elif g.get("michigan") or g.get("rivals"):
                g["rivals_only"], g["mq"] = True, False
                trimmed.append(g)
            continue
        trimmed.append(g)
    keep = trimmed
    for g in keep:
        g.pop("coveronly", None)
        # the surviving covers are `standin` like any other window-less game;
        # the candidate flag itself is of no use to the page
        g.pop("coverpick", None)
    print("  %d conference covers added, %d withdrawn as already shown"
          % (len(kept_cover), dropped))
    # the gaps: a conference-week that nothing on the three tiers could fill
    CONF_NAME = {"1": "ACC", "4": "Big 12", "5": "Big Ten", "8": "SEC",
                 "9": "Pac-12"}
    gaps = []
    for yr in sorted(set(champ_wk) | set(played)):
        last = min(champ_wk.get(yr, 99), played.get(yr, 0) + 1)
        for q, span in sorted(COVER_CONFS.items()):
            if not (span[0] <= yr <= span[1]):
                continue
            for w in range(1, last):
                if (yr, q, w) not in covered:
                    gaps.append((yr, CONF_NAME[q], w))
    if gaps:
        print("  %d conference-weeks still empty: %s"
              % (len(gaps), ", ".join("%d %s wk %d" % g for g in gaps)))
    io.open(os.path.join(OUT, "cover-added.txt"), "w", encoding="utf-8").write(
        "\n".join("%d\twk %s\t%s\t%s\t%s\t%s" % (
            g["season"], g["week"], g["date"], g["time"],
            "/".join(g["nets"]),
            " at ".join(teams[k["id"]]["short"] for k in
                        sorted(g["teams"], key=lambda k: k["home"])))
            for g in kept_cover) + "\n")

    # THE SERIES TAG (his call 2026-09-14), worked out rather than typed: two
    # meetings in CONSECUTIVE seasons that the two schools arranged between
    # them. A conference opponent is annual, a tournament meeting is the
    # bracket's doing, an MTE is the event's, and a Big Ten/ACC Challenge or
    # Gavitt game is the leagues' -- none of those is a series, and he tags
    # none of them. tags.json still overrides this per game.
    cand = collections.defaultdict(list)
    for g in keep:
        if not g.get("michigan") or g.get("stage") or g.get("preseason"):
            continue
        if g.get("event"):
            continue
        opp = next((s for s in g["teams"] if s["id"] != rules.MICHIGAN), None)
        if not opp or opp.get("conf") == rules.BIG_TEN[g["sport"]]:
            continue
        cand[(g["sport"], opp["id"])].append(g)

    def _side(g):
        opp = next(s for s in g["teams"] if s["id"] != rules.MICHIGAN)
        return ("neutral" if g.get("neutral")
                else "away" if opp.get("home") else "home")

    series = 0
    for games in cand.values():
        games.sort(key=lambda x: x["date"])
        for i, a_ in enumerate(games):
            for b_ in games[i + 1:]:
                if b_["season"] - a_["season"] != 1:
                    continue
                ka, kb = _side(a_), _side(b_)
                if ka == "neutral" and kb == "neutral":
                    lab = "Neutral & Neutral"
                elif {ka, kb} == {"home", "away"}:
                    lab = "Home & Home"
                else:
                    # a MATCHED pair or nothing: two homes, two aways, or one
                    # home and one neutral is coincidence, not a contract
                    continue
                for g in (a_, b_):
                    if not g.get("series"):
                        g["series"] = lab
                        series += 1
    print("  %d games in a home-and-home style series" % series)

    # THE ROUND INSIDE THE EVENT (his call 2026-09-14). He asked whether he had
    # to type these in; he does not -- an MTE bracket is fixed, so the round
    # falls out of the ORDER of Michigan's games and whether it won them.
    #   three games = an eight-team bracket, two = a four-team one
    # His Round column still wins wherever he disagrees (see michCard).
    for key, games in pre.items():
        if len(games) < 2:
            continue
        games.sort(key=lambda x: x["date"])
        won = [any(t["id"] == "130" and t["win"] for t in g["teams"])
               for g in games]
        if len(games) >= 3:
            # the Players Era Festival is POOL PLAY into one placement game,
            # not a bracket -- the only such event he has played
            pool = "Players Era" in (games[0].get("event") or "")
            rounds = ["Game 1" if pool else "Quarters",
                      "Game 2" if pool else ("Semifinals" if won[0] else "Consolation"),
                      "Final" if won[0] and won[1]
                      else "3rd Place" if won[0]
                      else "5th Place" if won[1] else "7th Place"]
        else:
            rounds = ["Semifinals", "Final" if won[0] else "3rd Place"]
        for g, r in zip(games, rounds):
            g["mte_round"] = r

    # HIS LOCATIONS TAB decides which games carry a show chip (2026-09-13).
    # One host name per date is enough: no team plays twice in a day. A late
    # kickoff shifts the Eastern date, so the day either side is tried too.
    by_date = {}
    for g in keep:
        by_date.setdefault((g["sport"], g["date"]), []).append(g)
    hit = miss = 0
    for (code, day), shows in sorted(locs.items()):
        for tag, who in shows.items():
            want = norm(who)
            found = None
            for probe in (day, _shift_day(day, -1), _shift_day(day, 1)):
                for g in by_date.get((code, probe), []):
                    if any(norm((teams.get(t["id"]) or {}).get("short") or "")
                           == want for t in g["teams"]):
                        found = g
                        break
                if found:
                    break
            # he does not want the shows on postseason games
            if found is None or found.get("post") or found.get("champ"):
                miss += 1
                continue
            found.setdefault("shows", [])
            if tag not in found["shows"]:
                found["shows"].append(tag)
            hit += 1
    print("  locations matched %d shows (%d unmatched or postseason)" % (hit, miss))

    # SEEDS SET BY HAND in game-overrides.json ("seeds": {team id: seed}) --
    # the 2023 NIT, which ESPN seeds nowhere (his call 2026-09-18)
    for g in keep:
        sd = game_over.get(g["id"], {}).get("seeds") or {}
        for t in g["teams"]:
            if t["id"] in sd:
                t["seed"] = sd[t["id"]]
    for (code, tid), (_, conf) in latest_conf.items():
        if tid in teams:
            teams[tid].setdefault("conf", {})[code] = conf
    for tid, nm in rules.DISPLAY_BY_ID.items():
        if tid in teams:
            teams[tid]["short"] = nm
    os.makedirs(OUT, exist_ok=True)
    json.dump({"games": keep, "teams": teams, "order": rules.ORDER,
               "window_net": rules.WINDOW_NET,
               "hidden_windows": rules.HIDDEN_WINDOWS,
               "header_tint": rules.HEADER_TINT, "net_tint": rules.NET_TINT,
               "big_ten": rules.BIG_TEN, "season_names": rules.SEASON_NAMES,
               "team_conf": {"172": rules.CORNELL_CONF},
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
