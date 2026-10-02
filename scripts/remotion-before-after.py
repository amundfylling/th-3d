"""Before/after at the intended video framing: the Remotion static stills (iteration-19 cameras, 1920x1080),
same camera and lighting, cropped to the skaters and enlarged 2x (nearest) so the figures stay legible.

    python3 scripts/remotion-before-after.py BEFORE_OBLIQUE.png BEFORE_SIDE.png OUT.png
    python3 scripts/remotion-before-after.py R6_OBL.png,R7_OBL.png R6_SIDE.png,R7_SIDE.png OUT.png R6,R7,R8
The last version (AFTER) = validation/19/19-oblique.png and validation/19/19-side.png.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
pairs = [("oblique", sys.argv[1].split(","), (0.30, 0.30, 0.62, 0.62)), ("side", sys.argv[2].split(","), None)]
LAB = sys.argv[4].split(",") if len(sys.argv) > 4 else ["BEFORE", "AFTER"]
rows = []
for name, before, box in pairs:
    srcs = [Image.open(x).convert("RGB") for x in before] + [Image.open(REPO / "validation" / "19" / f"19-{name}.png").convert("RGB")]
    W, H = srcs[-1].size
    k = 2 if len(srcs) <= 2 else 3
    if box is None:  # full frame, reduced
        tiles = [im.resize((W // k, H // k), Image.LANCZOS) for im in srcs]
    else:
        c = (int(W * box[0]), int(H * box[1]), int(W * box[2]), int(H * box[3]))
        f = 1.5 if len(srcs) <= 2 else 1.0
        tiles = [im.crop(c).resize((int((c[2] - c[0]) * f), int((c[3] - c[1]) * f)), Image.LANCZOS) for im in srcs]
    row = Image.new("RGB", ((tiles[0].width + 10) * len(tiles), tiles[0].height + 30), "white")
    d = ImageDraw.Draw(row)
    for i, t in enumerate(tiles):
        row.paste(t, (i * (t.width + 10), 30))
        d.text((i * (t.width + 10) + 6, 4), f"{name} still - {LAB[i]}", fill=(0, 0, 0), font=F)
    rows.append(row)
out = Image.new("RGB", (max(r.width for r in rows), sum(r.height + 10 for r in rows)), "white")
y = 0
for r in rows:
    out.paste(r, (0, y))
    y += r.height + 10
out.save(sys.argv[3])
print("wrote", sys.argv[3], out.size)
