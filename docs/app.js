/* Games History -- the whole app. site.py copies this in and fills the
   __PLACEHOLDERS__. Kept as a real .js file rather than a Python string so it
   stays editable and lintable. */
const REPO = "kyeill/games-history", TAGS_PATH = "docs/tags.json";
const STARTER = ["Big Noon Kickoff", "College GameDay", "Home & Home", "Neutral & Neutral", "Home & Neutral", "Annual", "Buy Game"];
// Every data file carries the build stamp. Without it a rebuild keeps serving
// the PREVIOUS games.json out of the service worker / HTTP cache -- which it
// did, silently, and the page rendered games missing their newest fields.
const BUILD = "20260911-205623";
const CARD = [0x1e, 0x1e, 0x23];
let GAMES = [], TEAMS = {}, COLORS = {}, CRESTS = {}, TAGS = {}, PENDING = {};
// TAB is the SPORT (his call 2026-09-09 -- he wants each population isolable);
// VIEW switches between the two collections within it.
let BROWSE = null, TAB = "cfb", VIEW = "tv", SHEET = null;
let FILT = { season: null, week: null, month: null, type: null, windows: null,
              team: null, marquee: false, rival: null, post: false, winner: null };

/* Season order, not calendar order: a basketball season runs Nov to Apr. */
const MONTHS = ["January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November",
                "December"];
function monthOrder(m) { return m >= 8 ? m - 12 : m; }
let ORDER = {}, SEASONS = [], WINDOW_NET = {};
let HEADER_TINT = {}, NET_TINT = {}, NET_PRIORITY = {}, BIG_TEN = {};
let SEASON_NAMES = {}, HIDDEN_WINDOWS = {};
// Oldest-first by default (his call 2026-09-09): with a season filter on, that
// reads as the season unfolding. The toggle flips it.
let SORT = "desc";   // Newest First is the tab default (his call 2026-09-11)
const SPORT_OF = { cfb: "CFB", cbb: "CBB" };
// Key Games opens on the upset category -- it is the longest list and the one
// he actually came for. TV Windows opens unfiltered.

/* ---------- storage: every accessor can throw in a locked-down browser --- */
function lsGet(k, d) {
  try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; }
  catch (e) { return d; }
}
function lsSet(k, v) {
  try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { }
}
function token() {
  try { return localStorage.getItem("gh_token") || ""; } catch (e) { return ""; }
}

