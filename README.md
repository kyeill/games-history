# Games History

A browsable archive of past college football and college basketball games that
meet Kyle's criteria, 2021 through 2025-26. Two dimensions, which may overlap:
**TV windows** (a recurring broadcast slot) and **game types** (ranking-driven),
plus Power Five conference championships. Every game can also carry his own
tags, editable from the app on any device.

Read `NOTES.md` before changing anything — it records each trap that already
cost a debugging pass.

Live at **https://kyeill.github.io/games-history/**

## The shape of the thing

Past games never change. So unlike [sports-daily](../sports-daily) and
[standings](../standings), this project **fetches once and freezes** — there is
no daily build, no cron, and **no Actions workflow at all**. GitHub Pages
serves `docs/` straight off `main`. `cache/` holds the raw ESPN responses, so a
re-harvest costs nothing.

```
python harvest.py    ESPN -> output/games.json   (apply rules.py; run when a season ends)
python colors.py     the row-wash colour per team -> output/colors.json
python site.py       build the app -> docs/  (GitHub Pages serves this)
python mock.py       the three row treatments Kyle chose from -> output/mockups.html
```

Python is not on PATH:
`C:\Users\kyleh\AppData\Local\Programs\Python\Python312-arm64\python.exe`

**No pandas or numpy** — Windows Smart App Control blocks numpy's ARM64
binaries on this machine. Standard library plus `requests`, same as the other
two projects.

## The rules (`rules.py`)

Postseason is excluded everywhere — bowls, the CFP and the NCAA tournament are
all ESPN season type 3. Conference championships and conference tournaments are
type 2 and **are** included, all rounds.

### TV windows

Named and ordered as Kyle names them, 2026-09-09. `rules.ORDER` is the single
source of truth for both the vocabulary and the display sequence, and
`harvest.py` copies it into `games.json` so the page never re-derives it.

**CFB** — FOX Big Noon · CBS B1G Time · NBC Saturday Night · ABC Saturday · FOX Friday.

**The football windows did not all exist for the whole archive.** There is **no
CBS or NBC window before the 2023 season**, and in **2021-22 the ABC window is
primetime only** (7pm or later). That tracks how the packages actually moved —
Big Ten Saturday Night began on NBC in 2023, CBS picked the Big Ten up in 2024
— so the first two seasons are FOX Big Noon plus ABC at night and nothing else:
13 and 13 a season, against ~120 from 2023 on.

**CBB** — FOX · CBS · NBC · ABC · B1G Peacock · Big Monday · Super Tuesday ·
*ESPN Sat night*.

ESPN Sat night sits last because it was in his original slot list but not in
the order he later gave. He confirmed keeping it.

`B1G Peacock` is narrowed to **Big Ten vs Big Ten, Tue/Thu, at least one ranked
team**. Peacock alone carries every Big Ten home non-conference game and
returned 246 games including Alcorn State at Minnesota; the narrowed rule
returns 39.

### Game types — and they differ by sport

Kyle's definitions, 2026-09-09. A game gets **at most one**, and membership of
the Key Games tab is exactly "has one, or is a conference title game". The
upset categories are tested first on purpose, so "anyone beats #1" is not
swallowed by the ranked-vs-ranked cases.

| CFB | means | count |
|---|---|---|
| Top 10 Upsets | unranked beats a top-10 team, **or anyone beats #1** | 54 |
| Ranked Upsets | worse-ranked team won, in top-10 v top-10 **or** ranked v ranked with a Big Ten team | 31 |
| Ranked Games | the same two scopes, better-ranked team won | 36 |

| CBB | means | count |
|---|---|---|
| Top 5 Upsets | unranked beats a top-**5** team, **or anyone beats #1** | 82 |
| Top 10 Games | top-10 v top-10, either winner | 75 |
| Ranked Big Ten | any *other* ranked v ranked with a Big Ten team, **excluding the Big Ten Tournament before its Final** | 75 |

