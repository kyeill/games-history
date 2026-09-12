# Traps

Each of these cost a debugging pass or would have. Do not rediscover them.

## ESPN data

**Sponsor names are inside the championship headline, and the suffix moves
year to year.** `Subway ACC Championship Game` (2021) → `Subway ACC
Championship` (2022) → `ACC Championship` (2024); `New York Life ACC
Tournament` (2021) → `T. Rowe Price ACC Tournament` (2025); `Dr Pepper Big 12
Championship` every year. Matching on a prefix reported **zero** Power Five
championship games in 2021 and 2022 — a silent, plausible-looking wrong answer.
Substring on the conference name is the only thing that holds, and `FCS
Championship` has to be excluded explicitly. See `rules.power5_title`.

**`conferenceId` is historical, not current.** ESPN returns USC as Pac-12 (9)
in 2021 and Big Ten (5) in 2025. This is the *good* case and worth knowing:
the Big Ten rules do not retroactively credit USC, UCLA, Oregon and Washington
games from before 2024. Big Ten is **5 in football and 7 in basketball**.

**CBB 404s on a wide date range and silently caps at 1,000 events.** A whole
season returns 0 events; a single month returns exactly 1000, truncated with no
error. `harvest.py` walks CBB a week at a time and warns on the cap. CFB
accepts a four-month range fine. The Browse tab hits the same cap and says so.

**Broadcast coverage thins going back, badly.** CFB is ~90-100% from 2015 and
~50% in 2008-2010. CBB is **zero before 2011-12**, 31% in 2012, 50% in 2018,
100% by 2024. This is what bounded the project at 2021. Do not read a missing
network as a data error in the early seasons — 2021-22 CBB is 22% blank.

**Some old events carry no `competitions` block at all.** A 2001 CFB fetch
raised `KeyError: 'competitions'` on one event. Guard it.

**Before 2021, basketball headlines are in CAPITALS.** "BIG TEN MEN'S
TOURNAMENT - QUARTERFINAL", "MEN'S BASKETBALL CHAMPIONSHIP - EAST REGION -
SWEET 16", "STATE FARM CHAMPIONS CLASSIC"; from 2021 they are mixed case.
Every test that looked for "Tournament", "hampionship" or "- Final" missed the
old ones, so the pre-2021 Big Ten Tournament games on Rivals had no stage
header, no Big Ten border and the raw headline as their chip (found by him
2026-09-11). `is_championship`, `power5_title` and `is_title_game` are now
case-blind -- the conference matched as a whole word, since capitals would let
"SEC" hide inside other words -- and `event-overrides.json` is looked up
case-blind too, which is what finally matched the old Champions Classic and
the "Presented by" / "presented by" Jimmy V variants.

**Before 2021 an event name can't earn its place by size.** The chip keeps an
event name only when more than two teams played under it that season, but the
pre-2021 caches hold only Ohio State, Michigan State and Notre Dame games, so
the count almost never passes two and the city shows instead -- the 2014, 2016
and 2017 CBS Sports Classic games read United Center, Las Vegas and New
Orleans. An `event-overrides.json` entry forces the name whatever the count;
"CBS Sports Classic" is there now (which also names the 2021 edition, a single
game after the COVID cancellation).

**Most one-off event names read better as the city** (his review of every
basketball chip, 2026-09-11). `event-overrides.json` now forces the city for
PK80, Phil Knight Invitational and Legacy, the Basketball Hall of Fame London
Showcase, Milwaukee Hoops Showdown, Orlando Classic, Legends of Basketball
Showcase, Las Vegas Clash, Holiday Hoopsgiving, Hall of Fame Tip-Off and the
CBS Sports Thanksgiving Classic. Champions Classic and CBS Sports Classic keep
their name AND add the place as a second chip (`PLACE_TOO` in app.js), since
both move every year. The New York / Los Angeles / Chicago arena rule has one
exception, `rules.CITY_NOT_VENUE`: Credit Union 1 Arena reads Chicago. A
game with an event forced to the city still shows the ARENA when that city is
one of those three metros -- the Thanksgiving Classic reads United Center.
Detroit joined those metros (his call 2026-09-11), so Little Caesars Arena
and Ford Field show by name, and Uncasville reads "Connecticut"
(`rules.CITY_OVERRIDES`) -- nobody knows where Mohegan Sun Arena is by town.

**Rank 99 means unranked**, not 99th. `curatedRank.current` is 99 for everyone
outside the poll, and the ranks are the poll on the day of the game.

**Historical point spreads are gone.** `pickcenter` is empty on every finished
game, including recent ones; `odds` is `[]`; `againstTheSpread` is season ATS
records, not the game line. So "upset" has to mean a ranking gap. Win
probability curves *do* survive (154 points on 2024 Michigan-Ohio State) and
would support computed comeback/thriller tags — Kyle declined those, so nothing
fetches the summary endpoint today.

**Attendance is 0 before about 2010** even where the game exists.

## Rules

**Top-10 vs top-10 is not an upset.** Two of the four "upset" rules Kyle gave
are marquee-matchup rules. The tab is named Key Games for that reason.

**Peacock on its own is a firehose.** 246 games, including Alcorn State at
Minnesota 95-50 and Providence vs George Washington. It carries every Big Ten
home non-conference game. Narrowed to Big Ten vs Big Ten, Tue/Thu, one ranked
team: 39.

**Power Five finals were already in the archive.** Restricting the P5 rule to
finals only adds **9 net new games across five seasons**, because a conference
final is on CBS with ranked teams and the slot and big-game rules already catch
it. All-rounds adds 256. Kyle chose all rounds, so the addition is really the
early rounds.

## Colours and crests

**A wash and a stripe want different colours.** sports-daily and standings use
maize `#ffcb05` for Michigan because it is drawn as a stripe. Lightened into a
row wash, maize is nearly the page's ink. This project keeps ESPN's navy and
deliberately does **not** read the shared `Colors` sheet tab.

**Nine schools return `#000000` as their primary** (Appalachian State, Army,
Bryant, Cincinnati, Davidson, Milwaukee, Providence, UCF, Vanderbilt) and would
all wash to the same grey. `colors.py` falls back to the ESPN alternate when a
primary is *both* dark and desaturated — which also correctly catches Iowa's
`#231f20` and yields the gold sports-daily already uses. Navy is dark but has
real hue, so it survives the test.

**Two ESPN colours are simply wrong**: Syracuse `#000e54` (navy; the school is
orange `#f76900`) and Texas `#af5c37` (a muddy tan, not burnt orange
`#bf5700`). Keep this list short — a rule needing many exceptions is the wrong
rule.

**The naive `/500/` → `/500-dark/` swap is wrong** for 25 of the 150 teams,
whose dark crest is a flat white silhouette. `logos.py` measures the actual
pixels of both variants. Ported from sports-daily; its two imports (`espn`,
`sports_daily`) are made optional here because this project takes its team list
from the harvest, not a config.

