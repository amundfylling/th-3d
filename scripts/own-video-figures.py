"""Figure tracks of the handheld match by analysis-by-synthesis in the per-frame camera (docs/own-video-tracking.md, step 2).

    /root/venvs/blender/bin/python scripts/own-video-figures.py [--workers 4] [--from S --to S] [--kit-test]

The NM26 networks cannot be reused here (they are not in the repo, and they read 200 px crops of 80-90 px figures; in
this phone video a figure is 20-35 px tall). Instead every figure's 3D mold is placed at candidate poses on its slot,
projected with the frame's camera (own-video-camera.py), and compared with the frame:
- maps per frame (video px): foreground = colour difference from the empty-table background (background.png of the
  stabilisation, warped into the frame); kit maps = foreground AND kit colour (yellow, white, blue);
- per figure and pose (u every 5 mm along the slot, heading every 30 deg): the mean kit-map value at the projected mold
  points of each part (jersey points against the team's jersey colour, blue points against blue), averaged over the
  two parts;
- per figure, a Viterbi over the whole match on (u, heading): slot speed up to 1.2 m/s (assumed), heading steps
  penalised, then a refinement of u to 1 mm around the path.
Which kit belongs to which end is measured, not assumed (--kit-test, recorded in the output).
Score volumes are cached in out/own-video/ (not committed). Writes data/games/fylling-vs-moe-2022/own-video/figure-tracks.json.
Status: PROPOSED (model fit, no labels for this video).
"""
import json, sys, time
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from own_video_common import *  # noqa: E402,F403
from game_common import stabilisation, crop_matrix, CROP_W, CROP_H  # noqa: E402

A = sys.argv[1:]
def arg(n, d): return A[A.index(n) + 1] if n in A else d
CACHE = REPO / "out/own-video"; CACHE.mkdir(parents=True, exist_ok=True)
F0 = int(round(float(arg("--from", MATCH_START_S)) * FPS)); F1 = int(round(float(arg("--to", MATCH_END_S)) * FPS))
DU_MM, DH = 5.0, 30
HEADS = np.arange(0, 360, DH)
NPTS = 40
FIGS = SKATERS + GOALIES
KIT_OF_END = json.loads(arg("--kits", '{"W": "yellow", "E": "white"}'))


def mold_sample(kind, kit_name):
    P, L = mold(kind, kit_name, 1); rng = np.random.default_rng(0); out = []
    for part in (2, 0):            # jersey, blue
        idx = np.flatnonzero((L == part) & (P[:, 2] > 3.0))
        out.append(P[rng.choice(idx, NPTS, replace=False)])
    return np.concatenate(out)       # first NPTS jersey, next NPTS blue


def poses(pid):
    n = int(slot_length(pid) // DU_MM) + 1
    return np.linspace(0, 1, n)


def world_points():
    """All candidate poses' world points, figure by figure: dict pid -> (U, H, 2*NPTS, 3)."""
    W = {}
    for pid in FIGS:
        pts = mold_sample("goalie" if pid.endswith("G") else "skater", "SWE")
        us = poses(pid)
        W[pid] = np.stack([np.stack([place(pts, pid, u, h) for h in HEADS]) for u in us])
    return W


def maps(img, bg):
    a = cv2.cvtColor(cv2.GaussianBlur(img, (3, 3), 0), cv2.COLOR_BGR2LAB).astype(np.float32)
    b = cv2.cvtColor(cv2.GaussianBlur(bg, (3, 3), 0), cv2.COLOR_BGR2LAB).astype(np.float32)
    d = np.sqrt(((a - b) ** 2 * [0.5, 1, 1]).sum(-1))
    fg = np.clip((d - 14) / 20.0, 0, 1)
    h = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32); H, S, V = h[..., 0], h[..., 1], h[..., 2]
    yellow = ((H >= 15) & (H <= 38) & (S > 90) & (V > 100)).astype(np.float32)
    white = ((S < 60) & (V > 165)).astype(np.float32)
    blue = ((H >= 95) & (H <= 130) & (S > 80) & (V > 40)).astype(np.float32)
    k = lambda m: cv2.GaussianBlur(m * fg, (0, 0), 0.8)
    return {"yellow": k(yellow), "white": k(white), "blue": k(blue)}


def score_frame(M, Q, kit):
    """Q: (U, H, 2N, 2) projected points -> (U, H) score."""
    h, w = M["blue"].shape
    x = np.clip(np.round(Q[..., 0]).astype(int), 0, w - 1); y = np.clip(np.round(Q[..., 1]).astype(int), 0, h - 1)
    inside = (Q[..., 0] >= 0) & (Q[..., 0] < w) & (Q[..., 1] >= 0) & (Q[..., 1] < h)
    j = np.where(inside[..., :NPTS], M[kit][y[..., :NPTS], x[..., :NPTS]], 0).mean(-1)
    b = np.where(inside[..., NPTS:], M["blue"][y[..., NPTS:], x[..., NPTS:]], 0).mean(-1)
    return 0.5 * (j + b)


def work(rng_):
    a, b, kit_test = rng_
    cv2.setNumThreads(1)
    WP = world_points(); bg = cv2.imread(str(GAME / "background.png"))
    Hs = stabilisation(); Tc = crop_matrix()
    flat = np.concatenate([WP[p].reshape(-1, 3) for p in FIGS]); sizes = [WP[p].shape for p in FIGS]
    res = {p: [] for p in FIGS}; kitres = {p: [] for p in FIGS}; idx = []
    for i, img in frames():
        if i < a: continue
        if i >= b: break
        if kit_test and i % 25: continue
        bgv = cv2.warpPerspective(bg, np.linalg.inv(Tc @ Hs[i]), (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        M = maps(img, bgv)
        Q = project(i, flat); o = 0
        for p, sh in zip(FIGS, sizes):
            n = sh[0] * sh[1] * sh[2]; q = Q[o:o + n].reshape(sh[0], sh[1], sh[2], 2); o += n
            if kit_test: kitres[p].append([score_frame(M, q, k).max() for k in ("yellow", "white")])
            else: res[p].append(score_frame(M, q, KIT_OF_END[p[0]]).astype(np.float16))
        idx.append(i)
    return idx, res, kitres


def chunks(n):
    edges = np.linspace(F0, F1, n + 1).astype(int); return list(zip(edges[:-1], edges[1:]))


if __name__ == "__main__":
    nw = int(arg("--workers", 4)); t0 = time.time()
    if "--kit-test" in A:
        with Pool(nw) as pool: parts = pool.map(work, [(a, b, True) for a, b in chunks(nw)])
        out = {}
        for p in FIGS:
            k = np.concatenate([np.array(r[2][p]) for r in parts])
            out[p] = {"yellow_score_mean": round(float(k[:, 0].mean()), 4), "white_score_mean": round(float(k[:, 1].mean()), 4),
                      "frames": len(k)}
        print(json.dumps(out, indent=1)); save(CACHE / "kit-test.json", out); sys.exit()
    todo = [(a, b) for a, b in chunks(int(arg("--chunks", 40))) if not (CACHE / f"scores_{a}_{b}.npz").exists()]
    print(len(todo), "chunks to score", flush=True)
    with Pool(nw) as pool:
        for idx, res, _ in pool.imap_unordered(work, [(a, b, False) for a, b in todo]):
            np.savez_compressed(CACHE / f"scores_{idx[0]}_{idx[-1] + 1}.npz", frames=np.array(idx), **{p: np.stack(res[p]) for p in FIGS})
            print("chunk", idx[0], "done", round(time.time() - t0), "s", flush=True)
