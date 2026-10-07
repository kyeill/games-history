/* Games History -- the whole app. site.py copies this in and fills the
   __PLACEHOLDERS__. Kept as a real .js file rather than a Python string so it
   stays editable and lintable. */
// Every data file carries the build stamp. Without it a rebuild keeps serving
// the PREVIOUS games.json out of the service worker / HTTP cache -- which it
// did, silently, and the page rendered games missing their newest fields.
const BUILD = "__BUILD__";
const CARD = [0x1e, 0x1e, 0x23];
let GAMES = [], TEAMS = {}, COLORS = {}, CRESTS = {}, TAGS = {};
// TAB is the SPORT (his call 2026-09-09 -- he wants each population isolable);
// VIEW switches between the two collections within it.
// TOP is the tab along the top (his order, 2026-09-16): Michigan, CFB, CBB --
// Hockey and Detroit join as they are built, and Browse is gone. TAB is still
// the SPORT and VIEW the view within it, so every rule keyed on those is
// untouched; TOP only decides which buttons the second row offers.
let TOP = "michigan", TAB = "cfb", VIEW = "michigan";
let FILT = { season: null, week: null, month: null, type: null, windows: null,
              team: null, marquee: false, rival: null, post: false, winner: null,
              net: null, recent: false };
// what the filters were before CURRENT was pressed, so releasing it puts them
// back (his call 2026-09-16)
let CURRENT_PREV = null, COMB_PREV = null;

/* Season order, not calendar order: a basketball season runs Nov to Apr. */
const MONTHS = ["January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November",
                "December"];
function monthOrder(m) { return m >= 8 ? m - 12 : m; }
let ORDER = {}, SEASONS = [], WINDOW_NET = {};
let HEADER_TINT = {}, NET_TINT = {}, NET_PRIORITY = {}, BIG_TEN = {}, CONF_LABEL = {};
let FINAL_RANK = {}, CONF_PLACE = {}, CHAMPS = {};
// the conference a non-Michigan team view capitalises, per team and sport
let TEAM_CONF = {};
let SEASON_NAMES = {}, HIDDEN_WINDOWS = {};
// Oldest-first by default (his call 2026-09-09): with a season filter on, that
// reads as the season unfolding. The toggle flips it.
// THE DEFAULT SORT FOLLOWS THE DEVICE (his call 2026-09-13): a phone opens
// Newest First, because the newest game is what he checks; a desktop opens
// Oldest First, where the whole season reads down the page in order. The
// button still flips it either way, and every "back to the default" below
// asks this rather than assuming.
function defaultSort() {
  // ...except the MICHIGAN views, which open Oldest First on any device, bar
  // Combined (Newest First), and Cornell hockey, Oldest First too (his calls
  // 2026-09-18)
  if (typeof VIEW !== "undefined") {
    if (VIEW === "michigan") return SPORT_OF[TAB] ? "asc" : "desc";
    if (VIEW === "cornell" && SPORT_OF[TAB] === "CHK") return "asc";
  }
  return (window.innerWidth || 0) >= 900 ? "asc" : "desc";
}
// "all" is Michigan's COMBINED view (2026-09-18): every sport at once
const SPORT_OF = { cfb: "CFB", cbb: "CBB", chk: "CHK", all: null, nfl: "NFL",
                   nhl: "NHL", nba: "NBA", mlb: "MLB" };
let SORT = defaultSort();
// Key Games opens on the upset category -- it is the longest list and the one
// he actually came for. TV Windows opens unfiltered.

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
// THE MICHIGAN VIEW'S OWN WASH, where it differs from every other view: Notre
// Dame's card stays antique gold there while the rest of the site reads navy
// (his call 2026-09-16). A border marked "Opponent" still uses teamColor.
const MICH_WASH = { "87": "c99700" };
/* THE CONFERENCE FILTER (his call 2026-09-24). Each view lists the
   conferences he cares about, in his order, under a bar at the foot of the
   Teams dropdown. A game counts when a team was in that conference THAT
   SEASON -- the conference on the game, never today's alignment -- so Houston
   reads AAC before 2023 and Big XII after. */
const CONF_MENU = {
  CFB: ["SEC", "Big XII", "ACC", "Pac-12", "MAC", "Mountain West", "American"],
  CBB: ["SEC", "ACC", "Big XII", "Big East", "Pac-12", "MAC", "American",
        "Atlantic 10", "Mountain West"],
  CHK: ["Hockey East", "NCHC", "ECAC", "CCHA", "Atlantic"],
  CHK_CORNELL: ["Hockey East", "NCHC", "Big Ten", "CCHA", "Atlantic"],
  ALL: ["SEC", "Big XII", "ACC", "Big East", "Pac-12", "MAC", "Mountain West",
        "American"],
};
// the options themselves: a bar, then his conferences for this view, each one
// kept only when the list would return games under the other filters
function confOptions(pool) {
  const have = new Set();
  (pool || []).forEach(g => confsIn(g).forEach(c => have.add(c)));
  const list = confMenu().filter(c => have.has(c) || FILT.team === "conf:" + c);
  return list.length
    ? [["─".repeat(12), null]].concat(list.map(c => [c, "conf:" + c])) : [];
}
function confMenu() {
  if (!SPORT_OF[TAB]) return ["Big Ten"].concat(CONF_MENU.ALL);
  if (SPORT_OF[TAB] === "CHK")
    return VIEW === "cornell" ? CONF_MENU.CHK_CORNELL
      : ["Big Ten"].concat(CONF_MENU.CHK);
  const list = CONF_MENU[SPORT_OF[TAB]] || [];
  // EVERY list leads with the BIG TEN (his calls 2026-09-24) -- on a Michigan
  // view it picks out the conference games
  return ["Big Ten"].concat(list);
}
function confOf(g, t) {
  return ((CONF_LABEL[g.sport] || {})[String(t.conf)]) || "";
}
// the conferences a game can be filtered by: the opponents' own, never the
// focus team's (a Michigan view lists who Michigan played)
function confsIn(g) {
  return g.teams.filter(t => !teamView() || t.id !== focusId())
    .map(t => confOf(g, t)).filter(Boolean);
}
// A 7PM-OR-LATER START (his call 2026-09-25), the Michigan tab's Primetime.
// The postseason stays out, as it does for a network.
function primetime(g) {
  return !g.stage && g.time !== "TBD" && g.time >= "19:00";
}
function teamColor(t) {
  // a PRO team ("nfl-8") takes ESPN's colour from the team list
  const pro = t.id.indexOf("-") > 0 && TEAMS[t.id] ? TEAMS[t.id].color : null;
  // the colour the club wore THAT SEASON comes first (2026-09-28): it is set
  // on the game's own team side, and only for a franchise that has moved
  return (t.color || "").replace("#", "") || COLORS[t.id] || pro || "6a6a70";
}
function crest(t) {
  // the crest the club wore THAT SEASON, where the two differ (2026-09-28)
  if (t.logo) return t.logo;
  if (TEAMS[t.id] && TEAMS[t.id].logo) return TEAMS[t.id].logo;
  return CRESTS[t.id] ||
    "https://a.espncdn.com/i/teamlogos/ncaa/500-dark/" + t.id + ".png";
}
// ON A FILLED RIVALS CARD the winner's crest sits on its own colour, where the
// dark-ground logo can vanish -- Michigan's maize M on the maize fill (found
// 2026-09-18). ESPN's light-ground logo is outlined, so it is used there.
function washedWinner(t, g) {
  return !!(g && VIEW === "rivals" && t.win && rivalsFill(g));
}
function crestOnColour(t) {
  return CRESTS[t.id] || "https://a.espncdn.com/i/teamlogos/ncaa/500/" + t.id + ".png";
}
function teamName(t, sport, season) {
  // a pro team keeps the name it had THAT season (the New Jersey Nets)
  let nm = t.place || (TEAMS[t.id] && TEAMS[t.id].short) || t.name || t.id;
  // a name that changes with the era -- UCLA reads "Ucla" before 2023
  const sn = SEASON_NAMES[t.id];
  if (sn && season != null && season < sn.before) nm = sn.name;
  // Big Ten teams go up in caps. Membership is as of THAT SEASON, so USC is
  // capitalised from 2024 and not before.
  // RIVALS reads in proper case, all but Michigan and Cornell (his call
  // 2026-09-18)
  if (VIEW === "rivals") return (t.id === MICHIGAN || t.id === CORNELL) ? nm.toUpperCase() : nm;
  const caps = VIEW === "cornell" ? (TEAM_CONF[CORNELL] || {})[sport] : BIG_TEN[sport];
  return (sport && t.conf === caps) ? nm.toUpperCase() : nm;
}
/* ESPN'S CAPITALS (his call 2026-10-06). It wrote event and bowl names in
   capitals before about 2021 and in title case after -- "GAVITT TIPOFF GAMES"
   then "Gavitt Tipoff Games" -- so every test against one of its names
   compares without case. The same class of bug as "Fox" against "FOX". */
