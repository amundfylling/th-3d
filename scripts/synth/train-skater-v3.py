"""Skater model v3 for tracker v3: model v2's outputs plus a presence output (docs/tracker-v3.md).

    /root/venvs/blender/bin/python scripts/synth/train-skater-v3.py [epochs] [--real-train g1,g2,g4,g6] [--out skater-pose-v3]

Outputs per crop and target skater (one-hot plane, as v2): pivot pixel (x, y), (sin, cos) of the rotation, and a
presence logit: is the target skater's pivot inside the crop at all? The tracker reads a crop at each candidate the
kit-colour localiser finds and uses presence to drop a wrong candidate.
Training data:
- base renders (out/synth/skaters/train, render-skater-hard.py base = the v2 recipe), target present;
- re-targeted base renders (no extra rendering): the same crop with the one-hot of another skater whose slot runs
  through the crop. Its pivot is in the crop (present, with its own pivot and rotation from the render's labels) or not
  (absent: the localiser locked onto this spot of its slot while the skater stands elsewhere, or the skater is hidden);
- hard-example renders (out/synth/skaters/hard): wings at the boards, crowding, offset and hidden negatives;
- the user's real labelled crops of --real-train games (present), as v2b.
Loss: as v2 for the pose where the target is present, plus binary cross-entropy on presence for all samples.
Validation: renders with seed tens digit 9 (as v2), and the real test games through train-skater-pose.py's real set.
"""
import importlib.util, json, math, random, sys, time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
spec = importlib.util.spec_from_file_location("ts", REPO / "scripts/synth/train-skater-pose.py"); ts = importlib.util.module_from_spec(spec)
_argv = sys.argv; sys.argv = [_argv[0], "0"]; spec.loader.exec_module(ts); sys.argv = _argv
from compose import compose, degrade  # noqa: E402

ORDER = ts.ORDER; A = sys.argv[1:]
def arg(n, d): return A[A.index(n) + 1] if n in A else d
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
HOME = {"W": 0.0, "E": 180.0}
WIN = (25, 175, 30, 180)  # crop px window in which a pivot counts as present (x0, x1, y0, y1)


def project(p):
    q = K @ (R @ np.array([p[0], p[1], 0.0]) + t); return q[:2] / q[2]


def arc_point(P, u):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = u * seg.sum(); acc = np.r_[0, np.cumsum(seg)]
    k = min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1); f = (s - acc[k]) / seg[k]
    return P[k] + f * (P[k + 1] - P[k])


SLOTPX = {p: np.array([project(arc_point(ts.SLOT[p], u)) for u in np.linspace(0, 1, 120)]) for p in ORDER}


# ImageNet ResNet-18 weights. download.pytorch.org (torchvision's IMAGENET1K_V1, used by v2) is blocked by this
# container's network policy (2026-10-10), so v3 starts from timm's ResNet-18 ImageNet weights (RSB recipe A1, same
# architecture and parameter names), fetched from timm's GitHub release:
# https://github.com/rwightman/pytorch-image-models/releases/download/v0.1-rsb-weights/resnet18_a1_0-d63eafa0.pth
INIT = Path("/root/.cache/torch/hub/checkpoints/alt/resnet18_a1.pth")


def model(pretrained=True):
    m = torchvision.models.resnet18(weights=None)
    if pretrained and INIT.exists():
        sd = torch.load(INIT, map_location="cpu"); m.load_state_dict({k: v for k, v in sd.items() if k in m.state_dict()}, strict=False)
    w = m.conv1.weight.data; m.conv1 = nn.Conv2d(3 + len(ORDER), 64, 7, 2, 3, bias=False)
    m.conv1.weight.data[:, :3] = w; m.conv1.weight.data[:, 3:] = 0
    m.fc = nn.Linear(512, 5); return m


def inside(xy): return WIN[0] <= xy[0] <= WIN[1] and WIN[2] <= xy[1] <= WIN[3]


def entries(L, rnd):
    """Training entries: (label, target pid, pivot px or None, theta or None, present)."""
    out = []
    for l in L:
        pres = l.get("present", 1); out.append((l, l["pid"], l["pivot_px"] if pres else None, l["theta_deg"] if pres else None, pres))
        if l.get("kind", "base") != "base": continue
        o = np.array(l["crop_origin_ref_px"], float); others = {x["id"]: x for x in l["others"]}
        cand = [p for p in ORDER if p != l["pid"] and np.any((np.abs(SLOTPX[p][:, 0] - o[0] - 100) < 45) & (np.abs(SLOTPX[p][:, 1] - o[1] - 136) < 45))]
        if not cand: continue
        b = rnd.choice(cand)
        if b in others:
            pv = project(arc_point(ts.SLOT[b], others[b]["u"])) - o
            if inside(pv): out.append((l, b, [float(pv[0]), float(pv[1])], others[b]["theta_deg"], 1)); continue
        out.append((l, b, None, None, 0))
    return out


