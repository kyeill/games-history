"""Build the Games History app into docs/, which GitHub Pages serves.

A static GitHub Pages PWA. Three tabs: the two rule-driven collections Kyle
defined (TV slots, big games) and a Browse mode that queries ESPN live so any
game can be pulled in by hand -- ESPN sends
`Access-Control-Allow-Origin: *`, so the browser can call it directly and the
site never has to ship all ~35,000 games.

Tags live in tags.json IN THE REPO, which the page writes back to through
GitHub's REST API (also CORS-open for PUT with an Authorization header). So a
tag added on the phone is a commit, and every device sees it.
"""
import json
import os
import shutil
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
# GitHub Pages serves this folder directly from the default branch, so the
# project needs no Actions workflow at all -- there is no daily build.
SITE = os.path.join(HERE, "docs")

REPO = "kyeill/games-history"      # where tags.json is committed
# The page fetches "tags.json" relative to itself (= docs/tags.json once
# Pages serves docs/ as the site root), so the API path must match or a save
# would write a file the app never reads.
TAGS_PATH = "docs/tags.json"

# The manual tags. These are DETAILS shown on a row, deliberately NOT filter
# options -- his call 2026-09-09, along with dropping "home and home", which he
# would rather write in a note. "Big Noon Kickoff" is FOX's pregame SHOW being
# on site, not the noon kickoff window itself (that is the TV window "FOX Big
# Noon"). Any other tag can still be typed into the sheet.
STARTER_TAGS = [
    "Big Noon Kickoff", "College GameDay", "Home & Home", "Neutral & Neutral",
    "Home & Neutral", "Annual", "Buy Game",
]

