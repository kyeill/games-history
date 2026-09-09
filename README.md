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

**CFB** — FOX Friday night · FOX Big Noon · CBS 3:30 · NBC 7:30 · ABC Saturday.

**CBB** — ESPN Mon night · ESPN Tue night · ESPN Sat night · FOX · CBS · NBC ·
ABC · Peacock B1G.

`Peacock B1G` is narrowed to **Big Ten vs Big Ten, Tue/Thu, at least one ranked
team**. Peacock alone carries every Big Ten home non-conference game and
returned 246 games including Alcorn State at Minnesota; the narrowed rule
returns 39.

### Game types — and they differ by sport

Kyle's definitions, 2026-09-09. A game gets **at most one**, and membership of
the Big Games tab is exactly "has one, or is a conference title game". The
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
| Ranked Big Ten | any *other* ranked v ranked with a Big Ten team | 83 |

CBB casts a tighter net on purpose — college basketball is far the bigger
slate. An unranked win over a CBB #7 is deliberately *not* a category.

**Power Five titles** — ACC, Big Ten, Big 12, SEC, Pac-12 championship games
(CFB) and conference tournaments (CBB), every round.

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

**Three tabs.** *Slots* and *Big Games* are the rule-driven collections.
*Browse* takes a date range and queries **ESPN live from the browser** — ESPN
sends `Access-Control-Allow-Origin: *`, so the page can call it directly and
the site never ships all ~35,000 games. Anything found there can be pulled into
the archive by hand.

**The Big Games tab hides what he does not want to relive:** no Michigan
losses, and no Ohio State, Michigan State or Notre Dame wins. Both still appear
on the Slots tab, which is a record of what was *on*, not a highlight reel.
598 games pass; the Slots tab still carries the 31 Michigan losses and 115
rival wins.

**Filters** are a sport toggle plus five dropdowns — his call, 2026-09-09:

| filter | control | source |
|---|---|---|
| Sport | buttons | CFB / CBB |
| Year | dropdown | season |
| Game type | dropdown | `rules.game_type` |
| TV window | dropdown | whichever slot rule matched |
| Team | dropdown | 147 of them |
| Tag | dropdown | overtime, neutral site, conference titles |

**Game type and TV window follow the sport toggle**, because CFB and CBB share
none of their values — CFB offers 3 types and 5 windows, CBB 3 and 8. That is
what lets one pair of tabs serve both sports instead of two. Switching sport
clears both, or a leftover value would silently filter everything away.

His own tags (**College GameDay**, **Big Noon Kickoff**) are **details on the
row, not filter options**. Note that Big Noon Kickoff is FOX's pregame *show*
being on site — not the noon kickoff window, which is the TV window "FOX Big
Noon".

**The row** is variant C of the three mocked, minus the left rail: the winning
team's line takes a lightened wash of its colour, the loser's line stays plain.
Kyle chose it over washing the whole row, which turns a long list into a colour
chart. **The exception is a Michigan win, which takes the whole box in maize** —
maize is right for a full box and wrong for a single line, which is the same
reason `colors.py` keeps ESPN's navy for the per-line wash.

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