**Game types differ by sport and are not interchangeable.** CFB uses Top 10
Upsets / Ranked Upsets / Ranked Games; CBB uses Top 5 Upsets / Top 10 Games /
Ranked Big Ten. The two sets share no values, and neither do their TV windows.
So the app's dropdowns are rebuilt from the games the sport toggle leaves in
scope, and switching sport **clears** the game-type and TV-window filters —
without that, a CFB value left set while viewing CBB filters everything away
and the page looks broken rather than empty-by-choice.

**Every game in the archive must be REACHABLE from a view.** A game qualifies
by a TV window, a game type, a Black Friday flag or a manual override -- and
being a conference-tournament game is NOT one of them. It used to be, and it
held 265 early-round basketball games that Key Games showed but nobody wanted
and TV Windows could not reach at all. Check `not type and not slots and not
bfri` after any rule change: it should be zero.

**ESPN publishes NO RANKINGS for conference tournament games** in the early
seasons -- 0 of 600 in 2021-22, 0 of 302 in 2022-23, and only ~13% from
2023-24. Auburn reads unranked in the 2022 SEC tournament six weeks after being
#1. Any rule that judges a tournament game on rank is therefore unreliable,
which is part of why non-final tournament games are excluded outright.

**Non-final conference tournament and playoff games are OUT of the archive
entirely**, both tabs. Only Power SIX finals survive (basketball adds the Big
East; the AAC is deliberately excluded). That also drops mid-major conference
finals that held a real TV window -- the MVC final on CBS, the WCC final on
Super Tuesday, the Atlantic 10 final.

**"Championship" in an event name does NOT mean a conference tournament.**
The Baha Mar Championship is a November showcase, and excluding it cost a real
Purdue-Texas Tech game. Basketball conference tournaments are a MARCH thing, so
the exclusion is gated on the month -- and note `d.month >= 3` is WRONG, since
November is 11: it must be `in (3, 4)`.

**The Jan-Mar limit is on the TV WINDOWS only.** Key Games spans every month,
which is how the November showcases (Champions Classic, Players Era, Fort Myers
Tip-Off) stay in.

**The Big Ten Tournament is excluded from "Ranked Big Ten" before its Final.**
A ranked-v-ranked quarterfinal otherwise lands in a category meant for
regular-season meetings. Those games are NOT removed from the archive -- they
keep their conference-tournament billing and their blue chip, and stay
reachable under "All Game Types". 83 -> 75.

**The upset categories must be tested before the ranked-v-ranked ones.**
"Anyone beats #1" and "top-10 v top-10 with the worse rank winning" both match
a #2-over-#1 result; Kyle wants it read as an upset.

## The app

**GitHub's REST API is CORS-open**, including `PUT` with an `Authorization`
header from any origin (`Access-Control-Allow-Origin: *`, `access-control-
allow-methods` lists PUT). Verified 2026-09-09. This is what makes tagging from
a static Pages site possible at all.

**ESPN's API is CORS-open too**, which is what lets Browse query it live rather
than shipping ~35,000 games.

**A save must re-read `tags.json` before writing it.** Otherwise a phone with
stale state clobbers what the laptop saved. `save()` GETs the file, merges
PENDING over the remote copy, and PUTs with the returned `sha`.

**`tags.json` must never be served from cache.** It is the shared state; the
service worker skips it and the fetch is `no-store`. GitHub Pages sends
`index.html` with `max-age=600`, so the service worker cache name carries the
build timestamp and navigations are `no-store` — the same fix standings needed.

**An explicit `<link rel="icon">` is required.** The manifest covers only the
*installed* icon; without the link the browser asks for `/favicon.ico`, 404s,
and the tab shows a blank globe. `purpose: "any maskable"` is what makes the
installed icon crop to the launcher's own shape.

**`localStorage` can throw**, not just return null — a locked-down browser
raises on the accessor itself. Every read and write is wrapped.

**`docs/` is both the build output AND the repo folder**, so `docs/tags.json`
is its own source. `site.py` seeds it once and must never copy over it — an
earlier version tried to, which raised `SameFileError` and would otherwise have
wiped every tag on the next build. Nothing else in `docs/` is hand-edited;
everything but `tags.json` is regenerated.

**The Key Games exclusions live in the APP, not the harvest.** Michigan losses
and rival wins stay in `games.json` because the TV Windows view still shows
them — filtering them at harvest time would lose them from both.

**TV window and game type names are HIS, and `rules.ORDER` owns both the names
and the sequence.** Renaming a window changes the values stored in
`games.json`, so a rename needs a re-harvest — cheap, since `cache/` holds
every response. Tag keys are game ids, so tags survive a rename untouched.

**Border colour is normalised by LUMINANCE, not by a lighten factor.** One
fixed factor cannot serve both: it left Penn State's navy muddy and turned
Indiana's red pink. `brighten()` solves for the blend that hits a target
luminance, which is exact because luminance is linear in the blend factor.

**`clearFilters` must be a function declaration, not a `const`.** `init()`
calls it well above its position in the file; as a `const` arrow it sat in the
temporal dead zone and threw.

**The celebrate border colour MUST come from a CSS variable.** The rule
originally hardcoded maize, so the per-team colours app.js computed were never
applied and every flagged row looked like a Michigan win -- and it looked
correct, because most flagged rows ARE Michigan wins. Verified by reading
`getComputedStyle(row).borderTopColor`, not by reading the function that
returns the colour: testing the helper proves nothing about what renders.

**The TV window filter holds a LIST, not a value.** Marquee Windows selects
three at once. The dropdown writes a one-element list and falls back to its
"All" label whenever the selection is not exactly one, so the marquee state is
shown by its own lit button rather than by the dropdown.

**ESPN's `broadcasts` lists simulcasts and streams, not just the broadcaster.**
"NBC, Peacock", "CBS, Paramount+", "ESPN, ESPN+", "ESPN, ESPN3". Only one is
wanted on the row, and picking the first alphabetically is wrong (BTN sorts
before FOX), so `primaryNet()` ranks the majors explicitly. The full list stays
in `games.json` -- this is display only, and the slot RULES still read every
network, which is what lets "NBC, Peacock" match the NBC window.

**A "home" game is not always at home, and ESPN will not tell you.** Michigan
at Northwestern 2025 was played at Wrigley Field; `neutralSite` is false,
because Northwestern really was the host. The only signal is the venue field,
so `offsite_games()` counts each home team's venues per season and flags the
rare one.

The cutoff is ABSOLUTE -- at most two games at that venue -- not a percentage,
and that is the whole difficulty. Several teams keep a genuine second home
floor: UConn splits Gampel and Hartford 8/9, Villanova plays 5 of 14 downtown,
St John's a quarter of its home games at Madison Square Garden, Kansas 4 of 20
in Kansas City. None of those deserve a chip. But Wrigley was 2 of
Northwestern's 7 home games -- 29% -- so any percentage loose enough to catch
it also catches every one of those second homes. The absolute cutoff splits
them cleanly: measured across the archive it keeps exactly six games (Wrigley,
Ford Field, MSG twice for Rutgers, Spokane Arena, Delta Center) and drops
every second home floor.

