"""Compare the hand puck readings (shots/edwall/puck-readings.json) and the saved Edwall traces with another puck track.

    python3 scripts/edwall-puck-compare.py <puck-track.json> [goal_id ...]

Per goal and frame from 30 frames before the user's goal frame to 3 after: the hand reading (back-projected to z = 6 mm),
the other track's x/y, the trace's puck at that frame, and the distances. Prints a table and a JSON summary; writes nothing.
"""
import json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import edwall_common as ec  # noqa: E402

trk = json.loads(Path(sys.argv[1]).read_text()); C = trk["columns"]
det = {int(r[0]): (r[C.index("x_mm")], r[C.index("y_mm")], r[C.index("score")]) for r in trk["rows"]}
R = json.loads((REPO / "shots/edwall/puck-readings.json").read_text())
z = R.get("z_mm", 6.0)
summary = {}
for gid in sys.argv[2:] or ["g2-goal2", "g2-goal3", "g2-goal4"]:
    g = R["goals"][gid] if "goals" in R else R[gid]
    lab = g["label_frame"]; hand = {int(r[0]): r for r in g["readings"]}
    tr = json.loads((REPO / f"data/traces/edwall-{gid}.trace.json").read_text()); F0 = tr["time_base"]["video_frame_at_t0"]
    nt = np.array([n["t"] for n in tr["puck"]["nodes"]]); nx = np.array([n["x_mm"] for n in tr["puck"]["nodes"]]); ny = np.array([n["y_mm"] for n in tr["puck"]["nodes"]])
    rows = []
    print(f"{gid} (label {lab}): frame kind | hand | detector (score) | trace | hand-det, trace-det mm")
    for f in range(lab - 30, lab + 4):
        h = hand.get(f); d = det.get(f); t = (f - F0) / 30
        tp = (float(np.interp(t, nt, nx)), float(np.interp(t, nt, ny))) if 0 <= t <= nt[-1] else None
        hw = None
        if h and h[3] != "hidden":
            hw = [float(v) for v in ec.crop_to_world(np.array([h[1], h[2]], float), z)[0]]
        if not h and not d: continue
        hd = round(float(np.hypot(hw[0] - d[0], hw[1] - d[1])), 1) if hw and d and d[0] is not None else None
        td = round(float(np.hypot(tp[0] - d[0], tp[1] - d[1])), 1) if tp and d and d[0] is not None else None
        rows.append({"frame": f, "kind": h[3] if h else None, "hand_mm": [round(v, 1) for v in hw] if hw else None,
                     "detector_mm": [round(d[0], 1), round(d[1], 1)] if d and d[0] is not None else None, "detector_score": d[2] if d else None,
                     "trace_mm": [round(v, 1) for v in tp] if tp else None, "hand_vs_detector_mm": hd, "trace_vs_detector_mm": td})
        r = rows[-1]; print(f"  {f} {r['kind'] or '-':7s} | {r['hand_mm']} | {r['detector_mm']} ({r['detector_score']}) | {r['trace_mm']} | {hd}, {td}")
    summary[gid] = rows
print(json.dumps({k: {"frames_both": sum(1 for r in v if r["hand_vs_detector_mm"] is not None),
                      "median_hand_vs_detector_mm": float(np.median([r["hand_vs_detector_mm"] for r in v if r["hand_vs_detector_mm"] is not None] or [np.nan]))}
                  for k, v in summary.items()}))
