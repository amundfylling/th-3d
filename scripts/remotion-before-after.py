"""Before/after at the intended video framing: the Remotion static stills (iteration-19 cameras, 1920x1080),
same camera and lighting, cropped to the skaters and enlarged 2x (nearest) so the figures stay legible.

    python3 scripts/remotion-before-after.py BEFORE_OBLIQUE.png BEFORE_SIDE.png OUT.png
AFTER = validation/19/19-oblique.png and validation/19/19-side.png.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
pairs = [("oblique", sys.argv[1], (0.30, 0.30, 0.62, 0.62)), ("side", sys.argv[2], None)]
rows = []
for name, before, box in pairs:
    b = Image.open(before).convert("RGB")
    a = Image.open(REPO / "validation" / "19" / f"19-{name}.png").convert("RGB")
    W, H = a.size
    if box is None:  # full frame, halved
        tiles = [im.resize((W // 2, H // 2), Image.LANCZOS) for im in (b, a)]
    else:
        c = (int(W * box[0]), int(H * box[1]), int(W * box[2]), int(H * box[3]))
        tiles = [im.crop(c).resize(((c[2] - c[0]) * 3 // 2, (c[3] - c[1]) * 3 // 2), Image.LANCZOS) for im in (b, a)]
    row = Image.new("RGB", (tiles[0].width * 2 + 10, tiles[0].height + 30), "white")
    d = ImageDraw.Draw(row)
    for i, t in enumerate(tiles):
        row.paste(t, (i * (t.width + 10), 30))
        d.text((i * (t.width + 10) + 6, 4), f"{name} still - {('BEFORE', 'AFTER')[i]}", fill=(0, 0, 0), font=F)
    rows.append(row)
out = Image.new("RGB", (max(r.width for r in rows), sum(r.height + 10 for r in rows)), "white")
y = 0
for r in rows:
    out.paste(r, (0, y))
    y += r.height + 10
out.save(sys.argv[3])
print("wrote", sys.argv[3], out.size)
