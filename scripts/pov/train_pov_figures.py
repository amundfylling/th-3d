"""Step 6: train the POV figure model (pov_figures.py) on the composited POV renders (docs/pov-videos.md).

    python3 scripts/pov/train_pov_figures.py <render_dir> <out.pt> [epochs=6] [--lr 1e-3]

Samples (drawn afresh every epoch): a composited frame (compose_pov.py) and a target figure. In 60% the crop is placed
at the target's slot position plus up to 30 mm along the slot (the localiser's search step and error); otherwise at a
random point of its slot. The label is the target's pivot and rotation when its pivot falls inside the crop's WIN
(present), else absent; hidden figures and pivots outside the frame are always absent. Light crop augmentation: rotation +-6 deg, scale +-6%,
shift +-4 px. Loss as skater-v3: 5 x BCE(presence) + 10 x L1(pivot) + squared error of (sin, cos) where present.
Validation: renders with seed tens digit 9 (as scripts/synth), with fixed draws.
"""
import json, math, os, random, sys, time
import numpy as np
import cv2
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(__file__))
import pov_figures as pf
from pov_common import K_of, project
import camera_fit as cf

A = sys.argv[1:]
def arg(n, d): return A[A.index(n) + 1] if n in A else d


def arc_at(P, s):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); acc = np.r_[0, np.cumsum(seg)]; s = float(np.clip(s, 0, acc[-1]))
    k = min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1); f = (s - acc[k]) / seg[k]
    return P[k] + f * (P[k + 1] - P[k]), acc[-1]


class DS(torch.utils.data.Dataset):
    def __init__(self, L, rdir, train, per_frame=12):
        self.L, self.rdir, self.train = L, rdir, train; self.E = [(i, pid) for i in range(len(L)) for pid in pf.ORDER]
    def __len__(self): return len(self.E)
    def __getitem__(self, j):
        i, pid = self.E[j]; l = self.L[i]
        rnd = random.Random((np.random.randint(1 << 30) if self.train else 0) + j * 7919)
        img = cv2.imread(os.path.join(self.rdir, f"{l['seed']}.jpg"))
        lens = l["lens"]; K, D = K_of(lens["f"]), cf.dist_of([lens["k1"], lens["k2"]]); rv, tv = np.array(l["rv"]), np.array(l["tv"])
        fig = l["figures"].get(pid); P = pf.SL[pid]
        for _ in range(20):
            if fig and rnd.random() < 0.6: p, _ = arc_at(P, fig["s_mm"] + rnd.uniform(-30, 30))
            else: p, _ = arc_at(P, rnd.uniform(0, 1e4) % arc_at(P, 0)[1])
            M = pf.crop_M(p, rv, tv, K, D)
            if M is not None: break
        if M is None: M = pf.similarity([0, 0], [0, -1], pf.ANCHOR, pf.ANCHOR + [0, -1])
        if self.train:
            Ma = cv2.getRotationMatrix2D(tuple(pf.ANCHOR), rnd.uniform(-6, 6), rnd.uniform(0.94, 1.06)); Ma[:, 2] += [rnd.uniform(-4, 4), rnd.uniform(-4, 4)]
            M = Ma @ np.r_[M, [[0, 0, 1]]]
        c = pf.crop(img, M)
        if self.train:
            c = np.clip(c.astype(np.float32) * rnd.uniform(0.9, 1.1) + rnd.uniform(-8, 8), 0, 255).astype(np.uint8)
        y = torch.zeros(6)
        if fig:
            q = project(np.array([[*fig["pivot_mm"], 0.0]]), rv, tv, K, D)[0]; xy = M @ np.r_[q, 1.0]
            if pf.inside(xy) and 0 <= q[0] < 960 and 0 <= q[1] < 720:
                a = math.radians(fig["theta_deg"]); y = torch.tensor([xy[0] / pf.CS, xy[1] / pf.CS, math.sin(a), math.cos(a), 1.0, 1.0])
        return pf.to_tensor(c, pid), y


