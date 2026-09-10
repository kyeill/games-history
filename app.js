/* Games History -- the whole app. site.py copies this in and fills the
   __PLACEHOLDERS__. Kept as a real .js file rather than a Python string so it
   stays editable and lintable. */
const REPO = "__REPO__", TAGS_PATH = "__TAGS_PATH__";
const STARTER = __STARTER__;
// Every data file carries the build stamp. Without it a rebuild keeps serving
// the PREVIOUS games.json out of the service worker / HTTP cache -- which it
// did, silently, and the page rendered games missing their newest fields.
const BUILD = "__BUILD__";
const CARD = [0x1e, 0x1e, 0x23];
let GAMES = [], TEAMS = {}, COLORS = {}, CRESTS = {}, TAGS = {}, PENDING = {};
// TAB is the SPORT (his call 2026-09-09 -- he wants each population isolable);
// VIEW switches between the two collections within it.
let BROWSE = null, TAB = "cfb", VIEW = "tv", SHEET = null;
let FILT = { season: null, week: null, month: null, type: null, windows: null,
              team: null, marquee: false };

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
let SORT = "asc";
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
const NET_RANK = ["ABC", "CBS", "NBC", "FOX", "ESPN", "ESPN2", "ESPNU", "BTN",
                  "FS1", "FS2", "SECN", "Peacock", "Paramount+", "ESPN+"];