Counted per season, because "usual" moves -- Northwestern's usual venue was
the temporary lakefront stadium in 2025 and Ryan Field again in 2026, and the
rule follows without being told. Two guards protect an in-progress season,
where a team may not have played enough home games for "usual" to mean
anything: the usual venue must have strictly more games, and the team must
have at least four home games on record.

**Basketball's TV tab is January to March, ride-alongs included.**
`cbb_slots` already returns nothing outside those months, but a College
GameDay game is admitted to the TV tab on `show` with no window of its own,
and two November 2025 games were reaching Marquee that way. The filter is now
applied to the CBB TV list as a whole. Key Games still carries every month --
that split is his standing rule.

**`event.week.number` is on every CFB event** (weeks 1-16, zero missing across
all five seasons). Basketball has one too but it means nothing to a viewer, so
only football renders it.

**Three across needed padding, not content.** The desktop list went from two
columns to three at 1240px by taking width off the card's side padding, the
gutter to the meta column and the meta column's own floor -- 13px to 11px,
14px to 10px, 92px to 72px. Nothing about the team lines changed. Measured at
1400px: three 378px columns, no card overflowing its box and no horizontal
scroll on the page; mobile stays one column.

**A stretched card spreads its slack across every grid track.** Cards sit in
a two-column list and each is stretched to the height of its taller neighbour.
`.row` is itself a grid, and the default `align-content:stretch` hands that
extra height to ALL THREE tracks -- so the teams row grew about 10px taller
than the two team lines it contains, and `.meta`'s 1fr/1fr split silently
stopped matching them. Every card was off by an amount that depended on its
neighbour, which is why an earlier spot check measured 0px: that card happened
to be the tallest in its row. `align-content:start` sends the slack to the
bottom and every track keeps its content height. Verified at 0.00px across
280 cards on all four tabs.

**A grid item spanning two rows cannot align with either.** `.meta` originally
covered `"sport meta" "teams meta"`, so its first line sat against the header,
64px off the away team's line. Fixed by giving the header its own full-width
row (`"sport sport"`) and making `.meta` a two-row grid inside the teams row.
Verify alignment by comparing bounding-box centres, not by eye. The two-row
grid is gone as of 2026-09-10 -- the date joined the column, and three lines
against two team lines have no row to match -- but `"sport sport"` stays,
because the header still has to be full width.

**"Power Four/Five" scopes CHAMPIONSHIP GAMES, not TV windows.** A version
that gated every window on a power-conference team was wrong and he corrected
it: a TV window is a time slot on a network, whoever is playing. The real
problem was narrower -- non-Power-Five CHAMPIONSHIP games falling into windows
by accident of scheduling (Mountain West Championship -> FOX Friday, American
Athletic Championship -> ABC Saturday, FCS playoff quarterfinals -> ABC
Saturday). `rules.is_championship` catches any title/playoff headline and
harvest strips the window when the conference is not Power Five. 7 games.

Two things measured while getting this wrong, worth keeping:
* **Conference ids are per SPORT and they collide.** 4 is the Big 12 in
  football and the **Big East** in basketball; the ACC is 1 vs 2.
* **A power-conference test would drop Notre Dame**, an INDEPENDENT
  (conference 18) -- and NBC's entire college football package is Notre Dame
  home games. Any future conference rule must special-case it.
* On basketball the same test would have dropped **177 games** -- UConn 42,
  St. John's 28, Creighton 27, Villanova 23, Gonzaga 21, Marquette 19.

**Army-Navy is a FALSE CBS match, five years out of five.** December Saturday
afternoon on CBS hits the CBS window exactly, but the game belongs to no
package. Excluded by team id in `cfb_slots`. Removed 5 games (1659 -> 1654).

**17 of the 46 championship games have NO TV window** and would vanish from
that view: the Big Ten football title kicks at 8pm, the Pac-12 one was on a
Friday, and every basketball final is on ESPN either just outside the
Saturday-night cutoff or on a Sunday. They are admitted to the view by the
`title` flag AND exempted from the window filter, or Marquee Windows (now the
opening state) would hide them again.

**Every Power Five CFB championship game now carries a category.** They belong
in Key Games, but many match no ranking rule (an unranked pair, or a ranked
favourite winning), and Key Games DEFAULTS to the upset category -- so an
uncategorised title game was invisible. `rules.title_fallback` files them by
result: upset -> Ranked Upsets, anything else -> Ranked Games. **CBB conference
tournaments are deliberately NOT covered** -- 302 games, different category
names, and 269 remain uncategorised, visible only under "All Game Types".

**An IN-PROGRESS season must never be cached.** The cache is keyed on a date
RANGE, so a partial answer fetched in week one would be served for the rest of
the year. `season_over()` gates it: football is done after 1 Feb, basketball
after 1 May. 2026 football is live right now and refetches every run.

**FOOTBALL never shows an event name -- the city, every time** (his call).
The Aflac and Chick-fil-A Kickoffs read Atlanta and Charlotte. The rule below
therefore runs for basketball only. In the New York, Los Angeles and Chicago metros the
location shows the VENUE rather than the municipality -- nobody says "a Bronx
game" or "an Inglewood game" -- so `rules.VENUE_METROS` swaps in Madison Square
Garden, Yankee Stadium, MetLife Stadium, Barclays Center and Intuit Dome.

**"Is it an event or one neutral-site game?" is DERIVABLE, not a judgement.**
A tournament fields more than two teams under its name; a showcase game fields
exactly two. Counted per season from the raw events (`event_sizes`), that
separates all 37 names correctly: Maui runs 8 teams over 12 games, the Aer
Lingus College Football Classic is one game between two. **Count PER SEASON** --
there were two Duke's Mayo Classic games in 2021 and one every other year, so
the same name is an event in one season and a single game in the next.
`event-overrides.json` forces either answer where the rule is not what he wants.

**A show-broadcast game is its own admission reason.** He wants every College
GameDay and Big Noon Kickoff game in the archive, and 24 of the stragglers were
ESPN games that no window reaches. `harvest.show_games()` reads the tables out
of seed_tags.py -- one list, not two that drift -- and flags the game `show`,
which admits it to the TV Windows view and lets it ride Marquee. Postseason
still stays out: the 2024 Mountain West Championship is the case that tests it.

**Names must be compared through `rules.display_name` on BOTH sides.** The
seeder matched the table's "UConn" against the archive's "Connecticut" and
missed a game that was sitting right there. `norm()` routes everything through
display_name so UConn/Connecticut, BYU/Brigham Young and USC/Southern
California all
resolve.

**ESPN carries NOTHING about College GameDay or Big Noon Kickoff** -- not in
the scoreboard, not in the summary endpoint. Searching the payloads for
"gameday" finds only article prose. Those tags are supplied by hand.

