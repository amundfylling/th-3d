"""Train the pilot goalie-pose model on synthetic crops (docs/synthetic-goalie-pilot.md).

    /root/venvs/blender/bin/python scripts/synth/train-goalie-pose.py [epochs] [--renders d1,d2] [--drop-ref-w]
        [--real-train g1,g2,...] [--out name]

Options (defaults reproduce the first pilot run): --renders, render directories under out/synth (default train);
--drop-ref-w, leave out W renders made with the reference kit (the white end fix, kit "nm26" in the labels);
--real-train, add the user-labelled real crops of these games (data/games/nm26-semifinal/goalie-facing-labels.json;
rotation loss only, u unlabelled; the other games' labelled crops are the real test set reported each epoch);
--out, model file name under out/synth (default goalie-pose; the report is <name>-report.json, or train-report.json).

Input: out/synth/train/<seed>.png (RGBA renders) + labels.jsonl, composited on the fly onto the real clean plates
(scripts/synth/compose.py). Output: out/synth/goalie-pose.pt and out/synth/train-report.json.
Model: ResNet-18 (ImageNet weights), input 160 x 160, outputs u (slot position 0-1) and (sin, cos) of the rotation
relative to the team's home heading; one model for both ends, the end as a constant input plane.
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
from compose import compose, degrade, load_plates  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
A = sys.argv[1:]
def opt(name, default):
    return A[A.index(name) + 1] if name in A else default
EPOCHS = int(A[0]) if A and not A[0].startswith("--") else 12
DIRS = [REPO / "out/synth" / d for d in opt("--renders", "train").split(",")]
OUTNAME = opt("--out", "goalie-pose"); REAL_TRAIN = [g for g in opt("--real-train", "").split(",") if g]
torch.set_num_threads(4); torch.manual_seed(0)
L = []
for D in DIRS:
    for l in map(json.loads, open(D / "labels.jsonl")):
        l["path"] = str(D / f"{l['seed']}.png")
        if Path(l["path"]).exists() and not ("--drop-ref-w" in A and l["end"] == "W" and l.get("kit", "ref") != "nm26"): L.append(l)
VAL = [l for l in L if l["seed"] % 10 == 9]; TR = [l for l in L if l["seed"] % 10 != 9]
PLATES = load_plates()
HOME = {"W": 0.0, "E": 180.0}


def real_labelled():
    """User-labelled real crops: (image, end, theta_deg, game)."""
    lab = {r["id"]: r for r in json.loads((REPO / "data/games/nm26-semifinal/goalie-facing-labels.json").read_text())["labels"]
           if r["verdict"] == "facing"}
    crops = json.loads((REPO / "data/games/nm26-semifinal/goalie-facing-crops.json").read_text())["crops"]
    out = []
    for g in sorted({c["game"] for c in crops}):
        z = np.load(REPO / f"out/synth/real_{g}.npz")
        for end in "WE":
            arr = z[end]
            for c in crops:
                if c["game"] == g and c["end"] == end and c["id"] in lab:
                    out.append((arr[c["k"]].copy(), end, (lab[c["id"]]["user_facing_deg"] - HOME[end]) % 360, g, c["id"]))
    return out
MEAN = np.array([0.485, 0.456, 0.406]); STD = np.array([0.229, 0.224, 0.225])


def to_tensor(bgr, end):
    x = cv2.resize(bgr[20:190, 15:185], (160, 160), interpolation=cv2.INTER_AREA)[..., ::-1] / 255.0
    x = (x - MEAN) / STD
    e = np.full((160, 160, 1), 1.0 if end == "E" else -1.0)
    return torch.tensor(np.concatenate([x, e], -1).transpose(2, 0, 1), dtype=torch.float32)


class DS(torch.utils.data.Dataset):
    def __init__(self, labels, train): self.l, self.train = labels, train
    def __len__(self): return len(self.l)
    def __getitem__(self, i):
        l = self.l[i]; rnd = random.Random((l["seed"] * 7919 + (np.random.randint(1 << 20) if self.train else 0)))
        rgba = cv2.imread(l["path"], cv2.IMREAD_UNCHANGED)
        img = compose(rgba, rnd.choice(PLATES[l["end"]]), rnd)
        th = math.radians(l["theta_deg"])
        return to_tensor(img, l["end"]), torch.tensor([l["u"], math.sin(th), math.cos(th), 1.0], dtype=torch.float32)


class RealDS(torch.utils.data.Dataset):
    """Labelled real crops, lightly degraded (they are already broadcast frames); the 4th target (u weight) is 0."""
    def __init__(self, items, train, repeat=1): self.items, self.train, self.repeat = items, train, repeat
    def __len__(self): return len(self.items) * self.repeat
    def __getitem__(self, i):
        img, end, th, _, _ = self.items[i % len(self.items)]
        if self.train: img = degrade(img, random.Random(np.random.randint(1 << 30)), blur=(0.01, 0.6), jpeg=(60, 92))
        th = math.radians(th)
        return to_tensor(img, end), torch.tensor([0.0, math.sin(th), math.cos(th), 0.0], dtype=torch.float32)


def model():
    m = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.IMAGENET1K_V1)
    w = m.conv1.weight.data; m.conv1 = nn.Conv2d(4, 64, 7, 2, 3, bias=False); m.conv1.weight.data[:, :3] = w; m.conv1.weight.data[:, 3:] = 0
    m.fc = nn.Linear(512, 3); return m


def ang_err(p, y):
    a = torch.atan2(p[:, 1], p[:, 2]); b = torch.atan2(y[:, 1], y[:, 2]); d = torch.remainder(a - b + math.pi, 2 * math.pi) - math.pi
    return d.abs() * 180 / math.pi


if __name__ == "__main__":
    net = model(); opt = torch.optim.AdamW(net.parameters(), 1e-3, weight_decay=1e-4)
    real = real_labelled() if (REAL_TRAIN or "--real-train" in A) else []
    rtr = [r for r in real if r[3] in REAL_TRAIN]; rte = [r for r in real if r[3] not in REAL_TRAIN]
    tds = DS(TR, True)
    if rtr: tds = torch.utils.data.ConcatDataset([tds, RealDS(rtr, True, repeat=max(1, len(TR) // (6 * len(rtr))))])
    tl = torch.utils.data.DataLoader(tds, batch_size=32, shuffle=True, num_workers=3, persistent_workers=True)
    vl = torch.utils.data.DataLoader(DS(VAL, False), batch_size=64, num_workers=3)
    if not real and "--no-real-test" not in A: real = real_labelled(); rte = real
    print(f"renders train {len(TR)} val {len(VAL)}; real train {len(rtr)} crops ({len(tds) - len(TR)} samples per epoch), real test {len(rte)}", flush=True)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 1e-3, total_steps=EPOCHS * len(tl))
    hist = []
    for ep in range(EPOCHS):
        net.train(); t0 = time.time(); tot = 0
        for x, y in tl:
            p = net(x); loss = ((p[:, 0] - y[:, 0]).abs() * y[:, 3]).sum() / y[:, 3].sum().clamp(min=1) + ((p[:, 1:] - y[:, 1:3]) ** 2).sum(1).mean()
            opt.zero_grad(); loss.backward(); opt.step(); sched.step(); tot += loss.item() * len(x)
        net.eval(); E, U = [], []
        with torch.no_grad():
            for x, y in vl:
                p = net(x); E.append(ang_err(p, y[:, :3])); U.append((p[:, 0] - y[:, 0]).abs())
            RE = {"W": [], "E": []}
            for k in range(0, len(rte), 64):
                b = rte[k:k + 64]; p = net(torch.stack([to_tensor(r[0], r[1]) for r in b]))
                th = torch.tensor([math.radians(r[2]) for r in b]); e = ang_err(p, torch.stack([th * 0, th.sin(), th.cos()], 1))
                for r, ei in zip(b, e.tolist()): RE[r[1]].append(ei)
        E, U = torch.cat(E), torch.cat(U)
        h = {"epoch": ep + 1, "train_loss": round(tot / len(TR), 4), "val_theta_median_deg": round(E.median().item(), 2),
             "val_theta_p90_deg": round(E.quantile(0.9).item(), 2), "val_u_mae": round(U.mean().item(), 4), "s": round(time.time() - t0)}
        for e in "WE":
            if RE[e]: v = np.array(RE[e]); h[f"real_{e}_median_deg"] = round(float(np.median(v)), 1); h[f"real_{e}_flipped"] = round(float(np.mean(v > 90)), 3)
        hist.append(h); print(h, flush=True)
        torch.save(net.state_dict(), REPO / f"out/synth/{OUTNAME}.pt")
    rep = "train-report.json" if OUTNAME == "goalie-pose" else f"{OUTNAME}-report.json"
    json.dump({"args": A, "train": len(TR), "val": len(VAL), "real_train_games": REAL_TRAIN, "real_train": len(rtr), "real_test": len(rte),
               "real_test_ids": [r[4] for r in rte], "history": hist}, open(REPO / f"out/synth/{rep}", "w"), indent=1)