function primaryNet(nets) {
  if (!nets || !nets.length) return "";
  let best = nets[0], bestRank = 999;
  nets.forEach(n => {
    const r = NET_RANK.indexOf(n);
    if (r > -1 && r < bestRank) { bestRank = r; best = n; }
  });
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
const TAG_CLASS = { "Big Noon Kickoff": "g-yellow", "College GameDay": "g-red",
                    "H&H": "g-grey" };
function tagClass(t) { return TAG_CLASS[t] || ""; }

function chip(kind, text) {
  return '<span class="tag t-' + kind + '">' + esc(text) + "</span>";
}
function teamLine(t, sport, season) {
  return '<div class="tl' + (t.win ? " won" : "") + '">' +
    '<img class="crest" loading="lazy" src="' + crest(t) + '" alt="">' +
    '<span class="rk">' + (t.rank || "") + "</span>" +
    '<span class="nm">' + esc(teamName(t, sport, season)) + "</span>" +
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
  if (g.champ) {
    const r = g.round || "";
    tags.push(chip("champ", g.champ + " " +
      (r.indexOf(" - ") > -1 ? r.split(" - ").pop() : "Championship")));
  } else if (g.event) {
    tags.push(chip("champ", g.event));
  } else if (g.offsite) {
    // Named by VENUE, not city -- the venue IS the story here. Wrigley Field,
    // Ford Field, Madison Square Garden.
    tags.push(chip("champ", g.offsite));
  } else if (g.neutral && g.city) {
    tags.push(chip("champ", g.city));
  }
  myTags(g.id).forEach(t => tags.push(chip("mine " + tagClass(t), t)));
  // overtime underlines the winning score rather than adding a chip

  const inArch = GAMES.some(x => x.id === g.id) || isAdded(g.id);
  const mark = browse && inArch ? ' <span class="inarch">IN ARCHIVE</span>' : "";
  // Header: football reads "WEEK 1", with the window after a pipe when there
  // is one. Basketball reads the window, or the day of the week when there is
  // none. The DATE itself lives in the meta column now.
  const label = g.header;
  const tint = g.sport === "CFB" ? HEADER_TINT[label] : null;
  const netCol = g.sport === "CBB" ? NET_TINT[primaryNet(g.nets)] : null;
  const DAYS = { Mon: "Monday", Tue: "Tuesday", Wed: "Wednesday",
                 Thu: "Thursday", Fri: "Friday", Sat: "Saturday",
                 Sun: "Sunday" };
  let when;
  if (g.sport === "CFB") {
    when = (g.week ? '<span class="wk">Week ' + g.week + "</span>" : "") +
      (label ? (g.week ? " | " : "") + esc(label) : "");
    // Browse pulls straight from ESPN, where a week number can be missing;
    // never leave the header empty.
    if (!when) when = esc(DAYS[g.dow] || g.dow);
  } else {
    when = esc(label || DAYS[g.dow] || g.dow);
  }
  // A coloured BORDER flags a Michigan win or a rival loss. A full maize box
  // was too loud, so the winner's line keeps its own wash either way.
  const flag = celebrated(g);
  const ring = flag ? celebrateColor(g) : null;
  return '<button class="row' + (flag ? " celebrate" : "") +
    (dimmed(g) ? " dimmed" : "") + (g.ot ? " ot" : "") +
    '" data-id="' + g.id + '" style="--winwash:' + shade(teamColor(win)) +
    (ring ? ";--celeb:" + ring[0] + ";--celebring:" + ring[1] : "") + '">' +
    // The header row: slot label left, DATE right. The date sits here rather
    // than in the meta column because this is the only way it lines up with
    // the header. No weekday -- his call 2026-09-10.
    '<div class="sport"' + (tint ? ' style="color:' + tint + '"' : "") + ">" +
      "<span>" + when + mark + "</span>" +
      '<span class="hdate">' + fmtDate(g.date) + "</span></div>" +
    '<div class="teams">' + teamLine(away, g.sport, g.season) +
      teamLine(home, g.sport, g.season) + "</div>" +
    // network on the away team's line, time on the home team's
    '<div class="meta"><div class="mrow"' +
      (netCol ? ' style="color:' + netCol + '"' : "") + ">" +
      esc(primaryNet(g.nets) || "—") + '</div><div class="mrow">' +
      fmtTime(g.time) + "</div></div>" +
    '<div class="tags">' + tags.join("") + "</div></button>";
}

/* Kyle's teams. ESPN gives a school one id across both sports. */
const MICHIGAN = "130";
const RIVALS = ["194", "127", "87"];   // Ohio State, Michigan State, Notre Dame

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
    return m.win ? ["#ffcb05", "#ffcb0544"] : ["#5a5a62", "#5a5a6244"];
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
  list = list.filter(g => VIEW === "tv"
    ? ((g.slots || []).length || g.title || g.bfri || g.show)
    : (g.type && bigViewAllows(g)));
  // Basketball's TV tab is JANUARY TO MARCH (his standing rule, and his call
  // again 2026-09-10 for Marquee). The window rules already enforce it, but a
  // College GameDay game rides along on `show` with no window of its own --
  // two November games were reaching Marquee that way. Key Games still has
  // every month.
  if (VIEW === "tv" && SPORT_OF[TAB] === "CBB") {
    list = list.filter(g => {
      const m = +g.date.slice(5, 7);
      return m >= 1 && m <= 3;
    });
  }
  if (FILT.season != null) list = list.filter(g => g.season === FILT.season);
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
  const block = g => (g.sport === "CFB" && g.week)
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

// Opening state, not an empty one: newest season always, plus the upset
// category when the Key Games view is showing. A function declaration, not a
// const -- init() calls it before this point in the file.
function clearFilters() {
  FILT = {
    season: SEASONS.length ? Math.max.apply(null, SEASONS) : null,
    type: null,
    windows: null,
    // TV Windows opens on Marquee -- the games he plans a weekend around
    marquee: VIEW === "tv",
    week: null, month: null, team: null
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
  const select = (kind, allLabel, pairs, current) =>
    '<select class="fsel" data-kind="' + kind + '">' +
    '<option value="">' + allLabel + "</option>" +
    pairs.map(p => '<option value="' + esc(p[1]) + '"' +
      (String(current) === String(p[1]) ? " selected" : "") + ">" +
      esc(p[0]) + "</option>").join("") + "</select>";

  let h = group("Year", select("season", "All Years",
    SEASONS.slice().sort((a, b) => b - a).map(y => [seasonLabel(y), y]),
    FILT.season));
  // Football is played in numbered weeks; basketball is not. The list follows
  // the season, since week 16 only exists in some years.
  if (sport === "CFB") {
    const weeks = new Set();
    GAMES.forEach(g => {
      if (g.sport !== "CFB" || !g.week) return;
      if (FILT.season != null && g.season !== FILT.season) return;
      weeks.add(g.week);
    });
    h += group("Week", select("week", "All Weeks",
      Array.from(weeks).sort((a, b) => a - b).map(w => ["Week " + w, w]),
      FILT.week));
  }
  // Basketball has no week worth showing, so the month is its equivalent
  // coarse cut. Like the week list it follows the SEASON, and it also follows
  // the VIEW -- the TV tab is January to March, so offering November there
  // would be offering an empty list.
  if (sport === "CBB") {
    const months = new Set();
    GAMES.forEach(g => {
      if (g.sport !== "CBB") return;
      if (FILT.season != null && g.season !== FILT.season) return;
      const m = +g.date.slice(5, 7);
      if (VIEW === "tv" && (m < 1 || m > 3)) return;
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
  h += group("Team", select("team", "All Teams",
    Object.keys(TEAMS).map(id => [TEAMS[id].short || id, id])
      .sort((a, b) => a[0].localeCompare(b[0])), FILT.team));
  h += group("", quickButtons());
  return h;
}

function marqueeOn() { return !!FILT.marquee; }
function quickButtons() {
  return '<button class="f" data-act="marquee" aria-pressed="' + marqueeOn() +
    '">Marquee Windows</button>' +
    '<button class="f" data-act="sort">' +
    (SORT === "asc" ? "Oldest First" : "Newest First") + "</button>";
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
    ? list.map(g => rowHtml(g, TAB === "browse")).join("")
    : '<p class="empty">' + (TAB === "browse"
      ? "Pick a start and end date, then Load."
      : "Nothing matches those filters.") + "</p>";
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

  const today = new Date().toISOString().slice(0, 10);
  document.getElementById("from").value = today;
  document.getElementById("to").value = today;
  draw();

  document.querySelectorAll("nav button").forEach(b =>
    b.addEventListener("click", e => {
      TAB = e.currentTarget.dataset.tab;
      // CFB and CBB share no game types or TV windows, so a value left over
      // from the other sport would silently filter everything away
      clearFilters();
      draw();
      window.scrollTo({ top: 0 });
    }));
  document.querySelectorAll("#viewbar button").forEach(b =>
    b.addEventListener("click", e => {
      // the sport does not change, so the filters are still valid -- only the
      // game-type / TV-window pair is view-specific
      VIEW = e.currentTarget.dataset.view;
      FILT.type = null;
      // The TV tab is January to March on basketball, so a November chosen
      // under Key Games would survive the switch and empty the list.
      if (VIEW === "tv" && FILT.month != null
          && (FILT.month < 1 || FILT.month > 3)) FILT.month = null;
      FILT.windows = null;
      FILT.marquee = VIEW === "tv";
      draw();
      window.scrollTo({ top: 0 });
    }));
  document.getElementById("filters").addEventListener("click", e => {
    const b = e.target.closest("button.f[data-act]");
    if (!b) return;
    if (b.dataset.act === "marquee") {
      FILT.marquee = !FILT.marquee;
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
             team: null, marquee: false };
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
