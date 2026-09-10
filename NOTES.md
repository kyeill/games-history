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
are marquee-matchup rules. The tab is named Big Games for that reason.

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
held 265 early-round basketball games that Big Games showed but nobody wanted
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

**The Jan-Mar limit is on the TV WINDOWS only.** Big Games spans every month,
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

**The Big Games exclusions live in the APP, not the harvest.** Michigan losses
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

**`event.week.number` is on every CFB event** (weeks 1-16, zero missing across
all five seasons). Basketball has one too but it means nothing to a viewer, so
only football renders it.

**A grid item spanning two rows cannot align with either.** `.meta` originally
covered `"sport meta" "teams meta"`, so its first line sat against the header,
64px off the away team's line. Fixed by giving the header its own full-width
row (`"sport sport"`) and making `.meta` a two-row grid inside the teams row.
Verify alignment by comparing bounding-box centres, not by eye.

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
in Big Games, but many match no ranking rule (an unranked pair, or a ranked
favourite winning), and Big Games DEFAULTS to the upset category -- so an
uncategorised title game was invisible. `rules.title_fallback` files them by
result: upset -> Ranked Upsets, anything else -> Ranked Games. **CBB conference
tournaments are deliberately NOT covered** -- 302 games, different category
names, and 269 remain uncategorised, visible only under "All Game Types".

**An IN-PROGRESS season must never be cached.** The cache is keyed on a date
RANGE, so a partial answer fetched in week one would be served for the rest of
the year. `season_over()` gates it: football is done after 1 Feb, basketball
after 1 May. 2026 football is live right now and refetches every run.

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
display_name so UConn/Connecticut, BYU/Brigham Young and USC/Southern Cal all
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

**The three ESPN brackets, and they differ on purpose.** ESPN Saturday takes
the LATEST tip between 6:00 and 9:00pm -- exactly one game a week. Big Monday
and Super Tuesday take EVERY game between 6:00 and 9:30pm, several a night.
The header suffixes use the same brackets as the windows, so a card's label
can never disagree with the window it is in.

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

**ESPN Saturday is chosen PER DATE, not by a clock rule.** One game a week --
the latest tip between 6 and 9pm ET -- so it needs a pre-pass over the season's
events, like `fox_friday_dates`. Measured: 46 Saturdays, zero ties, so no
tiebreak is needed. The old 6:30pm cutoff kept 11 games at 18:30 while dropping
27 at 18:00, which is what made it wrong.

**The Week filter follows the SEASON.** Week 16 exists only in some years, so
the options are rebuilt from the games in the chosen season and the week is
cleared whenever the season changes -- otherwise a stale week empties the list.
Football only: basketball has no meaningful week.

**Header tint contrast against the #1e1e23 card.** FOX #ffcb05 = 10.9:1,
NBC #0b85c8 = 4.11:1, CBS #005ae4 = 2.83:1. The WCAG floor is 4.5:1, so CBS and
NBC sit under it -- but #005ae4 replaced #1c4469, which measured **1.64:1** and
was genuinely invisible. Measure any new tint before shipping it; the card is
dark and dark blues vanish.

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

**Conference membership is AS OF THE SEASON, which bites the Black Friday
rule.** Narrowing Black Friday to "FOX/CBS/NBC with a Big Ten team" drops the
2023 Oregon-Oregon State game, because Oregon was still Pac-12 that year and
only joined the Big Ten in 2024 -- and that is the very game he had asked about
a round earlier. Flagged to him rather than quietly exempted. 30 games -> 10.

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
