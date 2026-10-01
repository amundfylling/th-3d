"""Before/after sheet for a figure refinement round: photo | BEFORE model | AFTER model, same feature crop,
same frozen camera and the same render lighting (assets/blender/render_closeups.py). Held-out views (never used
to guide the changes) are labelled in red.

    python3 scripts/closeup-before-after.py BEFORE_DIR OUT.png
BEFORE_DIR holds closeups-skater.png / closeups-goalie.png rendered from the previous molds with the SAME
validation/players/<kind>-fit.json and -heldout-fit.json cameras (row order and crop windows identical).
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
VAL = REPO / "validation" / "players"
TILE, ROW = 300, 334
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
before_dir, out = Path(sys.argv[1]), Path(sys.argv[2])


def order(kind):
    rows = []
    for tag, f in (("fitted", f"{kind}-fit.json"), ("HELD-OUT", f"{kind}-heldout-fit.json")):
        rows += [(v, tag) for v in json.loads((VAL / f).read_text())["views"]]
    return rows


# (kind, view, feature slot 0-3, label)
PICK = [
    ("skater", "skater-video-t13.25", 2, "skater gloves (front)"),
    ("skater", "skater-video-t14.50", 2, "skater gloves (front)"),
    ("skater", "skater-video-t13.25", 1, "skater arms/cuffs (front)"),
    ("skater", "skater-video-t03.00", 1, "skater arms/cuffs (profile)"),
    ("skater", "skater-video-t01.50", 2, "skater gloves (front-left)"),
    ("skater", "skater-video-t22.60", 1, "skater arms/cuffs (held)"),
    ("skater", "skater-video-t13.25", 0, "skater head/collar (front)"),
    ("skater", "skater-video-t03.00", 0, "skater helmet (profile)"),
    ("goalie", "goalie-photo-front", 0, "goalie mask (front)"),
    ("goalie", "goalie-photo-back", 0, "goalie mask skin (back)"),
    ("goalie", "goalie-photo-top", 0, "goalie mask skin (top)"),
    ("goalie", "goalie-video-t16.75", 0, "goalie mask (top, video)"),
    ("goalie", "goalie-photo-front", 1, "goalie pads (front)"),
    ("goalie", "goalie-video-t02.50", 1, "goalie pads (rotation video)"),
    ("goalie", "goalie-photo-front", 2, "goalie catcher (front)"),
    ("goalie", "goalie-video-t12.25", 2, "goalie catcher (front, video)"),
]
sheets = {}
for kind in ("skater", "goalie"):
    sheets[kind] = (Image.open(before_dir / f"closeups-{kind}.png").convert("RGB"), Image.open(VAL / f"closeups-{kind}.png").convert("RGB"))
cols = 2
W = cols * (3 * TILE + 20)
H = ((len(PICK) + cols - 1) // cols) * (TILE + 34)
sheet = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(sheet)
for i, (kind, view, slot, label) in enumerate(PICK):
    rows = order(kind)
    idx = [v for v, _ in rows].index(view)
    tag = rows[idx][1]
    y0 = idx * ROW + 32
    x0 = 2 * TILE + slot * 2 * TILE
    b, a = sheets[kind]
    photo = a.crop((x0, y0, x0 + TILE, y0 + TILE))
    before = b.crop((x0 + TILE, y0, x0 + 2 * TILE, y0 + TILE))
    after = a.crop((x0 + TILE, y0, x0 + 2 * TILE, y0 + TILE))
    X, Y = (i % cols) * (3 * TILE + 20), (i // cols) * (TILE + 34)
    for j, t in enumerate((photo, before, after)):
        sheet.paste(t, (X + j * TILE, Y + 30))
        d.text((X + j * TILE + 6, Y + 34), ("PHOTO", "BEFORE", "AFTER")[j], fill=(255, 255, 255), font=F, stroke_width=2, stroke_fill=(0, 0, 0))
    d.text((X + 4, Y + 6), f"{label} - {view.split('-', 1)[1]} [{tag}]", fill=(170, 0, 0) if tag == "HELD-OUT" else (0, 0, 0), font=F)
sheet.save(out)
print("wrote", out, sheet.size)