CSS = """
:root{
  --bg:#16161a; --card:#1e1e23; --ink:#ececea; --muted:#9a9a95;
  --line:#2b2b31; --rank:#8fb0d8; --accent:#e0834f; --ok:#7fb98a;
  --sheet:#212127;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"Source Sans 3",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:15px;line-height:1.45;-webkit-font-smoothing:antialiased;
  overscroll-behavior-y:none}
.wrap{max-width:1180px;margin:0 auto;padding:0 14px 90px}

/* h1 and the count share a baseline, so both need the SAME line-height --
   otherwise flex computes the baseline off different boxes and the count
   rides low against the title. */
header{display:flex;align-items:baseline;gap:9px;padding:18px 0 10px}
h1{font-size:22px;margin:0;letter-spacing:-.2px;font-weight:700;line-height:1.2}
.count{color:var(--muted);font-size:13.5px;font-variant-numeric:tabular-nums;
  line-height:1.2}
.spacer{flex:1}
.iconbtn{background:none;border:1px solid var(--line);color:var(--muted);
  border-radius:7px;padding:4px 9px;font:inherit;font-size:13px;cursor:pointer}
.iconbtn:hover{color:var(--ink);border-color:#3b3b43}
.iconbtn:focus-visible{outline:2px solid var(--rank);outline-offset:2px}

nav{position:sticky;top:0;z-index:6;background:var(--bg);display:flex;gap:2px;
  border-bottom:1px solid var(--line);margin-bottom:10px}
nav button{flex:1;background:none;border:0;border-bottom:2px solid transparent;
  color:var(--muted);font:inherit;font-size:14.5px;font-weight:600;
  padding:9px 4px;cursor:pointer}
nav button[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--accent)}
nav button:focus-visible{outline:2px solid var(--rank);outline-offset:-2px}

/* the two populations within a sport -- a segmented control, not more tabs,
   so the sport stays put while he switches which view of it he is reading */
.viewbar{display:inline-flex;gap:0;margin:0 0 12px;border:1px solid var(--line);
  border-radius:8px;overflow:hidden;background:var(--card)}
.viewbar button{background:none;border:0;color:var(--muted);font:inherit;
  font-size:13.5px;font-weight:600;padding:6px 16px;cursor:pointer}
.viewbar button[aria-selected="true"]{background:#2e3a48;color:#cfe0f2}
.viewbar button:focus-visible{outline:2px solid var(--rank);outline-offset:-2px}

.filters{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 12px}
.f{border:1px solid var(--line);background:var(--card);color:var(--muted);
  border-radius:999px;padding:3px 11px;font:inherit;font-size:13px;
  cursor:pointer;white-space:nowrap}
.f[aria-pressed="true"]{background:#2e3a48;border-color:#3f5064;color:#cfe0f2}
.f:focus-visible{outline:2px solid var(--rank);outline-offset:2px}
.fgroup{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.fsel{background:var(--card);border:1px solid var(--line);color:var(--ink);
  border-radius:999px;padding:4px 10px;font:inherit;font-size:13px;
  max-width:210px;cursor:pointer}
.fsel:focus-visible{outline:2px solid var(--rank);outline-offset:2px}
.flabel{font-size:11px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--muted);font-weight:700;margin-right:2px}
/* the quick-action group carries no label, so it must not keep the gap */
.flabel:empty{margin-right:0}

/* one column on a phone, two from 900px -- the gap replaces the row margin */
#list{display:grid;grid-template-columns:1fr;gap:8px;align-content:start}
@media (min-width:900px){#list{grid-template-columns:1fr 1fr;gap:9px}}
/* Three across once there is room for it. The card gives up width in the
   places that were padding rather than content: the gutter to the meta
   column, the card's own side padding, and the meta column's floor. */
@media (min-width:1240px){
  #list{grid-template-columns:repeat(3,1fr);gap:9px}
  #list .row{padding:10px 11px;column-gap:10px}
  #list .meta{min-width:72px;padding-left:10px}
}
#list .empty{grid-column:1/-1}

.row{display:grid;background:var(--card);border:1px solid var(--line);
  border-radius:9px;padding:10px 13px;
  grid-template-columns:1fr auto;
  /* meta occupies ONLY the teams row, so its two rows can be made to match
     the two team lines exactly. Spanning the header row too put it 64px out. */
  grid-template-areas:"sport sport" "teams meta" "tags tags";
  /* align-content:start is what makes the meta column line up. A card is
     stretched to the height of the tallest card beside it, and the default
     align-content:stretch spreads that slack across ALL THREE tracks -- so
     the teams row grew ~10px taller than the team lines and meta's 1fr/1fr
     split no longer matched them. Sending the slack to the bottom instead
     keeps every track at its content height. */
  column-gap:14px;align-items:start;align-content:start;
  cursor:pointer;text-align:left;
  width:100%;font:inherit;color:inherit}
.row:hover{border-color:#3b3b43}
.row:focus-visible{outline:2px solid var(--rank);outline-offset:2px}
/* week + date, where the sport label used to be */
/* The header row carries the slot label at the left and the DATE at the
   right, where it lines up with the network and time in the column below. */
.sport{grid-area:sport;display:flex;align-items:baseline;
  justify-content:space-between;gap:10px;
  font-size:11.5px;font-weight:500;letter-spacing:.05em;
  text-transform:uppercase;color:var(--muted);margin-bottom:5px}
.hdate{flex:none;font-size:13px;font-weight:500;letter-spacing:0;
  text-transform:none;color:var(--muted);font-variant-numeric:tabular-nums}
/* the week takes the header's colour, tinted or plain -- no orange of its own
   (his call: an untinted header should read entirely plain) */
.teams{grid-area:teams;display:flex;flex-direction:column;gap:3px}
.tl{display:grid;grid-template-columns:22px 24px 1fr auto;align-items:center;
  gap:8px;padding:2px 6px 2px 7px;margin-left:-7px;border-radius:5px}
.tl.won{background:var(--winwash)}
/* A coloured border marks a result he wants to see: Michigan won (maize), or a
   rival lost (the colour of whoever beat them). A full maize box was too loud,
   so the winner's line keeps its own wash and only the frame carries the flag.
   Both colours are computed per row in app.js -- do NOT hardcode maize here,
   which is exactly the bug that made every border look like a Michigan win. */
.row.celebrate{border-color:var(--celeb,#ffcb05);
  box-shadow:0 0 0 1px var(--celebring,#ffcb0544)}
.row.celebrate:hover{filter:brightness(1.12)}
/* a Michigan loss: dashed and muted, never mistaken for a grey winner */
.row.celebrate.mloss{border-style:dashed;box-shadow:none}
/* a rival won, or Michigan lost: both team lines go italic */
.row.dimmed .nm{font-style:italic}
.crest{width:21px;height:21px;object-fit:contain;display:block}
.rk{color:var(--rank);font-size:12.5px;font-weight:600;
  font-variant-numeric:tabular-nums;text-align:right}
.rk:not(:empty)::before{content:"#"}
/* rankings: orange on an upset (Sports Daily's accent), grey when Michigan lost */
.row.rk-upset .rk{color:var(--accent)}
.row.rk-mloss .rk{color:var(--muted)}
.nm{font-size:15.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tl.won .nm{font-weight:600}
/* overtime: the winning score is underlined, instead of an OT chip */
.row.ot .tl.won .sc{text-decoration:underline;text-underline-offset:3px;
  text-decoration-thickness:2px}
.tl:not(.won) .nm,.tl:not(.won) .sc{color:#a5a5a0}
.sc{font-size:16px;font-variant-numeric:tabular-nums;font-weight:600;
  min-width:30px;text-align:right}
/* just the kickoff time now -- the network moved back to the bottom left */
/* Network on the away team's line, time on the home team's. Same row count
   and gap as .tl, so the two columns line up exactly. */
/* Two rows against the two team lines: network on the away line, time on the
   home line. The date is NOT here -- it sits in the header row above, which is
   the only way it can align with the header. */
.meta{grid-area:meta;padding-left:14px;border-left:1px solid var(--line);
  min-width:92px;align-self:stretch;display:grid;grid-template-rows:1fr 1fr;gap:3px}
.mrow{display:flex;align-items:center;justify-content:flex-end;
  font-size:13px;color:var(--ink);font-variant-numeric:tabular-nums}
.tags{grid-area:tags;display:flex;flex-wrap:wrap;gap:5px;margin-top:9px;
  align-items:center}
.tags:empty{display:none}
.tag{font-size:11.5px;border-radius:4px;padding:2px 7px;letter-spacing:.02em;
  border:1px solid transparent;white-space:nowrap}
/* TV window chips carry the network's own colour: FOX yellow, CBS a lighter
   blue, NBC grey, ABC a darker blue. Anything else (ESPN, Peacock) keeps the
   default slate. */
.t-slot{background:#232f3a;border-color:#31414f;color:#a9c6dd}
.t-slot.n-fox{background:#3a3218;border-color:#584a1d;color:#e8c766}
.t-slot.n-cbs{background:#1b3340;border-color:#2b4d61;color:#8fc9e4}
.t-slot.n-nbc{background:#2c2c31;border-color:#414147;color:#bcbcb7}
.t-slot.n-abc{background:#1b2440;border-color:#2b3860;color:#93a9dc}
.t-slot.n-espn{background:#3a1d1f;border-color:#5a2c2f;color:#e69a9a}
.t-big{background:#33261f;border-color:#4a382c;color:#e0a983}
/* conference championship / event name / neutral-site location -- BLUE,
   his call 2026-09-09 (it was purple) */
.t-champ{background:#1b2a40;border-color:#2c4265;color:#9dbde8}
.t-mine{background:#1f2e28;border-color:#2f4539;color:#9ecab0}
.t-mine.g-yellow{background:#3a3218;border-color:#584a1d;color:#e8c766}
.t-mine.g-red{background:#3a1d1f;border-color:#5a2c2f;color:#e69a9a}
.t-mine.g-grey{background:#2c2c31;border-color:#414147;color:#bcbcb7}
.t-grey{background:#2c2c31;border-color:#414147;color:#bcbcb7}

.empty{color:var(--muted);text-align:center;padding:44px 10px;font-size:14.5px}
.daterow{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 12px}
.daterow input{background:var(--card);border:1px solid var(--line);
  color:var(--ink);border-radius:7px;padding:5px 9px;font:inherit;font-size:14px}
.daterow input:focus-visible{outline:2px solid var(--rank);outline-offset:1px}
.go{background:#2e3a48;border:1px solid #3f5064;color:#cfe0f2;border-radius:7px;
  padding:5px 14px;font:inherit;font-size:14px;font-weight:600;cursor:pointer}
.inarch{color:var(--ok);font-size:11.5px;font-weight:700;letter-spacing:.05em}

/* bottom sheet: tag editor + settings */
.scrim{position:fixed;inset:0;background:#000a;z-index:20;display:none}
.scrim.on{display:block}
.sheet{position:fixed;left:0;right:0;bottom:0;z-index:21;background:var(--sheet);
  border-top:1px solid var(--line);border-radius:14px 14px 0 0;
  padding:16px 16px calc(18px + env(safe-area-inset-bottom));
  max-height:82vh;overflow-y:auto;display:none;
  max-width:880px;margin:0 auto}
.sheet.on{display:block}
.sheet h3{margin:0 0 3px;font-size:17px}
.sheet .sub{color:var(--muted);font-size:13.5px;margin:0 0 14px}
.sheet label{display:block;font-size:11px;text-transform:uppercase;
  letter-spacing:.07em;color:var(--muted);font-weight:700;margin:14px 0 6px}
.sheet input[type=text],.sheet input[type=password],.sheet textarea{
  width:100%;background:var(--card);border:1px solid var(--line);
  color:var(--ink);border-radius:7px;padding:7px 10px;font:inherit;font-size:14px}
.sheet textarea{min-height:56px;resize:vertical}
.tagpick{display:flex;flex-wrap:wrap;gap:6px}
.done{margin-top:16px;width:100%;background:#2e3a48;border:1px solid #3f5064;
  color:#cfe0f2;border-radius:8px;padding:9px;font:inherit;font-size:15px;
  font-weight:600;cursor:pointer}
.danger{color:var(--accent);font-size:13px;margin-top:10px}
.hint{color:var(--muted);font-size:12.5px;margin-top:8px}
.hint code{background:var(--card);padding:1px 5px;border-radius:4px;
  font-size:12px}

.syncbar{position:fixed;left:0;right:0;bottom:0;z-index:10;
  background:#232830;border-top:1px solid #333a45;
  padding:9px 14px calc(9px + env(safe-area-inset-bottom));
  display:none;align-items:center;gap:12px;justify-content:center}
.syncbar.on{display:flex}
.syncbar span{font-size:14px}
.syncbar button{background:#3a5570;border:1px solid #4a6a8a;color:#dceaf7;
  border-radius:7px;padding:5px 14px;font:inherit;font-size:14px;
  font-weight:600;cursor:pointer}
.toast{position:fixed;left:50%;transform:translateX(-50%);bottom:74px;z-index:30;
  background:#2b3a2e;border:1px solid #3d5442;color:#c8e6cf;padding:8px 16px;
  border-radius:8px;font-size:14px;display:none}
.toast.on{display:block}
.toast.bad{background:#3a2a28;border-color:#54413d;color:#e6cdc8}

@media (max-width:560px){
  /* the phone keeps the two columns -- the meta side is only ~90px wide and
     stacking it would lose the away/home alignment that is the point of it */
  .row{column-gap:10px}
  .meta{min-width:78px;padding-left:10px}
  h1{font-size:20px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

BODY = """
<div class="wrap">
<header>
  <h1>Games History</h1>
  <span class="count" id="count"></span>
  <span class="spacer"></span>
  <button class="iconbtn" id="clearbtn">Clear Filters</button>
  <button class="iconbtn" id="settingsbtn">Settings</button>
