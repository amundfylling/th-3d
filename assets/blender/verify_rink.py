"""Iteration 11 scale check on the orthographic overhead render (no Blender needed):
measures the ice extent in pixels -> mm and samples the render along every slot centreline.
    /root/venvs/blender/bin/python assets/blender/verify_rink.py
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
rep = json.loads((REPO / "validation" / "11-rink-report.json").read_text())
g = json.loads((REPO / "data" / "geometry.json").read_text())
# Measured on the unlit ID render (ice white, boards red, housing blue, holes black). An earlier version
# measured the lit still, where board shadows darken the ice edge; that check was invalid and replaced.
img = np.asarray(Image.open(REPO / "validation" / "11-rink-overhead-id.png").convert("RGB")).astype(int)
H, W = img.shape[:2]
mmpp = rep["overhead_render"]["ortho_scale_m"] * 1000 / W
cx, cy = rep["overhead_render"]["centre_mm"]
to_px = lambda x, y: (W / 2 + (x - cx) / mmpp, H / 2 - (y - cy) / mmpp)
to_mm = lambda u, v: (cx + (u - W / 2) * mmpp, cy - (v - H / 2) * mmpp)

# Ice: white ID pixels connected to the rink centre (slots are black, boards red).
lum = img.mean(axis=2)
bright = (img[..., 0] > 200) & (img[..., 1] > 200) & (img[..., 2] > 200)
from collections import deque
seed = tuple(int(round(v)) for v in to_px(0, 0))[::-1]
seen = np.zeros_like(bright)
q = deque([seed]); seen[seed] = True
while q:
    r, c = q.popleft()
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        rr, cc = r + dr, c + dc
        if 0 <= rr < H and 0 <= cc < W and bright[rr, cc] and not seen[rr, cc]:
            seen[rr, cc] = True; q.append((rr, cc))
rows, cols = np.nonzero(seen)
x0, y1 = to_mm(cols.min(), rows.min()); x1, y0 = to_mm(cols.max() + 1, rows.max() + 1)
bounds = g["board"]["inner_boundary"]["world"]["points_mm"]
bx = [p[0] for p in bounds]; by = [p[1] for p in bounds]
ice = {"render_mm": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)], "data_mm": [round(min(bx), 2), round(min(by), 2), round(max(bx), 2), round(max(by), 2)]}
ice["max_abs_diff_mm"] = round(max(abs(a - b) for a, b in zip(ice["render_mm"], ice["data_mm"])), 2)

# Slots: every centreline point should land on a dark (hole) pixel.
dark_frac = {}
for f in g["fixture_paths"]:
    pts = f["centreline"]["points_mm"][2:-2]
    hits = []
    for x, y in pts:
        u, v = to_px(x, y)
        hits.append(lum[int(v), int(u)] < 150)
    dark_frac[f["player_id"]] = round(float(np.mean(hits)), 3)
out = {"mm_per_px": round(mmpp, 5), "ice_extent": ice, "tolerance_mm": round(2 * mmpp, 2), "slot_centreline_on_dark_fraction": dark_frac}
out["pass"] = bool(ice["max_abs_diff_mm"] <= 2 * mmpp and min(dark_frac.values()) >= 0.95)
(REPO / "validation" / "11-rink-verify.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=1))
