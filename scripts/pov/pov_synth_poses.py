"""Camera poses of real solved POV frames for the synthetic renders (render_pov_frames.py).

    python3 scripts/pov/pov_synth_poses.py <track.npz> <out.json> [n=1500] [--exclude-eval figures.json]

Frames: solved and with at least 70% of the board boundary in view (as the step-5 baseline), spread evenly over the
game. Frames used by the step-5 baseline (figures.json) and their +-3 neighbours (backgrounds only: compose_pov.py replaces the real figures with the plate) are left out, so the evaluation frames
are not backgrounds of training renders.
"""
import json, sys
import numpy as np

A = sys.argv[1:]
T = np.load(A[0]); R = T["rows"]; intr = T["intr"]
n = int(A[2]) if len(A) > 2 and not A[2].startswith("--") else 1500
good = R[(R[:, 11] > 0) & (R[:, 13] >= 0.7)]
if "--exclude-eval" in A:
    ev = np.array([r["frame"] for r in json.load(open(A[A.index("--exclude-eval") + 1]))["rows"]])
    good = good[np.min(np.abs(good[:, 0][:, None] - ev[None]), 1) > 3]
sel = good[np.linspace(0, len(good) - 1, min(n, len(good))).astype(int)]
json.dump({"lens": {"f": float(intr[0]), "k1": float(intr[1]), "k2": float(intr[2]), "cx": 480.0, "cy": 360.0},
           "frames": [{"frame": int(r[0]), "rv": [float(v) for v in r[1:4]], "tv": [float(v) for v in r[4:7]]} for r in sel]},
          open(A[1], "w"))
print(len(good), "eligible,", len(sel), "written")
