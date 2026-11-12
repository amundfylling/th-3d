"""POV figure model (step 6, docs/pov-videos.md): crop, network and slot-search localiser shared by training and use.

Crop: a 160 x 160 similarity warp of the POV frame (lens-distorted, as recorded) around a point p on a figure's slot:
p's image point goes to ANCHOR, the image direction of the vertical at p points up, and the scale is CROP_PX_PER_MM
at p's distance from the camera (so a figure has the same size in every crop, whatever its distance). The network is
ResNet-18 with 3 + 12 input planes (RGB and a one-hot of the target figure: ten skaters and the two goalies) and five
outputs: the target's pivot in the crop (x, y as a fraction of 160), (sin, cos) of its rotation theta (relative to
its end's home heading, W 0 deg, E 180 deg, as scripts/synth), and a presence logit (is the target's pivot inside
the crop's WIN). Initialised from skater-v3 (the skater planes keep their weights, the goalie planes start at zero).
Localiser: the network at every STEP mm along the target's slot; the best presence wins and is read once more from a
crop centred on its predicted pivot.
"""
import math, os, sys
import numpy as np
import cv2
import torch
import torch.nn as nn
import torchvision

sys.path.insert(0, os.path.dirname(__file__))
from pov_common import REPO, project, slots, resample, W_PX, H_PX

ORDER = ["W-LW", "E-LW", "W-RW", "E-RW", "W-C", "E-C", "W-LD", "E-LD", "W-RD", "E-RD", "W-G", "E-G"]
HOME = {"W": 0.0, "E": 180.0}
CS = 160; ANCHOR = np.array([80.0, 100.0]); CROP_PX_PER_MM = 1.25; WIN = (14, 146, 14, 146)
MEAN = np.array([0.485, 0.456, 0.406]); STD = np.array([0.229, 0.224, 0.225])
STEP = 18.0
SL = slots()


def similarity(src_a, src_b, dst_a, dst_b):
    a = np.asarray(src_b, float) - src_a; b = np.asarray(dst_b, float) - dst_a
    s = np.linalg.norm(b) / max(np.linalg.norm(a), 1e-6)
    th = math.atan2(b[1], b[0]) - math.atan2(a[1], a[0])
    Rm = s * np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    return np.c_[Rm, np.asarray(dst_a, float) - Rm @ src_a]


def crop_M(p, rv, tv, K, D):
    """2 x 3 affine POV px -> crop px for the slot point p (world mm, x y), or None when p is behind or off the frame."""
    P = np.array([[p[0], p[1], 0.0], [p[0], p[1], 50.0]])
    Rm = cv2.Rodrigues(np.asarray(rv, float))[0]; Xc = P @ Rm.T + tv
    if Xc[0, 2] < 50: return None
    f, h = project(P, rv, tv, K, D)
    if not (-40 < f[0] < W_PX + 40 and -40 < f[1] < H_PX + 40): return None
    up = (h - f) / max(np.linalg.norm(h - f), 1e-6)
    s = CROP_PX_PER_MM * np.linalg.norm(Xc.mean(0)) / K[0, 0]
    return similarity(f, f + up, ANCHOR, ANCHOR + [0, -s])


def crop(img, M):
    return cv2.warpAffine(img, M, (CS, CS), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))


def to_tensor(bgr, pid):
    x = (bgr[..., ::-1] / 255.0 - MEAN) / STD
    oh = np.zeros((CS, CS, len(ORDER))); oh[..., ORDER.index(pid)] = 1.0
    return torch.tensor(np.concatenate([x, oh], -1).transpose(2, 0, 1), dtype=torch.float32)


def model(init_v3=True):
    m = torchvision.models.resnet18(weights=None)
    m.conv1 = nn.Conv2d(3 + 10, 64, 7, 2, 3, bias=False); m.fc = nn.Linear(512, 5)
    if init_v3: m.load_state_dict(torch.load(REPO / "out/synth/skater-pose-v3.pt", map_location="cpu"))
    w = m.conv1.weight.data; m.conv1 = nn.Conv2d(3 + len(ORDER), 64, 7, 2, 3, bias=False)
    m.conv1.weight.data[:, :13] = w; m.conv1.weight.data[:, 13:] = 0
    return m


