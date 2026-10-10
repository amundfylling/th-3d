"""Evaluate the puck detector on the held-out games (docs/synthetic-puck.md).

    /root/venvs/blender/bin/python scripts/synth/eval-puck-detector.py [--model puck-det-v1] [--n 600]

Crops of the real triplets of the validation games (g3, g7; never trained on) with fixed randomness:
- real: only the real puck where the current track is sure of it (no synthetic puck, never erased), split into
  resting disks and smudges (motion blur);
- synthetic: the real puck erased where possible, one held-out render (seed % 10 == 9) pasted, split by speed and by
  the visible fraction after real figures hide it.
A detection = a heatmap peak >= 0.3 within 12 stab px of the label. Writes out/synth/<model>-eval.json.
"""
import importlib.util, json, math, random, sys
from pathlib import Path
import numpy as np, torch
REPO = Path(__file__).resolve().parents[2]
A = sys.argv[1:]
def arg(n, d): return A[A.index(n) + 1] if n in A else d
MODEL = arg("--model", "puck-det-v1"); N = int(arg("--n", 600))
spec = importlib.util.spec_from_file_location("tp", REPO / "scripts/synth/train-puck-detector.py"); tp = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0]]; spec.loader.exec_module(tp)
net = tp.PuckNet(); net.load_state_dict(torch.load(REPO / f"out/synth/{MODEL}.pt")); net.eval()
R = [s for s in tp.load_renders() if s["seed"] % 10 == 9]; F = [s for s in tp.load_real() if s["game"] in tp.VAL_GAMES]


def run(x, hm, off, msk):
    with torch.no_grad():
        lg, of = net(x[None])
    v, iy, ix = tp.peaks(lg[:, 0], k=6)
    det = [(float(ix[0, j] + of[0, 0, iy[0, j], ix[0, j]]), float(iy[0, j] + of[0, 1, iy[0, j], ix[0, j]])) for j in range(6) if v[0, j] > 0.3]
    gt = [(float(c[1] + off[0, c[0], c[1]]), float(c[0] + off[1, c[0], c[1]])) for c in msk.nonzero().tolist()]
    hit = []
    for gx, gy in gt:
        d = [math.hypot((a - gx) * 4, (b - gy) * 4) for a, b in det]
        hit.append(min(d) if d and min(d) < 12 else None)
    return hit, len(det)


res = {"real_disk": [], "real_smudge": [], "syn": []}; fps = []
for i in range(N):
    rnd = random.Random(10_000 + i); fr = F[rnd.randrange(len(F))]
    x, hm, off, msk, wt = tp.make_sample(fr, R, rnd, n_synth=0, erase_p=0.0)
    hit, nd = run(x, hm, off, msk)
    if hit: res["real_smudge" if "smudge" in fr["kinds"][1] else "real_disk"].append(hit[0])
    fps.append(nd - sum(h is not None for h in hit))
    rnd = random.Random(20_000 + i); info = []
    x, hm, off, msk, wt = tp.make_sample(fr, R, rnd, n_synth=1, erase_p=1.0, info=info)
    if not info or info[0]["visible"] is None: continue
    hit, nd = run(x, hm, off, msk)
    # the synthetic puck is the label nearest the render's position; with a real puck also present, take the best hit
    res["syn"].append({"speed": info[0]["speed"], "visible": info[0]["visible"], "hit": (min([h for h in hit if h is not None], default=None) if info[0]["visible"] >= 0.25 else None)})


def summ(h):
    ok = [e for e in h if e is not None]
    return {"n": len(h), "recall": round(len(ok) / max(len(h), 1), 3), "loc_err_px_median": round(float(np.median(ok)), 2) if ok else None}


out = {"model": MODEL, "val_games": tp.VAL_GAMES, "real_disk": summ(res["real_disk"]), "real_smudge": summ(res["real_smudge"]),
       "false_peaks_per_real_crop": round(float(np.mean(fps)), 3), "synthetic": {}}
S = res["syn"]
for lo, hi in ((0, 300), (300, 1500), (1500, 3000), (3000, 6001)):
    out["synthetic"][f"speed_{lo}-{hi}_mm_s_visible>=50%"] = summ([s["hit"] for s in S if lo <= s["speed"] < hi and s["visible"] >= 0.5])
out["synthetic"]["visible_25-50%"] = summ([s["hit"] for s in S if 0.25 <= s["visible"] < 0.5])
out["synthetic"]["visible_50-90%"] = summ([s["hit"] for s in S if 0.5 <= s["visible"] < 0.9])
out["synthetic"]["visible_>=90%"] = summ([s["hit"] for s in S if s["visible"] >= 0.9])
(REPO / f"out/synth/{MODEL}-eval.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
