"""Do the saved Edwall traces still agree with another figure-track file (e.g. tracker v3)?

    EDWALL_TRACKS=<tracks.json> /root/venvs/blender/bin/python scripts/edwall-track-compare.py <goal_id>

Rebuilds the ten tracked figures (all but W-RW and W-C, which are designed) from the other track file and checks the
SAVED puck path of data/traces/edwall-<goal_id>.trace.json against them every 0.25 ms (clearance, same rule as the trace
checks). Also reports how far the other file's poses differ from the cleaned tracks the trace used (slot mm and degrees)
over the goal window, and the W-RW / W-C rest and return poses. Prints JSON; writes nothing.
"""
import importlib.util, json, math, os, sys
from pathlib import Path

import numpy as np
from shapely.geometry import Point

REPO = Path(__file__).resolve().parents[1]
gid = sys.argv[1]; other = os.environ["EDWALL_TRACKS"]
sys.path.insert(0, str(REPO / "scripts"))
import edwall_common as ec  # noqa: E402

base = {}
os.environ.pop("EDWALL_TRACKS"); base = ec.tracks(gid); os.environ["EDWALL_TRACKS"] = other; alt = ec.tracks(gid)
argv = sys.argv; sys.argv = [argv[0], gid]
spec = importlib.util.spec_from_file_location("et", REPO / "scripts/edwall-trace.py"); et = importlib.util.module_from_spec(spec); spec.loader.exec_module(et)
sys.argv = argv
sp = et.sp
tr = json.loads((REPO / f"data/traces/edwall-{gid}.trace.json").read_text())
nt = np.array([n["t"] for n in tr["puck"]["nodes"]]); nx = np.array([n["x_mm"] for n in tr["puck"]["nodes"]]); ny = np.array([n["y_mm"] for n in tr["puck"]["nodes"]])
T = et.TGRID; F0 = et.F0
P = np.c_[np.interp(T, nt, nx), np.interp(T, nt, ny)]
S = [et.Sampled(f) for f in et.tracked_figures().values()]
clear = {}
for g in S:
    worst, tw, bad = 1e9, None, []
    for k in range(len(T)):
        if np.hypot(*(P[k] - g.piv[k])) > et.REACH[g.kind] + 20:
            continue
        q = Point(*g.local(k, P[k])); low = sp.LOW[g.kind]; dd = low.boundary.distance(q)
        c = (-dd if low.contains(q) else dd) - et.R_PUCK
        if c < worst: worst, tw = c, float(T[k])
        if c < -et.PEN_TOL: bad.append(float(T[k]))
    clear[g.pid] = {"min_clearance_mm": None if tw is None else round(worst, 2), "t": tw,
                    "overlap_s": [round(bad[0], 4), round(bad[-1], 4)] if bad else None}
frames = sorted(f for f in base if F0 <= f <= F0 + round(T[-1] * 30))
L = {pid: sp.Slot(pid).length if hasattr(sp, "Slot") else None for pid in sp.ASM}
diff = {}
for pid in sp.ASM:
    du, dth, n = [], [], 0
    for f in frames:
        a, b = base[f].get(pid), alt.get(f, {}).get(pid)
        if not a or not b or a[0] is None or b[0] is None: continue
        n += 1; du.append(abs(a[0] - b[0]) * (L[pid] or 1)); dth.append(abs((a[1] - b[1] + 180) % 360 - 180))
    diff[pid] = {"frames": n, "max_slot_mm": round(max(du), 1) if du else None, "median_slot_mm": round(float(np.median(du)), 1) if du else None,
                 "max_deg": round(max(dth), 1) if dth else None, "median_deg": round(float(np.median(dth)), 1) if dth else None}
print(json.dumps({"goal": gid, "other_tracks": other, "window_frames": [frames[0], frames[-1]], "tracked_figure_clearance_vs_saved_puck": clear,
                  "track_difference_in_window": diff, "overlaps": [p for p, v in clear.items() if v["overlap_s"]]}, indent=1))
