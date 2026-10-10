"""Puck track of one NM26 game with the synthetic puck detector (docs/synthetic-puck.md).

    /root/venvs/blender/bin/python scripts/synth/track-puck.py <game> [--model puck-det-v1] [--detect-only] [--track-only]
        [--t0 S --t1 S]

1. Detect (four worker processes, time chunks): every frame of the game window is warped to stab px with the
   homography interpolated from out/nm26/<game>/H.npz (scripts/synth/puck-frames.py: every 6th frame registered);
   the detector (out/synth/<model>.pt) sees frames t-1, t, t+1 and the game's background and gives a heatmap for t;
   up to 6 peaks per frame with score >= 0.05 are kept (stab px, score) in out/nm26/<game>/puck-cands-<model>.json
   (cache, not committed).
2. Track: Viterbi over {absent, peak 1..n} per frame, as scripts/nm26-track.py but with the detector's score as the
   emission (logit of the score, clipped to [-4, 5]) and a faster motion limit (the detector sees blur):
   moving costs (d / SIGMA)^2 / 2 with d in mm per frame, impossible above D_MAX; entering or leaving "absent" costs
   SWITCH. No interpolation: frames without a chosen peak are "not seen".
   Positions: the detector's point is the puck's top-face centre, mapped to the ice through the reference camera on the
   plane 12 mm above the ice (the Blender puck's top), so x_mm, y_mm are the puck centre without the +y shift of the
   blob centre that puck-track.json carries (see docs/synthetic-puck.md).
Writes data/games/nm26-semifinal/<game>/puck-track-synth.json (same columns as puck-track.json; kind "det").
"""
import json, sys, time
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "scripts/synth"))
from nm26_common import CFG, OUT, T_ROI, W_STAB, H_STAB, X0, Y0, frames, game_dir, save, FPS  # noqa: E402

A = sys.argv[1:]; GAME = A[0]
def arg(n, d): return A[A.index(n) + 1] if n in A else d
MODEL = arg("--model", "puck-det-v1"); WORKERS = int(arg("--workers", 4))
T0, T1 = float(arg("--t0", CFG["games"][GAME]["video_window_s"][0])), float(arg("--t1", CFG["games"][GAME]["video_window_s"][1]))
CANDS = OUT / GAME / f"puck-cands-{MODEL}.json"
SIGMA, D_MAX, SWITCH = 60.0, float(arg("--dmax", 350.0)), 3.0
BIAS = float(arg("--bias", 1.0))  # added to every emission (1.0 chosen by the frame review, docs/synthetic-puck.md)
OUT_NAME = arg("--out", "puck-track-synth.json")
TOP_MM = 12.0
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
Kc, Rc, tc = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
# plane z = TOP_MM: world (x, y) -> stab px
H_TOP = np.array([[1, 0, -X0], [0, 1, -Y0], [0, 0, 1.0]]) @ Kc @ np.c_[Rc[:, 0], Rc[:, 1], Rc[:, 2] * TOP_MM + tc]
H_TOP_INV = np.linalg.inv(H_TOP)


def homographies():
    z = np.load(OUT / GAME / "H.npz")
    f, H8 = z["frame"], z["H8"]
    Hn = np.c_[H8, np.ones(len(H8))]
    return f, Hn


def H_at(i, f, Hn):
    k = np.searchsorted(f, i)
    if k < len(f) and f[k] == i: return Hn[k].reshape(3, 3)
    if k == 0: return Hn[0].reshape(3, 3)
    if k >= len(f): return Hn[-1].reshape(3, 3)
    a, b = f[k - 1], f[k]; w = (i - a) / (b - a)
    return ((1 - w) * Hn[k - 1] + w * Hn[k]).reshape(3, 3)


