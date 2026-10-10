"""Evaluate the pilot goalie-pose model on real NM26 crops (docs/synthetic-goalie-pilot.md).

    /root/venvs/blender/bin/python scripts/synth/eval-goalie-real.py [out/synth/<name>.pt]

A model other than out/synth/goalie-pose.pt writes out/synth/eval-real-<name>.json and
validation/synth-goalie-pilot-real-<name>.jpg.

There are no hand-labelled real poses (front/back cannot be judged reliably at this resolution). The checks are:
1. silhouette agreement: the IoU-free soft F1 of the model's predicted pose silhouette against the real foreground,
   compared with the best F1 of an exhaustive silhouette search on the same crop (120 crops, all games, both ends);
2. agreement with that search: slot position |du| (mm) and rotation difference folded to 0-90 deg (the silhouette
   leaves front/back open, so only the axis is compared);
3. temporal smoothness: frame-to-frame changes over 10 s of continuous video per end (g5, 2400-2410 s).
Writes out/synth/eval-real.json and validation/synth-goalie-pilot-real.jpg (predictions drawn on real crops).
"""
import json, math, sys
from pathlib import Path
import cv2, numpy as np, torch
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import importlib.util
spec = importlib.util.spec_from_file_location("tr", Path(__file__).resolve().parent / "train-goalie-pose.py"); tr = importlib.util.module_from_spec(spec)
MODEL = sys.argv[1] if len(sys.argv) > 1 else "out/synth/goalie-pose.pt"
SUF = "" if Path(MODEL).stem == "goalie-pose" else "-" + Path(MODEL).stem
sys.argv = [sys.argv[0], "0"]; spec.loader.exec_module(tr)
from fit_goalie import silhouette, column, foreground, fit, SLOT  # noqa: E402
from nm26_common import frames, load, OUT  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
net = tr.model(); net.load_state_dict(torch.load(REPO / MODEL)); net.eval()
plates = {e: cv2.imread(str(REPO / f"out/synth/plates/plate_{e}_raw.png")).astype(np.float32) for e in "WE"}
cols = {e: column(e) for e in "WE"}
slot_len = {e: float(np.linalg.norm(np.diff(SLOT[f"{e}-G"], axis=0), axis=1).sum()) for e in "WE"}


def predict(crops, ends):
    with torch.no_grad():
        p = net(torch.stack([tr.to_tensor(c, e) for c, e in zip(crops, ends)])).numpy()
    return np.clip(p[:, 0], 0, 1), np.degrees(np.arctan2(p[:, 1], p[:, 2])) % 360


def f1(end, u, th, fg):
    s = (silhouette(end, u, th) & cols[end]).astype(np.float32); tp = (s * fg).sum(); pr = tp / max(s.sum(), 1); rc = tp / (fg.sum() + 1e-6)
    return 2 * pr * rc / max(pr + rc, 1e-6)


C = json.load(open(REPO / "out/synth/real_val_candidates.json")); D = {}
crops, ends = [], []
for c in C:
    if c["game"] not in D: D[c["game"]] = np.load(REPO / f"out/synth/real_{c['game']}.npz")
    crops.append(D[c["game"]][c["end"]][c["k"]]); ends.append(c["end"])
U, TH = predict(crops, ends)
rows = []; tiles = []
for c, crop, u, th in zip(C, crops, U, TH):
    fg = foreground(crop, plates[c["end"]], cols[c["end"]])
    fp = f1(c["end"], u, th, fg); fb = c["fit"]["f1"]
    dth = abs((th - c["fit"]["theta"] + 180) % 360 - 180); axis = min(dth, 180 - dth)
    rows.append({"id": c["id"], "end": c["end"], "pred_u": round(float(u), 3), "pred_theta": round(float(th), 1), "pred_f1": round(float(fp), 3),
                 "search_f1": fb, "du_mm": round(abs(float(u) - c["fit"]["u"]) * slot_len[c["end"]], 1), "axis_diff_deg": round(float(axis), 1)})
    if len(tiles) < 24:
        v = crop.copy(); cnt, _ = cv2.findContours(silhouette(c["end"], u, th), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(v, cnt, -1, (0, 255, 0), 1); cv2.putText(v, f"th {th:.0f} f1 {fp:.2f}/{fb:.2f}", (2, 12), 0, 0.35, (0, 0, 0), 1)
        tiles.append(v[15:195, 10:190])
cv2.imwrite(str(REPO / f"validation/synth-goalie-pilot-real{SUF}.jpg"), np.vstack([np.hstack(tiles[i:i + 8]) for i in range(0, 24, 8)]), [cv2.IMWRITE_JPEG_QUALITY, 85])
# temporal smoothness: 10 s of continuous frames per end
F = {f[0]: f for f in load(OUT / "g5/frames.json")}
BOX = tr.json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())["goal_crop_boxes_video_px"]
seq = {"W": [], "E": []}
for i, a in frames(2400.0, 2410.0):
    H = np.r_[F[i][2], 1].reshape(3, 3)
    for e in "WE":
        x0, y0, x1, y1 = BOX[e]; T = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.0]])
        seq[e].append(cv2.warpPerspective(a, T @ H, (x1 - x0, y1 - y0)))
temporal = {}
for e in "WE":
    u, th = predict(seq[e], [e] * len(seq[e]))
    du = np.abs(np.diff(u)) * slot_len[e]; dt = np.abs((np.diff(th) + 180) % 360 - 180)
    temporal[e] = {"frames": len(u), "du_mm_median": round(float(np.median(du)), 2), "du_mm_p95": round(float(np.percentile(du, 95)), 2),
                   "dtheta_deg_median": round(float(np.median(dt)), 2), "dtheta_deg_p95": round(float(np.percentile(dt, 95)), 2),
                   "flips_over_90deg": int((dt > 90).sum())}
R = np.array([[r["pred_f1"], r["search_f1"], r["du_mm"], r["axis_diff_deg"]] for r in rows])
summary = {"crops": len(rows), "pred_f1_median": round(float(np.median(R[:, 0])), 3), "search_f1_median": round(float(np.median(R[:, 1])), 3),
           "pred_f1_ge_90pct_of_search": round(float(np.mean(R[:, 0] >= 0.9 * R[:, 1])), 3),
           "du_mm_median": round(float(np.median(R[:, 2])), 1), "axis_diff_deg_median": round(float(np.median(R[:, 3])), 1),
           "axis_diff_le_20deg": round(float(np.mean(R[:, 3] <= 20)), 3), "temporal": temporal}
json.dump({"summary": summary, "crops": rows}, open(REPO / f"out/synth/eval-real{SUF}.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
