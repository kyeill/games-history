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
