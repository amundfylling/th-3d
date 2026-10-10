"""Which puck and figure tracks the NM26 analysis reads (docs/nm26-new-tracks.md). Pure Python + NumPy.

Defaults (switched 2026-10-10 from the old tracks):
- puck: <game>/puck-track-synth.json, the synthetic puck detector (docs/synthetic-puck.md). x_mm, y_mm = the puck
  centre (12 mm plane). The old <game>/puck-track.json gives the dark blob's centre on the ice plane, about 13 mm
  further +y (away from the camera).
- figures: <game>/figure-tracks-v3.json, tracker v3 (docs/tracker-v3.md). Same columns as the old cleaned tracks
  (<game>/figure-tracks-smooth.json): <fig>_u, <fig>_theta_deg, <fig>_src (u and theta null when unknown).
Environment overrides, used for the before/after runs: NM26_PUCK_TRACK=puck-track.json,
NM26_FIGURE_TRACKS=figure-tracks-smooth.json.

SLOW: the old track's 'disk' kind meant "the puck seen as a dark disk", in practice at rest or slow; the scripts used
it to find holds and touches. The new track has one kind ('det'), so slowness is measured instead: a detection is slow
when the puck moves under SLOW_MM_S to each neighbouring detection within MAX_GAP frames (at least one neighbour).
For the old track 'slow' is exactly kind == 'disk', so the old outputs rebuild unchanged.
"""
import json
import os
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data/games/nm26-semifinal"
FPS = 30.0
PUCK_TRACK = os.environ.get("NM26_PUCK_TRACK", "puck-track-synth.json")
FIGURE_TRACKS = os.environ.get("NM26_FIGURE_TRACKS", "figure-tracks-v3.json")
SLOW_MM_S = 300.0  # the flight threshold of scripts/nm26-passes.py (MIN_SPEED)
MAX_GAP = 3


def puck_path(game):
    return DATA / game / PUCK_TRACK


def figure_path(game):
    return DATA / game / FIGURE_TRACKS


def slow_flags(track):
    """One bool per row of a puck track (see the module docstring)."""
    C = track["columns"]; R = track["rows"]
    ik, ix, iy, i_f = C.index("kind"), C.index("x_mm"), C.index("y_mm"), C.index("frame")
    if not any(r[ik] == "det" for r in R):
        return [r[ik] == "disk" for r in R]
    fr = np.array([r[i_f] for r in R], float)
    xy = np.array([[np.nan if r[ix] is None else r[ix], np.nan if r[iy] is None else r[iy]] for r in R], float)
    out = []
    for k in range(len(R)):
        sp = []
        for j in (k - 1, k + 1):
            if 0 <= j < len(R) and 0 < abs(fr[j] - fr[k]) <= MAX_GAP:
                sp.append(float(np.hypot(*(xy[j] - xy[k]))) / (abs(fr[j] - fr[k]) / FPS))
        out.append(bool(sp) and all(s < SLOW_MM_S for s in sp))
    return out


def load_puck(game):
    """The selected puck track with a 'slow' list next to its rows."""
    T = json.loads(puck_path(game).read_text())
    T["slow"] = slow_flags(T)
    T["file"] = PUCK_TRACK
    return T


def load_figures(game):
    T = json.loads(figure_path(game).read_text())
    T["file"] = FIGURE_TRACKS
    return T
