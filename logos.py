"""Pick a readable crest for every team, and record the exceptions.

    python logos.py            report what would change
    python logos.py --write    write the result into config.json

ESPN's `-dark` crest is normally the right one on a dark page, but for some
clubs it is a flat white silhouette -- Liverpool and Tottenham are both pure
white, so they look identical at 20px. This measures the actual pixels of both
available 500px variants and picks per team:

  * the dark variant when it carries colour
  * otherwise the default variant, if it is light enough to read
  * otherwise the dark one anyway -- some crests read badly in both variants,
    and the cures for that are worse than the disease (see README)

The richer `primary_logo_on_black_color` variants are deliberately not used:
they are 4096px and around 170KB each, and the CDN ignores resize parameters.
"""

import argparse
import collections
import json
import os
import struct
import zlib

import requests

try:                      # only the bulk-discovery paths need it, and
    import espn           # this project takes its team list from harvest.py
except ImportError:
    espn = None
try:
    import sports_daily   # config loader; unused by read_png/measure/choose
except ImportError:
    sports_daily = None

HERE = os.path.dirname(os.path.abspath(__file__))
COLOURLESS = 0.15      # mean saturation below this reads as a silhouette
TOO_DARK = 60          # mean luminance below this disappears on #16161a
FLAT = 40              # channel spread below this is a black/grey crest

# Only these divisions can realistically reach the page, and ESPN's teams
# endpoint ignores ?groups=, so the ids come from the core API instead.
DIVISIONS = {
    "college-football": ("football", "college-football", ("80", "81")),
    "mens-college-basketball": ("basketball", "mens-college-basketball", ("50",)),
}

# Measuring ~1,700 teams means downloading and decoding a few thousand PNGs,
# which takes minutes. Crests almost never change, so the numbers are kept and
# a re-run costs nothing.
CACHE = os.path.join(HERE, "output", "logo-measurements.json")


def read_png(data):
    """Minimal 8-bit PNG reader -> (width, height, pixels, channels).

    Most ESPN crests are colour type 6 at depth 8; a few clubs are palette
    images (type 3), which are expanded to RGBA here so callers do not have to
    care. Anything else -- 4-bit palettes, GIFs served with a .png name --
    returns None rather than guessing.
    """
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, idat, width = 8, [], None
    palette = trns = None
    while pos < len(data):
        length, tag = struct.unpack(">I", data[pos:pos + 4])[0], data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if tag == b"IHDR":
            width, height, depth, ctype = struct.unpack(">IIBB", chunk[:10])
            if depth != 8 or ctype not in (2, 3, 6):
                return None
            channels = {6: 4, 3: 1}.get(ctype, 3)
        elif tag == b"PLTE":
            palette = chunk
        elif tag == b"tRNS":
            trns = chunk
        elif tag == b"IDAT":
            idat.append(chunk)
        elif tag == b"IEND":
            break
        pos += 12 + length
    if width is None:
        return None

    raw = zlib.decompress(b"".join(idat))
    stride = width * channels
    out, prev, at = [], bytearray(stride), 0
    for _ in range(height):
        filt = raw[at]; at += 1
        line = bytearray(raw[at:at + stride]); at += stride
        # Undo the per-scanline filter; this is the whole of PNG decoding.
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if filt == 1:   line[i] = (line[i] + a) & 0xFF
            elif filt == 2: line[i] = (line[i] + b) & 0xFF
            elif filt == 3: line[i] = (line[i] + (a + b) // 2) & 0xFF
            elif filt == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else
                                      b if pb <= pc else c)) & 0xFF
        out.append(bytes(line))
        prev = line

    if ctype == 3:
        if not palette:
            return None
        # Expand indices to RGBA so everything downstream sees one format.
        rgba = bytearray()
        for line in out:
            for index in line:
                at = index * 3
                rgba += palette[at:at + 3]
                rgba.append(trns[index] if trns and index < len(trns) else 255)
        return width, height, bytes(rgba), 4

    return width, height, b"".join(out), channels


_measured = {}
_rgb = {}


def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as fh:
            got = json.load(fh)
        _measured.update(got.get("measured") or got)
        _rgb.update(got.get("rgb") or {})
    except (OSError, ValueError):
        pass


def save_cache():
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as fh:
        json.dump({"measured": _measured, "rgb": _rgb}, fh)


