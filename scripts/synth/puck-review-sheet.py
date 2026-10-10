"""Contact sheet of registered frames with the current (red) and synthetic-detector (green) puck positions.

    /root/venvs/blender/bin/python scripts/synth/puck-review-sheet.py <out.jpg> <game>:<t0>:<t1>[:<step_frames>] [...]
        [--new puck-track-synth.json] [--crop 360x220] [--cols 6]

docs/synthetic-puck.md. Each tile: one frame warped to stab px (homography interpolated from out/nm26/<game>/H.npz),
cropped around the new position (else the old one, else the previous tile's centre); red circle = puck-track.json
(blob centre), green circle = the new track (top-face centre), label = game, video time, and which tracks have a
position. Used for the before/after review in the doc.
"""
import json, sys
from pathlib import Path
import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from nm26_common import OUT, T_ROI, W_STAB, H_STAB, frames  # noqa: E402

A = sys.argv[1:]
def arg(n, d): return A[A.index(n) + 1] if n in A else d
NEW = arg("--new", "puck-track-synth.json"); CW, CH = map(int, arg("--crop", "360x220").split("x")); COLS = int(arg("--cols", 6))
dest = A[0]; specs = [a for a in A[1:] if a.count(":") >= 2 and not a.startswith("--")]
D = REPO / "data/games/nm26-semifinal"
tiles = []
for sp in specs:
    p = sp.split(":"); g, t0, t1 = p[0], float(p[1]), float(p[2]); step = int(p[3]) if len(p) > 3 else 1
    old = {r[0]: r for r in json.loads((D / g / "puck-track.json").read_text())["rows"]}
    nf = D / g / NEW
    new = {r[0]: r for r in json.loads(nf.read_text())["rows"]} if nf.exists() else {}
    z = np.load(OUT / g / "H.npz"); fH, Hn = z["frame"], np.c_[z["H8"], np.ones(len(z["H8"]))]
    c = np.array([W_STAB / 2, H_STAB / 2])
    for i, a in frames(t0, t1):
        if (i - int(round(t0 * 30))) % step: continue
        k = np.searchsorted(fH, i); k = min(max(k, 1), len(fH) - 1); w_ = (i - fH[k - 1]) / max(fH[k] - fH[k - 1], 1)
        H = ((1 - np.clip(w_, 0, 1)) * Hn[k - 1] + np.clip(w_, 0, 1) * Hn[k]).reshape(3, 3)
        im = cv2.warpPerspective(a, T_ROI @ H, (W_STAB, H_STAB))
        o, n = old.get(i), new.get(i)
        if n: c = np.array(n[4:6])
        elif o: c = np.array(o[4:6])
        x0 = int(np.clip(c[0] - CW / 2, 0, W_STAB - CW)); y0 = int(np.clip(c[1] - CH / 2, 0, H_STAB - CH))
        t = im[y0:y0 + CH, x0:x0 + CW].copy()
        if o: cv2.circle(t, (int(o[4] - x0), int(o[5] - y0)), 16, (0, 0, 255), 2)
        if n: cv2.circle(t, (int(n[4] - x0), int(n[5] - y0)), 12, (0, 220, 0), 2)
        lab = f"{g} {i / 30:.2f}s {'O' if o else '-'}{'N' if n else '-'}"
        cv2.putText(t, lab, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3); cv2.putText(t, lab, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        tiles.append(t)
while len(tiles) % COLS: tiles.append(np.zeros((CH, CW, 3), np.uint8))
sheet = np.vstack([np.hstack(tiles[r:r + COLS]) for r in range(0, len(tiles), COLS)])
cv2.imwrite(dest, sheet, [cv2.IMWRITE_JPEG_QUALITY, 85]); print(dest, len(tiles), sheet.shape)
