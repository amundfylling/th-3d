"""Per-frame 3D camera of the handheld match recording (docs/own-video-tracking.md, step 1).

    /root/venvs/blender/bin/python scripts/own-video-camera.py

Inputs (already in the repo, docs/game-tracking.md): the per-frame stabilisation (video px -> ref px) and the rink-plane
calibration (world mm -> crop px). Their product is a per-frame homography world (z = 0) -> video px. A homography of a
plane fixes a pinhole camera up to its intrinsics, so:
1. intrinsics: square pixels, principal point at the image centre (assumed, a phone camera), one focal length f for
   the whole recording (assumed: no zoom change). f is chosen to minimise the median PnP residual over 300 frames
   spread over the recording;
2. per frame: cv2.solvePnP on a 9 x 5 grid of ice points mapped through that frame's homography gives R, t; the
   residual (px) says how far the homography is from a rigid camera with that f;
3. slot check (every 5th frame): every slot centreline projected with the frame's camera; the share of sample points
   that lie on a pixel darker than both neighbours 4 px to either side (the dark slot). A wrong camera falls off the
   slots;
4. height check: the camera also gives the figures' heads. That is checked by eye on validation/own-video-camera.jpg.
Writes data/games/fylling-vs-moe-2022/own-video/camera-track.json and validation/own-video-camera.jpg.
Status: PROPOSED; the calibration it rests on is assumed (preview scale, goal.W at the left).
"""
import json, sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from game_common import GAME, crop_matrix, frames, stabilisation, world_to_crop, geometry, FPS  # noqa: E402

OUTD = GAME / "own-video"; OUTD.mkdir(parents=True, exist_ok=True)
W, H = 640, 360
Hs = stabilisation(); N = len(Hs)
Hwv = [np.linalg.inv(S) @ np.linalg.inv(crop_matrix()) @ world_to_crop() for S in Hs]  # world z=0 -> video px
gx, gy = np.meshgrid(np.linspace(-380, 380, 9), np.linspace(-190, 190, 5))
GRID = np.c_[gx.ravel(), gy.ravel(), np.zeros(gx.size)]


def hp(Hm, P):
    q = np.c_[P[:, :2], np.ones(len(P))] @ Hm.T; return q[:, :2] / q[:, 2:]


def K_of(f): return np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1.0]])


def pnp(i, K, guess=None):
    img = hp(Hwv[i], GRID)
    if guess is None: ok, rv, tv = cv2.solvePnP(GRID, img, K, None, flags=cv2.SOLVEPNP_IPPE)
    else: ok, rv, tv = cv2.solvePnP(GRID, img, K, None, guess[0].copy(), guess[1].copy(), True, cv2.SOLVEPNP_ITERATIVE)
    q, _ = cv2.projectPoints(GRID, rv, tv, K, None)
    return rv, tv, float(np.sqrt(((q[:, 0] - img) ** 2).sum(1)).mean())


# 1. focal length
sample = np.linspace(0, N - 1, 300).astype(int)
scan = []
for f in np.arange(300, 1601, 20):
    K = K_of(f); scan.append((float(np.median([pnp(i, K)[2] for i in sample])), float(f)))
f0 = min(scan)[1]
fine = [(float(np.median([pnp(i, K_of(f))[2] for i in sample])), float(f)) for f in np.arange(f0 - 20, f0 + 21, 2)]
FOCAL = min(fine)[1]; K = K_of(FOCAL)
print("focal", FOCAL, "median residual", min(fine)[0])

# 2. per-frame camera
cams = []; prev = None
for i in range(N):
    rv, tv, res = pnp(i, K)            # IPPE: closed form, no drift from the previous frame
    Rm = cv2.Rodrigues(rv)[0]; C = (-Rm.T @ tv).ravel()
    if C[2] < 0: print("warning: camera below the ice at frame", i)
    cams.append([i, *np.round(rv.ravel(), 6).tolist(), *np.round(tv.ravel(), 3).tolist(), round(res, 3), *np.round(C, 1).tolist()])

