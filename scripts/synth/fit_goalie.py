"""Fit the goalie pose in a real crop by silhouette search (validation labels for the pilot; docs/synthetic-goalie-pilot.md).

The goalie mold's vertices are projected with the reference camera for candidate (slot position u, rotation theta) and
compared with the real foreground (difference from the clean plate) by IoU inside the goalie column.
"""
import json
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
BOX = CAM["goal_crop_boxes_video_px"]
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
HOME = {"W": 0.0, "E": 180.0}
M = np.load(REPO / "out/synth/goalie_mesh.npz"); V = M["V"][::3].astype(np.float64)   # every 3rd vertex is dense enough at ~1.5 px/mm


def arc_point(P, u):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = u * seg.sum(); acc = np.r_[0, np.cumsum(seg)]
    k = min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1); f = (s - acc[k]) / seg[k]
    return P[k] + f * (P[k + 1] - P[k])


def silhouette(end, u, theta, shape=(200, 200)):
    p = arc_point(SLOT[f"{end}-G"], u); h = np.radians(HOME[end] + theta)
    Rz = np.array([[np.cos(h), -np.sin(h), 0], [np.sin(h), np.cos(h), 0], [0, 0, 1]])
    W = V @ Rz.T + [p[0], p[1], 0]
    X = W @ R.T + t; q = (X @ K.T); q = q[:, :2] / q[:, 2:] - BOX[end][:2]
    m = np.zeros(shape, np.uint8); qi = np.round(q).astype(int)
    ok = (qi[:, 0] >= 0) & (qi[:, 0] < shape[1]) & (qi[:, 1] >= 0) & (qi[:, 1] < shape[0])
    m[qi[ok, 1], qi[ok, 0]] = 1
    return cv2.morphologyEx(cv2.dilate(m, np.ones((2, 2), np.uint8)), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))


def column(end, shape=(200, 200), r=42, h=62):
    P = SLOT[f"{end}-G"]; m = np.zeros(shape, np.uint8)
    for s in np.linspace(0, 1, 25):
        c = P[0] + (P[-1] - P[0]) * s
        ring = np.array([(c[0] + r * np.cos(a), c[1] + r * np.sin(a), z) for a in np.linspace(0, 2 * np.pi, 24) for z in (0, h)])
        X = ring @ R.T + t; q = X @ K.T; q = q[:, :2] / q[:, 2:] - BOX[end][:2]
        cv2.fillPoly(m, [cv2.convexHull(q.astype(np.int32))], 1)
    return m


def foreground(crop, plate, col):
    """Soft foreground in [0, 1]: blurred colour difference from the clean plate, discounted near strong plate edges
    (registration leaves a pixel or two of misalignment there)."""
    a = cv2.cvtColor(cv2.GaussianBlur(crop, (0, 0), 1.2), cv2.COLOR_BGR2LAB).astype(np.float32)
    b = cv2.cvtColor(cv2.GaussianBlur(plate.astype(np.uint8), (0, 0), 1.2), cv2.COLOR_BGR2LAB).astype(np.float32)
    d = np.sqrt(((a - b) ** 2 * [0.6, 1, 1]).sum(-1))
    gp = cv2.cvtColor(plate.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    edge = cv2.dilate(np.hypot(cv2.Sobel(gp, cv2.CV_32F, 1, 0), cv2.Sobel(gp, cv2.CV_32F, 0, 1)), np.ones((5, 5), np.uint8))
    thr = 18 + 0.25 * np.clip(edge, 0, 200)
    return np.clip((d - thr) / 25.0, 0, 1) * (col > 0)


def fit(end, fg, col):
    best = []
    tot = fg.sum() + 1e-6
    def score(u, th):
        s = (silhouette(end, u, th) & col).astype(np.float32)
        tp = (s * fg).sum(); prec = tp / max(s.sum(), 1); rec = tp / tot
        return 2 * prec * rec / max(prec + rec, 1e-6)
    cands = [(score(u, th), u, th) for u in np.linspace(0, 1, 9) for th in range(0, 360, 10)]
    cands.sort(reverse=True)
    for _, u0, t0 in cands[:4]:
        loc = [(score(u, th), u, th % 360) for u in np.clip(np.linspace(u0 - 0.1, u0 + 0.1, 9), 0, 1) for th in np.arange(t0 - 10, t0 + 11, 2.5)]
        best += loc
    best.sort(reverse=True)
    alt = next((b for b in best if min(abs(b[2] - best[0][2]) % 360, 360 - abs(b[2] - best[0][2]) % 360) > 60), None)
    return best[0], alt
