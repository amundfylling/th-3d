"""Shared helpers for the match-tracking scripts (scripts/game-*.py). See docs/game-tracking.md.

Coordinates:
- video px: the recording's own pixels (640 x 360);
- ref px: video px of the reference frame REF_FRAME after per-frame stabilisation (homography video -> ref);
- crop px: the stabilised working image, ref px of the rink region ROI scaled by CROP_SCALE
  (crop = CROP_SCALE * (ref - ROI origin));
- world mm: data/geometry.json rink coordinates (origin at the rink centre, +x toward goal.E, +y toward the far long
  side in this recording).
"""
import json
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
VIDEO = REPO / "references/games/fylling-vs-moe-trondheim-open-2022-final.mov"
GAME = REPO / "data/games/fylling-vs-moe-2022"
OUT = REPO / "out/game"
FPS = 25.0
REF_FRAME = 3000
ROI = (95, 120, 485, 275)  # x0, y0, x1, y1 in ref px: the whole table
CROP_SCALE = 2
CROP_W, CROP_H = (ROI[2] - ROI[0]) * CROP_SCALE, (ROI[3] - ROI[1]) * CROP_SCALE
# Match clock from the audio timer (docs/game-mechanics.md section 3; confirmed by the user, A4)
MATCH_START_S, MATCH_END_S = 7.5, 307.5


def load(p):
    return json.loads(Path(p).read_text())


def save(p, obj, indent=None):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, indent=indent) + "\n")


def geometry():
    return load(REPO / "data/geometry.json")


def proj(H, P):
    """Apply a 3x3 homography to N x 2 points."""
    P = np.atleast_2d(np.asarray(P, float))
    q = np.c_[P, np.ones(len(P))] @ np.asarray(H, float).T
    return q[:, :2] / q[:, 2:]


def crop_matrix():
    """ref px -> crop px."""
    s = CROP_SCALE
    return np.array([[s, 0, -ROI[0] * s], [0, s, -ROI[1] * s], [0, 0, 1]], float)


def frames():
    """Yield (index, BGR frame) for every frame of the recording."""
    cap = cv2.VideoCapture(str(VIDEO))
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        yield i, f
        i += 1
    cap.release()


def stabilisation():
    """Per-frame homographies video px -> ref px (list of 3x3 arrays)."""
    S = load(GAME / "stabilisation.json")
    return [np.r_[h, 1.0].reshape(3, 3) for h in S["H_video_to_ref"]]


def stabilised_crops():
    """Yield (index, crop) of every frame, warped to the stabilised crop."""
    Hs = stabilisation()
    T = crop_matrix()
    for i, f in frames():
        yield i, cv2.warpPerspective(f, T @ Hs[i], (CROP_W, CROP_H), flags=cv2.INTER_CUBIC)


def world_to_crop():
    return np.array(load(GAME / "calibration.json")["H_world_mm_to_crop_px"], float)


def match_frames():
    return range(int(round(MATCH_START_S * FPS)), int(round(MATCH_END_S * FPS)))