class DS(torch.utils.data.Dataset):
    def __init__(self, E, train): self.E, self.train = E, train
    def __len__(self): return len(self.E)
    def __getitem__(self, i):
        l, pid, piv, th, pres = self.E[i]; rnd = random.Random(l["seed"] * 7919 + i + (np.random.randint(1 << 20) if self.train else 0))
        rgba = cv2.imread(l["path"], cv2.IMREAD_UNCHANGED); x0, y0 = l["crop_origin_ref_px"]
        plate = rnd.choice(ts.PLATES)[y0 - ts.ROI[1]:y0 - ts.ROI[1] + 200, x0 - ts.ROI[0]:x0 - ts.ROI[0] + 200]
        Ms = []; img = compose(rgba, plate, rnd, out_M=Ms)
        if rnd.random() < 0.33: img = ts.motion_blur(img, rnd)
        y = torch.zeros(6)
        if pres:
            x, yy = Ms[0] @ np.array([*piv, 1.0]); nx, ny = ts.px_to_net((x, yy)); a = math.radians(th)
            y = torch.tensor([nx, ny, math.sin(a), math.cos(a), 1.0, 1.0])
        return ts.to_tensor(img, pid), y


class RealDS(ts.RealDS):
    def __getitem__(self, i):
        x, y = super().__getitem__(i); return x, torch.cat([y, torch.tensor([1.0])])


def loss_fn(p, y):
    pres = y[:, 5]; m = pres > 0.5
    lp = nn.functional.binary_cross_entropy_with_logits(p[:, 4], pres)
    if m.any():
        lp = lp + 10 * (p[m, :2] - y[m, :2]).abs().sum(1).mean() + ((p[m, 2:4] - y[m, 2:4]) ** 2).sum(1).mean()
    return lp


if __name__ == "__main__":
    EPOCHS = int(A[0]) if A and not A[0].startswith("--") else 8
    OUTNAME = arg("--out", "skater-pose-v3"); REAL_TRAIN = [g for g in arg("--real-train", "g1,g2,g4,g6").split(",") if g]
    torch.set_num_threads(4); torch.manual_seed(0); rnd = random.Random(0)
    L = []
    for d in arg("--renders", "train,hard").split(","):
        D = REPO / "out/synth/skaters" / d
        for l in map(json.loads, open(D / "labels.jsonl")):
            l["path"] = str(D / f"{l['seed']}.png")
            if Path(l["path"]).exists(): L.append(l)
    VAL = [l for l in L if (l["seed"] // 10) % 10 == 9]; TR = [l for l in L if (l["seed"] // 10) % 10 != 9]
    ETR, EVA = entries(TR, rnd), entries(VAL, random.Random(1))
    real = ts.real_labelled(); rtr = [r for r in real if r[3] in REAL_TRAIN]; rte = [r for r in real if r[3] not in REAL_TRAIN]
    net = model(); opt = torch.optim.AdamW(net.parameters(), 1e-3, weight_decay=1e-4)
    tds = torch.utils.data.ConcatDataset([DS(ETR, True), RealDS(rtr, True, repeat=max(1, len(ETR) // (6 * max(1, len(rtr)))))])
    tl = torch.utils.data.DataLoader(tds, batch_size=32, shuffle=True, num_workers=3, persistent_workers=True)
    vl = torch.utils.data.DataLoader(DS(EVA, False), batch_size=64, num_workers=3)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 1e-3, total_steps=EPOCHS * len(tl))
    print(f"renders train {len(TR)} -> {len(ETR)} entries ({sum(e[4] == 0 for e in ETR)} absent), val {len(EVA)}; real train {len(rtr)}, test {len(rte)}", flush=True)
    hist = []
    for ep in range(EPOCHS):
        net.train(); t0 = time.time(); tot = 0
        for x, y in tl:
            loss = loss_fn(net(x), y); opt.zero_grad(); loss.backward(); opt.step(); sched.step(); tot += loss.item() * len(x)
        net.eval(); E, U, PR, YP = [], [], [], []
        with torch.no_grad():
            for x, y in vl:
                p = net(x); m = y[:, 5] > 0.5; PR.append(torch.sigmoid(p[:, 4])); YP.append(y[:, 5])
                if m.any(): E.append(ts.ang_err(p[m, 2:4], y[m, 2:4])); U.append((p[m, :2] - y[m, :2]).norm(dim=1) * 170)
            RE = []
            for k in range(0, len(rte), 64):
                b = rte[k:k + 64]; p = net(torch.stack([ts.to_tensor(r[0], r[1]) for r in b]))
                th = torch.tensor([math.radians(r[2]) for r in b]); RE += ts.ang_err(p[:, 2:4], torch.stack([th.sin(), th.cos()], 1)).tolist()
                RE_p = torch.sigmoid(p[:, 4])
        E, U, PR, YP = torch.cat(E), torch.cat(U), torch.cat(PR), torch.cat(YP)
        acc = float(((PR > 0.5).float() == YP).float().mean())
        h = {"epoch": ep + 1, "train_loss": round(tot / len(tds), 4), "val_theta_median_deg": round(E.median().item(), 2),
             "val_pivot_px_median": round(U.median().item(), 2), "val_presence_acc": round(acc, 3),
             "val_absent_called_present": round(float((PR[YP < 0.5] > 0.5).float().mean()), 3),
             "val_present_called_absent": round(float((PR[YP > 0.5] <= 0.5).float().mean()), 3), "s": round(time.time() - t0)}
        if RE: h["real_test_median_deg"] = round(float(np.median(RE)), 1); h["real_test_flipped"] = round(float(np.mean(np.array(RE) > 90)), 3)
        hist.append(h); print(h, flush=True)
        torch.save(net.state_dict(), REPO / f"out/synth/{OUTNAME}.pt")
    json.dump({"args": A, "train_entries": len(ETR), "val_entries": len(EVA), "real_train_games": REAL_TRAIN, "real_train": len(rtr),
               "real_test": len(rte), "history": hist}, open(REPO / f"out/synth/{OUTNAME}-report.json", "w"), indent=1)
