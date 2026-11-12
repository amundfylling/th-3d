"""Move pictures: each puck.no picture beside our redrawn one (docs/move-pictures.md).

    python3 scripts/move-pictures/compare.py   -> validation/move-pictures/comparison/page<N>.jpg (four moves a page)
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
VAL = REPO / "validation/move-pictures"
FONT = str(REPO / "public/fonts/BarlowCondensed-ExtraBold.ttf")
CELL_W, CELL_H, PAD, HEAD = 1180, 620, 16, 44


def pair(spec):
    a = Image.open(REPO / spec["puck_no_picture"]).convert("RGBA")
    a = Image.alpha_composite(Image.new("RGBA", a.size, (255, 255, 255, 255)), a).convert("RGB")
    b = Image.open(VAL / f"{spec['id']}.png").convert("RGB")
    h = CELL_H - HEAD
    h = min(h, int((CELL_W - 3 * PAD) / (a.width / a.height + b.width / b.height)))  # both whole, same height
    a = a.resize((round(a.width * h / a.height), h), Image.LANCZOS)
    b = b.resize((round(b.width * h / b.height), h), Image.LANCZOS)
    cell = Image.new("RGB", (CELL_W, CELL_H), (255, 255, 255))
    d = ImageDraw.Draw(cell)
    d.text((PAD, 4), f"{spec['name']}   (puck.no left, ours right)", font=ImageFont.truetype(FONT, 30), fill=(14, 42, 87))
    x = (CELL_W - a.width - b.width - PAD) // 2
    cell.paste(a, (x, HEAD))
    cell.paste(b, (x + a.width + PAD, HEAD))
    return cell


def main():
    specs = [json.loads(p.read_text()) for p in sorted((REPO / "data/move-pictures").glob("*.json")) if p.stem != "formation"]
    specs = [s for s in specs if "puck_no_picture" in s]
    out = VAL / "comparison"
    for old in out.glob("page*.jpg"):
        old.unlink()
    for n in range(0, len(specs), 4):
        sheet = Image.new("RGB", (2 * CELL_W, 2 * CELL_H), (255, 255, 255))
        for i, s in enumerate(specs[n:n + 4]):
            sheet.paste(pair(s), ((i % 2) * CELL_W, (i // 2) * CELL_H))
        sheet.save(out / f"page{n // 4 + 1:02d}.jpg", quality=88)
        print("wrote", (out / f"page{n // 4 + 1:02d}.jpg").relative_to(REPO), [s["id"] for s in specs[n:n + 4]])


if __name__ == "__main__":
    main()