`seed_tags.py` takes a table of (date, visitor, host) rows and MERGES the tag
into `docs/tags.json`, which is live shared state -- anything he tagged from a
device is preserved. It also looks a day either side of the given date, since
a late kickoff shifts the Eastern date. Of 73 Big Noon rows, 63 matched and the
10 that did not are all games the archive correctly excludes: the show
travelled to Thursday-night openers, 3:30 and 4pm kickoffs, an ESPN 10pm game
and the Mountain West Championship. A useful cross-check on the window rules.

**ESPN can answer a whole week with NOTHING, and the cache believed it.**
Basketball is fetched a week at a time from 1 November. For the opening week
of 2023-24, 2024-25 and 2025-26 ESPN returned zero events -- 213, 289 and 360
games in reality -- and so did the week of 14 March 2022 (95 games, all
postseason). The empty answers were cached as if true. No error, no warning:
the archive simply lacked opening week. That is how James Madison's upset at
Michigan State (2023) and Baylor at Gonzaga (2024) went missing, and why the
series scan never saw Kansas at North Carolina (2025) and so never proposed
that home & home. It is not simply "the week starts before the first game" --
1-7 November 2022 came back fine -- so `harvest.cbb_range` does not guess: any
empty week is re-asked one day at a time, which also repairs the old cached
files without deleting them. An EMPTY week is detectable; a PARTIAL one would
not be, and nothing checks for that. Found by comparing every cached week with
live day-by-day counts (2026-09-11).

**A week that crosses into the postseason comes back half empty.** A CBB
range query answers with ONE season phase: a week starting in conference
tournament play returns only its regular-season days, so the week of 13 March
2016 ended at 13 March and lost Michigan State against Middle Tennessee, and
the week of 14 March 2021 lost Michigan State-UCLA and Ohio State-Oral
Roberts. The seasontype parameter does not change the answer; single-day
requests do return the games. Unlike an empty week this one is not empty, so
the empty-week fallback never fired. `cbb_range` now compares the newest game
returned with the last day asked for and fetches the rest one day at a time.
Checked on six boundary weeks, 2016 to 2026.

**Rivals history is fetched whole but cached filtered.** 2014 to 2020 exist
only for Rivals, so `harvest.rival_events` keeps just the games Ohio State,
Michigan State or Notre Dame played, as cache/rivals-SPORT-SEASON.json --
kilobytes, where full scoreboards for seven seasons would add hundreds of
megabytes to the Drive-synced cache. Two traps on the way: a whole football
season sits close to the 1,000-event cap, so it is fetched in three ranges, and
ESPN occasionally returns an event with no id at all, which crashed the first
run. Every game from those seasons is `rivals_only`, and the app keeps
`rivals_only` games out of TV Windows, Key Games, their Year lists and the
newest-season default.

