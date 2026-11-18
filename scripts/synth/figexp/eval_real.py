"""Evaluate the render-trained keypoint model and Tracker v3 against the user's hand labels (PROPOSED).

    python3 scripts/synth/figexp/eval_real.py <model.pt> [report.json]

Ground truth: the user's feet->facing taps (skater-labels.json, 352 'facing' labels, scripts/synth/skater-labels.py).
- New model: every label crop (real broadcast frames; the model never saw a real image or label).
- Tracker v3: data/games/nm26-semifinal/<g>/figure-tracks-v3.json theta at the label frame, where that frame is in the
  committed track (the v3 weights are not published, so the v3 model cannot be run on the other crops).
Errors are heading errors in degrees on the table plane (absolute, wrapped to 180). Test games 3, 5, 7 are the games
v3's own training never used labels from (docs/tracker-v3.md).
"""
import json, math, sys
from pathlib import Path
import cv2, numpy as np, torch
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
import train_kp as T  # noqa: E402

HOME = {"W": 0.0, "E": 180.0}
D = REPO / "data/games/nm26-semifinal"
model = T.make_model(); model.load_state_dict(torch.load(sys.argv[1])); model.eval()
idx = json.loads((REPO / "out/synth/figexp/real/index.json").read_text())
X = [T.to_tensor(cv2.imread(str(REPO / f"out/synth/figexp/real/{r['id']}.png"))) for r in idx]
P = T.predict(model, X)
tracks = {}
rows = []
for p, r in zip(P, idx):
    d = T.decode(p, r["crop_origin_ref_px"])
    row = {"id": r["id"], "pid": r["pid"], "game": r["game"], "frame": r["frame"], "label": r["facing_deg"]}
    for k in ("direct", "stick", "comb"): row[k] = d[k]
    g = r["game"]
    if g not in tracks:
        t = json.loads((D / g / "figure-tracks-v3.json").read_text()); tracks[g] = (t["columns"], {row_[0]: row_ for row_ in t["rows"]} if "rows" in t else None, t)
    cols, byf, t = tracks[g]
    if byf is not None and r["frame"] in byf and f"{r['pid']}_theta_deg" in cols:
        rr = byf[r["frame"]]; th = rr[cols.index(f"{r['pid']}_theta_deg")]; src = rr[cols.index(f"{r['pid']}_src")]
        if th is not None and src != 2: row["v3"] = (th + HOME[r["pid"][0]]) % 360.0; row["v3_src"] = src
    rows.append(row)


def ad(a, b): return abs((a - b + 180.0) % 360.0 - 180.0)


def stats(e):
    e = np.array(e); return {"n": len(e), "median": round(float(np.median(e)), 1), "mean": round(float(e.mean()), 1),
                             "p90": round(float(np.percentile(e, 90)), 1), "p95": round(float(np.percentile(e, 95)), 1),
                             "over30": round(float((e > 30).mean() * 100, ), 1), "flip_over150": round(float((e > 150).mean() * 100), 1)}


out = {}
sets = {"all_352": lambda r: True, "test_games_3_5_7": lambda r: r["game"] in ("g3", "g5", "g7"),
        "v3_frames_all": lambda r: "v3" in r, "v3_frames_test": lambda r: "v3" in r and r["game"] in ("g3", "g5", "g7")}
for name, f in sets.items():
    S = [r for r in rows if f(r)]
    if not S: continue
    out[name] = {k: stats([ad(r[k], r["label"]) for r in S]) for k in ("direct", "stick", "comb")}
    if "v3" in S[0]: out[name]["v3"] = stats([ad(r["v3"], r["label"]) for r in S])
# per-pid breakdown for the combined estimate
out["per_slot_comb"] = {pid: stats([ad(r["comb"], r["label"]) for r in rows if r["pid"] == pid]) for pid in sorted({r["pid"] for r in rows})}
print(json.dumps(out, indent=1))
if len(sys.argv) > 2: Path(sys.argv[2]).write_text(json.dumps({"summary": out, "rows": rows}, indent=1))
