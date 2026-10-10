"""Train the skater-pose model on synthetic crops (docs/synthetic-goalie-pilot.md, skaters).

    /root/venvs/blender/bin/python scripts/synth/train-skater-pose.py [epochs] [--renders d1,d2] [--real-train g1,...]
        [--out name]

Input: out/synth/skaters/<renders>/<seed>.png (RGBA, 200 x 200 around the target skater's pivot) + labels.jsonl,
composited on the fly onto the matching window of a real rink plate (out/synth/skaters/plate_*.png) with the camera
degradations of compose.py and, in a third of the samples, motion blur (real skaters move fast).
Model: ResNet-18 (ImageNet weights); input the 160 x 160 crop plus 10 constant planes, one-hot for the target skater
(the crop shows neighbours too); outputs the skater's pivot (feet) position in the crop (x, y in network-input pixels
/ 160) and (sin, cos) of the rotation relative to the team's home heading. The slot position u follows from the pivot
pixel, the crop origin and the camera (pivot_to_u). Version 1 (models skater-pose-v1a/v1b) predicted u directly and
read it poorly from a small crop (2026-10-09: 17 mm median against the user's feet taps, worse than the crop centre). --real-train adds the user's labelled real crops of those games (data/games/nm26-semifinal/
skater-labels.json, made by skater-labels.py from the label page), the feet tap as their pivot target. Output: out/synth/<name>.pt (default skater-pose) and <name>-report.json.
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


CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
_K, _R, _t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
_Hinv = np.linalg.inv(_K @ np.c_[_R[:, 0], _R[:, 1], _t])
_G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in _G["fixture_paths"]}


def px_to_net(xy):
    """Crop px (200 x 200) -> network target: the to_tensor window [20:190, 15:185] resized to 160, divided by 160."""
    return ((xy[0] - 15) / 170.0, (xy[1] - 20) / 170.0)


def net_to_px(v):
    return (v[0] * 170.0 + 15, v[1] * 170.0 + 20)


def ice_from_ref_px(q):
    w = _Hinv @ np.array([q[0], q[1], 1.0]); return w[:2] / w[2]


def pivot_to_u(pid, crop_xy, crop_origin):
    """Pivot pixel in the crop -> (u on the slot, distance from the slot in mm)."""
    q = ice_from_ref_px((crop_xy[0] + crop_origin[0], crop_xy[1] + crop_origin[1])); P = SLOT[pid]
    seg = np.diff(P, axis=0); L = np.linalg.norm(seg, axis=1); acc = np.r_[0, np.cumsum(L)]; best = (1e9, 0.0)
    for k in range(len(seg)):
        f = np.clip(np.dot(q - P[k], seg[k]) / (L[k] ** 2), 0, 1); d = np.linalg.norm(P[k] + f * seg[k] - q)
        if d < best[0]: best = (d, (acc[k] + f * L[k]) / acc[-1])
    return best[1], best[0]


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
        Ms = []; img = compose(rgba, plate, rnd, out_M=Ms)
        if rnd.random() < 0.33: img = motion_blur(img, rnd)
        th = math.radians(l["theta_deg"]); x, y = Ms[0] @ np.array([*l["pivot_px"], 1.0]); nx, ny = px_to_net((x, y))
        return to_tensor(img, l["pid"]), torch.tensor([nx, ny, math.sin(th), math.cos(th), 1.0], dtype=torch.float32)


def real_labelled():
    """User-labelled real crops: (image, pid, theta_deg, game, id, u_from_feet, feet_px in the crop)."""
    p = REPO / "data/games/nm26-semifinal/skater-labels.json"
    if not p.exists(): return []
    import base64, re
    lab = {r["id"]: r for r in json.loads(p.read_text())["labels"] if r["verdict"] == "facing"}
    crops = {c["id"]: c for c in json.loads((REPO / "data/games/nm26-semifinal/skater-facing-crops.json").read_text())["crops"]}
    html = (REPO / "validation/skater-facing-review.html").read_text()
    D = json.loads(re.search(r"const D = (\[.*?\]);\n", html, re.S).group(1))
    out = []
    for d in D:
        if d["id"] in lab:
            r = lab[d["id"]]; im = cv2.imdecode(np.frombuffer(base64.b64decode(d["img"].split(",")[1]), np.uint8), 1)
            o = crops[d["id"]]["crop_origin_ref_px"]; q = _K @ (_R @ np.array([*r["feet_mm"], 0.0]) + _t); q = q[:2] / q[2] - o
            out.append((im, d["pid"], r["theta_deg"], d["game"], d["id"], r["u"], (float(q[0]), float(q[1]))))
    return out


class RealDS(torch.utils.data.Dataset):
    """Labelled real crops, lightly degraded; the pivot target is the user's feet tap."""
    def __init__(self, items, train, repeat=1): self.items, self.train, self.repeat = items, train, repeat
    def __len__(self): return len(self.items) * self.repeat
    def __getitem__(self, i):
        img, pid, th, _, _, _, feet = self.items[i % len(self.items)]; x, y = feet
        if self.train:
            Ms = []; img = degrade(img, random.Random(np.random.randint(1 << 30)), blur=(0.01, 0.6), jpeg=(60, 92), out_M=Ms)
            x, y = Ms[0] @ np.array([x, y, 1.0])
        nx, ny = px_to_net((x, y)); th = math.radians(th)
        return to_tensor(img, pid), torch.tensor([nx, ny, math.sin(th), math.cos(th), 1.0], dtype=torch.float32)