# 3. slot check
G = geometry()
SL = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
slot_pts = np.concatenate([np.c_[P[::2], np.zeros(len(P[::2]))] for P in SL.values()])
slot_score = {}
for i, fr in frames():
    if i % 5: continue
    g = cv2.GaussianBlur(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)
    c = cams[i]; rv, tv = np.array(c[1:4]), np.array(c[4:7])
    q = cv2.projectPoints(slot_pts, rv, tv, K, None)[0][:, 0]
    Rm = cv2.Rodrigues(rv)[0]
    # normal to the slot in the image: approximate by the image direction of world y (slots run mostly along x)
    q2 = cv2.projectPoints(slot_pts + [0, 6, 0], rv, tv, K, None)[0][:, 0]
    nrm = q2 - q; nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
    ok = (q[:, 0] > 5) & (q[:, 0] < W - 5) & (q[:, 1] > 5) & (q[:, 1] < H - 5)
    def s(P): return cv2.remap(g, P[:, 0].astype(np.float32).reshape(-1, 1), P[:, 1].astype(np.float32).reshape(-1, 1), cv2.INTER_LINEAR).ravel()
    a, b, m = s(q + 4 * nrm), s(q - 4 * nrm), s(q)
    hit = (m < a - 8) & (m < b - 8)
    slot_score[i] = round(float(hit[ok].mean()), 3) if ok.sum() > 50 else None

res = np.array([c[7] for c in cams]); C = np.array([c[8:11] for c in cams])
ss = np.array([v for v in slot_score.values() if v is not None])
out = {
    "description": "Per-frame pinhole camera of the handheld match recording (scripts/own-video-camera.py). Columns per frame: "
                   "rvec (Rodrigues, world -> camera), t_mm, PnP residual px against the frame's ice-plane homography, camera "
                   "centre in world mm. Project a world point X (mm, z up) with cv2.projectPoints(X, rvec, t, K, None).",
    "status": "proposed",
    "status_note": "Rests on the assumed ice-plane calibration (preview scale, goal.W at the video's left) and on the assumed "
                   "intrinsics: square pixels, principal point at the image centre, one focal length for the whole video.",
    "image_size_px": [W, H], "fps": FPS,
    "K": K.round(3).tolist(),
    "focal_scan": [{"f_px": f, "median_residual_px": round(r, 3)} for r, f in sorted(fine, key=lambda x: x[1])],
    "focal_scan_coarse": [{"f_px": f, "median_residual_px": round(r, 3)} for r, f in sorted(scan, key=lambda x: x[1])],
    "summary": {
        "frames": N, "pnp_residual_px_median": round(float(np.median(res)), 3), "pnp_residual_px_p95": round(float(np.percentile(res, 95)), 3),
        "camera_height_mm_median": round(float(np.median(C[:, 2])), 1), "camera_height_mm_range_p5_p95": np.percentile(C[:, 2], [5, 95]).round(1).tolist(),
        "camera_distance_from_rink_centre_mm_median": round(float(np.median(np.linalg.norm(C, axis=1))), 1),
        "slot_check_frames": int(len(ss)), "slot_check_on_slot_share_median": round(float(np.median(ss)), 3),
        "slot_check_on_slot_share_p10": round(float(np.percentile(ss, 10)), 3),
    },
    "slot_check": {"method": "share of projected slot-centreline points darker than both neighbours 4 px away (by 8 grey levels); every 5th frame",
                   "per_frame": slot_score},
    "columns": ["frame", "rx", "ry", "rz", "tx_mm", "ty_mm", "tz_mm", "pnp_residual_px", "cx_mm", "cy_mm", "cz_mm"],
    "rows": cams,
}
(OUTD / "camera-track.json").write_text(json.dumps(out, separators=(",", ":")) + "\n")
print(json.dumps(out["summary"], indent=1))