CBB casts a tighter net on purpose — college basketball is far the bigger
slate. An unranked win over a CBB #7 is deliberately *not* a category.

**Power Five titles** — ACC, Big Ten, Big 12, SEC, Pac-12 championship games
(CFB) and conference tournaments (CBB), every round.

**Key Games requires a game TYPE.** Being a conference-tournament game is not
itself a qualification -- that admitted 265 early-round basketball games (ACC
first-rounders between unranked teams and the like) that no view could
usefully surface. Every championship game carries a type anyway, so nothing
real is lost. Those 265 left the archive entirely, since they were not on a TV
window either.

**A "championship game"** in the app's sense is narrower: a football title game
or a basketball tournament **final** — "finals only, not the rest of the
tournaments". 23 of each, 46 in all (`rules.is_title_game`). Those 46 get two
privileges: a category even when no ranking rule fits, and a guaranteed place
on TV Windows even with no broadcast window. Both matter — **17 of the 46 have
no window**, because the Big Ten title game kicks at 8pm, the Pac-12 one was on
a Friday, and every basketball final is on ESPN just outside the Saturday-night
cutoff or on a Sunday.

Football's fallback (`rules.title_fallback`) files by result: an upset becomes
**Ranked Upsets**, anything else **Ranked Games**. A basketball final matching
nothing becomes a **Top 10 Games** instead — his call, rather than borrowing
football's labels.

They also carry **no TV window chip**. A championship game is not part of a
broadcast package, so the card shows none; the `title` flag is what admits it
to the TV Windows view. It rides along with **Marquee Windows**, but selecting
one specific window shows none of them — 23 under Marquee, 0 under "FOX Big
Noon".

**Power Four/Five scopes CHAMPIONSHIP GAMES ONLY** — not TV windows. A window
is a time slot on a network, whoever is playing, so Boise State at BYU on ABC
in September is a real ABC Saturday game.

What it does exclude is a **non-Power-Five championship or playoff** that lands
in a window by accident of scheduling: the Mountain West Championship kicks off
on a December Friday night and falls squarely into FOX Friday, the American
Athletic Championship into ABC Saturday, and the FCS playoff quarterfinals do
the same. Seven games, all football. Basketball is untouched — a Big East
tournament game on FOX genuinely is a FOX basketball game.

**Army–Navy is excluded from the CBS window.** It is played on a December
Saturday afternoon on CBS, which made it a false match every year, five for
five. It is the last game of the season and belongs to neither package.

### What the rules return

**1,659 games — CFB 470, CBB 1,189 — across 147 teams.**

Several TV windows have **no history before 2023-24**, and this is real rather
than missing data: NBC 7:30 began with Big Ten Saturday Night in 2023, FOX
Friday in 2024, and Peacock's Big Ten package in 2023-24. Early seasons lean on
ABC/CBS/FOX.

## The app (`docs/`)

A static GitHub Pages PWA, installable, dark only, Sports Daily's visual
language throughout — `#16161a` ground, `#1e1e23` cards, `--rank` blue `#8fb0d8`
for rankings, Source Sans 3, and `logos.py`'s measured crest variants. One
column on a phone, **two from 900px**.

**Tabs are the SPORT** — College Football, College Basketball, Browse — and a
segmented control under them switches the **view**: *TV Windows* or *Key
Games*. Kyle asked for this over a single mixed list: the two sports share no
game types and no TV windows, and he wants to be able to isolate one population
at a time. Four populations result:

| | TV Windows | Key Games |
|---|---|---|
| CFB | 422 | 113 |
| CBB | 775 | 485 |

Switching sport clears every filter (a CFB game type would empty a CBB list);
switching view clears only game type and TV window, since the rest still apply.

*Browse* takes a date range and queries **ESPN live from the browser** — ESPN
sends `Access-Control-Allow-Origin: *`, so the page can call it directly and
the site never ships all ~35,000 games. Anything found there can be pulled into
the archive by hand.

