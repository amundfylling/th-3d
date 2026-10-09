"""Train the skater-pose model on synthetic crops (docs/synthetic-goalie-pilot.md, skaters).

    /root/venvs/blender/bin/python scripts/synth/train-skater-pose.py [epochs] [--renders d1,d2] [--real-train g1,...]
        [--real-u-from model.pt] [--out name]

Input: out/synth/skaters/<renders>/<seed>.png (RGBA, 200 x 200 around the target skater's pivot) + labels.jsonl,
composited on the fly onto the matching window of a real rink plate (out/synth/skaters/plate_*.png) with the camera
degradations of compose.py and, in a third of the samples, motion blur (real skaters move fast).
Model: ResNet-18 (ImageNet weights); input the 160 x 160 crop plus 10 constant planes, one-hot for the target skater
(the crop shows neighbours too); outputs u (slot position 0-1) and (sin, cos) of the rotation relative to the team's
home heading. --real-train adds the user's labelled real crops of those games (data/games/nm26-semifinal/
skater-labels.json, made by skater-labels.py from the label page); --real-u-from gives them slot targets from a model
instead of the feet taps. Output: out/synth/<name>.pt (default skater-pose) and <name>-report.json.
"""
import json
import math
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compose import compose, degrade  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
ORDER = ["W-LW", "E-LW", "W-RW", "E-RW", "W-C", "E-C", "W-LD", "E-LD", "W-RD", "E-RD"]
ROI = (160, 360)
A = sys.argv[1:]
def arg(name, default):
    return A[A.index(name) + 1] if name in A else default
EPOCHS = int(A[0]) if A and not A[0].startswith("--") else 12
DIRS = [REPO / "out/synth/skaters" / d for d in arg("--renders", "train").split(",")]
OUTNAME = arg("--out", "skater-pose"); REAL_TRAIN = [g for g in arg("--real-train", "").split(",") if g]
torch.set_num_threads(4); torch.manual_seed(0)
MEAN = np.array([0.485, 0.456, 0.406]); STD = np.array([0.229, 0.224, 0.225])
SD = REPO / "out/synth/skaters"
PLATES = [cv2.imread(str(f)).astype(np.float32) for f in sorted(SD.glob("plate_*.png"))]


def to_tensor(bgr, pid):
    x = cv2.resize(bgr[20:190, 15:185], (160, 160), interpolation=cv2.INTER_AREA)[..., ::-1] / 255.0
    x = (x - MEAN) / STD
    oh = np.zeros((160, 160, len(ORDER))); oh[..., ORDER.index(pid)] = 1.0
    return torch.tensor(np.concatenate([x, oh], -1).transpose(2, 0, 1), dtype=torch.float32)


def motion_blur(img, rnd):
    n = rnd.randint(3, 9); k = np.zeros((n, n), np.float32); k[n // 2, :] = 1.0 / n
    k = cv2.warpAffine(k, cv2.getRotationMatrix2D((n / 2 - 0.5, n / 2 - 0.5), rnd.uniform(0, 180), 1.0), (n, n)); k /= max(k.sum(), 1e-6)
    return cv2.filter2D(img, -1, k)


class DS(torch.utils.data.Dataset):
    def __init__(self, labels, train): self.l, self.train = labels, train
    def __len__(self): return len(self.l)
    def __getitem__(self, i):
        l = self.l[i]; rnd = random.Random(l["seed"] * 7919 + (np.random.randint(1 << 20) if self.train else 0))
        rgba = cv2.imread(l["path"], cv2.IMREAD_UNCHANGED); x0, y0 = l["crop_origin_ref_px"]
        plate = rnd.choice(PLATES)[y0 - ROI[1]:y0 - ROI[1] + 200, x0 - ROI[0]:x0 - ROI[0] + 200]
        img = compose(rgba, plate, rnd)
        if rnd.random() < 0.33: img = motion_blur(img, rnd)
        th = math.radians(l["theta_deg"])
        return to_tensor(img, l["pid"]), torch.tensor([l["u"], math.sin(th), math.cos(th), 1.0], dtype=torch.float32)


def real_labelled():
    """User-labelled real crops: (image, pid, theta_deg, game, id, u_from_feet)."""
    p = REPO / "data/games/nm26-semifinal/skater-labels.json"
    if not p.exists(): return []
    import base64, re
    lab = {r["id"]: r for r in json.loads(p.read_text())["labels"] if r["verdict"] == "facing"}
    html = (REPO / "validation/skater-facing-review.html").read_text()
    D = json.loads(re.search(r"const D = (\[.*?\]);\n", html, re.S).group(1))
    out = []
    for d in D:
        if d["id"] in lab:
            r = lab[d["id"]]; im = cv2.imdecode(np.frombuffer(base64.b64decode(d["img"].split(",")[1]), np.uint8), 1)
            out.append((im, d["pid"], r["theta_deg"], d["game"], d["id"], r["u"]))
    return out


class RealDS(torch.utils.data.Dataset):
    def __init__(self, items, train, repeat=1, u=None): self.items, self.train, self.repeat, self.u = items, train, repeat, u
    def __len__(self): return len(self.items) * self.repeat
    def __getitem__(self, i):
        img, pid, th, _, _, uf = self.items[i % len(self.items)]
        if self.train: img = degrade(img, random.Random(np.random.randint(1 << 30)), blur=(0.01, 0.6), jpeg=(60, 92))
        uu = self.u[i % len(self.items)] if self.u is not None else uf; th = math.radians(th)
        return to_tensor(img, pid), torch.tensor([uu, math.sin(th), math.cos(th), 1.0], dtype=torch.float32)


def model():
    m = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.IMAGENET1K_V1)
    w = m.conv1.weight.data; m.conv1 = nn.Conv2d(3 + len(ORDER), 64, 7, 2, 3, bias=False)
    m.conv1.weight.data[:, :3] = w; m.conv1.weight.data[:, 3:] = 0
    m.fc = nn.Linear(512, 3); return m


