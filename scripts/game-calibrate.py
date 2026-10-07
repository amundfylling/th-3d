"""Rink-plane calibration of the match recording: homography world mm (ice plane) -> stabilised crop px.

    /root/venvs/blender/bin/python scripts/game-calibrate.py

Inputs: data/games/fylling-vs-moe-2022/{calibration-inputs.json, background.png}, data/geometry.json (slot centrelines,
board landmarks and the inner board boundary, all in world mm with the repo's preview scale).
Outputs: data/games/fylling-vs-moe-2022/calibration.json, validation/game-calibration.png.

Fit: least squares over (1) the hand-picked slot-end anchors, (2) the two blue lines (perpendicular distance of
world points on each line to the image line, weight 2), (3) every skater slot centreline on dark background pixels
(truncated distance, weight 0.5, soft-L1). Stage 1 uses (1)+(2) only, stage 2 all three.
"""
import cv2
import numpy as np
from scipy.optimize import least_squares

from game_common import GAME, REPO, geometry, load, proj, save

G = geometry()
INP = load(GAME / "calibration-inputs.json")
SL = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
B = np.array(G["board"]["inner_boundary"]["world"]["points_mm"], float)
M = np.array(G["image_to_world"][0]["matrix"]).reshape(3, 3)
LM = {l["id"]: proj(M, [l["px"]])[0] for l in G["landmarks"] if l["source_image_id"] == "stiga_se_fi_overhead"}

AW = np.array([SL[a["player_id"]][0 if a["end"] == "start" else -1] for a in INP["slot_end_anchors"]])
AI = np.array([a["crop_px"] for a in INP["slot_end_anchors"]])
LINES = []
for l in INP["lines"]:
    t, b = LM[l["landmark_pair"][0]], LM[l["landmark_pair"][1]]
    pts = np.array([t + (b - t) * u for u in np.linspace(0.08, 0.92, 15)])
    a, c = np.array(l["crop_px"], float)
    n = np.array([-(c - a)[1], (c - a)[0]])
    LINES.append((pts, a, n / np.linalg.norm(n)))

bg = cv2.imread(str(GAME / "background.png"))
S = 4
hsv = cv2.cvtColor(cv2.resize(bg, None, fx=S, fy=S, interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2HSV)
dark = ((hsv[..., 2] < 110) & (hsv[..., 1] < 120)).astype(np.uint8)
DT = cv2.distanceTransform(1 - dark, cv2.DIST_L2, 5) / S
SP = []
for pid, P in SL.items():
    if pid.endswith("-G"):
        continue
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    SP += [[np.interp(a, s, P[:, 0]), np.interp(a, s, P[:, 1])] for a in np.arange(3, s[-1] - 3, 3)]
SP = np.array(SP)


def parts(p):
    H = np.r_[p, 1].reshape(3, 3)
    ra = (proj(H, AW) - AI).ravel()
    rl = np.concatenate([(proj(H, pts) - a) @ n for pts, a, n in LINES])
    q = proj(H, SP) * S
    x = np.clip(q[:, 0], 0, DT.shape[1] - 1).astype(int)
    y = np.clip(q[:, 1], 0, DT.shape[0] - 1).astype(int)
    return ra, rl, np.minimum(DT[y, x], 3.0)


# initial estimate: anchors + the goalie slot ends (see calibration-inputs.json)
init_w = np.r_[AW, [SL["W-G"][0], SL["W-G"][-1], SL["E-G"][0], SL["E-G"][-1]]]
init_i = np.r_[AI, [[202.7, 125.0], [210.7, 165.0], [562.7, 100.7], [586.7, 121.7]]]
H0, _ = cv2.findHomography(init_w, init_i, 0)
p0 = (H0 / H0[2, 2]).ravel()[:8]
r1 = least_squares(lambda p: np.r_[parts(p)[0], 2 * parts(p)[1]], p0, diff_step=1e-5)
r2 = least_squares(lambda p: np.r_[parts(p)[0], 2 * parts(p)[1], 0.5 * parts(p)[2]], r1.x, diff_step=1e-5, loss="soft_l1", f_scale=1.5)
H = np.r_[r2.x, 1].reshape(3, 3)
ra, rl, rs = parts(r2.x)


def local_scale(x, y):
    a = proj(H, [[x, y]])[0]
    return {"world_mm": [x, y], "crop_px_per_mm_along_x": round(float(np.linalg.norm(proj(H, [[x + 1, y]])[0] - a)), 3),
            "crop_px_per_mm_across_y": round(float(np.linalg.norm(proj(H, [[x, y + 1]])[0] - a)), 3)}


res = {
    "anchor_rms_crop_px": round(float(np.sqrt(np.mean(ra ** 2))), 2),
    "line_rms_crop_px": round(float(np.sqrt(np.mean(rl ** 2))), 2),
    "slot_points_median_distance_crop_px": round(float(np.median(rs)), 2),
    "slot_points_within_1px": round(float(np.mean(rs < 1.0)), 3),
    "slot_points": int(len(rs)),
}
save(GAME / "calibration.json", {
    "H_world_mm_to_crop_px": H.tolist(),
    "plane": "ice top (z = 0); not valid for raised objects",
    "status": "assumed",
    "status_note": "Fitted to the repo's slot centrelines and board landmarks, which are traced from the official overhead with the assumed preview scale (geometry.json map.overhead.preview). The user confirmed the table layout is the same (A9); no measured dimension of this table is used.",
    "inputs": "data/games/fylling-vs-moe-2022/calibration-inputs.json",
    "residuals": res,
    "local_scale": [local_scale(x, y) for x, y in [(0, 0), (-300, 150), (-300, -150), (300, 150), (300, -150), (0, 200), (0, -200)]],
    "near_board_note": "The near board and housing hide a strip of ice along the near (-y) board: the projected inner board boundary on the near side lies below the visible ice edge.",
})
print(res)

im = cv2.resize(bg, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
for pid, P in SL.items():
    q = (proj(H, P) * 2).astype(np.int32)
    cv2.polylines(im, [q], False, (255, 0, 255) if pid[0] == "W" else (0, 200, 0), 2, cv2.LINE_AA)
    cv2.putText(im, pid, tuple(int(v) for v in q[len(q) // 2] + [4, -6]), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 220), 1, cv2.LINE_AA)
cv2.polylines(im, [(proj(H, B) * 2).astype(np.int32)], True, (0, 140, 255), 1, cv2.LINE_AA)
for k, v in LM.items():
    if k.startswith("lm.board"):
        cv2.circle(im, tuple((proj(H, [v])[0] * 2).astype(int)), 4, (0, 0, 255), -1)
for a in AI:
    cv2.drawMarker(im, tuple((a * 2).astype(int)), (255, 255, 0), cv2.MARKER_CROSS, 12, 2)
cv2.putText(im, "Calibration: repo slot centrelines (magenta W / green E), inner board boundary (orange), board/line landmarks (red), anchors (cyan)",
            (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
cv2.imwrite(str(REPO / "validation/game-calibration.png"), im)
