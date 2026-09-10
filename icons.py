"""Candidate app icons, drawn by pixel maths and written as PNGs.

There is no image library on this machine (Smart App Control blocks numpy's
ARM64 wheels), so every shape here is a filled rectangle or a filled disc
resolved per pixel, then deflated into a PNG by hand -- the same approach
site.py uses for the live icon and logos.py uses to read one.

`python icons.py` writes output/icons/*.png plus a preview page showing each
option at 192px and at 44px, because the small size is where an icon fails.
"""
import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output", "icons")

BG = (0x16, 0x16, 0x1A)        # the app's ground
CARD = (0x1E, 0x1E, 0x23)
MAIZE = (0xFF, 0xCB, 0x05)     # Michigan, and the app's one loud colour
INK = (0xEC, 0xEC, 0xEA)
MUTED = (0x9A, 0x9A, 0x95)
LINE = (0x3A, 0x3A, 0x42)
ACCENT = (0xE0, 0x83, 0x4F)


def png_bytes(size, pixel):
    """pixel(x, y) -> (r, g, b), evaluated once per pixel."""
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            row += bytes(pixel(x, y))

        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def rect(x, y, x0, y0, x1, y1):
    return x0 <= x < x1 and y0 <= y < y1


def disc(x, y, cx, cy, r):
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


# --- the candidates ------------------------------------------------------
# Each takes a unit-scaled size and returns a pixel function. Everything is
# expressed as a FRACTION of the icon so it renders identically at any size,
# and every mark stays inside the maskable safe circle (r = 0.4 about centre).

def calendar_grid(s):
    """A calendar page: a header bar with two hanger tabs and a 3x3 grid of
    day cells, one of them maize -- the game you are looking for."""
    def px(x, y):
        u, v = x / s, y / s
        if rect(u, v, .18, .10, .28, .22) or rect(u, v, .62, .10, .72, .22):
            return MUTED                                   # hanger tabs
        if not rect(u, v, .12, .18, .88, .86):
            return BG
        if v < .34:
            return ACCENT                                  # header band
        cw, gap = .22, .025
        for r_ in range(3):
            for c in range(3):
                x0 = .155 + c * (cw + gap)
                y0 = .40 + r_ * (.145 + gap)
                if rect(u, v, x0, y0, x0 + cw, y0 + .145):
                    return MAIZE if (r_ == 1 and c == 1) else MUTED
        return CARD
    return px


def calendar_date(s):
    """A calendar page whose grid is replaced by one big maize date block --
    reads as a single day rather than a month."""
    def px(x, y):
        u, v = x / s, y / s
        if rect(u, v, .18, .10, .28, .22) or rect(u, v, .62, .10, .72, .22):
            return MUTED
        if not rect(u, v, .12, .18, .88, .86):
            return BG
        if v < .34:
            return ACCENT
        if rect(u, v, .22, .44, .78, .78):
            return MAIZE
        return CARD
    return px


def scoreboard(s):
    """Two stacked team rows, the winner's washed maize -- the app's own card,
    reduced to its essentials."""
    def px(x, y):
        u, v = x / s, y / s
        if not rect(u, v, .10, .20, .90, .80):
            return BG
        if rect(u, v, .14, .28, .86, .46):
            return MAIZE                                   # winner
        if rect(u, v, .14, .54, .86, .72):
            return LINE                                    # loser
        return CARD
    return px


def bracket(s):
    """A tournament bracket fork, maize on the advancing side."""
    def px(x, y):
        u, v = x / s, y / s
        t = .055
        if rect(u, v, .20, .26, .20 + t, .42) or rect(u, v, .20, .58, .20 + t, .74):
            return MUTED                                   # the two stems
        if rect(u, v, .20, .26, .46, .26 + t) or rect(u, v, .20, .74 - t, .46, .74):
            return MUTED                                   # the two arms
        if rect(u, v, .46 - t, .26, .46, .74):
            return MUTED                                   # the join
        if rect(u, v, .46, .50 - t / 2, .78, .50 + t / 2):
            return MAIZE                                   # the winner's line
        if disc(u, v, .80, .50, .075):
            return MAIZE
        return BG
    return px


