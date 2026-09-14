"""Fetch every past CFB/CBB game matching rules.py and freeze it to JSON.

Past games never change, so this runs once per new week of games -- there is
no daily build and nothing goes stale. `cache/` holds raw ESPN responses so a
re-run is free.
"""
import collections, csv, datetime as dt, io, json, os, re, sys, time
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


def fetch(sport, params, key, cacheable=True):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, key + ".json")
    if cacheable and os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    d = get_json(f"{BASE}/{sport}/scoreboard", params=params)
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
                out[k["team"]["id"]] = rules.FINISH_SHORT.get(rnd, rnd or "Playoff")
    return out


SHEET_ID = "1yLrd2BOhtLqS0YZLGBlBlDiypMhGjNJ5nw8fVs1nZu0"
SHEET_TABS = {"CFB": "Michigan CFB", "CBB": "Michigan CBB"}


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
    out, used = {}, {}
    for code, tab in SHEET_TABS.items():
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
            if season is None or date is None:
                continue
            box = {"score_bg": cell("score bg"), "score_font": cell("score font"),
                   "rank_bg": cell("rank bg"), "rank_font": cell("rank font")}
            out[(code, season, date)] = {
                "name": cell("opponent"), "attended": bool(cell("attended")),
                "shade": bool(cell("shade")), "border": cell("border"),
                "note": cell("notes") or cell("note"),
                "footer": cell("footer"), "box": box,
                # the round inside a multi-team event ("Final", "Semis"), from
                # a Round column he may not have added yet -- "" until he does
                "round": cell("round"),
            }
            flags = used.setdefault((code, season), set())
            for label, flag in (("attended", "attended"), ("shade", "shade"),
                                ("border", "border"), ("notes", "note"),
                                ("note", "note"), ("footer", "footer"),
                            ("round", "round")):
                if cell(label):
                    flags.add(flag)
            if any(box.values()):
                flags.add("box")
    print("  sheet: %d rows across %d season-sports" % (len(out), len(used)))
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
    key = flat((teams.get(team_id) or {}).get("short") or "")
    hit = ratings.get((code, season, key))
    if hit:
        return hit
    if key and code in rated_teams and key not in rated_teams[code]:
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
    locs = load_locations()
    ev_overrides = load_event_overrides()
    game_over = load_game_overrides()
    ratings, rated_teams = load_ratings()
    seeds = load_seeds()
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
                        both_big_ten=all(q == bt for q in confs))
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
                # every Michigan game in a Michigan-view season is kept, whatever
                # else is true of it
                if not normal and not rivals and not mich:
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
                                 "rank": rank_of(k) or (ap.get(t["id"]) if rivals_only else None),
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
                    "header": (rules.cfb_header(card_slots, d, forced,
                                                season=y, week=week_no)
                               if code == "CFB" else suffix),
                    "slots": sorted(slots), "type": gtype,
                    "champ": conf, "round": head, "title": title,
                    # an override KEY that is present wins even when empty --
                    # "" means show nothing, which `or` could not express
                    "event": (game_over[x["id"]]["event"]
                              if "event" in game_over.get(x["id"], {}) else event),
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
        for x in upcoming_events(code, start, end):
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
            if not (start <= d.date() <= end):
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
                             "conf": str(t.get("conferenceId")), "seed": None})
            if len(side) != 2:
                continue
            mich = any(s["id"] == rules.MICHIGAN for s in side)
            heads = [n.get("headline") or "" for n in (c.get("notes") or [])]
            wk = (x.get("week") or {}).get("number")
            bt_code = rules.BIG_TEN[code]
            confs = [s["conf"] for s in side]
            ids = {s["id"] for s in side}
            ranked = any(s["rank"] for s in side)
            if code == "CFB":
                slots = rules.cfb_slots(nets, d, y, ids, set(confs))
            else:
                slots = rules.cbb_slots(nets, d, all(q == bt_code for q in confs),
                                        ranked, bt_code in confs)
            if not slots and not mich:
                continue          # nothing to show it under on TV Windows
            v = c.get("venue") or {}
            keep.append({
                "id": x["id"], "sport": code, "season": y,
                "date": d.strftime("%Y-%m-%d"), "dow": rules.DOW[d.weekday()],
                "time": d.strftime("%H:%M"), "neutral": bool(c.get("neutralSite")),
                "nets": sorted(nets), "teams": side, "week": wk,
                "slots": sorted(slots), "type": None, "champ": None,
                "round": (heads[0] if heads else None), "title": False,
                "header": (rules.cfb_header(sorted(slots), d, season=y, week=wk)
                           if code == "CFB" else None),
                "venue": v.get("fullName"),
                "city": rules.display_city((v.get("address") or {}).get("city"),
                                           v.get("fullName")),
                "post": False, "event": None, "bowl": None, "offsite": None,
                "stage": None, "ot": False, "mq": False, "show": None,
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
        sig = (g["sport"], g["date"], g["time"],
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
        if g.get("michigan") and not g["post"] and not g["champ"]:
            key = (g["sport"], g["season"], len({t["conf"] for t in g["teams"]}) == 1)
            count[key] += 1
            if key[2]:
                g["mx"]["num"] = "g%d" % count[key]
            else:
                opp = next((t for t in g["teams"] if t["id"] != rules.MICHIGAN), None)
                big = opp is not None and rules.nc_power(
                    g["sport"], g["season"], opp["id"], opp.get("conf"))
                g["mx"]["num"] = ("NC%d" if big else "nc%d") % count[key]
    # HIS SHEET, laid over the top (2026-09-13). Per FIELD, and per season: a
    # column he has not touched for that season leaves the existing rule alone,
    # so basketball keeps its capitals and washes until he marks them.
    sheet, sheet_used = load_sheet()

    def sheet_case(g):
        """His column C as a CASE instruction, or None when it says nothing.

        Only meaningful where MY name is not itself an acronym: "UNLV" against
        my "Unlv" is a real signal, "UCLA" against my "UCLA" is not -- ESPN
        writes those in capitals whatever he intends.
        """
        row = sheet.get((g["sport"], g["season"], g["date"]))
        if not row:
            return None
        opp = next(t["id"] for t in g["teams"] if t["id"] != rules.MICHIGAN)
        mine = (teams.get(opp) or {}).get("short") or ""
        if not mine or mine == mine.upper():
            return None
        core = re.sub(r"^(at |vs\. )", "", row["name"]).strip()
        letters = [c for c in core if c.isalpha()]
        if not letters:
            return None
        return "Y" if all(c.isupper() for c in letters) else "N"

    # CAPITALS ARE PER SEASON, like every other column: a season he has not
    # marked keeps the rules it has (the championship scopes in app.js).
    # Without this gate every unmarked row read as "not capitals" and the
    # basketball seasons lost all 85 of theirs (caught 2026-09-13).
    caps_seasons = {(g["sport"], g["season"]) for g in keep
                    if g.get("michigan") and sheet_case(g) == "Y"}
    hits = 0
    for g in keep:
        if not g.get("michigan"):
            continue
        row = sheet.get((g["sport"], g["season"], g["date"]))
        if not row:
            continue
        hits += 1
        flags = sheet_used.get((g["sport"], g["season"]), set())
        mx = g.setdefault("mx", {})
        if (g["sport"], g["season"]) in caps_seasons:
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
                      "Game 2" if pool else ("Semis" if won[0] else "Con"),
                      "Final" if won[0] and won[1]
                      else "3rd Place" if won[0]
                      else "5th Place" if won[1] else "7th Place"]
        else:
            rounds = ["Semis", "Final" if won[0] else "3rd Place"]
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