**Stage labels read the headline from the END.** A CFP headline can carry a
suffix ("College Football Playoff Quarterfinal at the Allstate Sugar Bowl -
Rescheduled from Jan 1"), and an NCAA headline puts the round last ("Men's
Basketball Championship - South Region - 1st Round"), so the round is taken
from the last part that names one. Order matters inside a part: final four and
semifinal must be tried before final, or a Final Four reads as a Championship.
The CFP test runs before the bowl name, because CFP games are played in bowls.

**Bash heredocs choke on apostrophes here.** An inline Python script with an
odd number of apostrophes fails to parse before anything runs ("unexpected EOF
while looking for matching quote"), even inside a quoted heredoc. Scripts that
need apostrophes go into a file first.

**ESPN has no week 0.** Week 0 games are numbered week 1 -- and so are the
bowls -- so `week_zero_ids` finds them by date: the regular-season week-1 games
played before the main Week 1 weekend, whose Saturday carries the most week-1
games. 2021-2025 that is one early Saturday a year: 8/28, 8/27, 8/26, 8/24,
8/23.

**The series scan, and the five ways its first rule was wrong.** The Home &
Home, Neutral & Neutral and Home & Neutral tags came from a one-off scan of the 2019-2026 schedules -- 2019 and 2020 to
catch 2021's second legs, the published 2026 football and part of the
2026-27 basketball schedule to catch first legs -- followed by his review.
* "Has an ESPN note" is not "is an event": Iowa-Iowa State carries "Iowa Corn
  Cy-Hawk Series" in some years.
* "More than two teams under one note" is not an event either. Showcase
  doubleheaders (Indy Classic, West Coast Hoops Showdown) are exactly how
  neutral & neutral series get packaged. A larger event is a TOURNAMENT (a
  team plays twice within four days -- the Hall of Fame Series has a team play
  twice, but weeks apart), a CONFERENCE CHALLENGE, or a recurring event whose
  teams each play once (Champions Classic, CBS Sports Classic, Jimmy V).
* Conference ids break after realignment. ESPN's per-game
  `conferenceCompetition` flag is the better test, but it calls UNC-Wake Forest
  non-conference, so same-conference pairs are excluded outright.
* "Annual" cannot mean every season: Kentucky-Louisville skipped 2021-22 and
  Notre Dame-USC skipped 2020. The scan counted 5+ meetings in 2019-2025.
* ESPN can list the same HOST both years (Illinois-UConn at MSG, then at
  Gampel flagged neutral), so hosts are compared as well as venues.
* "Consecutive seasons" is too strict. Villanova-UCLA basketball stretched its
  home & home over 2021-22 and 2023-24, so the scan also flags meetings a
  season apart ("Home & Home?: a season apart") for review.
The per-game list is a record of his rulings, not a rule to re-run: a new
season needs a new scan and a new review. `series_scan.py` is that scan, kept
in the repo (his call 2026-09-11). It writes output/series_review.txt, marks
the pairs seed_series.py already covers so only new ones need a ruling, and
caches the seasons harvest never keeps (the two before the archive, and
unfinished schedules, re-fetched daily) in the system temp folder rather than
the Drive-synced cache/.

**A new archive game can complete a series nobody reviewed.** The Week 0/1
rule brought in Oregon State at San Jose State 2023, North Carolina at
Minnesota 2024 and the 2022 leg of Florida State-LSU, and each turned out to be
the missing leg of a clean Home & Home or of a pair he had already ruled
Neutral & Neutral -- so they were tagged without a new review. Re-run the scan
after any rule change that adds games, not just at season end. A pair he rules
OUT goes in `seed_series.NOT_SERIES` (Arizona-Kansas State, Virginia-Notre
Dame, Notre Dame-Navy): otherwise an untagged pair looks like an open question
forever, and a seeder run strips any series tag its games already carry --
which is how Notre Dame-Navy's four Annual tags came off.

**Notre Dame against an ACC team is never a series, from 2014 on** (his call
2026-09-11). Its scheduling agreement with the ACC sends it home and away
against the same schools, which reads exactly like a home & home to the scan.
Seven had been tagged -- Virginia Tech (2016), Miami (2017, 2025), North
Carolina (2022), Clemson (2022, 2023), Louisville (2023) -- and all came off;
Virginia Tech at Notre Dame (2016) left Rivals with its tag, since nothing else
qualified it. `seed_series.nd_acc` ignores such rows and strips Home & Home /
Neutral & Neutral / Home & Neutral from those games (Annual is untouched), and
`series_scan.py` no longer asks about them. It is a rule, not NOT_SERIES rows,
so a new ACC opponent needs no entry.

**series_scan records carry NO winner.** `load_all()` keeps teams, venue and
conference but not who won, so a check that picks rival LOSSES out of them
finds none from 2019 on -- only the 2013-2020 rival caches, which keep the raw
competitors, ever produced a loss. The fix is to read `winner` from the same
cached schedules via `load_season()`. Done right (2026-09-11), it turned up six
untagged rival-loss legs, now Home & Home in `seed_series.SERIES`: Pittsburgh
at Ohio State (2024-25) and Ohio State at Pittsburgh (2025-26) in basketball;
Notre Dame at Georgia, Notre Dame at Michigan and Arizona State at Michigan
State (all 2019) and Michigan State at Boston College (2024) in football. Three
of those were not in the archive at all; the series tag is what brought them
into Rivals.

**The scan reaches one season apart, no further.** A home & home stretched
wider reads as two one-offs: LSU at UCLA (2021) and UCLA at LSU (2024) is the
clearest case. The non-conference review list of 2026-09-11 prints every other
meeting of the pair beside each "one-off" so a longer gap can be spotted by
eye rather than widening the rule.

**Annual is by pair, and counts NON-CONFERENCE meetings only.** It maintains
itself: Washington-Washington State 2026 was tagged as soon as the pair was
listed (his call 2026-09-11, "as is Oregon-Oregon State"). But both pairs were
Pac-12 rivals until 2024, so their earlier meetings were league games rather
than a scheduled series -- and Oregon-Oregon State's only archive game, 2022,
is one of those, so that pair carries no tag yet. `ANNUAL_SINCE` makes the
start explicit: both pairs count from 2024 (his call).

**The tags are spelled out** -- Home & Home, Neutral & Neutral, Home & Neutral
(his call 2026-09-11) -- after starting life as H&H / N&N / H&N.
`seed_series.RENAMED` rewrites an abbreviation wherever one survives in
tags.json, since an old cached copy of the app could still write one.
**Buy Game** is by id, from him: Marshall and Northern Illinois at Notre Dame,
Appalachian State at Texas A&M. He placed the Northern Illinois game in 2025;
the only meeting in the archive is 2024-09-07, so that is the one tagged.

**A dropdown that hides empty choices must ask the view, not the data.** The
Team and Winner lists come from `visibleWithout(key)`: the list the current view
would show with THAT filter cleared and every other filter left alone. Building
them from the raw games instead would still offer a team that has nothing in
the chosen season or view. The current selection is always added back, or
changing another filter could make it vanish from its own dropdown.

**Rivals cannot sort by week blocks.** Newest First walks football week blocks,
and a bowl or CFP game has no week, so its block is its date -- and the string
"2025-15" sorts after "2025-12-31". The Big Ten title game landed ahead of the
CFP quarterfinal played three weeks later. Rivals orders by true date instead.

**ESPN drops some old rankings; the AP poll does not.** Oklahoma #5 at Ohio
State #2 (2017) and Michigan State #16 at Northwestern (2017) both read
unranked on ESPN's scoreboard (curatedRank 99 on both sides), so neither
reached Rivals. ESPN's core API serves the AP poll by season and week
(.../seasons/S/types/2/weeks/W/rankings/1, with basketball filed under the year
the season ends), and `harvest.ap_ranks` asks it when a rival loss has no
ranking at all. Measured across every rival loss since 2014 it matters for only
three games, so it is used for Rivals alone and never rewrites Key Games ranks.

**The series scan could not see Rivals history.** It judged only games already
in the archive, from 2019. A Rivals home and home before that, or a plain loss
that no other rule brought in, was invisible twice over: never scanned, and
never harvested. The fix works from both ends -- a scan of every rival loss
since 2014 against the full schedules plus the filtered rival caches back to
2013 (which found every pair he named: Michigan State-Arizona State, Ohio
State-Oklahoma, Notre Dame against Georgia, Miami and Texas, Ohio State-Virginia
Tech), and harvest keeping any rival loss whose id is in seed_series.SERIES or
carries a series tag in tags.json.

**A game kept only for Rivals must not leak into the other views.** Harvest
drops postseason games at the top of its loop and non-final conference
tournament rounds near the bottom. A rival's loss in either is now kept, and
that game's slots, type, Black Friday, show and opener flags are cleared
(`rivals_only`): a bowl played on a Saturday on ABC would otherwise land in ABC
Saturday, and a ranked upset in the NCAA tournament in Key Games. Its week is
cleared too, because ESPN numbers the bowls week 1 and the card would read
"WEEK 1" in January. The check after any change here: the TV Windows and Key
Games populations must come out identical before and after.

A tag can land on a game no tab shows: Arkansas-Michigan State 2025-26 is Home & Neutral,
but it is a November game (the basketball TV tab is January-March) and an MSU
win (Key Games hides rival wins).

**The WINDOW and the HEADER LABEL are not the same thing.** ABC is the case
that forces the distinction: the window holds EVERY Saturday ABC game (202 of
them), while the header reads "ABC Primetime" only for a 7-8pm kick (69) and
nothing at all otherwise. `rules.cfb_header` decides the label; `cfb_slots`
decides the window. Narrowing the window to 7-8pm instead cost 134 games and
was a misreading of what he asked for.

**Football's TV windows are ERA-DEPENDENT.** No CBS or NBC window before the
2023 season, and ABC is primetime-only (7pm+) in 2021-22. Without that, the
early seasons showed windows that did not exist yet -- the packages moved to
NBC in 2023 and CBS in 2024. `cfb_slots` therefore needs the SEASON, which is
why harvest passes it.

**Baseline alignment in flex needs matching line-heights.** The header's h1
(22px) and count (13.5px) both inherit line-height 1.45, which computes the
flex baseline off differently-sized boxes and drops the count. Setting both to
1.2 fixes it.

**A variable read one line before it is assigned reads the PREVIOUS loop
pass.** `heads` (an event's headline notes) was assigned just below the
CFB/CBB branch but used inside it, so every basketball game's
conference-tournament test ran against the game harvested before it. Python
raises nothing -- the name is bound from the last iteration -- so it looked
like it worked. It cost two labels: Duke-Wake Forest 2025-03-03 and Duke-North
Carolina 2026-03-07 were both suppressed as tournament games because the
event before each of them was one. Fixed by hoisting the assignment above the
branch.

**Marquee could not stay a list of windows.** It began as one -- the button
ticked three window names -- with Black Friday and show broadcasts admitted
alongside by a special case in `visible()`. Both halves broke. Football picked
up games he had not asked for through the ride-along, and basketball's
"FOX Weekend" window is any FOX game between January and March, weeknights
included, so a Tuesday game reached a filter meant for weekends. His call
2026-09-10 made it a rule: `rules.is_marquee` decides per game and harvest
freezes the answer as `mq`. Measured: 151 football games (exactly the three
windows, nothing riding along) and 142 basketball games (no weekday among
them; the 14 without a Big Ten team are all FOX Friday or FOX Primetime, as
specified). The only weekend Big Ten games on FOX/CBS/NBC left out are the
five Big Ten tournament finals, which is his standing rule.

**The broadcast-network header labels are Big Ten only.** His rules
2026-09-10: ABC and NBC get a label on any day, named for the day (`NBC
Saturday`); FOX gets `FOX Saturday` for the Saturday afternoon that
`FOX Primetime` does not cover; CBS gets `CBS Sunday`. All three need at least
one Big Ten team -- ABC will put any two teams on a Saturday -- and none apply
to a conference tournament. Measured, they label 64 games: 40 CBS Sunday, 21
FOX Saturday, 3 NBC Saturday, and ZERO ABC, because all 15 ABC basketball
games in the archive are non-Big-Ten. The rules still carry the January-March
gate every other CBB label has, which suppresses five Nov/Dec games.

**The ESPN brackets are one bracket now, and the label is what narrows it.**
All three -- ESPN Saturday, Big Monday, Super Tuesday -- take EVERY game
tipping between 6:00 and 9:30pm. Saturday used to take only the latest of
them; his call 2026-09-10 widened the WINDOW to the whole bracket (16 more
games) and left the "ESPN Primetime" LABEL on the latest game alone, which is
the first time a card's label and its window deliberately say different
things. Measured: 71 games in the window across 41 Saturdays, exactly one
Primetime label on each, none missing and none doubled.

**The app icon is the scoreboard** -- two team rows, winner washed maize (his
pick of six; `icons.py` draws all six and a preview page). It is declared
`purpose: "any maskable"`, so Android crops the square to the launcher shape:
the background must be FULL BLEED and every mark must sit inside the safe
circle of radius 0.40 about centre. **Measure it, do not eyeball it** -- the
first version put the card corners at 0.408 and would have been clipped. The
shipped card is 0.20-0.80 by 0.26-0.74, furthest mark 0.383.

**YELLOW BELONGS TO MICHIGAN.** Nine other schools washed yellow and were
moved to their other colour. Six of them are black-and-gold schools
(Appalachian State, Central Florida, Colorado, Iowa, Missouri, Vanderbilt), so
they now wash GREY and are not distinguishable from one another -- the honest
trade for keeping maize unique. Arizona State took its maroon and West Virginia
its navy. **Georgia Tech had no usable ESPN alternative** (old gold, then
WHITE), so its override is the school's real navy #003057 rather than an ESPN
value.

**Big Ten team names render in CAPS, keyed on conference AS OF THAT SEASON.**
USC is capitalised from 2024 and not before; so are Oregon and Washington.
The name itself comes from `rules.NAME_OVERRIDES`, which spells out the schools
ESPN abbreviates (BYU -> Brigham Young, LSU -> Louisiana State, TCU -> Texas
Christian and so on) and softens UNLV and UConn the other way.

**"The latest game" is chosen PER DATE, not by a clock rule.** It needs a
pre-pass over the season's events, like `fox_friday_dates`, because no clock
cutoff can express "the last one": the old 6:30pm attempt kept 11 games at
18:30 while dropping 27 at 18:00. Measured: 41 Saturdays, zero ties, so no
tiebreak is needed. Since 2026-09-10 this decides only which game is LABELLED
"ESPN Primetime" -- the window itself is the plain 6:00-9:30pm bracket -- and
the pre-pass bracket was widened to 9:30pm to match, so "the latest" means the
latest of the games actually in the window.

**The Week filter follows the SEASON.** Week 16 exists only in some years, so
the options are rebuilt from the games in the chosen season and the week is
cleared whenever the season changes -- otherwise a stale week empties the list.
Football only: basketball has no meaningful week. Week 0 is a real value, so
every test for a week must be `!= null`: `!g.week` silently dropped Week 0 from
the dropdown, the card header and the Newest First blocks.

**The newest season is per SPORT.** `SEASONS` covers both sports, and
basketball's newest one (2026-27) has no games until November, so opening a tab
on the overall max showed an empty basketball list. `latestSeason()` takes the
newest season with games in the tab's own sport.

**A team's latest ARCHIVE game can come from its old conference.** The Team
filter sorts by current membership. Taking that from each team's latest game
in the archive put Stanford football (latest archive game: 2023, Pac-12) and
Arizona State basketball below the divider, though both have since joined
power leagues. Harvest now records every team's conference from its latest
game of ANY kind in each sport (`teams[id].conf`) -- something the archive's
own games cannot tell you.

**Header tint contrast against the #1e1e23 card.** FOX #ffcb05 = 10.9:1,
NBC #0b85c8 = 4.11:1, CBS #005ae4 = 2.83:1. The WCAG floor is 4.5:1, so CBS and
NBC sit under it -- but #005ae4 replaced #1c4469, which measured **1.64:1** and
was genuinely invisible. Measure any new tint before shipping it; the card is
dark and dark blues vanish.

**The Michigan view (trial) keeps games no other view wants** (2026-09-11).
`rules.MICHIGAN_SEASONS` names the seasons; harvest keeps every Michigan game
in them and marks it `michigan` with an `mx` object (finish, final AP rank,
reigning champion, rating, his sheet columns, football game number). A game
kept only for this view is `rivals_only` -- the flag really means "not on TV
Windows or Key Games" -- and `rivalsAllows` still rejects it, so TV, Key and
Rivals are unchanged (checked: 27 games added, none visible there). TRAP: the
early `stype != 2` filter dropped every postseason game that was not a rival
loss before the Michigan test ran -- the CFP semifinal and final and all six
NCAA Tournament games went missing until `mich` joined that test. The final AP
poll is the LAST entry in the core API's season list (`final_poll`), not a
fixed week: football 2023 ends types/3/weeks/1, basketball 2025-26 types/3/
weeks/3. His sheet keeps uniforms, borders and caps as cell FORMATTING, so
they come from `michigan.csv`, not an import. Printing the emoji to the Windows
console raises UnicodeEncodeError -- set PYTHONIOENCODING=utf-8; the data is fine.

**Where the Michigan view puts the rating and Michigan rank** (measured on the
live site, 2026-09-11). After the opponent name, the name gave way on small
phones: 5 of 15 football and 16 of 40 basketball names cut at 375px, 2 and 4
at 390px, none at 430px. In the header beside the date, the long NCAA
Tournament headers wrapped to two lines under 430px. He moved both to the
bottom right of the card (`.mside`, pushed right inside the chip row), which
costs neither the name nor the header any width. Divider tiles: solid border,
team-name type size, and no "weeks off" (his calls). Then (same day) he moved
ALL the TV information into the header beside the date, which drops the card's
meta column entirely (`.row.mich` is one column: sport / teams / muni / tags)
and gives the team line the full width -- so the rating went back after the
name. Michigan's rank became a navy-on-maize box at the far right of the
uniform row (`.mrank`, margin-right 6px so it sits under the score, whose line
carries 6px of right padding). The Dense / Compact switch is gone: with the
rows fixed there was nothing left for it to move. A postseason win or a win
over a rival washes the whole card (`.mwash`) instead of the name line.
Then the uniform moved INTO the score and rank boxes (jersey behind the
score, pants behind Michigan's rank, accessories as the text), Michigan's
rank moved beside the score, the TV details went into the header only when
it names no window or stage, and the chips became one row in his order.
TRAP: an accessories colour can vanish into its box -- blue on blue, white on
maize -- and he wants those pairings anyway. `ink()` therefore keeps the HUE
and moves LIGHTNESS until the text reads 3:1 on its box: maize on maize is the
lightest gold that works (#8f7100, fine 0.01 steps so it stops as soon as it
crosses), blue on blue a lighter blue (#0076e5, coarser 0.05 steps -- he liked
that one). WHITE is exempt by his call 2026-09-11: the school palette shows
unshifted, so a white box takes maize or blue and a maize or blue box takes
white; white on white alone would vanish, so it reads blue. That leaves the
two maize-and-white pairings at 1.36:1, faint on purpose. The rank
column is 36px because "NO. 16" measures 35.4px in Source Sans 3; measure
again if the font or size changes.
RANKINGS line up on their VISUAL MIDDLE with the name: the shared baseline was
tried first (grid centring left the 12.5px digits 1.07px above the 15.5px
name's baseline) and he preferred the middle, so `.tl` simply centres every
cell. A postseason SEED now reads in FRONT of the name (`.rkin`, "vs. 2
WASHINGTON") rather than "NO. 2" in the column, so the rank column is 20px --
"#25" -- in every view, and the whole team line shifts left. ITALICS ARE GONE from every view (his call 2026-09-11): on a card `dimmed()`
marks -- a rival won, or Michigan lost -- the WINNER's name is struck through
instead (`.row.dimmed .tl.won .nm`, and `.row.mich.dimmed .mn` for the one-team
card). The seed box (`.rkin`) is the width of the rank column it replaces with
the digits right aligned, and `.row.rk-no` drops the column itself, so a
two-digit seed and a one-digit seed still start their names together and in
line with every non-postseason card. Michigan's own rank shows no "#", and both
Michigan boxes hold their widest reading. The box colours are the OFFICIAL
ones and never shift (maize #ffcb05, blue #00274c, white #ffffff); only the
text moves. The hash stays on Michigan rank except a CFP or NCAA seed, and the
inline seed takes the ranking size, not the name size (6.6ch for 121-108, 2ch for a rank)
via tabular figures (7.2ch, measured: 121-108 needs 50.5px of the 6.6ch box
at 50.5px, too close to trust). The rank box is 3ch: #25 measured 39px and
stretched the 2ch box, so every rank box now holds one width.

**Conference-tournament SEEDS come from him, not ESPN** (2026-09-11). ESPN's
ranking field is the SEED in the NCAA Tournament but the AP POLL in a
conference tournament -- checked in the scoreboard, the game summary, the core
API competitors, the tournament resource and its seasons; the bracket endpoint
404s. So `seeds.csv` (sport, season, team id, seed) feeds `load_seeds`, harvest
attaches a `seed` to each side of a Big Ten Tournament game, and the app shows
a seed wherever one exists (`seedOf`), with no hash, the way the CFP and NCAA
cards already read. 51 Big Ten Tournament games sit on the tabs and 74
team-seasons cover them. A conference-tournament card shows BOTH numbers (his
call 2026-09-11): his seed in front of the name and the poll ranking in the
column, so those cards keep the column and stay in line with every other card.
Only a CFP or NCAA card drops the column, because there ESPN's number is the
seed itself and no ranking is left to show.

**His BOX COLOURS are their own columns** (2026-09-11). The uniform gave a
first cut -- jersey behind the score, pants behind the rank -- but his real
cards do not follow it (Maryland 2023 is white on both boxes though its pants
were blue), so `michigan.csv` carries `score_bg`, `score_font`, `rank_bg` and
`rank_font`, and they win wherever they are filled. The readability rules still
run on top: the same colour on itself shifts in lightness, maize on white
darkens a touch, white on maize stays white, white on white reads a light grey (#b4b4ae, 2.3:1)
rather than navy. A Michigan card keeps its rank column on a seeded game, empty,
so the vs. starts where it starts on every other card, and in that view the
seed is plain inline text rather than the fixed box the other views use; the other views collapse
it instead, because their names have no vs. in front.

**Football finals are the CFP COMMITTEE RANKINGS from 2014** (his call
2026-09-11), the AP poll only through 2013. ESPN type 21 ("Playoff Committee
Rankings") runs 2014 onward; 2013 and earlier carry only AP (1), coaches (2)
and the BCS standings (3). The two differ on 48 of Michigan opponents since
2014 -- Ohio State 2024 is AP 1 but CFP 6 -- because the committee stops before
the bowls while the AP poll votes after them. The CFP cache is a separate file
per season so an AP final saved earlier is never served in its place.
Basketball stays on AP.

**One height for the stripe and both boxes** (his call 2026-09-11): 26px, set
on all three, with the stripe vertical padding dropped so border-box leaves the
whole 26px to content. Matching heights is what makes the score line up with
the highlight top and bottom -- the boxes were 24px against a 26.5px stripe.
The DATE stops at the box padding edge (8px), not the card edge: the numbers
below it are centred in their boxes and never reach the edge themselves.

**TRAP: an emptied grid track still takes its gap.** When the rank box left the
team line, `.row.mich .tl` kept three columns and the score stopped 7px short of
the card edge -- the 0px track plus its 6px gap -- while the rank box, alone in
its own row, reached the edge. Measure `gridTemplateColumns` when two things
that should share an edge do not.

**Michigan's rank moved to the THIRD ROW** (his call 2026-09-11): under the
score, the same width as it, the number centred, which gives a row that would
otherwise hold one lonely rating (five 2023 cards) a right edge. With the rank
gone from the team line, the opponent's finish went back after the name.

**The opponent finish moved OFF the name line** (his call 2026-09-11): it cut
long names short, so the finish or rating now leads the DETAIL ROW, which is
itself plain grey text in the header style -- no chip backgrounds -- with a
bar between items in the header's own colour, in proper case with no brackets
or parentheses (his calls). The row is indented 29px -- the crest plus its gap --
so it starts under the first letter of the team name (57px at 390px, measured), and a CFP or NCAA card leaves the
opponent finish out, the header already naming the round. TRAP: taking the finish out of the name line also took the stripe's
CLOSING tag with it, which dropped the score and rank boxes inside the stripe
and wrapped them onto a second line.

**The Michigan view reaches back to 2011** (loaded 2026-09-11). The archive
keeps whole seasons only from 2021, and the 2014-2020 Rivals caches hold only
Ohio State, Michigan State and Notre Dame games, so every season before 2021
is walked again: `michigan_events` fetches the whole scoreboard, keeps the
Michigan games as cache/michigan-SPORT-SEASON.json and every team's postseason
as cache/post-SPORT-SEASON.json (`postseason_events` fetches 2010's on its own,
for 2011's reigning champion). An opponent's CFP / NCAA finish needs those
postseason games -- a Michigan-only list would only know the rounds Michigan
played. Before the CFP the title game is the BCS National Championship, which
`stage_label` reads as a bowl, so `playoff_finish` treats any "national
championship" headline as the final. Rivals still starts in 2014: in an older
season `rival_loss` is forced False, or Michigan's wins over rivals in 2011-2013
would have reached that view. Neutral-site detection stays honest on these
partial seasons because `offsite_games` needs a team's four home games before
calling a venue unusual. Basketball networks are thin in ESPN's data before
2012-13, so early cards can show no network (accepted, his call).

**Ranking colours are a CARD class, not a team one** (2026-09-11): `rk-upset`
(orange, `--accent` #e0834f, 5.95:1 on the card) or `rk-grey` (grey, `--muted`
#9a9a95, 5.87:1), set in `rowHtml` for every view including Rivals. Grey is
exactly `dimmed()` -- a Michigan loss or a win by Ohio State, Michigan State or
Notre Dame (either sport) -- and is tested first, so such an upset reads grey.
`rk-no` (the CFP and NCAA Tournament, `playoffGame`) swaps the "#" for "NO." and gives the number (`.rn`) two digits of width, left-aligned inside a right-aligned cell, so "NO." holds still; every card now uses the 44px rank column, so names and final digits line up across cards --
and widens the rank column from 24px to 44px on that card only. The upset test
is by rank alone (`isUpset` in app.js: the loser ranked, the winner unranked or
worse-ranked) -- deliberately NOT the Key Games type, which files a game once
and would miss upsets it filed as Top 10 Games or Ranked Big Ten.

**ESPN sometimes records a network game with only its STREAMING feed.**
Texas A&M at Florida (2024-09-14) reads "ESPN+, ESPN3" and nothing else -- a
weather delay, and `geoBroadcasts` is empty too, so nothing in ESPN's data
recovers it. Of 73 power-vs-power games with no major network, the vast
majority are GENUINE streaming exclusives (Peacock's Big Ten package, BIG12|
ESPN+, ESPN3 for the ACC), so there is no rule that separates the real ones
from the degraded ones. `window-overrides.json` is the escape hatch: game id ->
window list, read by harvest.

**CBS B1G Time is the 3:30 window and ONLY that.** I once widened it to any
Saturday CBS game (or CBS + Big Ten/SEC) to explain a missing game, and he
rejected both -- they dragged in Washington-Washington State, UCLA-Hawai'i and
a dozen 2023 fixtures. **Both games he reported missing were WEATHER DELAYED**:
USC at Purdue reads 6:45pm because of the delay, and Texas A&M at Florida lost
its network entirely. Those are `window-overrides.json` entries, not rule
changes. Read a missing game as a data problem before widening a rule.

**Seven tabbed games have NO network at all, and ESPN has none to give.**
Checked 2026-09-11: the scoreboard's `broadcasts`, `geoBroadcasts` and
`broadcast` are empty, and the per-game summary endpoint is empty too. Five are
Rivals-only basketball and football (Butler-Ohio State at the 2017 PK80,
Wisconsin-Ohio State 2019-03-10, Michigan State at Wisconsin football
2019-10-12, Florida-Ohio State at the 2021 Fort Myers Tip-Off, Iowa-Ohio State
2022-02-19); one is on TV Windows (Indiana State-Ball State, 2023 Indy Classic)
and one on Key Games (Ole Miss-Purdue, 2024-11-29). He supplied all seven
networks, which now live in `network-overrides.json` (game id -> networks),
used only when ESPN lists none and read BEFORE the window rules -- so a
network there can place a game in a window. It did twice: Iowa at Ohio State
(2022-02-19, FOX) became FOX Saturday and Marquee and left Rivals-only for TV
Windows, and Ole Miss-Purdue (2024-11-29, FOX) joined FOX Weekend.
`window-overrides.json` could not have done this -- it sets windows, not
networks.

**A Buy Game is by id and on any tab, not only Key Games.** He named two from
the non-conference review (2026-09-11) that sit on Rivals and TV Windows:
Texas Southern at Michigan State (2014-15) and Notre Dame at Howard (2021-22).
`seed_series.BUY_GAMES` tags whatever id it is given; the "Key Games only" of
the first round was which games he was asked about, not a rule. Separately, 244 games carry
only networks outside `NET_PRIORITY`; they still display, because the primary
network falls back to the first one listed.

**An override re-files a game; an EXTRA only files it.** `window-overrides.json`
replaces a game's windows, and the header follows them. `window-extras.json`
(2026-09-11) adds a window the game is FILTERED under -- and counted toward
Marquee -- while the card is still drawn from the windows the rules gave it.
Penn State at Michigan State, Black Friday 2023 on NBC at 7:30pm, is the one
case: he wants it under NBC Saturday Night without it reading or colouring
like one. Harvest decides the header from `card_slots` BEFORE the extras join
`slots`; do it the other way round and the card changes.

**Conference membership is AS OF THE SEASON, which bites the Black Friday
rule.** Narrowing Black Friday to "FOX/CBS/NBC with a Big Ten team" drops the
2023 Oregon-Oregon State game, because Oregon was still Pac-12 that year and
only joined the Big Ten in 2024 -- and that is the very game he had asked about
a round earlier. Flagged to him rather than quietly exempted. 30 games -> 10.

**`HIDDEN_WINDOWS` hides a filter OPTION, not the games.** ABC Saturday
(football) and ABC Weekend, ESPN Saturday, Big Monday and Super Tuesday
(basketball) are out of the TV Window dropdown, but the games keep their
window and still appear under "All TV Windows" -- 202 football, and 71 / 59 /
77 for ESPN Saturday, Big Monday and Super Tuesday.

**A game with no window needs explicit admission to the TV Windows view.**
Championship AND Black Friday games carry no window, so both need
`|| g.title || g.bfri` in the view filter and in the Marquee exemption. Black
Friday games were harvested correctly but unreachable on the page until that
was added -- the data was right and the view was wrong, which is the hard kind
to spot.

**Two navigation axes, not one.** TAB is the sport, VIEW is the collection.
Switching sport must clear EVERY filter (CFB and CBB share no game types or TV
windows, so a leftover value empties the list and the page looks broken rather
than empty-by-choice); switching view clears only game type and TV window,
because year, team and tag still apply.

## Validation

There is no selftest yet — **worth writing before this is trusted.** What it
should cover, based on what actually broke: the sponsor-name matching across
all five seasons, the CBB week-walk not dropping games at boundaries, the
near-black colour rule, the conference-at-the-time assumption, and a structural
check of the built page (balanced tags, every `getElementById` present in the
HTML). The last one already runs ad hoc and catches real breakage; note that
`settings` and `sheet` look unused because they are reached through `show()`.
