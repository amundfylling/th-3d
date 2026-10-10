"""Register every frame of one NM26 game and sample real frame triplets for the synthetic puck detector.

    /root/venvs/blender/bin/python scripts/synth/puck-frames.py <game> [--per-game 360]

docs/synthetic-puck.md. One pass over the game window (four worker processes, time chunks as scripts/nm26-detect.py):
- every 6th frame (--h-every) and every sampled frame is registered to the reference frame (game 1 at 180 s) with the
  same Registrar as nm26-detect.py (registration is the slow step: about 10 frames/s per process); the homographies go
  to out/nm26/<game>/H.npz (frame index, inliers, H video px -> reference video px; cache, not committed).
  scripts/synth/track-puck.py interpolates between them (the broadcast camera drifts slowly; checked there);
- training backgrounds: frame triplets (t-1, t, t+1) at frames where the current track (puck-track.json) is sure of
  the puck, warped to stab px (the nm26 ROI) and saved as JPEG under out/synth/puck/real/<game>_<frame>_{a,b,c}.jpg,
  with the current track's position at each of the three frames in out/synth/puck/real/<game>.jsonl.
  "Sure" = a disk with score >= 2 whose neighbours (+-1 frame) are disks within 6 px (70% of samples), or a smudge
  inside a kept flight run with smudge or disk neighbours (30%; real motion blur). These are the only real pucks the
  detector sees in training; frames where the current track is unsure are never used (their puck would be an
  unlabelled positive).
"""
import json, random, sys
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from nm26_common import CFG, OUT, T_ROI, W_STAB, H_STAB, Registrar, frames, game_dir, load, reference_frame  # noqa: E402

A = sys.argv[1:]; GAME = A[0]
def arg(n, d): return A[A.index(n) + 1] if n in A else d
PER_GAME = int(arg("--per-game", 360)); WORKERS = 4; H_EVERY = int(arg("--h-every", 6))
T0, T1 = CFG["games"][GAME]["video_window_s"]
DEST = REPO / "out/synth/puck/real"


def pick_frames():
    rows = load(game_dir(GAME) / "puck-track.json")["rows"]; by = {r[0]: r for r in rows}
    disk, smudge = [], []
    for r in rows:
        a, c = by.get(r[0] - 1), by.get(r[0] + 1)
        if not (a and c): continue
        if r[6] == "disk" and r[7] >= 2 and a[6] == "disk" and c[6] == "disk" and \
                max(np.hypot(a[4] - r[4], a[5] - r[5]), np.hypot(c[4] - r[4], c[5] - r[5])) <= 6:
            disk.append(r[0])
        elif r[6] == "smudge" and a[6] in ("smudge", "disk") and c[6] in ("smudge", "disk"):
            smudge.append(r[0])
    rnd = random.Random(f"puck-{GAME}")
    pick = set(); nd = int(PER_GAME * 0.7)
    for pool, n in ((disk, nd), (smudge, PER_GAME - nd)):
        pool = list(pool); rnd.shuffle(pool); got = 0
        for f in pool:
            if got >= n: break
            if all(abs(f - q) > 8 for q in pick): pick.add(f); got += 1
    labels = {f: [by[f + d][4:7] for d in (-1, 0, 1)] for f in pick}
    print(GAME, "sure disks", len(disk), "sure smudges", len(smudge), "picked", len(pick))
    return labels


def work(args):
    t0, t1, want = args
    reg = Registrar(reference_frame(GAME))
    Hs, keep = [], {}
    need = {f + d: (f, k) for f in want for k, d in enumerate((-1, 0, 1))}
    for i, a in frames(t0, t1):
        if i % H_EVERY and i not in need: continue
        H, n = reg(a)
        Hs.append([i, n] + [float(z) for z in H.ravel()[:8]])
        if i in need:
            f, k = need[i]
            w = cv2.warpPerspective(a, T_ROI @ H, (W_STAB, H_STAB), flags=cv2.INTER_LINEAR)
            cv2.imwrite(str(DEST / f"{GAME}_{f}_{'abc'[k]}.jpg"), w, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return Hs


if __name__ == "__main__":
    DEST.mkdir(parents=True, exist_ok=True)
    labels = pick_frames()
    edges = np.linspace(T0, T1, WORKERS + 1)
    jobs = [(edges[k], edges[k + 1], [f for f in labels if edges[k] <= f / 30 < edges[k + 1]]) for k in range(WORKERS)]
    with Pool(WORKERS) as p:
        R = p.map(work, jobs)
    Hs = np.array(sorted({r[0]: r for part in R for r in part}.values(), key=lambda r: r[0]), np.float64)
    (OUT / GAME).mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / GAME / "H.npz", frame=Hs[:, 0].astype(np.int64), inliers=Hs[:, 1].astype(np.int32), H8=Hs[:, 2:])
    with open(DEST / f"{GAME}.jsonl", "w") as fo:
        for f, lab in sorted(labels.items()):
            if all((DEST / f"{GAME}_{f}_{c}.jpg").exists() for c in "abc"):
                fo.write(json.dumps({"game": GAME, "frame": f, "track_stab_px": [[l[0], l[1]] for l in lab], "kinds": [l[2] for l in lab]}) + "\n")
    print(GAME, "frames registered", len(Hs), "fallbacks", int((Hs[:, 1] == 0).sum()))
