"""Train the synthetic puck detector (docs/synthetic-puck.md).

    /root/venvs/blender/bin/python scripts/synth/train-puck-detector.py [--epochs 12] [--name puck-det-v1]
        [--val-games g3,g7] [--steps 1200] [--threads 4]

Training sample = one crop (384 x 256 stab px) of a real NM26 frame triplet (t-1, t, t+1; scripts/synth/puck-frames.py)
plus the game's background (empty rink), with:
- the real puck: kept and labelled with the current track's position (frames where that track is sure), or erased
  (replaced by the background) where nothing else is near it, so that the image has no real puck;
- 0-2 synthetic pucks from the Blender renders (scripts/synth/render-puck-crops.py): three consecutive motion-blurred
  frames pasted at their rendered place (same camera). Real figures hide them: a real foreground blob covering the
  puck whose lowest pixel (its feet) is nearer the camera than the puck's front edge is drawn over it. The renders'
  light-catcher pixels (light, non-puck) are dropped; the sprite gets camera blur, gain and noise; the crop is
  re-encoded as JPEG.
Input: the three frames and the background at half resolution (12 channels). Output at 1/4 resolution (96 x 64 per
crop): a puck heatmap for the middle frame (CenterNet focal loss, Gaussian sigma 1.5 cells) and a sub-cell offset
(L1). Label point = the puck's top-face centre (renders: exact; real pucks: the current track's blob centre moved by
the mean blob-to-top offset measured on the renders). A synthetic puck hidden for more than 75% of its area is not a
target (its region is ignored in the loss).
Validation: renders with seed % 10 == 9 and the real triplets of --val-games (never trained on), fixed randomness.
Writes out/synth/<name>.pt and out/synth/<name>-report.json.
"""
import json, math, random, sys, time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

REPO = Path(__file__).resolve().parents[2]
A = sys.argv[1:]
def arg(n, d): return A[A.index(n) + 1] if n in A else d
NAME = arg("--name", "puck-det-v1"); EPOCHS = int(arg("--epochs", 12)); STEPS = int(arg("--steps", 1200))
VAL_GAMES = arg("--val-games", "g3,g7").split(","); BS = int(arg("--batch", 16))
torch.set_num_threads(int(arg("--threads", 4)))
CFG = json.loads((REPO / "data/games/nm26-semifinal/config.json").read_text())
X0, Y0 = CFG["roi_px"][:2]                       # stab px = reference video px - (X0, Y0)
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
Kc, Rc, tc = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
R_PUCK = 12.7
RD = REPO / "out/synth/puck/real"; RR = REPO / "out/synth/puck/renders"
CW, CH = 384, 256                                # crop, stab px (full resolution)
STRIDE = 4                                       # output cell = 4 stab px
BLOB_TO_TOP = np.array(json.loads((REPO / "out/synth/puck/blob-offset.json").read_text())["mean_px"]) \
    if (REPO / "out/synth/puck/blob-offset.json").exists() else np.zeros(2)


def project(P):
    P = np.atleast_2d(np.asarray(P, float)); q = (P @ Rc.T + tc) @ Kc.T; return q[:, :2] / q[:, 2:] - [X0, Y0]


# ---------------------------------------------------------------- model
def cbr(i, o, s=1, d=1):
    return nn.Sequential(nn.Conv2d(i, o, 3, s, d, dilation=d, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True))


class PuckNet(nn.Module):
    """Small encoder-decoder: 12 x H x W (half resolution) -> heatmap logit and offset at H/2 x W/2 (1/4 full res)."""

    def __init__(self):
        super().__init__()
        self.e1 = nn.Sequential(cbr(12, 32, 2), cbr(32, 32))            # 1/2 of input
        self.e2 = nn.Sequential(cbr(32, 48, 2), cbr(48, 48))            # 1/4
        self.e3 = nn.Sequential(cbr(48, 64, 2), cbr(64, 64), cbr(64, 64, d=2), cbr(64, 64, d=4))  # 1/8
        self.d2 = cbr(64 + 48, 48)
        self.d1 = nn.Sequential(cbr(48 + 32, 32), cbr(32, 32))
        self.hm = nn.Conv2d(32, 1, 1); self.off = nn.Conv2d(32, 2, 1)
        nn.init.constant_(self.hm.bias, -4.0)

    def forward(self, x):
        a = self.e1(x); b = self.e2(a); c = self.e3(b)
        u = self.d2(torch.cat([F.interpolate(c, size=b.shape[2:], mode="bilinear", align_corners=False), b], 1))
        u = self.d1(torch.cat([F.interpolate(u, size=a.shape[2:], mode="bilinear", align_corners=False), a], 1))
        return self.hm(u), self.off(u)


