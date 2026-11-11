"""The table as the tracking scripts see it: figure ids, home headings, slots and the NM26 reference camera.

One definition of what the NM26, synthetic-data and replay scripts each used to spell out themselves (the slot-position
helper alone existed twelve times). Pure Python + NumPy: importable from the Blender, PyTorch and plain scripts alike,
and from the tests (tests/synth/test_table_common.py).

Conventions (docs/pose.md, docs/synthetic-goalie-pilot.md):
- world mm: data/geometry.json rink coordinates, +z up;
- a figure stands on its slot centreline at slot position u in [0, 1], the fraction of the centreline's arc length from
  its first point; its heading is HOME[end] + theta (deg, 0 = facing +x), end = the first letter of the figure id;
- kit colour is an END, not a player: W is the white/blue end, E the yellow end (CLAUDE.md).

The move engine (scripts/shotlib/world.py) and the older trace scripts keep their own copies of HOME and Slot: the
engine's files are part of every engine-built trace's identity, so they are not touched from here.
"""
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
NM26 = REPO / "data/games/nm26-semifinal"
GEOMETRY = json.loads((REPO / "data/geometry.json").read_text())

# The ten skaters in the order of the skater-pose models' one-hot input (scripts/synth/train-skater-pose.py): changing
# the order changes what a trained model reads, so it is fixed here and pinned by a test.
SKATERS = ["W-LW", "E-LW", "W-RW", "E-RW", "W-C", "E-C", "W-LD", "E-LD", "W-RD", "E-RD"]
GOALIES = ["W-G", "E-G"]
HOME = {"W": 0.0, "E": 180.0}  # heading of theta = 0, by end (deg)

# slot centrelines (N x 2 mm), cumulative arc length along each (mm, starts at 0) and total length
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in GEOMETRY["fixture_paths"]}
ACC = {p: np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))] for p, P in SLOT.items()}
SLOT_LEN = {p: float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum()) for p, P in SLOT.items()}


def arc_point_s(P, u):
    """Point at slot position u on the centreline P, and its arc length s (mm). u outside [0, 1] extends the end
    segments in a straight line."""
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = u * seg.sum(); acc = np.r_[0, np.cumsum(seg)]
    k = min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1); f = (s - acc[k]) / seg[k]
    return P[k] + f * (P[k + 1] - P[k]), s


def arc_point(P, u):
    """Point at slot position u on the centreline P (see arc_point_s)."""
    return arc_point_s(P, u)[0]


def slot_points(pid, u):
    """Points (N x 2 mm) of figure pid at slot positions u (array or scalar); u outside [0, 1] is held at the ends."""
    P, acc = SLOT[pid], ACC[pid]; s = np.asarray(u) * acc[-1]
    return np.c_[np.interp(s, acc, P[:, 0]), np.interp(s, acc, P[:, 1])]


def slot_point(pid, u):
    """Point (2,) of figure pid at slot position u (scalar); u outside [0, 1] is held at the ends."""
    P, acc = SLOT[pid], ACC[pid]; s = u * acc[-1]
    return np.array([np.interp(s, acc, P[:, 0]), np.interp(s, acc, P[:, 1])])


def nearest_on_slot(P, q):
    """(distance in mm, slot position u) of the point of the centreline P nearest to q; u is clamped to [0, 1]."""
    seg = np.diff(P, axis=0); L = np.linalg.norm(seg, axis=1); acc = np.r_[0, np.cumsum(L)]; best = (1e9, 0.0)
    for k in range(len(seg)):
        f = np.clip(np.dot(q - P[k], seg[k]) / (L[k] ** 2), 0, 1); d = np.linalg.norm(P[k] + f * seg[k] - q)
        if d < best[0]: best = (d, (acc[k] + f * L[k]) / acc[-1])
    return best


# ---------------------------------------------------------------- NM26 reference camera
# camera-ref.json: the broadcast camera of game 1's reference frame (all seven games are registered to it), decomposed by
# hand from g1/calibration.json (docs/synthetic-goalie-pilot.md section A). x_px ~ K (R X_mm + t).
REF_CAMERA = json.loads((NM26 / "camera-ref.json").read_text())


def ref_camera():
    """(K, R, t_mm) of the reference camera as new arrays."""
    return np.array(REF_CAMERA["K"]), np.array(REF_CAMERA["R"]), np.array(REF_CAMERA["t_mm"])


def ref_project(X):
    """World points (N x 3 mm, or N x 2 on the ice) -> reference video px (N x 2)."""
    K, R, t = ref_camera()
    X = np.atleast_2d(np.asarray(X, float))
    if X.shape[1] == 2:
        X = np.c_[X, np.zeros(len(X))]
    q = (X @ R.T + t) @ K.T
    return q[:, :2] / q[:, 2:]


def ref_plane_homography(z=0.0):
    """3 x 3 homography from the horizontal plane at height z (world x, y in mm) to reference video px."""
    K, R, t = ref_camera()
    return K @ np.c_[R[:, 0], R[:, 1], R[:, 2] * z + t]


def ref_to_plane(px, z=0.0):
    """Reference video px (N x 2) back onto the horizontal plane at height z: world x, y in mm (N x 2)."""
    q = np.atleast_2d(np.asarray(px, float))
    w = np.c_[q, np.ones(len(q))] @ np.linalg.inv(ref_plane_homography(z)).T
    return w[:, :2] / w[:, 2:]
