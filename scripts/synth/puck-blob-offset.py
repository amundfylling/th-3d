"""Mean offset from the puck's blob centre to its top-face centre in the reference camera (docs/synthetic-puck.md).

    /root/venvs/blender/bin/python scripts/synth/puck-blob-offset.py

The current track (puck-track.json) gives the centre of the dark blob (the whole visible puck: top face and side); the
detector's label is the projection of the puck's top-face centre. Geometry, no rendering: at 400 places on the ice the
puck (25.4 mm, top 12 mm above the ice as in the Blender model) is projected with the reference camera; blob = the
filled convex hull of the top and bottom rims. Writes out/synth/puck/blob-offset.json (mean, median, spread in stab
px); scripts/synth/train-puck-detector.py adds the mean to the current track's positions.
"""
import json
from pathlib import Path
import cv2, numpy as np
REPO = Path(__file__).resolve().parents[2]
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
def project(P): q = (np.atleast_2d(P) @ R.T + t) @ K.T; return q[:, :2] / q[:, 2:]
rng = np.random.default_rng(0); a = np.linspace(0, 2 * np.pi, 64, endpoint=False); D = []
for _ in range(400):
    x, y = rng.uniform(-420, 420), rng.uniform(-220, 220)
    rim = np.vstack([np.c_[x + 12.7 * np.cos(a), y + 12.7 * np.sin(a), np.full(64, z)] for z in (0.0, 12.0)])
    q = project(rim); top = project([[x, y, 12.0]])[0]
    o = q.min(0) - 2; S = 8
    m = np.zeros((int((q[:, 1].max() - o[1]) * S) + 4, int((q[:, 0].max() - o[0]) * S) + 4), np.uint8)
    cv2.fillConvexPoly(m, cv2.convexHull(((q - o) * S).astype(np.int32)), 1)
    ys, xs = np.nonzero(m); c = o + np.array([xs.mean(), ys.mean()]) / S
    D.append(top - c)
D = np.array(D)
out = {"n": len(D), "mean_px": D.mean(0).round(2).tolist(), "median_px": np.median(D, 0).round(2).tolist(), "std_px": D.std(0).round(2).tolist(),
       "method": "geometry: centroid of the projected puck silhouette vs projected top-face centre, reference camera"}
(REPO / "out/synth/puck/blob-offset.json").write_text(json.dumps(out, indent=1)); print(out)
