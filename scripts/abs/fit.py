"""Analysis-by-synthesis fit of figure poses (u, theta) per frame against the broadcast frame, init from tracker v3.

    python3 scripts/abs/fit.py <goal> <frame0> <frame1> [out.json]
"""
import sys, json, time
from pathlib import Path
import numpy as np, torch, cv2
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/abs"))
import synth
from synth import tc
torch.set_num_threads(4)
SC = 0.5            # fit resolution relative to reference px
NPTS = 1500
PLATE = cv2.imread(str(REPO / "out/abs/plate-g2.png"))
FIGS = tc.SKATERS + tc.GOALIES
HALFOFF = torch.tensor(synth.HALF[:2], dtype=torch.float32)


def load_v3(game="g2"):
    D = json.loads((tc.NM26 / game / "figure-tracks-v3.json").read_text()); C = D["columns"]
    return {r[0]: {f: (r[C.index(f + "_u")], r[C.index(f + "_theta_deg")], r[C.index(f + "_src")]) for f in FIGS} for r in D["rows"]}


def foreground(img):
    """Soft foreground in [0,1] (fit_goalie.foreground): blurred Lab difference from the plate, discounted at plate edges."""
    a = cv2.cvtColor(cv2.GaussianBlur(img, (0, 0), 1.2), cv2.COLOR_BGR2LAB).astype(np.float32)
    b = cv2.cvtColor(cv2.GaussianBlur(PLATE, (0, 0), 1.2), cv2.COLOR_BGR2LAB).astype(np.float32)
    d = np.sqrt(((a - b) ** 2 * [0.6, 1, 1]).sum(-1))
    gp = cv2.cvtColor(PLATE, cv2.COLOR_BGR2GRAY).astype(np.float32)
    edge = cv2.dilate(np.hypot(cv2.Sobel(gp, cv2.CV_32F, 1, 0), cv2.Sobel(gp, cv2.CV_32F, 0, 1)), np.ones((5, 5), np.uint8))
    m = np.clip((d - (9 + 0.2 * np.clip(edge, 0, 200))) / 15.0, 0, 1); m[:, 880:] = 0
    return m


def column(fid, r=55, h=62):
    """Image mask (crop px, 1x) of everything the figure can occupy: its slot swept, radius r, height h."""
    P = tc.SLOT[fid]; m = np.zeros((640, 1000), np.uint8); K, R, t = tc.ref_camera()
    for s in np.linspace(0, 1, 30):
        c = tc.slot_point(fid, s)
        ring = np.array([(c[0] + r * np.cos(a), c[1] + r * np.sin(a), z) for a in np.linspace(0, 2 * np.pi, 20) for z in (0, h)])
        q = (ring @ R.T + t) @ K.T; q = q[:, :2] / q[:, 2:] - synth.HALF[:2]
        cv2.fillPoly(m, [cv2.convexHull(q.astype(np.int32))], 1)
    return m


def window(fid, u, th, pad=14):
    q = synth.project(synth.world_points(fid, torch.tensor(float(u)), torch.tensor(float(th)), NPTS)).numpy() - synth.HALF[:2]
    x0, y0 = np.floor(q.min(0) - pad - 40).astype(int); x1, y1 = np.ceil(q.max(0) + pad + 40).astype(int)
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, 1000), min(y1, 640)
    return x0, y0, x1 - (x1 - x0) % 2, y1 - (y1 - y0) % 2


def fig_sil(fid, u, th, win, sig=1.0):
    """Soft silhouette of one figure inside window win (1x crop px), rendered at scale SC."""
    x0, y0, x1, y1 = win
    q = (synth.project(synth.world_points(fid, u, th, NPTS)) - HALFOFF - torch.tensor([x0, y0], dtype=torch.float32)) * SC
    return synth.splat(q, (int((y1 - y0) * SC), int((x1 - x0) * SC)), sig)


def iou(S, F, ign):
    w = 1 - ign
    I = (S * F * w).sum(); U = ((S + F - S * F) * w).sum()
    return I / (U + 1e-6)


