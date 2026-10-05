"""Review sheet of the analysis video: the whole video (every 15th frame) and one large frame from the middle of every
segment of the analysis timeline (data/presentations/shovel-17.analysis.json).

    /root/venvs/blender/bin/python scripts/analysis-review.py validation/analysis-shovel-17.mp4 validation/analysis-shovel-17-review.png
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
video, out = sys.argv[1], sys.argv[2]
cap = cv2.VideoCapture(str(REPO / video))
fps = round(cap.get(cv2.CAP_PROP_FPS))
frames = []
while True:
    ok, f = cap.read()
    if not ok:
        break
    frames.append(f)
n = len(frames)
H, W = frames[0].shape[:2]
script = (
    "import { readFileSync } from 'node:fs'; import { resolveAnalysis } from './src/model/analysis.ts';"
    "const a = resolveAnalysis(JSON.parse(readFileSync('data/presentations/shovel-17.analysis.json','utf8')),"
    " JSON.parse(readFileSync('data/traces/shovel-17.trace.json','utf8')));"
    "console.log(JSON.stringify(a.timeline.segments.map(s => [s.id, s.kind, s.f0, s.f1])));"
)
segments = json.loads(subprocess.run(["node", "--input-type=module", "-e", script], cwd=REPO, capture_output=True, text=True, check=True).stdout)


def tile(i, w, label):
    """The frame scaled to width w, with its label in a band ABOVE the image (never over the captions)."""
    im = cv2.resize(frames[i], (w, int(w * H / W)), interpolation=cv2.INTER_AREA)
    band = np.full((22, w, 3), 255, np.uint8)
    cv2.putText(band, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 160), 1, cv2.LINE_AA)
    return np.vstack([band, im])


strip = [tile(i, 240, f"{i} ({i / fps:.2f} s)") for i in range(0, n, 15)]
while len(strip) % 10:
    strip.append(np.full_like(strip[0], 255))
rows = [np.hstack(strip[r:r + 10]) for r in range(0, len(strip), 10)]
key = [tile(min(n - 1, int((f0 + f1) / 2)), 600, f"{sid} ({kind}) frame {int((f0 + f1) / 2)}") for sid, kind, f0, f1 in segments]
while len(key) % 4:
    key.append(np.full_like(key[0], 255))
keyrows = [np.hstack(key[r:r + 4]) for r in range(0, len(key), 4)]
width = max(rows[0].shape[1], keyrows[0].shape[1])
pad = lambda im: np.hstack([im, np.full((im.shape[0], width - im.shape[1], 3), 255, np.uint8)]) if im.shape[1] < width else im  # noqa: E731
head = np.full((40, width, 3), 255, np.uint8)
cv2.putText(head, f"Analysis video review - {video}: {n} frames at {fps} fps ({W}x{H}); top: every 15th frame; bottom: middle frame of every segment",
            (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
sheet = np.vstack([head] + [pad(r) for r in rows] + [np.full((16, width, 3), 255, np.uint8)] + [pad(r) for r in keyrows])
cv2.imwrite(str(REPO / out), sheet, [cv2.IMWRITE_PNG_COMPRESSION, 9])
print("wrote", out, n, "frames", sheet.shape)