/* ---------- colour: the same wash maths as colors.py -------------------- */
function shade(hex, lighten, strength) {
  lighten = lighten === undefined ? 0.42 : lighten;
  strength = strength === undefined ? 0.34 : strength;
  hex = (hex || "6a6a70").replace("#", "");
  if (hex.length !== 6) hex = "6a6a70";
  const p = [0, 2, 4].map(i => parseInt(hex.slice(i, i + 2), 16))
    .map(c => Math.round(c + (255 - c) * lighten));
  return "#" + p.map((c, i) => Math.round(CARD[i] + (c - CARD[i]) * strength)
    .toString(16).padStart(2, "0")).join("");
}
function teamColor(t) {
  return COLORS[t.id] || (t.color || "").replace("#", "") || "6a6a70";
}
function crest(t) {
  return CRESTS[t.id] ||
    "https://a.espncdn.com/i/teamlogos/ncaa/500-dark/" + t.id + ".png";
}
function teamName(t, sport, season) {
  let nm = (TEAMS[t.id] && TEAMS[t.id].short) || t.name || t.id;
  // a name that changes with the era -- UCLA reads "Ucla" before 2023
  const sn = SEASON_NAMES[t.id];
  if (sn && season != null && season < sn.before) nm = sn.name;
  // Big Ten teams go up in caps. Membership is as of THAT SEASON, so USC is
  // capitalised from 2024 and not before.
  return (sport && t.conf === BIG_TEN[sport]) ? nm.toUpperCase() : nm;
}
function esc(s) {
  return String(s).replace(/[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* ---------- tag state --------------------------------------------------- */
function eff(id) {
  const base = TAGS[id] || {}, over = PENDING[id];
  return over ? Object.assign({}, base, over) : base;
}
function myTags(id) { return eff(id).tags || []; }
function isHidden(id) { return !!eff(id).hide; }
function isAdded(id) { return !!eff(id).add; }
function pendingCount() { return Object.keys(PENDING).length; }

function setPending(id, patch, game) {
  const cur = Object.assign({}, TAGS[id] || {}, PENDING[id] || {}, patch);
  if (game && !cur.game && !GAMES.some(g => g.id === id)) cur.game = game;
  // returning to exactly what the repo already holds is not a change
  if (JSON.stringify(cur) === JSON.stringify(TAGS[id] || {})) delete PENDING[id];
  else PENDING[id] = cur;
  lsSet("pending", PENDING);
  drawSync();
}

/* ---------- rendering --------------------------------------------------- */
function fmtDate(d) {
  // "2025-09-06" -> "9/6/25"
  return String(+d.slice(5, 7)) + "/" + String(+d.slice(8, 10)) + "/" +
    d.slice(2, 4);
}
function fmtTime(t) {
  const p = t.split(":"), h = +p[0] % 12 || 12;
  return h + ":" + p[1] + (+p[0] < 12 ? "am" : "pm");
}
// ESPN lists simulcasts and streams alongside the real network -- "NBC,
// Peacock", "CBS, Paramount+", "ESPN, ESPN+". Only the broadcaster is wanted,
// and alphabetical order does not reliably put it first (BTN would beat FOX),
// so the majors are ranked explicitly.
// A TV channel ALWAYS beats a streaming service (2026-09-11): a channel
// missing from the list used to lose to a listed streamer, so Creighton at
// UConn read "HBO Max" over TNT and Iowa State at Cincinnati "Peacock" over
// NBCSN. Unlisted channels rank after the listed ones, streamers last.
const NET_RANK = ["ABC", "CBS", "NBC", "FOX", "ESPN", "ESPN2", "ESPNU", "BTN",
                  "FS1", "FS2", "TNT", "TBS", "truTV", "CBSSN", "NBCSN",
                  "USA Net", "SEC Network", "SECN", "ACC Network", "PACN", "CW"];
const STREAMERS = ["Peacock", "Paramount+", "ESPN+", "HBO Max", "Disney+",
                   "ESPN3", "B1G+", "BIG12|ESPN+", "SECN+", "ACCNX"];
function primaryNet(nets) {
  if (!nets || !nets.length) return "";
  const rank = n => NET_RANK.indexOf(n) > -1 ? NET_RANK.indexOf(n)
    : STREAMERS.indexOf(n) > -1 ? 900 + STREAMERS.indexOf(n) : 500;
  let best = nets[0];
  nets.forEach(n => { if (rank(n) < rank(best)) best = n; });
  return best;
}

// A TV window chip is painted in its network's colour, from the explicit map
// in rules.py. Parsing the name does not work: "Big Monday", "Super Tuesday"
// and "B1G Peacock" carry no network in their names.
function netClass(window) {
  const n = WINDOW_NET[window];
  return n ? "n-" + n : "";
}

// His bottom-row tags each carry a colour: the pregame shows are branded,
// H&H and OT are incidental detail.
// The scheduling tags (Home & Home, Neutral & Neutral, Home & Neutral, Annual,
// Buy Game) share one quiet grey -- they describe how the game was arranged,
// not how it was broadcast.
const TAG_CLASS = { "Big Noon Kickoff": "g-yellow", "College GameDay": "g-red",
                    "Home & Home": "g-grey", "Neutral & Neutral": "g-grey",
                    "Home & Neutral": "g-grey", "Annual": "g-grey",
                    "Buy Game": "g-grey" };
function tagClass(t) { return TAG_CLASS[t] || ""; }

const PLACE_TOO = ["Champions Classic", "CBS Sports Classic"];
function chip(kind, text) {
  return '<span class="tag t-' + kind + '">' + esc(text) + "</span>";
}
function teamLine(t, sport, season, seed) {
  // A postseason SEED reads in front of the name instead of in the rank column
  // (his call 2026-09-11): "2 WASHINGTON", not "NO. 2". The column then only
  // ever holds a poll ranking, so it is as narrow as "#25".
  const inline = seed && t.rank
    ? '<span class="rkin">' + t.rank + "</span> " : "";
  return '<div class="tl' + (t.win ? " won" : "") + '">' +
    '<img class="crest" loading="lazy" src="' + crest(t) + '" alt="">' +
    '<span class="rk">' +
    (t.rank && !seed ? '<span class="rn">' + t.rank + "</span>" : "") + "</span>" +
    '<span class="nm">' + inline + esc(teamName(t, sport, season)) + "</span>" +
    '<span class="sc">' + t.score + "</span></div>";
}

function rowHtml(g, browse) {
  const home = g.teams[0], away = g.teams[1];
  const win = home.win ? home : away;
  const tags = [];
  // No game-type label on any card, either view (his call 2026-09-09). The
  // field still drives the Game Type filter.
  // The purple chip is the conference championship OR the location, never
  // both -- a title game is played somewhere, but the title is the story.
  // One blue chip, in priority order: conference championship, then a named
  // event (SEC Quarterfinals, Battle 4 Atlantis), then a home game played
  // away from the home team's own building, then the neutral-site city.
  // a game whose header already names the event shows the LOCATION instead
  if (g.champ && !g.stage) {
    const r = g.round || "";
    tags.push(chip("champ", g.champ + " " +
      (r.indexOf(" - ") > -1 ? r.split(" - ").pop() : "Championship")));
  } else if (g.event && !g.stage) {
    tags.push(chip("champ", g.event));
  } else if (g.bowl) {
    // a CFP game short of the final names its bowl, not the city (his call
    // 2026-09-11): Rose, Cotton, Peach, Fiesta, Orange or Sugar
    tags.push(chip("champ", g.bowl));
  } else if (g.offsite) {
    // Named by VENUE, not city -- the venue IS the story here. Wrigley Field,
    // Ford Field, Madison Square Garden.
    tags.push(chip("champ", g.offsite));
  } else if (g.neutral && g.city) {
    tags.push(chip("champ", g.city));
  }
  // Champions Classic and CBS Sports Classic move every year, so their cards
  // name the place as a second chip (his call 2026-09-11)
  if (g.event && !g.stage && PLACE_TOO.indexOf(g.event) > -1 &&
      (g.offsite || (g.neutral && g.city)))
    tags.push(chip("champ", g.offsite || g.city));
  myTags(g.id).forEach(t => tags.push(chip("mine " + tagClass(t), t)));
  // overtime underlines the winning score rather than adding a chip

  const inArch = GAMES.some(x => x.id === g.id) || isAdded(g.id);
  const mark = browse && inArch ? ' <span class="inarch">IN ARCHIVE</span>' : "";
  // Header: football reads "WEEK 1", with the window after a pipe when there
  // is one. Basketball reads the window, or the day of the week when there is
  // none. The DATE itself lives in the meta column now.
  const label = g.header;
  // Football takes the WINDOW's colour, which exists for exactly the three
  // marquee windows, and paints the header, the network and the time with it.
  // Basketball takes the NETWORK's colour: the network cell always, and the
  // header and time as well on a Marquee game (his call 2026-09-10).
  const tint = g.sport === "CFB" ? HEADER_TINT[label] : null;
  // no network colour on a Big Ten or NCAA Tournament game (his call
  // 2026-09-11): the tournament, not the broadcaster, is the story
  const bigTourney = /^(Big Ten|NCAA) Tournament/.test(g.stage || "");
  const netTint = g.sport === "CBB" && !bigTourney
    ? NET_TINT[primaryNet(g.nets)] : null;
  const netCol = g.sport === "CFB" ? tint : netTint;
  const winCol = g.sport === "CFB" ? tint : (g.mq ? netTint : null);
  // ...but the HEADER keeps that colour only when a Big Ten team is playing
  // (his call 2026-09-11). The network and the time keep theirs regardless.
  const bigTen = g.teams.some(t => t.conf === BIG_TEN[g.sport]);
  const headCol = bigTen ? winCol : null;
  const timeCol = winCol;
  const col = c => (c ? ' style="color:' + c + '"' : "");
  const DAYS = { Mon: "Monday", Tue: "Tuesday", Wed: "Wednesday",
                 Thu: "Thursday", Fri: "Friday", Sat: "Saturday",
                 Sun: "Sunday" };
  let when;
  if (g.stage) {
    // an EVENT rather than a week (his call 2026-09-11): "FIESTA BOWL (SAT)",
    // "CFP | QUARTERS (WED)", "NCAA TOURNAMENT | ROUND 1
    // (THU)", "BIG TEN TOURNAMENT | SEMIS (SAT)", "BIG TEN CHAMPIONSHIP (SAT)"
    // a postseason game carries its year (his call 2026-09-11): the season a
    // football game belongs to (2020 CFP), the March a basketball game is
    // played in (2016 NCAA Tournament)
    const year = g.post ? (g.sport === "CFB" ? g.season : g.season + 1) + " " : "";
    when = year + esc(g.stage) + " (" + esc(g.dow) + ")";
  } else if (g.sport === "CFB") {
    // Week 0 is a real week, so test for a MISSING week, not a falsy one
    const hasWeek = g.week != null;
    when = (hasWeek ? '<span class="wk">Week ' + g.week + "</span>" : "") +
      (label ? (hasWeek ? " | " : "") + esc(label) : "");
    // a bare "WEEK 1" off a Saturday names its day (his call 2026-09-11)
    if (hasWeek && !label && g.dow !== "Sat") when += " (" + esc(g.dow) + ")";
    // Browse pulls straight from ESPN, where a week number can be missing;
    // never leave the header empty.
    if (!when) when = esc(DAYS[g.dow] || g.dow);
  } else {
    when = esc(label || DAYS[g.dow] || g.dow);
  }
  // the Michigan view draws its own card from the same header and chips
  if (VIEW === "michigan" && !browse)
    return michCard(g, { tags: tags, when: when, headCol: headCol,
                         netCol: netCol, timeCol: timeCol });
  // A coloured BORDER flags a Michigan win or a rival loss. A full maize box
  // was too loud, so the winner's line keeps its own wash either way.
  let flag = celebrated(g);
  let ring = flag ? celebrateColor(g) : null;
  if (VIEW === "rivals") {
    const c = rivalsBorder(g);
    flag = !!c;
    ring = c ? [c, c + "44"] : null;
  }
  return '<button class="row' + (flag ? " celebrate" : "") +
    (dimmed(g) ? " dimmed" : "") + (g.ot ? " ot" : "") +
    // a Michigan loss is DASHED (his call 2026-09-11): a solid grey border
    // looked like a rival loss to a black-and-gold winner such as Iowa
    ((VIEW !== "rivals" && michTeam(g) && !michTeam(g).win) ? " mloss" : "") +
    // ranking colour (his calls 2026-09-11), every view: a Michigan loss or a
    // win by Ohio State, Michigan State or Notre Dame greys the rankings;
    // otherwise an upset paints them Sports Daily's orange
    (dimmed(g) ? " rk-grey" : isUpset(g) ? " rk-upset" : "") +
    // the CFP and the NCAA Tournament read "NO. 3", not "#3"
    (playoffGame(g) ? " rk-no" : "") +
    '" data-id="' + g.id + '" style="--winwash:' + shade(teamColor(win)) +
    (ring ? ";--celeb:" + ring[0] + ";--celebring:" + ring[1] : "") + '">' +
    // The header row: slot label left, DATE right. The date sits here rather
    // than in the meta column because this is the only way it lines up with
    // the header. No weekday -- his call 2026-09-10.
    '<div class="sport"' + col(headCol) + ">" +
      "<span>" + when + mark + "</span>" +
      '<span class="hdate">' + fmtDate(g.date) + "</span></div>" +
    '<div class="teams">' + teamLine(away, g.sport, g.season, playoffGame(g)) +
      teamLine(home, g.sport, g.season, playoffGame(g)) + "</div>" +
    // network on the away team's line, time on the home team's
    '<div class="meta"><div class="mrow"' + col(netCol) + ">" +
      esc(primaryNet(g.nets) || "—") + '</div><div class="mrow"' +
      col(timeCol) + ">" + fmtTime(g.time) + "</div></div>" +
    '<div class="tags">' + tags.join("") + "</div></button>";
}

/* MICHIGAN view (trial, his call 2026-09-11). One card per Michigan game, in
   the same frame as every other card: the header (his emoji and the NC / B1G
   game number in front), then ONE team line -- the opponent, with its rank at
   the time, its playoff finish [Semis] or final rank [#13] or his SP+/KenPom
   (73+), and the score and Michigan's rank in boxes painted as Michigan's
   uniform. Then one row of chips.
   His own columns come from michigan.csv via harvest: emoji, border, caps,
   uniform and note. */
const MICH_COLOURS = { blue: "#00274c", maize: "#ffcb05", white: "#f2f2f0",
  gold: "#c28c19", grey: "#8a8a92", gray: "#8a8a92", black: "#111114",
  red: "#c8102e", green: "#1d7a3a", navy: "#00274c" };
function michColour(v) {
  const s = String(v || "").trim();
  if (/^#?[0-9a-f]{6}$/i.test(s)) return "#" + s.replace("#", "");
  return MICH_COLOURS[s.toLowerCase()] || null;
}
function michCard(g, p) {
  const m = michTeam(g), opp = g.teams.find(t => t.id !== MICHIGAN) || g.teams[0];
  const mx = g.mx || {}, lost = !m.win;
  // his caps column wins; left blank, the Big Ten rule of every other view holds
  let nm = mx.caps === "N" ? teamName(opp, null, g.season)
    : teamName(opp, g.sport, g.season);
  if (mx.caps === "Y") nm = nm.toUpperCase();
  const where = g.neutral ? "vs. " : opp.home ? "at " : "";
  const fin = mx.finish ? "[" + mx.finish + "]" : mx.final ? "[#" + mx.final + "]"
    : mx.rating ? "(" + mx.rating + "+)" : "";
  const col = c => (c ? ' style="color:' + c + '"' : "");
  // HEADER (his calls 2026-09-11). The TV details follow a bar -- "[nc1] WEEK 1
  // | PEACOCK 12:00PM" -- unless a window label already fills the header. A
  // STAGE card drops its own bar and the word "Tournament", takes the TV
  // details after the bar instead, and moves its day beside the date:
  // "2026 NCAA ROUND 1 | CBS 7:30PM" ... "THU 3/19/26".
  const tvBits = ' | <span' + col(p.netCol) + ">" + esc(primaryNet(g.nets) || "\u2014") +
    "</span> <span" + col(p.timeCol) + ">" + fmtTime(g.time) + "</span>";
  let when = p.when, right = fmtDate(g.date);
  if (g.stage) {
    const year = g.post ? (g.sport === "CFB" ? g.season : g.season + 1) + " " : "";
    when = year + esc(g.stage.replace(" Tournament", "").replace(" | ", " ")) + tvBits;
    right = '<span class="hdow">' + esc(g.dow) + "</span> " + right;
  } else if (!g.header) {
    when += tvBits;
  }
  const head = (mx.emoji ? esc(mx.emoji) + " " : "") +
    (mx.num ? '<span class="mnum">[' + esc(mx.num) + "]</span> " : "") + when;
  // UNIFORM (his calls 2026-09-11): the score box is the jersey, the rank box
  // the pants, and the accessories colour is the text on both. He wants maize
  // ON maize and blue ON blue, which cannot be read as the same value, so the
  // text KEEPS ITS HUE and moves in lightness until it reads (3:1) -- maize on
  // maize becomes a deep gold, blue on blue a lighter blue. Only a colour that
  // still cannot get there falls back to navy or maize. Basketball's single
  // uniform colours both boxes.
  const u = (mx.uni || []).map(michColour);
  const top = u[0] || null;
  const pants = (u.length >= 3 ? u[1] : u[0]) || null;
  const acc = u.length >= 3 ? u[2] : null;
  const lum = hex => {
    const v = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map(x => x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4));
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
  };
  const ratio = (a, b) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05);
  const WHITE = "#f2f2f0";
  const toHsl = hex => {
    const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
    const hi = Math.max(r, g, b), lo = Math.min(r, g, b), l = (hi + lo) / 2;
    if (hi === lo) return { h: 0, s: 0, l: l };
    const d = hi - lo;
    const s = l > 0.5 ? d / (2 - hi - lo) : d / (hi + lo);
    const h = hi === r ? ((g - b) / d + (g < b ? 6 : 0))
      : hi === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return { h: h / 6, s: s, l: l };
  };
  const toHex = (h, s, l) => {
    const f = n => {
      const k = (n + h * 12) % 12, a = s * Math.min(l, 1 - l);
      const v = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
      return Math.round(v * 255).toString(16).padStart(2, "0");
    };
    return "#" + f(0) + f(8) + f(4);
  };
  const readable = (fg, bg) => {
    // WHITE keeps the school palette (his call 2026-09-11): maize or blue on a
    // white box, white on a maize or blue one, with no shifting -- white on
    // white alone would vanish, so that reads blue
    if (fg === WHITE && bg === WHITE) return "#00274c";
    if (fg === WHITE) return fg;
    if (bg === WHITE) {
      // maize on white reads faint, so it goes a touch darker (his call
      // 2026-09-11); blue on white already stands out and is left alone
      if (ratio(fg, bg) >= 3) return fg;
      const w = toHsl(fg);
      return toHex(w.h, w.s, Math.max(0, w.l - 0.1));
    }
    if (ratio(fg, bg) >= 3) return fg;
    // a light box darkens the text in fine steps, so maize on maize stops at
    // the LIGHTEST gold that still reads (his call); a dark box lightens faster
    const c = toHsl(fg), darken = lum(bg) > 0.18;
    const step = darken ? 0.01 : 0.05;
    for (let i = 1; i <= 100; i++) {
      const l = darken ? c.l - i * step : c.l + i * step;
      if (l < 0 || l > 1) break;
      const cand = toHex(c.h, c.s, l);
      if (ratio(cand, bg) >= 3) return cand;
    }
    return ratio("#00274c", bg) >= ratio("#ffcb05", bg) ? "#00274c" : "#ffcb05";
  };
  const ink = bg => acc ? readable(acc, bg)
    : ratio("#00274c", bg) >= ratio("#ffcb05", bg) ? "#00274c" : "#ffcb05";
  const paint = bg => (bg ? ' style="background:' + bg + ";color:" + ink(bg) + '"' : "");
  // the two boxes share one height and one type size (his call)
  const score = '<span class="sc mbox"' + paint(top) + ">" + m.score + "-" + opp.score +
    "</span>";
  // Michigan's rank at the time beside the score; blank when unranked, the box
  // still showing the pants colour when there is one
  const umRank = (m.rank || pants)
    ? '<span class="mrank"' + paint(pants) + ">" +
      (m.rank ? String(m.rank) : "") + "</span>"
    : "<span></span>";
  // TEAM LINE: the colour stripe runs from the crest through the rating and
  // stops before the two boxes (his call 2026-09-11)
  const oppLine = '<div class="tl' + (lost ? "" : " won") + '"><span class="mstripe">' +
    '<img class="crest" loading="lazy" src="' + crest(opp) + '" alt="">' +
    '<span class="rk">' +
    (opp.rank && !playoffGame(g) ? '<span class="rn">' + opp.rank + "</span>" : "") +
    "</span>" +
    '<span class="nm mnm"><span class="mn">' + esc(where) +
      (playoffGame(g) && opp.rank ? '<span class="rkin">' + opp.rank + "</span> " : "") +
      esc(nm) +
      (mx.reigning ? '<span class="mcaret">^</span>' : "") + "</span>" +
      (fin ? '<span class="mfin">' + esc(fin) + "</span>" : "") + "</span></span>" +
    score + umRank + "</div>";
  // ONE CHIP ROW, in his order (2026-09-11): location, event, the home & home
  // family, Big Noon, GameDay, anything else, then his Big Ten note. The two
  // long show tags carry a short form for trimMichChips.
  const mine = myTags(g.id);
  const SERIES_FAMILY = ["Home & Home", "Neutral & Neutral", "Home & Neutral",
                         "Annual", "Buy Game"];
  const tagChip = (t, short) => '<span class="tag t-mine ' + tagClass(t) + '"' +
    (short ? ' data-short="' + esc(short) + '"' : "") + ">" + esc(t) + "</span>";
  const place = g.bowl || g.offsite || (g.neutral && g.city ? g.city : "");
  const chips = [];
  if (place) chips.push(chip("champ", place));
  if (g.event && !g.stage) chips.push(chip("champ", g.event));
  mine.filter(t => SERIES_FAMILY.indexOf(t) > -1).forEach(t => chips.push(tagChip(t)));
  if (mine.indexOf("Big Noon Kickoff") > -1) chips.push(tagChip("Big Noon Kickoff", "Big Noon"));
  if (mine.indexOf("College GameDay") > -1) chips.push(tagChip("College GameDay", "GameDay"));
  mine.filter(t => SERIES_FAMILY.indexOf(t) < 0 && t !== "Big Noon Kickoff" &&
    t !== "College GameDay").forEach(t => chips.push(tagChip(t)));
  if (mx.note) chips.push(chip("grey", mx.note));
  // a postseason win, or a win over Ohio State, Michigan State or Notre Dame,
  // washes the WHOLE card in the opponent's colour instead of its stripe
  const bigWin = !lost && !!(g.post || g.champ || RIVALS.indexOf(opp.id) > -1);
  let cls = " mich" + (bigWin ? " mwash" : "") + (lost ? " dimmed" : "") +
    (g.ot ? " ot" : "") +
    (dimmed(g) ? " rk-grey" : isUpset(g) ? " rk-upset" : "") +
    (playoffGame(g) ? " rk-no" : "");
  // his border colour when he gives one; otherwise a loss is dashed and muted
  const bc = michColour(mx.border);
  let ring = "";
  if (bc) {
    cls += " celebrate";
    ring = ";--celeb:" + bc + ";--celebring:" + bc + "44";
  } else if (lost) {
    cls += " celebrate mloss";
    ring = ";--celeb:#5a5a62";
  }
  return '<button class="row' + cls + '" data-id="' + g.id + '" style="--winwash:' +
    shade(teamColor(opp)) + ring + '">' +
    '<div class="sport"' + col(p.headCol) + "><span>" + head + "</span>" +
      '<span class="hdate">' + right + "</span></div>" +
    '<div class="teams">' + oppLine + "</div>" +
    '<div class="tags">' + chips.join("") + "</div></button>";
}

// A Michigan chip row that runs onto a second line trims its long show tags --
// "Big Noon Kickoff" to "Big Noon", "College GameDay" to "GameDay" (his call
// 2026-09-11). Re-run after every draw and when the window changes size.
function trimMichChips() {
  document.querySelectorAll(".row.mich .tags").forEach(row => {
    const shorts = row.querySelectorAll("[data-short]");
    if (!shorts.length) return;
    shorts.forEach(s => { if (s.dataset.full) s.textContent = s.dataset.full; });
    const first = row.firstElementChild;
    const wrapped = () => Array.prototype.some.call(row.children,
      c => c.offsetTop > first.offsetTop + 2);
    if (!wrapped()) return;
    shorts.forEach(s => {
      if (!s.dataset.full) s.dataset.full = s.textContent;
      s.textContent = s.dataset.short;
    });
  });
}
let MICH_RESIZE = null;
window.addEventListener("resize", () => {
  clearTimeout(MICH_RESIZE);
  MICH_RESIZE = setTimeout(() => { if (VIEW === "michigan") trimMichChips(); }, 150);
});

/* Dividers in the Michigan view (his call 2026-09-11), only when one season
   is picked: a BYE for each Saturday a football schedule skips, and
   POSTSEASON where the conference title game or tournament begins. Each is a
   TILE in the grid, so
   on a desktop it takes one card's slot and three-across stays in step. */
function michListHtml(list) {
  const cards = list.map(g => rowHtml(g, false));
  if (FILT.season == null || list.length < 2) return cards.join("");
  const day = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) / 864e5;
  const iso = n => new Date(n * 864e5).toISOString().slice(0, 10);
  const post = g => !!(g.post || g.champ);
  const tile = t => '<div class="mgap">' + t + "</div>";
  const out = [cards[0]];
  for (let i = 1; i < list.length; i++) {
    const a = list[i - 1], b = list[i];
    const lo = Math.min(day(a.date), day(b.date)), hi = Math.max(day(a.date), day(b.date));
    const gaps = [];
    if (post(a) !== post(b)) {
      gaps.push("Postseason");
    } else if (!post(a) && a.sport === "CFB") {
      for (let d = lo + 4; d <= hi - 4; d++)
        if (new Date(d * 864e5).getUTCDay() === 6) gaps.push("Bye \u00b7 " + fmtDate(iso(d)));
      if (SORT !== "asc") gaps.reverse();
    }
    gaps.forEach(t => out.push(tile(t)));
    out.push(cards[i]);
  }
  return out.join("");
}

/* Kyle's teams. ESPN gives a school one id across both sports. */
const MICHIGAN = "130";
const RIVALS = ["194", "127", "87"];   // Ohio State, Michigan State, Notre Dame

/* RIVALS (his call 2026-09-11): games Ohio State or Michigan State (both sports)
   or Notre Dame (football) LOST -- two of them playing each other only when
   rules.RIVALS_INCLUDE names the game. Harvest flags the ones that count
   (g.rivals): postseason or conference tournament, a ranked team, a neutral
   site, or a Marquee window. The home & home family is checked here instead,
   because those tags live in tags.json. Games that are ONLY here -- a bowl, an
   early tournament round -- carry no window or type, so no other view shows
   them. */
function rivalsAllows(g) {
  if (g.rivals) return true;
  if (!g.rival_loss) return false;
  const series = ["Home & Home", "Neutral & Neutral", "Home & Neutral"];
  return myTags(g.id).some(t => series.indexOf(t) > -1);
}

function bigViewAllows(g) {
  // Key Games is the view he browses for pleasure: no Michigan losses and no
  // rival wins. Both still appear under TV Windows, which is a record of what
  // was ON, not a highlight reel.
  const mich = g.teams.find(t => t.id === MICHIGAN);
  if (mich && !mich.win) return false;
  return !g.teams.some(t => RIVALS.indexOf(t.id) > -1 && t.win);
}
function isRival(t) { return RIVALS.indexOf(t.id) > -1; }
function michTeam(g) { return g.teams.find(t => t.id === MICHIGAN); }
// An upset: a ranked team lost to an unranked or a worse-ranked team.
function isUpset(g) {
  const w = g.teams.find(t => t.win), l = g.teams.find(t => !t.win);
  return !!(w && l && l.rank && (!w.rank || w.rank > l.rank));
}

/* A result he does not want to relive: a rival won, or Michigan lost. Both
   team lines go italic. */
function dimmed(g) {
  const m = michTeam(g);
  return (m && !m.win) || g.teams.some(t => isRival(t) && t.win);
}

function celebrated(g) {
  const m = michTeam(g);
  if (m) return true;                       // maize for a win, grey for a loss
  // Two rivals playing each other cancel out -- one of them had to win, and
  // colouring the winner would celebrate a rival.
  if (g.teams.every(isRival)) return false;
  return g.teams.some(t => isRival(t) && !t.win);
}
function brighten(hex, target) {
  // Lift a colour toward white until it reaches a target luminance, so every
  // border reads at the same strength. A fixed lighten does not work here:
  // Penn State navy stayed muddy at the same factor that turned Indiana's red
  // pink. Luminance is linear in the blend factor, so solve for it directly.
  hex = (hex || "6a6a70").replace("#", "");
  if (hex.length !== 6) hex = "6a6a70";
  const c = [0, 2, 4].map(i => parseInt(hex.slice(i, i + 2), 16));
  const lum = .299 * c[0] + .587 * c[1] + .114 * c[2];
  const t = Math.max(0, Math.min(1, (target - lum) / (255 - lum)));
  return "#" + c.map(v => Math.round(v + (255 - v) * t)
    .toString(16).padStart(2, "0")).join("");
}
function celebrateColor(g) {
  // Michigan's own win is maize; a Michigan loss is plain grey. A rival losing
  // to anyone else is coloured by whoever DID it -- Indiana over Ohio State
  // reads Indiana red.
  const m = michTeam(g);
  if (m) {
    return m.win ? ["#ffcb05", "#ffcb0544"] : ["#7a7a82", "#7a7a8244"];
  }
  const solid = brighten(teamColor(g.teams.find(t => t.win)), 130);
  return [solid, solid + "44"];
}

function visible() {
  if (TAB === "browse") return BROWSE || [];
  let list = GAMES.filter(g => !isHidden(g.id));
  // games added by hand live only in tags.json, so fold them back in
  Object.keys(TAGS).concat(Object.keys(PENDING)).forEach(id => {
    const e = eff(id);
    if (e.add && e.game && !list.some(g => g.id === id)) list.push(e.game);
  });
  list = list.filter(g => g.sport === SPORT_OF[TAB]);
  // A championship game shows on TV Windows even with no broadcast window --
  // 17 of the 46 have none, because the Big Ten title game kicks at 8pm and
  // the Pac-12 one was on a Friday. His call: they must all show.
  // Black Friday games carry no window, like championship games, so they need
  // the same admission -- without this they sat in the data unreachable.
  // Key Games needs a game TYPE. Being a conference-tournament game is not
  // itself a qualification -- an ACC first-rounder between unranked teams has
  // no business here, and every championship game carries a type anyway.
  list = list.filter(g => VIEW === "michigan" ? !!g.michigan
    : VIEW === "rivals" ? rivalsAllows(g)
    : g.rivals_only ? false
    : VIEW === "tv"
      ? ((g.slots || []).length || g.title || g.bfri || g.show || g.opener
         || g.showcase || g.kickoff)
      : (g.type && bigViewAllows(g)));
  // Basketball TV Windows run November to March now (his call 2026-09-11),
  // because the windows themselves reach into November and December. A game
  // with NO window of its own -- a College GameDay ride-along -- still has to
  // be January to March, which is what kept two November shows out before.
  if (VIEW === "tv" && SPORT_OF[TAB] === "CBB") {
    list = list.filter(g => {
      const m = +g.date.slice(5, 7);
      return (m >= 1 && m <= 3) || (g.slots || []).length || g.showcase;
    });
  }
  if (FILT.season != null) list = list.filter(g => g.season === FILT.season);
  // Rivals filters by whose loss it was, what kind of game, and who won
  if (VIEW === "rivals") {
    if (FILT.rival) list = list.filter(g => rivalLoser(g) === FILT.rival);
    // the Postseason button: everything by default, pressed only the CFP and
    // the NCAA Tournament (his call 2026-09-11)
    if (FILT.post) list = list.filter(playoffGame);
    if (FILT.winner) list = list.filter(g =>
      g.teams.some(t => t.win && t.id === FILT.winner));
  }
  if (FILT.week != null) list = list.filter(g => g.week === FILT.week);
  if (FILT.month != null)
    list = list.filter(g => +g.date.slice(5, 7) === FILT.month);
  // Marquee is a rule of its own now (rules.is_marquee), not a set of
  // windows the button ticks, so it stacks with the window dropdown instead
  // of pretending to be it. Nothing rides along any more.
  if (FILT.marquee) list = list.filter(g => g.mq);
  if (FILT.windows && FILT.windows.length)
    list = list.filter(g =>
      (g.slots || []).some(w => FILT.windows.indexOf(w) > -1));
  if (FILT.type) list = list.filter(g => g.type === FILT.type);
  if (FILT.team) list = list.filter(g =>
    g.teams.some(t => t.id === FILT.team));
  // Same kickoff minute: the bigger network leads (his order).
  const rank = g => {
    const pri = NET_PRIORITY[g.sport] || [];
    const i = pri.indexOf(primaryNet(g.nets));
    return i < 0 ? 99 : i;
  };
  // Newest First walks the BLOCKS backwards but reads each one forwards --
  // week 14, then 13, then 12, and inside a week the Thursday game first.
  // A football block is its week; basketball has none, so its block is the
  // date. Oldest First is simply chronological throughout.
  // Rivals orders by TRUE date (his call 2026-09-11): a CFP game has no week,
  // so a week block would put the Big Ten title game ahead of it
  const block = g => (VIEW !== "rivals" && VIEW !== "michigan" &&
      g.sport === "CFB" && g.week != null)
    ? g.season + "-" + String(g.week).padStart(2, "0")
    : g.date;
  const chron = (a, b) => (a.date !== b.date)
    ? a.date.localeCompare(b.date)
    : (a.time !== b.time ? a.time.localeCompare(b.time) : rank(a) - rank(b));
  list.sort((a, b) => {
    if (SORT === "asc") return chron(a, b);
    const ba = block(a), bb = block(b);
    return ba === bb ? chron(a, b) : bb.localeCompare(ba);
  });
  return list;
}

// The newest season that actually has games in THIS sport. SEASONS spans both
// sports, and basketball's newest one is empty for months -- 2026-27 has no
// games until November -- so the overall max opened the tab on nothing.
function latestSeason() {
  const own = GAMES.filter(g => g.sport === SPORT_OF[TAB] &&
      (VIEW === "michigan" ? g.michigan : !g.rivals_only))
    .map(g => g.season);
  if (own.length) return Math.max.apply(null, own);
  return SEASONS.length ? Math.max.apply(null, SEASONS) : null;
}

// Opening state, not an empty one: the newest season with games, and Marquee
// on the TV view. A function declaration, not a const -- init() calls it
// before this point in the file.
function clearFilters() {
  FILT = {
    season: latestSeason(),
    type: null,
    windows: null,
    // TV Windows opens on Marquee -- the games he plans a weekend around
    marquee: VIEW === "tv",
    week: null, month: null, team: null, rival: null, post: false, winner: null
  };
}

function seasonLabel(y) {
  // College football is one calendar year; basketball straddles two.
  return SPORT_OF[TAB] === "CFB" ? String(y) : y + "-" + String(y + 1).slice(2);
}

function filterChips() {
  if (TAB === "browse") return "";
  // Every filter is a dropdown (his call 2026-09-09), and the Tag filter is
  // gone. Game type and TV window come from ORDER in games.json -- HIS
  // sequence, not alphabetical -- scoped to the sport tab, because CFB and CBB
  // share none of their values.
  const sport = SPORT_OF[TAB];
  const order = ORDER[sport] || { types: [], windows: [] };
  const types = new Set(), windows = new Set();
  GAMES.forEach(g => {
    if (g.sport !== sport) return;
    if (g.type) types.add(g.type);
    (g.slots || []).forEach(w => windows.add(w));
  });

  const group = (label, inner) => '<div class="fgroup"><span class="flabel">' +
    label + "</span>" + inner + "</div>";
  // a pair whose value is null is a divider line, not a choice
  const select = (kind, allLabel, pairs, current) =>
    '<select class="fsel" data-kind="' + kind + '">' +
    '<option value="">' + allLabel + "</option>" +
    pairs.map(p => p[1] === null
      ? "<option disabled>" + esc(p[0]) + "</option>"
      : '<option value="' + esc(p[1]) + '"' +
        (String(current) === String(p[1]) ? " selected" : "") + ">" +
        esc(p[0]) + "</option>").join("") + "</select>";

  // only the seasons this view can show: Rivals reaches back to 2014, the
  // other views start with the archive
  const viewSeasons = Array.from(new Set(GAMES.filter(g => g.sport === sport &&
    (VIEW === "rivals" ? rivalsAllows(g)
      : VIEW === "michigan" ? g.michigan : !g.rivals_only)).map(g => g.season)));
  let h = group("Year", select("season", "All Years",
    viewSeasons.sort((a, b) => b - a).map(y => [seasonLabel(y), y]),
    FILT.season));
  // MICHIGAN (trial, 2026-09-11): Year and the sort
  if (VIEW === "michigan")
    return h + group("", sortButton());
  // RIVALS has its own filters (his call 2026-09-11): Year, Rival, Winner and
  // a Postseason button -- no week, month, game type, TV window, team or
  // Marquee
  if (VIEW === "rivals") {
    const optOf = id => [(TEAMS[id] && TEAMS[id].short) || id, id];
    const lined = ids => ids.length
      ? [["\u2500".repeat(12), null]].concat(ids.map(optOf)) : [];
    // Rival sits far left, ahead of Year (his call 2026-09-11)
    h = group("Rival", select("rival", "All Rivals",
      (sport === "CFB" ? ["194", "127", "87"] : ["127", "194", "87"]).map(optOf),
      FILT.rival)) + h;
    // only winners that would return games under the other filters
    const w = teamOrder(sport, teamsIn(visibleWithout("winner"),
      g => g.teams.filter(t => t.win).map(t => t.id), FILT.winner), ["130"]);
    h += group("Winner", select("winner", "All Winners",
      w.bigTen.map(optOf).concat(lined(w.power), lined(w.rest)), FILT.winner));
    return h + group("", postButton() + sortButton());
  }
  // Football is played in numbered weeks; basketball is not. The list follows
  // the season, since week 16 only exists in some years.
  if (sport === "CFB") {
    const weeks = new Set();
    GAMES.forEach(g => {
      if (g.sport !== "CFB" || g.week == null) return;
      if (FILT.season != null && g.season !== FILT.season) return;
      weeks.add(g.week);
    });
    h += group("Week", select("week", "All Weeks",
      Array.from(weeks).sort((a, b) => a - b).map(w => ["Week " + w, w]),
      FILT.week));
  }
  // Basketball has no week worth showing, so the month is its equivalent
  // coarse cut. Like the week list it follows the SEASON.
  if (sport === "CBB") {
    const months = new Set();
    GAMES.forEach(g => {
      if (g.sport !== "CBB") return;
      if (FILT.season != null && g.season !== FILT.season) return;
      const m = +g.date.slice(5, 7);
      months.add(m);
    });
    h += group("Month", select("month", "All Months",
      Array.from(months).sort((a, b) => monthOrder(a) - monthOrder(b))
        .map(m => [MONTHS[m - 1], m]),
      FILT.month));
  }
  h += group("Game type", select("type", "All Game Types",
    order.types.filter(t => types.has(t)).map(t => [t, t]), FILT.type));
  // The dropdown holds ONE window; Marquee Windows sets three at once, and
  // while it is on the dropdown falls back to its "All" label.
  const one = (FILT.windows && FILT.windows.length === 1) ? FILT.windows[0] : "";
  // some windows are deliberately absent from the dropdown -- the games keep
  // the window and still show under "All TV Windows"
  const hidden = HIDDEN_WINDOWS[sport] || [];
  h += group("TV window", select("window", "All TV Windows",
    order.windows.filter(w => windows.has(w) && hidden.indexOf(w) < 0)
      .map(w => [w, w]), one));
  // not "order": that name already holds the game-type / window sequence above
  // only teams that would return games under the other filters
  const teamList = teamOrder(sport, teamsIn(visibleWithout("team"),
    g => g.teams.map(t => t.id), FILT.team));
  const teamOpt = id => [(TEAMS[id] && TEAMS[id].short) || id, id];
  // a divider line opens each group after the Big Ten's (his call 2026-09-11)
  const withLine = ids => ids.length
    ? [["─".repeat(12), null]].concat(ids.map(teamOpt)) : [];
  h += group("Team", select("team", "All Teams",
    teamList.bigTen.map(teamOpt).concat(withLine(teamList.power), withLine(teamList.rest)),
    FILT.team));
  h += group("", quickButtons());
  return h;
}

/* The Team filter in HIS order (2026-09-11): his teams pinned and the rest of
   the Big Ten; a divider; the other power leagues together, alphabetically; a
   divider; everyone else. Only teams that play this sport are listed -- TEAMS spans
   both. Membership is a team's CURRENT conference, so USC sorts with the Big
   Ten and Texas with the SEC. Harvest records it from each team's latest game
   of ANY kind (teams[id].conf), because its latest ARCHIVE game can predate a
   move -- Stanford's is a 2023 Pac-12 game; that game is only the fallback.
   Declared inside the function, not as top-level consts, because init() runs
   before later top-level consts are initialised (see clearFilters). */
function teamOrder(sport, allowed, pinsOverride) {
  const PINS = { CFB: ["130", "194", "127", "87"],   // Michigan, Ohio State, Michigan State, Notre Dame
                 CBB: ["130", "127", "194"] };       // Michigan, Michigan State, Ohio State
  const POWER = { CFB: ["1", "8", "4"],              // ACC, SEC, Big 12
                  CBB: ["2", "23", "8", "4"] };      // ACC, SEC, Big 12, Big East
  const latest = {};
  GAMES.forEach(g => {
    if (g.sport !== sport) return;
    g.teams.forEach(t => {
      if (!latest[t.id] || g.date > latest[t.id].date)
        latest[t.id] = { date: g.date, conf: t.conf };
    });
  });
  const name = id => (TEAMS[id] && TEAMS[id].short) || id;
  const byName = (a, b) => name(a).localeCompare(name(b));
  const ok = id => !allowed || allowed.has(id);
  const pins = (pinsOverride || PINS[sport] || []).filter(id => latest[id] && ok(id));
  const others = Object.keys(latest).filter(id => pins.indexOf(id) < 0 && ok(id));
  const confOf = id =>
    (TEAMS[id] && TEAMS[id].conf && TEAMS[id].conf[sport]) || latest[id].conf;
  const inBigTen = id => confOf(id) === BIG_TEN[sport];
  const inPower = id => (POWER[sport] || []).indexOf(confOf(id)) > -1;
  return {
    bigTen: pins.concat(others.filter(inBigTen).sort(byName)),
    power: others.filter(id => !inBigTen(id) && inPower(id)).sort(byName),
    rest: others.filter(id => !inBigTen(id) && !inPower(id)).sort(byName)
  };
}

/* A dropdown lists only choices that would return games (his call
   2026-09-11): the list this view would show with THAT filter cleared. The
   current choice always stays listed, so a selection never vanishes. */
function visibleWithout(key) {
  const saved = FILT[key];
  FILT[key] = null;
  try { return visible(); } finally { FILT[key] = saved; }
}
function teamsIn(list, idsOf, current) {
  const ids = new Set();
  list.forEach(g => idsOf(g).forEach(id => ids.add(id)));
  if (current) ids.add(current);
  return ids;
}

/* Rivals: whose loss it was. Notre Dame counts in basketball too, but harvest
   only lets its NCAA Tournament losses in (rules.RIVALS_NCAA_ONLY). */
function rivalLoser(g) {
  const ids = ["194", "127", "87"];
  const t = g.teams.find(x => !x.win && ids.indexOf(x.id) > -1);
  return t ? t.id : null;
}
// The Postseason button keeps only the CFP and the NCAA Tournament (his call
// 2026-09-11) -- not the bowls, the NIT, or the Big Ten title game and tournament
function playoffGame(g) {
  const s = g.stage || "";
  return s.indexOf("CFP") === 0 || s.indexOf("NCAA Tournament") === 0;
}

// Rivals cards drop the usual borders for one coloured by the EVENT (his call
// 2026-09-11). A regular-season game has none.
function rivalsBorder(g) {
  const s = g.stage || "";
  if (s.indexOf("CFP") === 0) return "#c28c19";
  if (s.indexOf("NCAA Tournament") === 0) return "#0053b8";
  if (g.champ === "Big Ten" || s.indexOf("Big Ten ") === 0) return "#0088ce";
  // grey for bowls, the NIT, and any other conference title game -- Notre
  // Dame's 2020 ACC Championship is the one case (his call 2026-09-11)
  if (g.post || s) return "#8a8a92";
  return null;
}

// Rivals shows every game until this is pressed, then only the CFP and the
// NCAA Tournament (his call 2026-09-11)
function postButton() {
  return '<button class="f" data-act="post" aria-pressed="' + !!FILT.post +
    '">Postseason</button>';
}

function sortButton() {
  return '<button class="f" data-act="sort">' +
    (SORT === "asc" ? "Oldest First" : "Newest First") + "</button>";
}

function marqueeOn() { return !!FILT.marquee; }
function quickButtons() {
  return '<button class="f" data-act="marquee" aria-pressed="' + marqueeOn() +
    '">Marquee Windows</button>' +
    sortButton();
}

function draw() {
  const browsing = TAB === "browse";
  document.querySelectorAll("nav button").forEach(b =>
    b.setAttribute("aria-selected", String(b.dataset.tab === TAB)));
  document.querySelectorAll("#viewbar button").forEach(b =>
    b.setAttribute("aria-selected", String(b.dataset.view === VIEW)));
  document.getElementById("viewbar").style.display =
    browsing ? "none" : "inline-flex";
  document.getElementById("filters").innerHTML = filterChips();
  document.getElementById("daterow").style.display = browsing ? "flex" : "none";
  const list = visible();
  document.getElementById("count").textContent = TAB === "browse"
    ? (BROWSE === null ? "pick a date range" : list.length + " games")
    : list.length.toLocaleString() + " games";
  document.getElementById("list").innerHTML = list.length
    ? (VIEW === "michigan" && TAB !== "browse" ? michListHtml(list)
      : list.map(g => rowHtml(g, TAB === "browse")).join(""))
    : '<p class="empty">' + (TAB === "browse"
      ? "Pick a start and end date, then Load."
      : "Nothing matches those filters.") + "</p>";
  if (VIEW === "michigan" && TAB !== "browse") trimMichChips();
  drawSync();
}

function drawSync() {
  const n = pendingCount();
  document.getElementById("syncbar").classList.toggle("on", n > 0);
  document.getElementById("synctext").textContent =
    n + (n === 1 ? " unsaved change" : " unsaved changes");
}

/* ---------- the tag sheet ----------------------------------------------- */
function openSheet(id) {
  const g = (BROWSE || []).concat(GAMES).find(x => x.id === id) || eff(id).game;
  if (!g) return;
  SHEET = g;
  const e = eff(id), mine = myTags(id);
  const seen = Object.keys(TAGS).concat(Object.keys(PENDING))
    .reduce((a, k) => a.concat(myTags(k)), []);
  const known = Array.from(new Set(STARTER.concat(seen))).sort();
  const inArchive = GAMES.some(x => x.id === id) || !!e.add;

  // a neutral-site game has no home team, so "at" would be wrong
  document.getElementById("sh-title").textContent =
    teamName(g.teams[1], g.sport, g.season) + (g.neutral ? " vs " : " at ") +
    teamName(g.teams[0], g.sport, g.season);
  document.getElementById("sh-sub").textContent =
    g.dow + " " + g.date + "  ·  " + g.teams[1].score + "–" +
    g.teams[0].score + "  ·  " +
    (primaryNet(g.nets) || "no network listed");
  document.getElementById("sh-tags").innerHTML = known.map(t =>
    '<button class="f" aria-pressed="' + (mine.indexOf(t) > -1) +
    '" data-tag="' + esc(t) + '">' + esc(t) + "</button>").join("");
  document.getElementById("sh-note").value = e.note || "";
  const ib = document.getElementById("sh-inarch");
  ib.textContent = inArchive ? "Remove from archive" : "Add to archive";
  ib.dataset.on = String(inArchive);
  document.getElementById("sh-new").value = "";
  show("sheet");
}
function show(which) {
  document.getElementById("scrim").classList.add("on");
  document.getElementById(which).classList.add("on");
}
function hideAll() {
  document.getElementById("scrim").classList.remove("on");
  document.querySelectorAll(".sheet").forEach(s => s.classList.remove("on"));
  SHEET = null;
  draw();
}
function toggleTag(t) {
  if (!SHEET) return;
  const cur = myTags(SHEET.id).slice(), i = cur.indexOf(t);
  if (i < 0) cur.push(t); else cur.splice(i, 1);
  setPending(SHEET.id, { tags: cur }, SHEET);
  openSheet(SHEET.id);
}

/* ---------- Browse: ESPN queried live from the browser ------------------ */
const ESPN = {
  CFB: ["football/college-football", "80"],
  CBB: ["basketball/mens-college-basketball", "50"]
};
function etParts(iso) {
  const f = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit",
    day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
    weekday: "short"
  }).formatToParts(new Date(iso));
  const g = t => f.find(p => p.type === t).value;
  return {
    date: g("year") + "-" + g("month") + "-" + g("day"),
    time: (g("hour") === "24" ? "00" : g("hour")) + ":" + g("minute"),
    dow: g("weekday").slice(0, 3)
  };
}
function normalize(ev, sport) {
  const c = (ev.competitions || [])[0];
  if (!c) return null;
  const cs = c.competitors || [];
  if (cs.length !== 2) return null;
  if (!((c.status || {}).type || {}).completed) return null;
  const p = etParts(ev.date), nets = [];
  (c.broadcasts || []).forEach(b => (b.names || []).forEach(n => nets.push(n)));
  const teams = cs.map(k => {
    const r = (k.curatedRank || {}).current;
    if (k.team && !TEAMS[k.team.id]) {
      TEAMS[k.team.id] = { short: k.team.location || k.team.displayName,
                           name: k.team.displayName };
    }
    return {
      id: k.team.id, score: +k.score, rank: (r && r !== 99) ? r : null,
      win: !!k.winner, home: k.homeAway === "home",
      color: k.team.color || "", name: k.team.location || k.team.displayName
    };
  });
  const v = c.venue || {};
  return {
    id: ev.id, sport: sport, season: null, date: p.date, dow: p.dow,
    time: p.time, neutral: !!c.neutralSite,
    ot: ((c.status || {}).period || 0) > (sport === "CFB" ? 4 : 2),
    venue: v.fullName, city: (v.address || {}).city,
    nets: Array.from(new Set(nets)).sort(), teams: teams,
    week: (ev.week || {}).number || null,
    slots: [], big: [], champ: null,
    round: ((c.notes || [])[0] || {}).headline || null
  };
}
async function browseLoad() {
  const a = document.getElementById("from").value;
  const b = document.getElementById("to").value;
  if (!a || !b) { toast("Pick both dates", true); return; }
  document.getElementById("list").innerHTML =
    '<p class="empty">Loading…</p>';
  const from = a.replace(/-/g, ""), to = b.replace(/-/g, ""), out = [];
  let capped = false;
  for (const sp of Object.keys(ESPN)) {
    const path = ESPN[sp][0], grp = ESPN[sp][1];
    try {
      const r = await fetch("https://site.api.espn.com/apis/site/v2/sports/" +
        path + "/scoreboard?dates=" + from + "-" + to + "&groups=" + grp +
        "&limit=1000");
      if (!r.ok) continue;
      const j = await r.json();
      const ev = j.events || [];
      if (ev.length >= 1000) capped = true;
      ev.forEach(e => { const g = normalize(e, sp); if (g) out.push(g); });
    } catch (e) { toast("Could not reach ESPN", true); }
  }
  BROWSE = out;
  // ESPN silently caps a range at 1000 events rather than paginating
  if (capped) toast("1000-game cap hit — narrow the range", true);
  draw();
}