def load(path):
    m = model(False); m.load_state_dict(torch.load(path, map_location="cpu")); return m.eval()


def inside(xy): return WIN[0] <= xy[0] <= WIN[1] and WIN[2] <= xy[1] <= WIN[3]


def inv_affine(M, xy):
    A = np.r_[M, [[0, 0, 1]]]; return np.linalg.solve(A, [xy[0], xy[1], 1.0])[:2]


def backproject(px, rv, tv, K, D, z=0.0):
    n = cv2.undistortPoints(np.asarray(px, float).reshape(1, 1, 2), K, D)[0, 0]
    Rm = cv2.Rodrigues(np.asarray(rv, float))[0]; C = -Rm.T @ np.asarray(tv, float)
    d = Rm.T @ np.r_[n, 1.0]; s = (z - C[2]) / d[2]; return (C + s * d)[:2]


def u_and_dist(pid, xy):
    P = SL[pid]; seg = np.diff(P, axis=0); L = np.linalg.norm(seg, axis=1); acc = np.r_[0, np.cumsum(L)]
    best = (1e9, 0.0)
    for k in range(len(seg)):
        f = np.clip(np.dot(xy - P[k], seg[k]) / (L[k] ** 2), 0, 1); d = np.linalg.norm(P[k] + f * seg[k] - xy)
        if d < best[0]: best = (d, (acc[k] + f * L[k]) / acc[-1])
    return best[1], best[0]


def candidates(pid, step=STEP):
    P = SL[pid]; L = float(np.sum(np.linalg.norm(np.diff(P, axis=0), axis=1)))
    return resample(P, min(step, L / 4)) if L > 4 * step else resample(P, L / 4)


@torch.no_grad()
def run(net, items, batch=128):
    out = []
    for k in range(0, len(items), batch):
        out.append(net(torch.stack(items[k:k + batch])).numpy())
    return np.concatenate(out) if out else np.zeros((0, 5))


def localise(net, img, rv, tv, K, D, pids=ORDER):
    """Per figure: {xy_mm, u, slot_dist_mm, theta_deg, presence, crop M, crop px} at the slot point of highest presence."""
    tens, meta = [], []
    for pid in pids:
        for p in candidates(pid):
            M = crop_M(p, rv, tv, K, D)
            if M is None: continue
            tens.append(to_tensor(crop(img, M), pid)); meta.append((pid, p, M))
    P = run(net, tens)
    best = {}
    for (pid, p, M), q in zip(meta, P):
        if pid not in best or q[4] > best[pid][2][4]: best[pid] = (p, M, q)
    # second read: a crop centred on the first prediction
    tens2, meta2 = [], []
    for pid, (p, M, q) in best.items():
        w = backproject(inv_affine(M, q[:2] * CS), rv, tv, K, D)
        M2 = crop_M(w, rv, tv, K, D)
        if M2 is None: M2, w = M, p
        tens2.append(to_tensor(crop(img, M2), pid)); meta2.append((pid, M2))
    P2 = run(net, tens2); res = {}
    for (pid, M2), q in zip(meta2, P2):
        px = inv_affine(M2, q[:2] * CS); w = backproject(px, rv, tv, K, D); u, d = u_and_dist(pid, w)
        res[pid] = {"xy_mm": [float(w[0]), float(w[1])], "u": float(u), "slot_dist_mm": float(d), "px": [float(px[0]), float(px[1])],
                    "theta_deg": float(math.degrees(math.atan2(q[2], q[3])) % 360), "presence": float(1 / (1 + math.exp(-q[4]))),
                    "presence_first": float(1 / (1 + math.exp(-best[pid][2][4]))), "M": M2}
    return res