function sameName(a, b) {
  return String(a || "").toLowerCase() === String(b || "").toLowerCase();
}
function esc(s) {
  return String(s).replace(/[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* ---------- tag state --------------------------------------------------- */
// tags.json as it stands -- there is no local overlay any more (2026-09-14)
function eff(id) { return TAGS[id] || {}; }
function myTags(id) { return eff(id).tags || []; }
const SHOW_TAGS = ["Big Noon Kickoff", "College GameDay"];
// HIS LOCATIONS TAB IS THE ONLY SOURCE for the two shows (his call
// 2026-09-13). tags.json still holds the old hand-seeded copies, but they are
// deliberately NOT unioned in: he pruned the tab of postseason games and
// one-off weeknight shows, and reading the stale tags would put those chips
// straight back. They stay in the file, invisible, until they are cleaned out.
function showsOf(g) {
  const out = g.shows || [];
  return SHOW_TAGS.filter(t => out.indexOf(t) > -1);
}
function plainTags(g) {
  return myTags(g.id).filter(t => SHOW_TAGS.indexOf(t) < 0);
}
function isHidden(id) { return !!eff(id).hide; }
function isAdded(id) { return !!eff(id).add; }

/* ---------- rendering --------------------------------------------------- */
function fmtDate(d) {
  // "2025-09-06" -> "9/6/2025". Every view spells the year out (his call
  // 2026-09-14): the date sits top right, where the room is.
  return String(+d.slice(5, 7)) + "/" + String(+d.slice(8, 10)) + "/" +
    d.slice(0, 4);
}

/* THE NAME OF A POSTSEASON GAME, one way for every view (his calls
   2026-09-14). "Big Ten Tournament | Championship" reads

       2015 BIG TEN TOURNAMENT FINAL

   The YEAR is the one the game was PLAYED in -- football's season year,
   basketball's season plus one, since a basketball season is named for the
   year it starts. Then the bar goes; rounds 1 and 2 spell themselves out;
   Semis becomes Semifinals; a CONFERENCE tournament crowns a FINAL, while the
   NCAA and the NIT keep their Championship; and a conference title GAME says
   so, which the CFP championship must not. The Michigan card layers its own
   abbreviations on top of this. */
function stageYear(g) {
  return (g.sport === "CFB" ? g.season : g.season + 1) + " ";
}
function stageLabel(g) {
  let s = g.stage || "";
  if (!s) return "";
  // tested BEFORE the bar goes: "CFP | Championship" is not a title game
  if (s.indexOf(" | ") < 0 && /Championship$/.test(s)) s += " Game";
  s = s.replace(" | ", " ")
    .replace("Round 1", "First Round")
    .replace("Round 2", "Second Round")
    .replace("Semis", "Semifinals");
  if (/(Tournament|Ivy Madness) Championship$/.test(s) && !/^(NCAA|NIT)/.test(s)) {
    s = s.replace(/Championship$/, "Final");
  }
  return s;
}
/* THE SEASON LINE (his call 2026-09-29). With ONE season chosen on a
   Michigan view, the count at the top of the page gives way to how the season
   went: how far he got, then the conference.

     CFP Semis (13-1) | B1G CHAMPIONS (9-0)
     NCAA Sweet Sixteen (No. 4, 25-8) | B1G (14-6) | BTT CHAMPIONS (No. 3)

   Everything here is read from the games themselves -- the rounds from their
   stages, the records from their results -- except the final ranking, which
   comes from the polls (see harvest's final_rank) and stands in when he
   reached no round of his own. */
/* THE RECORD IS THE FIRST THING A PHONE GIVES UP (his call 2026-09-30):
   the line bled over its two lines and pushed the title onto a second one.
   Each record is wrapped so the stylesheet can drop it under 700px, seeds
   and rounds and names all staying. */
function rec(seed, record) {
  return seed != null
    ? " (No. " + seed + '<span class="srec">, ' + record + "</span>)"
    : '<span class="srec"> (' + record + ")</span>";
}
// a piece of the season line that celebrates something (2026-09-29)
function win(colour, html, bold) {
  // the callers build their own markup now -- a record wrapped so a phone can
  // drop it -- so this paints what it is given rather than escaping it
  return '<span style="color:' + colour + (bold ? ";font-weight:700" : "") +
    '">' + html + "</span>";
}
/* WHO WON THAT SEASON (his call 2026-09-29). TV Windows and Key Games are
   not his team's views, so with one season chosen they name the champions of
   it instead of counting games: the national champion, the Big Ten champion,
   and in basketball the tournament winner too.

   MICHIGAN goes up in capitals, bold and maize. Ohio State, Michigan State
   and Notre Dame are struck through. Any other Big Ten team that won the
   national title is capitalised, because that is the achievement being named.
   Everyone else keeps their own colour -- never a yellow one, which belongs
   to Michigan alone. */
function bigTenTeam(id, sport, season) {
  const conf = (BIG_TEN || {})[sport];
  return !!conf && GAMES.some(g => g.sport === sport && g.season === season &&
    g.teams.some(t => t.id === id && t.conf === conf));
}
function champColour(id) {
  const raw = teamColor({ id: id });
  const hex = "#" + String(raw).replace("#", "");
  const c = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
  const hi = Math.max.apply(null, c), lo = Math.min.apply(null, c);
  const d = hi - lo;
  let h = 0;
  if (d) {
    h = hi === c[0] ? ((c[1] - c[2]) / d + (c[1] < c[2] ? 6 : 0))
      : hi === c[1] ? (c[2] - c[0]) / d + 2 : (c[0] - c[1]) / d + 4;
    h *= 60;
  }
  // a yellow keeps the page's one yellow for Michigan, so it gives way to the
  // team's second colour, or to grey where that is yellow too
  const yellow = x => x >= 38 && x <= 72 && d > 0.25;
  if (!yellow(h)) return brighten(hex, 150);
  const alt = (TEAMS[id] || {}).alt;
  return alt ? brighten("#" + alt.replace("#", ""), 150) : "#b4b4ae";
}
function champPart(t, sport, season, national) {
  if (!t || !t[0]) return null;
  const id = t[0];
  const mich = id === MICHIGAN;
  const rival = RIVALS.indexOf(id) > -1;
  // the capitals mark the achievement: Michigan wherever it appears, and a
  // Big Ten team that won the NATIONAL title (his call 2026-09-29) -- not
  // merely one that won the conference, which is what that slot is for
  const caps = mich || (national && bigTenTeam(id, sport, season));
  const nm = caps ? String(t[1]).toUpperCase() : t[1];
  const style = mich ? "color:#ffcb05;font-weight:700"
    : "color:" + champColour(id) + (rival ? ";text-decoration:line-through" : "");
  return '<span style="' + style + '">' + esc(nm) + "</span>";
}
function champLine() {
  const sport = SPORT_OF[TAB];
  const ch = CHAMPS[sport + "-" + FILT.season];
  if (!ch) return null;
  const part = (t, nat) => champPart(t, sport, FILT.season, nat);
  // ...each under the title it won (his call 2026-09-30), since stacked on a
  // phone the order alone no longer says which is which
  const tag = x => '<span class="srole">' + x + ":</span> ";
  const out = [];
  if (ch.nat) out.push(tag(sport === "CFB" ? "CFP" : "NCAA") + part(ch.nat, true));
  // a SHARED Big Ten title names everyone who won it, slashed together
  if ((ch.conf || []).length) {
    // (map hands its callback an INDEX too, which read as "this is the
    //  national champion" and capitalised the second name -- 2026-09-29)
    out.push(tag("B1G") + (ch.conf || []).map(t => part(t)).filter(Boolean).join("/"));
  }
  if (sport === "CBB" && ch.cup) out.push(tag("BTT") + part(ch.cup));
  if (!out.length) return null;
  return out.map(x => '<span class="spart">' + x + "</span>")
    .join('<span class="ssep"> | </span>');
}
function ordinal(n, tied) {
  const tens = n % 100, ones = n % 10;
  const suffix = (tens >= 11 && tens <= 13) ? "th"
    : ones === 1 ? "st" : ones === 2 ? "nd" : ones === 3 ? "rd" : "th";
  return (tied ? "t-" : "") + n + suffix;
}
function seasonRound(games, prefix) {
  // the LAST stage game of a run, which is the furthest he got
  const run = games.filter(g => (g.stage || "").indexOf(prefix) === 0 && !upcoming(g));
  if (!run.length) return null;
  const last = run[run.length - 1];
  const me = last.teams.find(t => t.id === focusId());
  return { game: last, won: !!(me && me.win), seed: seedOf(last, me) };
}
function seasonLine() {
  const fid = focusId(), sport = SPORT_OF[TAB];
  const games = GAMES.filter(g => g.sport === sport && g.focus === fid &&
    g.season === FILT.season && !upcoming(g));
  if (!games.length) return null;
  const mine = g => g.teams.find(t => t.id === fid) || {};
  // the OVERALL record, ties and all -- hockey keeps its third number
  let w = 0, l = 0, t = 0;
  games.forEach(g => { if (g.tie) t++; else if (mine(g).win) w++; else l++; });
  const recd = w + "-" + l + (t ? "-" + t : "");
  // ...and the CONFERENCE record, the regular season only. CORNELL answers
  // to the ECAC rather than the Big Ten (his call 2026-09-29).
  const cornell = fid === CORNELL;
  const conf = cornell ? (TEAM_CONF[CORNELL] || {})[sport] : (BIG_TEN || {})[sport];
  let cw = 0, cl = 0, ct = 0, any = false;
  games.forEach(g => {
    if (g.stage || g.post) return;
    const opp = g.teams.find(q => q.id !== fid) || {};
    if (!conf || opp.conf !== conf) return;
    any = true;
    if (g.tie) ct++; else if (mine(g).win) cw++; else cl++;
  });
  // the round a stage names, in his short forms -- "Semis", not
  // "Semifinals" -- but an early round spelled out (his call 2026-09-29)
  const tail = g => ((g.stage || "").split(" | ")[1] || g.stage || "")
    .replace(/^Round 1$/, "First Round").replace(/^Round 2$/, "Second Round");
  const parts = [];
  // 1. THE NATIONAL POSTSEASON: the furthest round, or where he finished --
  // and where he missed it, the NIT still says how far he got (his call
  // 2026-09-29, for 2022-23)
  const nat = sport === "CFB" ? seasonRound(games, "CFP")
    : seasonRound(games, "NCAA Tournament") ||
      (sport === "CBB" ? seasonRound(games, "NIT") : null);
  const natName = sport === "CFB" ? "CFP"
    : nat && (nat.game.stage || "").indexOf("NIT") === 0 ? "NIT" : "NCAA";
  if (nat) {
    const round = tail(nat.game).replace(/^Championship$/, "Final");
    // the SEED belongs to basketball and hockey; football's playoff had none
    // until 2024 and he does not want one there (his call 2026-09-29)
    const seedNo = sport !== "CFB" ? nat.seed : null;
    /* HOW DEEP A RUN HAS TO BE TO WEAR ITS COLOUR (his calls 2026-09-29):
       every CFP game is gold, because reaching it at all is the achievement;
       basketball turns blue at the Sweet Sixteen and hockey at the Frozen
       Four, the point at which each tournament stops being a first weekend.
       A run that ended before then is MAIZE -- it still got him there. A
       title is bold on top of the colour, and the NIT is never painted. */
    const DEEP = { CBB: ["Sweet Sixteen", "Elite Eight", "Final Four", "Final"],
                   CHK: ["Frozen Four", "Final"] };
    const deep = (DEEP[sport] || []).indexOf(round) > -1;
    // ...and CORNELL wears its own red for the NCAA Tournament rather than
    // Michigan's maize, at any depth (his call 2026-09-30)
    const colour = sport === "CFB" ? "#c28c19"
      : natName !== "NCAA" ? null
      : deep ? "#4d9ae0" : cornell ? "#c0053c" : "#ffcb05";
    /* HOW IT READS (his calls 2026-09-29): the NCAA Tournament goes without
       saying, so only its FINAL names it; the rounds he remembers by name go
       up in capitals. Football keeps the CFP in front of its rounds. */
    const CAPS = ["Final Four", "Frozen Four", "Final", "Semis"];
    const label = (sport === "CFB" ? "CFP " : natName === "NIT" ? "NIT "
      : round === "Final" ? "NCAA " : "") +
      (CAPS.indexOf(round) > -1 ? round.toUpperCase() : round);
    const text = (nat.won && round === "Final" ? "NATIONAL CHAMPIONS" : label) +
      rec(seedNo, recd);
    parts.push(colour ? win(colour, text, nat.won && round === "Final") : text);
  } else {
    // ...or where he finished: the number alone, and NR when he finished
    // outside it (his call 2026-09-29). Which poll it came from is not worth
    // the room -- the CFP committee's last from 2014, the AP before that,
    // and USCHO's last for hockey.
    const fr = FINAL_RANK[sport + "-" + FILT.season] || {};
    const n = fr.cfp || fr.ap;
    // ...and a NEW YEAR'S SIX BOWL is the season's achievement where there
    // was no playoff to reach, so the ranking wears maize (his call
    // 2026-09-29): 2011, 2016 and 2018
    const ny6 = sport === "CFB" && games.some(ny6Bowl);
    const text = (n ? "#" + n : "NR") + rec(null, recd);
    parts.push(ny6 ? win("#ffcb05", text) : text);
  }
  // 2. THE CONFERENCE: where he finished in it, and the DIVISION he finished
  // in where there was one -- "2nd B1G East", "t-5th B1G" (his call
  // 2026-09-29). First place reads CHAMPIONS, shared first CO-CHAMPIONS;
  // football answers to its title game instead, which is what decides the
  // conference there.
  /* ...AND SO IS CORNELL'S (2026-09-29): the ECAC seeds its tournament by
     the same standings, so the seed is the finish there too.
     HOCKEY'S PLACE IS ITS TOURNAMENT SEED (his call 2026-09-29, after the
     table was built and thrown away). ESPN carries no Big Ten hockey
     standings, and the table USCHO's schedules give cannot reproduce the
     conference's own -- its shootout results are half missing, and the
     ordering rule changed along the way, so five of thirteen seasons came out
     a place wrong. The Big Ten seeds its tournament BY those standings, so
     the seed is the finish, and it is already on the cards. */
  // the conference tournament of whichever conference he is in
  const cupName = cornell ? "ECAC Tournament" : "Big Ten Tournament";
  const cupShort = cornell ? "ECACT" : "BTT";
  const bttSeed = sport === "CHK"
    ? (seasonRound(games, cupName) || {}).seed : null;
  /* WHERE NO TOURNAMENT SEEDED THE SEASON (his call 2026-09-30): 2019-20
     stopped before the ECAC's, and Cornell had won the league outright. */
  const FINISH_FIX = { "172-CHK-2019": { place: 1, tied: false, division: null } };
  const fix = FINISH_FIX[fid + "-" + sport + "-" + FILT.season];
  const place = (fix && Object.assign({}, fix,
      { record: cw + "-" + cl + (ct ? "-" + ct : "") })) ||
    CONF_PLACE[sport + "-" + FILT.season] ||
    (bttSeed != null ? { place: bttSeed, tied: false, division: null,
                         record: cw + "-" + cl + (ct ? "-" + ct : "") } : null);
  if (any || place) {
    const cRec = place ? place.record : cw + "-" + cl + (ct ? "-" + ct : "");
    const name = (cornell ? "ECAC" : "B1G") +
      (place && place.division ? " " + place.division : "");
    const title = seasonRound(games, "Big Ten Championship");
    // A SHARED TITLE READS AS A PLACE, not as a championship (his call
    // 2026-09-29): "t-1st B1G", in maize. Only a title of his own is blue.
    let head, colour = null;
    if (sport === "CFB") {
      head = title && title.won ? "B1G CHAMPIONS"
        : place ? ordinal(place.place, place.tied) + " " + name : name;
    } else if (place && place.place === 1 && !place.tied) {
      head = name + " CHAMPIONS";
    } else {
      head = place ? ordinal(place.place, place.tied) + " " + name : name;
      if (place && place.place === 1) colour = "#ffcb05";
    }
    // the ECAC's own red where it is his conference, the Big Ten's blue
    // otherwise -- the same two the cards and the tiles use (2026-09-29)
    const confBlue = cornell ? "#c0053c" : "#0088ce";
    const cText = head + rec(null, cRec);
    parts.push(/CHAMPIONS/.test(head) ? win(confBlue, cText, true)
      : colour ? win(colour, cText) : cText);
    /* THE IVY LEAGUE SITS BETWEEN THEM (his call 2026-09-29), in its own
       green: the six Ivies play each other inside the ECAC, and harvest marks
       those games, so the record is read straight off them. */
    if (cornell) {
      let iw = 0, il = 0, it = 0;
      games.forEach(g => {
        if ((g.labels || []).indexOf("Ivy League") < 0) return;
        if (g.tie) it++; else if (mine(g).win) iw++; else il++;
      });
      if (iw + il + it) {
        parts.push(win("#0f6a37",
          "Ivy" + rec(null, iw + "-" + il + (it ? "-" + it : ""))));
      }
    }
  }
  // 3. ...and the CONFERENCE TOURNAMENT, basketball and hockey (his call)
  /* 2019-20 HAD NO CONFERENCE TOURNAMENT TO SPEAK OF (his call 2026-09-30):
     the Big Ten's and the ECAC's were called off part-played, so neither says
     anything. Cornell had already won the ECAC outright, which is the finish
     that season shows -- there was no tournament to seed it. */
  if ((sport === "CBB" || sport === "CHK") && FILT.season !== 2019) {
    const btt = seasonRound(games, cupName);
    if (btt) {
      const round = tail(btt.game).replace(/^Championship$/, "Final");
      const seed = btt.seed != null ? " (No. " + btt.seed + ")" : "";
      const bttHead = btt.won && round === "Final" ? cupShort + " CHAMPIONS"
        : cupShort + " " + (round === "Final" ? "FINAL" : round);
      void 0;
      // ...and reaching the FINAL and losing it is maize (his call 2026-09-29)
      parts.push(/CHAMPIONS/.test(bttHead)
        ? win(cornell ? "#c0053c" : "#0088ce", bttHead + seed, true)
        : round === "Final" ? win("#ffcb05", bttHead + seed)
        : esc(bttHead + seed));
    }
  }
  // EACH PART ON ITS OWN LINE ON A PHONE (his call 2026-09-29): the bars
  // between them go with the single line they were holding together.
  return parts.map(x => '<span class="spart">' + x + "</span>")
    .join('<span class="ssep"> | </span>');
}
function fmtTime(t) {
  // a kickoff not yet set reads TBD (2026-09-18, with the whole season loaded)
  if (!t || t === "TBD") return "TBD";
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
function teamLine(t, sport, season, seed, g0) {
  // A SEED reads in front of the name instead of in the rank column (his call
  // 2026-09-11): "2 WASHINGTON", not "NO. 2". The column then only ever holds a
  // poll ranking, so it is as narrow as "#25".
  const inline = seed != null
    ? '<span class="rkin">' + seed + "</span> " : "";
  return '<div class="tl' + (t.win || (g0 && t.id === MICHIGAN && michAhead(g0))
    ? " won" : "") + '">' +
    '<img class="crest" loading="lazy" src="' + (washedWinner(t, g0) ? crestOnColour(t) : crest(t)) +
      '" alt="">' +
    '<span class="rk">' +
    (t.rank && !seedOnly(g0) ? '<span class="rn">' + t.rank + "</span>" : "") + "</span>" +
    '<span class="nm">' + inline + esc(teamName(t, sport, season)) +
    // A CONFERENCE-TOURNAMENT game carries his seed in front of the name, so
    // the poll ranking moves to AFTER it, small and grey like a Michigan card's
    // final rating (his call 2026-09-16) -- the rank column goes, and both
    // names line up with every other card
    (g0 && rankAfter(g0) && t.rank ? '<span class="rkaft">#' + t.rank + "</span>" : "") +
    "</span>" +
    '<span class="sc">' + scoreText(t.score) + "</span></div>";
}

/* A TOURNAMENT HEADER WEARS ITS TOURNAMENT'S COLOUR (his calls 2026-09-14,
   Rivals too 2026-09-16): the Big Ten Tournament and Championship Game in Big
   Ten blue, the NCAA Tournament in its blue -- lightened to read on a card,
   as it is on a divider tile -- and the CFP and the New Year's Six bowls in
   CFP gold. The NIT and the other bowls stay plain. */
function ny6Bowl(g) {
  return ["Rose Bowl", "Sugar Bowl", "Orange Bowl", "Cotton Bowl",
          "Fiesta Bowl", "Peach Bowl"].some(b => sameName(b, g.stage));
}
function stageColor(g) {
  const st = g.stage || "";
  if (ny6Bowl(g) || st.indexOf("CFP") === 0) return "#c28c19";
  if (st.indexOf("Big Ten Tournament") === 0 ||
      st.indexOf("Big Ten Championship") === 0) return "#0088ce";
  if (st.indexOf("NCAA Tournament") === 0) return "#4d9ae0";
  if (st.indexOf("ECAC Tournament") === 0) return "#c0053c";      // his hex, 2026-09-17
  if (st.indexOf("Ivy Madness") === 0) return "#0f6a37";          // his hex, 2026-09-17
  return null;
}

// MICHIGAN'S UPCOMING GAME wears a winner's stripe on TV Windows and Key
// Games until it is played (his call 2026-09-21); after that the ordinary
// rules take over
function michAhead(g) {
  return upcoming(g) && (VIEW === "tv" || VIEW === "big") &&
    g.teams.some(t => t.id === MICHIGAN);
}
function rowHtml(g, browse) {
  const home = g.teams[0], away = g.teams[1];
  const win = michAhead(g) ? g.teams.find(t => t.id === MICHIGAN)
    : home.win ? home : away;
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
  if (g.event && !g.stage && PLACE_TOO.some(e => sameName(e, g.event)) &&
      (g.offsite || (g.neutral && g.city)))
    tags.push(chip("champ", g.offsite || g.city));
  showsOf(g).forEach(t => tags.push(chip("mine " + tagClass(t), t)));
  plainTags(g).forEach(t => tags.push(chip("mine " + tagClass(t), t)));
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
  // a December conference game carries the network's colour too, even though
  // basketball Marquee does not reach December (his call 2026-09-13): FOX
  // yellow, CBS blue, from the same NET_TINT table
  const decGame = g.sport === "CBB" && /^December /.test(g.header || "");
  const winCol = g.sport === "CFB" ? tint
    : ((g.mq || decGame) ? netTint : null);
  // ...but the HEADER keeps that colour only when a Big Ten team is playing
  // (his call 2026-09-11). The network and the time keep theirs regardless.
  const bigTen = g.teams.some(t => t.conf === BIG_TEN[g.sport]);
  const headCol = (VIEW === "rivals" && stageColor(g)) || (bigTen ? winCol : null);
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
    // the long ones keep a short form for trimStageHeads to reach for: a
    // conference or the NCAA gives up the word TOURNAMENT before it wraps
    const lab = stageLabel(g);
    const brief = lab.replace(/ Tournament /, " ");
    when = stageYear(g) +
      (brief !== lab
        ? '<span data-short="' + esc(brief) + '">' + esc(lab) + "</span>"
        : esc(lab)) +
      " (" + esc(g.dow) + ")";
  } else if (g.sport === "CFB" || g.sport === "NFL") {
    // Week 0 is a real week, so test for a MISSING week, not a falsy one
    const hasWeek = g.week != null;
    when = (hasWeek ? '<span class="wk">Week ' + g.week + "</span>" : "") +
      (label ? (hasWeek ? " | " : "") + esc(label) : "");
    // a bare "WEEK 1" off a Saturday names its day (his call 2026-09-11)
    // (an NFL week's own day is SUNDAY, so the Lions name only the others)
    if (hasWeek && !label && g.dow !== (g.sport === "NFL" ? "Sun" : "Sat"))
      when += " (" + esc(g.dow) + ")";
    // Browse pulls straight from ESPN, where a week number can be missing;
    // never leave the header empty.
    if (!when) when = esc(DAYS[g.dow] || g.dow);
  } else {
    when = esc(label || DAYS[g.dow] || g.dow);
  }
  // the Michigan view draws its own card from the same header and chips.
  // THERE A COLOUR IS ALL OR NOTHING (his call 2026-09-14): the network alone
  // being tinted -- which is what a non-Marquee game used to get -- read as an
  // accident rather than a signal, so whatever colour the card earns paints
  // the whole header. It does not wait on a Big Ten team either.
  if (teamView() && !browse) {
    const one = winCol || netCol;
    return michCard(g, { tags: tags, when: when, headCol: one,
                         netCol: one, timeCol: one });
  }
  // A coloured BORDER flags a Michigan win or a rival loss. A full maize box
  // was too loud, so the winner's line keeps its own wash either way.
  let flag = celebrated(g);
  let ring = flag ? celebrateColor(g) : null;
  // KEY GAMES READS keyRing IN EVERY SPORT (his call 2026-10-02): before this
  // only football did, so a basketball card took the winner's colour where the
  // Big Ten / CFP / NCAA colours now belong. It no longer waits on
  // `celebrated` either -- a postseason colour is its own reason to frame.
  if (VIEW === "big") {
    ring = keyRing(g);
    flag = !!ring;
  }
  /* HIS RESULTS CARRY THEIR OWN COLOURS (his call 2026-10-02): the Shade
     column fills the card and the Border column frames it -- in the winner's
     colour, or Big Ten blue where he says Big Ten. */
  const imx = VIEW === "big" ? (g.imx || null) : null;
  if (imx && imx.border) {
    const w = g.teams.find(t => t.win);
    const c = /big ten/i.test(imx.border) ? "#0088ce"
      : brighten(teamColor(w || g.teams[0]), 130);
    flag = true;
    ring = [c, c + "44"];
  }
  if (VIEW === "rivals") {
    const c = rivalsBorder(g);
    flag = !!c;
    ring = c ? [c, c + "44"] : null;
  }
  return '<div class="row' + (flag ? " celebrate" : "") +
    (dimmed(g) ? " dimmed" : "") + (struck(g) ? " struck" : "") +
    (flatWin(g) ? " flatwin" : "") + (g.ot ? " ot" : "") +
    ((VIEW === "rivals" && rivalsFill(g)) || keyFill(g) || marqueeFill(g) ||
      (imx && imx.shade) ? " rwash" : "") +
    // a Michigan loss is DASHED on these views (his call 2026-09-11); the
    // Michigan view keeps a plain frame
    ((VIEW !== "rivals" && michTeam(g) && !michTeam(g).win) ? " mloss" : "") +
    // ranking colour (his calls 2026-09-11), every view: a Michigan loss or a
    // win by Ohio State, Michigan State or Notre Dame greys the rankings;
    // otherwise an upset paints them Sports Daily's orange
    (dimmed(g) ? " rk-grey" : isUpset(g) ? " rk-upset" : "") +
    // a seeded game drops the rank column: the seed rides with the name
    ((seedOnly(g) || rankAfter(g)) ? " rk-no" : "") +
    '" data-id="' + g.id + '" style="--winwash:' + shade(teamColor(win)) +
    (ring ? ";--celeb:" + ring[0] + ";--celebring:" + ring[1] : "") + '">' +
    // The header row: slot label left, DATE right. The date sits here rather
    // than in the meta column because this is the only way it lines up with
    // the header. No weekday -- his call 2026-09-10.
    '<div class="sport"' + col(headCol) + ">" +
      "<span>" + when + mark + "</span>" +
      '<span class="hdate">' + fmtDate(g.date) + "</span></div>" +
    '<div class="teams">' + teamLine(away, g.sport, g.season, seedOf(g, away), g) +
      teamLine(home, g.sport, g.season, seedOf(g, home), g) + "</div>" +
    // network on the away team's line, time on the home team's
    // ABC READS RED on a football card (his call 2026-09-25); every other
    // network keeps the card's own colour
    '<div class="meta"><div class="mrow"' +
      col(g.sport === "CFB" && primaryNet(g.nets) === "ABC" ? "#e03a3a" : netCol) + ">" +
      esc(primaryNet(g.nets) || "—") + '</div><div class="mrow"' +
      col(timeCol) + ">" + fmtTime(g.time) + "</div></div>" +
    '<div class="tags">' + tags.join("") + "</div></div>";
}

/* MICHIGAN view (trial, his call 2026-09-11). One card per Michigan game, in
   the same frame as every other card: the header (his emoji and the NC / B1G
   game number in front), then ONE team line -- the opponent, with its rank at
   the time, its playoff finish [Semis] or final rank [#13] or his SP+/KenPom
   (73+), and the score and Michigan's rank in boxes painted as Michigan's
   uniform. Then one row of chips.
   His own columns come from michigan.csv via harvest: emoji, border, caps,
   uniform and note. */
// his own words for a border, from the sheet: B1G is the conference blue,
// CFP the playoff gold (2026-09-13)
const MICH_COLOURS = { blue: "#00274c", maize: "#ffcb05", white: "#ffffff",
  b1g: "#0088ce", cfp: "#c28c19",
  gold: "#c28c19", grey: "#8a8a92", gray: "#8a8a92", black: "#111114",
  red: "#c8102e", green: "#1d7a3a", navy: "#00274c",
  carnelian: "#b31b1b" };
function michColour(v) {
  const s = String(v || "").trim();
  if (/^#?[0-9a-f]{6}$/i.test(s)) return "#" + s.replace("#", "");
  return MICH_COLOURS[s.toLowerCase()] || null;
}
/* CAPITALS COME FROM HIS SHEET AND NOWHERE ELSE (his call 2026-09-14).

   The Case column says "UPPER" or it does not; a BLANK is Proper Case, with
   whatever display name the acronym rules give it (Ucla, Njit, Unlv, Utep).
   The "at " / "vs. " prefix is its own span and never takes the capitals.

   This replaced a set of CHAMPIONSHIP SCOPES held here -- CFB 2023 every game,
   CBB 2025 every game but the Big Ten Tournament, CFB 2021-22 Big Ten
   opponents, CBB 2013 the conference regular season, CBB 2016/17/24 the
   tournament games -- which encoded the same 109 cards his column now does.
   Two sources for one fact meant his sheet could ADD a capital but never
   remove one, so the scopes went (see NOTES.md). */

/* THE LIONS' CARD (his calls 2026-09-18), laid out like a TV Windows card:
   the week and the TV on the left of the header, the DATE at the far right,
   and a third row only when there is something to say -- where it was played
   abroad, a primetime slot or a holiday (no network in those chips):
     WEEK 16 | FOX 1:00 PM                        12/22/2024
     WEEK 13 | CBS 12:30 PM                       11/28/2024   [Thanksgiving]
     WEEK 8 | FOX 9:30 AM                          11/1/2015   [London]
     2023 NFC WILD CARD | SUN NBC 8:15 PM          1/14/2024 */
function nflParts(g) {
  const DAY = { Mon: "Monday", Tue: "Tuesday", Wed: "Wednesday", Thu: "Thursday",
                Fri: "Friday", Sat: "Saturday", Sun: "Sunday" };
  const net = primaryNet(g.nets);
  const t = fmtTime(g.time).replace(/(am|pm)$/, " $1").toUpperCase();
  const tv = (net ? net + " " : "") + t;
  const netCls = net ? " n-" + net.toLowerCase().replace(/[^a-z]/g, "") : "";
  const date = fmtDate(g.date);
  if (g.stage) {
    // the Lions' own SEED rides in the third row (his call 2026-09-18)
    const rnd = g.stage.replace(" Round", "");
    const me = g.teams.find(x => x.id === LIONS) || {};
    return { head: esc(g.season + " " + rnd) + " | " + date + " | " + esc(g.dow + " " + tv),
             chips: (me.seed ? chip("grey", "No. " + me.seed + " Seed") : "") +
               (g.neutral && g.city ? chip("champ", g.city) : "") };
  }
  const md = g.date.slice(5), d = +g.date.slice(8, 10);
  const hr = +String(g.time).slice(0, 2), timed = g.time !== "TBD";
  let sit = null;
  if (g.dow === "Thu" && md.slice(0, 2) === "11" && d >= 22 && d <= 28) sit = "Thanksgiving";
  else if (md === "12-25") sit = "Christmas";
  else if (g.dow === "Sun" && timed && hr >= 19) sit = "Sunday Night";
  else if (g.dow === "Mon" || g.dow === "Thu") sit = DAY[g.dow] + " Night";
  else if (g.dow !== "Sun") sit = DAY[g.dow];
  const chips = (g.neutral && g.city ? chip("champ", g.city) : "") +
    (sit ? '<span class="tag t-slot' + netCls + '">' + esc(sit) + "</span>" : "");
  // the DATE sits between the week and the TV (his call 2026-09-18)
  return { head: (g.week != null ? "Week " + g.week + " | " : "") + date + " | " + esc(tv),
           chips: chips };
}

function michCard(g, p) {
  const fid = g.focus || focusId();
  const m = g.teams.find(t => t.id === fid), opp = g.teams.find(t => t.id !== fid) || g.teams[0];
  /* CORNELL HOCKEY TAKES THE TIGERS' TREATMENT (his call 2026-09-27). He
     colours no score box there, so the card says it another way: a WIN runs
     the opponent's colour across the whole line, through a bare score, and a
     tie or a defeat carries no background at all. Its own number moves beside
     the footer on every card -- see cuNum below. */
  const cuPlain = g.sport === "CHK" && fid === CORNELL;
  // HOCKEY SERIES CARDS (his call 2026-09-16): consecutive regular-season
  // games against one opponent share a card (michListHtml groups them into
  // g._series, oldest first; a lone game is a series of one). The result is
  // by POINTS -- 3 a regulation win, 2 an overtime win, 1 an overtime loss, a
  // tie shared -- so a win and an overtime loss is a series WON:
  //   more than half   the stripe and bold
  //   exactly half     the stripe, not bold, against a RANKED opponent;
  //                    plain grey text against an unranked one
  //   less than half   struck through, like any loss
  const series = g._series || null;
  /* POINTS DECIDE THE CARD (his rule 2026-09-23), one game or two, the way
     the Big Ten counts a weekend: a win in regulation is 3, a win in overtime
     or the shootout 2, a loss there 1, a loss in regulation 0, and a tie
     nobody won 1.5 each. More points reads BOLD, fewer reads struck through,
     and level points are settled by who won the extra sessions -- a shootout
     win breaks the tie. Only a card level on both counts stays plain. */
  let sres = null;
  {
    const games = series || [g];
    let mine = 0, theirs = 0, myX = 0, theirX = 0;
    games.forEach(x => {
      if (upcoming(x)) return;
      const me = x.teams.find(t => t.id === fid);
      const extra = x.ot || x.so;
      if (x.tie) {
        if (x.sho_win === true) { mine += 2; theirs += 1; myX++; }
        else if (x.sho_win === false) { mine += 1; theirs += 2; theirX++; }
        else { mine += 1.5; theirs += 1.5; }
      } else if (me && me.win) {
        mine += extra ? 2 : 3; theirs += extra ? 1 : 0;
        if (extra) myX++;
      } else {
        mine += extra ? 1 : 0; theirs += extra ? 2 : 3;
        if (extra) theirX++;
      }
    });
    if (games.some(x => !upcoming(x)))
      sres = mine > theirs ? "win" : mine < theirs ? "loss"
        : myX > theirX ? "win" : myX < theirX ? "loss" : "split";
  }
  // ...but a TOURNAMENT series is won by games: the bubble reads the series
  // score (2-1) and the bottom row each game's score (his call 2026-09-16)
  const tSeries = !!(series && g.stage);
  let sWins = 0, sLosses = 0, sTies = 0;
  if (tSeries) {
    series.forEach(x => {
      if (upcoming(x)) return;
      const me = x.teams.find(t => t.id === fid);
      if (x.tie) sTies++; else if (me.win) sWins++; else sLosses++;
    });
    sres = sWins > sLosses ? "win" : sWins === sLosses ? "split" : "loss";
  }
  // hockey can end level (2026-09-16): a TIE is neither dimmed nor bold
  const oppRanked = series
    ? series.some(x => (x.teams.find(t => t.id !== fid) || {}).rank) : !!opp.rank;
  const tied = sres === "split" && !oppRanked;
  const flatSplit = !tSeries && sres === "split" && oppRanked;
  const mx = g.mx || {};
  const lost = sres === "loss";
  // Proper Case is the DEFAULT here -- the Big Ten rule of the other views
  // does not reach this one -- and his Case column is the only thing that
  // lifts a name into capitals (2026-09-14).
  let nm = teamName(opp, null, g.season);
  // ...but on the MICHIGAN tab these three read as the acronyms they are again
  // (his call 2026-09-18)
  if (VIEW === "michigan") nm = { Unlv: "UNLV", Utep: "UTEP", Njit: "NJIT" }[nm] || nm;
  const caps = mx.caps === "Y";
  if (caps) nm = nm.toUpperCase();
  const whereOf = x => x.neutral ? "vs. " :
    (x.teams.find(t => t.id !== fid) || {}).home ? "at " : "";
  // A HOME-AND-AWAY SERIES -- one game each way, as Western Michigan's usually
  // is -- reads "vs." and says which came first in the footer, in place of
  // the Home & Home tag (his call 2026-09-16)
  const homeAway = !!(series && series.length === 2 && !series.some(x => x.neutral) &&
    whereOf(series[0]) !== whereOf(series[1]));
  const where = homeAway ? "vs. " : whereOf(g);
  // the rating reads "73+"; a team no system rates reads "DII" as it is
  // ...and a BOWL shows no final ranking for the opponent (his call 2026-09-18)
  const bowlFin = g.sport === "CFB" && !!g.stage && !playoffGame(g) &&
    g.stage.indexOf("Big Ten Championship") !== 0;
  const fin = mx.finish ? mx.finish : mx.final ? (bowlFin ? "" : "#" + mx.final)
    : mx.rating ? (mx.rating === "DII" ? "DII" : mx.rating + "+") : "";
  const col = c => (c ? ' style="color:' + c + '"' : "");
  // HEADER (his calls 2026-09-11). The TV details follow a bar -- "[nc1] WEEK 1
  // | PEACOCK 12:00PM" -- unless a window label already fills the header. A
  // STAGE card drops its own bar and the word "Tournament", takes the TV
  // details after the bar instead, and moves its day beside the date:
  // "2026 NCAA ROUND 1 | CBS 7:30PM" ... "THU 3/19/26".
  // WHERE A CARD PUTS ITS PIECES (his call 2026-09-13). Two shapes lift the
  // ROUND and the PLACE into the header and drop the date and the TV details
  // into the third row:
  //   a tournament  "2026 NCAA ELITE EIGHT | CHICAGO"    "SUN 3/29/26 | CBS 2:15PM"
  //   an MTE        "[nc7] PLAYERS ERA FESTIVAL | FINAL" "Las Vegas | TNT 9:30 | 11/26/25"
  // The ordinary bowls stay out of this set: a Citrus Bowl header already IS
  // its location, and lifting it would print the name twice.
  const TOURNEY = ["Big Ten Tournament", "NCAA Tournament", "NIT ", "CFP ",
                   "Big Ten Championship", "ECAC Tournament", "Ivy Madness"];
  const bigStage = !!g.stage && TOURNEY.some(s => g.stage.indexOf(s) === 0);
  const mteCard = !!g.preseason && !g.stage;
  // a series card names the place and the event of ANY of its games -- the
  // Duel in the D shares a card with the Munn game beside it
  const placeOf = x => x.bowl || x.offsite || (x.neutral && x.city ? x.city : "");
  const place = series ? (series.map(placeOf).find(Boolean) || "") : placeOf(g);
  const eventName = series ? (series.map(x => x.event).find(Boolean) || null) : g.event;
  // the network and time as plain text, for the third row of those two shapes
  // CORNELL NAMES NO BROADCAST BUT THE NCAA TOURNAMENT'S (his call
  // 2026-09-27): ESPN+ carries nearly everything else it plays, which tells
  // him nothing he wants on a card.
  const netTxt = cuPlain && (g.stage || "").indexOf("NCAA Tournament") !== 0
    ? "" : primaryNet(g.nets);
  const tvTxt = netTxt ? netTxt + " " + fmtTime(g.time) : fmtTime(g.time);
  // ESPN lists no broadcast at all for 20 basketball games -- early-season
  // ones against small schools. They now show the TIME alone rather than an
  // em dash standing in for a network (his call 2026-09-14).
  // a card with ONE game runs the day into its time -- "FRIDAY 7:05PM" --
  // with no pipe between them (his call 2026-09-23)
  const tvBits = (g.sport === "CHK" && !g._series ? ' ' : ' | ') +
    (netTxt ? '<span' + col(p.netCol) + ">" + esc(netTxt) + "</span> " : "") +
    '<span' + col(p.timeCol) + ">" + fmtTime(g.time) + "</span>";
  // SEPTEMBER 21 is his date: a Michigan WIN that day spells itself out --
  // "Sep 21, 2024" -- in the header and in the third row alike. Every other
  // date stays in slashes (his call 2026-09-13).
  const sept21Win = !lost && !upcoming(g) && g.date.slice(5) === "09-21";
  const shownDate = sept21Win
    ? MONTHS[+g.date.slice(5, 7) - 1].slice(0, 3) + " " +
      (+g.date.slice(8, 10)) + ", " + g.date.slice(0, 4)
    : fmtDate(g.date);
  // "DECEMBER SATURDAY" reads "SATURDAY" on this view (his call 2026-09-16);
  // the date beside it already says December
  let when = p.when.replace(/^December /, ""), right = shownDate;
  // the year leads every tournament header (his call 2026-09-14) -- ESPN does
  // not count the Big Ten Tournament as postseason, so `post` alone missed it
  // The tournament writes itself out in full on this view (his call
  // 2026-09-14): "NCAA TOURNAMENT", "COLLEGE FOOTBALL PLAYOFF". The Big Ten
  // Tournament stays short -- "BIG TEN QUARTERS" -- because the conference
  // name already carries it. Rounds 1 and 2 read FIRST and SECOND here too.
  const stageHead = () => {
    const yr = g.post || bigStage
      ? (g.sport === "CFB" || g.sport === "NFL" ? g.season : g.season + 1) + " " : "";
    // the shared label, plus the one abbreviation this view makes on its own:
    // the Big Ten's early rounds drop the word Tournament, won or not (his
    // call 2026-09-14) -- they are the longest labels and the least interesting
    const full = stageLabel(g)
      .replace("Big Ten Tournament First Round", "Big Ten First Round")
      .replace("Big Ten Tournament Second Round", "Big Ten Second Round");
    // the longest rounds against the longest cities run past his phone, so
    // each of these keeps a short form for trimMichChips to reach for. A Big
    // Ten SEMIFINAL keeps the word and gives up the spelling instead.
    let brief = full
      .replace("NCAA Tournament ", "NCAA ")
      .replace("Big Ten Championship Game", "Big Ten Championship");
    brief = full === "Big Ten Tournament Semifinals"
      ? "Big Ten Tournament Semis"
      : brief.replace("Big Ten Tournament ", "Big Ten ");
    return yr + (brief !== full
      ? '<span class="hstage" data-short="' + esc(brief) + '">' + esc(full) + "</span>"
      : esc(full));
  };
  if (bigStage) {
    // the round, then WHERE it was played; the date and the TV details have
    // gone down to the third row
    when = stageHead() + (place ? " | " + esc(place) : "") +
      // GAME 2 (1-1) on a split tournament series (his call 2026-09-22)
      (g._gm ? " | Game " + g._gm.n + (g._gm.rec ? " (" + esc(g._gm.rec) + ")" : "") : "");
  } else if (mteCard) {
    // the event, then the round within it -- his Round column, blank until he
    // fills it in, and then the header is simply the event
    // the bracket works the round out on its own (see harvest); the Round
    // column that used to override it is retired (2026-09-14)
    const rnd = g.mte_round || "";
    // the one event long enough to run past the header on its longer rounds;
    // it keeps the full name wherever it fits (2026-09-14)
    const EVENT_SHORT = {
      "Fort Myers Tip-Off | Beach Division": "Fort Myers Tip-Off | Beach Div" };
    const ev = g.event || place;
    const evShort = EVENT_SHORT[ev];
    // THE LOCATION RIDES IN THE HEADER (his call 2026-09-14), which leaves the
    // third row holding nothing but the network, the time and the date -- all
    // spelled out. Only these events need one: the rest say where they are in
    // their own names (Maui, Battle 4 Atlantis, Puerto Rico, Fort Myers).
    const MTE_PLACE = ["Ice Breaker", "NIT Tip-Off", "Legends Classic", "2K Classic",
                       "Hall of Fame Tip-Off", "Roman Main Event",
                       "Players Era"];
    const wantPlace = MTE_PLACE.some(e => ev.indexOf(e) > -1);
    // the location reads next to its EVENT and the round comes last (his call
    // 2026-09-14) -- the opposite of a tournament card, where the round is
    // part of the tournament's own name and the location closes the line
    when = (evShort
      ? '<span data-short="' + esc(evShort) + '" data-trim="3">' + esc(ev) + "</span>"
      : esc(ev)) + (wantPlace && place ? " | " + esc(place) : "") +
      (rnd ? " | " + esc(rnd) : "");
  } else if (g.stage) {
    when = stageHead() + tvBits;
    right = '<span class="hdow">' + esc(g.dow) + "</span> " + right;
  } else if (!g.header || /^December /.test(g.header)) {
    // a window label already names its network ("FOX PRIMETIME"), so the TV
    // details are left off -- but "DECEMBER SATURDAY" names nothing, and
    // dropping them there lost the network and the time (his catch
    // 2026-09-13)
    when += tvBits;
  } else if (g.sport === "CBB") {
    // ...and where the label DOES name the network, BASKETBALL still shows the
    // time (his call 2026-09-14), appended to the back of the label -- TV
    // Windows leaves it out because the window implies it. Football keeps it
    // off: that header already carries a week, a window and a date.
    when += ' <span' + col(p.timeCol) + ">" + fmtTime(g.time) + "</span>";
  }
  // no emoji in the header any more (his call 2026-09-13)
  const head = (mx.num ? '<span class="mnum">[' + esc(mx.num) + "]</span> " : "") +
    (series && !tSeries ? series.map(x => esc(x.dow) + " " + fmtTime(x.time)).join(" | ") : when);
  // The DATE goes at the end of the header -- unless the third row would be
  // empty, in which case it drops down there instead and the header ends
  // without it (his call 2026-09-13). Decided below, once the footer is known.
  const headDate = ' | <span class="hdate">' + right + "</span>";
  const dateText = (g.stage ? g.dow.toUpperCase() + " " : "") + shownDate;
  // UNIFORM (his calls 2026-09-11): the score box is the jersey, the rank box
  // the pants, and the accessories colour is the text on both. He wants maize
  // ON maize and blue ON blue, which cannot be read as the same value, so the
  // text KEEPS ITS HUE and moves in lightness until it reads (3:1) -- maize on
  // maize becomes a deep gold, blue on blue a lighter blue. Only a colour that
  // still cannot get there falls back to navy or maize. Basketball's single
  // uniform colours both boxes.
  // His box colours (michigan.csv: score_bg / score_font, rank_bg / rank_font)
  // win when he gives them -- they do not always follow the uniform. Otherwise
  // the uniform paints them: jersey behind the score, pants behind the rank,
  // accessories as the text on both.
  // HOCKEY TRACKS NO JERSEY (his call 2026-09-16): its boxes are always
  // Michigan blue with maize, and his Sheet needs no colour columns for it
  // CORNELL'S does, from his Sheet; where those columns are blank it reads
  // carnelian with white on the road, white with carnelian at home, and the
  // grey placeholder at a neutral site (his call 2026-09-16)
  // A GAME HIS SHEET HAS NOT COLOURED READS GREY (his call 2026-09-23),
  // played or not: no home-and-road default, no school colours standing in
  const HOCKEY_BOX = {};
  // WHERE HIS SHEET SPEAKS AT ALL, SILENCE MEANS GREY (his call 2026-09-28).
  // A team he colours game by game -- the Tigers, the Lions, the Red Wings --
  // takes the placeholder wherever he has not, exactly as Michigan does;
  // Honolulu blue and Tigers navy used to stand in, which read as colours he
  // had chosen rather than ones he had not. A team with no colours of his
  // anywhere keeps the one set for it, since nothing else would paint its box.
  const u = (mx.uni || []).map(michColour),
    bx = mx.box || (g.sport === "CHK" || sheetBoxed(fid) ? HOCKEY_BOX
      : PRO_BOX[fid] ? { score_bg: PRO_BOX[fid].bg, score_font: PRO_BOX[fid].fg,
                         rank_bg: PRO_BOX[fid].bg, rank_font: PRO_BOX[fid].fg } : {});
  // the placeholder until his sheet is filled: a quiet grey, not the maize the
  // CSS used to default the rank box to
  const UNSET = "#4a4a52";
  // (the silver he had in these cells read nearly white as a score bubble, so
  // it was darkened here for a day; he has since written "Gray" into the
  // Tigers' and the Lions' cells instead, which is the tidier place for it,
  // and the substitution is gone again -- 2026-09-28)
  const top = michColour(bx.score_bg) || u[0] || UNSET;
  const pants = michColour(bx.rank_bg) || (u.length >= 3 ? u[1] : u[0]) || UNSET;
  const uniAcc = u.length >= 3 ? u[2] : null;
  const scoreInk = michColour(bx.score_font) || uniAcc;
  const rankInk = michColour(bx.rank_font) || uniAcc;
  const lum = hex => {
    const v = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map(x => x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4));
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
  };
  const ratio = (a, b) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05);
  const WHITE = "#ffffff";
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
    if (fg === WHITE && bg === WHITE) return "#b4b4ae";
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
  // a card he has given no colours reads WHITE on the grey placeholder (his
  // call 2026-09-14) rather than picking maize or navy by contrast
  // a PRO TEAM'S OWN COLOURS are used exactly as he gave them, with no
  // contrast nudge (the Pistons' orange read grey-brown, his catch 2026-09-18)
  const exact = !mx.box && !!PRO_BOX[fid];
  const ink = (bg, fg) => bg === UNSET ? WHITE
    : fg && exact ? fg
    // THE LIONS' SHEET COLOURS take Michigan's rule below (his call
    // 2026-09-18): white on white reads light grey, and a font too close to its
    // box moves only as far as it must -- blue on grey stays near-blue
    : fg ? readable(fg, bg)
    : ratio("#00274c", bg) >= ratio("#ffcb05", bg) ? "#00274c" : "#ffcb05";
  const paint = (bg, fg) => (bg ? ' style="background:' + bg + ";color:" +
    ink(bg, fg) + '"' : "");
  // the two boxes share one height and one type size (his call)
  // BOTH BUBBLES ALWAYS SHOW, an unplayed game included (his call
  // 2026-09-14) -- it is painted like any other, just with no score in it,
  // which on a card with no colours is the grey placeholder
  // HOCKEY: a score is UNDERLINED when the game went to overtime, a shootout
  // or ended tied, and a shootout says so -- "2-2 (SO)" (his call 2026-09-16)
  // EACH GAME OF A SERIES WEARS ITS OWN ROW'S SCORE COLOURS (his call
  // 2026-09-22): the Friday box from the Friday row, the Saturday box from
  // the Saturday row, and the card's own colours where a row leaves them blank
  const bubble = x => {
    const xb = (x.mx && x.mx.box) || {};
    const xTop = michColour(xb.score_bg) || top;
    const xInk = michColour(xb.score_font) || (xb.score_bg ? null : scoreInk);
    const me = x.teams.find(t => t.id === fid), op = x.teams.find(t => t.id !== fid);
    // ...and on the Red Wings' playoff cards (his call 2026-09-18), and on
    // football and basketball as well (his call 2026-09-25): an overtime game
    // is underlined whether Michigan won it or lost it, so 2016 at Ohio State
    // reads underlined and italic both.
    const UNDERLINE_OT = ["CHK", "NHL", "CFB", "CBB"];
    const mark = UNDERLINE_OT.indexOf(g.sport) > -1 && !upcoming(x) &&
      (x.ot || x.so || x.tie);
    // A SHOOTOUT reads in brackets -- "[2-2]" -- still underlined, and the
    // team that LOST the shootout has it italic like any other defeat (his
    // call 2026-09-22). Most college shootouts go down as ties, so the loser
    // comes from USCHO's note (sho_win); an unknown one stays upright.
    const shoot = g.sport === "CHK" && !upcoming(x) && x.so;
    // ...and a Big Ten tie decided in 3-on-3 overtime reads as a defeat too,
    // without the brackets a shootout earns (his call 2026-09-22)
    const lossScore = !upcoming(x) && ((!x.tie && !me.win) || x.sho_win === false);
    return '<span class="sc mbox' + (mark ? " u" : "") + (lossScore ? " l" : "") + '"' +
      paint(xTop, xInk) + ">" +
      (upcoming(x) ? "" : shoot ? "[" + me.score + "-" + op.score + "]"
        : me.score + "-" + op.score) +
      "</span>";
  };
  let score = bubble(g);
  // Michigan's rank sits on the THIRD ROW, under the score and the same width
  // as it, its number centred (his calls 2026-09-11). It reads "No. 1" in the
  // CFP or the NCAA Tournament, a bare seed in a conference tournament, "#3" in
  // the regular season, and a dash when Michigan was unranked.
  const umSeed = seedOf(g, m);
  // a pro team has no poll: its box holds the RECORD after the game
  const umText = g.sport === "NFL" ? (mx.rec || "\u2013")
    : playoffGame(g) && m.rank ? "No. " + m.rank
    : umSeed != null ? "No. " + umSeed
    : m.rank ? "#" + m.rank : "\u2013";
  // a LOSS italicises the rank box as well as the score, in football and
  // basketball (his call 2026-09-18)
  const lossRank = g.sport !== "CHK" && !upcoming(g) && !g.tie && !m.win;
  // a REGULAR-SEASON WIN AS #1 bolds the number (his call 2026-09-18)
  const topWin = g.sport !== "CHK" && !g.stage && !upcoming(g) && m.win && m.rank === 1;
  let umRank = '<span class="mrank' + (lossRank ? " l" : "") + (topWin ? " b" : "") + '"' +
    paint(pants, rankInk) + ">" + umText + "</span>";
  if (tSeries) {
    score = '<span class="sc mbox"' + paint(top, scoreInk) + ">" +
      (sWins + sLosses + sTies ? "[" + sWins + "-" + sLosses + (sTies ? "-" + sTies : "") + "]" : "") +
      "</span>";
  } else if (series) {
    const second = series[1];
    umRank = second ? bubble(second) : "";
  }
  // on a series card the team's OWN rank reads under the opponent's, in its
  // colour -- maize, or Cornell's carnelian -- and nothing when it was unranked
  // A MICHIGAN HOCKEY REGULAR-SEASON GAME OUTSIDE A SERIES -- an MTE like the
  // 2021 Ice Breaker -- reads like the series around it (his call 2026-09-22):
  // no rank box, Michigan's rank in maize beside the footer instead
  // ...and Cornell's the same way (his call 2026-09-22)
  const hkySingle = g.sport === "CHK" && (fid === MICHIGAN || fid === CORNELL) &&
    !series && !g.post && !g.stage;
  if (hkySingle) umRank = "";
  // CORNELL CARRIES NO RANK BOX AT ALL (his call 2026-09-27) -- its number
  // sits beside the footer on every card, the poll ranking in the regular
  // season and, in the postseason, its SEED as a bare figure: no "#" and no
  // "No.", which is what that box used to print.
  if (cuPlain) umRank = "";
  const cuNum = !cuPlain ? "" : seedOf(g, m) != null ? String(seedOf(g, m))
    : m.rank ? "#" + m.rank : "";
  const ownRank = cuPlain
    ? (cuNum ? '<span class="mrk2" style="color:#b31b1b">' + esc(cuNum) + "</span>" : "")
    : ((series && !tSeries) || hkySingle) && m.rank
    ? '<span class="mrk2" style="color:' + (fid === CORNELL ? "#b31b1b" : "#ffcb05") +
      '">#' + m.rank + "</span>" : "";
  // TEAM LINE: the colour stripe runs from the crest through the rating and
  // stops before the two boxes (his call 2026-09-11)
  // MICHIGAN AGAINST CORNELL, on either team's card, bolds nothing (his call
  // 2026-09-16)
  const bothMine = (g.sport === "CHK" && g.teams.some(t => t.id === MICHIGAN) &&
    g.teams.some(t => t.id === CORNELL)) ||
    // ...and so does the CAVALIERS AGAINST THE PISTONS since 2016-17 (his call
    // 2026-09-18)
    (g.sport === "NBA" && g.season >= 2016 && g.teams.some(t => t.id === "nba-5") &&
     g.teams.some(t => t.id === "nba-8"));
  // ...and on a Cornell card only a WIN wears the band -- in regulation, in
  // overtime or in the shootout (his call 2026-09-27). A tie carries none,
  // even against a ranked team, where every other view still washes a split.
  const oppLine = '<div class="tl' +
    ((cuPlain ? sres !== "win" : (lost || tied)) ? "" : " won") + '"><span class="mstripe">' +
    '<img class="crest" loading="lazy" src="' + crest(opp) + '" alt="">' +
    '<span class="rk">' +
    // AN NCAA TOURNAMENT GAME SHOWS THE SEED ALONE (his call 2026-09-27): the
    // seed already sits in front of the opponent's name, so the poll ranking
    // beside it says the same thing twice. Hockey is the case that reached
    // here -- basketball's NCAA games drop the column through seedGame.
    (opp.rank && !seedGame(g) && (g.stage || "").indexOf("NCAA Tournament") !== 0
      ? '<span class="rn">' + opp.rank + "</span>" : "") +
    // an NFL playoff opponent's SEED, bare, where a rank would sit
    (["NFL", "NHL", "NBA", "MLB"].indexOf(g.sport) > -1 && opp.seed
      ? '<span class="rn nseed">' + opp.seed + "</span>" : "") +
    "</span>" +
    '<span class="nm mnm"><span class="mn">' + esc(where) +
      (seedOf(g, opp) != null && ["NFL", "NHL", "NBA", "MLB"].indexOf(g.sport) < 0 ? '<span class="rkin">' + seedOf(g, opp) + "</span> " : "") +
      esc(nm) +
      (mx.reigning ? '<span class="mcaret">^</span>' : "") + "</span>" +
      // the finish or rating reads after the name again (his call 2026-09-11),
      // the name giving way first when the two do not fit
      (fin && !playoffGame(g) ? '<span class="mfin"' +
        ({ "Sweet Sixteen": ' data-short="S16"', "Elite Eight": ' data-short="E8"' }[fin] || "") +
        ">" + esc(fin) + "</span>" : "") +
      "</span></span>" +
    score + "</div>";
  // THE THIRD ROW: plain grey text in the header style rather than chips (his
  // call 2026-09-11) -- location, event, the home & home family, Big Noon,
  // GameDay, anything else, his Big Ten note -- with Michigan's rank box held
  // to the right, under the score. The two long show tags carry a short form
  // for trimMichChips.
  const mine = myTags(g.id);
  const SERIES_FAMILY = ["Home & Home", "Neutral & Neutral", "Home & Neutral",
                         "Annual", "Buy Game"];
  // shortened only when the row would otherwise wrap (his call 2026-09-13),
  // the same way Big Noon Kickoff and College GameDay already do it
  const SERIES_SHORT = { "Home & Home": "H&H", "Neutral & Neutral": "N&N",
                         "Home & Neutral": "H&N" };
  // The footer is collected as PARTS first, so his Footer column can colour
  // them (2026-09-13). A blank contributes nothing -- no span, no separator.
  const parts = [];
  // THE ORDER PIECES GIVE WAY IN (his call 2026-09-14), lowest first. He reads
  // the date and the network as facts and the rest as labels, so a show name
  // shortens long before a location does.
  //   1 the two shows      College GameDay -> GameDay
  //   2 the series tags    Home & Home -> H&H
  //   3 the location       Madison Square Garden -> MSG
  //   4 the TV time        ESPN2 9:30pm -> ESPN2
  // The DATE carries no short form at all, so it can never be given up.
  const bit = (s, short, his, pri) => {
    if (s === null || s === undefined || !String(s).trim()) return "";
    parts.push({ t: String(s), short: short || "", his: !!his, pri: pri || 5 });
    return true;                      // the array below only counts entries
  };
  // the two venue names long enough to push the row onto a second line (his
  // call 2026-09-13); the short form appears only when it has to
  const PLACE_SHORT = { "Madison Square Garden": "MSG",
                        "Little Caesars Arena": "LCA" };
  // HOCKEY HAS NO ROOM FOR THE ASTERISK -- the left gutter holds the rank --
  // so a game he attended says so in the footer instead (his call 2026-09-23)
  if (bigStage && tSeries) {
    series.forEach(x => {
      const me = x.teams.find(t => t.id === fid), op = x.teams.find(t => t.id !== fid);
      bit(upcoming(x) ? x.dow.toUpperCase() + " " + fmtDate(x.date)
        : me.score + "-" + op.score + (x.so ? " (SO)" : x.ot ? " (OT)" : ""));
      if (!upcoming(x) && !x.tie && !me.win) parts[parts.length - 1].it = true;
    });
  } else if (bigStage) {
    // the date leads and the TV details follow it -- the reverse of an
    // ordinary card, where both sit up in the header (his call 2026-09-13)
    bit(dateText);
    bit(tvTxt, netTxt, false, 4);
  } else if (mteCard) {
    // the location has gone up into the header (2026-09-14), so this row holds
    // the network, the time and the date, and has room to spell them out
    // ...except a HOCKEY MTE whose header carries no place: Cornell's Florida
    // College Classic and the rest name it here, first (his call 2026-09-16)
    if (g.sport === "CHK" && place &&
        !["Ice Breaker"].some(e =>
          (g.event || "").toLowerCase().indexOf(e.toLowerCase()) > -1)) bit(place);
    // ...and Cornell's shows no time (his call 2026-09-17), only a network
    if (fid === CORNELL && g.sport === "CHK") bit(netTxt);
    else bit(tvTxt, netTxt, false, 4);
    bit(dateText);
  }
  // the EVENT first and its city after for these (his call 2026-09-18):
  // "Jumpman Invitational | Charlotte"
  const eventFirst = ["Jumpman Invitational"].indexOf(eventName) > -1;
  if (eventFirst && !g.stage && !mteCard) bit(eventName);
  if (!bigStage && !mteCard && place && !ny6Bowl(g)) {
    // a NEW YEAR'S SIX bowl names no city (his call 2026-09-16): the header
    // already says Orange Bowl, and Miami Gardens adds nothing to it
    bit(place, PLACE_SHORT[place], false, 3);
  }
  if (eventName && !eventFirst && !g.stage && !mteCard) bit(eventName);
  // harvest's own footer words -- "Ivy League" on Cornell's Ivy games
  (series ? Array.from(new Set([].concat.apply([], series.map(x => x.labels || []))))
    : (g.labels || [])).forEach(t => bit(t));
  // THE SERIES IS DERIVED at harvest (two meetings in consecutive seasons the
  // schools arranged between them) -- but a tag he wrote by hand still wins,
  // which is what keeps Texas 2024 marked when its return leg sits in 2027,
  // outside the archive (2026-09-14)
  const handSeries = mine.filter(t => SERIES_FAMILY.indexOf(t) > -1);
  if (homeAway) {
    bit(whereOf(series[0]) === "at " ? "Away & Home" : "Home & Away");
  } else {
    (handSeries.length ? handSeries : (g.series ? [g.series] : []))
      .forEach(t => bit(t, SERIES_SHORT[t], false, 2));
  }
  const shows = showsOf(g);
  if (shows.indexOf("Big Noon Kickoff") > -1) bit("Big Noon Kickoff", "Big Noon", false, 1);
  if (shows.indexOf("College GameDay") > -1) bit("College GameDay", "GameDay", false, 1);
  plainTags(g).filter(t => SERIES_FAMILY.indexOf(t) < 0).forEach(t => bit(t));
  if (mx.note) bit(mx.note, "", true);

  // HIS FOOTER COLUMN (2026-09-13). "maize" paints the whole row maize.
  // "stripe" alternates blue and maize, starting blue: between the PIPES when
  // there is more than one piece, and word by word when there is only one.
  // Michigan navy would vanish on this card, so the blue is the lightened one
  // the box colours already use.
  // a deep Michigan blue, not the lightened one the boxes use -- it has to
  // read as navy against maize (his call 2026-09-13)
  // His Footer column is used two ways and both are honoured (2026-09-13):
  //   FOOTBALL   a bare colour word -- "Maize", "Stripe" -- painting whatever
  //              text the row already has (his note, tags, the location).
  //   BASKETBALL the whole phrase -- "Maize Out", "Pink Out", "Blue Out" --
  //              with Notes empty, so the phrase is ALSO the text.
  const FBLUE = "#003d7a", FMAIZE = "#ffcb05", FPINK = "#fd1272";
  const SOLID = { maize: FMAIZE, blue: FBLUE, pink: FPINK };
  const rawFooter = String(mx.footer || "").trim();
  const mode = rawFooter.split(/\s+/)[0].toLowerCase();
  if (rawFooter.indexOf(" ") > -1 &&
      !parts.some(q => q.t.toLowerCase() === rawFooter.toLowerCase())) {
    parts.push({ t: rawFooter, short: "", his: true });
  }
  // THE DATE DROPS TO THE THIRD ROW when nothing there is the card's own
  // (his call 2026-09-13): his Notes read fine after a date -- "9/23/23 |
  // B1G East" -- but a location, a show or a series tag is worth the row on
  // its own, and then the date stays up in the header. An empty row counts as
  // nothing, so the date fills it.
  // ...and on a tournament or an MTE card it is ALWAYS down there, placed
  // above in the order he asked for, so the header must not print it again
  // ...REVERSED 2026-09-16: his Notes are DETAILS like any other, so they take
  // the third row on their own and the date stays up in the header. The date
  // only drops when the row would otherwise be empty.
  // A SERIES CARD'S MONTH goes up into the header, after the days and times,
  // whenever the bottom row has details of its own -- Home & Home, Duel in the
  // D, Red Hot Hockey -- and fills the bottom row only when it would otherwise
  // be empty (his call 2026-09-16)
  let monthHead = "";
  if (series && !tSeries) {
    const month = MONTHS[+g.date.slice(5, 7) - 1] + " " + g.date.slice(0, 4);
    // a GLI, Duel in the D, Red Hot Hockey or Frozen Apple card carries its
    // DATE instead (his call 2026-09-17)
    if (series.some(x => x.dated)) monthHead = " | " + esc(fmtDate(g.date));
    else if (parts.length) monthHead = " | " + esc(month);
    else parts.unshift({ t: month, short: "", his: false });
  }
  const dateDown = tSeries || (!series && (bigStage || mteCard || !parts.length));
  if (dateDown && !bigStage && !mteCard) {
    parts.unshift({ t: dateText, short: "", his: false });
  }
  const wrap = (p, colour) => '<span class="mdet' + (p.att ? " matt" : "") + '"' +
    (p.short ? ' data-short="' + esc(p.short) + '" data-trim="' + (p.pri || 5) + '"' : "") +
    (colour || p.it ? ' style="' + (colour ? "color:" + colour + ";" : "") +
      (p.it ? "font-style:italic" : "") + '"' : "") + ">" + esc(p.t) + "</span>";
  // ...and the ATTENDED note closes the row, hard against the boxes (his
  // call 2026-09-23)
  /* ATTENDED (his calls 2026-09-23): the footer says so, and names the game
     when his Attended cell does -- "Gm1", "Gm2". An x, or anything else, just
     reads "Attended". */
  const attWord = v => {
    const m = /gm\s*([12])/i.exec(String(v == null ? "" : v));
    return m ? "Gm" + m[1] : "";
  };
  const attGms = (series || [g]).map(x => attWord((x.mx || {}).attended))
    .filter(Boolean).filter((v, i, a) => a.indexOf(v) === i);
  const attText = g.sport === "CHK" && mx.attended
    ? "Attended" + (attGms.length ? " " + attGms.join(" & ") : "") : "";
  const SEP = '<span class="msep">|</span>';
  let chipHtml;
  // ATTENDED closes the details like any other, behind a pipe (his call
  // 2026-09-23): "Home & Home | Attended"
  if (attText) parts.push({ t: attText, short: "", his: true, att: true });
  // A NOTE WITH ITS OWN PIPES stripes by piece, not word by word (his call
  // 2026-09-21): "Stripe Out | B1G Expansion" reads Stripe Out in blue, B1G
  // Expansion in maize, and a grey pipe between
  if (mode === "stripe") {
    const pieces = [].concat.apply([], parts.map(p => p.t.indexOf(" | ") > -1
      ? p.t.split(" | ").map(t => Object.assign({}, p, { t: t, short: "" })) : [p]));
    parts.length = 0;
    pieces.forEach(p => parts.push(p));
  }
  if (SOLID[mode]) {
    chipHtml = parts.map(p => wrap(p, SOLID[mode])).join(SEP);
  } else if (mode === "stripe" && parts.length > 1) {
    chipHtml = parts.map((p, i) => wrap(p, i % 2 ? FMAIZE : FBLUE)).join(SEP);
  } else if (mode === "stripe" && parts.length === 1) {
    // THE STRIPE RULE, for one piece of text (his calls 2026-09-13):
    //   a SPELLED-OUT DATE   "Sep 21, 2024" -> the day blue, the YEAR maize
    //   several words        alternate word by word, starting blue
    //   one unbroken run     "9/21/24" -> digits blue, separators maize
    const only = parts[0].t;
    const spaced = only.indexOf(" ") > -1;
    const longDate = /^[A-Z][a-z]{2} \d+, \d{4}$/.test(only);
    let runs;
    if (longDate) {
      const cut = only.lastIndexOf(" ");
      runs = [[only.slice(0, cut), FBLUE], [only.slice(cut + 1), FMAIZE]];
    } else if (spaced) {
      runs = only.split(/\s+/).map((w, i) => [w, i % 2 ? FMAIZE : FBLUE]);
    } else {
      runs = only.split(/(\d+)/).filter(Boolean)
        .map(s => [s, /\d/.test(s) ? FBLUE : FMAIZE]);
    }
    chipHtml = '<span class="mdet">' + runs
      .map(r => '<span style="color:' + r[1] + '">' + esc(r[0]) + "</span>")
      .join(longDate ? " " : (spaced ? " " : "")) + "</span>";
  } else {
    chipHtml = parts.map(p => wrap(p)).join(SEP);
  }
  // a postseason win, or a win over Ohio State, Michigan State or Notre Dame,
  // washes the WHOLE card in the opponent's colour instead of its stripe.
  // THE WASH IS HIS SHEET'S DECISION AND NOTHING ELSE (his call 2026-09-14).
  // It used to fall back to rules of my own -- postseason, a conference title,
  // a rival, a Big Ten Tournament won -- which he has now retired in favour of
  // the Shade column. A season he has not filled in simply has no washes.
  // CORNELL BASKETBALL (his call 2026-09-18): every NCAA Tournament win and
  // every Ivy Madness win is filled; an NCAA win takes an NCAA-blue border and
  // an Ivy Madness FINAL won takes Ivy green
  const cuCbb = fid === CORNELL && g.sport === "CBB" && !lost && !upcoming(g);
  const cuNcaa = cuCbb && (g.stage || "").indexOf("NCAA Tournament") === 0;
  const cuIvyFinal = cuCbb && g.stage === "Ivy Madness | Championship";
  const cuIvy = cuCbb && (g.stage || "").indexOf("Ivy Madness") === 0;
  const bigWin = !!mx.shade || cuNcaa || cuIvy;
  // a CORNELL hockey NCAA Tournament LOSS greys the seed and the ranking (his
  // call 2026-09-18)
  const ncaaLoss = fid === CORNELL && g.sport === "CHK" && lost &&
    (g.stage || "").indexOf("NCAA Tournament") === 0;
  let cls = " mich mich-" + g.sport.toLowerCase() + (ncaaLoss ? " ncaaloss" : "") +
    // THE BANDED CARD, everywhere a pro game is not a playoff game (his call
    // 2026-09-28): the Tigers' regular season, the Red Wings' and the
    // Pistons' national-TV nights, and every NBA Cup game, Pistons or
    // Cavaliers. A win runs the opponent's colour across the line through a
    // bare score; a defeat goes grey and italic.
    (g.sport === "MLB" && !g.post || cuPlain ||
      ((g.sport === "NHL" || g.sport === "NBA") && !g.post &&
       (!g.stage || g.stage.indexOf("NBA Cup") === 0)) ? " band" : "") +
    (bigWin ? " mwash" : "") + (lost ? " dimmed" : "") +
    // the existing no-bold class: the wash stays, the weight goes
    (bothMine || flatSplit ? " flatwin" : "") +
    (g.sport === "NBA" && bothMine ? " nobold" : "") +
    (g.ot && !series ? " ot" : "") +
    // THE OPPONENT'S RANKING GREYS ON ANYTHING THAT IS NOT A WIN (his call
    // 2026-09-27): a tie as well as a defeat, a shootout he won included. The
    // only number that keeps its colour is one he beat.
    (sres && sres !== "win" ? " rk-grey"
      : series ? ""
      : dimmed(g) ? " rk-grey" : isUpset(g) ? " rk-upset" : "");
  // NOTE: no rk-no here. A Michigan card KEEPS its rank column on a seeded
  // game, empty (his call 2026-09-11), so the vs. starts where every other
  // card starts and the seed follows it.
  // A FINAL WON takes a border of its own (his calls 2026-09-11): the Big Ten
  // Tournament final in Big Ten blue, the NCAA final in NCAA blue, the CFP
  // title game in CFP gold. WINS ONLY -- reaching a final is not winning one,
  // so the 2013 and 2018 NCAA finals and the 2014 / 2019 / 2026 Big Ten finals
  // carry no frame. Nothing else borders itself either: an ordinary loss goes
  // unframed, the muting alone says it. A FINAL BEATS HIS BORDER COLUMN (his
  // call 2026-09-11): gold and blue win over a maize set by hand. On every
  // other game his column is still the last word.
  const st = g.stage || "";
  const finalRing = lost ? null
    : st === "Big Ten Tournament | Championship" ? "#0088ce"
    : st === "NCAA Tournament | Championship" ? "#005eb8"
    : st === "CFP | Championship" ? "#c28c19" : null;
  // "Opponent" in his Border column means THEIR colour (his call 2026-09-13),
  // brightened the way a rival-loss border is on the other views -- the card
  // wash is the same colour lightened toward the page, so the border reads as
  // the deeper version of it.
  const bword = String(mx.border || "").trim().toLowerCase();
  // A WIN IN THE NCAA TOURNAMENT OR THE CFP takes the same grey frame as a
  // preseason tournament when he has given no border of his own (his call
  // 2026-09-14). The championship rings above still beat it, so a title win
  // keeps its blue or its gold; a LOSS stays unframed, the muting says it.
  // THE NCAA TOURNAMENT FRAMES A LOSS TOO (his call 2026-09-14), the same as
  // the football postseason below -- it used to frame wins only, which left a
  // Sweet Sixteen defeat bare beside a dashed bowl defeat.
  const ncaaGame = !upcoming(g) && st.indexOf("NCAA Tournament") === 0;
  // AN ORDINARY BOWL takes the same grey an MTE does (his call 2026-09-14) --
  // not CFP gold. The CFP and the Big Ten Championship Game are not ordinary
  // bowls; everything else postseason in football is.
  // ...and the CFP counts as one for the FRAME (his call 2026-09-14), so a
  // semifinal LOSS is dashed grey like any other bowl loss. Only the Big Ten
  // Championship Game is left out, which carries his own blue.
  const bowlGame = g.sport === "CFB" && !!st &&
    st.indexOf("Big Ten Championship") !== 0;
  // A BIG TEN TOURNAMENT DEFEAT is dashed grey like a bowl (his call
  // 2026-09-22): basketball's every loss, and hockey's LOST GAMES IN A LOST
  // SERIES -- a win inside a lost series, or a loss inside one Michigan went
  // on to win, keeps its plain frame
  // ...and Cornell's ECAC Tournament and the NIT the same way (his call
  // 2026-09-22)
  // ...and Ivy Madness, its FINAL alone (his call 2026-09-22)
  const b1gTourney = st.indexOf("Big Ten Tournament") === 0 ||
    st.indexOf("ECAC Tournament") === 0 || st.indexOf("NIT") === 0 ||
    st === "Ivy Madness | Championship";
  const bttLoss = b1gTourney && lost && !upcoming(g) &&
    (g.sport !== "CHK" || !g._gm || g._gm.lost);
  // QUINNIPIAC'S FRAME READS YELLOW ON A CORNELL HOCKEY CARD (his call
  // 2026-09-28): the Bobcats' navy is all but the card's own ground, so an
  // "Opponent" border disappeared into it. Their gold instead -- the SHADING
  // is untouched, this is the frame alone.
  const CU_RING = { "2514": "#e8c34a" };      // Quinnipiac
  const bc = bword === "opponent"
    ? (cuPlain && CU_RING[opp.id]) || brighten(teamColor(opp), 130)
    : cuNcaa ? "#4d9ae0" : cuIvyFinal ? "#0f6a37"
    : michColour(mx.border) || finalRing ||
      // a PRESEASON TOURNAMENT carries a grey frame of its own (his call
      // 2026-09-13), dashed when the game was lost
      // ...and the Great Lakes Invitational (g.frame) takes it too (2026-09-16)
      (g.preseason || g.frame || bowlGame || ncaaGame || bttLoss ? "#8a8a92" : null);
  // ...and like an MTE it goes dashed on a loss
  if (((g.preseason || g.frame || bowlGame || ncaaGame) && lost) || bttLoss)
    cls += " predash";
  let ring = "";
  if (bc) {
    cls += " celebrate";
    ring = ";--celeb:" + bc + ";--celebring:" + bc + "44";
  }
  // A TOURNAMENT HEADER WEARS ITS TOURNAMENT'S COLOUR (his call 2026-09-14),
  // the same three the championship rings and the divider tiles use. NCAA blue
  // is lightened to read on the card, exactly as it is on a tile.
  // A NEW YEAR'S SIX bowl reads in CFP gold too (his call 2026-09-14) -- for
  // Michigan that is the 2011 Sugar, the 2016 Orange and the 2018 Peach. A CFP
  // game played IN one of them already carries the gold through its own stage.
  const stageCol = stageColor(g);
  // THE RED WINGS', PISTONS' AND CAVALIERS' CARD (his call 2026-09-18):
  //   2026 FIRST ROUND | GAME 2 (1-1)
  //   [logo] 4  Orlando                           [98-95]
  //          1  4/22/2026 | TNT 7:30 PM
  // the opponent's seed in the gap after the logo, his team's directly below
  // it, and the date and TV lined up under the opponent's name
  // THE TIGERS' REGULAR-SEASON CARD (2026-09-18): the date and TV in the
  // header, and a chip for why it is here -- Walk-Off, 11 Innings, No-Hitter
  if (g.sport === "MLB" && !g.post) {
    // NATIONAL TV ONLY on these (his call 2026-09-18), by his definition of
    // national (2026-09-22) -- no MLB Network; a game on the local channel
    // alone shows its time and nothing else
    const nets = g.nets || [];
    const net = PRO_NATIONAL.find(n => nets.indexOf(n) > -1) || "";
    const t = fmtTime(g.time).replace(/(am|pm)$/, " $1").toUpperCase();
    // NO-HITTER is the only chip left (his call 2026-09-18)
    const chips = mx.nohit ? chip("champ", "No-Hitter") : "";
    return '<div class="row' + cls + '" data-id="' + g.id + '" style="--winwash:' +
      shade(teamColor(opp)) + ring + '">' +
      '<div class="sport"' + col(p.headCol) + "><span>" + fmtDate(g.date) + " | " +
      esc(g.dow + " " + t + (net ? " | " + net : "")) + "</span></div>" +
      '<div class="teams">' + oppLine + "</div>" +
      (chips ? '<div class="tags">' + chips + "</div>" : "") + "</div>";
  }
  // A PISTONS OR RED WINGS REGULAR-SEASON GAME -- kept for being on national
  // TV (his call 2026-09-22) -- reads like the Tigers': the date, the day, the
  // network and the time in the header, the opponent below, nothing else
  if ((g.sport === "NHL" || g.sport === "NBA") && !g.post && !g.stage) {
    const nets = g.nets || [];
    const net = PRO_NATIONAL.find(n => nets.indexOf(n) > -1) || "";
    const t = fmtTime(g.time).replace(/(am|pm)$/, " $1").toUpperCase();
    return '<div class="row' + cls + '" data-id="' + g.id + '" style="--winwash:' +
      shade(teamColor(opp)) + ring + '">' +
      '<div class="sport"' + col(p.headCol) + "><span>" + fmtDate(g.date) + " | " +
      esc(g.dow + " " + t + (net ? " | " + net : "")) + "</span></div>" +
      '<div class="teams">' + oppLine + "</div></div>";
  }
  if (g.sport === "NHL" || g.sport === "NBA" || g.sport === "MLB") {
    // the NATIONAL broadcast when there was one; a local or regional channel
    // only when there was not (the 1997 Red Wings on WKBD), and never radio
    // or a streaming package
    const NATIONAL = ["ABC", "NBC", "CBS", "FOX", "ESPN", "TNT", "TBS", "ESPN2", "truTV",
                      "NBCSN", "CNBC", "USA Net", "NBA TV", "NHL Network", "Versus", "OLN",
                      "Prime Video", "Peacock", "Netflix", "HBO Max"];
    const nets = g.nets || [];
    // NATIONAL ONLY: every regional and local channel is gone (his call
    // 2026-09-18), so a game with no national broadcast shows its time alone
    const net = NATIONAL.find(n => nets.indexOf(n) > -1) || "";
    const t = fmtTime(g.time).replace(/(am|pm)$/, " $1").toUpperCase();
    let head;
    // a baseball season is named for its own year; the others end a year on
    const yr = g.sport === "MLB" ? g.season : g.season + 1;
    if (g.stage === "Play-In") {
      head = esc(yr + " Play-In Tournament");
    } else if (g.post) {
      head = esc(yr + " " + g.stage) + " | Game " + mx.game +
        " (" + esc(mx.series || "") + ")";
    } else {
      head = esc(g.date.slice(0, 4) + " " + g.stage);
    }
    const mySeed = m.seed ? '<span class="mrk2" style="color:' +
      ((PRO_BOX[fid] || {}).seed || "var(--rank)") + '">' + m.seed + "</span>" : "";
    return '<div class="row' + cls + '" data-id="' + g.id + '" style="--winwash:' +
      shade(teamColor(opp)) + ring + '">' +
      '<div class="sport"' + col(stageCol || p.headCol) + "><span>" + head + "</span></div>" +
      '<div class="teams">' + oppLine + "</div>" +
      '<div class="tags mdets">' + mySeed + '<span class="mdl"><span class="mdet">' +
      fmtDate(g.date) + " | " + esc((net ? net + " " : "") + t) + "</span></span></div></div>";
  }
  // THE LIONS' CARD (his call 2026-09-18): the header, the opponent, and a
  // third row of CHIPS like TV Windows' -- no record box
  if (g.sport === "NFL") {
    const nf = nflParts(g);
    return '<div class="row' + cls + '" data-id="' + g.id + '" style="--winwash:' +
      shade(teamColor(opp)) + ring + '">' +
      '<div class="sport"' + col(stageCol || p.headCol) + "><span>" + nf.head +
      "</span></div>" +
      '<div class="teams">' + oppLine + "</div>" +
      (nf.chips ? '<div class="tags">' + nf.chips + "</div>" : "") + "</div>";
  }
  return '<div class="row' + cls + '" data-id="' + g.id + '" style="--winwash:' +
    shade(MICH_WASH[opp.id] || teamColor(opp)) + ring + '">' +
    '<div class="sport"' + col(stageCol || p.headCol) + "><span>" + head +
      monthHead + (dateDown || series ? "" : headDate) + "</span></div>" +
    '<div class="teams">' + oppLine + "</div>" +
    '<div class="tags mdets">' +
      (mx.attended && g.sport !== "CHK" ? '<span class="mstar">*</span>' : "") +
      ownRank + '<span class="mdl">' +
      chipHtml + "</span>" + umRank +
    "</div></div>";
}

// A Michigan chip row that runs onto a second line trims its long show tags --
// "Big Noon Kickoff" to "Big Noon", "College GameDay" to "GameDay" (his call
// 2026-09-11). Re-run after every draw and when the window changes size.
/* The same idea as trimMichChips, for the OTHER views' headers: a stage label
   that would wrap gives up the word TOURNAMENT (2026-09-14). Their header is a
   flex row with the date pinned right, so a wrap is measured by HEIGHT against
   the line box. */
function trimStageHeads() {
  document.querySelectorAll(".row .sport").forEach(head => {
    const s = head.querySelector("[data-short]");
    if (!s) return;
    if (s.dataset.full) s.textContent = s.dataset.full;
    const lh = parseFloat(getComputedStyle(head).lineHeight) || 19;
    if (head.getBoundingClientRect().height <= lh * 1.6) return;
    if (!s.dataset.full) s.dataset.full = s.textContent;
    s.textContent = s.dataset.short;
  });
}

function trimMichChips() {
  // SWEET SIXTEEN and ELITE EIGHT after an opponent's name shorten to S16 and
  // E8 only when the name would otherwise be cut (his call 2026-09-18)
  document.querySelectorAll(".row.mich .mfin[data-short]").forEach(f => {
    if (f.dataset.full) f.textContent = f.dataset.full;
    const nm = f.parentElement && f.parentElement.querySelector(".mn");
    if (nm && nm.scrollWidth > nm.clientWidth + 1) {
      f.dataset.full = f.textContent;
      f.textContent = f.dataset.short;
    }
  });
  // THE HEADER FIRST (his call 2026-09-14). It holds one piece of text rather
  // than a row of them, so a wrap is measured by HEIGHT against the line box,
  // not by comparing children the way the footer does.
  document.querySelectorAll(".row.mich .sport").forEach(head => {
    const shorts = Array.prototype.slice.call(head.querySelectorAll("[data-short]"));
    if (!shorts.length) return;
    shorts.forEach(s => { if (s.dataset.full) s.textContent = s.dataset.full; });
    const lh = parseFloat(getComputedStyle(head).lineHeight) || 19;
    const wrapped = () => head.getBoundingClientRect().height > lh * 1.5;
    if (!wrapped()) return;
    shorts.sort((a, b) => (+a.dataset.trim || 5) - (+b.dataset.trim || 5));
    for (let i = 0; i < shorts.length; i++) {
      const s = shorts[i];
      if (!s.dataset.full) s.dataset.full = s.textContent;
      s.textContent = s.dataset.short;
      if (!wrapped()) return;
    }
  });
  document.querySelectorAll(".row.mich .mdl").forEach(row => {
    const shorts = Array.prototype.slice.call(row.querySelectorAll("[data-short]"));
    if (!shorts.length) return;
    // every pass starts from the FULL text: a wider window gives room back
    shorts.forEach(s => { if (s.dataset.full) s.textContent = s.dataset.full; });
    const first = row.firstElementChild;
    const wrapped = () => Array.prototype.some.call(row.children,
      c => c.offsetTop > first.offsetTop + 2);
    if (!wrapped()) return;
    // AS FEW PIECES AS POSSIBLE (his call 2026-09-14). Shortening everything
    // the moment a row wrapped left "LCA | N&N" on a card with room for
    // "Little Caesars Arena | N&N". One at a time instead, checking after
    // each, and in HIS order of preference -- see `bit` for the numbers. Ties
    // keep the order they were written in.
    shorts.sort((a, b) => (+a.dataset.trim || 5) - (+b.dataset.trim || 5));
    for (let i = 0; i < shorts.length; i++) {
      const s = shorts[i];
      if (!s.dataset.full) s.dataset.full = s.textContent;
      s.textContent = s.dataset.short;
      if (!wrapped()) return;
    }
  });
}
let MICH_RESIZE = null;
window.addEventListener("resize", () => {
  clearTimeout(MICH_RESIZE);
  MICH_RESIZE = setTimeout(() => {
    if (teamView()) trimMichChips(); else trimStageHeads();
  }, 150);
});

/* Dividers in the Michigan view (his call 2026-09-11), only when one season
   is picked: a BYE for each Saturday a football schedule skips, and
   POSTSEASON where the conference title game or tournament begins. Each is a
   TILE in the grid, so
   on a desktop it takes one card's slot and three-across stays in step. */
// Consecutive regular-season hockey games against one opponent, within three
// days, become one card (his call 2026-09-16). Each unit is drawn from its
// OLDEST game, carrying the pair as _series and his Sheet columns merged: a
// shade, a border or a star on either game belongs to the series.
// A CONFERENCE-TOURNAMENT SERIES groups as well (his call 2026-09-16) -- the
// Big Ten and ECAC best-of-threes -- up to three games of the same round
function hockeyConfSeries(g) {
  return /^(Big Ten|ECAC) Tournament/.test(g.stage || "");
}
// MICHIGAN STATE IS NEVER COMBINED (his call 2026-09-22): each game of the
// weekend gets its own card, both carrying the same week number
function groupable(g) {
  return g.sport === "CHK" && !g.preseason &&
    !g.teams.some(t => t.id === "127") &&
    // CORNELL IS NEVER COMBINED EITHER (his call 2026-09-27): a weekend gets
    // two cards. Its ECAC series still runs through the grouping, which is
    // what splits it one card per game and writes "Game 2 (1-0)".
    !(VIEW === "cornell" && !g.stage) &&
    (!g.stage || hockeyConfSeries(g));
}
// The runs of games a card can be built from -- the grouping alone, so the
// HIGHLIGHTS filter can ask its question of a whole card (his catch
// 2026-09-25) instead of splitting a weekend in half.
function hockeyGroups(list) {
  const units = [];
  const oppOf = g => (g.teams.find(t => t.id !== (g.focus || focusId())) || {}).id;
  const day = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) / 864e5;
  for (let i = 0; i < list.length; i++) {
    const g = list[i];
    if (!groupable(g)) { units.push([g]); continue; }
    const run = [g];
    const max = g.stage ? 3 : 2;
    while (run.length < max) {
      const n = list[i + run.length], last = run[run.length - 1];
      // a NEUTRAL-SITE game never shares a card with one that was not (his
      // call 2026-09-16): Duel in the D keeps a card of its own, same [wX]
      // ...nor two games played at DIFFERENT RINKS (his call 2026-10-02):
      // 2026-27 ends its Wisconsin weekend outdoors at Lambeau Field, which
      // is a card of its own
      const sameRink = !n || !n.venue || !g.venue || n.venue === g.venue;
      // ...but a weekend SPLIT BETWEEN THE TWO RINKS is one contract, not two
      // (his call 2026-10-04): Michigan hosts Bowling Green on the Friday and
      // visits on the Saturday, and that is one card -- which the card itself
      // has always known how to draw, reading "vs. Bowling Green" with
      // "Home & Away" underneath (see the homeAway footer). The rink test
      // above, written for the Lambeau weekend two days earlier, had quietly
      // split every one of these: six Western Michigan weekends and Cornell's
      // 2015 Niagara one as well as this. Wisconsin's Lambeau weekend is
      // still two cards, because both of THOSE are away games.
      const sideOf = x =>
        (x.teams.find(t => t.id !== (x.focus || focusId())) || {}).home ? "away" : "home";
      const split = !!n && !n.neutral && !g.neutral && sideOf(n) !== sideOf(g);
      if (!n || !groupable(n) || oppOf(n) !== oppOf(g) || (n.stage || "") !== (g.stage || "") ||
          !!n.neutral !== !!g.neutral || (!sameRink && !split) ||
          Math.abs(day(n.date) - day(last.date)) > 3) break;
      run.push(n);
    }
    i += run.length - 1;
    units.push(run.sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time)));
  }
  return units;
}