def fit_frame(img, init, prev=None, steps=60, grid=True):
    F1 = foreground(img)
    visible = [f for f in FIGS if init[f][0] is not None and init[f][1] is not None]
    wins = {f: window(f, init[f][0], init[f][1]) for f in visible}
    def inside(f):
        q = synth.project(synth.world_points(f, torch.tensor(float(init[f][0])), torch.tensor(float(init[f][1])), 300)).numpy() - synth.HALF[:2]
        return ((q[:, 0] > 10) & (q[:, 0] < 990) & (q[:, 1] > 10) & (q[:, 1] < 630)).mean() > 0.95
    visible = [f for f in visible if inside(f) and wins[f][2] - wins[f][0] > 60 and wins[f][3] - wins[f][1] > 60]
    wins = {f: wins[f] for f in visible}
    cur = {f: (float(init[f][0]), float(init[f][1])) for f in visible}
    res = {}
    Fs = {f: torch.tensor(cv2.resize(F1[w[1]:w[3], w[0]:w[2]] * 1.0, None, fx=SC, fy=SC, interpolation=cv2.INTER_AREA)) for f, w in wins.items()}
    def ignore(f, poses):
        """Pixels (window of f) covered by the other figures at their current pose."""
        x0, y0, x1, y1 = wins[f]; ign = torch.zeros((int((y1 - y0) * SC), int((x1 - x0) * SC)))
        for g, (ug, tg) in poses.items():
            if g == f: continue
            gx0, gy0, gx1, gy1 = wins[g]
            if gx1 < x0 or gx0 > x1 or gy1 < y0 or gy0 > y1: continue
            Sg = fig_sil(g, torch.tensor(ug), torch.tensor(tg), wins[f]).detach()
            ign = torch.maximum(ign, (Sg > 0.5).float())
        return ign
    t0 = time.time()
    base = {}
    for rnd in range(2):
        poses = dict(cur)
        for f in visible:
            ign = ignore(f, poses)
            if rnd == 0:
                base[f] = float(iou(fig_sil(f, torch.tensor(cur[f][0]), torch.tensor(cur[f][1]), wins[f]).detach(), Fs[f], ign))
            best = (-1, cur[f])
            if grid:
                for du in (-0.06, -0.03, 0, 0.03, 0.06):
                    for dth in range(-40, 41, 10):
                        u, th = float(np.clip(cur[f][0] + du, 0, 1)), cur[f][1] + dth
                        with torch.no_grad():
                            s = float(iou(fig_sil(f, torch.tensor(u), torch.tensor(th), wins[f]), Fs[f], ign))
                        if s > best[0]: best = (s, (u, th))
            u = torch.tensor(best[1][0] if grid else cur[f][0], requires_grad=True); th = torch.tensor(best[1][1] if grid else cur[f][1], requires_grad=True)
            opt = torch.optim.Adam([{"params": [u], "lr": 0.004}, {"params": [th], "lr": 1.0}])
            bl = (1e9, None)
            for k in range(steps):
                opt.zero_grad(); L = 1 - iou(fig_sil(f, u, th, wins[f], 2.0 if k < steps // 2 else 1.0), Fs[f], ign); L.backward(); opt.step()
                with torch.no_grad(): u.clamp_(0, 1)
                if k >= steps // 2 and float(L) < bl[0]: bl = (float(L), (float(u), float(th)))
            cur[f] = bl[1] if bl[1] else (float(u), float(th))
            poses[f] = cur[f]
    out = {}
    for f in visible:
        ign = ignore(f, cur)
        Sa = fig_sil(f, torch.tensor(cur[f][0]), torch.tensor(cur[f][1]), wins[f]).detach()
        out[f] = {"u": cur[f][0], "theta": cur[f][1], "iou_v3": base[f], "iou_fit": float(iou(Sa, Fs[f], ign)),
                  "u_v3": float(init[f][0]), "theta_v3": float(init[f][1])}
    return out, time.time() - t0


if __name__ == "__main__":
    gid, f0, f1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); outp = sys.argv[4] if len(sys.argv) > 4 else str(REPO / f"out/abs/{gid}-fit.json")
    T = load_v3(); res = {}
    for fr in range(f0, f1 + 1):
        img = cv2.imread(str(REPO / f"out/abs/{gid}/{fr}.png"))
        init = {f: (T[fr][f][0], T[fr][f][1]) for f in FIGS}
        res[fr], dt = fit_frame(img, init)
        print(fr, f"{dt:.1f}s", "mean IoU v3 %.3f -> fit %.3f" % (np.mean([v['iou_v3'] for v in res[fr].values()]), np.mean([v['iou_fit'] for v in res[fr].values()])), flush=True)
        Path(outp).write_text(json.dumps(res))
