"""Rink-plane calibration for one NM 2026 game: homography world mm -> stab px.

    /root/venvs/blender/bin/python scripts/nm26-calibrate.py g1

Inputs: data/games/nm26-semifinal/<game>/{background.png, calibration-inputs.json}, data/geometry.json.
Outputs: data/games/nm26-semifinal/<game>/calibration.json, validation/nm26-<game>-calibration.jpg.

Method:
1. Initial homography from the ten points where the goal, blue and centre lines meet the boards. These are
   hand-picked in the background image to about 5-20 px, and their world positions are the repo's board landmarks.
2. ICP on the skater slots: every skater slot centreline (sampled every 4 mm) is projected; each sample is matched to
   the nearest dark slot pixel of the background inside the ice polygon, within a shrinking radius
   (40 -> 5 px); the homography is refitted with RANSAC (3 px) each round.
The rink is point-symmetric, so the slots alone cannot tell the two ends apart; the line points fix the orientation
(goal.W at the video's left end).
"""
import sys

import cv2
import numpy as np
from scipy.spatial import cKDTree

from nm26_common import REPO, game_dir, ice_mask, load, proj, save

GAME = sys.argv[1] if len(sys.argv) > 1 else "g1"
G = load(REPO / "data/geometry.json")
INP = load(game_dir(GAME) / "calibration-inputs.json")
M = np.array(G["image_to_world"][0]["matrix"]).reshape(3, 3)
LM = {l["id"]: proj(M, [l["px"]])[0] for l in G["landmarks"] if l["source_image_id"] == "stiga_se_fi_overhead"}
W = np.array([LM["lm.board." + k] for k in INP["line_points_stab_px"]])
I = np.array(list(INP["line_points_stab_px"].values()), float)
SL = {f["player_id"]: np.array(f["centreline"]["points_mm"]) for f in G["fixture_paths"]}
SP = []
for pid, P in SL.items():
    if pid.endswith("-G"):
        continue
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    SP += [[np.interp(a, s, P[:, 0]), np.interp(a, s, P[:, 1])] for a in np.arange(5, s[-1] - 5, 4)]
SP = np.array(SP)

bg = cv2.imread(str(game_dir(GAME) / "background.png"))
hsv = cv2.cvtColor(bg, cv2.COLOR_BGR2HSV)
dark = (hsv[..., 2] < 100) & (hsv[..., 1] < 100) & ice_mask()
ys, xs = np.where(dark)
tree = cKDTree(np.c_[xs, ys])
H, _ = cv2.findHomography(W, I, 0)
init_d = float(np.median(tree.query(proj(H, SP))[0]))
for rad in [40, 30, 22, 16, 12, 9, 7, 6, 5, 5, 5]:
    d, k = tree.query(proj(H, SP), distance_upper_bound=rad)
    ok = np.isfinite(d)
    H, _ = cv2.findHomography(SP[ok], np.c_[xs, ys][k[ok]].astype(float), cv2.RANSAC, 3.0)
d, _ = tree.query(proj(H, SP))


def scale(x, y):
    a = proj(H, [[x, y]])[0]
    return {"world_mm": [x, y], "mm_per_px_along_x": round(float(1 / np.linalg.norm(proj(H, [[x + 1, y]])[0] - a)), 3),
            "mm_per_px_across_y": round(float(1 / np.linalg.norm(proj(H, [[x, y + 1]])[0] - a)), 3)}


save(game_dir(GAME) / "calibration.json", {
    "H_world_mm_to_stab_px": (H / H[2, 2]).tolist(),
    "plane": "ice top (z = 0)",
    "status": "assumed",
    "status_note": "Fitted to the repo's slot centrelines (traced from the official overhead with the assumed preview scale); the user confirmed the same table layout. No dimension of this table was measured.",
    "residuals": {"slot_samples": int(len(SP)), "initial_median_px": round(init_d, 2), "median_px": round(float(np.median(d)), 2),
                  "within_2px": round(float(np.mean(d < 2)), 3), "within_4px": round(float(np.mean(d < 4)), 3),
                  "note": "Distance from each projected slot sample to the nearest dark slot pixel; samples hidden by figures in the background stay far."},
    "local_scale": [scale(x, y) for x, y in [(0, 0), (-300, 150), (300, 150), (-300, -150), (300, -150)]],
})
im = bg.copy()
for pid, P in SL.items():
    cv2.polylines(im, [proj(H, P).astype(np.int32)], False, (255, 0, 255) if pid[0] == "W" else (0, 200, 0), 1, cv2.LINE_AA)
cv2.polylines(im, [proj(H, np.array(G["board"]["inner_boundary"]["world"]["points_mm"])).astype(np.int32)], True, (0, 140, 255), 1, cv2.LINE_AA)
cv2.putText(im, f"{GAME}: repo slot centrelines (magenta W, green E), inner board boundary (orange); median {np.median(d):.2f} px",
            (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
cv2.imwrite(str(REPO / f"validation/nm26-{GAME}-calibration.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 85])
print("initial median px", round(init_d, 2), "final median px", round(float(np.median(d)), 2), "within 2 px", round(float(np.mean(d < 2)), 3))
