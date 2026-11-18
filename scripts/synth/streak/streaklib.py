"""Streak puck detector experiment (docs/streak-puck.md): exposure-blur generator, nets, targets.
Pure numpy/cv2/torch; no Blender. The puck is drawn analytically as a dark opaque disk with a side wall, in the NM26
reference camera, and its motion blur is the exact time average of the disk over the shutter-open interval."""
import json, math, random, sys
from pathlib import Path
import cv2, numpy as np, torch, torch.nn as nn, torch.nn.functional as F

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import table_common  # noqa: E402
CFG = json.loads((REPO / "data/games/nm26-semifinal/config.json").read_text())
X0, Y0 = CFG["roi_px"][:2]
Kc, Rc, tc = table_common.ref_camera()
FPS = 30.0
R_PUCK, TOP_MM = 12.7, 12.0
CW, CH, STRIDE = 384, 256, 4
RD = REPO / "out/streak/train"
BGS = {g: cv2.imread(str(REPO / f"data/games/nm26-semifinal/{g}/background.png")) for g in CFG["games"]}
ICE_X, ICE_Y = 410.0, 215.0   # ice half extents used for sampling (mm), inside the boards


def proj(P, z=TOP_MM):
    """world mm (N,2) at height z -> stab px (N,2)."""
    P = np.atleast_2d(np.asarray(P, float)); W = np.c_[P, np.full(len(P), z)]
    q = (W @ Rc.T + tc) @ Kc.T
    return q[:, :2] / q[:, 2:] - [X0, Y0]


def puck_axes(P):
    """semi-axes (px) of the top-face ellipse at world point P, and the px height of the side wall."""
    a = proj([[P[0] - R_PUCK, P[1]], [P[0] + R_PUCK, P[1]]]); b = proj([[P[0], P[1] - R_PUCK], [P[0], P[1] + R_PUCK]])
    lo = proj([P], 0.0)[0] - proj([P], TOP_MM)[0]
    return abs(a[1, 0] - a[0, 0]) / 2, abs(b[1, 1] - b[0, 1]) / 2, abs(lo[1])


def render_alpha(path_px, axes, shape, origin, n_sub):
    """Time-averaged opacity of the puck along path_px (K,2 stab px at K sub-exposure times) in a window."""
    h, w = shape; acc = np.zeros((h, w), np.float32)
    rx, ry, hw = axes
    SS = 1
    for p in path_px:
        m = np.zeros((h, w), np.uint8)
        c = (int(round((p[0] - origin[0]) * 8)), int(round((p[1] - origin[1]) * 8)))
        cv2.ellipse(m, c, (int(rx * 8), int(ry * 8)), 0, 0, 360, 1, -1, cv2.LINE_8, 3)
        c2 = (c[0], c[1] + int(hw * 8))
        cv2.ellipse(m, c2, (int(rx * 8), int(ry * 8)), 0, 0, 360, 1, -1, cv2.LINE_8, 3)
        cv2.rectangle(m, (c[0] - int(rx * 8), c[1]), (c[0] + int(rx * 8), c2[1]), 1, -1, cv2.LINE_8, 3)
        acc += m
    return acc / len(path_px)


def sample_motion(rnd):
    """speed (mm/s), exposure fraction, direction (rad). Speeds: 20% slow, 30% medium, 50% shot speed (log-uniform)."""
    u = rnd.random()
    if u < 0.2: sp = rnd.uniform(0, 300)
    elif u < 0.5: sp = math.exp(rnd.uniform(math.log(300), math.log(1500)))
    else: sp = math.exp(rnd.uniform(math.log(1500), math.log(7500)))
    return sp, rnd.uniform(0.15, 1.0), rnd.uniform(0, 2 * math.pi)


def load_real():
    S = []
    for f in sorted(RD.glob("g*.jsonl")):
        S += [json.loads(l) for l in open(f) if l.strip()]
    return S


