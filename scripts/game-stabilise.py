"""Stabilise the handheld match recording: one homography per frame onto the reference frame, and a median background.

    /root/venvs/blender/bin/python scripts/game-stabilise.py

Input: references/games/fylling-vs-moe-trondheim-open-2022-final.mov.
Outputs: data/games/fylling-vs-moe-2022/stabilisation.json, data/games/fylling-vs-moe-2022/background.png.

Method: ORB features of the reference frame (inside the table region) matched to every frame, RANSAC homography
(3 px). A frame with too few matches keeps the previous homography (recorded with inliers 0). The homography treats
the whole table as one plane; the housing stands above the ice, so this is approximate where the camera moves most
(the first 5 s). The background is the per-pixel median of every 10th stabilised frame (the moving figures and the
puck drop out).
"""
import cv2
import numpy as np

from game_common import GAME, REF_FRAME, ROI, CROP_W, CROP_H, crop_matrix, frames, save

orb = cv2.ORB_create(3000, scaleFactor=1.2, nlevels=6, fastThreshold=10)
bf = cv2.BFMatcher(cv2.NORM_HAMMING)
ref = next(f for i, f in frames() if i == REF_FRAME)
rg = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
mask = np.zeros_like(rg)
mask[ROI[1] - 10:ROI[3] + 10, ROI[0] - 10:ROI[2] + 10] = 255
kr, dr = orb.detectAndCompute(rg, mask)

Hs, inl, samples = [], [], []
prev = np.eye(3)
T = crop_matrix()
for i, f in frames():
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    k, d = orb.detectAndCompute(g, None)
    h, n = None, 0
    if d is not None and len(k) > 20:
        m = bf.knnMatch(d, dr, k=2)
        good = [a for a, b in (x for x in m if len(x) == 2) if a.distance < 0.8 * b.distance]
        if len(good) > 25:
            src = np.float32([k[a.queryIdx].pt for a in good])
            dst = np.float32([kr[a.trainIdx].pt for a in good])
            h, ok = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
            n = int(ok.sum()) if h is not None else 0
    if h is None or n <= 20:
        h, n = prev, 0
    h = h / h[2, 2]
    prev = h
    Hs.append([float(f"{v:.9g}") for v in h.ravel()[:8]])
    inl.append(n)
    if i % 10 == 0:
        samples.append(cv2.warpPerspective(f, T @ h, (CROP_W, CROP_H), flags=cv2.INTER_CUBIC))
    if i % 1000 == 0:
        print(i, n, flush=True)

bg = np.median(np.stack(samples), axis=0).astype(np.uint8)
GAME.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(GAME / "background.png"), bg)
save(GAME / "stabilisation.json", {
    "video": "references/games/fylling-vs-moe-trondheim-open-2022-final.mov",
    "reference_frame": REF_FRAME,
    "roi_ref_px": list(ROI),
    "method": "ORB (3000 features in the table region of the reference frame), ratio test 0.8, RANSAC homography 3 px; "
              "frames with 20 or fewer inliers keep the previous homography (inliers recorded as 0)",
    "H_video_to_ref": Hs,
    "H_note": "Row-major 3x3 with H[2][2] = 1 omitted. Maps video px of frame i to ref px of the reference frame.",
    "inliers": inl,
    "frames": len(Hs),
    "frames_without_fit": int(sum(1 for n in inl if n == 0)),
})
print("frames", len(Hs), "without fit", sum(1 for n in inl if n == 0))