def loss_fn(p, y):
    pres = y[:, 5]; m = pres > 0.5
    lp = 5.0 * nn.functional.binary_cross_entropy_with_logits(p[:, 4], pres)
    if m.any(): lp = lp + 10 * (p[m, :2] - y[m, :2]).abs().sum(1).mean() + ((p[m, 2:4] - y[m, 2:4]) ** 2).sum(1).mean()
    return lp


def ang_err(p, y):
    a = torch.atan2(p[:, 2], p[:, 3]); b = torch.atan2(y[:, 2], y[:, 3]); d = torch.remainder(a - b + math.pi, 2 * math.pi) - math.pi
    return d.abs() * 180 / math.pi


if __name__ == "__main__":
    rdir, out = A[0], A[1]; EPOCHS = int(A[2]) if len(A) > 2 and not A[2].startswith("--") else 6
    torch.set_num_threads(4); torch.manual_seed(0); np.random.seed(0)
    L = [json.loads(s) for s in open(os.path.join(rdir, "labels.jsonl"))]
    L = [l for l in L if os.path.exists(os.path.join(rdir, f"{l['seed']}.jpg"))]
    TR = [l for l in L if (l["seed"] // 10) % 10 != 9]; VA = [l for l in L if (l["seed"] // 10) % 10 == 9]
    net = pf.model(True)
    if "--init" in A: net.load_state_dict(torch.load(arg("--init", "")))
    opt = torch.optim.AdamW(net.parameters(), 1e-3, weight_decay=1e-4)
    tl = torch.utils.data.DataLoader(DS(TR, rdir, True), batch_size=32, shuffle=True, num_workers=3, persistent_workers=True)
    vl = torch.utils.data.DataLoader(DS(VA, rdir, False), batch_size=64, num_workers=3)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, float(arg("--lr", 1e-3)), total_steps=EPOCHS * len(tl))
    print(f"frames train {len(TR)} val {len(VA)}; samples/epoch {len(tl.dataset)}", flush=True)
    hist = []
    for ep in range(EPOCHS):
        net.train(); t0 = time.time(); tot = 0
        for x, y in tl:
            loss = loss_fn(net(x), y); opt.zero_grad(); loss.backward(); opt.step(); sched.step(); tot += loss.item() * len(x)
        net.eval(); E, U, PR, YP, G = [], [], [], [], []
        with torch.no_grad():
            for x, y in vl:
                p = net(x); m = y[:, 5] > 0.5; PR.append(torch.sigmoid(p[:, 4])); YP.append(y[:, 5])
                isg = x[:, 3 + 10:].amax((2, 3)).sum(1) > 0
                if m.any(): E.append(ang_err(p[m], y[m])); U.append((p[m, :2] - y[m, :2]).norm(dim=1) * pf.CS / pf.CROP_PX_PER_MM); G.append(isg[m])
        E, U, G = torch.cat(E), torch.cat(U), torch.cat(G); PR, YP = torch.cat(PR), torch.cat(YP)
        acc = ((PR > 0.5).float() == YP).float().mean().item()
        h = {"epoch": ep + 1, "train_loss": round(tot / len(tl.dataset), 4), "val_presence_acc": round(acc, 4),
             "val_skater_angle_median_deg": round(E[~G].median().item(), 2), "val_skater_angle_p90_deg": round(E[~G].quantile(0.9).item(), 2),
             "val_goalie_angle_median_deg": round(E[G].median().item(), 2) if G.any() else None,
             "val_pivot_median_mm": round(U.median().item(), 2), "val_pivot_p90_mm": round(U.quantile(0.9).item(), 2), "s": round(time.time() - t0)}
        hist.append(h); print(json.dumps(h), flush=True)
        torch.save(net.state_dict(), out)
    json.dump(hist, open(os.path.splitext(out)[0] + ".history.json", "w"), indent=1)
