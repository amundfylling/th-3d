"""Iteration 23: labelled sheet of the Remotion diagnostic stills at the contact times (labels are review notes on
the sheet, not part of the composition). Reads validation/23-render-checks.json and out/23/diag-*.png.

    python3 scripts/shot23-sheet.py   ->  validation/23-diagnostics.png
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
R = json.loads((REPO / "validation/23-render-checks.json").read_text())
FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
FS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
TW, TH = 960, 540
tiles = []
for d in R["diagnostic_stills"]:
    im = Image.open(REPO / d["png"]).convert("RGB").resize((TW, TH), Image.LANCZOS)
    tile = Image.new("RGB", (TW, TH + 62), "white")
    tile.paste(im, (0, 62))
    dr = ImageDraw.Draw(tile)
    dr.text((8, 4), f"{d['event']}: t = {d['t_rendered']:.4f} s (trace {d['t_event']:.4f} s)", fill=(160, 0, 0), font=FB)
    st = d["state"]
    dr.text((8, 34), f"puck ({st['puck'][0]:.1f}, {st['puck'][1]:.1f}) mm, phase {st['phase']}; W-C arc {st['figures']['W-C'][0]:.1f} mm, "
                     f"heading {st['figures']['W-C'][4]:.1f} deg; render vs pure diff {d['max_diff_vs_pure']}", fill=(0, 0, 0), font=FS)
    tiles.append(tile)
oi = R["order_independence"]
clip = R.get("proof_clip", {})
head = 92
rows = (len(tiles) + 1) // 2
sheet = Image.new("RGB", (2 * TW, head + rows * (TH + 62)), "white")
dr = ImageDraw.Draw(sheet)
dr.text((10, 8), f"23 - Remotion playback, ACCEPTED trace '{R['trace_id']}', fixed overhead camera: W-RW foot drag-back and contact times",
        fill=(0, 0, 0), font=FB)
dr.text((10, 40), f"Shuffled/repeated frames ({len(oi['frames'])} frames x 2 orders): identical state and PNG bytes = {oi['pass']}. "
                  f"Proof clip: {clip.get('frames', '-')} frames, max diff vs pure evaluation {clip.get('max_diff_vs_pure', '-')}.", fill=(0, 0, 0), font=FS)
dr.text((10, 64), "Puck = black disk; trace figures W-C, W-RW, E-G, E-RD, E-LD posed from the trace; other figures in the static assembly pose. AI review.",
        fill=(0, 0, 0), font=FS)
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % 2) * TW, head + (i // 2) * (TH + 62)))
sheet.save(REPO / "validation/23-diagnostics.png")
print("wrote validation/23-diagnostics.png")