function hockeyUnits(list) {
  const units = hockeyGroups(list);
  const out = [];
  units.forEach(games => {
    // a single tournament game is an ordinary tournament card, not a series
    if (!groupable(games[0]) || (games[0].stage && games.length === 1)) {
      out.push({ g: games[0], html: rowHtml(games[0], false) });
      return;
    }
    // A BEST-OF-THREE TOURNAMENT SERIES IS ONE CARD PER GAME (his call
    // 2026-09-22), so each game wears the colours of its OWN Sheet row; the
    // header names the game and the series score through it
    if (games[0].stage) {
      // did the SERIES end in defeat? each card needs to know, for the dashed
      // frame a lost series wears (his call 2026-09-22)
      let fw = 0, fl = 0;
      games.forEach(x => {
        if (upcoming(x) || x.tie) return;
        const me = x.teams.find(q => q.id === (VIEW === "cornell" ? CORNELL : MICHIGAN));
        if (me && me.win) fw++; else fl++;
      });
      const seriesLost = fl > fw;
      let w = 0, l = 0, t = 0;
      games.forEach((x, i) => {
        const me = x.teams.find(q => q.id === (VIEW === "cornell" ? CORNELL : MICHIGAN));
        if (!upcoming(x)) {
          if (x.tie) t++; else if (me && me.win) w++; else l++;
        }
        const rec = upcoming(x) ? "" : w + "-" + l + (t ? "-" + t : "");
        out.push({ g: x, html: rowHtml(Object.assign({}, x,
          { _gm: { n: i + 1, rec: rec, lost: seriesLost } }), false) });
      });
      return;
    }
    const mx = Object.assign({}, games[0].mx || {});
    // WHICH GAME HE WAS AT (his call 2026-09-23): a weekend card names it,
    // "Attended Gm2", so the merged flag remembers the game numbers
    mx.attGames = games.map((x, i) => ((x.mx || {}).attended ? i + 1 : 0)).filter(Boolean);
    games.slice(1).forEach(x => {
      const o = x.mx || {};
      if (o.shade) mx.shade = o.shade;
      if (o.attended) mx.attended = o.attended;
      if (!mx.border && o.border) mx.border = o.border;
      if (o.caps === "Y") mx.caps = "Y";
      if (o.note && o.note !== mx.note) mx.note = mx.note ? mx.note + " | " + o.note : o.note;
    });
    const rep = Object.assign({}, games[0], { _series: games, mx: mx });
    out.push({ g: games[0], html: rowHtml(rep, false) });
  });
  return out;
}