def to_input(frames3, bg):
    """frames3: three HxWx3 uint8 BGR (full res), bg: HxWx3 -> 12 x H/2 x W/2 float tensor."""
    ims = [cv2.resize(f, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA) for f in (*frames3, bg)]
    x = np.concatenate(ims, 2).astype(np.float32) / 255.0 - 0.5
    return torch.from_numpy(x.transpose(2, 0, 1).copy())


# ---------------------------------------------------------------- data
def load_renders():
    S = []
    for l in open(RR / "labels.jsonl"):
        s = json.loads(l)
        if all((RR / f"{s['seed']}_{k}.png").exists() for k in range(3)): S.append(s)
    return S


def load_real():
    S = []
    for f in sorted(RD.glob("g*.jsonl")):
        S += [json.loads(l) for l in open(f)]
    return S


BGS = {g: cv2.imread(str(REPO / f"data/games/nm26-semifinal/{g}/background.png")) for g in CFG["games"]}


def sprite(s, k, rnd):
    """RGBA float sprite of render s, frame k, light-catcher pixels removed, camera blur and gain."""
    im = cv2.imread(str(RR / f"{s['seed']}_{k}.png"), cv2.IMREAD_UNCHANGED).astype(np.float32)
    rgb, a = im[..., :3], im[..., 3] / 255.0
    lum = rgb.mean(2)
    a[(lum > 100) & (a < 0.9)] = 0.0       # light catcher: the ice reflecting light, not the puck or its shadow
    rgb = np.clip(rgb * rnd.uniform(0.7, 1.5) + rnd.uniform(-6, 10), 0, 255)
    sg = rnd.uniform(0.4, 1.3)
    rgb = cv2.GaussianBlur(rgb, (0, 0), sg); a = cv2.GaussianBlur(a, (0, 0), sg)
    return rgb, a


def occluders(img, bg, rect):
    """Labelled real foreground blobs (figures) in img: strong colour difference from the empty rink."""
    d = np.abs(img.astype(np.int16) - bg.astype(np.int16)).max(2)
    m = (d > 40).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    return lab, st


