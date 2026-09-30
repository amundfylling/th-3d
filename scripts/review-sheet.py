"""Iteration 20: one static review sheet (validation/20-review-sheet.png).

    python3 scripts/review-sheet.py        (needs Pillow + numpy)
Row 1 overhead - MATCHED orthographic projection (same world window): reference photo | Blender Cycles |
Remotion/Three. Row 2 side and oblique - projection NOT matched (reference camera poses unknown):
qualitative only. Row 3 blade/puck close-up (no reference exists: provisional geometry) + findings text.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
Image.MAX_IMAGE_PIXELS = None
g = json.loads((REPO / "data/geometry.json").read_text())
rep = json.loads((REPO / "validation/20-reprojection.json").read_text())
M = next(m for m in g["image_to_world"] if m["id"] == "map.overhead.preview")["matrix"]
Ainv = np.linalg.inv(np.array([[M[0], M[1], M[2]], [M[3], M[4], M[5]], [0, 0, 1]]))
over = next(s for s in g["source_images"] if s["source_id"] == "stiga_se_fi_overhead")
win_w, win_h = 931.2, 931.2 * 1080 / 1920
c0 = Ainv @ np.array([-win_w / 2, win_h / 2, 1])
c1 = Ainv @ np.array([win_w / 2, -win_h / 2, 1])
ref_over = Image.open(REPO / over["local_path"]).convert("RGB").crop((int(c0[0]), int(c0[1]), int(c1[0]), int(c1[1])))

PW, PH = 960, 540
def tile(path_or_img, box=None):
    im = path_or_img if isinstance(path_or_img, Image.Image) else Image.open(REPO / path_or_img).convert("RGB")
    if box:
        im = im.crop(box)
    return im.resize((PW, PH))

try:
    font = ImageFont.truetype("DejaVuSans.ttf", 22)
    small = ImageFont.truetype("DejaVuSans.ttf", 18)
except OSError:
    font = small = ImageFont.load_default()

rows = [
    [("OVERHEAD reference (official photo, same world window)", tile(ref_over)),
     ("OVERHEAD Blender Cycles (iter. 17; clay figures)", tile("validation/17-overhead.png")),
     ("OVERHEAD Remotion/Three (iter. 19)", tile("validation/19/19-overhead.png"))],
    [("SIDE reference (side A) - projection NOT matched", tile("references/originals/stiga-sports-71-1145-01-side-a.jpg", (500, 2150, 4700, 2780))),
     ("OBLIQUE Blender Cycles 1920x1080 (iter. 18)", tile("validation/18-oblique-1080p.png")),
     ("OBLIQUE Remotion/Three 1920x1080 (iter. 19)", tile("validation/19/19-oblique.png"))],
    [("SIDE Remotion/Three (iter. 19)", tile("validation/19/19-side.png")),
     ("BLADE/PUCK close-up (Cycles) - NO reference; provisional contacts", tile("validation/18-blade-puck.png", (0, 150, 1000, 712))),
     ("OBLIQUE reference (oblique B) - projection NOT matched", tile("references/originals/stiga-sports-71-1145-01-oblique-b.jpg", (100, 1650, 5100, 3500)))],
]
notes = [
    "20 - MODEL REVIEW (AI review only; NO user approval recorded). Calibration intake: nothing supplied - canonical parameters unchanged.",
    f"GEOMETRY (separate from appearance): pipeline reprojection data -> Blender -> GLB -> Remotion, overhead at {rep['output_mm_per_px']} mm/px: slot centrelines mean offset <= {rep['slot_summary']['worst_mean_offset_px']} px (max offsets 7-11 px only where figures/puck cover slots);",
    f"   ice edge median {rep['ice_edge']['median_abs_offset_px']} px. Reference vs model (overhead, matched projection): markings, slots, goals and logos coincide visually; model derived from this photo, so this is consistency, not accuracy.",
    "   ABSOLUTE accuracy: preview scale ASSUMED (845 mm catalog length); trace uncertainty 21 source px ~ 3.8 mm; lens bow <= 10 px; figure pivots/blades/stops UNMEASURED. -> NO one-output-pixel claim is supported.",
    "APPEARANCE: Cycles - soft shadows, clear screens, printed ice read well; figures are smooth proxies (10 of 12 placeholders); boards grey placeholder; no decals.",
    "   Remotion/Three - same layout and colours but no shadows, opaque white end screens, flatter ice. Does NOT meet photorealism yet -> bounded Cycles benchmark proposed (docs/review.md).",
    "PROPOSED OUTPUT: 1920x1080 (1 px ~ 0.485 mm over the full rink in the overhead; ~0.6-1.2 mm in the oblique). Supported claim: illustrative prototype, provisional geometry.",
]
W = 3 * PW + 40
H = 3 * (PH + 40) + 40 + len(notes) * 30 + 30
sheet = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(sheet)
for r, row in enumerate(rows):
    for c, (title, im) in enumerate(row):
        x, y = 10 + c * (PW + 10), 10 + r * (PH + 40)
        d.text((x, y), title, fill=(0, 0, 0), font=small)
        sheet.paste(im, (x, y + 26))
y0 = 10 + 3 * (PH + 40) + 10
for i, t in enumerate(notes):
    d.text((14, y0 + i * 30), t, fill=(120, 0, 0) if "NO " in t or "NOT" in t else (0, 0, 0), font=small)
sheet.save(REPO / "validation/20-review-sheet.png")
print("wrote validation/20-review-sheet.png", sheet.size)
