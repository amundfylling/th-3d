"""Step 8: score puck-v1 on the user's near-end puck taps (docs/pov-videos.md).

    python3 scripts/pov/score_puck.py <video> <track.npz> <plate.png> <puck-review-crops.json> <taps_dir> <figures.pt> <out.json>

Per tapped picture: the tap goes back to LRF px (origin + tap / scale) and onto the ice (z = 0; the puck's centre is
a few mm above, so the error grows a little away from the camera). puck-v1 runs as in baseline_puck.py (frames t-1,
t, t+1 re-projected into the broadcast's stabilised view). Hit = a peak within HIT_MM of the tap on the ice. Hard-case
tags from the same frame: distance to the nearest figure pivot (the POV figure model) and to the inner board.
Also scored: the top peak after dropping peaks inside a goal cage (the far net is puck-v1's main POV false alarm).
"None in this half" pictures count a false alarm when puck-v1's top peak scores > 0.5 inside the near half.
"""
import glob, json, os, sys
import numpy as np
import cv2
import torch

sys.path.insert(0, os.path.dirname(__file__))
from pov_common import K_of, read_frames, board_points
import camera_fit as cf
import baseline_puck as bp
import pov_figures as pf

video, track, plate, cj, tdir, figm, out = sys.argv[1:8]
HIT_MM = 15.0
T = np.load(track); A = T["rows"]; intr = T["intr"]; K, D = K_of(intr[0]), cf.dist_of(intr[1:])
pics = {p["id"]: p for p in json.load(open(cj))["pictures"]}
taps = [json.load(open(f)) for f in glob.glob(os.path.join(tdir, "*.json"))]
taps = [t for t in taps if t["id"] in pics and t["verdict"] in ("puck", "none")]
net = bp.load_puck_net(); fig = pf.load(figm)
bgh = cv2.resize(bp.stab_background(cv2.imread(plate)), None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
need = sorted({f for t in taps for f in (t["frame"] - 1, t["frame"], t["frame"] + 1)})
F = {}
for k in range(0, len(need), 40): F.update(read_frames(video, need[k:k + 40]))
B = board_points(4.0)
GOAL_X, GOAL_HALF_Y = 300.0, 45.0   # goal cages: |x| > 300 mm, |y| < 45 mm (ASSUMED box around geometry.json's goals)
def in_goal(xy): return abs(xy[0]) > GOAL_X and abs(xy[1]) < GOAL_HALF_Y
rows = []
for t in sorted(taps, key=lambda t: t["frame"]):
    i = t["frame"]; r = A[i]; rv, tv = r[1:4], r[4:7]
    st = [cv2.resize(bp.stab_of_pov(F[j], A[j, 1:4], A[j, 4:7], K, D), None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA) for j in (i - 1, i, i + 1)]
    x = torch.from_numpy((np.concatenate(st + [bgh], 2).astype(np.float32) / 255.0 - 0.5).transpose(2, 0, 1)[None].copy())
    with torch.no_grad(): lg, of = net(x)
    val, iy, ix = bp.peaks(lg[:, 0], k=6); cands = []
    for j in range(6):
        yy, xx = int(iy[0, j]), int(ix[0, j]); pu = (xx + float(of[0, 0, yy, xx])) * bp.STRIDE; pv = (yy + float(of[0, 1, yy, xx])) * bp.STRIDE
        w = bp.Hr_inv @ [pu + bp.SX0, pv + bp.SY0, 1.0]; cands.append((float(val[0, j]), w[:2] / w[2]))
    row = {"id": t["id"], "frame": i, "verdict": t["verdict"], "top_score": round(cands[0][0], 3), "top_xy_mm": [round(float(v), 1) for v in cands[0][1]],
           "cands": [[round(c[0], 3), round(float(c[1][0]), 1), round(float(c[1][1]), 1)] for c in cands]}
    ng = [c for c in cands if not in_goal(c[1])]   # the same peaks with any inside a goal cage dropped (test only, no retraining)
    if t["verdict"] == "puck":
        p = pics[t["id"]]; px = np.array(p["origin_px"]) + np.array(t["tap_px"]) / p["scale"]
        w = pf.backproject(px, rv, tv, K, D); d = [float(np.linalg.norm(c[1] - w)) for c in cands]
        figs = pf.localise(fig, F[i], rv, tv, K, D)
        fd = min([np.linalg.norm(np.array(v["xy_mm"]) - w) for v in figs.values() if v["presence"] > 0.5] or [999])
        dn = float(np.linalg.norm(ng[0][1] - w)) if ng else 999.0
        row |= {"top1_no_goal_hit": dn <= HIT_MM, "tap_xy_mm": [round(float(v), 1) for v in w], "top1_dist_mm": round(d[0], 1), "top1_hit": d[0] <= HIT_MM,
                "top6_hit": min(d) <= HIT_MM, "score_at_tap": round(max([c[0] for c, dd in zip(cands, d) if dd <= HIT_MM] or [0.0]), 3),
                "nearest_figure_mm": round(float(fd), 1), "board_dist_mm": round(float(np.min(np.linalg.norm(B - w, axis=1))), 1)}
        row["case"] = "under/at a figure" if fd < 30 else ("at the boards" if row["board_dist_mm"] < 25 else "free")
    rows.append(row)
P = [r for r in rows if r["verdict"] == "puck"]; summ = {"tapped_puck": len(P), "none_in_half": len(rows) - len(P), "hit_mm": HIT_MM}
for case in ["all", "free", "under/at a figure", "at the boards"]:
    S = [r for r in P if case == "all" or r["case"] == case]
    if S: summ[case] = {"n": len(S), "top1_hit": round(float(np.mean([r["top1_hit"] for r in S])), 3), "top6_hit": round(float(np.mean([r["top6_hit"] for r in S])), 3),
                        "top1_hit_goal_peaks_dropped": round(float(np.mean([r["top1_no_goal_hit"] for r in S])), 3),
                        "top1_hit_and_score_gt_0.5": round(float(np.mean([r["top1_hit"] and r["top_score"] > 0.5 for r in S])), 3)}
N = [r for r in rows if r["verdict"] == "none"]
summ["none_false_alarm_top_gt_0.5_near_half"] = sum(r["top_score"] > 0.5 and r["top_xy_mm"][0] <= 0 for r in N)
json.dump({"status": "PROPOSED", "model": "puck-det-v1", "summary": summ, "rows": rows}, open(out, "w"), indent=1)
print(json.dumps(summ, indent=1))
for r in P: print(r["id"], r["case"], r["top1_dist_mm"], r["top_score"], r["score_at_tap"], r["tap_xy_mm"])
