"""Evaluate a skater-pose model on the user's labelled real crops (docs/synthetic-goalie-pilot.md, skaters).

    /root/venvs/blender/bin/python scripts/synth/eval-skater-real.py <model.pt> [--test-games g3,g5,g7] [--sheet]

Facing error = model heading vs the user's direction tap; slot error = model u vs the user's feet tap (projected onto
the slot), in mm along the slot. Summaries over all labelled crops and over the test games only (the games whose
labels a model did not train on). --sheet draws validation/skater-pose-<name>.jpg: 16 test crops, the user's
direction (pink) and the model's (green) from the user's feet point, the model's slot position (green dot).
Writes out/synth/eval-skater-<name>.json.
"""
import importlib.util, json, math, sys
from pathlib import Path

import cv2
import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
A = sys.argv[1:]; MODEL = A[0]; NAME = Path(MODEL).stem
TEST = A[A.index("--test-games") + 1].split(",") if "--test-games" in A else ["g3", "g5", "g7"]
spec = importlib.util.spec_from_file_location("ts", REPO / "scripts/synth/train-skater-pose.py"); ts = importlib.util.module_from_spec(spec)
argv = sys.argv; sys.argv = [argv[0], "0"]; spec.loader.exec_module(ts); sys.argv = argv
sd = torch.load(REPO / MODEL); V1 = sd["fc.weight"].shape[0] == 3  # v1 predicted u directly; v2 the pivot pixel
net = ts.model()
if V1: net.fc = torch.nn.Linear(512, 3)
net.load_state_dict(sd); net.eval()
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
HOME = {"W": 0.0, "E": 180.0}
labels = {r["id"]: r for r in json.loads((REPO / "data/games/nm26-semifinal/skater-labels.json").read_text())["labels"]}
crops = {c["id"]: c for c in json.loads((REPO / "data/games/nm26-semifinal/skater-facing-crops.json").read_text())["crops"]}


def slot_len(pid): return float(np.linalg.norm(np.diff(SLOT[pid], axis=0), axis=1).sum())


def arc_point(P, u):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = u * seg.sum(); acc = np.r_[0, np.cumsum(seg)]
    k = min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1); f = (s - acc[k]) / seg[k]
    return P[k] + f * (P[k + 1] - P[k])


def proj(p, origin):
    q = K @ (R @ np.array([p[0], p[1], 0.0]) + t); return q[:2] / q[2] - origin


items = ts.real_labelled()
with torch.no_grad():
    P = torch.cat([net(torch.stack([ts.to_tensor(r[0], r[1]) for r in items[k:k + 64]])) for k in range(0, len(items), 64)]).numpy()
rows = []
for (img, pid, th, game, cid, u_user, feet), p in zip(items, P):
    th_m = float(np.degrees(np.arctan2(p[-2], p[-1])) % 360)
    if V1: u_m = float(np.clip(p[0], 0, 1)); piv = None
    else: piv = ts.net_to_px(p[:2]); u_m, _ = ts.pivot_to_u(pid, piv, crops[cid]["crop_origin_ref_px"])
    err = (th_m - th + 180) % 360 - 180
    rows.append({"id": cid, "pid": pid, "game": game, "test": game in TEST, "user_theta": th, "model_theta": round(th_m, 1),
                 "err_deg": round(err, 1), "user_u": u_user, "model_u": round(u_m, 4), "du_mm": round(abs(u_m - u_user) * slot_len(pid), 1),
                 "pivot_px_err": None if piv is None else round(float(np.hypot(piv[0] - feet[0], piv[1] - feet[1])), 1)})


def summ(rs):
    if not rs: return None
    e = np.abs([r["err_deg"] for r in rs]); d = np.array([r["du_mm"] for r in rs])
    return {"n": len(rs), "median_deg": round(float(np.median(e)), 1), "p90_deg": round(float(np.percentile(e, 90)), 1),
            "within_20": round(float(np.mean(e <= 20)), 3), "flipped": round(float(np.mean(e > 90)), 3),
            "slot_mm_median": round(float(np.median(d)), 1), "slot_mm_p90": round(float(np.percentile(d, 90)), 1)}


S = {"all": summ(rows), "test": summ([r for r in rows if r["test"]]),
     "test_by_skater": {pid: summ([r for r in rows if r["test"] and r["pid"] == pid]) for pid in ts.ORDER}}
json.dump({"model": MODEL, "test_games": TEST, "summary": S, "rows": rows}, open(REPO / f"out/synth/eval-skater-{NAME}.json", "w"), indent=1)
print(json.dumps({k: v for k, v in S.items() if k != "test_by_skater"}, indent=1))
for pid, v in S["test_by_skater"].items(): print(pid, v and f"{v['median_deg']} deg, flipped {v['flipped']}, slot {v['slot_mm_median']} mm (n {v['n']})")

if "--sheet" in A:
    import base64, re
    html = (REPO / "validation/skater-facing-review.html").read_text()
    D = {d["id"]: d for d in json.loads(re.search(r"const D = (\[.*?\]);\n", html, re.S).group(1))}
    test = [r for r in rows if r["test"]]; rnd = np.random.default_rng(0)
    pick = sorted(test, key=lambda r: -abs(r["err_deg"]))[:6] + list(rnd.choice([r for r in test], 10, replace=False))
    tiles = []
    for r in pick:
        d = D[r["id"]]; im = cv2.imdecode(np.frombuffer(base64.b64decode(d["img"].split(",")[1]), np.uint8), 1)
        lab = labels[r["id"]]; o = np.array(crops[r["id"]]["crop_origin_ref_px"], float); feet = np.array(lab["feet_mm"])
        for th, col in ((r["user_theta"], (255, 0, 255)), (r["model_theta"], (0, 200, 0))):
            a = math.radians(HOME[r["pid"][0]] + th); q0 = proj(feet, o); q1 = proj(feet + 35 * np.array([math.cos(a), math.sin(a)]), o)
            cv2.arrowedLine(im, tuple(np.int32(q0)), tuple(np.int32(q1)), col, 2, tipLength=0.3)
        cv2.circle(im, tuple(np.int32(proj(arc_point(SLOT[r["pid"]], r["model_u"]), o))), 4, (0, 200, 0), -1)
        cv2.putText(im, f"{r['pid']} {abs(r['err_deg']):.0f}deg {r['du_mm']:.0f}mm", (3, 14), 0, 0.42, (0, 0, 0), 2)
        cv2.putText(im, f"{r['pid']} {abs(r['err_deg']):.0f}deg {r['du_mm']:.0f}mm", (3, 14), 0, 0.42, (255, 255, 255), 1)
        tiles.append(im)
    cv2.imwrite(str(REPO / f"validation/skater-pose-{NAME}.jpg"), np.vstack([np.hstack(tiles[k:k + 4]) for k in range(0, 16, 4)]), [cv2.IMWRITE_JPEG_QUALITY, 85])
