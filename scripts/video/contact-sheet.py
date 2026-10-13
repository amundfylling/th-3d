"""Contact sheet of review stills: python3 scripts/video/contact-sheet.py <index.json> <out.jpg> (needs Pillow)."""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

idx = json.loads(Path(sys.argv[1]).read_text())
stills = idx["stills"]
ims = [Image.open(s["file"]).convert("RGB") for s in stills]
w = 480
h = round(w * ims[0].height / ims[0].width)
cols = 4
rows = (len(ims) + cols - 1) // cols
cap = 46
sheet = Image.new("RGB", (cols * w, 40 + rows * (h + cap)), "white")
d = ImageDraw.Draw(sheet)
try:
    fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
except OSError:
    fb = fs = ImageFont.load_default()
d.text((8, 10), f"{idx['target']} - {len(ims)} review stills ({idx['mode']}, scale {idx['scale']}, {'auto' if idx['auto'] else 'requested'})", fill="black", font=fb)
for i, (s, im) in enumerate(zip(stills, ims)):
    x, y = (i % cols) * w, 40 + (i // cols) * (h + cap)
    sheet.paste(im.resize((w, h)), (x, y))
    d.text((x + 4, y + h + 2), f"f{s['frame']}  t={s.get('t', '')}  {s.get('segment', '')}", fill="black", font=fb)
    d.text((x + 4, y + h + 22), "; ".join(s["reasons"])[:78], fill=(60, 60, 60), font=fs)
sheet.save(sys.argv[2], quality=88)
print(sys.argv[2])
