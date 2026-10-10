"""Compact review sheet from the matched close-up sheets: one row per feature, photo | model pairs from fitted
views, former held-out views now inspected while modelling ("inspected") and "regression ref" frames, independent checks in earlier rounds (labels
say which). Input: validation/players/closeups-{skater,goalie}.png (+ their
row labels re-derived from the fit files). Output: validation/players/closeups-summary.png

    python3 scripts/closeup-summary.py      (Pillow)
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
VAL = REPO / "validation" / "players"
TILE, ROW = 300, 334
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)


def rows(kind):
    out = []
    for tag, f in (("fitted", f"{kind}-fit.json"), ("inspected", f"{kind}-heldout-fit.json"), ("regression ref", f"{kind}-independent-fit.json")):
        if (VAL / f).exists():
            out += [(v, tag) for v in json.loads((VAL / f).read_text())["views"]]
    return out


# (kind, view, feature slot index 0-3, label)
PICK = [
    ("skater", "skater-video-t13.25", 0, "skater head/face (front)"), ("skater", "skater-video-t01.50", 0, "skater head (front-left)"),
    ("skater", "skater-video-t07.25", 0, "skater head (back)"), ("skater", "skater-video-t14.50", 1, "skater arms/torso"),
    ("skater", "skater-video-t22.60", 1, "skater arms/torso"), ("skater", "skater-video-t13.25", 2, "skater gloves"),
    ("skater", "skater-video-t07.25", 2, "skater back print 21"), ("skater", "skater-video-t08.50", 2, "skater back print 21"),
    ("goalie", "goalie-photo-front", 0, "goalie mask (front)"), ("goalie", "goalie-photo-back", 0, "goalie mask (back)"),
    ("goalie", "goalie-photo-top", 0, "goalie mask (top)"), ("goalie", "goalie-photo-side", 0, "goalie mask (side)"),
    ("goalie", "goalie-photo-front", 1, "goalie pads + blocker"), ("goalie", "goalie-photo-front-oblique", 2, "goalie gloves"),
    ("goalie", "goalie-photo-back", 1, "goalie back print 30"), ("goalie", "goalie-photo-lying-back", 1, "goalie back print 30"),
    ("goalie", "goalie-video-t02.50", 1, "goalie pads + measured blade"), ("goalie", "goalie-video-t10.00", 0, "goalie mask (rot. video)"),
]
sheets = {k: Image.open(VAL / f"closeups-{k}.png").convert("RGB") for k in ("skater", "goalie")}
order = {k: rows(k) for k in sheets}
cols = 4
W, H = cols * 2 * TILE, ((len(PICK) + cols - 1) // cols) * (TILE + 30)
out = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(out)
for i, (kind, view, slot, label) in enumerate(PICK):
    idx = [v for v, _ in order[kind]].index(view)
    tag = order[kind][idx][1]
    y0 = idx * ROW + 32
    x0 = 2 * TILE + slot * 2 * TILE
    pair = sheets[kind].crop((x0, y0, x0 + 2 * TILE, y0 + TILE))
    X, Y = (i % cols) * 2 * TILE, (i // cols) * (TILE + 30)
    out.paste(pair, (X, Y + 28))
    d.text((X + 6, Y + 5), f"{label} - {view.split('-', 1)[1]} [{tag}]", fill=(170, 0, 0) if tag == "regression ref" else (0, 0, 0), font=FONT)
out.save(VAL / "closeups-summary.png")
print("wrote", VAL / "closeups-summary.png", out.size)