</header>

<nav>
  <button data-tab="cfb" aria-selected="true">College Football</button>
  <button data-tab="cbb" aria-selected="false">College Basketball</button>
  <button data-tab="browse" aria-selected="false">Browse</button>
</nav>

<div class="viewbar" id="viewbar">
  <button data-view="tv" aria-selected="true">TV Windows</button>
  <button data-view="big" aria-selected="false">Key Games</button>
  <button data-view="rivals" aria-selected="false">Rivals</button>
</div>

<div class="daterow" id="daterow" style="display:none">
  <input type="date" id="from" aria-label="From date">
  <input type="date" id="to" aria-label="To date">
  <button class="go" id="goload">Load</button>
</div>

<div class="filters" id="filters"></div>
<div id="list"></div>
</div>

<div class="scrim" id="scrim"></div>

<div class="sheet" id="sheet">
  <h3 id="sh-title"></h3>
  <p class="sub" id="sh-sub"></p>
  <label>Your tags</label>
  <div class="tagpick" id="sh-tags"></div>
  <label for="sh-new">Add a tag</label>
  <div class="daterow" style="display:flex">
    <input type="text" id="sh-new" placeholder="e.g. snow game"
           style="flex:1;min-width:140px">
    <button class="go" id="sh-add">Add</button>
  </div>
  <label for="sh-note">Note</label>
  <textarea id="sh-note" placeholder="Anything worth remembering"></textarea>
  <button class="iconbtn" id="sh-inarch" style="margin-top:14px;width:100%;
    padding:8px">Add to archive</button>
  <button class="done">Done</button>
