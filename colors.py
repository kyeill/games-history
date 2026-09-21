"""The row-wash colour for every team in the archive.

Started fresh for this project (Kyle's call 2026-09-09) rather than reading
sports-daily's `Colors` sheet tab, because a WASH and a STRIPE want different
answers -- standings/site.py records the same reasoning. Michigan is the clear
case: those projects use maize #ffcb05 for a stripe, but the wash wants the
navy, because a lightened maize is nearly the page's own ink.

Two sources of truth, in order:
  1. OVERRIDES below, for the handful ESPN gets wrong.
  2. ESPN's own `color`, except where it is a desaturated near-black -- nine
     schools return #000000, which every one of them would wash to the same
     grey, so those fall back to ESPN's `alternateColor`.

Regenerate colors.json with `python colors.py --write` after a harvest adds
teams.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")

# Only where ESPN is WRONG, not merely dark. Keep this list short: a rule that
# needs many exceptions is the wrong rule.
OVERRIDES = {
    "183": ("f76900", "Syracuse: ESPN returns navy #000e54; the school is orange"),
    "251": ("bf5700", "Texas: ESPN's #af5c37 is a muddy tan, not burnt orange"),
    # His call 2026-09-09, overruling the note above about washes wanting the
    # darker colour: a Michigan win should read MAIZE, not navy blue.
    "130": ("ffcb05", "Michigan: he wants the winning row yellow, not blue"),

    # YELLOW BELONGS TO MICHIGAN. Every other school whose wash came out yellow
    # is moved to its other colour (2026-09-09). Six of these are black-and-gold
    # schools, so they wash GREY and are not distinguishable from each other --
    # that is the honest trade for keeping maize unique.
    "2026": ("000000", "Appalachian State: black, not the gold"),
    "9": ("8c1d40", "Arizona State: maroon, not the gold"),
    "2116": ("000000", "Central Florida: black, not the gold"),
    "38": ("000000", "Colorado: black, not the gold"),
    "142": ("000000", "Missouri: black, not the gold"),
    "238": ("000000", "Vanderbilt: black, not the gold"),
    "277": ("002855", "West Virginia: navy, not the gold"),
    "2294": ("231f20", "Iowa: black, not the gold"),

    # More black-and-gold (and one navy-and-gold) schools, his list of
    # 2026-09-16. Black washes grey, the same trade as the six above.
    "119": ("000000", "Towson: black, not the gold"),
    "2029": ("000000", "Arkansas-Pine Bluff: black, not the gold"),
    "2670": ("000000", "VCU: black, not the gold"),
    "94": ("000000", "Northern Kentucky: black, not the gold"),
    "338": ("000000", "Kennesaw State: black, not the gold"),
    "2572": ("000000", "Southern Miss: black, not the gold"),
    "28": ("182b49", "UC San Diego: Triton navy, not the gold"),

    # NOTRE DAME IS NAVY everywhere but the Michigan view (his call
    # 2026-09-16), which keeps the antique gold #c99700 for its card wash --
    # that lives in app.js (MICH_WASH), not here. A border he marks "Opponent"
    # there takes this navy.
    "87": ("0c2340", "Notre Dame: navy; the Michigan view washes gold"),
    # his call 2026-09-16: ESPN's #061440 is so dark it washes grey
    "213": ("1e407c", "Penn State: Beaver Blue, bluer than ESPN's near-black navy"),

    # NO COLOUR FROM ESPN AT ALL -- a plain #000000 and no alternate, so these
    # washed the default grey. His colours, picked 2026-09-16 from each
    # school's own palette, never the gold.
    "2124": ("0033a0", "Chaminade: royal blue"),
    "2837": ("002d72", "East Texas A&M: blue"),
    "2222": ("ba0c2f", "Ferris State: crimson"),
    "2273": ("003087", "Hillsdale: blue"),
    "128": ("005a3c", "Northern Michigan: green"),
    "215": ("00653a", "Slippery Rock: green"),
    "284": ("3b2a7a", "Stonehill: purple"),
    "2627": ("4f2d7f", "Tarleton State: purple"),
    # hockey (2026-09-16): ESPN has no colour for Clarkson in any sport
    "2137": ("004f42", "Clarkson: green, not the gold"),
    # ...and these hockey schools ESPN gives only its #000000 placeholder, in
    # every sport. School colours, never the gold; the black-and-gold ones go
    # black, like the rest.
    "2779": ("a6192e", "St. Lawrence: scarlet"),
    "2392": ("000000", "Michigan Tech: black, not the gold"),
    "134": ("7a0019", "Minnesota Duluth: maroon"),
    "2385": ("00573f", "Mercyhurst: green"),
    "2022": ("000000", "American International: black, not the gold"),
    "2364": ("582c83", "Minnesota State: purple"),
    "2528": ("d6001c", "Rensselaer: cherry red"),
    "2594": ("c8102e", "St. Cloud State: red"),
    "2060": ("1b365d", "Bentley: navy"),
    "2815": ("000000", "Lindenwood: black, not the gold"),
    "285": ("003f87", "Lake Superior State: blue, not the gold"),
    "2008": ("0077c8", "Alabama Huntsville: blue"),
    "298": ("236192", "Alaska: blue, not the gold"),
    "2144": ("000000", "Colorado College: black, not the gold"),
    # ESPN offers Georgia Tech only old gold and WHITE, neither usable, so this
    # is the school's real navy rather than an ESPN value.
    "59": ("003057", "Georgia Tech: Tech navy; ESPN's only alternative is white"),
    # PRO TEAMS in their other colour (his calls 2026-09-21) -- each is ESPN's
    # own alternateColor for the team
    "mlb-5": ("e31937", "Guardians: red, not the navy"),
    "mlb-2": ("bd3039", "Red Sox: red, not the navy"),
    "mlb-18": ("eb6e1f", "Astros: orange, not the navy"),
    "nfl-14": ("ffd100", "Rams: yellow, not the blue"),
    "nfl-26": ("69be28", "Seahawks: green, not the navy"),
    "nfl-7": ("fc4c02", "Broncos: orange, not the navy"),
    "nba-11": ("ffd520", "Pacers: yellow, not the navy"),
    "nba-18": ("f58426", "Knicks: orange, not the blue"),
}

NEAR_BLACK = 36      # luminance below this reads as black on a light wash
FLAT = 26            # channel spread below this is a grey/black, not a hue


def _rgb(h):
    h = (h or "").lstrip("#")
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def luminance(rgb):
    r, g, b = rgb
    return .299 * r + .587 * g + .114 * b


def is_flat_dark(h):
    """True for a colour that is both dark and colourless -- pure black, or
    Iowa's #231f20. Navy (#00274c) is dark but has real hue, so it stays."""
    rgb = _rgb(h)
    if not rgb:
        return True
    return luminance(rgb) < NEAR_BLACK and (max(rgb) - min(rgb)) < FLAT