def division_ids(key, season=2025):
    """Team ids in the divisions worth bothering with, or None for no filter.

    College football returns 759 teams, most of them Division II and III
    schools no rule here could ever surface. FBS and FCS are 277 of them.
    """
    spec = DIVISIONS.get(key)
    if not spec:
        return None
    sport, league, roots = spec
    ids = set()
    for root in roots:
        url = "%s/%s/leagues/%s/seasons/%s/types/2/groups/%s/teams" % (
            espn.CORE, sport, league, season, root)
        data = espn._get(url, {"limit": 500},
                         cache_key="division-%s-%s" % (league, root),
                         max_age_min=60 * 24 * 30)
        for item in (data or {}).get("items") or []:
            ref = item.get("$ref") or ""
            ids.add(ref.rsplit("/", 1)[-1].split("?")[0])
    return ids or None


def mean_rgb(url, session):
    """Average colour of the opaque pixels, or None.

    Separate from measure() so the saturation/luminance cache format did not
    have to change; only the handful of undecided crests need this.
    """
    if url in _rgb:
        got = _rgb[url]
        return tuple(got) if got else None
    got = _mean_rgb(url, session)
    _rgb[url] = got
    return got


def _mean_rgb(url, session):
    try:
        data = session.get(url, timeout=20).content
    except Exception:
        return None
    parsed = read_png(data)
    if not parsed:
        return None
    _, _, pixels, channels = parsed
    totals, count = [0, 0, 0], 0
    for i in range(0, len(pixels), channels * 7):
        if channels == 4 and pixels[i + 3] < 128:
            continue
        for c in range(3):
            totals[c] += pixels[i + c]
        count += 1
    return tuple(t / count for t in totals) if count else None


def measure(url, session):
    """(saturation, luminance) over the opaque pixels, or None."""
    if url in _measured:
        got = _measured[url]
        return tuple(got) if got else None
    got = _measure(url, session)
    _measured[url] = got
    return got


def _measure(url, session):
    try:
        data = session.get(url, timeout=20).content
    except Exception:
        return None
    parsed = read_png(data)
    if not parsed:
        return None
    _, _, pixels, channels = parsed
    sat = lum = 0.0
    count = 0
    for i in range(0, len(pixels), channels * 7):     # every 7th pixel is plenty
        if channels == 4 and pixels[i + 3] < 128:
            continue
        r, g, b = pixels[i], pixels[i + 1], pixels[i + 2]
        top, bottom = max(r, g, b), min(r, g, b)
        sat += (top - bottom) / top if top else 0
        lum += 0.2126 * r + 0.7152 * g + 0.0722 * b
        count += 1
    return (sat / count, lum / count) if count else None


def choose(dark_url, default_url, session):
    """-> (url, why)."""
    dark = measure(dark_url, session)
    if dark and dark[0] >= COLOURLESS:
        return dark_url, "dark variant has colour"
    plain = measure(default_url, session)
    if plain and plain[1] >= TOO_DARK:
        return default_url, "dark variant is a silhouette; default reads"
    # Neither variant clears the brightness test, but that test is blind to
    # hue: a crimson A or a purple note reads perfectly well on #16161a, while
    # a navy crest genuinely disappears into it. So the deciding question is
    # what colour the default variant actually is.
    rgb = mean_rgb(default_url, session)
    if rgb:
        r, g, b = rgb
        spread = max(rgb) - min(rgb)
        if spread < FLAT:
            return dark_url, "black or grey; stays white"
        # Blue-dominant is not the same as navy. Navy runs r < g < b (0c2340,
        # 132448); purple runs g < r < b (the Jazz note, Grand Canyon). Only
        # the first genuinely vanishes into the page.
        if b > r and b > g and g >= r:
            return dark_url, "navy; stays white"
        return default_url, "dark but coloured; default reads"
    return dark_url, "unreadable either way; left alone"


PREVIEW_CSS = """
body { background: #16161a; color: #ececea; margin: 0; padding: 28px;
  font: 15px/1.5 "Source Sans 3", -apple-system, "Segoe UI", sans-serif; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .08em;
  color: #9a9a95; margin: 30px 0 10px; }
p { color: #9a9a95; font-size: 13px; margin: 0 0 18px; }
ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); }
li { display: flex; align-items: center; gap: 8px; background: #1e1e23;
  border: 1px solid #2e2e35; border-radius: 8px; padding: 8px 10px; }
img { width: 20px; height: 20px; object-fit: contain; flex: 0 0 20px; }
img.was { opacity: .85; }
.arrow { color: #9a9a95; font-size: 12px; }
"""


