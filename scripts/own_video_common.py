"""Shared helpers for the own-video pipeline (scripts/own-video-*.py; docs/own-video-tracking.md).

World mm as data/geometry.json (+z up). The per-frame camera comes from own-video-camera.py. Figure molds come from the
committed GLBs (assets/figures/*.glb: glTF Y-up metres, origin on the fixture axis), converted to Blender/world axes
(x, -z, y) in mm. A figure at slot position u and heading h (deg, 0 = facing +x) is Rz(h) @ mold + pivot, the same
convention as the NM26 renders (scripts/synth/render-skater-crops.py: heading = home + theta, home W 0, E 180).
"""
import json, sys
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from game_common import GAME, FPS, geometry, frames, MATCH_START_S, MATCH_END_S  # noqa: E402,F401

OUTD = GAME / "own-video"
SKATERS = ["W-LD", "W-RD", "W-C", "W-LW", "W-RW", "E-LD", "E-RD", "E-C", "E-LW", "E-RW"]
GOALIES = ["W-G", "E-G"]
HOME = {"W": 0.0, "E": 180.0}
PART = {0: "blue", 1: "skin", 2: "jersey", 3: "stick"}


@lru_cache(None)
def camera_track():
    d = json.loads((OUTD / "camera-track.json").read_text())
    rows = np.array(d["rows"], float)
    return np.array(d["K"], float), rows[:, 1:4], rows[:, 4:7]


def project(i, X):
    K, RV, TV = camera_track()
    X = np.ascontiguousarray(np.atleast_2d(X), float)
    return cv2.projectPoints(X, RV[i], TV[i], K, None)[0][:, 0]


def cam_centre(i):
    K, RV, TV = camera_track()
    R = cv2.Rodrigues(RV[i])[0]; return (-R.T @ TV[i]).ravel()


@lru_cache(None)
def slots():
    G = geometry()
    return {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}


def arc(P):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); return np.r_[0, np.cumsum(seg)]


def slot_point(pid, u):
    """Point and unit tangent at slot position u in [0, 1] (arc-length fraction of the centreline)."""
    P = slots()[pid]; acc = arc(P); s = np.clip(np.asarray(u, float), 0, 1) * acc[-1]
    x = np.interp(s, acc, P[:, 0]); y = np.interp(s, acc, P[:, 1])
    return np.stack([x, y], -1)


def slot_length(pid): return float(arc(slots()[pid])[-1])


@lru_cache(None)
def mold(kind, kit, step=1):
    """(points N x 3 mm in the mold frame, part index N) from the GLB vertices (every step-th vertex)."""
    import trimesh
    s = trimesh.load(REPO / f"assets/figures/{kind}_{kit}.glb")
    P, L = [], []
    for name, g in s.geometry.items():
        if name.startswith("Print"): continue
        k = int(name.split("_")[-1]) if "_" in name else 0
        if kind == "goalie" and k >= 3: k = 3          # goalie: the dark catcher and the stick count as "stick"
        v = np.asarray(g.vertices)[::step] * 1000.0
        P.append(np.c_[v[:, 0], -v[:, 2], v[:, 1]]); L.append(np.full(len(v), k))
    return np.concatenate(P), np.concatenate(L)


def place(points, pid, u, heading_deg):
    p = slot_point(pid, u); h = np.radians(heading_deg)
    Rz = np.array([[np.cos(h), -np.sin(h), 0], [np.sin(h), np.cos(h), 0], [0, 0, 1]])
    return points @ Rz.T + [p[0], p[1], 0]


def load(p): return json.loads(Path(p).read_text())


def save(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True); Path(p).write_text(json.dumps(obj, separators=(",", ":")) + "\n")
