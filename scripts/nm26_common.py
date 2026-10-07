"""Shared helpers for the NM 2026 semi-final scripts (scripts/nm26-*.py). See docs/nm26-passes.md.

Coordinates:
- video px: the broadcast frame (1920 x 1080);
- stab px: the rink region ROI of the game's reference frame, after per-frame registration (stab = ref - ROI origin);
- world mm: data/geometry.json rink coordinates (-x = the video's left end = goal.W).
Video decoding needs PyAV (libdav1d); OpenCV in this container cannot decode AV1.
"""
import json
from pathlib import Path

import av
import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data/games/nm26-semifinal"
OUT = REPO / "out/nm26"
CFG = json.loads((DATA / "config.json").read_text())
VIDEO = REPO / CFG["video"]["local_path"]
FPS = CFG["video"]["fps"]
X0, Y0, X1, Y1 = CFG["roi_px"]
W_STAB, H_STAB = X1 - X0, Y1 - Y0
T_ROI = np.array([[1, 0, -X0], [0, 1, -Y0], [0, 0, 1.0]])


def load(p):
    return json.loads(Path(p).read_text())


def save(p, obj, indent=None):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, indent=indent) + "\n")


def game_dir(game):
    return DATA / game


def frames(t0, t1, fmt="bgr24"):
    """Yield (frame_index, image) for video time t0 <= t < t1 (frame_index = round(t * fps))."""
    c = av.open(str(VIDEO))
    s = c.streams.video[0]
    s.thread_type = "AUTO"
    c.seek(int(max(0.0, t0 - 2.0) / s.time_base), stream=s)
    for fr in c.decode(s):
        if fr.time < t0 - 1e-6:
            continue
        if fr.time >= t1:
            break
        yield int(round(fr.time * FPS)), fr.to_ndarray(format=fmt)
    c.close()


def proj(H, P):
    P = np.atleast_2d(np.asarray(P, float))
    q = np.c_[P, np.ones(len(P))] @ np.asarray(H, float).T
    return q[:, :2] / q[:, 2:]


def ice_mask():
    m = np.zeros((H_STAB, W_STAB), np.uint8)
    cv2.fillPoly(m, [np.array(CFG["ice_polygon_stab_px"], np.int32)], 1)
    return m.astype(bool)


class Registrar:
    """Registers a video frame to the game's reference frame (ORB at half resolution on the rink and housing)."""

    def __init__(self, ref_bgr):
        self.orb = cv2.ORB_create(3000)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        g = cv2.resize(cv2.cvtColor(ref_bgr, cv2.COLOR_BGR2GRAY), None, fx=0.5, fy=0.5)
        k, d = self.orb.detectAndCompute(g, self._mask(g))
        self.kr, self.dr = np.float32([p.pt for p in k]), d
        self.prev = np.eye(3)
        S = np.diag([2.0, 2.0, 1.0])
        self.S, self.Si = S, np.linalg.inv(S)

    @staticmethod
    def _mask(g):
        x0, y0, x1, y1 = CFG["registration_mask_half_px"]
        m = np.zeros_like(g)
        m[y0:y1, x0:x1] = 255
        return m

    def __call__(self, bgr):
        """Homography video px -> reference video px, and the RANSAC inlier count (0 = previous homography kept)."""
        g = cv2.resize(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), None, fx=0.5, fy=0.5)
        k, d = self.orb.detectAndCompute(g, self._mask(g))
        n = 0
        if d is not None and len(k) > 30:
            mm = [a for a, b in (z for z in self.bf.knnMatch(d, self.dr, k=2) if len(z) == 2) if a.distance < 0.75 * b.distance]
            if len(mm) > 30:
                H, inl = cv2.findHomography(np.float32([k[q.queryIdx].pt for q in mm]), self.kr[[q.trainIdx for q in mm]], cv2.RANSAC, 1.5)
                if H is not None and inl.sum() >= 25:
                    self.prev, n = self.S @ H @ self.Si, int(inl.sum())
        return self.prev, n


def reference_frame(game):
    t = CFG["games"][game]["reference_frame_s"]
    return next(a for _, a in frames(t, t + 0.2))
