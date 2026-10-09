"""Turn the skater label page's db documents into skater pose labels (docs/synthetic-goalie-pilot.md, skaters).

    python3 scripts/synth/skater-labels.py <labels_dir>

<labels_dir> holds the page's documents (collection "skaters", one JSON per crop; ArtifactData list with out_dir).
The feet tap and the direction tap are mapped from crop px to the ice (z = 0) through the reference camera. The feet
point is projected onto the skater's slot centreline: u = arc-length fraction there (the mold's pivot is under the
left skate, so the feet tap sits a few mm from it; not corrected), slot_dist_mm = how far the tap lies from the slot (a
check: large values mean a wrong figure or a mis-tap). The direction feet -> tap is the facing heading (0 = +x, toward
the E end, counter-clockwise from above); theta_deg = heading - home heading (W 0, E 180), the model's convention.
Writes data/games/nm26-semifinal/skater-labels.json.
"""
import json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
Hinv = np.linalg.inv(K @ np.c_[R[:, 0], R[:, 1], t])
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
HOME = {"W": 0.0, "E": 180.0}
crops = {c["id"]: c for c in json.loads((REPO / "data/games/nm26-semifinal/skater-facing-crops.json").read_text())["crops"]}


def ice(px, origin):
    w = Hinv @ np.array([px[0] + origin[0], px[1] + origin[1], 1.0]); return w[:2] / w[2]


def on_slot(P, q):
    seg = np.diff(P, axis=0); L = np.linalg.norm(seg, axis=1); acc = np.r_[0, np.cumsum(L)]; best = (1e9, 0.0)
    for k in range(len(seg)):
        f = np.clip(np.dot(q - P[k], seg[k]) / (L[k] ** 2), 0, 1); d = np.linalg.norm(P[k] + f * seg[k] - q)
        if d < best[0]: best = (d, (acc[k] + f * L[k]) / acc[-1])
    return best


rows = []
for f in sorted(Path(sys.argv[1]).glob("*.json")):
    L = json.loads(f.read_text()); c = crops[L["id"]]; pid = c["player_id"]
    r = {"id": L["id"], "pid": pid, "game": c["game"], "frame": c["frame"], "verdict": L["verdict"]}
    if L["verdict"] == "facing":
        o = c["crop_origin_ref_px"]; a = ice(L["feet_px"], o); b = ice(L["dir_px"], o); v = b - a
        d, u = on_slot(SLOT[pid], a); head = float(np.degrees(np.arctan2(v[1], v[0])) % 360)
        r.update({"feet_mm": [round(float(a[0]), 1), round(float(a[1]), 1)], "u": round(float(u), 4), "slot_dist_mm": round(float(d), 1),
                  "facing_deg": round(head, 1), "theta_deg": round((head - HOME[pid[0]]) % 360, 1), "tap_distance_mm": round(float(np.hypot(*v)), 1)})
    rows.append(r)
out = {"description": "User labels for real NM26 skater crops (label page validation/skater-facing-review.html): feet on "
       "the ice and facing direction, mapped through the reference camera (scripts/synth/skater-labels.py). Status: user "
       "labels; tap precision not measured; u from the feet tap, not the exact pivot.", "labels": rows}
(REPO / "data/games/nm26-semifinal/skater-labels.json").write_text(json.dumps(out, indent=1) + "\n")
n = [r for r in rows if r["verdict"] == "facing"]
print(len(rows), "labels,", len(n), "with a pose; slot distance median",
      round(float(np.median([r["slot_dist_mm"] for r in n])), 1) if n else None, "mm")
