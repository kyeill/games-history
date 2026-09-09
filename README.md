# Games History

A browsable archive of past college football and college basketball games that
meet Kyle's criteria, 2021 through 2025-26. Two dimensions, which may overlap:
**TV slots** (a recurring broadcast window) and **big games** (ranking-driven),
plus Power Five conference championships. Every game can also carry his own
tags, editable from the app on any device.

Read `NOTES.md` before changing anything — it records each trap that already
cost a debugging pass.

Live at **https://kyeill.github.io/games-history/** (once the repo exists).

## The shape of the thing

Past games never change. So unlike [sports-daily](../sports-daily) and
[standings](../standings), this project **fetches once and freezes** — there is
no daily build, no cron, and nothing goes stale. `cache/` holds the raw ESPN
responses, so a re-harvest costs nothing.

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

Settled 2026-09-09. Postseason is excluded everywhere — bowls, the CFP and the
NCAA tournament are all ESPN season type 3. Conference championships and
conference tournaments are type 2 and **are** included, all rounds.

**CFB slots** — FOX Friday night · FOX Big Noon · CBS 3:30 · NBC 7:30 ·
ABC Saturday.

**CBB slots** — ESPN Mon night · ESPN Tue night · ESPN Sat night · FOX · CBS ·
NBC · ABC · Peacock B1G.

`Peacock B1G` is narrowed to **Big Ten vs Big Ten, Tue/Thu, at least one ranked
team**. Peacock alone carries every Big Ten home non-conference game and
returned 246 games including Alcorn State at Minnesota; the narrowed rule
returns 39.

**Big games** (both sports) — #1 loses · top-10 vs top-10 · ranked vs ranked
with at least one Big Ten team · top-10 loses to an unranked team.

**Power Five titles** — ACC, Big Ten, Big 12, SEC, Pac-12 championship games
(CFB) and conference tournaments (CBB), every round.

### What the rules actually return

1,733 games — CFB 470, CBB 1,263 — across 150 teams.

| | 21-22 | 22-23 | 23-24 | 24-25 | 25-26 |
|---|---|---|---|---|---|
| CFB slots | 69 | 74 | 84 | 99 | 96 |
| CBB slots | 134 | ~150 | 186 | 238 | 290 |
| Big games (CFB) | 29 | 20 | 15 | 29 | 28 |
| Big games (CBB) | 51 | 47 | 84 | 87 | 70 |

Several slots have **no history before 2023-24** and this is real, not missing
data: NBC 7:30 began with Big Ten Saturday Night in 2023, FOX Friday in 2024,
and Peacock's Big Ten package in 2023-24. Early seasons lean on ABC/CBS/FOX.

## The app (`docs/`)

A static GitHub Pages PWA, installable, dark only, Sports Daily's visual
language throughout — `#16161a` ground, `#1e1e23` cards, `--rank` blue `#8fb0d8`
for rankings, Source Sans 3, and `logos.py`'s measured crest variants.

**Three tabs.** *Slots* and *Big Games* are the rule-driven collections.
*Browse* takes a date range and queries **ESPN live from the browser** — ESPN
sends `Access-Control-Allow-Origin: *`, so the page can call it directly and
the site never ships all ~35,000 games. Anything found there can be pulled into
the archive by hand.

**The row** is variant C of the three mocked: the winning team's line takes a
lightened wash of its colour, the loser's line stays plain. Kyle chose it over
washing the whole row (which turns a long list into a colour chart) and asked
for the left rail to come off.

**Filters** are Kyle's six dimensions, 2026-09-09. Five are derived from the
data and one is typed:

| filter | where it comes from |
|---|---|
| Sport | CFB / CBB |
| Year | season |
| Game type | `rules.game_type` — **Upset** (unranked beats a ranked team), **Ranked Win** (both ranked, better rank won), **Ranked Upset** (both ranked, worse rank won) |
| TV window | whichever slot rule matched |
| Team | a `<select>`, not chips — 150 of them |
| Tag | OT, neutral, the conference titles, and his own tags |

Game type is a partition: a game gets at most one, and a ranked team beating an
unranked one gets none, which is the point. Counts across the archive are
Ranked Win 251, Ranked Upset 195, Upset 297.

**Tagging.** Tap any game for a sheet with the tag chips, a free-text box for
new tags, a note field, and an add/remove-from-archive toggle. Changes save to
the device immediately and batch into the sync bar. The starter tags are the
three he wanted — **College GameDay**, **Big Noon Kickoff** (FOX's pregame
*show* being on site, not the noon kickoff window, which is the TV window "FOX
Big Noon") and **home and home** — and any other can be typed in.

**Sync.** `tags.json` lives **in the repo** and the page writes it back through
GitHub's REST API, which is also CORS-open for `PUT` with an `Authorization`
header. So a tag added on the phone becomes a commit and every device sees it.
A save re-reads the current file first and merges, so two devices don't
clobber each other. The token is a fine-grained PAT scoped to Contents:write on
this repo alone, stored in the browser and pasted once per device.

## Colours (`colors.py`)

Started fresh rather than reading sports-daily's `Colors` sheet tab, because a
**wash** and a **stripe** want different answers — those projects use maize for
Michigan, but a lightened maize is nearly the page's own ink, so the wash wants
the navy.

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
| `cache/` | raw ESPN responses (gitignored) |