function michListHtml(list) {
  const units = hockeyUnits(list);
  const cards = units.map(u => u.html);
  list = units.map(u => u.g);
  // no dividers under a Highlights filter (his call 2026-09-16): a bye or a
  // tournament tile means nothing between two hand-picked games
  // ...nor under Postseason, nor on Combined, where three sports interleave
  if (FILT.season == null || list.length < 2 || FILT.hl || FILT.post || !SPORT_OF[TAB])
    return cards.join("");
  const day = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) / 864e5;
  const iso = n => new Date(n * 864e5).toISOString().slice(0, 10);
  const post = g => !!(g.post || g.champ);
  // each tile wears its tournament's colour -- the same three the championship
  // rings use (his call 2026-09-14)
  const TILE_CLASS = { "Big Ten Tournament": "g-b1g",
                       "NCAA Tournament": "g-ncaa",
                       "Postseason": "g-cfp" };
  const tile = t => '<div class="mgap' +
    (TILE_CLASS[t] ? " " + TILE_CLASS[t] : "") + '">' + t + "</div>";
  // WHICH TOURNAMENT A BASKETBALL GAME BELONGS TO (his call 2026-09-14), or ""
  // for the regular season, which needs no label of its own.
  const phase = g => {
    const st = g.stage || "";
    return st.indexOf("Big Ten Tournament") === 0 ? "Big Ten Tournament"
      : st.indexOf("ECAC Tournament") === 0 ? "ECAC Tournament"
      : st.indexOf("Ivy Madness") === 0 ? "Ivy Madness"
      : st.indexOf("NCAA Tournament") === 0 ? "NCAA Tournament"
      : st.indexOf("NIT") === 0 ? "National Invitation Tournament" : "";
  };
  const asc = SORT === "asc";
  const out = [];
  // A TILE MARKS WHERE THE TOURNAMENT BEGAN, not where the block starts on
  // screen (his call 2026-09-14). Oldest first that is above its games;
  // NEWEST first it is BELOW them -- the 2025-26 NCAA tile reads after Howard,
  // the first-round game, rather than above the championship. The two edges of
  // the list need it too, for a filter that leaves a run unbounded.
  if (asc && list[0].sport !== "CFB" && phase(list[0])) out.push(tile(phase(list[0])));
  out.push(cards[0]);
  for (let i = 1; i < list.length; i++) {
    const a = list[i - 1], b = list[i];
    const lo = Math.min(day(a.date), day(b.date)), hi = Math.max(day(a.date), day(b.date));
    const gaps = [];
    if (a.sport !== "CFB") {
      // basketball names the tournament rather than saying "Postseason": the
      // Big Ten Tournament is not flagged postseason, so one divider could
      // only ever sit between it and the NCAA. The label is whichever side is
      // LATER in time -- that is the run this boundary opens.
      const starts = asc ? b : a, from = asc ? a : b;
      if (phase(starts) && phase(starts) !== phase(from)) gaps.push(phase(starts));
    } else if (post(a) !== post(b)) {
      gaps.push("Postseason");
    } else if (!post(a)) {
      for (let d = lo + 4; d <= hi - 4; d++)
        if (new Date(d * 864e5).getUTCDay() === 6)
          gaps.push("Bye Week (" + fmtDate(iso(d)) + ")");
      if (SORT !== "asc") gaps.reverse();
    }
    gaps.forEach(t => out.push(tile(t)));
    out.push(cards[i]);
  }
  const last = list[list.length - 1];
  if (!asc && last.sport !== "CFB" && phase(last)) out.push(tile(phase(last)));
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

