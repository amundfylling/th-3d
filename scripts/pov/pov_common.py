"""Shared helpers for the POV pipeline (Karlis Balodis's head-mounted DJI Osmo Nano; docs/pov-videos.md).

World mm as data/geometry.json (+z up, rink-centred). Image px are .LRF proxy px (960 x 720) unless noted.
Camera model: OpenCV pinhole + radial/tangential distortion (k1, k2, p1, p2, k3).
"""
import json, subprocess
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
W_PX, H_PX = 960, 720
FPS = 30000 / 1001


@lru_cache(None)
def geometry():
    return json.loads((REPO / "data/geometry.json").read_text())


@lru_cache(None)
def landmarks():
    G = geometry()
    M = np.array(G["image_to_world"][0]["matrix"]).reshape(3, 3)
    out = {}
    for l in G["landmarks"]:
        if l["source_image_id"] != "stiga_se_fi_overhead":
            continue
        p = M @ [*l["px"], 1]
        out[l["id"]] = p[:2] / p[2]
    return out


@lru_cache(None)
def slots():
    return {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in geometry()["fixture_paths"]}


def resample(P, step):
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    a = np.arange(0, s[-1], step)
    return np.c_[np.interp(a, s, P[:, 0]), np.interp(a, s, P[:, 1])]


@lru_cache(None)
def slot_points(step=4.0, skaters_only=True, trim=5.0):
    pts = []
    for pid, P in slots().items():
        if skaters_only and pid.endswith("-G"):
            continue
        Q = resample(P, step)
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
        pts.append(Q[(s > trim) & (s < s[-1] - trim)])
    return np.concatenate(pts)


@lru_cache(None)
def board_points(step=4.0):
    B = np.array(geometry()["board"]["inner_boundary"]["world"]["points_mm"], float)
    return resample(np.r_[B, B[:1]], step)


def to3(P2, z=0.0):
    P2 = np.atleast_2d(P2)
    return np.c_[P2, np.full(len(P2), z)].astype(np.float64)


def project(X, rvec, tvec, K, dist):
    return cv2.projectPoints(np.ascontiguousarray(X, np.float64), np.asarray(rvec, float), np.asarray(tvec, float),
                             np.asarray(K, float), np.asarray(dist, float))[0][:, 0]


def K_of(f, cx=W_PX / 2, cy=H_PX / 2):
    return np.array([[f, 0, cx], [0, f, cy], [0, 0, 1]], float)


def read_frames(video, idxs, w=W_PX, h=H_PX):
    """Decode the listed frame indices (sorted) of the main video stream as BGR arrays."""
    idxs = sorted(set(int(i) for i in idxs))
    sel = "+".join(f"eq(n\\,{i})" for i in idxs)
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-map", "0:v:0", "-vf", f"select='{sel}'",
                        "-vsync", "0", "-s", f"{w}x{h}", "-pix_fmt", "bgr24", "-f", "rawvideo", "-"],
                       capture_output=True, check=True).stdout
    n = len(p) // (w * h * 3)
    arr = np.frombuffer(p, np.uint8)[: n * w * h * 3].reshape(n, h, w, 3)
    return dict(zip(idxs, arr))


def dark_mask(bgr):
    """Dark, unsaturated pixels: slots (black grooves), the board's dark foot strip. ASSUMED thresholds."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return (hsv[..., 2] < 110) & (hsv[..., 1] < 90)


def line_mask(bgr, thresh=28, k=11):
    """Thin dark lines on the white ice (slots, board foot strip): morphological black-hat on grey. ASSUMED."""
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    bh = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return (bh > thresh) & (hsv[..., 1] < 90)


def ice_polygon_mask(rvec, tvec, K, dist, inset_mm=0.0, shape=(H_PX, W_PX)):
    """Image mask of the projected inner board boundary (optionally shrunk/grown by inset_mm, approx. radial)."""
    B = board_points(8.0)
    if inset_mm:
        B = B * (1 - inset_mm / np.linalg.norm(B, axis=1, keepdims=True).clip(1))
    q = project(to3(B), rvec, tvec, K, dist)
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, [np.round(q).astype(np.int32)], 1)
    return m.astype(bool)