</div>

<div class="sheet" id="settings">
  <h3>Settings</h3>
  <p class="sub">Your tags are saved to <code>tags.json</code> in the
    repo, so every device sees them.</p>
  <label for="tokbox">GitHub token</label>
  <input type="password" id="tokbox" placeholder="github_pat_...">
  <button class="go" id="savetok" style="margin-top:9px">Save token</button>
  <p class="hint">A fine-grained token with <b>Contents: read and write</b> on
    <code>__REPO__</code> only. It is stored in this browser and never leaves
    it except as an Authorization header to GitHub. Paste it once per device.</p>
  <p class="danger">Anyone with this device can edit that one repo. Clearing
    browser data removes the token and you re-paste it.</p>
  <button class="done">Done</button>
</div>

<div class="syncbar" id="syncbar">
  <span id="synctext"></span>
  <button id="savebtn">Save to GitHub</button>
</div>
<div class="toast" id="toast"></div>
"""

MANIFEST = {
    "name": "Games History", "short_name": "Games",
    "start_url": ".", "scope": ".", "display": "standalone",
    "background_color": "#16161a", "theme_color": "#16161a",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png",
         "purpose": "any maskable"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png",
         "purpose": "any maskable"},
    ],
}

# Bump on every build so a redeploy cannot be served from the old cache --
# GitHub Pages sends index.html with max-age=600.
SW = """
const CACHE="games-history-__BUILD__";
// Only the shell is pre-cached. The data files carry ?v=<build> and are cached
// at runtime, so a rebuild always misses and refetches -- pre-caching them by
// bare name is what served a stale games.json after a rebuild.
const ASSETS=["./","./index.html","./manifest.webmanifest"];
self.addEventListener("install",e=>{
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(
    ASSETS.map(u=>new Request(u,{cache:"reload"})))).catch(()=>{}));
});
self.addEventListener("activate",e=>{
  e.waitUntil(caches.keys().then(ks=>Promise.all(
    ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>
      self.clients.claim()));
});
self.addEventListener("fetch",e=>{
  const u=new URL(e.request.url);
  // tags.json is shared state and ESPN is live: never serve either from cache
  if(u.pathname.endsWith("tags.json")||u.host!==location.host) return;
  if(e.request.mode==="navigate"){
    e.respondWith(fetch(e.request,{cache:"no-store"})
      .catch(()=>caches.match("./index.html")));
    return;
  }
  e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));
});
"""


def png(size):
    """The app icon: the archive's own card, reduced to two team rows with the
    winner washed maize. His pick of six candidates (see icons.py).

    Drawn by pixel maths -- there is no image library on this machine. The
    manifest declares `purpose: "any maskable"`, which means Android crops this
    square to the launcher's own shape, so the background is FULL BLEED and
    every mark sits inside the maskable safe circle (radius 0.4 about centre).
    The card corners land at 0.384 from centre, inside the 0.400 limit;
    an earlier 0.18/0.24 rectangle measured 0.408 and would have been cropped.
    """
    bg, card = (0x16, 0x16, 0x1A), (0x1E, 0x1E, 0x23)
    maize, line = (0xFF, 0xCB, 0x05), (0x4A, 0x4A, 0x54)
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            u, v = x / size, y / size
            if 0.20 <= u < 0.80 and 0.26 <= v < 0.74:
                if 0.24 <= u < 0.76 and 0.33 <= v < 0.46:
                    c = maize                      # the winning team
                elif 0.24 <= u < 0.76 and 0.54 <= v < 0.67:
                    c = line                       # the losing team
                else:
                    c = card
            else:
                c = bg                             # full bleed for the mask
            row += bytes(c)
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def crest_urls(teams):
    """Which of ESPN's two crest variants reads on a dark page, measured per
    team by logos.py -- the naive /500/ -> /500-dark/ swap turns some crests
    into flat white silhouettes."""
    import requests
    import logos
    session = requests.Session()
    out = {}
    for tid in teams:
        try:
            url, _why = logos.choose(
                "https://a.espncdn.com/i/teamlogos/ncaa/500-dark/%s.png" % tid,
                "https://a.espncdn.com/i/teamlogos/ncaa/500/%s.png" % tid,
                session)
            out[tid] = url
        except Exception:
            out[tid] = "https://a.espncdn.com/i/teamlogos/ncaa/500/%s.png" % tid
    return out


def build():
    import time
    data = json.load(open(os.path.join(OUT, "games.json"), encoding="utf-8"))
    os.makedirs(SITE, exist_ok=True)

    crests_path = os.path.join(OUT, "crests.json")
    if os.path.exists(crests_path):
        crests = json.load(open(crests_path, encoding="utf-8"))
    else:
        crests = {}
    missing = [t for t in data["teams"] if t not in crests]
    if missing:
        print("measuring %d crests..." % len(missing))
        crests.update(crest_urls(missing))
        json.dump(crests, open(crests_path, "w", encoding="utf-8"),
                  separators=(",", ":"), sort_keys=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    js = (open(os.path.join(HERE, "app.js"), encoding="utf-8").read()
          .replace("__REPO__", REPO)
          .replace("__TAGS_PATH__", TAGS_PATH)
          .replace("__BUILD__", stamp)
          .replace("__STARTER__", json.dumps(STARTER_TAGS)))
    html = ("<!doctype html>\n<html lang=\"en\">\n<head>\n"
            "<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,"
            "initial-scale=1,viewport-fit=cover\">\n"
            "<title>Games History</title>\n"
            "<meta name=\"theme-color\" content=\"#16161a\">\n"
            "<link rel=\"manifest\" href=\"manifest.webmanifest\">\n"
            # without an explicit icon link the browser asks for /favicon.ico,
            # 404s, and the tab shows a blank globe -- the manifest covers only
            # the INSTALLED icon
            "<link rel=\"icon\" href=\"icon-192.png\">\n"
            "<link rel=\"apple-touch-icon\" href=\"icon-180.png\">\n"
            "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">\n"
            "<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" "
            "crossorigin>\n"
            "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/"
            "css2?family=Source+Sans+3:wght@400;600;700&display=swap\">\n"
            "<style>%s</style>\n</head>\n<body>%s\n"
            "<script src=\"app.js?v=%s\"></script>\n</body>\n</html>\n"
            % (CSS, BODY.replace("__REPO__", REPO), stamp))

    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(html)
    open(os.path.join(SITE, "app.js"), "w", encoding="utf-8").write(js)
    open(os.path.join(SITE, "sw.js"), "w", encoding="utf-8").write(
        SW.replace("__BUILD__", stamp))
    json.dump(MANIFEST, open(os.path.join(SITE, "manifest.webmanifest"), "w",
                             encoding="utf-8"), indent=1)
    for name in ("games.json", "colors.json", "crests.json"):
        shutil.copyfile(os.path.join(OUT, name), os.path.join(SITE, name))
    # docs/tags.json is the shared state the APP writes, and docs/ is now the
    # repo folder itself -- so this file is its own source. Seed it once and
    # never touch it again, or a rebuild would wipe every tag.
    tags_out = os.path.join(SITE, "tags.json")
    if not os.path.exists(tags_out):
        open(tags_out, "w", encoding="utf-8").write("{}\n")
    for size in (180, 192, 512):
        open(os.path.join(SITE, "icon-%d.png" % size), "wb").write(png(size))

    total = sum(os.path.getsize(os.path.join(SITE, f))
                for f in os.listdir(SITE))
    print("docs/  %d games, %d teams, %.0f KB total"
          % (len(data["games"]), len(data["teams"]), total / 1024))
    print("  build stamp %s" % stamp)


if __name__ == "__main__":
    build()
