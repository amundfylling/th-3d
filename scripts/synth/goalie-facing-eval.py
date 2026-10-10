"""Compare the pilot model with the user's facing labels (docs/synthetic-goalie-pilot.md).

    python3 scripts/synth/goalie-facing-eval.py <labels_dir> [--model out/synth/<name>.pt] [--test-games g3,g5,g7]

With --model (run with /root/venvs/blender/bin/python), that model predicts the crops afresh and the results go to
out/synth/facing-eval-<name>.json; without it, the first pilot model's stored predictions are used. --test-games adds
a summary over those games only (the games a model did not see labels from).

<labels_dir> holds the label page's db documents (collection "facing", one JSON per crop; ArtifactData list with
out_dir). A tap and the pivot are mapped from crop px to the ice (z = 0) through the reference camera; the direction
pivot -> tap is the goalie's facing in world degrees (0 = +x, toward the E end). The model's facing is the mold's +x
axis (docs/players.md: +x facing) at heading HOME[end] + theta. Writes data/games/nm26-semifinal/goalie-facing-labels.json
(labels with world headings) and out/synth/facing-eval.json.
"""
import json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"]); BOX = CAM["goal_crop_boxes_video_px"]
Hinv = np.linalg.inv(K @ np.c_[R[:, 0], R[:, 1], t])
HOME = {"W": 0.0, "E": 180.0}
crops = {c["id"]: c for c in json.loads((REPO / "data/games/nm26-semifinal/goalie-facing-crops.json").read_text())["crops"]}
cand = {c["id"]: c for c in json.loads((REPO / "out/synth/real_val_candidates.json").read_text())}


def ice(px, end):
    w = Hinv @ np.array([px[0] + BOX[end][0], px[1] + BOX[end][1], 1.0]); return w[:2] / w[2]


def d(a, b): return (a - b + 180) % 360 - 180


LABELS, A = sys.argv[1], sys.argv[2:]
MODEL = A[A.index("--model") + 1] if "--model" in A else None
TEST = A[A.index("--test-games") + 1].split(",") if "--test-games" in A else []
if MODEL:
    import importlib.util, torch
    sys.argv = [sys.argv[0], "0"]
    spec = importlib.util.spec_from_file_location("tr", REPO / "scripts/synth/train-goalie-pose.py"); tr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tr)
    net = tr.model(); net.load_state_dict(torch.load(REPO / MODEL)); net.eval()
    imgs = {r[4]: (r[0], r[1]) for r in tr.real_labelled()}
    with torch.no_grad():
        ids = list(imgs); P = net(torch.stack([tr.to_tensor(*imgs[i]) for i in ids])).numpy()
    for i, p in zip(ids, P): crops[i]["model_theta_deg"] = round(float(np.degrees(np.arctan2(p[1], p[2])) % 360), 1)
rows = []
for f in sorted(Path(LABELS).glob("*.json")):
    L = json.loads(f.read_text()); c = crops[L["id"]]
    r = {"id": L["id"], "game": L["game"], "end": L["end"], "verdict": L["verdict"]}
    if L["verdict"] == "facing":
        v = ice(L["tap_px"], L["end"]) - ice(L["pivot_px"], L["end"])
        r["user_facing_deg"] = round(float(np.degrees(np.arctan2(v[1], v[0])) % 360), 1)
        r["tap_distance_mm"] = round(float(np.hypot(*v)), 1)
        r["model_facing_deg"] = round((HOME[L["end"]] + c["model_theta_deg"]) % 360, 1)
        r["model_err_deg"] = round(d(r["model_facing_deg"], r["user_facing_deg"]), 1)
        if L["id"] in cand:
            s = cand[L["id"]]
            r["search_err_deg"] = round(d((HOME[L["end"]] + s["fit"]["theta"]) % 360, r["user_facing_deg"]), 1)
            if s.get("alt"): r["search_alt_err_deg"] = round(d((HOME[L["end"]] + s["alt"]["theta"]) % 360, r["user_facing_deg"]), 1)
    rows.append(r)


def summ(rs, key):
    e = np.abs([r[key] for r in rs if key in r])
    if not len(e): return None
    ax = np.minimum(e, 180 - e)
    return {"n": int(len(e)), "median_deg": round(float(np.median(e)), 1), "p90_deg": round(float(np.percentile(e, 90)), 1),
            "within_20": round(float(np.mean(e <= 20)), 3), "within_45": round(float(np.mean(e <= 45)), 3),
            "front_back_flipped": round(float(np.mean(e > 90)), 3), "axis_median_deg": round(float(np.median(ax)), 1)}


S = {}
groups = [("all", lambda r: True), ("W", lambda r: r["end"] == "W"), ("E", lambda r: r["end"] == "E")]
if TEST: groups += [(f"test_{e}", lambda r, e=e: r["end"] == e and r["game"] in TEST) for e in "WE"]
for name, sel in groups:
    rs = [r for r in rows if sel(r)]
    S[name] = {"labels": len(rs), "unsure": sum(r["verdict"] == "unsure" for r in rs), "model": summ(rs, "model_err_deg"),
               "search_best": summ(rs, "search_err_deg"), "search_alt": summ(rs, "search_alt_err_deg")}
if MODEL:
    json.dump({"model": MODEL, "test_games": TEST, "summary": S, "rows": rows}, open(REPO / f"out/synth/facing-eval-{Path(MODEL).stem}.json", "w"), indent=1)
    print(json.dumps({k: (v["model"] if v else v) for k, v in S.items()}, indent=1)); sys.exit()
(REPO / "data/games/nm26-semifinal/goalie-facing-labels.json").write_text(json.dumps({
    "description": "User facing labels for real NM26 goalie crops (label page validation/goalie-facing-review.html, 2026-10-09). "
                   "user_facing_deg: world heading of the goalie's chest/mask, 0 = +x (toward the E end), counter-clockwise "
                   "seen from above; from the user's tap on the ice through the reference camera. status: user labels, tap "
                   "precision not measured.", "labels": rows}, indent=1) + "\n")
json.dump({"summary": S, "rows": rows}, open(REPO / "out/synth/facing-eval.json", "w"), indent=1)
print(json.dumps(S, indent=1))
