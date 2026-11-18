"""Evaluate P / S / L (docs/streak-puck.md).
  python3 scripts/synth/streak/eval-streak.py synth    # held-out g7 backgrounds, speed bins
  python3 scripts/synth/streak/eval-streak.py goals    # detect every frame of the 25 goal windows -> out/streak/goal-cands.json
Tracking and the last-0.2-s count: eval-goals-track.py"""
import json, sys, random
from pathlib import Path
import numpy as np, torch, cv2
sys.path.insert(0, str(Path(__file__).parent))
from streaklib import *
torch.set_num_threads(4)
OUTD = REPO / "out/streak"
def load(k):
    n = Net(k == "L"); n.load_state_dict(torch.load(OUTD / f"streak-{k}.pt")); n.eval(); return n

def decode(lg, of, st, thr=0.05):
    v, iy, ix = peaks(lg[:, 0]); res = []
    for b in range(lg.shape[0]):
        c = []
        for j in range(v.shape[1]):
            s = float(v[b, j])
            if s < thr: continue
            yy, xx = int(iy[b, j]), int(ix[b, j])
            u, w = (xx + float(of[b, 0, yy, xx])) * STRIDE, (yy + float(of[b, 1, yy, xx])) * STRIDE
            e = (st[b, :, yy, xx] * 16).tolist()
            c.append([u, w, s, e])
        res.append(c)
    return res

def synth():
    real = [s for s in load_real() if s["game"] == "g7"]
    bins = [(0, 300), (300, 1500), (1500, 3000), (3000, 5000), (5000, 7500)]
    nets = {k: load(k) for k in "PSL"}; out = {}
    for lo, hi in bins:
        rows = {k: dict(tp=0, n=0, fp=0, err=[], lenerr=[], spd=[]) for k in nets}; exps = []
        for i in range(160):
            rnd = random.Random(10_000 + i); sp = rnd.uniform(lo, hi); ex = rnd.uniform(0.15, 1.0)
            info = []
            x, t = make_sample(real[i % len(real)], rnd, n_synth=1, info=info, force=dict(speed=sp, exposure=ex))
            if t["msk"].sum() == 0: continue
            iv, iu = np.argwhere(t["msk"].numpy() > 0)[0]
            gt = np.array([(iu + t["off"][0, iv, iu].item()) * STRIDE, (iv + t["off"][1, iv, iu].item()) * STRIDE]); gst = t["st"][:, iv, iu].numpy() * 16
            for k, net in nets.items():
                with torch.no_grad(): lg, of, st = net(x[None])
                c = decode(lg, of, st, 0.3)[0]; r = rows[k]; r["n"] += 1
                hit = [q for q in c if np.hypot(q[0] - gt[0], q[1] - gt[1]) < 12]
                if hit:
                    q = max(hit, key=lambda z: z[2]); r["tp"] += 1; r["err"].append(float(np.hypot(q[0] - gt[0], q[1] - gt[1])))
                    if k != "P":
                        e = q[3]; Lp = np.hypot(e[2] - e[0], e[3] - e[1]); Lt = np.hypot(gst[2] - gst[0], gst[3] - gst[1])
                        r["lenerr"].append(float(Lp - Lt)); r["spd"].append((sp, float(Lp), float(Lt), ex))
                r["fp"] += len(c) - len(hit)
        out[f"{lo}-{hi}"] = {k: dict(n=r["n"], recall=round(r["tp"] / max(r["n"], 1), 3), fp_per_crop=round(r["fp"] / max(r["n"], 1), 3),
                              loc_err_med_px=round(float(np.median(r["err"])), 2) if r["err"] else None,
                              streak_len_err_med_px=round(float(np.median(np.abs(r["lenerr"]))), 2) if r["lenerr"] else None,
                              spd=r["spd"]) for k, r in rows.items()}
        print(lo, hi, {k: (v["recall"], v["fp_per_crop"], v["loc_err_med_px"]) for k, v in out[f"{lo}-{hi}"].items()}, flush=True)
    (OUTD / "synth-eval.json").write_text(json.dumps(out))

def goals():
    G = json.loads((REPO / "data/games/nm26-semifinal/goal-labels.json").read_text())["labels"]
    nets = {k: load(k) for k in "PSL"}; res = {}
    for g in G:
        d = OUTD / "goals" / g["id"]; bg = BGS[g["game"]]; bgh = cv2.resize(bg, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        gf = round(g["goal_video_s"] * 30); ims = {}
        for f in range(gf - 24, gf + 4):
            p = d / f"{f}.jpg"
            if p.exists(): ims[f] = cv2.resize(cv2.imread(str(p)), None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        r = {k: {} for k in nets}
        for f in sorted(ims):
            if f - 1 in ims and f + 1 in ims:
                x = torch.from_numpy((np.concatenate([ims[f - 1], ims[f], ims[f + 1], bgh], 2).astype(np.float32) / 255 - .5).transpose(2, 0, 1).copy())[None]
                for k, net in nets.items():
                    with torch.no_grad(): lg, of, st = net(x)
                    r[k][f] = decode(lg, of, st)[0]
        res[g["id"]] = {"goal_frame": gf, "cands": r}; print(g["id"], flush=True)
    (OUTD / "goal-cands.json").write_text(json.dumps(res))

if __name__ == "__main__":
    {"synth": synth, "goals": goals}[sys.argv[1]]()
