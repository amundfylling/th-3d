"""Before/after sheet for a figure refinement round: photo | BEFORE model | AFTER model, same feature crop and
the same frozen camera (assets/blender/render_closeups.py). Tags: "fitted" and "inspected" views guided the
modelling (fitting references); INDEPENDENT fresh frames (red) were inspected only after the round's modelling.

    python3 scripts/closeup-before-after.py OUT.png "TITLE" skater=BEFORE.png,AFTER.png goalie=BEFORE.png,AFTER.png
Each AFTER sheet has a sidecar AFTER.json (rows: view, tag, feature names) written by render_closeups.py; the
BEFORE sheet must come from the same cameras and the same --views list (identical rows and feature windows).
Picks: PICK below (round 5: goalie blocker, lower pads; skater upper cuff).
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
FT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
# (kind, view, feature window, label)
PICK = [
    ("goalie", "goalie-photo-front", "blocker", "goalie blocker (front)"),
    ("goalie", "goalie-photo-front-oblique", "blocker", "goalie blocker (front-oblique)"),
    ("goalie", "goalie-video-t02.50", "blocker", "goalie blocker (front-right)"),
    ("goalie", "goalie-photo-side", "blocker", "goalie blocker (right side)"),
    ("goalie", "goalie-video-t12.25", "pads", "goalie pads + stick (front, low)"),
    ("goalie", "goalie-video-t00.50", "pads", "goalie lower pads (front)"),
    ("goalie", "goalie-video-t01.25", "blocker", "goalie blocker"),
    ("goalie", "goalie-video-t01.25", "pads", "goalie pads"),
    ("skater", "skater-video-t13.25", "arms/torso", "skater upper cuff (front)"),
    ("skater", "skater-video-t03.00", "arms/torso", "skater upper cuff (front-right)"),
    ("skater", "skater-video-t00.00", "arms/torso", "skater upper cuff (elevated)"),
    ("skater", "skater-video-t00.75", "arms/torso", "skater upper cuff"),
]


def main():
    out, title = Path(sys.argv[1]), sys.argv[2]
    sheets = {}
    for a in sys.argv[3:]:
        kind, files = a.split("=", 1)
        b, f = files.split(",")
        idx = json.loads(Path(f).with_suffix(".json").read_text())
        sheets[kind] = (Image.open(b).convert("RGB"), Image.open(f).convert("RGB"), idx)
    picks = [p for p in PICK if p[0] in sheets]
    T = next(iter(sheets.values()))[2]["tile"]
    R = next(iter(sheets.values()))[2]["row"]
    cols = 2
    W = cols * (3 * T + 20)
    H = 44 + ((len(picks) + cols - 1) // cols) * (T + 34)
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)
    d.text((8, 8), title, fill=(0, 0, 0), font=FT)
    n = 0
    for kind, view, feat, label in picks:
        b, a, idx = sheets[kind]
        rows = [r["view"] for r in idx["rows"]]
        if view not in rows:
            continue
        i = rows.index(view)
        r = idx["rows"][i]
        if feat not in r["features"]:
            continue
        slot = r["features"].index(feat)
        y0, x0 = i * R + 32, 2 * T + slot * 2 * T
        tiles = (a.crop((x0, y0, x0 + T, y0 + T)), b.crop((x0 + T, y0, x0 + 2 * T, y0 + T)), a.crop((x0 + T, y0, x0 + 2 * T, y0 + T)))
        X, Y = (n % cols) * (3 * T + 20), 44 + (n // cols) * (T + 34)
        for j, t in enumerate(tiles):
            sheet.paste(t, (X + j * T, Y + 30))
            d.rectangle((X + j * T, Y + 30, X + j * T + 150, Y + 56), fill=(40, 40, 40))
            d.text((X + j * T + 6, Y + 34), ("PHOTO", "BEFORE", "AFTER")[j], fill=(255, 255, 255), font=F)
        tag = r["tag"]
        d.text((X + 4, Y + 6), f"{label} - {view.split('-', 1)[1]} [{tag}]", fill=(170, 0, 0) if tag == "INDEPENDENT" else (0, 0, 0), font=F)
        n += 1
    sheet = sheet.crop((0, 0, W, 44 + ((n + cols - 1) // cols) * (T + 34)))
    sheet.save(out)
    print("wrote", out, sheet.size, n, "pairs")


main()
