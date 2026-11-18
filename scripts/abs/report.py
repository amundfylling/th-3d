"""Metrics and contact sheet for the pilot: python3 scripts/abs/report.py (reads out/abs/g2-goal3-fit.json, -puck.json, labels-eval.json)."""
import sys, json
from pathlib import Path
import numpy as np, torch, cv2
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/abs")); sys.path.insert(0, str(REPO / "scripts"))
import fit, synth
from synth import tc
FIT = json.loads((REPO / "out/abs/g2-goal3-fit.json").read_text()); gid = "g2-goal3"
M = {}
# --- 1. IoU (the optimised cue) and boundary gradient (not optimised)
def boundary_grad(img, fid, u, th):
    g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (0, 0), 1.0).astype(np.float32)
    gm = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    q = (synth.project(synth.world_points(fid, torch.tensor(u), torch.tensor(th), 3000)) - fit.HALFOFF).numpy()
    m = np.zeros((640, 1000), np.uint8); qi = np.round(q).astype(int); ok = (qi[:, 0] >= 0) & (qi[:, 0] < 1000) & (qi[:, 1] >= 0) & (qi[:, 1] < 640)
    m[qi[ok, 1], qi[ok, 0]] = 1; m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    edge = m - cv2.erode(m, np.ones((3, 3), np.uint8))
    return float(gm[edge > 0].mean()) if edge.sum() else float("nan")
rows = []
for fr, figs in FIT.items():
    img = cv2.imread(str(REPO / f"out/abs/{gid}/{fr}.png"))
    for f, v in figs.items():
        rows.append({"frame": int(fr), "fid": f, "iou_v3": v["iou_v3"], "iou_fit": v["iou_fit"],
                     "edge_v3": boundary_grad(img, f, v["u_v3"], v["theta_v3"]), "edge_fit": boundary_grad(img, f, v["u"], v["theta"]),
                     "du": v["u"] - v["u_v3"], "dth": (v["theta"] - v["theta_v3"] + 180) % 360 - 180})
iv, ifit = np.array([r["iou_v3"] for r in rows]), np.array([r["iou_fit"] for r in rows])
ev, ef = np.array([r["edge_v3"] for r in rows]), np.array([r["edge_fit"] for r in rows])
M["figures_per_frame"] = len({r["fid"] for r in rows}); M["frames"] = len(FIT); M["figure_frames"] = len(rows)
M["iou_v3_mean"], M["iou_fit_mean"] = float(iv.mean()), float(ifit.mean())
M["iou_v3_median"], M["iou_fit_median"] = float(np.median(iv)), float(np.median(ifit))
M["iou_improved_share"] = float((ifit > iv + 1e-4).mean())
M["edge_grad_v3_mean"], M["edge_grad_fit_mean"] = float(np.nanmean(ev)), float(np.nanmean(ef))
M["edge_grad_fit_higher_share"] = float(np.nanmean(ef > ev))
M["du_median_abs_mm"] = float(np.median([abs(r["du"]) for r in rows]) * 83)  # slot length ~83 mm
M["dtheta_median_abs_deg"] = float(np.median([abs(r["dth"]) for r in rows]))
M["dtheta_p90_abs_deg"] = float(np.percentile([abs(r["dth"]) for r in rows], 90))
# temporal smoothness of heading (frame to frame)
def steps(key):
    out = []
    for f in {r["fid"] for r in rows}:
        s = sorted([(int(fr), figs[f]) for fr, figs in FIT.items() if f in figs])
        for (a, va), (b, vb) in zip(s, s[1:]):
            if b - a == 1: out.append(abs((vb[key] - va[key] + 180) % 360 - 180) if "theta" in key else abs(vb[key] - va[key]) * 83)
    return np.array(out)
M["theta_step_v3_med_p95_deg"] = [float(np.median(steps("theta_v3"))), float(np.percentile(steps("theta_v3"), 95))]
M["theta_step_fit_med_p95_deg"] = [float(np.median(steps("theta"))), float(np.percentile(steps("theta"), 95))]
M["u_step_v3_med_p95_mm"] = [float(np.median(steps("u_v3"))), float(np.percentile(steps("u_v3"), 95))]
M["u_step_fit_med_p95_mm"] = [float(np.median(steps("u"))), float(np.percentile(steps("u"), 95))]
# --- 2. user labels (held out)
try:
    L = json.loads((REPO / "out/abs/labels-eval.json").read_text())
    for kind in ("skater", "goalie"):
        S = [r for r in L if r["kind"] == kind]
        if not S: continue
        ev3, efit = np.abs([r["err_v3"] for r in S]), np.abs([r["err_fit"] for r in S])
        M[f"labels_{kind}"] = {"n": len(S), "v3_median_err_deg": float(np.median(ev3)), "fit_median_err_deg": float(np.median(efit)),
                               "v3_within20": float((ev3 <= 20).mean()), "fit_within20": float((efit <= 20).mean()),
                               "v3_mean": float(ev3.mean()), "fit_mean": float(efit.mean()),
                               "fit_better_share": float((efit < ev3).mean())}
    su = [r for r in L if r["kind"] == "skater" and r["label_u"] is not None]
    M["labels_skater_u"] = {"n": len(su), "v3_median_abs_mm": float(np.median([abs(r["v3_u"] - r["label_u"]) for r in su]) * 83), "fit_median_abs_mm": float(np.median([abs(r["fit_u"] - r["label_u"]) for r in su]) * 83)}
except FileNotFoundError: pass
# --- 3. puck vs hand readings
try:
    P = json.loads((REPO / "out/abs/g2-goal3-puck.json").read_text())
    hand = {r[0]: r for r in json.loads((REPO / "shots/edwall/puck-readings.json").read_text())["goals"][gid]["readings"] if r[1] is not None}
    d_t, d_f, kinds = [], [], []
    for fr, h in hand.items():
        p = P.get(str(fr))
        if not p: continue
        # hand reading: crop-2x px -> ref px -> world on z = 6 mm
        ref = np.array([[h[1] / 2 + 900, h[2] / 2 + 360]]); w = tc.ref_to_plane(ref, 6.0)[0]
        d_t.append(np.hypot(p["track_x"] - w[0], p["track_y"] - w[1])); d_f.append(np.hypot(p["x_mm"] - w[0], p["y_mm"] - w[1])); kinds.append(h[3])
    M["puck_vs_hand"] = {"n": len(d_t), "track_median_mm": float(np.median(d_t)), "fit_median_mm": float(np.median(d_f)), "per_frame": [(k, round(a, 1), round(b, 1)) for k, a, b in zip(kinds, d_t, d_f)]}
    M["puck_iou"] = {"track_mean": float(np.mean([p["iou_track"] for p in P.values()])), "fit_mean": float(np.mean([p["iou_fit"] for p in P.values()]))}
    M["puck_shift_median_mm"] = float(np.median([np.hypot(p["x_mm"] - p["track_x"], p["y_mm"] - p["track_y"]) for p in P.values()]))
except FileNotFoundError: pass
(REPO / "out/abs/metrics.json").write_text(json.dumps(M, indent=1)); print(json.dumps(M, indent=1))
