/* Games History -- the whole app. site.py copies this in and fills the
   __PLACEHOLDERS__. Kept as a real .js file rather than a Python string so it
   stays editable and lintable. */
const REPO = "kyeill/games-history", TAGS_PATH = "docs/tags.json";
const STARTER = ["College GameDay", "Big Noon Kickoff"];
// Every data file carries the build stamp. Without it a rebuild keeps serving
// the PREVIOUS games.json out of the service worker / HTTP cache -- which it
// did, silently, and the page rendered games missing their newest fields.
const BUILD = "20260909-165817";
const CARD = [0x1e, 0x1e, 0x23];
let GAMES = [], TEAMS = {}, COLORS = {}, CRESTS = {}, TAGS = {}, PENDING = {};
// TAB is the SPORT (his call 2026-09-09 -- he wants each population isolable);
// VIEW switches between the two collections within it.
let BROWSE = null, TAB = "cfb", VIEW = "tv", SHEET = null;
let FILT = { season: null, type: null, window: null, team: null, tag: null };
const SPORT_OF = { cfb: "CFB", cbb: "CBB" };

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
function teamName(t) {
  return (TEAMS[t.id] && TEAMS[t.id].short) || t.name || t.id;
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
function fmtTime(t) {
  const p = t.split(":"), h = +p[0] % 12 || 12;
  return h + ":" + p[1] + (+p[0] < 12 ? "am" : "pm");
}
function chip(kind, text) {
  return '<span class="tag t-' + kind + '">' + esc(text) + "</span>";
}
function teamLine(t) {
  return '<div class="tl' + (t.win ? " won" : "") + '">' +
    '<img class="crest" loading="lazy" src="' + crest(t) + '" alt="">' +
    '<span class="rk">' + (t.rank || "") + "</span>" +
    '<span class="nm">' + esc(teamName(t)) + "</span>" +
    '<span class="sc">' + t.score + "</span></div>";
}

function rowHtml(g, browse) {
  const home = g.teams[0], away = g.teams[1];
  const win = home.win ? home : away;
  const tags = [];
  (g.slots || []).forEach(s => tags.push(chip("slot", s)));
  // the raw rule names (#1 loses, top-10 vs top-10, ...) stay in the data but
  // are not drawn: Game Type is the vocabulary Kyle filters in
  if (g.type) tags.push(chip("big", g.type));
  if (g.champ) {
    const r = g.round || "";
    tags.push(chip("champ", g.champ + " " +
      (r.indexOf(" - ") > -1 ? r.split(" - ").pop() : "Championship")));
  }
  if (g.ot) tags.push(chip("ot", "OT"));
  myTags(g.id).forEach(t => tags.push(chip("mine", t)));

  const inArch = GAMES.some(x => x.id === g.id) || isAdded(g.id);
  const mark = browse && inArch ? ' <span class="inarch">IN ARCHIVE</span>' : "";
  const neutral = g.neutral ? ' <span class="nu">neutral</span>' : "";
  const site = g.neutral && g.city
    ? '<div class="site">' + esc(g.city) + "</div>" : "";
  // A maize BORDER flags a Michigan win or a rival loss. A full maize box was
  // too loud, so the winner's line keeps its own colour either way.
  return '<button class="row' + (celebrated(g) ? " celebrate" : "") +
    '" data-id="' + g.id + '" style="--winwash:' +
    shade(teamColor(win)) + '">' +
    '<div class="sport">' + g.sport + neutral + mark + "</div>" +
    '<div class="teams">' + teamLine(away) + teamLine(home) + "</div>" +
    '<div class="meta"><div class="when">' + g.dow + " " +
      g.date.slice(5).replace("-", "/") + "/" + g.date.slice(2, 4) +
      '</div><div class="tm">' + fmtTime(g.time) + "</div>" +
      '<div class="net">' +
      esc((g.nets || []).slice(0, 2).join(", ") || "—") + "</div>" +
      site + "</div>" +
    '<div class="tags">' + tags.join("") + "</div></button>";
}

/* Kyle's teams. ESPN gives a school one id across both sports. */
const MICHIGAN = "130";
const RIVALS = ["194", "127", "87"];   // Ohio State, Michigan State, Notre Dame

function bigViewAllows(g) {
  // Big Games is the view he browses for pleasure: no Michigan losses and no
  // rival wins. Both still appear under TV Windows, which is a record of what
  // was ON, not a highlight reel.
  const mich = g.teams.find(t => t.id === MICHIGAN);
  if (mich && !mich.win) return false;
  return !g.teams.some(t => RIVALS.indexOf(t.id) > -1 && t.win);
}
function celebrated(g) {
  // Michigan won, or a rival lost -- the two results worth flagging.
  if (g.teams.some(t => t.id === MICHIGAN && t.win)) return true;
  return g.teams.some(t => RIVALS.indexOf(t.id) > -1 && !t.win);
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
  list = list.filter(g => VIEW === "tv"
    ? (g.slots || []).length
    : ((g.type || g.champ) && bigViewAllows(g)));
  if (FILT.season != null) list = list.filter(g => g.season === FILT.season);
  if (FILT.window) list = list.filter(g =>
    (g.slots || []).indexOf(FILT.window) > -1);
  if (FILT.type) list = list.filter(g => g.type === FILT.type);
  if (FILT.team) list = list.filter(g =>
    g.teams.some(t => t.id === FILT.team));
  if (FILT.tag) list = list.filter(g =>
    myTags(g.id).indexOf(FILT.tag) > -1 ||
    (FILT.tag === "OT" && g.ot) || (FILT.tag === "neutral" && g.neutral) ||
    g.champ === FILT.tag);
  list.sort((a, b) => a.date === b.date
    ? a.time.localeCompare(b.time) : b.date.localeCompare(a.date));
  return list;
}

function filterChips() {
  if (TAB === "browse") return "";
  // Every filter is a dropdown (his call 2026-09-09). Game type and TV window
  // are drawn from the games in the CURRENT SPORT, because CFB and CBB share
  // none of their values.
  const scope = GAMES.filter(g => g.sport === SPORT_OF[TAB]);
  const types = new Set(), windows = new Set(), champs = new Set();
  scope.forEach(g => {
    if (g.type) types.add(g.type);
    (g.slots || []).forEach(s => windows.add(s));
    if (g.champ) champs.add(g.champ);
  });

  const group = (label, inner) => '<div class="fgroup"><span class="flabel">' +
    label + "</span>" + inner + "</div>";
  const select = (kind, allLabel, pairs, current) =>
    '<select class="fsel" data-kind="' + kind + '">' +
    '<option value="">' + allLabel + "</option>" +
    pairs.map(p => '<option value="' + esc(p[1]) + '"' +
      (String(current) === String(p[1]) ? " selected" : "") + ">" +
      esc(p[0]) + "</option>").join("") + "</select>";

  let h = group("Year", select("season", "All years",
    [2021, 2022, 2023, 2024, 2025].map(y =>
      [y + "-" + String(y + 1).slice(2), y]), FILT.season));
  h += group("Game type", select("type", "All game types",
    Array.from(types).sort().map(t => [t, t]), FILT.type));
  h += group("TV window", select("window", "All TV windows",
    Array.from(windows).sort().map(w => [w, w]), FILT.window));
  h += group("Team", select("team", "All teams",
    Object.keys(TEAMS).map(id => [TEAMS[id].short || id, id])
      .sort((a, b) => a[0].localeCompare(b[0])), FILT.team));
  // His own tags (College GameDay, Big Noon Kickoff) are DETAILS on the row,
  // not filters -- he said so explicitly.
  h += group("Tag", select("tag", "Any",
    [["Overtime", "OT"], ["Neutral site", "neutral"]].concat(
      Array.from(champs).sort().map(c => [c + " title", c])), FILT.tag));
  return h;
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
    teamName(g.teams[1]) + (g.neutral ? " vs " : " at ") + teamName(g.teams[0]);
  document.getElementById("sh-sub").textContent =
    g.dow + " " + g.date + "  ·  " + g.teams[1].score + "–" +
    g.teams[0].score + "  ·  " +
    ((g.nets || []).join(", ") || "no network listed");
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
  try {
    // cache-bust: Pages serves with max-age, and this file is the shared state
    const t = await fetch("tags.json?" + Date.now(), { cache: "no-store" });
    if (t.ok) TAGS = await t.json();
  } catch (e) { }

  const today = new Date().toISOString().slice(0, 10);
  document.getElementById("from").value = today;
  document.getElementById("to").value = today;
  draw();

  const clearFilters = () => {
    FILT = { season: null, type: null, window: null, team: null, tag: null };
  };
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
      FILT.window = null;
      draw();
      window.scrollTo({ top: 0 });
    }));
  document.getElementById("filters").addEventListener("change", e => {
    const k = e.target.dataset && e.target.dataset.kind;
    if (!k) return;
    const v = e.target.value;
    FILT[k] = v === "" ? null : (k === "season" ? +v : v);
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
