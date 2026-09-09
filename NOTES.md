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
