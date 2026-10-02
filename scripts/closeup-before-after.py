"""Before/after sheet for a figure refinement round: photo | BEFORE model | AFTER model, same feature crop and
the same frozen camera (assets/blender/render_closeups.py). Tags: "fitted" and "inspected" views guided the
modelling (fitting references); INDEPENDENT fresh frames (red) were inspected only after the round's modelling.

    python3 scripts/closeup-before-after.py OUT.png "TITLE" skater=BEFORE.png,AFTER.png goalie=BEFORE.png,AFTER.png
    python3 scripts/closeup-before-after.py OUT.png "TITLE" --labels=R6,R7,R8 skater=R6.png,R7.png,R8.png   (N versions)
Each AFTER sheet has a sidecar AFTER.json (rows: view, tag, feature names) written by render_closeups.py; the
BEFORE sheet must come from the same cameras and the same --views list (identical rows and feature windows).
Picks: PICK below (round 7: skater collar, neck and helmet).
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
FT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
# (kind, view, feature window, label)
PICK = [
    ("skater", "skater-video-t13.25", "head", "collar V + helmet (front)"),
    ("skater", "skater-video-t04.50", "head", "helmet + collar (right profile)"),
    ("skater", "skater-video-t07.25", "head", "neck strip + collar (back)"),
    ("skater", "skater-video-t08.50", "head", "collar on the left shoulder (back-left)"),
    ("skater", "skater-video-t06.00", "head", "neck + collar (back-right)"),
    ("skater", "skater-video-t00.00", "head", "helmet (elevated front)"),
    ("skater", "skater-video-t10.75", "head", "helmet (elevated front-right)"),
    ("skater", "skater-video-t03.00", "head", "helmet + collar (front-right)"),
    ("skater", "skater-video-t01.10", "head", "helmet + collar"),
    ("skater", "skater-video-t06.40", "head", "neck + collar (back-right)"),
    ("skater", "skater-video-t08.80", "head", "collar + helmet (left-back)"),
    ("skater", "skater-video-t14.50", "head", "collar V (front)"),
]


def main():
    out, title = Path(sys.argv[1]), sys.argv[2]
    labels = ["BEFORE", "AFTER"]
    sheets = {}
    for a in sys.argv[3:]:
        if a.startswith("--labels="):
            labels = a.split("=", 1)[1].split(",")
            continue
        kind, files = a.split("=", 1)
        fs = files.split(",")
        idx = json.loads(Path(fs[-1]).with_suffix(".json").read_text())  # all versions share rows and windows
        sheets[kind] = ([Image.open(x).convert("RGB") for x in fs], idx)
    picks = [p for p in PICK if p[0] in sheets]
    T = next(iter(sheets.values()))[1]["tile"]
    R = next(iter(sheets.values()))[1]["row"]
    nv = len(next(iter(sheets.values()))[0])
    cols = 2 if nv <= 2 else 1
    W = cols * ((nv + 1) * T + 20)
    H = 44 + ((len(picks) + cols - 1) // cols) * (T + 34)
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)
    d.text((8, 8), title, fill=(0, 0, 0), font=FT)
    n = 0
    for kind, view, feat, label in picks:
        ims, idx = sheets[kind]
        rows = [r["view"] for r in idx["rows"]]
        if view not in rows:
            continue
        i = rows.index(view)
        r = idx["rows"][i]
        if feat not in r["features"]:
            continue
        slot = r["features"].index(feat)
        y0, x0 = i * R + 32, 2 * T + slot * 2 * T
        tiles = [ims[-1].crop((x0, y0, x0 + T, y0 + T))] + [im.crop((x0 + T, y0, x0 + 2 * T, y0 + T)) for im in ims]
        X, Y = (n % cols) * ((nv + 1) * T + 20), 44 + (n // cols) * (T + 34)
        for j, t in enumerate(tiles):
            sheet.paste(t, (X + j * T, Y + 30))
            d.rectangle((X + j * T, Y + 30, X + j * T + 150, Y + 56), fill=(40, 40, 40))
            d.text((X + j * T + 6, Y + 34), (["PHOTO"] + labels)[j], fill=(255, 255, 255), font=F)
        tag = r["tag"]
        d.text((X + 4, Y + 6), f"{label} - {view.split('-', 1)[1]} [{tag}]", fill=(170, 0, 0) if tag == "INDEPENDENT" else (0, 0, 0), font=F)
        n += 1
    sheet = sheet.crop((0, 0, W, 44 + ((n + cols - 1) // cols) * (T + 34)))
    sheet.save(out)
    print("wrote", out, sheet.size, n, "pairs")


main()