def ang_err(p, y):
    a = torch.atan2(p[:, 1], p[:, 2]); b = torch.atan2(y[:, 1], y[:, 2]); d = torch.remainder(a - b + math.pi, 2 * math.pi) - math.pi
    return d.abs() * 180 / math.pi


if __name__ == "__main__":
    L = []
    for D in DIRS:
        for l in map(json.loads, open(D / "labels.jsonl")):
            l["path"] = str(D / f"{l['seed']}.png")
            if Path(l["path"]).exists(): L.append(l)
    VAL = [l for l in L if (l["seed"] // 10) % 10 == 9]; TR = [l for l in L if (l["seed"] // 10) % 10 != 9]  # every skater in val
    real = real_labelled(); rtr = [r for r in real if r[3] in REAL_TRAIN]; rte = [r for r in real if r[3] not in REAL_TRAIN]
    net = model(); opt = torch.optim.AdamW(net.parameters(), 1e-3, weight_decay=1e-4)
    tds = DS(TR, True); ru = None
    if rtr and "--real-u-from" in A:
        teacher = model(); teacher.load_state_dict(torch.load(REPO / A[A.index("--real-u-from") + 1])); teacher.eval()
        with torch.no_grad(): ru = teacher(torch.stack([to_tensor(r[0], r[1]) for r in rtr]))[:, 0].clamp(0, 1).tolist()
    if rtr: tds = torch.utils.data.ConcatDataset([tds, RealDS(rtr, True, repeat=max(1, len(TR) // (6 * len(rtr))), u=ru)])
    tl = torch.utils.data.DataLoader(tds, batch_size=32, shuffle=True, num_workers=3, persistent_workers=True)
    vl = torch.utils.data.DataLoader(DS(VAL, False), batch_size=64, num_workers=3)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 1e-3, total_steps=EPOCHS * len(tl))
    print(f"renders train {len(TR)} val {len(VAL)}; real train {len(rtr)}, real test {len(rte)}", flush=True)
    hist = []
    for ep in range(EPOCHS):
        net.train(); t0 = time.time(); tot = 0
        for x, y in tl:
            p = net(x)
            loss = ((p[:, 0] - y[:, 0]).abs() * y[:, 3]).sum() / y[:, 3].sum().clamp(min=1) + ((p[:, 1:] - y[:, 1:3]) ** 2).sum(1).mean()
            opt.zero_grad(); loss.backward(); opt.step(); sched.step(); tot += loss.item() * len(x)
        net.eval(); E, U, P = [], [], []
        with torch.no_grad():
            for x, y in vl:
                p = net(x); E.append(ang_err(p, y[:, :3])); U.append((p[:, 0] - y[:, 0]).abs())
            RE = {}
            for k in range(0, len(rte), 64):
                b = rte[k:k + 64]; p = net(torch.stack([to_tensor(r[0], r[1]) for r in b]))
                th = torch.tensor([math.radians(r[2]) for r in b]); e = ang_err(p, torch.stack([th * 0, th.sin(), th.cos()], 1))
                for r, ei in zip(b, e.tolist()): RE.setdefault(r[1], []).append(ei)
        E, U = torch.cat(E), torch.cat(U)
        h = {"epoch": ep + 1, "train_loss": round(tot / len(tds), 4), "val_theta_median_deg": round(E.median().item(), 2),
             "val_theta_p90_deg": round(E.quantile(0.9).item(), 2), "val_u_mae": round(U.mean().item(), 4), "s": round(time.time() - t0)}
        if RE:
            v = np.concatenate([np.array(x) for x in RE.values()])
            h["real_median_deg"] = round(float(np.median(v)), 1); h["real_flipped"] = round(float(np.mean(v > 90)), 3)
            h["real_by_skater"] = {k: round(float(np.median(x)), 1) for k, x in sorted(RE.items())}
        hist.append(h); print(h, flush=True)
        torch.save(net.state_dict(), REPO / f"out/synth/{OUTNAME}.pt")
    json.dump({"args": A, "train": len(TR), "val": len(VAL), "real_train_games": REAL_TRAIN, "real_train": len(rtr), "real_test": len(rte),
               "history": hist}, open(REPO / f"out/synth/{OUTNAME}-report.json", "w"), indent=1)
