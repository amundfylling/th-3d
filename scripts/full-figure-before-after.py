"""Full-figure before/after sheet at the photo framing: photo | BEFORE | AFTER per view, for neutral clay and final
materials (renders from assets/blender/render_closeups.py at the frozen fitted cameras; per-view renders are the
transparent RGBA frames it writes to out/figures/closeups/<kind>_<view>.png, copied per run).

    python3 scripts/full-figure-before-after.py OUT.png "TITLE" BEFORE_DIR AFTER_DIR VIEW[,VIEW...] [INDEPENDENT_VIEWS]
BEFORE_DIR/AFTER_DIR hold full_neutral/ and full_mat/ with skater_<view>.png. Rows: views; columns: photo, clay
before, clay after, materials before, materials after. Independent views (comma list) are labelled in red.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
MAN = json.loads((REPO / "references" / "derived" / "players" / "manifest.json").read_text())["items"]
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
FT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
out, title, bdir, adir, views = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5].split(",")
indep = set(sys.argv[6].split(",")) if len(sys.argv) > 6 else set()
TH = 330
BG = (38, 36, 34)


def tile(path):
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, BG + (255,))
    bg.alpha_composite(im)
    return bg.convert("RGB")


rows = []
for v in views:
    ph = Image.open(REPO / MAN[v]["file"]).convert("RGB")
    ims = [ph] + [tile(d / sub / f"skater_{v}.png") for sub in ("full_neutral", "full_mat") for d in (bdir, adir)]
    ims = [im.resize((round(im.width * TH / im.height), TH), Image.LANCZOS) for im in ims]
    rows.append((v, ims))
W = max(sum(im.width for im in ims) + 4 * 6 for _, ims in rows)
sheet = Image.new("RGB", (W, 40 + len(rows) * (TH + 28)), "white")
d = ImageDraw.Draw(sheet)
d.text((8, 8), title, fill=(0, 0, 0), font=FT)
for r, (v, ims) in enumerate(rows):
    y = 40 + r * (TH + 28)
    d.text((6, y + 4), v + ("  [INDEPENDENT]" if v in indep else ""), fill=(170, 0, 0) if v in indep else (0, 0, 0), font=F)
    x = 0
    for j, im in enumerate(ims):
        sheet.paste(im, (x, y + 24))
        d.rectangle((x, y + 24, x + 150, y + 46), fill=(40, 40, 40))
        d.text((x + 5, y + 26), ("PHOTO", "CLAY BEFORE", "CLAY AFTER", "MAT. BEFORE", "MAT. AFTER")[j], fill=(255, 255, 255), font=F)
        x += im.width + 6
sheet.save(out)
print("wrote", out, sheet.size)