def detect(chunk):
    import torch
    torch.set_num_threads(1)
    tp = __import__("importlib").import_module("train_puck_detector_mod")
    net = tp.PuckNet(); net.load_state_dict(torch.load(REPO / f"out/synth/{MODEL}.pt")); net.eval()
    bg = cv2.imread(str(game_dir(GAME) / "background.png"))
    bgh = cv2.resize(bg, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    f, Hn = homographies()
    t0, t1 = chunk
    buf, out = [], []
    def run(batch):
        x = torch.from_numpy(np.stack(batch["x"]))
        with torch.no_grad():
            lg, of = net(x)
        v, iy, ix = tp.peaks(lg[:, 0], k=6)
        for b, i in enumerate(batch["i"]):
            c = []
            for j in range(v.shape[1]):
                s = float(v[b, j])
                if s < 0.05: continue
                yy, xx = int(iy[b, j]), int(ix[b, j])
                c.append([round((xx + float(of[b, 0, yy, xx])) * tp.STRIDE, 1), round((yy + float(of[b, 1, yy, xx])) * tp.STRIDE, 1), round(s, 4)])
            out.append([i, c])
    batch = {"x": [], "i": []}
    for i, a in frames(max(T0, t0 - 1 / FPS - 1e-3), min(T1, t1 + 1 / FPS + 1e-3)):
        w = cv2.warpPerspective(a, T_ROI @ H_at(i, f, Hn), (W_STAB, H_STAB), flags=cv2.INTER_LINEAR)
        buf.append((i, cv2.resize(w, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)))
        if len(buf) > 3: buf.pop(0)
        if len(buf) == 3 and buf[2][0] - buf[0][0] == 2 and t0 <= buf[1][0] / FPS < t1:
            x = np.concatenate([buf[0][1], buf[1][1], buf[2][1], bgh], 2).astype(np.float32) / 255.0 - 0.5
            batch["x"].append(x.transpose(2, 0, 1).copy()); batch["i"].append(buf[1][0])
            if len(batch["i"]) == 8:
                run(batch); batch = {"x": [], "i": []}
    if batch["i"]: run(batch)
    return out


def track(C):
    rows_in = []
    for i, cs in C:
        if not cs: rows_in.append((i, [])); continue
        P = np.array([[c[0], c[1]] for c in cs])
        q = np.c_[P, np.ones(len(P))] @ H_TOP_INV.T; Wd = q[:, :2] / q[:, 2:]
        rows_in.append((i, [(float(w[0]), float(w[1]), float(np.clip(np.log(c[2] / (1 - c[2] + 1e-6)), -4, 5) + BIAS), c[0], c[1], c[2]) for c, w in zip(cs, Wd)]))
    prevS, prevXY, prevI, back = np.array([0.0]), np.zeros((0, 2)), None, []
    for i, cs in rows_in:
        gap = 1 if prevI is None else max(1, i - prevI); prevI = i
        n = len(cs)
        S, B = np.zeros(n + 1), np.zeros(n + 1, int)
        opts = np.r_[prevS[0], prevS[1:] - SWITCH]
        S[0], B[0] = opts.max(), int(opts.argmax())
        if n:
            XY = np.array([[c[0], c[1]] for c in cs]); em = np.array([c[2] for c in cs])
            for j in range(n):
                o = [prevS[0] - SWITCH]
                if len(prevXY):
                    d = np.hypot(*(prevXY - XY[j]).T) / gap
                    tt = prevS[1:] - 0.5 * (d / SIGMA) ** 2
                    tt[d > D_MAX] = -1e9
                    o += list(tt)
                k = int(np.argmax(o)); S[j + 1], B[j + 1] = o[k] + em[j], k
            prevXY = XY
        else:
            prevXY = np.zeros((0, 2))
        back.append(B); prevS = S
    st = int(np.argmax(prevS)); rows = []
    for (i, cs), B in zip(reversed(rows_in), reversed(back)):
        if st > 0:
            x, y, em, u, v, s = cs[st - 1]
            rows.append([i, round(i / FPS, 3), round(x, 1), round(y, 1), round(u, 1), round(v, 1), "det", round(s, 3)])
        st = B[st]
    rows.reverse()
    return rows


if __name__ == "__main__":
    if "--track-only" not in A:
        import importlib.util
        spec = importlib.util.spec_from_file_location("train_puck_detector_mod", REPO / "scripts/synth/train-puck-detector.py")
        mod = importlib.util.module_from_spec(spec); sys.modules["train_puck_detector_mod"] = mod
        argv = sys.argv; sys.argv = [argv[0]]; spec.loader.exec_module(mod); sys.argv = argv
        t = time.time()
        edges = np.linspace(T0, T1, WORKERS + 1)
        with Pool(WORKERS) as p:
            R = p.map(detect, [(edges[k], edges[k + 1]) for k in range(WORKERS)])
        C = sorted({r[0]: r for part in R for r in part}.values(), key=lambda r: r[0])
        save(CANDS, C)
        print(GAME, "frames", len(C), "with a peak >= 0.5:", sum(1 for c in C if c[1] and c[1][0][2] >= 0.5), "minutes", round((time.time() - t) / 60, 1), flush=True)
    if "--detect-only" in A: sys.exit()
    C = json.loads(CANDS.read_text())
    rows = track(C)
    nf = len(C)
    save(game_dir(GAME) / OUT_NAME, {
        "description": "Puck track from the synthetic puck detector (scripts/synth/track-puck.py, docs/synthetic-puck.md). One row per frame where a peak was chosen; other frames are not seen. PROPOSED.",
        "columns": ["frame", "video_t_s", "x_mm", "y_mm", "u_stab_px", "v_stab_px", "kind", "score"],
        "position_note": "x_mm, y_mm: the puck centre, from the detected top-face centre mapped through the reference camera onto the plane 12 mm above the ice (the Blender puck's top; real thickness unknown). puck-track.json maps the blob centre onto the ice plane instead, which puts it about 13 mm further +y (away from the camera). u/v_stab_px: the detected top-face centre.",
        "model": MODEL, "tracker": {"sigma_mm": SIGMA, "d_max_mm_per_frame": D_MAX, "switch_cost": SWITCH, "emission": "logit(score) clipped to [-4, 5], plus bias", "bias": BIAS},
        "frames": nf, "seen_fraction": round(len(rows) / max(nf, 1), 3),
        "rows": rows,
    })
    print(GAME, "frames", nf, "seen", len(rows), round(len(rows) / max(nf, 1), 3))