def write_preview(overrides):
    """A page of just the exceptions, at the size they are actually seen.

    Every crest here is shown on the real page background: the point is to
    check by eye that the measurement picked something readable.
    """
    def row(name, before, after, cls=""):
        bits = ['<img class="was" src="%s" alt="">' % before] if before else []
        if before:
            bits.append('<span class="arrow">&rarr;</span>')
        bits.append('<img class="%s" src="%s" alt="">' % (cls, after))
        bits.append("<span>%s</span>" % name)
        return "<li>%s</li>" % "".join(bits)

    out = ['<!doctype html><meta charset="utf-8"><title>Crests</title>',
           '<style>%s</style>' % PREVIEW_CSS,
           "<h1>Crest exceptions</h1>",
           "<p>Shown at 20px on the real page background.</p>",
           "<h2>Default variant used instead (%d)</h2><ul>" % len(overrides)]
    for name, url in sorted(overrides.items()):
        out.append(row(name, url.replace("/500/", "/500-dark/"), url))
    out.append("</ul>")

    path = os.path.join(HERE, "output", "logos.html")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("  preview written to %s" % path)


DARK_OF = {}


def crest_urls(config, keys=None):
    """name -> dark crest URL, from the cached team lists.

    Only the JSON is needed here, not the images, so this is instant on a warm
    cache and lets --from-config draw a preview without measuring anything.
    """
    found = {}
    for league in config.get("leagues", []):
        if keys and league["key"] not in keys:
            continue
        data = espn._get("%s/%s/teams" % (espn.SITE, league["path"]), {"limit": 1000},
                         cache_key="teams-%s" % league["key"], max_age_min=60 * 24 * 7)
        try:
            entries = data["sports"][0]["leagues"][0]["teams"]
        except (KeyError, IndexError, TypeError):
            continue
        for entry in entries:
            team = entry.get("team") or {}
            for logo in team.get("logos") or []:
                rel = set(logo.get("rel") or [])
                if "dark" in rel and team.get("displayName") not in found:
                    found[team["displayName"]] = logo.get("href")
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description="Choose readable crests")
    ap.add_argument("--write", action="store_true", help="save into config.json")
    ap.add_argument("--league", action="append", help="limit to a league key")
    ap.add_argument("--preview", action="store_true",
                    help="write output/logos.html showing the exceptions")
    ap.add_argument("--from-config", action="store_true",
                    help="preview what config.json already holds, without measuring")
    args = ap.parse_args(argv)

    config = sports_daily.load_config()
    if args.from_config:
        DARK_OF.update(crest_urls(config, set(args.league) if args.league else None))
        write_preview(config.get("logo_overrides") or {})
        return 0
    load_cache()
    session = requests.Session()
    session.headers.update({"Accept": "image/png"})

    overrides = {}
    counts = collections.Counter()
    for league in config.get("leagues", []):
        if args.league and league["key"] not in args.league:
            continue
        data = espn._get("%s/%s/teams" % (espn.SITE, league["path"]), {"limit": 1000},
                         cache_key="teams-%s" % league["key"], max_age_min=60 * 24 * 7)
        try:
            entries = data["sports"][0]["leagues"][0]["teams"]
        except (KeyError, IndexError, TypeError):
            continue
        keep = division_ids(league["key"])
        for entry in entries:
            team = entry.get("team") or {}
            if keep is not None and str(team.get("id")) not in keep:
                continue
            name = team.get("displayName")
            logos = {tuple(sorted(set(l.get("rel") or []) - {"full"})): l.get("href")
                     for l in team.get("logos") or []}
            dark = logos.get(("dark",))
            plain = logos.get(("default",))
            if not name or not dark or not plain or name in overrides:
                continue
            DARK_OF[name] = dark
            url, why = choose(dark, plain, session)
            counts[why] += 1
            if url != dark:
                overrides[name] = url
            if url != dark:
                print("  %-34s %s" % (name, why))

    save_cache()
    print()
    for why, n in counts.most_common():
        print("  %4d  %s" % (n, why))
    print("  overrides: %d" % len(overrides))

    if args.preview:
        write_preview(overrides)

    if args.write:
        config_path = os.path.join(HERE, "config.json")
        with open(config_path, encoding="utf-8-sig") as fh:
            live = json.load(fh)
        live["logo_overrides"] = overrides
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(live, fh, indent=2)
        print("  written to config.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