def make_sample(real, rnd, n_synth=None, info=None, force=None):
    """-> x (12,H/2,W/2), targets dict. force = dict(speed=, exposure=, dir=) for the evaluation sets."""
    g, f = real["game"], real["frame"]
    imgs = [cv2.imread(str(RD / f"{g}_{f}_{c}.jpg")).astype(np.float32) for c in "abc"]
    bg = BGS[g]; H, W = bg.shape[:2]
    uv = np.array(real["uv"], float)
    # erase the real puck in all three frames (it is still): blend the empty rink in over its blob
    for im in imgs:
        x, y = int(uv[0]), int(uv[1] + 8)
        if 40 <= x < W - 40 and 30 <= y < H - 30:
            m = np.zeros((60, 80), np.float32); cv2.ellipse(m, (40, 30), (30, 20), 0, 0, 360, 1, -1)
            m = cv2.GaussianBlur(m, (0, 0), 2.5)[..., None]; sl = np.s_[y - 30:y + 30, x - 40:x + 40]
            im[sl] = im[sl] * (1 - m) + bg[sl].astype(np.float32) * m
    segs = []     # per synthetic puck: dict
    n = rnd.choices([0, 1, 2], [0.1, 0.7, 0.2])[0] if n_synth is None else n_synth
    for _ in range(n):
        sp, ex, th = sample_motion(rnd)
        if force:
            sp, ex, th = force.get("speed", sp), force.get("exposure", ex), force.get("dir", th)
        v = np.array([math.cos(th), math.sin(th)]) * sp
        for _try in range(30):
            P1 = np.array([rnd.uniform(-ICE_X, ICE_X), rnd.uniform(-ICE_Y, ICE_Y)])
            Ps = [P1 + v * (k - 1) / FPS for k in range(3)]
            lo, hi = P1 - v * (0.5 + ex / 2) / FPS, P1 + v * (0.5 + ex / 2) / FPS
            if all(abs(q[0]) < ICE_X + 30 and abs(q[1]) < ICE_Y + 15 for q in (lo, hi)): break
        else:
            continue
        segs.append(dict(P=P1, v=v, sp=sp, ex=ex))
    # crop window around a target
    targets_c = [proj([s["P"]])[0] for s in segs]
    if targets_c and rnd.random() < 0.85:
        c = targets_c[rnd.randrange(len(targets_c))]
        cx, cy = c[0] + rnd.uniform(-CW / 2 + 40, CW / 2 - 40), c[1] + rnd.uniform(-CH / 2 + 30, CH / 2 - 30)
    else:
        cx, cy = rnd.uniform(CW / 2, W - CW / 2), rnd.uniform(CH / 2, H - CH / 2)
    x0 = int(np.clip(round(cx - CW / 2), 0, W - CW)); y0 = int(np.clip(round(cy - CH / 2), 0, H - CH))
    crops = [im[y0:y0 + CH, x0:x0 + CW].copy() for im in imgs]
    labels = []
    for s in segs:
        col = rnd.uniform(12, 70); gain = rnd.uniform(0.8, 1.3)
        sg = rnd.uniform(0.4, 1.2)
        axes = puck_axes(s["P"])
        nsub = 41
        for k in range(3):
            tk = (k - 1) / FPS
            ts = tk + (np.arange(nsub) / (nsub - 1) - 0.5) * s["ex"] / FPS     # shutter open interval
            path = proj(s["P"][None] + s["v"][None] * ts[:, None])
            a = render_alpha(path, axes, (CH, CW), (x0, y0), nsub)
            a = cv2.GaussianBlur(a, (0, 0), sg)
            crops[k] = crops[k] * (1 - a[..., None]) + (col * gain) * a[..., None]
        ts = np.array([-0.5, 0, 0.5]) * s["ex"] / FPS
        pp = proj(s["P"][None] + s["v"][None] * ts[:, None]) - [x0, y0]       # open, centre, close of the middle frame
        labels.append(dict(open=pp[0], c=pp[1], close=pp[2], sp=s["sp"], ex=s["ex"]))
        if info is not None: info.append(dict(speed=s["sp"], exposure=s["ex"], streak_px=float(np.hypot(*(pp[2] - pp[0])))))
    # still real puck erased; synthetic pucks only are targets
    q = rnd.randint(70, 95)
    crops = [cv2.imdecode(cv2.imencode(".jpg", np.clip(c, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, q])[1], cv2.IMREAD_COLOR) for c in crops]
    if rnd.random() < 0.5:
        gain = rnd.uniform(0.9, 1.1); off = rnd.uniform(-8, 8)
        crops = [np.clip(c.astype(np.float32) * gain + off, 0, 255).astype(np.uint8) for c in crops]
    x = to_input(crops, bg[y0:y0 + CH, x0:x0 + CW])
    return x, targets(labels)


def to_input(frames3, bg):
    ims = [cv2.resize(f, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA) for f in (*frames3, bg)]
    x = np.concatenate(ims, 2).astype(np.float32) / 255.0 - 0.5
    return torch.from_numpy(x.transpose(2, 0, 1).copy())