**Key Games hides what he does not want to relive:** no Michigan losses, and no
Ohio State, Michigan State or Notre Dame wins. Both still appear under TV
Windows, which is a record of what was *on*, not a highlight reel. Enforced in
the app rather than the harvest, precisely so TV Windows keeps them.

**Filters** are a sport toggle plus five dropdowns — his call, 2026-09-09:

| filter | control | source |
|---|---|---|
| Year | dropdown, newest first | season |
| Game type | dropdown, `rules.ORDER` sequence | `rules.game_type` |
| TV window | dropdown, `rules.ORDER` sequence | whichever slot rule matched |
| Week | dropdown, **football only** | 1-16, following the chosen season |
| Team | dropdown, alphabetical | 141 of them |
| Marquee Windows | toggle button | `rules.MARQUEE` — three windows at once |
| Sort | toggle button | Oldest First (default) / Newest First |

**Marquee Windows** is the one-tap shortcut to the networks he plans a Saturday
around: FOX Big Noon + CBS B1G Time + NBC Saturday Night on football, FOX + CBS
+ NBC on basketball. It selects all three, which is why the TV window filter
holds a **list** rather than a single value — the dropdown writes a
one-element list, the button writes three.

Years read **2025** on football and **2025-26** on basketball — football is one
calendar year, basketball straddles two.

**Opening state is not an empty state.** Every tab opens on the newest season
available (whatever `harvest.py` last pulled), sorted **Oldest First** so a
season reads as it unfolded. **Newest First walks the blocks backwards but
reads each one forwards** — week 14, then 13, then 12, and inside a week the
Thursday game before the Saturday one. A football block is its week;
basketball has no week, so its block is the date. TV Windows opens with **Marquee Windows** on;
Key Games opens on **All Game Types**, so the whole year's shortlist is there
before any narrowing.

**Game type and TV window are built from the active sport tab**, because CFB
and CBB share none of their values — CFB offers 3 types and 5 windows, CBB 3
and 8.

His own tags (**College GameDay**, **Big Noon Kickoff**) are **details on the
row, not filter options**. Note that Big Noon Kickoff is FOX's pregame *show*
being on site — not the noon kickoff window, which is the TV window "FOX Big
Noon".

**The row** is variant C of the three mocked, minus the left rail: the winning
team's line takes a lightened wash of its colour, the loser's line stays plain.
Kyle chose it over washing the whole row, which turns a long list into a colour
chart.

**Row borders and italics, in one table.** Michigan's presence decides first,
and two rivals playing each other cancel out -- one of them had to win, so
colouring the winner would celebrate a rival.

| the game | border | teams |
|---|---|---|
| Michigan won | maize `#ffcb05` | upright |
| Michigan lost | grey `#5a5a62` | *italic* |
| a rival lost to anyone else | the winner's colour | upright |
| two rivals played each other | none | *italic* |
| a rival won | none | *italic* |
| nobody's team | none | upright |

**A coloured border flags a result he wants to see: Michigan won, or a rival
lost.** A full maize box was tried first and was too loud, so the frame carries
the flag and the winner's line keeps its own wash. A Michigan win is maize; a
rival losing takes **the colour of whoever beat them** — Penn State over
Michigan State reads Penn State slate. So an Oregon win over Ohio State is
marked with Michigan nowhere near it (17 such games in CFB alone), and a
Michigan loss is never flagged, including when a rival does it.

`brighten()` lifts each border to a fixed target luminance rather than
lightening by a fixed factor — at one factor Penn State's navy stayed muddy
while Indiana's red turned pink.

**The row** heads with what the game WAS, not when it was. Football reads
**`WEEK 1`**, or **`WEEK 1 | ABC PRIMETIME`** when the slot has a name — ESPN
carries `week.number` on every football event. Basketball has no week a viewer
thinks in, so it reads the window (**`SUPER TUESDAY`**) or, failing that, the
day (**`THURSDAY`**).

