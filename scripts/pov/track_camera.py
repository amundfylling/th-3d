"""Step 4 of the POV plan: solve the camera for every frame of one .LRF game.

Per frame, forward through the whole video:
  1. Prediction: corners tracked by optical flow (pyramidal LK) from the previous frame, only inside the previous
     frame's projected ice; their previous pixels are back-projected onto the ice plane with the previous camera, and
     the new camera is solvePnPRansac on those world points (figures, hands: RANSAC outliers).
  2. Refinement: the rink fit (camera_fit.fit, intrinsics fixed) on slot centrelines and the board boundary, using
     only line pixels inside the grown predicted ice.
A frame is OK when the refined median residual is <= MAX_MED px and at least MIN_IN of the in-frame model points
lie within 2 px of a line pixel. If the prediction fails (too few inliers) the previous OK pose is kept and the frame
is flagged.
  3. Relocalisation, when step 2 fails or there is no previous pose: SIFT features of the frame matched to the
     empty-rink plate (rink_plate.py; the plate's pixels are world mm on the ice), solvePnPRansac, then step 2.
     Neighbouring tables carry the same artwork, so a relocalisation is accepted only through the step-2 check.
Thresholds are ASSUMED.
Usage: python3 scripts/pov/track_camera.py <video> <intrinsics.npy> <plate.png> <out.npz> [stop frame]
  intrinsics.npy: f, k1, k2 (further values ignored).
"""
import os, subprocess, sys, time
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from pov_common import W_PX, H_PX, K_of, ice_polygon_mask
import camera_fit as cf
import rink_plate as rp

MAX_MED, MIN_IN = 1.5, 0.5
video, seed, plate_path, out = sys.argv[1], np.load(sys.argv[2]), sys.argv[3], sys.argv[4]
STOP = int(sys.argv[5]) if len(sys.argv) > 5 else None   # debug: stop at this frame
intr = seed[:3]
K, D = K_of(intr[0]), cf.dist_of(intr[1:])


def stream(start, stop):
    vf = f"select='gte(n\\,{start})*lt(n\\,{stop})'"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-map", "0:v:0", "-vf", vf, "-vsync", "0",
                          "-pix_fmt", "bgr24", "-f", "rawvideo", "-"], stdout=subprocess.PIPE, bufsize=W_PX * H_PX * 3 * 4)
    i = start
    while True:
        b = p.stdout.read(W_PX * H_PX * 3)
        if len(b) < W_PX * H_PX * 3:
            break
        yield i, np.frombuffer(b, np.uint8).reshape(H_PX, W_PX, 3)
        i += 1
    p.wait()


def backproject(px, rv, tv):
    """Image px -> world points on the ice plane z = 0 for camera (rv, tv)."""
    n = cv2.undistortPoints(px.reshape(-1, 1, 2).astype(np.float64), K, D)[:, 0]
    Rm = cv2.Rodrigues(rv)[0]
    C = -Rm.T @ tv
    d = (Rm.T @ np.c_[n, np.ones(len(n))].T).T
    s = -C[2] / d[:, 2]
    return C + s[:, None] * d, s > 0


def predict(prev_gray, gray, pose):
    mask = cv2.erode(ice_polygon_mask(pose[0], pose[1], K, D).astype(np.uint8), np.ones((9, 9), np.uint8))
    p0 = cv2.goodFeaturesToTrack(prev_gray, 400, 0.01, 7, mask=mask)
    if p0 is None or len(p0) < 12:
        return None, 0
    p1, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, p0, None, winSize=(21, 21), maxLevel=3)
    p0b, stb, _ = cv2.calcOpticalFlowPyrLK(gray, prev_gray, p1, None, winSize=(21, 21), maxLevel=3)
    good = (st[:, 0] == 1) & (stb[:, 0] == 1) & (np.linalg.norm((p0b - p0)[:, 0], axis=1) < 1.0)
    if good.sum() < 12:
        return None, int(good.sum())
    Wp, ok = backproject(p0[good, 0], pose[0], pose[1])
    Wp, ip = Wp[ok], p1[good, 0][ok]
    try:
        r = cv2.solvePnPRansac(Wp, ip.astype(np.float64), K, D, pose[0].copy(), pose[1].copy(), useExtrinsicGuess=True,
                               iterationsCount=100, reprojectionError=2.0, flags=cv2.SOLVEPNP_ITERATIVE)
    except cv2.error:
        return None, 0
    if not r[0] or r[3] is None or len(r[3]) < 12:
        return None, 0 if r[3] is None else len(r[3])
    new = (r[1].ravel(), r[2].ravel())
    c_old = -cv2.Rodrigues(pose[0])[0].T @ pose[1]; c_new = -cv2.Rodrigues(new[0])[0].T @ new[1]
    if not np.all(np.isfinite(c_new)) or np.linalg.norm(c_new - c_old) > 150:   # a head moves < 150 mm per frame
        return None, len(r[3])
    return new, len(r[3])


