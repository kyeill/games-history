"""Three row treatments for the archive, rendered with real games.

Kyle's open question is how the winning team's colour should wash the row, so
all three variants show the SAME eight games and differ only in that.
Palette, fonts and crest handling are sports-daily's, deliberately.
"""
import base64
import json
import os

import requests

import logos

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
CARD_BG = (0x1E, 0x1E, 0x23)

# ESPN's own colour is wrong or unusable for a few schools, exactly as
# sports-daily's team_colors block records. Keep this list short.
COLOR_OVERRIDES = {"251": "bf5700"}      # Texas: ESPN's af5c37 is a muddy tan

PICKS = [
    ("2025-11-29", "130"),   # #1 Ohio State at #15 Michigan, FOX Big Noon
    ("2025-12-06", "194"),   # Indiana-Ohio State, Big Ten Championship, neutral
    ("2025-10-11", "2483"),  # #7 Indiana at #3 Oregon, CBS 3:30
    ("2025-08-30", "52"),    # #8 Alabama at Florida State, top-10 upset
    ("2025-09-27", "213"),   # #6 Oregon at #3 Penn State, NBC 7:30
    ("2026-02-17", "2509"),  # #1 Michigan at #7 Purdue, Peacock B1G
    ("2026-03-15", "130"),   # Big Ten Tournament final, CBS
    ("2024-01-09", "158"),   # #1 Purdue at Nebraska, #1 loses
]