def make_sample(real, renders, rnd, n_synth=None):
    g, f = real["game"], real["frame"]
    imgs = [cv2.imread(str(RD / f"{g}_{f}_{c}.jpg")) for c in "abc"]
    bg = BGS[g]
    H, W = bg.shape[:2]
    labels = []      # (x, y) stab px of pucks in the middle frame (targets)
    ignore = []      # regions (x, y) not to penalise
    rp = [np.array(p, float) for p in real["track_stab_px"]]
    # the real puck: erase it (all three frames) when it is a resting disk with clean surroundings, else label it
    erase = False
    if all(k == "disk" for k in real["kinds"]) and rnd.random() < 0.5:
        ok = True
        for im, p in zip(imgs, rp):
            x, y = int(p[0]), int(p[1])
            ann = np.zeros((H, W), np.uint8); cv2.ellipse(ann, (x, y), (40, 28), 0, 0, 360, 1, -1); cv2.ellipse(ann, (x, y), (26, 17), 0, 0, 360, 0, -1)
            if np.abs(im.astype(np.int16) - bg.astype(np.int16)).max(2)[ann > 0].mean() > 14: ok = False
        if ok:
            erase = True
            for im, p in zip(imgs, rp):
                m = np.zeros((H, W), np.float32); cv2.ellipse(m, (int(p[0]), int(p[1])), (28, 19), 0, 0, 360, 1, -1)
                m = cv2.GaussianBlur(m, (0, 0), 2)[..., None]
                im[:] = (im * (1 - m) + bg * m).astype(np.uint8)
    if not erase:
        labels.append(rp[1] + BLOB_TO_TOP)
    # synthetic pucks
    if n_synth is None: n_synth = rnd.choices([0, 1, 2], [0.12, 0.68, 0.20])[0]
    syn = []
    for _ in range(n_synth):
        s = renders[rnd.randrange(len(renders))]
        L = [np.array(s["label_ref_px"][k]) - [X0, Y0] for k in range(3)]
        if any(np.hypot(*(L[1] - q)) < 60 for q in labels): continue
        syn.append((s, L))
    # crop window
    targets = [q for q in labels] + [L[1] for _, L in syn]
    r = rnd.random()
    if targets and r < 0.85:
        c = targets[rnd.randrange(len(targets))] if not syn or r < 0.25 else syn[rnd.randrange(len(syn))][1][1]
        cx, cy = c[0] + rnd.uniform(-CW / 2 + 24, CW / 2 - 24), c[1] + rnd.uniform(-CH / 2 + 24, CH / 2 - 24)
    else:
        cx, cy = rnd.uniform(CW / 2, W - CW / 2), rnd.uniform(CH / 2, H - CH / 2)
    x0 = int(np.clip(round(cx - CW / 2), 0, W - CW)); y0 = int(np.clip(round(cy - CH / 2), 0, H - CH))
    for s, L in syn:
        vis_mid = None
        for k in range(3):
            im = imgs[k].astype(np.float32)
            rgb, a = sprite(s, k, rnd)
            sx, sy, sw, sh = s["crop_ref_px"][k]; sx -= X0; sy -= Y0
            # clip to image
            ax0, ay0, ax1, ay1 = max(sx, 0), max(sy, 0), min(sx + sw, W), min(sy + sh, H)
            if ax1 <= ax0 or ay1 <= ay0: continue
            rgb = rgb[ay0 - sy:ay1 - sy, ax0 - sx:ax1 - sx]; a = a[ay0 - sy:ay1 - sy, ax0 - sx:ax1 - sx]
            a_full = a.sum()
            # real figures in front of the puck hide it
            P = s["pos_mm"][k]
            front = project([[P[0], P[1] - R_PUCK, 0.0]])[0][1]  # the puck's near edge on the ice (image row)
            pad = 60
            bx0, by0, bx1, by1 = max(ax0 - pad, 0), max(ay0 - pad, 0), min(ax1 + pad, W), min(ay1 + pad + 90, H)
            lab, st = occluders(imgs[k][by0:by1, bx0:bx1], bg[by0:by1, bx0:bx1], None)
            sub = lab[ay0 - by0:ay1 - by0, ax0 - bx0:ax1 - bx0]
            occ = np.zeros_like(a)
            for q in np.unique(sub[sub > 0]):
                bottom = by0 + st[q][1] + st[q][3]          # lowest row of the blob (its feet)
                if bottom > front + 4: occ[sub == q] = 1.0
            occ = cv2.GaussianBlur(occ, (0, 0), 0.8)
            a = a * (1 - occ)
            patch = im[ay0:ay1, ax0:ax1]
            im[ay0:ay1, ax0:ax1] = patch * (1 - a[..., None]) + rgb * a[..., None]
            imgs[k] = np.clip(im, 0, 255).astype(np.uint8)
            if k == 1:
                puck_a = a_full if a_full > 0 else 1.0
                vis_mid = a.sum() / puck_a
        if vis_mid is not None and vis_mid >= 0.25:
            labels.append(L[1])
        else:
            ignore.append(L[1])
    crops = [im[y0:y0 + CH, x0:x0 + CW] for im in imgs]
    q = rnd.randint(70, 95)
    crops = [cv2.imdecode(cv2.imencode(".jpg", c, [cv2.IMWRITE_JPEG_QUALITY, q])[1], cv2.IMREAD_COLOR) for c in crops]
    if rnd.random() < 0.5:   # brightness / colour drift of the broadcast, the same for the three frames
        gain = rnd.uniform(0.9, 1.1); off = rnd.uniform(-8, 8)
        crops = [np.clip(c.astype(np.float32) * gain + off, 0, 255).astype(np.uint8) for c in crops]
    x = to_input(crops, bg[y0:y0 + CH, x0:x0 + CW])
    hm = np.zeros((CH // STRIDE, CW // STRIDE), np.float32); off = np.zeros((2,) + hm.shape, np.float32)
    msk = np.zeros(hm.shape, np.float32); wt = np.ones(hm.shape, np.float32)
    gy, gx = np.mgrid[0:hm.shape[0], 0:hm.shape[1]]
    for p in labels:
        u, v = (p[0] - x0) / STRIDE, (p[1] - y0) / STRIDE
        if not (0 <= u < hm.shape[1] and 0 <= v < hm.shape[0]): continue
        hm = np.maximum(hm, np.exp(-((gx - u + 0.5) ** 2 + (gy - v + 0.5) ** 2) / (2 * 1.5 ** 2)))
        iu, iv = int(u), int(v); hm[iv, iu] = 1.0; msk[iv, iu] = 1.0; off[:, iv, iu] = [u - iu, v - iv]
    for p in ignore:
        u, v = (p[0] - x0) / STRIDE, (p[1] - y0) / STRIDE
        wt[np.hypot(gx - u, gy - v) < 6] = 0.0
    return x, torch.from_numpy(hm), torch.from_numpy(off), torch.from_numpy(msk), torch.from_numpy(wt)


class DS(torch.utils.data.Dataset):
    def __init__(self, real, renders, n, fixed=False):
        self.real, self.renders, self.n, self.fixed = real, renders, n, fixed

    def __len__(self): return self.n

    def __getitem__(self, i):
        rnd = random.Random(i if self.fixed else random.getrandbits(48))
        return make_sample(self.real[rnd.randrange(len(self.real))], self.renders, rnd)


def focal(logit, hm, wt):
    p = torch.sigmoid(logit).clamp(1e-4, 1 - 1e-4)
    pos = hm.eq(1).float()
    lp = -((1 - p) ** 2) * torch.log(p) * pos
    ln = -((1 - hm) ** 4) * (p ** 2) * torch.log(1 - p) * (1 - pos) * wt
    return (lp.sum() + ln.sum()) / pos.sum().clamp(min=1)


def peaks(logit, k=5, thr=0.1):
    p = torch.sigmoid(logit)
    m = F.max_pool2d(p, 3, 1, 1)
    p = p * (p == m).float()
    B = p.shape[0]
    v, idx = p.view(B, -1).topk(k)
    W = p.shape[-1]
    return v, idx // W, idx % W


def evaluate(net, dl):
    net.eval(); tp = fp = fn = 0; err = []
    with torch.no_grad():
        for x, hm, off, msk, wt in dl:
            lg, of = net(x)
            v, iy, ix = peaks(lg[:, 0])
            for b in range(x.shape[0]):
                gt = [(float(c[1] + off[b, 0, c[0], c[1]]), float(c[0] + off[b, 1, c[0], c[1]])) for c in msk[b].nonzero().tolist()]
                det = [(float(ix[b, j] + of[b, 0, iy[b, j], ix[b, j]]), float(iy[b, j] + of[b, 1, iy[b, j], ix[b, j]])) for j in range(v.shape[1]) if v[b, j] > 0.3]
                used = set()
                for gx_, gy_ in gt:
                    d = [(math.hypot((dx - gx_) * STRIDE, (dy - gy_) * STRIDE), j) for j, (dx, dy) in enumerate(det) if j not in used]
                    d = [z for z in d if z[0] < 12]
                    if d:
                        e, j = min(d); used.add(j); tp += 1; err.append(e)
                    else:
                        fn += 1
                fp += len(det) - len(used)
    net.train()
    return {"recall": round(tp / max(tp + fn, 1), 4), "precision": round(tp / max(tp + fp, 1), 4),
            "loc_err_px_median": round(float(np.median(err)), 2) if err else None, "n_targets": tp + fn}


if __name__ == "__main__":
    renders = load_renders(); real = load_real()
    rtr = [s for s in renders if s["seed"] % 10 != 9]; rva = [s for s in renders if s["seed"] % 10 == 9]
    ftr = [s for s in real if s["game"] not in VAL_GAMES]; fva = [s for s in real if s["game"] in VAL_GAMES]
    print("renders", len(rtr), len(rva), "real triplets", len(ftr), len(fva), "blob->top offset px", BLOB_TO_TOP.tolist())
    dl = torch.utils.data.DataLoader(DS(ftr, rtr, STEPS * BS), batch_size=BS, num_workers=3, persistent_workers=True)
    dv_syn = torch.utils.data.DataLoader(DS(fva, rva, 400, fixed=True), batch_size=BS, num_workers=3)
    net = PuckNet()
    opt = torch.optim.AdamW(net.parameters(), 2e-3, weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.OneCycleLR(opt, 2e-3, total_steps=EPOCHS * STEPS, pct_start=0.15)
    log = []
    for ep in range(EPOCHS):
        t0 = time.time(); L = []
        for x, hm, off, msk, wt in dl:
            lg, of = net(x)
            l1 = focal(lg[:, 0], hm, wt)
            l2 = (torch.abs(of - off) * msk[:, None]).sum() / msk.sum().clamp(min=1)
            loss = l1 + l2
            opt.zero_grad(); loss.backward(); opt.step(); sch.step(); L.append(loss.item())
        ev = evaluate(net, dv_syn)
        log.append({"epoch": ep + 1, "loss": round(float(np.mean(L)), 4), "val": ev, "minutes": round((time.time() - t0) / 60, 1)})
        print(log[-1], flush=True)
        torch.save(net.state_dict(), REPO / f"out/synth/{NAME}.pt")
        (REPO / f"out/synth/{NAME}-report.json").write_text(json.dumps({"name": NAME, "val_games": VAL_GAMES, "renders_train": len(rtr),
            "renders_val": len(rva), "real_train": len(ftr), "real_val": len(fva), "blob_to_top_px": BLOB_TO_TOP.tolist(), "log": log}, indent=1))