def ticket(s):
    """A ticket stub with a torn notch, maize on a dark ground."""
    def px(x, y):
        u, v = x / s, y / s
        if disc(u, v, .50, .28, .075) or disc(u, v, .50, .72, .075):
            return BG                                      # the notches
        if not rect(u, v, .14, .28, .86, .72):
            return BG
        if u < .50:
            return MAIZE
        if rect(u, v, .58, .38, .80, .44) or rect(u, v, .58, .48, .80, .54) \
                or rect(u, v, .58, .58, .74, .64):
            return MUTED                                   # ruled lines
        return CARD
    return px


def clock_slot(s):
    """A clock face with a maize wedge -- the TV window, which is what the
    whole archive is organised around."""
    def px(x, y):
        u, v = x / s, y / s
        if not disc(u, v, .5, .5, .36):
            return BG
        if not disc(u, v, .5, .5, .30):
            return MUTED                                   # the rim
        if rect(u, v, .485, .22, .515, .52):
            return MAIZE                                   # hour hand
        if rect(u, v, .50, .485, .74, .515):
            return MAIZE                                   # minute hand
        return CARD
    return px


OPTIONS = [
    ("calendar-grid", calendar_grid,
     "Calendar page, 3x3 grid, one day picked out in maize."),
    ("calendar-date", calendar_date,
     "Calendar page reduced to a single date block."),
    ("scoreboard", scoreboard,
     "The app's own card: two team rows, winner washed maize."),
    ("bracket", bracket,
     "A bracket fork, maize on the advancing side."),
    ("ticket", ticket,
     "A ticket stub with torn notches."),
    ("clock-slot", clock_slot,
     "A clock face with maize hands -- the TV window."),
]


def build():
    os.makedirs(OUT, exist_ok=True)
    cards = []
    for name, fn, blurb in OPTIONS:
        for size in (192, 44):
            path = os.path.join(OUT, "%s-%d.png" % (name, size))
            open(path, "wb").write(png_bytes(size, fn(size)))
        cards.append(
            '<figure><div class="pair">'
            '<img src="%s-192.png" width="120" height="120" alt="">'
            '<img src="%s-44.png" width="44" height="44" alt="">'
            "</div><figcaption><b>%s</b><span>%s</span></figcaption></figure>"
            % (name, name, name, blurb))

    html = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Games History icon options</title>
<style>
body{margin:0;background:#16161a;color:#ececea;
  font-family:"Source Sans 3",system-ui,-apple-system,sans-serif;padding:26px}
h1{font-size:21px;margin:0 0 4px;color:#ececea}
p.sub{color:#9a9a95;margin:0 0 24px;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));
  gap:18px;max-width:1000px}
figure{margin:0;background:#1e1e23;border:1px solid #2b2b31;border-radius:10px;
  padding:16px}
.pair{display:flex;align-items:flex-end;gap:14px}
img{border-radius:22%%;display:block}
figcaption{margin-top:12px;display:flex;flex-direction:column;gap:3px}
figcaption b{color:#ececea;font-size:14px}
figcaption span{color:#9a9a95;font-size:12.5px;line-height:1.35}
</style></head><body>
<h1>Games History &mdash; icon options</h1>
<p class="sub">Each shown at 120px and at 44px. The small one is the test:
that is roughly how big it renders on a home screen and in a browser tab.</p>
<div class="grid">%s</div>
</body></html>""" % "".join(cards)
    path = os.path.join(OUT, "preview.html")
    open(path, "w", encoding="utf-8").write(html)
    print("%d options -> %s" % (len(OPTIONS), path))


if __name__ == "__main__":
    build()
