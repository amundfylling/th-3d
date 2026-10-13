"""Review sheets for tracker 2 (docs/synthetic-puck.md section 8).

    /root/venvs/blender/bin/python scripts/synth/puck-shot-sheet.py <track file> <out.jpg> [--goals | --sample N --seed S]
    /root/venvs/blender/bin/python scripts/synth/puck-shot-sheet.py <track file> <out.jpg> --removed N --seed S
    /root/venvs/blender/bin/python scripts/synth/puck-shot-sheet.py <track file> <out.jpg> --goal-frames <goal id,...>

--removed: N rows per game that puck-track-synth.json has and <track file> does not (what tracker 2 removed), one
registered frame each, red circle on the removed position.
--goal-frames: per goal, the last sighting of <track file> before the goal moment and the 7 frames after it (stab px,
green = track position): is the shot visible at all?
Default mode (shot completion, --shot-completion tracks):

Per row: the registered broadcast (stab px, out/nm26/<game>/H.npz) of the frame before the shot row, the shot row's
frame and the frame after, cropped around the step; green circle = the track position in that frame, red = the shot row.
--goals: the shot rows in the last 2 s before the 25 user-marked goals; --sample: N random shot rows of all games.
"""
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from nm26_common import OUT, T_ROI, W_STAB, H_STAB, frames  # noqa: E402

D = REPO / "data/games/nm26-semifinal"
A = sys.argv[1:]
TRACK, DEST = A[0], A[1]
LABS = [x for x in json.loads((D / "goal-labels.json").read_text())["labels"] if x.get("goal_video_s")]
CW, CH = 420, 220


def H_fn(g):
    z = np.load(OUT / g / "H.npz"); f, Hn = z["frame"], np.c_[z["H8"], np.ones(len(z["H8"]))]
    def H(i):
        k = np.searchsorted(f, i)
        if k < len(f) and f[k] == i: return Hn[k].reshape(3, 3)
        if k == 0 or k >= len(f): return Hn[min(k, len(f) - 1)].reshape(3, 3)
        a, b = f[k - 1], f[k]; w = (i - a) / (b - a)
        return ((1 - w) * Hn[k - 1] + w * Hn[k]).reshape(3, 3)
    return H


def warped(g, i):
    H = H_fn(g)
    for k, a in frames(i / 30 - 0.001, i / 30 + 0.03):
        return cv2.warpPerspective(a, T_ROI @ H(k), (W_STAB, H_STAB))


def crop(w, c, cw, ch):
    x0 = int(np.clip(c[0] - cw / 2, 0, W_STAB - cw)); y0 = int(np.clip(c[1] - ch / 2, 0, H_STAB - ch))
    return w[y0:y0 + ch, x0:x0 + cw].copy(), x0, y0


if "--removed" in A or "--goal-frames" in A:
    lines = []
    if "--removed" in A:
        n = int(A[A.index("--removed") + 1]); rnd = random.Random(int(A[A.index("--seed") + 1]) if "--seed" in A else 1); ims = []
        for g in [f"g{k}" for k in range(1, 8)]:
            a = {r[0]: r for r in json.loads((D / g / "puck-track-synth.json").read_text())["rows"]}
            b = {r[0] for r in json.loads((D / g / TRACK).read_text())["rows"]}
            for f in sorted(rnd.sample(sorted(k for k in a if k not in b), n)):
                r = a[f]; c, x0, y0 = crop(warped(g, f), r[4:6], 280, 160)
                cv2.circle(c, (int(r[4] - x0), int(r[5] - y0)), 18, (0, 0, 255), 1)
                cv2.putText(c, f"{g} {f} score {r[7]:.2f}", (3, 14), 0, 0.45, (0, 0, 255), 1); ims.append(c)
        while len(ims) % 4: ims.append(np.zeros_like(ims[0]))
        lines = [np.hstack(ims[i:i + 4]) for i in range(0, len(ims), 4)]
    else:
        ids = A[A.index("--goal-frames") + 1].split(",")
        for x in [x for x in LABS if x["id"] in ids]:
            g = x["game"]; T = {r[0]: r for r in json.loads((D / g / TRACK).read_text())["rows"]}; fg = int(round(x["goal_video_s"] * 30))
            last = max(k for k in T if k <= fg); gx = 287.0 if x["scoring_end"] == "W" else -288.0
            c0 = np.array(T[last][4:6]); ims = []
            for i in range(last, last + 8):
                c, x0, y0 = crop(warped(g, i), c0 + [0.5 * (1 if gx > 0 else -1) * 140, 0], 380, 200)
                if i in T: cv2.circle(c, (int(T[i][4] - x0), int(T[i][5] - y0)), 17, (0, 200, 0), 1)
                cv2.putText(c, f"{x['id']} {i - fg:+d}", (3, 14), 0, 0.45, (0, 0, 255), 1); ims.append(c)
            lines.append(np.hstack(ims))
    cv2.imwrite(DEST, np.vstack(lines), [cv2.IMWRITE_JPEG_QUALITY, 82])
    print(len(lines), "lines", DEST); sys.exit()

picks = []
tracks = {}
for g in [f"g{k}" for k in range(1, 8)]:
    tracks[g] = {r[0]: r for r in json.loads((D / g / TRACK).read_text())["rows"]}
if "--goals" in A:
    for x in LABS:
        fg = int(round(x["goal_video_s"] * 30))
        for f, r in sorted(tracks[x["game"]].items()):
            if r[6] == "shot" and fg - 60 <= f <= fg + 6:
                picks.append((x["game"], f, x["id"]))
else:
    n = int(A[A.index("--sample") + 1]); rnd = random.Random(int(A[A.index("--seed") + 1]) if "--seed" in A else 1)
    allr = [(g, f, "") for g in tracks for f, r in tracks[g].items() if r[6] == "shot" and tracks[g].get(f - 1, [0] * 7)[6] != "shot"]
    picks = sorted(rnd.sample(allr, min(n, len(allr))))
lines = []
for g, f, tag in picks:
    T = tracks[g]; r = T[f]
    prev = max(k for k in T if k < f)
    c = (np.array(T[prev][4:6]) + np.array(r[4:6])) / 2
    x0 = int(np.clip(c[0] - CW / 2, 0, W_STAB - CW)); y0 = int(np.clip(c[1] - CH / 2, 0, H_STAB - CH))
    H = H_fn(g); ims = []
    for i, a in frames(prev / 30 - 0.001, (f + 2) / 30 - 0.001):
        w = cv2.warpPerspective(a, T_ROI @ H(i), (W_STAB, H_STAB))[y0:y0 + CH, x0:x0 + CW].copy()
        if i in T:
            q = T[i]; col = (0, 0, 255) if q[6] == "shot" else (0, 200, 0)
            cv2.circle(w, (int(q[4] - x0), int(q[5] - y0)), 17, col, 1)
        cv2.putText(w, f"{g} {i} {tag} {'' if i not in T else T[i][6] + ' %.2f' % T[i][7]}", (3, 14), 0, 0.45, (0, 0, 255), 1)
        ims.append(w)
    ims = ims[-4:] if len(ims) > 4 else ims
    while len(ims) < 4: ims.append(np.zeros((CH, CW, 3), np.uint8))
    lines.append(np.hstack(ims))
cv2.imwrite(DEST, np.vstack(lines) if lines else np.zeros((10, 10, 3), np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 85])
print(len(picks), "rows", DEST)
