"""Figure paths from the cached pose scores (docs/own-video-tracking.md, step 2b).

    /root/venvs/blender/bin/python scripts/own-video-figure-paths.py

Per figure, a Viterbi over all match frames on the (u, heading) grid of own-video-figures.py:
- reward: the frame's pose score / 0.05;
- slot motion: cost (du / 25 mm)^2, at most 1.2 m/s (48 mm per frame at 25 fps; assumed maximum figure speed);
- rotation: cost 0.5 per (30 deg step)^2, any size allowed (figures spin).
The heading has a front/back ambiguity at this resolution (a figure is 20-35 px tall); the score margin between the
chosen heading and the opposite one is written per frame so a reader can see where the rotation is unsupported.
Writes data/games/fylling-vs-moe-2022/own-video/figure-tracks.json. Status: PROPOSED.
"""
import importlib.util, json, sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from own_video_common import *  # noqa: E402,F403

spec = importlib.util.spec_from_file_location("ovf", REPO / "scripts/own-video-figures.py")
ovf = importlib.util.module_from_spec(spec); argv = sys.argv; sys.argv = [argv[0]]; spec.loader.exec_module(ovf); sys.argv = argv
CACHE = REPO / "out/own-video"
SCALE, UMM, HSTEP_COST, VMAX = 0.05, 25.0, 0.5, 1200.0

files = sorted(CACHE.glob("scores_*.npz"), key=lambda p: int(p.stem.split("_")[1]))
Z = [np.load(f) for f in files]
fr = np.concatenate([z["frames"] for z in Z])
assert np.all(np.diff(fr) == 1), "score chunks are not contiguous"
NH = len(ovf.HEADS)
dh = np.minimum(np.abs(np.arange(NH)[:, None] - np.arange(NH)[None]), NH - np.abs(np.arange(NH)[:, None] - np.arange(NH)[None]))
CH = HSTEP_COST * dh ** 2


def viterbi(S, pid):
    T, U, H = S.shape
    dmax = int(VMAX / FPS / ovf.DU_MM); D = np.arange(-dmax, dmax + 1)
    CU = (D * ovf.DU_MM / UMM) ** 2
    V = S[0] / SCALE; bpd = np.zeros((T, U, H), np.int8); bph = np.zeros((T, U, H), np.int8)
    for t in range(1, T):
        M = V[:, None, :] - CH[None]            # (U, h_new, h_old)
        bh = M.argmax(-1); M1 = np.take_along_axis(M, bh[..., None], -1)[..., 0]
        best = np.full((U, H), -np.inf); bd = np.zeros((U, H), np.int8)
        for d, c in zip(D, CU):
            src = np.full((U, H), -np.inf)
            if d >= 0: src[:U - d] = M1[d:] if d else M1
            else: src[-d:] = M1[:U + d]
            v = src - c; m = v > best; best[m] = v[m]; bd[m] = d
        bpd[t] = bd; bph[t] = bh[(np.arange(U)[:, None] + bd).clip(0, U - 1), np.arange(H)[None]]
        V = best + S[t] / SCALE
        V -= V.max()
    u = np.zeros(T, int); h = np.zeros(T, int)
    u[-1], h[-1] = np.unravel_index(np.argmax(V), V.shape)
    for t in range(T - 1, 0, -1):
        d = bpd[t, u[t], h[t]]; hp = bph[t, u[t], h[t]]
        u[t - 1] = u[t] + d; h[t - 1] = hp
    return u, h


cols = ["u", "heading_deg", "x_mm", "y_mm", "score", "flip_margin"]
tracks = {}; summary = {}
for pid in ovf.FIGS:
    S = np.concatenate([z[pid] for z in Z]).astype(np.float32)
    ui, hi = viterbi(S, pid)
    us = ovf.poses(pid)[ui]; hs = ovf.HEADS[hi].astype(float); xy = slot_point(pid, us)
    sc = S[np.arange(len(S)), ui, hi]; opp = S[np.arange(len(S)), ui, (hi + NH // 2) % NH]
    tracks[pid] = np.c_[us.round(4), hs, xy.round(1), sc.round(4), (sc - opp).round(4)].tolist()
    step = np.abs(np.diff(us)) * slot_length(pid)
    summary[pid] = {"score_median": round(float(np.median(sc)), 3), "frames_score_below_0.1": round(float((sc < 0.1).mean()), 3),
                    "slot_step_mm_p95": round(float(np.percentile(step, 95)), 1), "u_range": [round(float(us.min()), 3), round(float(us.max()), 3)],
                    "heading_flip_margin_median": round(float(np.median(sc - opp)), 3)}
    print(pid, summary[pid], flush=True)

out = {"description": "Figure tracks of the handheld match (scripts/own-video-figures.py scores, scripts/own-video-figure-paths.py "
       "Viterbi), every frame of the 5:00 match. Per figure and frame: u = slot position 0-1 along the slot centreline "
       "(data/geometry.json), heading_deg = facing direction in world degrees (0 = +x, counter-clockwise; the team's home "
       "heading is W 0, E 180), x_mm/y_mm = pivot on the slot centreline, score = mean kit-map value at the projected mold "
       "(0-1; below 0.1 the figure is barely supported), flip_margin = score minus the score of the opposite heading (near 0: "
       "front and back cannot be told apart).",
       "status": "proposed", "kits": {"W": ovf.KIT_OF_END["W"], "E": ovf.KIT_OF_END["E"],
                                      "evidence": "out/own-video/kit-test.json: 11 of 12 slots score higher with this kit (E-G does not)"},
       "grid": {"u_step_mm": ovf.DU_MM, "heading_step_deg": int(ovf.DH)},
       "viterbi": {"reward_scale": SCALE, "slot_cost_mm": UMM, "heading_step_cost": HSTEP_COST, "max_speed_mm_s": VMAX},
       "frames": [int(fr[0]), int(fr[-1])], "fps": FPS, "columns": cols, "summary": summary, "tracks": tracks}
save(OUTD / "figure-tracks.json", out)