/* A KEY GAME THAT QUALIFIED BEFORE KICKOFF (his call 2026-09-20): both teams
   ranked, so the match-up itself was the draw -- a top-10 pair, or a ranked
   Big Ten meeting. TV Windows takes only these; an upset that needed the
   result is not added to the week after the fact. */
function rankedBefore(g) {
  return g.teams.length === 2 && g.teams.every(t => !!t.rank);
}
/* KEY GAMES (his call 2026-09-20) is wider than its categories: a Marquee
   window, any Ohio State / Michigan State / Notre Dame LOSS, and any Michigan
   WIN all belong, on top of the games with a type. */
/* HOW FAR BACK KEY GAMES READS (his call 2026-10-02): football to 2014 and
   basketball to 2011-12, the seasons the archive holds his rivals' games for.
   Before this it stopped at 2021 for both. */
const KEY_FROM = { CFB: 2014, CBB: 2011 };
function keyShows(g) {
  // a game from his RESULTS tab is here whatever else is true of it
  if (g.important) return true;
  if (!bigViewAllows(g)) return false;
  // FOOTBALL ONLY (his call 2026-09-20): basketball's Key Games stays the
  // categories and nothing else
  // ...and the floor holds for every reason but his own list
  if (g.season < (KEY_FROM[g.sport] || 2021)) return false;
  // basketball's Key Games is its categories, and now the seasons before the
  // archive as well -- their games kept for Rivals carry a type again
  if (g.sport !== "CFB") return !!g.type;
  // a MARQUEE WINDOW is not a qualification of its own (his call 2026-09-20):
  // such a game is here only if a category, a Michigan win or a rival's loss
  // puts it here
  if (g.type) return true;
  // ...and those two reach back only to 2021, with no CFP game and no bowl
  // (his calls 2026-09-20); a conference title game still arrives on its own
  // category above
  if (upcoming(g) || g.bowl || g.stage) return false;
  const m = michTeam(g);
  if (m && m.win) return true;
  return g.teams.some(t => isRival(t) && !t.win);
}
/* ...and a border is rarer here than elsewhere (his call 2026-09-20): MICHIGAN
   earns one by beating a ranked team or winning its conference title game, a
   RIVAL by losing while ranked or losing its conference title game. Nothing
   else on this tab is framed. */
// A BORDER ON KEY GAMES FILLS THE CARD TOO (his call 2026-10-02): the ring
// marked the game and the card stayed dark, which read as half an answer.
/* THE POSTSEASON NAMES ITS OWN COLOUR HERE (his call 2026-10-02), and it beats
   the winner's: the Big Ten in Big Ten blue, the CFP in gold, the NCAA
   Tournament in blue. It reads on Michigan's own win and on a rival's loss
   alike -- a rival losing the Big Ten Championship Game or the Big Ten
   Tournament final is Big Ten blue, a CFP or NCAA Tournament loss gold or
   blue -- and the card fills either way. These are the same colours Rivals
   uses (see rivalsBorder) and the season line (see champColour).
   A CONFERENCE FINAL ONLY: the quarters and the semis are not a title, and a
   bowl that is not a CFP game earns nothing extra. */
function keyStage(g) {
  if (upcoming(g)) return null;
  // Michigan's own game, or a rival's loss. (Key Games already bars a Michigan
  // loss and a rival win, so either one is the result he wants coloured.)
  if (!michTeam(g) && !g.teams.some(t => isRival(t) && !t.win)) return null;
  const s = g.stage || "";
  if (s.indexOf("CFP") === 0) return "#c28c19";
  if (s.indexOf("NCAA Tournament") === 0) return "#0053b8";
  if (s === "Big Ten Championship" || s === "Big Ten Tournament | Championship")
    return "#0088ce";
  return null;
}
/* A MICHIGAN WIN OVER A RANKED TEAM IN A MARQUEE WINDOW FILLS MAIZE (his call
   2026-10-06). Marquee is TV Windows' own idea -- the games he plans a weekend
   around -- and that is the one view where a Michigan win like this was marked
   by a border alone. Elsewhere it is a no-op: Key Games already fills a
   bordered Michigan card, and on Rivals a Michigan win fills whatever else is
   true. The wash is the winner's colour, which for Michigan is maize. */
function marqueeFill(g) {
  if (upcoming(g) || !g.mq) return false;
  if (g.sport !== "CFB" && g.sport !== "CBB") return false;
  const m = michTeam(g);
  if (!m || !m.win) return false;
  return g.teams.some(t => t.id !== MICHIGAN && !!t.rank);
}
function keyFill(g) {
  if (VIEW !== "big") return false;
  if (keyStage(g)) return true;
  return !!michTeam(g) && !!keyRing(g);
}
function keyRing(g) {
  const stage = keyStage(g);
  if (stage) return [stage, stage + "44"];
  const m = michTeam(g);
  if (m) {
    const beat = g.teams.find(t => t.id !== MICHIGAN);
    return (g.title || (beat && beat.rank)) ? celebrateColor(g) : null;
  }
  const rival = g.teams.find(t => isRival(t) && !t.win);
  return (g.title || (rival && rival.rank)) ? celebrateColor(g) : null;
}
function bigViewAllows(g) {
  // Key Games is the view he browses for pleasure: no Michigan losses and no
  // rival wins. Both still appear under TV Windows, which is a record of what
  // was ON, not a highlight reel.
  const mich = g.teams.find(t => t.id === MICHIGAN);
  // ...but a game that has not kicked off has no winner, and must not be read
  // as a Michigan loss (his call 2026-09-14, when upcoming games joined this
  // view) -- see `upcoming` below
  if (mich && !mich.win && !upcoming(g)) return false;
  return !g.teams.some(t => RIVALS.indexOf(t.id) > -1 && t.win);
}
// NOT PLAYED YET (his call 2026-09-12). An upcoming game has no score and no
// winner, so every rule that reads a RESULT has to step around it: the washes,
// the borders, the capitals, the strikethrough, the grey rankings. Without
// this a game that has not kicked off reads as a Michigan loss, because
// "did not win" and "lost" are the same test everywhere else.
function upcoming(g) { return !!g.upcoming; }
/* BASKETBALL'S WEEK (his call 2026-10-06), for TV Windows only. Football takes
   its week number from ESPN; basketball's means nothing to a viewer, so a week
   is Monday to Sunday and the numbering starts with the week that holds
   JANUARY'S FIRST SATURDAY -- the point conference play is fully under way,
   and the same line Marquee is drawn on. November and December are buckets in
   front of it and the conference tournaments are Postseason behind it, so the
   numbered weeks are the conference season and nothing else.
   It comes to 9 or 10 weeks a season; only 2022-23, whose New Year's Day fell
   on a Sunday, is a week short. */
function cbbWeek1(season) {
  const jan = new Date(Date.UTC(season + 1, 0, 1));
  // the first Saturday on or after 1 January, then back to its Monday
  const sat = jan.getTime() + ((6 - jan.getUTCDay() + 7) % 7) * 864e5;
  return sat - 5 * 864e5;
}
function cbbWeekNo(g) {
  if (g.sport !== "CBB" || g.stage) return null;
  const m = +g.date.slice(5, 7);
  // November and December are named, not numbered -- "December" means
  // December, even in the years when week 1's Monday falls on the 27th
  if (m === 11 || m === 12) return null;
  const d = Date.UTC(+g.date.slice(0, 4), m - 1, +g.date.slice(8, 10));
  const mon = d - ((new Date(d).getUTCDay() + 6) % 7) * 864e5;
  // a game before week 1 -- 1 January in a year whose first Saturday is the
  // 7th -- is week 1 all the same
  return Math.max(1, Math.round((mon - cbbWeek1(g.season)) / (7 * 864e5)) + 1);
}
// this week's Monday, as YYYY-MM-DD
function weekStart() {
  const d = new Date();
  d.setDate(d.getDate() - (d.getDay() + 6) % 7);
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" +
    String(d.getDate()).padStart(2, "0");
}
// today through the coming Sunday (today itself on a Sunday), as YYYY-MM-DD
function weekEnd() {
  const d = new Date();
  d.setDate(d.getDate() + (7 - d.getDay()) % 7);
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" +
    String(d.getDate()).padStart(2, "0");
}
// A score that does not exist yet must render as NOTHING. Concatenating null
// into markup prints the word "null", which is how the first upcoming cards
// went out reading "null null" (2026-09-12).
function scoreText(v) { return (v === null || v === undefined) ? "" : v; }
function isRival(t) { return RIVALS.indexOf(t.id) > -1; }
function michTeam(g) { return g.teams.find(t => t.id === MICHIGAN); }
/* TEAM VIEWS (2026-09-16): the Michigan card now serves any FOCUS team --
   Michigan's views, and Cornell's (hockey, and basketball's Ivy and NCAA
   Tournament games). Every record of a team view carries `focus`, the team the
   card is about; a game in two teams' views is two records. */
