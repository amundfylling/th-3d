"""Iteration 24: review sheet of the presentation stills (validation/24-comparison.png) from
validation/24-render-checks.json and out/24/f*-overlay.png.

    python3 scripts/shot24-sheet.py
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
R = json.loads((REPO / "validation/24-render-checks.json").read_text())
FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
FS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
TW, TH, LAB = 960, 540, 34
st = {s["frame"]: s for s in R["review_stills"]}
order = [70, 123, R["contact_pause"]["frames"][1], 190]
names = {70: "normal speed", 123: "replay 1/4 speed (same source time as the left)", order[2]: "paused at the key contact", 190: "replay after the contact"}
head = 96
sheet = Image.new("RGB", (2 * TW, head + 2 * (TH + LAB)), "white")
d = ImageDraw.Draw(sheet)
nv = R["normal_vs_replay"]
d.text((10, 8), f"24 - '{R['presentation_id']}' ({R['camera']} benchmark camera, {R['frames']} frames at {R['fps']} fps): normal pass, 1/4-speed replay, pause at the key contact",
       fill=(0, 0, 0), font=FB)
d.text((10, 40), f"Normal vs replay at the same source time ({len(nv['rows'])} pairs, overlays off): identical state and PNG bytes = {nv['pass']}. "
                 f"Contact pause ({len(R['contact_pause']['frames'])} frames): identical = {R['contact_pause']['pass']}.", fill=(0, 0, 0), font=FS)
clip = R.get("draft_clip", {})
d.text((10, 64), f"Draft clip: {clip.get('frames', '-')} frames, frames differing from the pure evaluation: {clip.get('frames_differing_from_pure', '-')}. AI review.",
       fill=(0, 0, 0), font=FS)
for i, f in enumerate(order):
    s = st[f]
    im = Image.open(REPO / s["png"]).convert("RGB").resize((TW, TH), Image.LANCZOS)
    x, y = (i % 2) * TW, head + (i // 2) * (TH + LAB)
    sheet.paste(im, (x, y + LAB))
    d.text((x + 8, y + 6), f"frame {f} - {names[f]}: source t = {s['t']:.4f} s ({s['segment']})", fill=(160, 0, 0), font=FS)
sheet.save(REPO / "validation/24-comparison.png")
print("wrote validation/24-comparison.png")
