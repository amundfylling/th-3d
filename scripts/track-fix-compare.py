"""Before/after comparison of the E-RW and W-RW track fix (2026-10-01): stick occlusion boxes in the slot tracer.

    python3 scripts/track-fix-compare.py BEFORE_GEOMETRY.json BEFORE_19_OVERHEAD.png
Row per path: reference overhead crop (4x) with the old centreline (red) and the new one (green) and the
occlusion box (yellow) | Remotion overhead before (4x) | Remotion overhead after (4x) | lateral profile plot
(deviation from a straight line, mm, before red / after green). Output: validation/track-fix-compare.png
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
Image.MAX_IMAGE_PIXELS = None
before = json.loads(Path(sys.argv[1]).read_text())
after = json.loads((REPO / "data" / "geometry.json").read_text())
ren_b = Image.open(sys.argv[2]).convert("RGB")
ren_a = Image.open(REPO / "validation" / "19" / "19-overhead.png").convert("RGB")
seeds = json.loads((REPO / "data" / "slot-seeds.json").read_text())["paths"]
M = np.array(next(m for m in after["image_to_world"] if m["id"] == "map.overhead.preview")["matrix"]).reshape(3, 3)
Mi = np.linalg.inv(M)
ov = Image.open(REPO / "references" / "originals" / "stiga-sports-71-1145-01-overhead.jpg").convert("RGB")
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
MMPP_R = 931.2 / 1920  # Remotion overhead still: 931.2 mm over 1920 px, centred on the origin
CASES = (("E-RW", -300, -100), ("W-RW", 100, 300))
W, H = 760, 260


def path(g, pid):
    return np.array(next(f for f in g["fixture_paths"] if f["player_id"] == pid)["centreline"]["points_mm"])


def to_ov(P):
    q = np.c_[P, np.ones(len(P))] @ Mi.T
    return q[:, :2]


rows = []
stats = {}
for pid, x0, x1 in CASES:
    Pb, Pa = path(before, pid), path(after, pid)
    yc = float(np.median(Pa[(Pa[:, 0] > x0) & (Pa[:, 0] < x1), 1]))
    # reference crop
    c0, c1 = to_ov(np.array([[x0, yc + 8], [x1, yc - 8]]))
    box = (int(c0[0]), int(c0[1]), int(c1[0]), int(c1[1]))
    crop = ov.crop(box)
    s = W / crop.width
    crop = crop.resize((W, int(crop.height * s * 4)), Image.LANCZOS)  # 4x vertical exaggeration
    d = ImageDraw.Draw(crop)
    sy = s * 4
    for P, col in ((Pb, (255, 40, 40)), (Pa, (40, 220, 60))):
        q = to_ov(P)
        d.line([((u - box[0]) * s, (v - box[1]) * sy) for u, v in q if box[0] - 50 < u < box[2] + 50], fill=col, width=2)
    for ob in seeds[f"path.{pid}"].get("occluded_boxes_overhead", []):
        u0, v0, u1, v1 = ob["box"]
        d.rectangle(((u0 - box[0]) * s, (v0 - box[1]) * sy, (u1 - box[0]) * s, (v1 - box[1]) * sy), outline=(255, 220, 0), width=2)
    d.text((6, 4), f"{pid} reference overhead (vertical x4): red before, green after, yellow = stick box", fill=(0, 0, 0), font=F, stroke_width=2, stroke_fill=(255, 255, 255))
    tiles = [crop]
    # Remotion before/after crops (same window)
    for im, lab in ((ren_b, "Remotion overhead BEFORE"), (ren_a, "Remotion overhead AFTER")):
        u0, u1 = 960 + x0 / MMPP_R, 960 + x1 / MMPP_R
        v0, v1 = 540 - (yc + 8) / MMPP_R, 540 - (yc - 8) / MMPP_R
        t = im.crop((int(u0), int(v0), int(u1), int(v1)))
        sc = W / t.width
        t = t.resize((W, int(t.height * sc * 4)), Image.LANCZOS)
        ImageDraw.Draw(t).text((6, 4), lab + " (vertical x4)", fill=(0, 0, 0), font=F, stroke_width=2, stroke_fill=(255, 255, 255))
        tiles.append(t)
    # deviation plot
    pl = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(pl)
    d.text((6, 4), f"{pid}: deviation from a straight line (mm), x {x0}..{x1} mm", fill=(0, 0, 0), font=F)
    zero = H // 2 + 10
    d.line((0, zero, W, zero), fill=(150, 150, 150))
    for mm in (-2, -1, 1, 2):
        y = zero - mm * 40
        d.line((0, y, W, y), fill=(225, 225, 225))
        d.text((W - 40, y - 9), f"{mm:+d}", fill=(120, 120, 120), font=F)
    for P, col, tag in ((Pb, (220, 30, 30), "before"), (Pa, (30, 170, 50), "after")):
        q = P[(P[:, 0] > x0) & (P[:, 0] < x1)]
        c = np.polyfit(q[:, 0], q[:, 1], 1)
        r = q[:, 1] - np.polyval(c, q[:, 0])
        stats[f"{pid}_{tag}"] = {"max_mm": round(float(abs(r).max()), 3), "rms_mm": round(float(np.sqrt((r ** 2).mean())), 3)}
        d.line([((x - x0) / (x1 - x0) * W, zero - v * 40) for x, v in zip(q[:, 0], r)], fill=col, width=3)
    d.text((6, H - 26), f"before max {stats[pid + '_before']['max_mm']} mm   after max {stats[pid + '_after']['max_mm']} mm", fill=(0, 0, 0), font=F)
    tiles.append(pl)
    rows.append(tiles)

hs = [max(t.height for t in r) for r in rows]
cols = 2
out = Image.new("RGB", (cols * W + 10, sum(((len(r) + 1) // cols) * h for r, h in zip(rows, hs)) + 40 * len(rows)), "white")
y = 0
for r, h in zip(rows, hs):
    for i, t in enumerate(r):
        out.paste(t, ((i % cols) * (W + 10), y + (i // cols) * (h + 10)))
    y += ((len(r) + 1) // cols) * (h + 10) + 30
out = out.crop((0, 0, out.width, y))
out.save(REPO / "validation" / "track-fix-compare.png")
(REPO / "validation" / "track-fix-report.json").write_text(json.dumps({"straightness_deviation": stats, "method": "occluded_boxes_overhead in data/slot-seeds.json; sections inside are not measured and are bridged by the tracer's Hermite gap interpolation"}, indent=2) + "\n")
print(json.dumps(stats))