/* ---------- saving to GitHub -------------------------------------------- */
function toast(msg, bad) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.toggle("bad", !!bad);
  t.classList.add("on");
  setTimeout(() => t.classList.remove("on"), 3200);
}
function b64encode(s) {
  return btoa(String.fromCharCode.apply(null,
    Array.from(new TextEncoder().encode(s))));
}
function b64decode(s) {
  return new TextDecoder().decode(
    Uint8Array.from(atob(s.replace(/\s/g, "")), c => c.charCodeAt(0)));
}
async function save() {
  const tk = token();
  if (!tk) { show("settings"); toast("Add a GitHub token first", true); return; }
  const api = "https://api.github.com/repos/" + REPO + "/contents/" + TAGS_PATH;
  const hdr = { Authorization: "Bearer " + tk,
                Accept: "application/vnd.github+json" };
  const btn = document.getElementById("savebtn");
  btn.disabled = true;
  try {
    // read the CURRENT file first, so two devices merge instead of clobbering
    let sha = null, remote = {};
    const g = await fetch(api, { headers: hdr });
    if (g.status === 200) {
      const j = await g.json();
      sha = j.sha;
      try { remote = JSON.parse(b64decode(j.content)) || {}; } catch (e) { }
    } else if (g.status !== 404) {
      throw new Error("GitHub said " + g.status);
    }
    const merged = Object.assign({}, remote);
    Object.keys(PENDING).forEach(id => {
      const v = PENDING[id];
      const empty = (!v.tags || !v.tags.length) && !v.add && !v.hide && !v.note;
      if (empty) delete merged[id]; else merged[id] = v;
    });
    const body = {
      message: "tags: " + pendingCount() + " change(s) from the app",
      content: b64encode(JSON.stringify(merged, null, 1))
    };
    if (sha) body.sha = sha;
    const p = await fetch(api,
      { method: "PUT", headers: hdr, body: JSON.stringify(body) });
    if (!p.ok) {
      const j = await p.json().catch(() => ({}));
      throw new Error(j.message || ("GitHub said " + p.status));
    }
    TAGS = merged;
    PENDING = {};
    lsSet("pending", {});
    toast("Saved to GitHub");
  } catch (e) {
    toast(String(e.message || e), true);
  } finally {
    btn.disabled = false;
    draw();
  }
}

