"""Train the pilot goalie-pose model on synthetic crops (docs/synthetic-goalie-pilot.md).

    /root/venvs/blender/bin/python scripts/synth/train-goalie-pose.py [epochs]

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
from compose import compose, load_plates  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
D = REPO / "out/synth/train"
EPOCHS = int(sys.argv[1]) if len(sys.argv) > 1 else 12
torch.set_num_threads(4); torch.manual_seed(0)
L = [json.loads(l) for l in open(D / "labels.jsonl")]
L = [l for l in L if (D / f"{l['seed']}.png").exists()]
VAL = [l for l in L if l["seed"] % 10 == 9]; TR = [l for l in L if l["seed"] % 10 != 9]
PLATES = load_plates()
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
        rgba = cv2.imread(str(D / f"{l['seed']}.png"), cv2.IMREAD_UNCHANGED)
        img = compose(rgba, rnd.choice(PLATES[l["end"]]), rnd)
        th = math.radians(l["theta_deg"])
        return to_tensor(img, l["end"]), torch.tensor([l["u"], math.sin(th), math.cos(th)], dtype=torch.float32)


def model():
    m = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.IMAGENET1K_V1)
    w = m.conv1.weight.data; m.conv1 = nn.Conv2d(4, 64, 7, 2, 3, bias=False); m.conv1.weight.data[:, :3] = w; m.conv1.weight.data[:, 3:] = 0
    m.fc = nn.Linear(512, 3); return m


def ang_err(p, y):
    a = torch.atan2(p[:, 1], p[:, 2]); b = torch.atan2(y[:, 1], y[:, 2]); d = torch.remainder(a - b + math.pi, 2 * math.pi) - math.pi
    return d.abs() * 180 / math.pi


if __name__ == "__main__":
    net = model(); opt = torch.optim.AdamW(net.parameters(), 1e-3, weight_decay=1e-4)
    tl = torch.utils.data.DataLoader(DS(TR, True), batch_size=32, shuffle=True, num_workers=3, persistent_workers=True)
    vl = torch.utils.data.DataLoader(DS(VAL, False), batch_size=64, num_workers=3)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 1e-3, total_steps=EPOCHS * len(tl))
    hist = []
    for ep in range(EPOCHS):
        net.train(); t0 = time.time(); tot = 0
        for x, y in tl:
            p = net(x); loss = (p[:, 0] - y[:, 0]).abs().mean() + ((p[:, 1:] - y[:, 1:]) ** 2).sum(1).mean()
            opt.zero_grad(); loss.backward(); opt.step(); sched.step(); tot += loss.item() * len(x)
        net.eval(); E, U = [], []
        with torch.no_grad():
            for x, y in vl:
                p = net(x); E.append(ang_err(p, y)); U.append((p[:, 0] - y[:, 0]).abs())
        E, U = torch.cat(E), torch.cat(U)
        h = {"epoch": ep + 1, "train_loss": round(tot / len(TR), 4), "val_theta_median_deg": round(E.median().item(), 2),
             "val_theta_p90_deg": round(E.quantile(0.9).item(), 2), "val_u_mae": round(U.mean().item(), 4), "s": round(time.time() - t0)}
        hist.append(h); print(h, flush=True)
        torch.save(net.state_dict(), REPO / "out/synth/goalie-pose.pt")
    json.dump({"train": len(TR), "val": len(VAL), "history": hist}, open(REPO / "out/synth/train-report.json", "w"), indent=1)