def model():
    m = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.IMAGENET1K_V1)
    w = m.conv1.weight.data; m.conv1 = nn.Conv2d(3 + len(ORDER), 64, 7, 2, 3, bias=False)
    m.conv1.weight.data[:, :3] = w; m.conv1.weight.data[:, 3:] = 0
    m.fc = nn.Linear(512, 4); return m


def ang_err(p, y):
    """p, y: (..., sin, cos) in their last two columns."""
    a = torch.atan2(p[:, -2], p[:, -1]); b = torch.atan2(y[:, -2], y[:, -1]); d = torch.remainder(a - b + math.pi, 2 * math.pi) - math.pi
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
    tds = DS(TR, True)
    if rtr: tds = torch.utils.data.ConcatDataset([tds, RealDS(rtr, True, repeat=max(1, len(TR) // (6 * len(rtr))))])
    tl = torch.utils.data.DataLoader(tds, batch_size=32, shuffle=True, num_workers=3, persistent_workers=True)
    vl = torch.utils.data.DataLoader(DS(VAL, False), batch_size=64, num_workers=3)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 1e-3, total_steps=EPOCHS * len(tl))
    print(f"renders train {len(TR)} val {len(VAL)}; real train {len(rtr)}, real test {len(rte)}", flush=True)
    hist = []
    for ep in range(EPOCHS):
        net.train(); t0 = time.time(); tot = 0
        for x, y in tl:
            p = net(x)
            loss = 10 * (p[:, :2] - y[:, :2]).abs().sum(1).mean() + ((p[:, 2:4] - y[:, 2:4]) ** 2).sum(1).mean()
            opt.zero_grad(); loss.backward(); opt.step(); sched.step(); tot += loss.item() * len(x)
        net.eval(); E, U, P = [], [], []
        with torch.no_grad():
            for x, y in vl:
                p = net(x); E.append(ang_err(p[:, 2:4], y[:, 2:4])); U.append((p[:, :2] - y[:, :2]).norm(dim=1) * 170)
            RE = {}
            for k in range(0, len(rte), 64):
                b = rte[k:k + 64]; p = net(torch.stack([to_tensor(r[0], r[1]) for r in b]))
                th = torch.tensor([math.radians(r[2]) for r in b]); e = ang_err(p[:, 2:4], torch.stack([th.sin(), th.cos()], 1))
                for r, ei in zip(b, e.tolist()): RE.setdefault(r[1], []).append(ei)
        E, U = torch.cat(E), torch.cat(U)
        h = {"epoch": ep + 1, "train_loss": round(tot / len(tds), 4), "val_theta_median_deg": round(E.median().item(), 2),
             "val_theta_p90_deg": round(E.quantile(0.9).item(), 2), "val_pivot_px_median": round(U.median().item(), 2), "s": round(time.time() - t0)}
        if RE:
            v = np.concatenate([np.array(x) for x in RE.values()])
            h["real_median_deg"] = round(float(np.median(v)), 1); h["real_flipped"] = round(float(np.mean(v > 90)), 3)
            h["real_by_skater"] = {k: round(float(np.median(x)), 1) for k, x in sorted(RE.items())}
        hist.append(h); print(h, flush=True)
        torch.save(net.state_dict(), REPO / f"out/synth/{OUTNAME}.pt")
    json.dump({"args": A, "train": len(TR), "val": len(VAL), "real_train_games": REAL_TRAIN, "real_train": len(rtr), "real_test": len(rte),
               "history": hist}, open(REPO / f"out/synth/{OUTNAME}-report.json", "w"), indent=1)