plate = cv2.cvtColor(cv2.imread(plate_path), cv2.COLOR_BGR2GRAY)
SIFT = cv2.SIFT_create(4000, contrastThreshold=0.02)
_pm = np.zeros(plate.shape, np.uint8); _pm[8:-8, 8:-8] = 1
KP_P, DES_P = SIFT.detectAndCompute(plate, _pm)
WP = np.array([[rp.X0 + k.pt[0], rp.Y1 - k.pt[1], 0.0] for k in KP_P])
BF = cv2.BFMatcher(cv2.NORM_L2)


def relocalise(gray):
    kp, des = SIFT.detectAndCompute(gray, None)
    if des is None or len(kp) < 10:
        return None
    m = BF.knnMatch(des, DES_P, k=2)
    good = [a for a, b in (x for x in m if len(x) == 2) if a.distance < 0.8 * b.distance]
    if len(good) < 12:
        return None
    ip = np.array([kp[a.queryIdx].pt for a in good]); wp = WP[[a.trainIdx for a in good]]
    try:
        ok, rv, tv, inl = cv2.solvePnPRansac(wp, ip, K, D, iterationsCount=2000, reprojectionError=4.0,
                                             flags=cv2.SOLVEPNP_SQPNP)
    except cv2.error:
        return None
    if not ok or inl is None or len(inl) < 12:
        return None
    return rv.ravel(), tv.ravel()


def refine(fr, pose):
    roi = cv2.dilate(ice_polygon_mask(pose[0], pose[1], K, D).astype(np.uint8),
                     np.ones((21, 21), np.uint8)).astype(bool)
    poses, _, st = cf.fit([cf.Target(fr, roi)], [pose], intr, free_intr=False, radii=(8, 5, 4, 3))
    s = st[0]
    ok = s["median_px"] <= MAX_MED and s["within2px"] >= MIN_IN and s["points_in_frame"] >= 300
    return (poses[0][0].copy(), poses[0][1].copy()), s, ok


def run(frames):
    rows, prev_gray, pose = [], None, None
    for i, fr in frames:
        gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        n_in, ok, s, src = 0, False, None, 0
        if prev_gray is not None and pose is not None:
            pred, n_in = predict(prev_gray, gray, pose)
            if pred is not None:
                pose = pred
            new, s, ok = refine(fr, pose)
            src = 1
        if not ok:
            rl = relocalise(gray)
            if rl is not None:
                new2, s2, ok2 = refine(fr, rl)
                if ok2 or s is None or s2["median_px"] < s["median_px"]:
                    new, s, ok, src = new2, s2, ok2, 2
        if s is None:
            rows.append(np.r_[i, np.full(6, np.nan), np.nan, np.nan, 0, 0, 0, 0, np.nan, 0]); prev_gray = gray; continue
        if ok:
            pose = new
        elif pose is None:
            pose = new
        q = cf.project(cf.BOARD3, pose[0], pose[1], K, D)
        bif = float(np.mean((q[:, 0] >= 0) & (q[:, 0] < W_PX) & (q[:, 1] >= 0) & (q[:, 1] < H_PX)))
        rows.append(np.r_[i, pose[0], pose[1], s["median_px"], s["p90_px"], s["within2px"], s["points_in_frame"],
                          ok, n_in, bif, src])
        prev_gray = gray
        if i % 500 == 0:
            A = np.array(rows); print(i, f"ok {A[:, 11].mean():.2f}", f"reloc {(A[:, 14] == 2).sum()}", f"{time.time() - t0:.0f}s", flush=True)
    return rows


t0 = time.time()
rows = run(stream(0, STOP or 10 ** 9))
A = np.array(rows)
np.savez(out, rows=A, intr=intr, cols=np.array("i r0 r1 r2 t0 t1 t2 med p90 within2 n_in ok flow_inliers board_in_frame "
                                              "source(1 flow, 2 reloc)".split()))
print("frames", len(A), "ok", int(A[:, 11].sum()), "median residual", np.nanmedian(A[A[:, 11] > 0, 7]),
      "relocalised", int((A[:, 14] == 2).sum()), f"{time.time() - t0:.0f}s")