The **date moved out of the header** and into the top right (his call
2026-09-10), where it sits above the time and the network as a three-line
stack: date muted, time and network in white. The date leads with the weekday
UNLESS the header already named that day -- "THURSDAY", "SUPER TUESDAY" and
"WEEK 1 | FOX FRIDAY" all drop it, "FOX PRIMETIME" keeps it. Three lines against two team
lines cannot be row-matched, so `.meta` is a centred flex column rather than
the two-row grid it was when it held only two.

Only **one network** is shown. ESPN lists simulcasts alongside the broadcaster
— "NBC, Peacock", "CBS, Paramount+", "ESPN, ESPN+" — so `primaryNet()` ranks
the majors explicitly; alphabetical order would not do it (BTN would beat FOX).
The full list stays in the data, and the slot rules still read all of it, which
is what lets a "NBC, Peacock" game match the NBC window.

**TV window chips carry their network's colour** — FOX yellow, CBS a lighter
blue, NBC grey, ABC a darker blue, ESPN red, Peacock mirroring NBC. The mapping
is explicit in `rules.WINDOW_NET`: parsing the window name does not work, since
"Big Monday", "Super Tuesday" and "B1G Peacock" name no network at all.

No **game type** is drawn on any card, either view — the field survives only
to drive the Game Type filter.

**The purple chip is the conference championship OR the location, never both.**
A title game is played somewhere, but the title is the story; otherwise a
neutral-site game shows its city, which is also what tells you it was neutral
now that there is no neutral marker. An **OT** note follows where it applies.

Between those two sits a fourth case: a **home game played somewhere other
than the home team's own building**, which shows the VENUE rather than a city
— Michigan at Northwestern in **Wrigley Field**, Penn State at Michigan State
in **Ford Field**. ESPN calls neither neutral, because there is a home team,
so nothing in the payload says the venue is remarkable; `offsite_games()`
derives it by counting each home team's venues per season and flagging any it
used at most twice. See NOTES for why that is an absolute cutoff and not a
percentage.

**Tagging.** Tap any game for a sheet with the tag chips, a free-text box for
new tags, a note field, and an add/remove-from-archive toggle. Changes save to
the device immediately and batch into the sync bar.

**Sync.** `docs/tags.json` lives in the repo and the page writes it back
through GitHub's REST API, which is also CORS-open for `PUT` with an
`Authorization` header. So a tag added on the phone becomes a commit and every
device sees it. A save re-reads the current file first and merges, so two
devices don't clobber each other. The token is a fine-grained PAT scoped to
Contents:write on this repo alone, stored in the browser and pasted once per
device.

## Colours (`colors.py`)

Started fresh rather than reading sports-daily's `Colors` sheet tab, because a
**wash** and a **stripe** want different answers — those projects use maize for
Michigan, but a lightened maize is nearly the page's own ink, so the per-line
wash wants the navy.

Two overrides where ESPN is wrong (Syracuse returns navy for an orange school;
Texas returns a muddy tan for burnt orange) plus one rule: a **desaturated
near-black primary falls back to ESPN's alternate**, because nine schools
return `#000000` and every one of them would wash to the same grey. That rule
picks up Iowa's gold `#fcd116` on its own, which is what sports-daily uses.

## Files

| file | what it does |
|---|---|
| `rules.py` | the rule set, and only that |
| `harvest.py` | ESPN → `output/games.json` |
| `colors.py` | row-wash colour per team |
| `logos.py` | ported from sports-daily; measures both crest variants |
| `site.py` | builds `docs/` — HTML, icons, manifest, service worker |
| `app.js` | the whole client app; `site.py` fills its `__PLACEHOLDERS__` |
| `mock.py` | the three row treatments, for reference |
| `docs/tags.json` | **the shared state the app writes.** Never rebuilt |
| `cache/` | raw ESPN responses (gitignored, ~600 MB) |