def targets(labels):
    """Heatmaps for the point model (Gaussian at the centre) and the streak model (Gaussian ridge along the segment), centre
    offset, and the streak endpoints relative to the centre (stab px / 16) at the centre cell."""
    hh, ww = CH // STRIDE, CW // STRIDE
    hm_p = np.zeros((hh, ww), np.float32); hm_s = np.zeros((hh, ww), np.float32)
    off = np.zeros((2, hh, ww), np.float32); st = np.zeros((4, hh, ww), np.float32); msk = np.zeros((hh, ww), np.float32)
    gy, gx = np.mgrid[0:hh, 0:ww]
    for L in labels:
        u, v = L["c"][0] / STRIDE, L["c"][1] / STRIDE
        if not (0 <= u < ww and 0 <= v < hh): continue
        hm_p = np.maximum(hm_p, np.exp(-((gx - u + 0.5) ** 2 + (gy - v + 0.5) ** 2) / (2 * 1.5 ** 2)))
        a = np.array(L["open"]) / STRIDE; b = np.array(L["close"]) / STRIDE
        ab = b - a; l2 = max(float(ab @ ab), 1e-6)
        t = np.clip(((gx + 0.5 - a[0]) * ab[0] + (gy + 0.5 - a[1]) * ab[1]) / l2, 0, 1)
        d2 = (gx + 0.5 - (a[0] + t * ab[0])) ** 2 + (gy + 0.5 - (a[1] + t * ab[1])) ** 2
        hm_s = np.maximum(hm_s, np.exp(-d2 / (2 * 1.5 ** 2)))
        iu, iv = int(u), int(v)
        hm_p[iv, iu] = 1.0; hm_s[iv, iu] = 1.0; msk[iv, iu] = 1.0; off[:, iv, iu] = [u - iu, v - iv]
        st[:, iv, iu] = np.r_[(np.array(L["open"]) - L["c"]) / 16, (np.array(L["close"]) - L["c"]) / 16]
    return dict(hm_p=torch.from_numpy(hm_p), hm_s=torch.from_numpy(hm_s), off=torch.from_numpy(off), st=torch.from_numpy(st), msk=torch.from_numpy(msk))


# ------------------------------------------------------------------ nets
def cbr(i, o, s=1, d=1):
    return nn.Sequential(nn.Conv2d(i, o, 3, s, d, dilation=d, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True))


class Net(nn.Module):
    """v1 PuckNet (large=False) with 1 + 2 + 4 outputs; large=True adds dilations 8 and 16 at 1/8 scale (receptive field
    about 4x larger along a streak)."""
    def __init__(self, large=False):
        super().__init__()
        self.e1 = nn.Sequential(cbr(12, 32, 2), cbr(32, 32))
        self.e2 = nn.Sequential(cbr(32, 48, 2), cbr(48, 48))
        e3 = [cbr(48, 64, 2), cbr(64, 64), cbr(64, 64, d=2), cbr(64, 64, d=4)]
        if large: e3 += [cbr(64, 64, d=8), cbr(64, 64, d=16)]
        self.e3 = nn.Sequential(*e3)
        self.d2 = cbr(64 + 48, 48); self.d1 = nn.Sequential(cbr(48 + 32, 32), cbr(32, 32))
        self.hm = nn.Conv2d(32, 1, 1); self.off = nn.Conv2d(32, 2, 1); self.st = nn.Conv2d(32, 4, 1)
        nn.init.constant_(self.hm.bias, -4.0)

    def forward(self, x):
        a = self.e1(x); b = self.e2(a); c = self.e3(b)
        u = self.d2(torch.cat([F.interpolate(c, size=b.shape[2:], mode="bilinear", align_corners=False), b], 1))
        u = self.d1(torch.cat([F.interpolate(u, size=a.shape[2:], mode="bilinear", align_corners=False), a], 1))
        return self.hm(u), self.off(u), self.st(u)


def focal(logit, hm):
    p = torch.sigmoid(logit).clamp(1e-4, 1 - 1e-4); pos = hm.eq(1).float()
    lp = -((1 - p) ** 2) * torch.log(p) * pos
    ln = -((1 - hm) ** 4) * (p ** 2) * torch.log(1 - p) * (1 - pos)
    return (lp.sum() + ln.sum()) / pos.sum().clamp(min=1)


def peaks(logit, k=6):
    p = torch.sigmoid(logit); m = F.max_pool2d(p, 3, 1, 1); p = p * (p == m).float()
    v, idx = p.view(p.shape[0], -1).topk(k); W = p.shape[-1]
    return v, idx // W, idx % W


class DS(torch.utils.data.Dataset):
    def __init__(self, real, n, fixed=False, **kw):
        self.real, self.n, self.fixed, self.kw = real, n, fixed, kw
    def __len__(self): return self.n
    def __getitem__(self, i):
        rnd = random.Random(i if self.fixed else random.getrandbits(48))
        x, t = make_sample(self.real[rnd.randrange(len(self.real))], rnd, **self.kw)
        return x, t
