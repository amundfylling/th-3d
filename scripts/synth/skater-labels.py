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
sys.path.insert(0, str(REPO / "scripts"))
import table_common  # noqa: E402
CAM = table_common.REF_CAMERA
K, R, t = table_common.ref_camera()
Hinv = np.linalg.inv(K @ np.c_[R[:, 0], R[:, 1], t])
G = table_common.GEOMETRY
SLOT = table_common.SLOT
HOME = table_common.HOME
crops = {c["id"]: c for c in json.loads((REPO / "data/games/nm26-semifinal/skater-facing-crops.json").read_text())["crops"]}


def ice(px, origin):
    w = Hinv @ np.array([px[0] + origin[0], px[1] + origin[1], 1.0]); return w[:2] / w[2]


on_slot = table_common.nearest_on_slot


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