/* ---------- wiring ------------------------------------------------------ */
async function init() {
  PENDING = lsGet("pending", {});
  const v = "?v=" + BUILD;
  const r = await Promise.all([
    fetch("games.json" + v).then(x => x.json()),
    fetch("colors.json" + v).then(x => x.json()).catch(() => ({})),
    fetch("crests.json" + v).then(x => x.json()).catch(() => ({}))]);
  GAMES = r[0].games; TEAMS = r[0].teams; COLORS = r[1]; CRESTS = r[2];
  ORDER = r[0].order || {};
  SEASONS = r[0].seasons || [];
  WINDOW_NET = r[0].window_net || {};
  HEADER_TINT = r[0].header_tint || {};
  NET_TINT = r[0].net_tint || {};
  BIG_TEN = r[0].big_ten || {};
  SEASON_NAMES = r[0].season_names || {};
  HIDDEN_WINDOWS = r[0].hidden_windows || {};
  NET_PRIORITY = r[0].net_priority || {};
  clearFilters();
  try {
    // cache-bust: Pages serves with max-age, and this file is the shared state
    const t = await fetch("tags.json?" + Date.now(), { cache: "no-store" });
    if (t.ok) TAGS = await t.json();
  } catch (e) { }

  // LOCAL dates, not toISOString -- that reads UTC, so an evening in the
  // Eastern time zone would open Browse on tomorrow.
  const ymd = d => d.getFullYear() + "-" +
    String(d.getMonth() + 1).padStart(2, "0") + "-" +
    String(d.getDate()).padStart(2, "0");
  // Browse opens on the past week, which is the stretch he is actually
  // checking -- a single day is almost always empty.
  document.getElementById("from").value = ymd(new Date(Date.now() - 7 * 864e5));
  document.getElementById("to").value = ymd(new Date());
  draw();

  document.querySelectorAll("nav button").forEach(b =>
    b.addEventListener("click", e => {
      TAB = e.currentTarget.dataset.tab;
      // Switching sport goes back to the TAB DEFAULT, not merely clean filters
      // (his call 2026-09-11): TV Windows, the latest season with games,
      // Marquee on, Newest First. CFB and CBB share no game types or windows
      // anyway, so a value left over from the other sport would filter
      // everything away.
      VIEW = "tv";
      SORT = "desc";
      clearFilters();
      draw();
      window.scrollTo({ top: 0 });
    }));
  document.querySelectorAll("#viewbar button").forEach(b =>
    b.addEventListener("click", e => {
      // the sport does not change, so the filters are still valid -- only the
      // game-type / TV-window pair is view-specific
      const leaving = VIEW;
      VIEW = e.currentTarget.dataset.view;
      FILT.type = null;
      FILT.windows = null;
      FILT.marquee = VIEW === "tv";
      if (VIEW === "rivals") {
        // his Rivals default (2026-09-11): every season, newest first, opened
        // on Ohio State in football and Michigan State in basketball
        FILT.season = null; FILT.week = null; FILT.month = null; FILT.team = null;
        FILT.rival = SPORT_OF[TAB] === "CFB" ? "194" : "127";
        FILT.post = false; FILT.winner = null;
        SORT = "desc";
      } else if (VIEW === "michigan") {
        // the Michigan view opens on its newest season, in schedule order
        FILT.season = latestSeason(); FILT.week = null; FILT.month = null;
        FILT.team = null; FILT.rival = null; FILT.post = false; FILT.winner = null;
        SORT = "asc";
      } else if (leaving === "rivals" || leaving === "michigan") {
        // leaving Rivals or Michigan puts back the season a normal view opens on
        FILT.season = latestSeason(); FILT.week = null; FILT.month = null;
        FILT.team = null; FILT.rival = null; FILT.post = false; FILT.winner = null;
        if (leaving === "michigan") SORT = "desc";
      }
      draw();
      window.scrollTo({ top: 0 });
    }));
  document.getElementById("filters").addEventListener("click", e => {
    const b = e.target.closest("button.f[data-act]");
    if (!b) return;
    if (b.dataset.act === "marquee") {
      FILT.marquee = !FILT.marquee;
    } else if (b.dataset.act === "post") {
      FILT.post = !FILT.post;
    } else {
      SORT = SORT === "asc" ? "desc" : "asc";
    }
    draw();
  });
  document.getElementById("filters").addEventListener("change", e => {
    const k = e.target.dataset && e.target.dataset.kind;
    if (!k) return;
    const v = e.target.value;
    if (k === "window") FILT.windows = v === "" ? null : [v];
    else FILT[k] = v === "" ? null
      : ((k === "season" || k === "week" || k === "month") ? +v : v);
    // a week or month chosen under one season may not exist in another
    if (k === "season") { FILT.week = null; FILT.month = null; }
    draw();
  });
  document.getElementById("list").addEventListener("click", e => {
    const row = e.target.closest("button.row");
    if (row) openSheet(row.dataset.id);
  });
  document.getElementById("sh-tags").addEventListener("click", e => {
    const b = e.target.closest("button");
    if (b) toggleTag(b.dataset.tag);
  });
  document.getElementById("sh-add").addEventListener("click", () => {
    const v = document.getElementById("sh-new").value.trim();
    if (v) toggleTag(v);
  });
  document.getElementById("sh-inarch").addEventListener("click", e => {
    if (!SHEET) return;
    const on = e.currentTarget.dataset.on === "true";
    const known = GAMES.some(x => x.id === SHEET.id);
    setPending(SHEET.id, known ? { hide: on } : { add: !on }, SHEET);
    openSheet(SHEET.id);
  });
  document.getElementById("sh-note").addEventListener("change", e => {
    if (SHEET) setPending(SHEET.id, { note: e.target.value.trim() }, SHEET);
  });
  document.querySelectorAll(".done").forEach(b =>
    b.addEventListener("click", hideAll));
  document.getElementById("scrim").addEventListener("click", hideAll);
  // Clear Filters wipes everything, including the opening defaults -- it is
  // the escape from "newest season + Marquee", not a reset to it.
  document.getElementById("clearbtn").addEventListener("click", () => {
    FILT = { season: null, week: null, month: null, type: null, windows: null,
             team: null, marquee: false, rival: null, post: false, winner: null };
    draw();
    window.scrollTo({ top: 0 });
  });
  document.getElementById("settingsbtn").addEventListener("click", () => {
    document.getElementById("tokbox").value = token();
    show("settings");
  });
  document.getElementById("savetok").addEventListener("click", () => {
    try {
      localStorage.setItem("gh_token",
        document.getElementById("tokbox").value.trim());
    } catch (e) { }
    toast("Token saved on this device");
    hideAll();
  });
  document.getElementById("savebtn").addEventListener("click", save);
  document.getElementById("goload").addEventListener("click", browseLoad);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") hideAll();
  });
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => { });
  }
}
init();