const CORNELL = "172";
// THE DETROIT TEAMS are team views too (2026-09-18): the Lions' card is the
// Michigan card, focused on "nfl-8"
const LIONS = "nfl-8";
const VIEW_TEAM = { michigan: "130", cornell: "172", lions: LIONS,
                    redwings: "nhl-5", pistons: "nba-8", cavaliers: "nba-5",
                    tigers: "mlb-6" };
function teamView() { return !!VIEW_TEAM[VIEW]; }
function focusId() { return VIEW_TEAM[VIEW] || MICHIGAN; }
function proView() {
  return ["tigers", "lions", "redwings", "pistons", "cavaliers"].indexOf(VIEW) > -1;
}
// the three PLAYOFF teams (and the NBA Cup): their own card and filters
// rules.py's PRO_NATIONAL: what counts as national TV for the Detroit
// teams' regular seasons (his definition, 2026-09-22)
const PRO_NATIONAL = ["FOX", "ABC", "NBC", "CBS", "ESPN", "TNT", "TBS", "FS1", "ESPN2",
  "NBCSN", "truTV", "CNBC", "USA Net", "USA", "Versus", "OLN", "Apple TV", "Apple TV+",
  "Peacock", "Prime Video", "Netflix", "YouTube", "Roku", "Facebook Watch"];
function seriesView() { return proView() && VIEW !== "lions"; }
// each team's boxes and the colour its own seed reads in
const PRO_BOX = {
  "nhl-5": { bg: "#ce1126", fg: "#ffffff", seed: "#ff5a5f" },     // Red Wings
  // his colours (2026-09-18)
  "nba-8": { bg: "#0186a7", fg: "#ffa300", seed: "#ffa300" },     // Pistons
  "nba-5": { bg: "#72253d", fg: "#b4985a", seed: "#b4985a" },     // Cavaliers
  "mlb-6": { bg: "#0c2340", fg: "#ffffff", seed: "#ff8a3d" }      // Tigers
};
function focusTeam(g) { return g.teams.find(t => t.id === (g.focus || focusId())); }
// Which teams his Sheet colours AT ALL -- read once from the data, so the day
// he colours a Pistons game their whole tab starts reading his columns
// instead of the fallback (his call 2026-09-28).
let SHEET_BOXED = null;
function sheetBoxed(fid) {
  if (!SHEET_BOXED) {
    SHEET_BOXED = new Set();
    GAMES.forEach(x => { if (x.focus && (x.mx || {}).box) SHEET_BOXED.add(x.focus); });
  }
  return SHEET_BOXED.has(fid);
}

/* HIGHLIGHTS on the Michigan views (his calls 2026-09-16). Never a game not
   yet played.
     Special     WIN, shaded, with a maize / CFP / NCAA border -- or a B1G
                 border, but only on a Big Ten Tournament game or the Big Ten
                 Championship Game (a regular-season title clinch does not count)
     Memorable   WIN, shaded and/or any border -- Special games included
     Tournament  BASKETBALL ONLY, WIN: the NCAA Tournament (no Big Ten
                 Tournament, no NIT). Football has no equivalent option.
     Attended    his * in the Attended column, WIN OR LOSS
     Details     WIN OR LOSS: a neutral site outside the postseason (MTEs
                 included, and a home game moved off campus -- Northwestern
                 at Wrigley Field), a Home & Home / Neutral & Neutral / Home & Neutral
                 (never Notre Dame's -- that is a rivalry, not a scheduled
                 series), the Big Ten/ACC Challenge or the Gavitt Games
   A "border" is the one HE gives in the sheet, or the championship ring a
   title win carries on its own. The automatic grey frame on a bowl, an MTE or
   an NCAA game is not one -- every such game has it, so it says nothing. */
function michBorder(g) {
  const st = g.stage || "";
  if (st === "Big Ten Tournament | Championship" ||
      st === "NCAA Tournament | Championship" ||
      st === "CFP | Championship") return "title";
  const b = String((g.mx || {}).border || "").trim().toLowerCase();
  if (!b) return "";
  const bigTenEvent = st.indexOf("Big Ten Tournament") === 0 ||
    st.indexOf("Big Ten Championship") === 0;
  if (["maize", "cfp", "ncaa"].indexOf(b) > -1 || (b === "b1g" && bigTenEvent))
    return "title";
  return "other";
}
/* THE JERSEY FILTER (Michigan football, his call 2026-09-18), from his Sheet's
   Jersey / Pants / Acc. columns: "Blue/Maize (White)", with his names for the
   ones that have them. In his order; a choice with no games is not offered. */
// UNIFORMS (renamed 2026-09-18): football's list, where White/Maize (Blue)
// is deliberately absent -- those games show only under All Uniforms -- and
// basketball's, from the score and rank boxes of his Sheet (J-M)
const JERSEYS = {
  CFB: ["Traditional", "Blue/Maize (Maize)", "Blue/Maize (White)",
        "All Blues", "Blue/Blue (Maize)", "Blue/Blue (White)",
        "White/Maize (White)", "White/Maize (Maize)",
        "White/Blue (White)", "White/Blue (Blue)",
        "All Whites", "White/White", "Maize Jersey"],
  CBB: ["Maize", "Blue", "White", "Special"]
};
function jerseyOf(g) {
  if (upcoming(g)) return null;
  const mx = g.mx || {};
  if (g.sport === "CBB") {
    // J (score background) names it, unless the game was SPECIAL: the two
    // boxes differ (J vs L, K vs M), or a maize or white jersey had anything
    // but blue lettering (his rules, 2026-09-18)
    const b = mx.box || {};
    const n = v => String(v || "").trim().toLowerCase();
    const j = n(b.score_bg), k = n(b.score_font), l = n(b.rank_bg), m = n(b.rank_font);
    if (!j) return null;
    if (j !== l || k !== m || ((j === "maize" || j === "white") && k !== "blue")) return "Special";
    return { maize: "Maize", blue: "Blue", white: "White" }[j] || "Special";
  }
  const u = mx.jersey;
  if (!u) return null;
  const [top, pants, acc] = u.split("/");
  if (top === "Maize") return "Maize Jersey";
  if (top === "White" && pants === "White") return acc === "White" ? "All Whites" : "White/White";
  if (top === "Blue" && pants === "Maize" && acc === "Blue") return "Traditional";
  if (top === "Blue" && pants === "Blue" && acc === "Blue") return "All Blues";
  return top + "/" + pants + " (" + acc + ")";
}
function highlightOf(g, kind) {
  const m = focusTeam(g);
  if (!m || upcoming(g)) return false;
  const mx = g.mx || {}, st = g.stage || "";
  const shaded = !!mx.shade, border = michBorder(g);
  if (kind === "Attended") return !!mx.attended;
  // PREGAME: College GameDay and/or Big Noon Kickoff was there (his call
  // 2026-09-18) -- football only, losses included like its neighbours
  // ...and on Combined, basketball's College GameDay too (2026-09-18)
  const combined = !SPORT_OF[TAB];
  if (kind === "Pregame") return (g.sport === "CFB" && showsOf(g).length > 0) ||
    (combined && g.sport === "CBB" && showsOf(g).indexOf("College GameDay") > -1);
  // MARQUEE (Combined, his call 2026-09-18), regular season, losses included:
  // football on a SATURDAY -- FOX at noon, CBS at 3:30, NBC or ABC in prime
  // time, or ABC against Ohio State at any hour; basketball on FOX, CBS or NBC,
  // or ESPN on a Saturday night from 6pm
  if (kind === "Marquee") {
    if (st) return false;
    const net = primaryNet(g.nets), hr = +String(g.time).slice(0, 2);
    if (g.sport === "CFB") {
      if (g.dow !== "Sat") return false;
      return (net === "FOX" && (hr === 11 || hr === 12)) ||
        (net === "CBS" && g.time === "15:30") ||
        ((net === "NBC" || net === "ABC") && hr >= 19) ||
        (net === "ABC" && g.teams.some(t => t.id === "194"));
    }
    if (g.sport === "CBB") {
      return ["FOX", "CBS", "NBC"].indexOf(net) > -1 ||
        (net === "ESPN" && g.dow === "Sat" && hr >= 18);
    }
    return false;
  }
  if (kind === "Details") {
    // the series the card itself shows: his hand tag wins over the derived one
    const FAMILY = ["Home & Home", "Neutral & Neutral", "Home & Neutral"];
    // (a weekend home-and-away is no longer a series at all -- see harvest)
    const hand = myTags(g.id).filter(t => FAMILY.indexOf(t) > -1);
    const notreDame = g.teams.some(t => t.id === "87");
    // (Combined leaves out hockey's series -- his call 2026-09-18)
    const series = !notreDame && !(combined && g.sport === "CHK") &&
      (hand.length > 0 || FAMILY.indexOf(g.series) > -1);
    // ...and in basketball, a College GameDay game (his call 2026-09-18)
    const gameDay = g.sport === "CBB" && showsOf(g).indexOf("College GameDay") > -1;
    return ((g.neutral || !!g.offsite) && !st && !g.post) || series || gameDay ||
      // CASE-INSENSITIVE, like every other test on an ESPN EVENT name (his
      // call 2026-10-06, after the "Fox" business): ESPN wrote these in
      // capitals before about 2021 -- "GAVITT TIPOFF GAMES", "BIG TEN/ACC
      // CHALLENGE" -- and nine games were missing this highlight.
      /ACC Challenge|Gavitt/i.test(g.event || "");
  }
  // HIS SHEET DECIDES THIS (his call 2026-09-25): he never shades or borders
  // a defeat, so the only work left here is keeping defeats out -- and a TIE
  // is not one, unless he lost the shootout, which reads as a defeat
  // everywhere else. That is what brings 2/9/2018 at Michigan State back.
  const lost = !m.win && (!g.tie || g.sho_win === false);
  if (lost) return false;
  const special = shaded && border === "title";
  if (kind === "Special") return special;
  if (kind === "Memorable") return shaded || !!border;
  if (kind === "Tournament") {
    return g.sport !== "CFB" && st.indexOf("NCAA Tournament") === 0;
  }
  // Combined's POSTSEASON: the NCAA Tournament plus the Big Ten Championship
  // Game and the CFP (2026-09-18)
  if (kind === "Postseason") {
    return (g.sport !== "CFB" && st.indexOf("NCAA Tournament") === 0) ||
      st.indexOf("Big Ten Championship") === 0 || st.indexOf("CFP") === 0;
  }
  return false;
}
// An upset: a ranked team lost to an unranked or a worse-ranked team.
/* LEVEL RANKS -- rules.py's LEVEL_BANDS, and its one-spot rule (his call
   2026-09-20). Two teams this close cannot upset one another, so the game is a
   Ranked Game and its numbers stay BLUE on TV Windows and Key Games. */
const LEVEL_BANDS = [[20, 25, 5], [11, 19, 4], [6, 10, 2]];
function levelRanks(a, b) {
  const lo = Math.min(a, b), hi = Math.max(a, b);
  if (hi - lo === 1 && hi > 5) return true;
  return LEVEL_BANDS.some(x => lo >= x[0] && hi <= x[1] && hi - lo <= x[2]);
}
// a REGULAR-SEASON game: the postseason reads its rankings literally
function regularSeason(g) {
  return !(g.post || g.bowl || g.stage || g.title || g.champ);
}
function isUpset(g) {
  if (upcoming(g)) return false;
  const w = g.teams.find(t => t.win), l = g.teams.find(t => !t.win);
  if (!(w && l && l.rank && (!w.rank || w.rank > l.rank))) return false;
  // the Ranked Game rule, both sports (his call 2026-09-20): a level pair is
  // no upset -- Ole Miss over LSU reads blue. REGULAR SEASON ONLY, and only on
  // TV Windows and Key Games; the Michigan and Rivals views read the rankings
  // as they stand
  const soft = (VIEW === "tv" || VIEW === "big") && regularSeason(g);
  return !(soft && w.rank && levelRanks(w.rank, l.rank));
}

/* A result he does not want to relive: a rival won, or Michigan lost. Both
   team lines go italic. */
function dimmed(g) {
  if (upcoming(g)) return false;
  const m = michTeam(g);
  // a hockey TIE MICHIGAN WON in the shootout or 3-on-3 is no defeat (his
  // call 2026-09-23)
  if (m && !m.win && g.tie && g.sho_win === true) return false;
  return (m && !m.win) || g.teams.some(t => isRival(t) && t.win);
}
// The STRIKETHROUGH is narrower than dimmed (his call 2026-09-12): it marks a
// team that beat MICHIGAN, nothing else. A rival beating anybody else still
// greys the rankings -- that is dimmed doing its job -- but the winner is not
// struck through, because it never beat him. 112 games stop being struck.
function struck(g) {
  if (upcoming(g)) return false;
  const m = michTeam(g);
  return !!(m && !m.win);
}
// ...and the winner is not even BOLD in two cases (his calls 2026-09-12):
// a RIVAL won, or ANYONE beat Michigan. A team that beat him reads struck
// through and unbolded, rival or not.
/* OHIO STATE, MICHIGAN STATE AND NOTRE DAME ARE NEVER BOLD on the CFB and CBB
   tabs (his call 2026-10-02: "it's rare, but never bold OSU, MSU, or ND names
   or scores"). It IS rare, which is why the rule used to be TV Windows' alone:
   Key Games bars a game a rival won and Rivals is a record of their losses.
   The way through is his RESULTS tab, which `keyShows` admits AHEAD of that
   bar -- two games in the archive, both of them two rivals meeting (Ohio State
   over Michigan State in 2012 and in 2021), and both read as Ohio State's
   triumph on Key Games until now. So the test is on the RESULT, not the view.
   Michigan's own defeat still unbolds on TV Windows only: the other views have
   no Michigan loss to show. */
function flatWin(g) {
  if (upcoming(g)) return false;
  if (g.teams.some(t => isRival(t) && t.win)) return true;
  if (VIEW !== "tv") return false;
  const m = michTeam(g);
  return !!(m && !m.win);
}

function celebrated(g) {
  if (upcoming(g)) return false;
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
  let list = GAMES.filter(g => !isHidden(g.id));
  // games added by hand live only in tags.json, so fold them back in
  Object.keys(TAGS).forEach(id => {
    const e = eff(id);
    if (e.add && e.game && !list.some(g => g.id === id)) list.push(e.game);
  });
  if (SPORT_OF[TAB]) list = list.filter(g => g.sport === SPORT_OF[TAB]);
  // A championship game shows on TV Windows even with no broadcast window --
  // 17 of the 46 have none, because the Big Ten title game kicks at 8pm and
  // the Pac-12 one was on a Friday. His call: they must all show.
  // Black Friday games carry no window, like championship games, so they need
  // the same admission -- without this they sat in the data unreachable.
  // Key Games needs a game TYPE. Being a conference-tournament game is not
  // itself a qualification -- an ACC first-rounder between unranked teams has
  // no business here, and every championship game carries a type anyway.
  list = list.filter(g => teamView() ? g.focus === focusId()
    : VIEW === "rivals" ? rivalsAllows(g)
    // KEY GAMES reaches the games kept for the Michigan and Rivals views too
    // (his call 2026-09-20): a Michigan win or a rival's loss belongs here
    // whether or not it had a window or a category of its own
    : VIEW === "big" ? keyShows(g)
    : g.rivals_only ? false
    : VIEW === "tv"
      ? ((g.slots || []).length || g.title || g.bfri || g.show || g.opener
         || g.showcase || g.kickoff || g.standin
         // a KEY GAME is on TV Windows too (his call 2026-09-18) -- never
         // Marquee, or it would have been here already -- but only one that
         // qualified BEFORE the week (2026-09-20)
         || (g.type && bigViewAllows(g) &&
             (g.sport !== "CFB" || rankedBefore(g))))
      : keyShows(g));
  // Basketball TV Windows run November to March now (his call 2026-09-11),
  // because the windows themselves reach into November and December. A game
  // with NO window of its own -- a College GameDay ride-along -- still has to
  // be January to March, which is what kept two November shows out before.
  if (VIEW === "tv" && SPORT_OF[TAB] === "CBB") {
    list = list.filter(g => {
      const m = +g.date.slice(5, 7);
      return (m >= 1 && m <= 3) || (g.slots || []).length || g.showcase ||
        (g.type && bigViewAllows(g));
    });
  }
  // CURRENT (his call 2026-09-16): every TV Windows game in the LATEST week
  // there is, the coming one included. Football's week is its number;
  // basketball has none, so its week is Monday to Sunday around the latest
  // game -- the same span the upcoming window runs to.
  // ...CURRENT IS NOW THIS WEEK, Monday to Sunday by the calendar (his call
  // 2026-09-18), not the latest week in the data. Only a week with nothing in
  // it -- basketball in September -- falls back to the latest one there is.
  const thisWeek = VIEW === "tv" && FILT.current
    ? list.filter(g => g.date >= weekStart() && g.date <= weekEnd()) : [];
  if (thisWeek.length) {
    list = thisWeek;
  } else if (VIEW === "tv" && FILT.current && list.length) {
    if (SPORT_OF[TAB] === "CFB") {
      const key = g => g.week == null ? -1 : g.season * 100 + g.week;
      const top = Math.max.apply(null, list.map(key));
      list = list.filter(g => key(g) === top);
    } else {
      const last = list.map(g => g.date).sort().pop();
      const d = new Date(last + "T12:00:00Z");
      const mon = new Date(d.getTime() - ((d.getUTCDay() + 6) % 7) * 864e5)
        .toISOString().slice(0, 10);
      list = list.filter(g => g.date >= mon);
    }
  }
  // the NETWORK a card actually names -- primaryNet, not every net ESPN lists,
  // so the filter and the header can never disagree (his call 2026-09-14).
  // It is a REGULAR-SEASON question: asking for CBS is asking what he watched
  // on CBS, not for the NCAA Tournament games CBS happened to carry, so any
  // game with a STAGE is out (a bowl, the CFP, the Big Ten or NCAA Tournament,
  // the NIT). A preseason MTE has no stage and stays.
  // ...and two questions that are not about a network at all, but that he
  // asks of the same dropdown (his call 2026-09-25): MARQUEE, the games he
  // plans a weekend around, and PRIMETIME, a 7pm-or-later start. They drop
  // the postseason exactly as a network does (his call 2026-09-25).
  if (FILT.net === "mq:") list = list.filter(g => g.mq && !g.stage);
  else if (FILT.net === "prime:") list = list.filter(primetime);
  else if (FILT.net) {
    list = list.filter(g => !g.stage && primaryNet(g.nets) === FILT.net);
  }
  // TV WINDOWS AND KEY GAMES look only as far as the coming Sunday (his call
  // 2026-09-18) -- the Michigan views load the whole season ahead, but these
  // two lists stop at the end of this week
  if (VIEW === "tv" || VIEW === "big") {
    const end = weekEnd();
    list = list.filter(g => !upcoming(g) || g.date <= end);
  }
  if (FILT.season != null) list = list.filter(g => g.season === FILT.season);
  if (teamView() && FILT.hl) {
    // A WEEKEND IS ONE CARD (his catch 2026-09-25): asking of each game
    // separately broke the pairs apart -- Ohio State 2019 and Penn State 2020
    // came back with the Saturday game gone and half a card left. Either game
    // qualifying now keeps both. A tournament series is one card per game, so
    // it shares nothing.
    const keep = new Set();
    hockeyGroups(list.slice().sort((a, b) =>
      (a.date + a.time).localeCompare(b.date + b.time))).forEach(run => {
      const hit = run.filter(x => highlightOf(x, FILT.hl));
      if (!hit.length) return;
      (run.length > 1 && run[0].stage ? hit : run).forEach(x => keep.add(x.id));
    });
    list = list.filter(g => keep.has(g.id));
  }
  if (teamView() && FILT.jersey) list = list.filter(g => jerseyOf(g) === FILT.jersey);
  if (seriesView() && FILT.cup) list = list.filter(g => !g.post);
  if (seriesView() && FILT.walk) list = list.filter(g => (g.mx || {}).walkoff);
  if (seriesView() && FILT.extra) list = list.filter(g => (g.mx || {}).extra);
  if (seriesView() && FILT.late) list = list.filter(g => (g.mx || {}).late);
  if (seriesView() && FILT.nohit) list = list.filter(g => (g.mx || {}).nohit);
  if (proView()) {
    if (FILT.prime) list = list.filter(g => !g.stage && (g.dow !== "Sun" ||
      (g.time !== "TBD" && g.time >= "19:00")));
    // KEY GAMES are his: a WIN he has shaded and/or bordered in the Sheet (his
    // call 2026-09-18), no longer the scoring-play rule
    if (FILT.key) list = list.filter(g => {
      const mx = g.mx || {}, me = g.teams.find(t => t.id === LIONS);
      return me && me.win && !upcoming(g) && (!!mx.shade || !!String(mx.border || "").trim());
    });
  }
  // Cornell basketball's NCAA Tournament button (his call 2026-09-17), and
  // Michigan's POSTSEASON button (2026-09-18): the Big Ten Championship Game
  // and Tournament, the CFP and the NCAA Tournament -- not the other bowls
  if (teamView() && FILT.post)
    list = list.filter(g => VIEW === "cornell"
      ? (g.stage || "").indexOf("NCAA Tournament") === 0
      : /^(Big Ten Championship|Big Ten Tournament|CFP|NCAA Tournament)/.test(g.stage || "") ||
        // ...and every bowl (his call 2026-09-18): a football stage is a bowl
        (g.sport === "CFB" && !!g.stage) || (g.sport === "NFL" && !!g.stage) ||
        ((g.sport === "NHL" || g.sport === "NBA" || g.sport === "MLB") && !!g.post));
  // Rivals filters by whose loss it was, what kind of game, and who won
  if (VIEW === "rivals") {
    if (FILT.rival) list = list.filter(g => rivalLoser(g) === FILT.rival);
    // the Postseason button: everything by default, pressed only the CFP and
    // the NCAA Tournament (his call 2026-09-11)
    if (FILT.post) list = list.filter(rivalsPost);
    if (FILT.winner) list = list.filter(g =>
      g.teams.some(t => t.win && t.id === FILT.winner));
  }
  // "Bowls" and "Postseason" are the named cuts at the end of those two
  // dropdowns (his call 2026-10-02); a numbered week or a named month is the
  // REGULAR season, so the postseason is taken out of March
  // Postseason is football's conference finals and bowls, basketball's
  // conference tournaments and the NCAA; November and December are
  // basketball's two buckets in front of its numbered weeks (2026-10-06)
  if (FILT.week === "postseason")
    list = list.filter(g => g.sport === "CFB" ? (!!g.title || g.week == null)
      : !!g.stage);
  else if (FILT.week === "nov" || FILT.week === "dec")
    list = list.filter(g => !g.stage &&
      +g.date.slice(5, 7) === (FILT.week === "nov" ? 11 : 12));
  else if (FILT.week != null)
    list = list.filter(g => g.sport === "CFB" ? (g.week === FILT.week && !g.title)
      : cbbWeekNo(g) === FILT.week);
  if (FILT.month === "postseason") list = list.filter(g => !!g.stage);
  else if (FILT.month != null)
    list = list.filter(g => +g.date.slice(5, 7) === FILT.month && !g.stage);
  // Marquee is a rule of its own now (rules.is_marquee), not a set of
  // windows the button ticks, so it stacks with the window dropdown instead
  // of pretending to be it. Nothing rides along any more.
  if (FILT.marquee) list = list.filter(g => g.mq);
  // UPSETS: the two upset categories on football's Key Games (his call
  // 2026-09-20)
  // ...and the games brought onto the tab without a category of their own --
  // Michigan over Oklahoma in Week 2 -- when the ranks make them upsets too
  // (his call 2026-09-20)
  if (FILT.upset) list = list.filter(g => /Upsets$/.test(g.type || "") || isUpset(g));
  // HIS RECENT STRETCH (2026-09-14): football from 2021, basketball from the
  // 2020-21 season -- which is season 2020 in the file, a basketball season
  // being named for the year it starts in.
  if (FILT.recent) {
    list = list.filter(g => g.season >= (g.sport === "CFB" ? 2021 : 2020));
  }
  if (FILT.windows && FILT.windows.length)
    list = list.filter(g =>
      (g.slots || []).some(w => FILT.windows.indexOf(w) > -1));
  // ...and "Important Results" is his Results tab rather than a category
  // (his call 2026-10-02), so it sits at the end of the same dropdown
  if (FILT.type === "important") list = list.filter(g => !!g.important);
  else if (FILT.type) list = list.filter(g => g.type === FILT.type);
  // COMBINED shows PLAYED GAMES ONLY (his call 2026-09-24), and can drop
  // hockey altogether
  if (teamView() && !SPORT_OF[TAB]) {
    list = list.filter(g => !upcoming(g));
    if (FILT.nohky) list = list.filter(g => g.sport !== "CHK");
  }
  if (FILT.team && String(FILT.team).indexOf("conf:") === 0) {
    const want = String(FILT.team).slice(5);
    list = list.filter(g => confsIn(g).indexOf(want) > -1);
  } else if (FILT.team) list = list.filter(g =>
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
  const block = g => (VIEW !== "rivals" && !teamView() &&
      g.sport === "CFB" && g.week != null)
    ? g.season + "-" + String(g.week).padStart(2, "0")
    : g.date;
  const chron = (a, b) => (a.date !== b.date)
    ? a.date.localeCompare(b.date)
    : (a.time !== b.time ? a.time.localeCompare(b.time) : rank(a) - rank(b));
  // KEY GAMES and RIVALS do not block at all (his call 2026-09-13): Newest
  // First means the LATEST KICKOFF first, so a night game leads the day it was
  // played. Only the date and time reverse -- the network tiebreak still reads
  // in his order, so two games at the same minute keep FOX ahead of ESPN.
  const flatSort = VIEW === "big" || VIEW === "rivals";
  const chronDesc = (a, b) => (a.date !== b.date)
    ? b.date.localeCompare(a.date)
    : (a.time !== b.time ? b.time.localeCompare(a.time) : rank(a) - rank(b));
  // A HIGHLIGHTS list read Newest First runs the SEASONS backwards but each
  // season forwards (his call 2026-09-18)
  const hlDesc = teamView() && FILT.hl && SORT !== "asc";
  list.sort((a, b) => {
    if (hlDesc) return a.season !== b.season ? b.season - a.season : chron(a, b);
    if (SORT === "asc") return chron(a, b);
    if (flatSort) return chronDesc(a, b);
    const ba = block(a), bb = block(b);
    return ba === bb ? chron(a, b) : bb.localeCompare(ba);
  });
  return list;
}

// The newest season that actually has games in THIS sport. SEASONS spans both
// sports, and basketball's newest one is empty for months -- 2026-27 has no
// games until November -- so the overall max opened the tab on nothing.
function latestSeason() {
  const own = GAMES.filter(g => (!SPORT_OF[TAB] || g.sport === SPORT_OF[TAB]) &&
      (teamView() ? g.focus === focusId() : !g.rivals_only))
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
    week: null, month: null, team: null, rival: null, post: false, winner: null,
    upset: false
  };
  // Combined's opening state is every season's Special games
  if (typeof TAB !== "undefined" && !SPORT_OF[TAB] && teamView()) {
    FILT.season = null; FILT.hl = "Special";
  }
}