def wash_color(tid, team):
    """The hex (no #) this team's winning rows are washed with, plus why."""
    if tid in OVERRIDES:
        return OVERRIDES[tid][0], OVERRIDES[tid][1]
    primary = (team.get("color") or "").lstrip("#")
    if not is_flat_dark(primary):
        return primary, "ESPN primary"
    alt = (team.get("alt") or "").lstrip("#")
    if alt and not is_flat_dark(alt):
        return alt, "primary is a flat near-black; using ESPN alternate"
    return "6a6a70", "no usable colour from ESPN"


def build(verbose=True):
    data = json.load(open(os.path.join(OUT, "games.json"), encoding="utf-8"))
    teams = data["teams"]
    out, notes = {}, []
    for tid, t in teams.items():
        hexc, why = wash_color(tid, t)
        out[tid] = hexc
        if why != "ESPN primary":
            notes.append((t["short"], hexc, why))
    json.dump(out, open(os.path.join(OUT, "colors.json"), "w",
                        encoding="utf-8"), separators=(",", ":"), sort_keys=True)
    if verbose:
        print("%d teams -> output/colors.json" % len(out))
        print("%d not taken straight from ESPN's primary:" % len(notes))
        for name, hexc, why in sorted(notes):
            print("   %-22s #%s  %s" % (name, hexc, why))
    return out


if __name__ == "__main__":
    build(verbose="--quiet" not in sys.argv)