def row_shade(hexcolor, lighten=0.42, strength=0.34):
    """A readable wash of a team's colour over the card background.

    Lightened towards white first (Michigan navy and Michigan State green are
    otherwise invisible on #1e1e23), then laid over the card at partial
    strength so text on top stays readable. Ported from standings/site.py.
    """
    r, g, b = (int(hexcolor[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(c + (255 - c) * lighten) for c in (r, g, b))
    return "#%02x%02x%02x" % tuple(
        int(bg + (c - bg) * strength) for bg, c in zip(CARD_BG, (r, g, b)))


def edge(hexcolor, lighten=0.30):
    r, g, b = (int(hexcolor[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(int(c + (255 - c) * lighten) for c in (r, g, b))


def crests(team_ids, session):
    out = {}
    for tid in team_ids:
        url, _why = logos.choose(
            "https://a.espncdn.com/i/teamlogos/ncaa/500-dark/%s.png" % tid,
            "https://a.espncdn.com/i/teamlogos/ncaa/500/%s.png" % tid, session)
        raw = session.get(url, timeout=30).content
        out[tid] = "data:image/png;base64," + base64.b64encode(raw).decode()
    return out


def pick_games(games):
    chosen = []
    for date, tid in PICKS:
        for g in games:
            if g["date"] == date and any(t["id"] == tid for t in g["teams"]):
                chosen.append(g)
                break
    return chosen


def color_of(tid, teams):
    return COLOR_OVERRIDES.get(tid) or teams[tid]["color"] or "6a6a70"


def tags_of(g):
    out = [("slot", s) for s in g["slots"]] + [("big", b) for b in g["big"]]
    if g["champ"]:
        head = g["round"] or ""
        rnd = head.split(" - ")[-1] if " - " in head else "Championship"
        out.append(("champ", "%s %s" % (g["champ"], rnd)))
    return out


def chip(kind, text):
    return '<span class="tag t-%s">%s</span>' % (kind, text)


def team_line(t, teams, art):
    c = teams[t["id"]]
    rank = '<span class="rk">%s</span>' % (t["rank"] or "")
    won = " won" if t["win"] else ""
    return ('<div class="tl%s">'
            '<img class="crest" src="%s" alt="">'
            '%s<span class="nm">%s</span>'
            '<span class="sc">%s</span></div>'
            % (won, art[t["id"]], rank, c["short"], t["score"]))


def meta(g):
    nets = ", ".join(g["nets"][:2]) or "&mdash;"
    hh, mm = g["time"].split(":")
    h12 = int(hh) % 12 or 12
    ampm = "am" if int(hh) < 12 else "pm"
    when = "%s %s/%s" % (g["dow"], g["date"][5:7].lstrip("0"),
                         g["date"][8:10].lstrip("0"))
    yr = g["date"][2:4]
    site = ('<div class="site">%s</div>' % g["city"]
            if g["neutral"] and g["city"] else "")
    return ('<div class="meta"><div class="when">%s/%s</div>'
            '<div class="tm">%s:%s%s</div>'
            '<div class="net">%s</div>%s</div>'
            % (when, yr, h12, mm, ampm, nets, site))


def render_rows(games, teams, art, variant):
    html = []
    for g in games:
        home, away = g["teams"][0], g["teams"][1]
        win = home if home["win"] else away
        wc = color_of(win["id"], teams)
        shade, rail = row_shade(wc), edge(wc)
        tg = "".join(chip(k, t) for k, t in tags_of(g))
        neutral = ' <span class="nu">neutral</span>' if g["neutral"] else ""

        if variant == "A":       # left rail only, card stays neutral
            style = "border-left:3px solid %s" % rail
        elif variant == "B":     # whole row washed in the winner's colour
            style = "background:%s" % shade
        else:                    # C: winner's line tinted, loser's plain
            style = "--winwash:%s;--winrail:%s" % (shade, rail)

        html.append(
            '<article class="row v%s" style="%s">'
            '<div class="sport">%s%s</div>'
            '<div class="teams">%s%s</div>'
            '%s'
            '<div class="tags">%s</div>'
            '</article>'
            % (variant, style, g["sport"], neutral,
               team_line(away, teams, art), team_line(home, teams, art),
               meta(g), tg))
    return "\n".join(html)


CSS = """
:root{
  --bg:#16161a; --card:#1e1e23; --ink:#ececea; --muted:#9a9a95;
  --line:#2b2b31; --rank:#8fb0d8; --accent:#e0834f;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"Source Sans 3",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:15px;line-height:1.45;-webkit-font-smoothing:antialiased}
.wrap{max-width:880px;margin:0 auto;padding:28px 18px 70px}
h1{font-size:27px;margin:0;letter-spacing:-.2px;text-wrap:balance}
.sub{color:var(--muted);margin:4px 0 0;font-size:15px;max-width:62ch}
.stats{display:flex;flex-wrap:wrap;gap:14px 26px;margin:18px 0 0;
  padding:13px 0;border-top:1px solid var(--line);
  border-bottom:1px solid var(--line)}
.stat b{font-size:19px;font-variant-numeric:tabular-nums;display:block;
  font-weight:600;line-height:1.2}
.stat span{color:var(--muted);font-size:11.5px;text-transform:uppercase;
  letter-spacing:.06em}

h2{font-size:14px;text-transform:uppercase;letter-spacing:.09em;
  color:var(--muted);margin:46px 0 3px;font-weight:700}
.lede{color:var(--muted);font-size:14px;margin:0 0 15px;max-width:64ch}
.lede b{color:var(--ink);font-weight:600}

.filters{display:flex;flex-wrap:wrap;gap:7px;margin:14px 0 0}
.f{border:1px solid var(--line);background:var(--card);color:var(--muted);
  border-radius:999px;padding:4px 11px;font-size:13px}
.f.on{background:#2e3a48;border-color:#3f5064;color:#cfe0f2}

.row{display:grid;background:var(--card);border:1px solid var(--line);
  border-radius:9px;margin:8px 0;padding:10px 13px;
  grid-template-columns:1fr auto;
  grid-template-areas:"sport meta" "teams meta" "tags tags";
  column-gap:14px;align-items:start}
.sport{grid-area:sport;font-size:11px;font-weight:700;letter-spacing:.09em;
  color:var(--muted);text-transform:uppercase;margin-bottom:5px}
.nu{color:var(--accent);font-weight:600;letter-spacing:.05em}
.teams{grid-area:teams;display:flex;flex-direction:column;gap:3px}
.tl{display:grid;grid-template-columns:22px 24px 1fr auto;align-items:center;
  gap:8px;padding:2px 6px 2px 2px;border-radius:5px}
.crest{width:21px;height:21px;object-fit:contain;display:block}
.rk{color:var(--rank);font-size:12.5px;font-weight:600;
  font-variant-numeric:tabular-nums;text-align:right}
.rk:not(:empty)::before{content:"#"}
.nm{font-size:15.5px}
.tl.won .nm{font-weight:600}
.tl:not(.won) .nm,.tl:not(.won) .sc{color:#a5a5a0}
.sc{font-size:16px;font-variant-numeric:tabular-nums;font-weight:600;
  min-width:30px;text-align:right}
.meta{grid-area:meta;text-align:right;padding-left:14px;
  border-left:1px solid var(--line);min-width:120px;align-self:stretch}
.when,.tm{font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
.net{font-size:13px;margin-top:2px}
.site{font-size:12px;color:var(--muted);margin-top:2px}
.tags{grid-area:tags;display:flex;flex-wrap:wrap;gap:5px;margin-top:9px}
.tag{font-size:11.5px;border-radius:4px;padding:2px 7px;letter-spacing:.02em;
  border:1px solid transparent;white-space:nowrap}
.t-slot{background:#232f3a;border-color:#31414f;color:#a9c6dd}
.t-big{background:#33261f;border-color:#4a382c;color:#e0a983}
.t-champ{background:#26202f;border-color:#3a3145;color:#bda9d4}
.t-mine{background:#1f2e28;border-color:#2f4539;color:#9ecab0}

.vC .tl.won{background:var(--winwash);box-shadow:inset 2px 0 0 var(--winrail)}

footer{margin-top:54px;padding-top:16px;border-top:1px solid var(--line);
  color:var(--muted);font-size:12.5px;max-width:64ch}
@media (max-width:560px){
  .row{grid-template-columns:1fr;
    grid-template-areas:"sport" "teams" "meta" "tags"}
  .meta{text-align:left;border-left:0;padding-left:0;margin-top:7px;
    display:flex;gap:12px}
  .nm{font-size:15px}
}
"""

VARIANTS = [
    ("A", "A &mdash; colour on the edge only",
     "The card stays neutral and the winner's colour reads as a 3px rail. "
     "Quietest of the three; the crest and the rank do the identifying work. "
     "Closest to how <b>Standings</b> draws its cut line."),
    ("B", "B &mdash; the whole row washed",
     "Your stated preference: the full row takes a lightened wash of the "
     "winning team's colour. Strongest at a glance, but with eight rows "
     "stacked the page becomes a colour chart, and two schools with similar "
     "colours stop being distinguishable."),
    ("C", "C &mdash; winner's line tinted, loser's plain",
     "A split treatment: the wash sits only on the winning team's line, so the "
     "row still reads as one game but the result is legible without looking at "
     "the score. Stays calm at eight rows and at eighty."),
]

FILTER_CHIPS = [
    ("All sports", True), ("CFB", False), ("CBB", False),
    ("2021-22", False), ("2022-23", False), ("2023-24", False),
    ("2024-25", False), ("2025-26", True),
    ("FOX Big Noon", False), ("CBS 3:30", False), ("ABC Saturday", False),
    ("Peacock B1G", True), ("top-10 upset", False), ("#1 loses", False),
    ("attended", False), ("home-and-home", False),
]


def build():
    data = json.load(open(os.path.join(OUT, "games.json"), encoding="utf-8"))
    games, teams = data["games"], data["teams"]
    picks = pick_games(games)
    ids = sorted({t["id"] for g in picks for t in g["teams"]})
    session = requests.Session()
    art = crests(ids, session)

    n_cfb = sum(1 for g in games if g["sport"] == "CFB")
    n_slot = sum(1 for g in games if g["slots"])
    n_big = sum(1 for g in games if g["big"])
    n_champ = sum(1 for g in games if g["champ"])

    stats = [(len(games), "games in archive"), (n_cfb, "college football"),
             (len(games) - n_cfb, "college basketball"),
             (n_slot, "matched a TV slot"), (n_big, "matched a big-game rule"),
             (n_champ, "conference title games"), (len(teams), "teams")]
    stat_html = "".join('<div class="stat"><b>%s</b><span>%s</span></div>'
                        % ("{:,}".format(n), lbl) for n, lbl in stats)
    filt = "".join('<span class="f%s">%s</span>' % (" on" if on else "", t)
                   for t, on in FILTER_CHIPS)
    blocks = "".join('<h2>%s</h2><p class="lede">%s</p>%s'
                     % (title, note, render_rows(picks, teams, art, v))
                     for v, title, note in VARIANTS)

    html = """<title>Archive Row Treatments</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap">
<style>%s</style>
<div class="wrap">
<h1>Archive row treatments</h1>
<p class="sub">Three ways to colour a row, with the same eight real games in
each. Palette, crests and type are Sports Daily's.</p>

<div class="stats">%s</div>

<h2>Filter bar</h2>
<p class="lede">One treatment, shown once: sport, then season, then the slot
and big-game tags the rules assign, then your own. Lit chips are active.</p>
<div class="filters">%s</div>

%s

<footer>Real games from the harvest, 2021-22 through 2025-26. Ranks are the
teams' rankings on the day the game was played, not their final ones. Texas is
the one colour overridden so far, because ESPN returns a muddy tan for burnt
orange.</footer>
</div>
""" % (CSS, stat_html, filt, blocks)

    path = os.path.join(OUT, "mockups.html")
    open(path, "w", encoding="utf-8").write(html)
    print("%s  (%.0f KB, %d crests inlined)"
          % (path, len(html) / 1024, len(ids)))


if __name__ == "__main__":
    build()