function seasonLabel(y) {
  // College football is one calendar year; basketball straddles two.
  return (SPORT_OF[TAB] === "CFB" || SPORT_OF[TAB] === "NFL" || SPORT_OF[TAB] === "MLB")
    ? String(y) : y + "-" + String(y + 1).slice(2);
}

function filterChips() {
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
  const viewSeasons = Array.from(new Set(GAMES.filter(g => (!sport || g.sport === sport) &&
    (VIEW === "rivals" ? rivalsAllows(g)
      : teamView() ? g.focus === focusId()
      // KEY GAMES reaches its own seasons (2026-10-02), which run further back
      // than TV Windows' and include games kept only for the other views
      : VIEW === "big" ? keyShows(g)
      : !g.rivals_only)).map(g => g.season)));
  // ...and while "2021-Onward" is on, the years it hides are not offered
  // either (his call 2026-09-14) -- picking one could only return nothing
  const yearFloor = sport === "CFB" ? 2021 : 2020;
  // ...and under a Highlights choice, only the years that have one (his call
  // 2026-09-18)
  const hlYears = teamView() && FILT.hl
    ? new Set(visibleWithout("season").map(g => g.season)) : null;
  const yearList = (FILT.recent ? viewSeasons.filter(y => y >= yearFloor) : viewSeasons)
    .filter(y => !hlYears || hlYears.has(y) || y === FILT.season);
  let h = group("Year", select("season", "All Years",
    yearList.sort((a, b) => b - a).map(y => [seasonLabel(y), y]),
    FILT.season));
  // MICHIGAN (trial, 2026-09-11): Year, the OPPONENT and the sort.
  // Michigan is in every game on this view, so the Team filter lists who it
  // PLAYED and leaves Michigan itself out (his call 2026-09-14). His order is
  // rivals, the rest of the Big Ten, the other power leagues, then everyone
  // else, with a bar between each group -- one more bar than the other views,
  // which run the rivals into the Big Ten.
  if (teamView()) {
    // Cornell has no rivals pinned; its own league leads the list instead
    const rivalIds = VIEW === "cornell" ? []
      : sport === "CFB" ? ["194", "127", "87"] : ["127", "194", "87"];
    // COMBINED lists every opponent of the three sports in basketball's order
    // (his call 2026-09-20)
    const allSports = !sport;
    const seen = teamsIn(visibleWithout("team"),
      g => g.teams.map(t => t.id), FILT.team);
    seen.delete(focusId());
    const mt = teamOrder(allSports ? null : sport, seen, rivalIds,
      VIEW === "cornell" ? (TEAM_CONF[CORNELL] || {})[sport] : null,
      allSports ? "CBB" : null);
    const optOf = id => [(TEAMS[id] && TEAMS[id].short) || id, id];
    const lined = ids => ids.length
      ? [["─".repeat(12), null]].concat(ids.map(optOf)) : [];
    // teamOrder hands the pins back at the head of its Big Ten group; split
    // them out again so a bar can sit between the rivals and the rest
    const isRival = id => rivalIds.indexOf(id) > -1;
    // groups with nothing in them bring no bar (2026-09-16)
    // CORNELL splits only conference and non-conference (his call 2026-09-17)
    const byName = (x, y) => optOf(x)[0].localeCompare(optOf(y)[0]);
    // CORNELL HOCKEY: the five Ivies in his order, the rest of the ECAC, then
    // everyone else (his call 2026-09-18)
    const IVY_ORDER = ["Harvard", "Brown", "Dartmouth", "Princeton", "Yale"];
    const ivyOf = id => IVY_ORDER.indexOf(optOf(id)[0]);
    const teamGroups = (VIEW === "cornell" && sport === "CHK"
      ? [mt.bigTen.filter(id => ivyOf(id) > -1).sort((a, b) => ivyOf(a) - ivyOf(b)),
         mt.bigTen.filter(id => ivyOf(id) < 0).sort(byName),
         mt.power.concat(mt.rest).sort(byName)]
      : VIEW === "cornell"
      ? [mt.bigTen.filter(isRival), mt.bigTen.filter(id => !isRival(id)),
         mt.power.concat(mt.rest).sort(byName)]
      : [mt.bigTen.filter(isRival), mt.bigTen.filter(id => !isRival(id)),
         mt.power, mt.rest]).filter(ids => ids.length);
    // THE LIONS (his spec 2026-09-16): Year, Team, and three buttons --
    // PRIMETIME (every Sunday-night game and every game not on a Sunday), KEY
    // GAMES (wins decided in the last two minutes or overtime) and PLAYOFFS
    if (seriesView()) {
      // ...and the Cubs are named in this list, so his two Chicagos are not
      // both "Chicago" (his call 2026-09-20)
      const nameOf = id => id === "mlb-16" ? "Chi Cubs"
        : (TEAMS[id] && TEAMS[id].short) || id;
      /* HIS ORDERS FOR THESE DROPDOWNS (2026-09-20), a bar between sections and
         alphabetical inside any section he did not name:
           Tigers     Cleveland, Chicago, Minnesota, Kansas City | rest of the
                      AL | the NL
           Red Wings  Colorado, Chicago | the East | the West
         Leagues and conferences are read as they stand today, so Houston is an
         AL team throughout and Milwaukee a National League one. */
      const AL = ["1", "2", "3", "4", "5", "6", "7", "9", "10", "11", "12", "13",
                  "14", "18", "30"].map(n => "mlb-" + n);
      const EAST = ["1", "2", "5", "7", "10", "11", "12", "13", "14", "15", "16",
                    "20", "21", "23", "26", "29"].map(n => "nhl-" + n);
      const HEAD = { "mlb-6": ["mlb-5", "mlb-4", "mlb-9", "mlb-7"],
                     "nhl-5": ["nhl-17", "nhl-4"] }[focusId()] || [];
      const SPLIT = { "mlb-6": AL, "nhl-5": EAST }[focusId()];
      const alpha = ids => ids.map(id => [nameOf(id), id])
        .sort((a, b) => a[0].localeCompare(b[0]));
      const rest = Array.from(seen).filter(id => HEAD.indexOf(id) < 0);
      const groups = (SPLIT
        ? [HEAD.filter(id => seen.has(id)).map(id => [nameOf(id), id]),
           alpha(rest.filter(id => SPLIT.indexOf(id) > -1)),
           alpha(rest.filter(id => SPLIT.indexOf(id) < 0))]
        : [alpha(Array.from(seen))]).filter(x => x.length);
      h += group("Team", select("team", "All Teams",
        [].concat.apply([], groups.map((x, i) =>
          (i ? [["─".repeat(12), null]] : []).concat(x))),
        FILT.team));
      const btn = (act, on, label) => '<button class="f" data-act="' + act +
        '" aria-pressed="' + !!on + '">' + label + "</button>";
      return h + group("", (sport === "NBA" ? btn("post", FILT.post, "Playoffs") +
        btn("cup", FILT.cup, "NBA Cup") : "") +
        (sport === "MLB" ? btn("post", FILT.post, "Playoffs") +
          // Comebacks and Extra Innings buttons removed (his call 2026-09-18)
          btn("walk", FILT.walk, "Walk-Offs") +
          btn("nohit", FILT.nohit, "No-Hitters") : "") + sortButton());
    }
    if (proView()) {
      // the division first -- Green Bay, Chicago, Minnesota -- then a bar
      // and everyone else (his call 2026-09-18)
      const DIV = ["nfl-9", "nfl-3", "nfl-16"];
      const nameOf = id => (TEAMS[id] && TEAMS[id].short) || id;
      // ...then the rest of the NFC, a bar, and the AFC (his call 2026-09-18)
      const NFC = ["22", "1", "29", "3", "6", "8", "9", "14", "16", "18", "19", "21", "25",
                   "26", "27", "28"].map(n => "nfl-" + n);
      const alpha = ids => ids.map(id => [nameOf(id), id]).sort((a, b) => a[0].localeCompare(b[0]));
      const rest = Array.from(seen).filter(id => DIV.indexOf(id) < 0);
      const groups = [DIV.filter(id => seen.has(id)).map(id => [nameOf(id), id]),
                      alpha(rest.filter(id => NFC.indexOf(id) > -1)),
                      alpha(rest.filter(id => NFC.indexOf(id) < 0))].filter(x => x.length);
      h += group("Team", select("team", "All Teams",
        [].concat.apply([], groups.map((x, i) => (i ? [["\u2500".repeat(12), null]] : []).concat(x))),
        FILT.team));
      const btn = (act, on, label) => '<button class="f" data-act="' + act +
        '" aria-pressed="' + !!on + '">' + label + "</button>";
      return h + group("", btn("post", FILT.post, "Playoffs") +
        btn("key", FILT.key, "Key Games") + btn("prime", FILT.prime, "Primetime") +
        sortButton());
    }
    // COMBINED has a Team filter of its own (his call 2026-09-20); the
    // Network one stays out, three sports sharing no windows
    h += group("Team", select("team", "All Teams",
      [].concat.apply([], teamGroups.map((ids, i) => i ? lined(ids) : ids.map(optOf)))
        .concat(confOptions(visibleWithout("team"))),
      FILT.team));
    // THE NETWORK, in HIS order, which differs by sport (2026-09-14): the
    // broadcast networks he watches on, a bar, then the cable tier, then
    // whatever else carried a game, alphabetically. A group with nothing in
    // it brings no bar with it.
    const NET_GROUPS = {
      CFB: [["FOX", "CBS", "NBC"],
            ["ABC", "ESPN", "ESPN2", "FS1", "BTN", "Peacock"]],
      CBB: [["FOX", "CBS", "NBC", "ABC", "ESPN", "FS1", "BTN", "Peacock"]]
    };
    // ...and a network whose only games are postseason never reaches the
    // dropdown, since choosing it could only ever return nothing
    const seenNet = new Set();
    visibleWithout("net").forEach(g => {
      const n = primaryNet(g.nets);
      if (n && !g.stage) seenNet.add(n);
    });
    if (FILT.net) seenNet.add(FILT.net);
    const groups = NET_GROUPS[sport] || [];
    const namedNet = [].concat.apply([], groups);
    const restNet = Array.from(seenNet)
      .filter(n => namedNet.indexOf(n) < 0)
      .sort((x, y) => x.localeCompare(y, undefined, { sensitivity: "base" }));
    const netOpt = n => [n, n];
    let netOpts = [];
    groups.concat([restNet]).forEach(grp => {
      const have = grp.filter(n => seenNet.has(n));
      if (!have.length) return;
      if (netOpts.length) netOpts.push(["────────────", null]);
      netOpts = netOpts.concat(have.map(netOpt));
    });
    // MARQUEE and PRIMETIME sit under a bar of their own at the foot of the
    // list (his call 2026-09-25). Basketball takes Marquee alone -- a 7pm tip
    // is most of its schedule, so the question does not sort anything. Neither
    // appears where no game would come back.
    const extraNet = (sport === "CFB"
      ? [["Marquee", "mq:"], ["Primetime", "prime:"]]
      : sport === "CBB" ? [["Marquee", "mq:"]] : [])
      .filter(o => o[1] === FILT.net || visibleWithout("net")
        .some(o[1] === "mq:" ? (g => !!g.mq) : primetime));
    if (extraNet.length) {
      if (netOpts.length) netOpts.push(["─".repeat(12), null]);
      netOpts = netOpts.concat(extraNet);
    }
    // no Network filter where every game is a tournament game or TV is rare
    if (sport && sport !== "CHK" && VIEW !== "cornell")
      h += group("Network", select("net", "All Networks", netOpts, FILT.net));
    // HIGHLIGHTS (2026-09-16), offering only the kinds the other filters
    // leave any games for
    const hlBase = visibleWithout("hl");
    const hlOpts = (sport
      ? ["Special", "Tournament", "Memorable", "Attended", "Pregame", "Details"]
      : ["Special", "Postseason", "Memorable", "Attended", "Marquee", "Pregame", "Details"])
      .filter(k => k === FILT.hl || hlBase.some(g => highlightOf(g, k)))
      .map(k => [k, k]);
    // ...but not on Cornell basketball, nine games in all (his call 2026-09-17)
    if (!(VIEW === "cornell" && sport === "CBB"))
      h += group("Highlights", select("hl", "All Games", hlOpts, FILT.hl));
    // UNIFORMS, Michigan football and basketball (2026-09-18)
    if (VIEW === "michigan" && JERSEYS[sport]) {
      const jBase = visibleWithout("jersey");
      const jOpts = JERSEYS[sport].filter(k => k === FILT.jersey ||
        jBase.some(g => jerseyOf(g) === k)).map(k => [k, k]);
      h += group("Uniforms", select("jersey", "All Uniforms", jOpts, FILT.jersey));
    }
    // Cornell hockey has no 2021-Onward button (his call 2026-09-17), and
    // Cornell basketball has NCAA Tournament in its place
    const extra = VIEW !== "cornell"
      ? '<button class="f" data-act="post" aria-pressed="' + !!FILT.post +
        '">Postseason</button>' +
        '<button class="f" data-act="recent" aria-pressed="' + !!FILT.recent +
        '">2021-Onward</button>'
      : sport === "CBB"
        ? '<button class="f" data-act="post" aria-pressed="' + !!FILT.post +
          '">NCAA Tournament</button>'
        : "";
    // COMBINED: CURRENT opens this season across all three sports, in date
    // order (his call 2026-09-24), and sits between 2021-Onward and Hockey
    const curBtn = (!sport && teamView())
      ? '<button class="f" data-act="combcur" aria-pressed="' + !!FILT.combcur +
        '">Current</button>' : "";
    const hkyBtn = (!sport && teamView())
      ? '<button class="f" data-act="nohky" aria-pressed="' + !FILT.nohky +
        '">Hockey</button>' : "";
    return h + group("", extra + curBtn + hkyBtn + sortButton());
  }
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
    const wSeen = teamsIn(visibleWithout("winner"),
      g => g.teams.filter(t => t.win).map(t => t.id), FILT.winner);
    if (sport === "CHK") {
      // HOCKEY: Michigan and Cornell first, then everyone else (his call
      // 2026-09-18)
      const top = ["130", "172"].filter(id => wSeen.has(id));
      const others = Array.from(wSeen).filter(id => top.indexOf(id) < 0)
        .sort((a, b) => optOf(a)[0].localeCompare(optOf(b)[0]));
      h += group("Winner", select("winner", "All Winners",
        top.map(optOf).concat(top.length ? lined(others) : others.map(optOf)), FILT.winner));
    } else {
      const w = teamOrder(sport, wSeen, ["130"]);
      h += group("Winner", select("winner", "All Winners",
        w.bigTen.map(optOf).concat(lined(w.power), lined(w.rest)), FILT.winner));
    }
    // every hockey Rivals game is an NCAA Tournament game: no Postseason button
    return h + group("", (sport === "CHK" ? "" : postButton()) + sortButton());
  }
  /* Football is played in numbered weeks; basketball is not. The list follows
     the season, since week 16 only exists in some years.
     THE END OF THE SEASON IS NAMED, NOT NUMBERED (his call 2026-10-02): the
     conference finals, the bowls and the CFP gather under one "Postseason"
     option after the numbered weeks, which is how basketball's month list
     ends too. Both lists now come from the games this view can actually show,
     so a week it has nothing in is not offered. */
  // the games this VIEW can show in the chosen season, with the two cuts that
  // would otherwise hide whole weeks lifted: TV WINDOWS opens on Current,
  // which IS one week, and on Marquee
  const seasonBase = key => {
    const cur = FILT.current, mq = FILT.marquee;
    FILT.current = false; FILT.marquee = false;
    try { return visibleWithout(key); }
    finally { FILT.current = cur; FILT.marquee = mq; }
  };
  if (sport === "CFB") {
    const base = seasonBase("week");
    const weeks = new Set();
    let post = false;
    base.forEach(g => {
      // A CONFERENCE FINAL LEAVES ITS WEEK NUMBER BEHIND (his call
      // 2026-10-02): it belongs with the bowls and the CFP under one
      // POSTSEASON entry, whether or not ordinary games were played that same
      // week -- 2016 is the case that tests it, where Bedlam was played on
      // championship Saturday and has to keep Week 14 to itself. The two
      // began as separate "Conf Champ" and "Bowls" entries and he merged
      // them, so football's list now ends the way basketball's does.
      if (g.title || g.week == null) { post = true; return; }
      weeks.add(g.week);
    });
    if (typeof FILT.week === "number") weeks.add(FILT.week);
    h += group("Week", select("week", "All Weeks",
      Array.from(weeks).sort((a, b) => a - b).map(w => ["Week " + w, w])
        .concat(post || FILT.week === "postseason"
          ? [["Postseason", "postseason"]] : []),
      FILT.week));
  }
  /* BASKETBALL GETS WEEKS TOO, on TV WINDOWS (his call 2026-10-06), and they
     replace the month list there: November, December, Week 1 to 9 or 10, then
     Postseason. The weeks are the conference season -- see cbbWeekNo -- which
     is why the two months in front of them are named rather than numbered.
     Key Games keeps its months: its seasons run back to 2011-12 and it has no
     conference-play line to draw. */
  if (sport === "CBB" && VIEW === "tv") {
    const base = seasonBase("week");
    const weeks = new Set();
    let nov = false, dec = false, post = false;
    base.forEach(g => {
      if (g.stage) { post = true; return; }
      const m = +g.date.slice(5, 7);
      if (m === 11) { nov = true; return; }
      if (m === 12) { dec = true; return; }
      const w = cbbWeekNo(g);
      if (w != null) weeks.add(w);
    });
    if (typeof FILT.week === "number") weeks.add(FILT.week);
    h += group("Week", select("week", "All Weeks",
      (nov || FILT.week === "nov" ? [["November", "nov"]] : [])
        .concat(dec || FILT.week === "dec" ? [["December", "dec"]] : [])
        .concat(Array.from(weeks).sort((a, b) => a - b).map(w => ["Week " + w, w]))
        .concat(post || FILT.week === "postseason"
          ? [["Postseason", "postseason"]] : []),
      FILT.week));
  }
  // Basketball has no week worth showing, so the month is its equivalent
  // coarse cut. Like the week list it follows the SEASON.
  // THE CONFERENCE TOURNAMENTS AND THE NCAA TOURNAMENT LEAVE MARCH (his call
  // 2026-10-02): they gather under one "Postseason" option at the end, so
  // March means the regular-season March games and nothing else. April, whose
  // every game is a Final Four, disappears into it.
  if (sport === "CBB" && VIEW !== "tv") {
    const months = new Set();
    let post = false;
    seasonBase("month").forEach(g => {
      if (g.stage) { post = true; return; }
      months.add(+g.date.slice(5, 7));
    });
    if (typeof FILT.month === "number") months.add(FILT.month);
    h += group("Month", select("month", "All Months",
      Array.from(months).sort((a, b) => monthOrder(a) - monthOrder(b))
        .map(m => [MONTHS[m - 1], m])
        .concat(post || FILT.month === "postseason"
          ? [["Postseason", "postseason"]] : []),
      FILT.month));
  }
  // Each view drops the dropdown it has no use for (his call 2026-09-12):
  // TV WINDOWS is already a cut by window, so Game Type would cross two
  // unrelated axes; KEY GAMES is a cut by game type, so the TV window would.
  // The FILTER still exists -- only the control goes -- so clearFilters keeps
  // working and a value set on the other view is cleared on the way in.
  if (VIEW !== "tv")
    h += group("Game type", select("type", "All Game Types",
      order.types.filter(t => types.has(t)).map(t => [t, t])
        .concat(VIEW === "big" && visibleWithout("type").some(g => g.important)
          ? [["Important Results", "important"]] : []),
      FILT.type));
  if (VIEW !== "big") {
    // The dropdown holds ONE window; Marquee Windows sets three at once, and
    // while it is on the dropdown falls back to its "All" label.
    const one = (FILT.windows && FILT.windows.length === 1) ? FILT.windows[0] : "";
    // some windows are deliberately absent from the dropdown -- the games keep
    // the window and still show under "All TV Windows"
    const hidden = HIDDEN_WINDOWS[sport] || [];
    h += group("TV window", select("window", "All TV Windows",
      order.windows.filter(w => windows.has(w) && hidden.indexOf(w) < 0)
        .map(w => [w, w]), one));
  }
  // not "order": that name already holds the game-type / window sequence above
  // only teams that would return games under the other filters
  const teamList = teamOrder(sport, teamsIn(visibleWithout("team"),
    g => g.teams.map(t => t.id), FILT.team));
  const teamOpt = id => [(TEAMS[id] && TEAMS[id].short) || id, id];
  // a divider line opens each group after the Big Ten's (his call 2026-09-11)
  const withLine = ids => ids.length
    ? [["─".repeat(12), null]].concat(ids.map(teamOpt)) : [];
  h += group("Team", select("team", "All Teams",
    teamList.bigTen.map(teamOpt).concat(withLine(teamList.power), withLine(teamList.rest),
      confOptions(visibleWithout("team"))),
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
function teamOrder(sport, allowed, pinsOverride, leadConf, confSport) {
  // COMBINED passes no sport and asks for basketball's order (his call
  // 2026-09-20): every sport's opponents, filed by their basketball league
  const key = confSport || sport;
  const PINS = { CFB: ["130", "194", "127", "87"],   // Michigan, Ohio State, Michigan State, Notre Dame
                 CBB: ["130", "127", "194"] };       // Michigan, Michigan State, Ohio State
  const POWER = { CFB: ["1", "8", "4"],              // ACC, SEC, Big 12
                  CBB: ["2", "23", "8", "4"] };      // ACC, SEC, Big 12, Big East
  const latest = {};
  GAMES.forEach(g => {
    if (sport && g.sport !== sport) return;
    g.teams.forEach(t => {
      if (!latest[t.id] || g.date > latest[t.id].date)
        latest[t.id] = { date: g.date, conf: t.conf };
    });
  });
  const name = id => (TEAMS[id] && TEAMS[id].short) || id;
  const byName = (a, b) => name(a).localeCompare(name(b));
  const ok = id => !allowed || allowed.has(id);
  const pins = (pinsOverride || PINS[key] || []).filter(id => latest[id] && ok(id));
  const others = Object.keys(latest).filter(id => pins.indexOf(id) < 0 && ok(id));
  const confOf = id =>
    (TEAMS[id] && TEAMS[id].conf && TEAMS[id].conf[key]) || latest[id].conf;
  const inBigTen = id => confOf(id) === (leadConf || BIG_TEN[key]);
  const inPower = id => (POWER[key] || []).indexOf(confOf(id)) > -1;
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
/* A SEED shows instead of a ranking when ESPN's number IS the seed (the CFP
   and the NCAA Tournament) or when he has given one (seeds.csv, the Big Ten
   Tournament -- ESPN only carries the poll there). */
function seedOf(g, t) {
  if (t.seed != null) return t.seed;
  return playoffGame(g) && t.rank ? t.rank : null;
}
// Only the CFP and the NCAA Tournament drop the rank column: there ESPN's
// number IS the seed, so there is no ranking left to show. A conference
// tournament keeps both (his call 2026-09-11) -- his seed by the name, the poll
// ranking in the column.
function seedGame(g) {
  return playoffGame(g);
}

function confSeeded(g) {
  return !playoffGame(g) && g.teams.some(t => t.seed != null);
}
// A card showing the SEED ALONE, no ranking: the CFP and the NCAA Tournament,
// and hockey Rivals, which drops the USCHO ranking (his call 2026-09-18)
function seedOnly(g) {
  return !!g && (seedGame(g) || (VIEW === "rivals" && g.sport === "CHK"));
}
// ...where the poll rank moves AFTER the name on a seeded game -- but not in
// HOCKEY, whose tournament cards keep the ranking in its column beside the
// in-line seed (his call 2026-09-16)
function rankAfter(g) {
  return confSeeded(g) && g.sport !== "CHK";
}
// The Rivals Postseason button: the CFP and the NCAA Tournament, plus the Big
// Ten Tournament FINAL and the Big Ten Championship Game (his call 2026-09-16)
function rivalsPost(g) {
  const s = g.stage || "";
  return playoffGame(g) || s === "Big Ten Tournament | Championship" ||
    s.indexOf("Big Ten Championship") === 0;
}
function playoffGame(g) {
  const s = g.stage || "";
  // HOCKEY is left out (2026-09-16): its NCAA Tournament number is the USCHO
  // RANKING, not a seed, so it stays in the rank column like any other game
  return s.indexOf("CFP") === 0 ||
    (s.indexOf("NCAA Tournament") === 0 && g.sport !== "CHK");
}

// A RIVALS card FILLS with the winner's colour (his call 2026-09-17) for the
// losses that matter most: any loss to Michigan, any CFP loss, a Final Four or
// title-game loss, and an NCAA Tournament upset -- a single-digit seed beaten
// by a double-digit one. (Hockey Rivals, when built: Michigan wins plus Frozen
// Four and title-game losses.)
function rivalsFill(g) {
  if (upcoming(g)) return false;
  const loser = g.teams.find(t => !t.win && isRival(t));
  if (!loser) return false;
  const winner = g.teams.find(t => t.win);
  // Michigan or Cornell beating a rival always fills (his call 2026-09-18)
  if (winner && (winner.id === MICHIGAN || winner.id === CORNELL)) return true;
  const s = g.stage || "";
  if (g.sport === "CHK") return s === "NCAA Tournament | Frozen Four" ||
    s === "NCAA Tournament | Championship";
  if (s.indexOf("CFP") === 0) return true;
  // ...and losing a conference FINAL fills too (his call 2026-10-02): the
  // Big Ten Championship Game, and the Big Ten Tournament's final
  if (s === "Big Ten Championship" || s === "Big Ten Tournament | Championship") return true;
  if (s === "NCAA Tournament | Final Four" || s === "NCAA Tournament | Championship") return true;
  if (s.indexOf("NCAA Tournament") === 0 && winner) {
    const ls = seedOf(g, loser), ws = seedOf(g, winner);
    return ls != null && ws != null && ls < 10 && ws >= 10;
  }
  return false;
}

// Rivals cards drop the usual borders for one coloured by the EVENT (his call
// 2026-09-11). A regular-season game has none.
function rivalsBorder(g) {
  const s = g.stage || "";
  // HOCKEY: a Michigan win wears maize, a Cornell win Cornell red (his call
  // 2026-09-18)
  if (g.sport === "CHK" && !upcoming(g)) {
    const w = g.teams.find(t => t.win);
    if (w && w.id === MICHIGAN) return "#ffcb05";
    if (w && w.id === CORNELL) return "#b31b1b";
  }
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
  return (VIEW === "tv" ? '<button class="f" data-act="current" aria-pressed="' +
      !!FILT.current + '">Current</button>' : "") +
    // Marquee games are simply IN Key Games now, so the button goes (his
    // call 2026-09-20)
    (VIEW === "big" && SPORT_OF[TAB] === "CFB" ? ""
      : '<button class="f" data-act="marquee" aria-pressed="' +
        marqueeOn() + '">Marquee Windows</button>') +
    // UPSETS (his call 2026-09-20): the two upset categories, nothing else
    (VIEW === "big" && SPORT_OF[TAB] === "CFB"
      ? '<button class="f" data-act="upset" aria-pressed="' + !!FILT.upset +
        '">Upsets</button>' : "") +
    sortButton();
}

// Each top tab's second row: label, sport, view.
const NAV = {
  michigan: [["Football", "cfb", "michigan"], ["Basketball", "cbb", "michigan"],
             ["Hockey", "chk", "michigan"], ["Combined", "all", "michigan"]],
  cfb: [["TV Windows", "cfb", "tv"], ["Key Games", "cfb", "big"],
        ["Rivals", "cfb", "rivals"]],
  cbb: [["TV Windows", "cbb", "tv"], ["Key Games", "cbb", "big"],
        ["Rivals", "cbb", "rivals"], ["Cornell", "cbb", "cornell"]],
  hockey: [["Cornell", "chk", "cornell"], ["Rivals", "chk", "rivals"]],
  detroit: [["Tigers", "mlb", "tigers"], ["Lions", "nfl", "lions"],
            ["Red Wings", "nhl", "redwings"],
            ["Pistons", "nba", "pistons"], ["Cavaliers", "nba", "cavaliers"]]
};

function draw() {
  document.querySelectorAll("nav button").forEach(b =>
    b.setAttribute("aria-selected", String(b.dataset.top === TOP)));
  document.getElementById("viewbar").innerHTML = NAV[TOP].map(v =>
    '<button data-tab="' + v[1] + '" data-view="' + v[2] + '" aria-selected="' +
    (v[1] === TAB && v[2] === VIEW) + '">' + v[0] + "</button>").join("");
  document.getElementById("filters").innerHTML = filterChips();
  const list = visible();
  // the count gives way to the season line where there is one (2026-09-29)
  const line = FILT.season == null ? null
    : teamView() && SPORT_OF[TAB] ? seasonLine()
    : (VIEW === "tv" || VIEW === "big") && (SPORT_OF[TAB] === "CFB" || SPORT_OF[TAB] === "CBB")
      ? champLine() : null;
  document.getElementById("count").innerHTML =
    line || esc(list.length.toLocaleString() + " games");
  document.getElementById("list").innerHTML = list.length
    ? (teamView() ? michListHtml(list)
      : list.map(g => rowHtml(g, false)).join(""))
    : '<p class="empty">Nothing matches those filters.</p>';
  if (teamView()) trimMichChips();
  else trimStageHeads();
}

/* ---------- saving to GitHub -------------------------------------------- */
function toast(msg, bad) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.toggle("bad", !!bad);
  t.classList.add("on");
  setTimeout(() => t.classList.remove("on"), 3200);
}
/* ---------- wiring ------------------------------------------------------ */
function switchView(view) {
  const leaving = VIEW;
  VIEW = view;
  FILT.type = null;
  FILT.windows = null;
  FILT.marquee = VIEW === "tv";
  FILT.current = false; CURRENT_PREV = null;
  FILT.hl = null;
  if (VIEW === "rivals") {
    // his Rivals default (2026-09-11): every season, newest first, opened
    // on Ohio State in football and Michigan State in basketball
    FILT.season = null; FILT.week = null; FILT.month = null; FILT.team = null;
    FILT.net = null;
    // hockey, fourteen games in all, opens on every rival (2026-09-18)
    FILT.rival = SPORT_OF[TAB] === "CFB" ? "194" : SPORT_OF[TAB] === "CHK" ? null : "127";
    FILT.post = false; FILT.winner = null;
    // hockey Rivals always opens Newest First (his call 2026-09-18)
    SORT = SPORT_OF[TAB] === "CHK" ? "desc" : defaultSort();
  } else if (teamView()) {
    // the Michigan view opens on its newest season, in schedule order --
    // Cornell's basketball, nine tournament games in all, opens on every year
    FILT.season = ((VIEW === "cornell" && SPORT_OF[TAB] === "CBB") || seriesView())
      ? null : latestSeason();
    FILT.week = null; FILT.month = null;
    FILT.team = null; FILT.rival = null; FILT.post = false; FILT.winner = null;
    FILT.net = null;
    SORT = defaultSort();
  } else if (leaving === "rivals" || leaving === "michigan" || leaving === "cornell") {
    // leaving Rivals or Michigan puts back the season a normal view opens on
    FILT.season = latestSeason(); FILT.week = null; FILT.month = null;
    FILT.team = null; FILT.rival = null; FILT.post = false; FILT.winner = null;
    FILT.net = null;
    if (leaving === "michigan" || leaving === "cornell") SORT = defaultSort();
  }
  // TV WINDOWS OPENS ON CURRENT, oldest first (his call 2026-09-18); turning
  // Current off gives back the old opening -- the newest season, Marquee on
  if (VIEW === "tv") enterCurrent();
  // KEY GAMES OPENS ON THE LATEST COMPLETED WEEK, oldest first (his call
  // 2026-09-20) -- football by week number, basketball by nothing, it has none
  if (VIEW === "big" && SPORT_OF[TAB] === "CFB") {
    const done = GAMES.filter(g => g.sport === SPORT_OF[TAB] &&
      !upcoming(g) && keyShows(g));
    if (done.length) {
      FILT.season = Math.max.apply(null, done.map(g => g.season));
      // ...and the end of the season is one Postseason entry now
      // (2026-10-02), so "the latest week" is Postseason once the conference
      // finals have been played
      const rows = done.filter(g => g.season === FILT.season);
      const plain = rows.filter(g => g.week != null && !g.title);
      const postDate = rows.filter(g => g.title || g.week == null)
        .map(g => g.date).sort().pop();
      const plainDate = plain.map(g => g.date).sort().pop();
      FILT.week = (postDate && (!plainDate || postDate > plainDate)) ? "postseason"
        : plain.length ? Math.max.apply(null, plain.map(g => g.week)) : null;
    }
    FILT.marquee = false;
    SORT = "asc";
  }
}
function enterCurrent() {
  // (the state it gives back is Marquee's: this season, oldest first)
  CURRENT_PREV = { filt: Object.assign({}, FILT, { current: false }),
                   sort: FILT.marquee ? (SPORT_OF[TAB] === "CBB" ? "desc" : "asc") : SORT };
  // ...and CURRENT CARRIES THE SEASON (his call 2026-09-20): the Year filter
  // reads this season, the latest one with a game played
  const played = GAMES.filter(g => g.sport === SPORT_OF[TAB] && !g.rivals_only &&
    !upcoming(g)).map(g => g.season);
  FILT = { season: played.length ? Math.max.apply(null, played) : latestSeason(),
           week: null, month: null, type: null,
           windows: null, team: null, marquee: false, rival: null,
           post: false, winner: null, net: null, recent: false,
           current: true };
  SORT = "asc";
}
function go(tab, view) {
  if (tab !== TAB) {
    // Switching sport goes back to the TAB DEFAULT, not merely clean filters
    // (his call 2026-09-11): the latest season with games, the default sort.
    // CFB and CBB share no game types or windows, so a value left over from
    // the other sport would filter everything away.
    TAB = tab;
    VIEW = "michigan";
    SORT = defaultSort();
    clearFilters();
    FILT.current = false; CURRENT_PREV = null;
    // COMBINED opens on every season's Special games, newest first
    if (!SPORT_OF[TAB]) { FILT.season = null; FILT.hl = "Special"; SORT = "desc"; }
  }
  if (view !== VIEW) switchView(view);
  draw();
  window.scrollTo({ top: 0 });
}
async function init() {
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
  CONF_LABEL = r[0].conf_label || {};
  FINAL_RANK = r[0].final_rank || {};
  CONF_PLACE = r[0].conf_place || {};
  CHAMPS = r[0].champs || {};
  TEAM_CONF = r[0].team_conf || {};
  SEASON_NAMES = r[0].season_names || {};
  HIDDEN_WINDOWS = r[0].hidden_windows || {};
  NET_PRIORITY = r[0].net_priority || {};
  clearFilters();
  try {
    // cache-bust: Pages serves with max-age, and this file is the shared state
    const t = await fetch("tags.json?" + Date.now(), { cache: "no-store" });
    if (t.ok) TAGS = await t.json();
  } catch (e) { }

  draw();

  // THE TWO ROWS (2026-09-16). A top tab opens on its first view; a view button
  // may change the sport as well as the view (Michigan's Football/Basketball).
  document.querySelectorAll("nav button").forEach(b =>
    b.addEventListener("click", e => {
      TOP = e.currentTarget.dataset.top;
      const first = NAV[TOP][0];
      go(first[1], first[2]);
    }));
  document.getElementById("viewbar").addEventListener("click", e => {
    const b = e.target.closest("button[data-view]");
    if (b) go(b.dataset.tab, b.dataset.view);
  });

  /* SWIPING BETWEEN TABS ON A PHONE (his call 2026-09-27, narrowing the one
     he made on 2026-09-24). A horizontal drag across the cards walks the TOP
     row -- Michigan, CFB, CBB, HKY, Detroit -- and wraps at either end,
     landing on each tab's first view exactly as tapping the tab does. It used
     to walk every view of every tab instead, which made crossing Detroit five
     swipes wide; the second row is left to his fingers. A swipe must be
     clearly sideways (60px across, and more than twice the up-and-down) or an
     ordinary scroll would trigger it, and a drag that starts on a dropdown or
     a button is left alone. */
  const TOPS = Object.keys(NAV);
  function stepTab(dir) {
    const i = TOPS.indexOf(TOP);
    if (i < 0) return;
    TOP = TOPS[(i + dir + TOPS.length) % TOPS.length];
    const first = NAV[TOP][0];
    go(first[1], first[2]);
  }
  let tx = 0, ty = 0, tracking = false;
  document.addEventListener("touchstart", e => {
    if (e.touches.length !== 1 || e.target.closest("select,button,input,a")) {
      tracking = false;
      return;
    }
    tracking = true;
    tx = e.touches[0].clientX;
    ty = e.touches[0].clientY;
  }, { passive: true });
  document.addEventListener("touchend", e => {
    if (!tracking) return;
    tracking = false;
    const t = e.changedTouches[0];
    const dx = t.clientX - tx, dy = t.clientY - ty;
    if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 2) return;
    stepTab(dx < 0 ? 1 : -1);
    window.scrollTo(0, 0);
  }, { passive: true });
  document.getElementById("filters").addEventListener("click", e => {
    const b = e.target.closest("button.f[data-act]");
    if (!b) return;
    if (b.dataset.act === "current") {
      if (!FILT.current) {
        // everything else off, oldest first -- the week reads in order
        enterCurrent();
      } else {
        if (CURRENT_PREV) { FILT = CURRENT_PREV.filt; SORT = CURRENT_PREV.sort; }
        FILT.current = false;
        CURRENT_PREV = null;
      }
      draw();
      return;
    }
    if (b.dataset.act !== "sort") { FILT.current = false; CURRENT_PREV = null; }
    if (b.dataset.act === "marquee") {
      FILT.marquee = !FILT.marquee;
      // MARQUEE opens on the current season, oldest first (his call 2026-09-18)
      // -- the latest season with a game PLAYED, so basketball in September
      // opens on last season, not on next season's schedule
      if (FILT.marquee) {
        const played = GAMES.filter(g => g.sport === SPORT_OF[TAB] && !g.rivals_only &&
          !upcoming(g)).map(g => g.season);
        FILT.season = played.length ? Math.max.apply(null, played) : latestSeason();
        // ...basketball Newest First (his call 2026-09-18)
        SORT = SPORT_OF[TAB] === "CBB" ? "desc" : "asc";
      }
    } else if (b.dataset.act === "combcur") {
      FILT.combcur = !FILT.combcur;
      if (FILT.combcur) {
        // the newest season with a game PLAYED, in any of the three sports
        COMB_PREV = { hl: FILT.hl, season: FILT.season, nohky: FILT.nohky,
                      post: FILT.post, recent: FILT.recent, team: FILT.team, sort: SORT };
        const played = GAMES.filter(g => g.focus === focusId() && !upcoming(g))
          .map(g => g.season);
        FILT.season = played.length ? Math.max.apply(null, played) : latestSeason();
        FILT.hl = null; FILT.nohky = false; FILT.post = false; FILT.recent = false;
        FILT.team = null;
        SORT = "asc";
      } else if (COMB_PREV) {
        FILT.hl = COMB_PREV.hl; FILT.season = COMB_PREV.season;
        FILT.nohky = COMB_PREV.nohky; FILT.post = COMB_PREV.post;
        FILT.recent = COMB_PREV.recent; FILT.team = COMB_PREV.team;
        SORT = COMB_PREV.sort;
        COMB_PREV = null;
      }
    } else if (b.dataset.act === "nohky") {
      FILT.nohky = !FILT.nohky;
    } else if (b.dataset.act === "upset") {
      FILT.upset = !FILT.upset;
    } else if (b.dataset.act === "post") {
      FILT.post = !FILT.post;
    } else if (b.dataset.act === "recent") {
      FILT.recent = !FILT.recent;
    } else if (b.dataset.act === "prime") {
      FILT.prime = !FILT.prime;
    } else if (b.dataset.act === "key") {
      FILT.key = !FILT.key;
    } else if (b.dataset.act === "cup") {
      FILT.cup = !FILT.cup;
    } else if (b.dataset.act === "walk" || b.dataset.act === "extra" || b.dataset.act === "late" ||
               b.dataset.act === "nohit") {
      FILT[b.dataset.act] = !FILT[b.dataset.act];
    } else {
      SORT = SORT === "asc" ? "desc" : "asc";
    }
    draw();
  });
  document.getElementById("filters").addEventListener("change", e => {
    const k = e.target.dataset && e.target.dataset.kind;
    if (!k) return;
    const v = e.target.value;
    FILT.current = false; CURRENT_PREV = null;
    if (k === "window") FILT.windows = v === "" ? null : [v];
    // ...and a week or month can now be a NAME -- "postseason" --
    // so only a run of digits is read as a number (his call 2026-10-02)
    else FILT[k] = v === "" ? null
      : ((k === "season" || k === "week" || k === "month") && /^\d+$/.test(v)
         ? +v : v);
    // NOVEMBER AND DECEMBER SHOW EVERYTHING (his call 2026-10-06). Marquee is
    // a January-onward idea -- he keeps it that way deliberately, conference
    // play being the point of it -- so a December game can never be Marquee
    // and the bucket would otherwise open empty under the TV Windows default.
    if (k === "week" && (v === "nov" || v === "dec")) FILT.marquee = false;
    // a week or month chosen under one season may not exist in another
    if (k === "season") { FILT.week = null; FILT.month = null; }
    draw();
  });
  // Clear Filters wipes everything, including the opening defaults -- it is
  // the escape from "newest season + Marquee", not a reset to it.
  document.getElementById("clearbtn").addEventListener("click", () => {
    FILT = { season: null, week: null, month: null, type: null, windows: null,
             team: null, marquee: false, rival: null, post: false, winner: null,
             net: null, recent: false };
    draw();
    window.scrollTo({ top: 0 });
  });
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => { });
  }
}
init();
