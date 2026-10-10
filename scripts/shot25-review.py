"""Iteration 25: review sheet of a rendered video - the whole playback (every 12th frame) and the frames that show the
contact events in the normal pass and in the replay (scripts/shot25-keyframes.ts).

    /root/venvs/blender/bin/python scripts/shot25-review.py VIDEO OUT.png
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
kf = json.loads(subprocess.run(["node", "scripts/shot25-keyframes.ts", str(fps)], cwd=REPO, capture_output=True, text=True, check=True).stdout)
frames = []
while True:
    ok, f = cap.read()
    if not ok:
        break
    frames.append(f)
n = len(frames)
H, W = frames[0].shape[:2]


def tile(i, w, label):
    """The frame scaled to width w, with its label in a band ABOVE the image (never over the captions)."""
    im = cv2.resize(frames[i], (w, int(w * H / W)), interpolation=cv2.INTER_AREA)
    band = np.full((22, w, 3), 255, np.uint8)
    cv2.putText(band, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 160), 1, cv2.LINE_AA)
    return np.vstack([band, im])


strip = [tile(i, 240, f"{i} ({i / fps:.2f} s)") for i in range(0, n, 12)]
while len(strip) % 8:
    strip.append(np.full_like(strip[0], 255))
rows = [np.hstack(strip[r:r + 8]) for r in range(0, len(strip), 8)]
key = []
for ev, v in kf["events"].items():
    for which in ("normal", "replay"):
        key.append(tile(v[which], 480, f"{ev} t={v['t']:.4f} s - {which} frame {v[which]}"))
keyrows = [np.hstack(key[r:r + 4]) for r in range(0, len(key), 4)]
width = max(rows[0].shape[1], keyrows[0].shape[1])
pad = lambda im: np.hstack([im, np.full((im.shape[0], width - im.shape[1], 3), 255, np.uint8)]) if im.shape[1] < width else im  # noqa: E731
head = np.full((40, width, 3), 255, np.uint8)
cv2.putText(head, f"25 - review of {video}: {n} frames at {fps} fps ({W}x{H}); top: every 12th frame; bottom: contact events (normal pass / replay)",
            (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
sheet = np.vstack([head] + [pad(r) for r in rows] + [np.full((16, width, 3), 255, np.uint8)] + [pad(r) for r in keyrows])
cv2.imwrite(str(REPO / out), sheet)
print("wrote", out, n, "frames")
