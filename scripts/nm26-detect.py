"""Register every frame of one game and find puck candidates of two kinds.

    /root/venvs/blender/bin/python scripts/nm26-detect.py g1

Outputs:
- data/games/nm26-semifinal/<game>/background.png: median of registered frames (every 3 s), the empty rink;
- out/nm26/<game>/frames.json (cache, not committed): per frame [index, inliers, H (8 values, video -> reference
  video px), disks, smudges].
  - disk = the puck at rest or slow: a dark, neutral, compact blob of puck size;
  - smudge = the puck in flight: a grey blob darker than the background and changed since the previous frame
    (motion), inside the ice polygon, neutral in colour.
  - Each candidate: [x_stab, y_stab, area, w, h, mean value, mean saturation, b-r, elongation, angle_deg].

Four worker processes split the game into time chunks; each starts one second early to have a previous frame.
"""
import sys
from multiprocessing import Pool

import cv2
import numpy as np

from nm26_common import CFG, OUT, T_ROI, W_STAB, H_STAB, Registrar, frames, game_dir, ice_mask, reference_frame, save

GAME = sys.argv[1] if len(sys.argv) > 1 else "g1"
G = CFG["games"][GAME]
T0, T1 = G["video_window_s"]
WORKERS = 4


def warp(a, H):
    return cv2.warpPerspective(a, T_ROI @ H, (W_STAB, H_STAB), flags=cv2.INTER_LINEAR)


def blob_stats(lab, q, st, cen, w, hsv):
    x, y, ww, hh, ar = st[q]
    bm = lab[y:y + hh, x:x + ww] == q
    pf = w[y:y + hh, x:x + ww][bm].astype(int)
    ys, xs = np.nonzero(bm)
    cov = np.cov(np.c_[xs, ys].T) if len(xs) > 2 else np.eye(2)
    ev, evec = np.linalg.eigh(cov)
    elong = float(np.sqrt(max(ev[1], 1e-6) / max(ev[0], 1e-6)))
    ang = float(np.degrees(np.arctan2(evec[1, 1], evec[0, 1])))
    return [round(float(cen[q][0]), 2), round(float(cen[q][1]), 2), int(ar), int(ww), int(hh),
            round(float(hsv[..., 2][y:y + hh, x:x + ww][bm].mean()), 1), round(float(hsv[..., 1][y:y + hh, x:x + ww][bm].mean()), 1),
            int(pf[:, 0].mean() - pf[:, 2].mean()), round(elong, 2), round(ang, 1)]


def background(_):
    ref = reference_frame(GAME)
    reg = Registrar(ref)
    S = []
    for i, a in frames(T0, T1):
        if i % (3 * 30):
            continue
        H, _ = reg(a)
        S.append(warp(a, H))
    return np.median(np.array(S), axis=0).astype(np.uint8)


def detect(chunk):
    t0, t1 = chunk
    ref = reference_frame(GAME)
    reg = Registrar(ref)
    bg = cv2.imread(str(game_dir(GAME) / "background.png"))
    bgv = cv2.cvtColor(bg, cv2.COLOR_BGR2HSV)[..., 2].astype(np.int16)
    bgg = bg.mean(2)
    ice = ice_mask()
    out, prev = [], None
    for i, a in frames(max(T0, t0 - 1.0), t1):
        H, n = reg(a)
        w = warp(a, H)
        hsv = cv2.cvtColor(w, cv2.COLOR_BGR2HSV)
        v, sat = hsv[..., 2].astype(np.int16), hsv[..., 1]
        g = w.mean(2)
        moving = np.abs(g - prev) > 12 if prev is not None else np.zeros_like(ice)
        prev = g
        if i < int(round(t0 * 30)):
            continue
        # disks
        seed = (v < 70) & (bgv > v + 60) & (sat < 130) & ice
        lo = ((((v < 130) & (bgv > v + 60) & (sat < 130)) | seed) & ice).astype(np.uint8)
        lo = cv2.morphologyEx(lo, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        nl, lab, st, cen = cv2.connectedComponentsWithStats(lo)
        keep = set(np.unique(lab[seed]).tolist())
        disks = [blob_stats(lab, q, st, cen, w, hsv) for q in range(1, nl)
                 if q in keep and 150 <= st[q][4] <= 1600 and st[q][2] <= 60 and st[q][3] <= 45]
        # smudges
        sm = ((bgg - g > 22) & (w.max(2).astype(int) - w.min(2) < 55) & ice & moving).astype(np.uint8)
        sm = cv2.morphologyEx(sm, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        nl, lab, st, cen = cv2.connectedComponentsWithStats(sm)
        smudges = [blob_stats(lab, q, st, cen, w, hsv) for q in range(1, nl) if 60 <= st[q][4] <= 3500]
        out.append([i, n, [round(float(z), 6) for z in H.ravel()[:8]], disks, smudges])
    return out


if __name__ == "__main__":
    gd = game_dir(GAME)
    gd.mkdir(parents=True, exist_ok=True)
    if not (gd / "background.png").exists() or "--bg" in sys.argv:
        bg = background(None)
        cv2.imwrite(str(gd / "background.png"), bg)
        print("background written")
    edges = np.linspace(T0, T1, WORKERS + 1)
    with Pool(WORKERS) as p:
        R = p.map(detect, [(edges[k], edges[k + 1]) for k in range(WORKERS)])
    F = sorted({r[0]: r for part in R for r in part}.values(), key=lambda r: r[0])
    save(OUT / GAME / "frames.json", F)
    print("frames", len(F), "registration fallbacks", sum(1 for f in F if f[1] == 0),
          "disks/frame", round(np.mean([len(f[3]) for f in F]), 2), "smudges/frame", round(np.mean([len(f[4]) for f in F]), 2))
