"""Shared helpers for the Edwall hat-trick rebuild (scripts/edwall-*.py; docs/rebuild-g2-edwall-v2.md).

Pixel frames: out/edwall/<goal_id>/<frame>.png are the E half of the game's reference frame at 2x
(crop px = 2 * (reference px - (900, 360))). World mm: data/geometry.json (z up); the reference camera
(camera-ref.json) maps world to reference px.
"""
import os
import json
from pathlib import Path

import numpy as np

from nm26_tracks import FIGURE_TRACKS

REPO = Path(__file__).resolve().parents[1]
D = REPO / "data/games/nm26-semifinal"
CAM = json.loads((D / "camera-ref.json").read_text())
K, R, T = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
HALF0 = np.array([900.0, 360.0]); SCALE = 2.0
GOALS = {r["id"]: r for r in json.loads((D / "goal-labels.json").read_text())["labels"]}
FPS = 30


def world_to_crop(P, z=0.0):
    P = np.atleast_2d(np.asarray(P, float)); X = np.c_[P[:, :2], np.full(len(P), z)] @ R.T + T; q = X @ K.T
    return SCALE * (q[:, :2] / q[:, 2:] - HALF0)


def crop_to_world(q, z=0.0):
    """Back-project crop px onto the horizontal plane at height z (mm)."""
    H = K @ np.c_[R[:, 0], R[:, 1], R[:, 2] * z + T]
    q = np.atleast_2d(np.asarray(q, float)) / SCALE + HALF0
    w = np.c_[q, np.ones(len(q))] @ np.linalg.inv(H).T
    return w[:, :2] / w[:, 2:]


def goal_frame(gid):
    return int(round(GOALS[gid]["goal_video_s"] * FPS))


def tracks(gid, file=None):
    """Figure tracks (game file, 30 fps inside the goal windows): {frame: {pid: (u, theta_deg, src)}}. Default: the
    selected tracks (scripts/nm26_tracks.py: figure-tracks-v3.json), or `file` in the game folder; EDWALL_TRACKS=<file> overrides
    both (scripts/edwall-track-compare.py)."""
    g = GOALS[gid]["game"]; S = json.loads(Path(os.environ.get("EDWALL_TRACKS", D / g / (file or FIGURE_TRACKS))).read_text())
    C = S["columns"]; f0 = goal_frame(gid); out = {}
    pids = [c[:-2] for c in C if c.endswith("_u")]
    for r in S["rows"]:
        if f0 - 270 <= r[0] <= f0 + 30:
            v = dict(zip(C, r)); out[r[0]] = {p: (v[f"{p}_u"], v[f"{p}_theta_deg"], v[f"{p}_src"]) for p in pids}
    return out
