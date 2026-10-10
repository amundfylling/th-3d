"""Back-print lettering of the STIGA figures, traced from the user's photos (IMG_2566, IMG_2570: 'SVERIGE' / '30').

Numbers: collegiate BLOCK digits - uniform bars, chamfered convex corners, rectangular counters, short spurs on
the open ends of 3/5/6/9 - filled with the ink colour, then a thin gap of kit colour and a thin dark outline.
Name: plain medium sans capitals (Liberation Sans, Arial metrics), straight, about 0.27 x the digit height,
spaced so the name is about as wide as a two-digit number. Pure Python (shapely + Pillow): used by
build_figures.py and testable without Blender.

Proportions (digit height H = 1): width 0.69 (the '1' 0.44), bar 0.225, chamfer 0.095, digit gap 0.12, spur 0.21,
outline gap 0.022, outline 0.016; name cap height 0.27 H, gap name->number 0.23 H - read from the 30 on IMG_2566
(digit height ~285 px: '3' ~210 px wide, bars ~70 px, chamfers ~28 px, counter of '0' ~65 x 170 px).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

W, T, CH, GAP = 0.69, 0.225, 0.095, 0.12
OUT_GAP, OUT_W = 0.022, 0.016
NAME_FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"


def _bars(d: str):
    """Bars (x0, y0, x1, y1) of one block digit in a W x 1 cell (y up)."""
    w = 0.44 if d == "1" else W
    L, R = (0, T), (w - T, w)
    top, bot = (1 - T, 1), (0, T)
    mid = (0.5 - T / 2, 0.5 + T / 2)
    full, upper, lower = (0, 1), (0.5 - T / 2, 1), (0, 0.5 + T / 2)
    spur = 0.21
    B = {
        "0": [(*L[:1], 0, L[1], 1), (R[0], 0, R[1], 1), (0, top[0], w, 1), (0, 0, w, T)],
        "1": [(R[0], 0, R[1], 1), (0.04, 1 - T * 0.85, R[1], 1)],
        "2": [(0, top[0], w, 1), (R[0], upper[0], R[1], 1), (0, mid[0], w, mid[1]), (0, 0, T, mid[1]), (0, 0, w, T)],
        "3": [(0, top[0], w, 1), (R[0], 0, R[1], 1), (0.38 * w, mid[0], w, mid[1]), (0, 0, w, T), (0, 1 - spur, T, 1), (0, 0, T, spur)],
        "4": [(0, upper[0], T, 1), (0, mid[0], w, mid[1]), (R[0], 0, R[1], 1)],
        "5": [(0, top[0], w, 1), (0, upper[0], T, 1), (0, mid[0], w, mid[1]), (R[0], 0, R[1], mid[1]), (0, 0, w, T), (0, 0, T, spur)],
        "6": [(0, top[0], w, 1), (0, 0, T, 1), (0, 0, w, T), (R[0], 0, R[1], mid[1]), (0, mid[0], w, mid[1]), (R[0], 1 - spur, R[1], 1)],
        "7": [(0, top[0], w, 1), (R[0], 0, R[1], 1), (0, 1 - spur * 0.8, T, 1)],
        "8": [(0, 0, T, 1), (R[0], 0, R[1], 1), (0, top[0], w, 1), (0, 0, w, T), (0, mid[0], w, mid[1])],
        "9": [(0, top[0], w, 1), (0, upper[0], T, 1), (0, mid[0], w, mid[1]), (R[0], 0, R[1], 1), (0, 0, w, T), (0, 0, T, spur)],
    }[d]
    return B, w


def digit(d: str) -> tuple[Polygon | MultiPolygon, float]:
    bars, w = _bars(d)
    shape = unary_union([box(*b) for b in bars])
    # chamfer convex corners (outer and counter): erode, then grow back with bevelled joins
    shape = shape.buffer(-CH, join_style="mitre").buffer(CH, join_style="bevel", mitre_limit=2.0)
    return shape, w


def number_shape(num: str):
    """Ink shape and outline ring of a number, origin at the bottom-left, height 1."""
    x, ink, ring = 0.0, [], []
    for ch in num:
        s, w = digit(ch)
        from shapely.affinity import translate
        s = translate(s, x)
        ink.append(s)
        outer = s.buffer(OUT_GAP + OUT_W, join_style="mitre", mitre_limit=2.0)
        inner = s.buffer(OUT_GAP, join_style="mitre", mitre_limit=2.0)
        ring.append(outer.difference(inner))
        x += w + GAP
    return unary_union(ink), unary_union(ring), x - GAP


def _draw(d: ImageDraw.ImageDraw, geom, to_px, fill):
    for g in (geom.geoms if hasattr(geom, "geoms") else [geom]):
        if g.is_empty:
            continue
        d.polygon([to_px(p) for p in g.exterior.coords], fill=fill)
        for hole in g.interiors:
            d.polygon([to_px(p) for p in hole.coords], fill=(0, 0, 0, 0))


def print_image(name: str, number: str, ink, outline, size_units, digit_h, name_cap_h, name_y, number_y, px_per_unit=64) -> Image.Image:
    """RGBA print on a transparent sheet of size_units (w, h) mold units; name/number centred horizontally;
    name_y / number_y = top of the name / number measured from the sheet top (mold units)."""
    Wpx, Hpx = int(size_units[0] * px_per_unit), int(size_units[1] * px_per_unit)
    im = Image.new("RGBA", (Wpx, Hpx), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if number:
        ink_s, ring_s, width = number_shape(number)
        x0 = (size_units[0] - width * digit_h) / 2
        y_top = number_y
        to_px = lambda p: ((x0 + p[0] * digit_h) * px_per_unit, (y_top + (1 - p[1]) * digit_h) * px_per_unit)
        _draw(d, ring_s, to_px, (*outline, 255))
        _draw(d, ink_s, to_px, (*ink, 255))
    if name:
        cap_px = name_cap_h * px_per_unit
        font = ImageFont.truetype(NAME_FONT, int(cap_px / 0.716))  # Liberation Sans cap height = 0.716 em
        track = 0.10 * cap_px
        widths = [d.textlength(c, font=font) for c in name]
        total = sum(widths) + track * (len(name) - 1)
        x = (Wpx - total) / 2
        ybase = (name_y + name_cap_h) * px_per_unit
        for c, w in zip(name, widths):
            d.text((x, ybase), c, font=font, fill=(*ink, 255), anchor="ls")
            x += w + track
    return im


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[2] / "out" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    im = print_image("SVERIGE", "30", (24, 22, 20), (30, 26, 20), (16, 12), 7.0, 1.9, 1.0, 1.0 + 1.9 + 0.23 * 7.0)
    bg = Image.new("RGBA", im.size, (226, 166, 8, 255))
    Image.alpha_composite(bg, im).save(out / "print_test_30.png")
    im = print_image("SVERIGE", "0123456789", (24, 22, 20), (30, 26, 20), (66, 12), 7.0, 1.9, 1.0, 1.0 + 1.9 + 0.23 * 7.0)
    Image.alpha_composite(Image.new("RGBA", im.size, (226, 166, 8, 255)), im).save(out / "print_test_digits.png")
    print("ok")
