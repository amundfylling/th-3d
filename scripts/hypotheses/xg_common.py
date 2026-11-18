"""Shared loaders for the expected-goals (xG) hypothesis test. Reads only committed NM26 data."""
import json, numpy as np
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
D = REPO / "data/games/nm26-semifinal"
HW = json.load(open(REPO / "validation/12-hardware-report.json"))["goal"]
GEO = json.load(open(REPO / "data/geometry.json"))
CFG = json.load(open(D / "config.json"))
FPS = 30.0
GX = {"W": HW["placement_mm"]["W"][0], "E": HW["placement_mm"]["E"][0]}
GY = {"W": HW["placement_mm"]["W"][1], "E": HW["placement_mm"]["E"][1]}
HALF = {k: v / 2 for k, v in HW["mouth_width_per_goal_mm"].items()}
GOALS = {c["id"]: c for c in json.load(open(D / "combo-labels.json"))["goals"]}


def depth(x, goal):
    """distance in front of the goal line (positive = in the rink)."""
    return x - GX[goal] if goal == "W" else GX[goal] - x


def load_track(g):
    rows = json.load(open(D / f"g{g}/puck-track-synth-v2.json"))["rows"]
    r = np.array([[x[0], x[1], x[2], x[3]] for x in rows], float)  # frame, t, x, y
    v_in = np.r_[0, np.hypot(*np.diff(r[:, 2:4], axis=0).T) / (np.diff(r[:, 0]) / FPS)]
    v_out = np.r_[v_in[1:], 0]
    return r[~((v_in > 6000) & (v_out > 6000))]


def team_of_end(g, end):
    return CFG["games"][f"g{g}"][f"team_{end}"]
