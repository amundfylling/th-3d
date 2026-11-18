"""Puck by analysis-by-synthesis: a 25.4 mm cylinder, optionally smeared along its velocity (motion blur), fitted to the
foreground residual that the fitted figures do not explain.   python3 scripts/abs/puck.py <goal> <fit.json> <out.json>"""
import sys, json
from pathlib import Path
import numpy as np, torch, cv2
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/abs"))
import synth, fit
from synth import tc
RAD, ZH = 12.7, 6.0   # puck radius; top-face height above ice (mm). Thickness is unknown (geometry.json), 12 mm = synth puck plane.
ang = np.linspace(0, 2 * np.pi, 40, endpoint=False)
DISK = torch.tensor(np.r_[[(r * np.cos(a), r * np.sin(a)) for r in (3, 6, 9, 12) for a in ang]], dtype=torch.float32)
TAUS = torch.linspace(-0.2, 0.2, 7)   # fraction of a frame (exposure ~0.4 frame)


def puck_sil(xy, v, win, sc=fit.SC, sig=1.0):
    pts = []
    for tau in TAUS:
        c = xy + v * tau / 30.0
        for z in (0.0, ZH, 2 * ZH):
            pts.append(torch.cat([DISK + c, torch.full((len(DISK), 1), float(z))], 1))
    W = torch.cat(pts)
    x0, y0, x1, y1 = win
    q = (synth.project(W) - fit.HALFOFF - torch.tensor([x0, y0], dtype=torch.float32)) * sc
    return synth.splat(q, (int((y1 - y0) * sc), int((x1 - x0) * sc)), sig)


def to_px(xy):
    q = synth.project(torch.tensor([[xy[0], xy[1], ZH]], dtype=torch.float32))[0] - fit.HALFOFF
    return float(q[0]), float(q[1])


if __name__ == "__main__":
    gid, fitp, outp = sys.argv[1:4]
    FIT = json.loads(Path(fitp).read_text())
    P = json.loads((tc.NM26 / "g2/puck-track-synth-v2.json").read_text()); C = P["columns"]
    trk = {r[0]: (r[C.index("x_mm")], r[C.index("y_mm")]) for r in P["rows"]}
    out = {}
    for fr, figs in FIT.items():
        fr = int(fr); img = cv2.imread(str(REPO / f"out/abs/{gid}/{fr}.png")); F1 = fit.foreground(img)
        if fr not in trk: continue
        x0, y0 = trk[fr]
        vel = np.array([(trk[fr + 1][0] - trk[fr - 1][0]), (trk[fr + 1][1] - trk[fr - 1][1])]) * 15.0 if fr + 1 in trk and fr - 1 in trk else np.zeros(2)
        px, py = to_px((x0, y0)); sp = float(np.hypot(*vel))
        pad = 30 + min(sp / 30.0 * 2.2, 80)
        win = [max(int(px - pad), 0), max(int(py - pad), 0), min(int(px + pad), 1000), min(int(py + pad), 640)]
        win[2] -= (win[2] - win[0]) % 2; win[3] -= (win[3] - win[1]) % 2
        Fw = torch.tensor(cv2.resize(F1[win[1]:win[3], win[0]:win[2]] * 1.0, None, fx=fit.SC, fy=fit.SC, interpolation=cv2.INTER_AREA))
        # ignore pixels explained by fitted figures
        ign = torch.zeros_like(Fw)
        for f, v in figs.items():
            wf = fit.window(f, v["u"], v["theta"])
            if wf[2] < win[0] or wf[0] > win[2] or wf[3] < win[1] or wf[1] > win[3]: continue
            ign = torch.maximum(ign, (fit.fig_sil(f, torch.tensor(v["u"]), torch.tensor(v["theta"]), win) > 0.5).float())
        def score(xy, v):
            return fit.iou(puck_sil(xy, v, win), Fw, ign)
        v0 = torch.tensor(vel, dtype=torch.float32)
        best = (-1, None)
        for dx in range(-24, 25, 6):
            for dy in range(-24, 25, 6):
                xy = torch.tensor([x0 + dx, y0 + dy], dtype=torch.float32)
                with torch.no_grad(): s = float(score(xy, v0))
                if s > best[0]: best = (s, xy)
        xy = best[1].clone().requires_grad_(True); v = v0.clone().requires_grad_(True)
        opt = torch.optim.Adam([{"params": [xy], "lr": 0.8}, {"params": [v], "lr": 12.0}])
        bl = (1e9, None)
        for k in range(80):
            opt.zero_grad(); L = 1 - score(xy, v); L.backward(); opt.step()
            if float(L) < bl[0]: bl = (float(L), (xy.detach().clone(), v.detach().clone()))
        xyf, vf = bl[1]
        s_init = float(score(torch.tensor([x0, y0], dtype=torch.float32), v0))
        out[fr] = {"x_mm": float(xyf[0]), "y_mm": float(xyf[1]), "vx": float(vf[0]), "vy": float(vf[1]), "iou_track": s_init, "iou_fit": 1 - bl[0],
                   "track_x": x0, "track_y": y0, "fg_px": float((Fw * (1 - ign)).sum() / fit.SC ** 2)}
        print(fr, f"track ({x0:.1f},{y0:.1f}) -> fit ({float(xyf[0]):.1f},{float(xyf[1]):.1f}) IoU {s_init:.2f}->{1-bl[0]:.2f}", flush=True)
    Path(outp).write_text(json.dumps(out))
