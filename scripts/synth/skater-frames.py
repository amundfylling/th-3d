"""Sample registered NM26 frames for the skater label page (docs/synthetic-goalie-pilot.md, skaters).

    /root/venvs/blender/bin/python scripts/synth/skater-frames.py <game> [count]

Picks <count> (default 40) random live-play frames of the game (start tone to the end of regulation, at least 3 s
apart), warps each to the reference frame (game 1 at 180 s) with the game's frames.json homography and saves the rink
area as out/synth/skaters/frames/<game>_<frame>.jpg (reference video px, offset ROI[:2]).
"""
import json, random, sys
from pathlib import Path
import cv2, numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nm26_common import frames, load, OUT, CFG  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
ROI = (160, 360, 1900, 1000)  # reference video px: x0, y0, x1, y1 (the rink with figure height)
g = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
T = json.loads((REPO / "data/games/nm26-semifinal/timeline.json").read_text())["games"][g]
t0 = T["start_signal_s"]; t1 = min(t0 + 300.0, CFG["games"][g]["video_window_s"][1] - 1)
F = {f[0]: f for f in load(OUT / g / "frames.json")}
rnd = random.Random(f"skaters-{g}"); ts = []
while len(ts) < n:
    t = rnd.uniform(t0 + 2, t1)
    if all(abs(t - u) >= 3 for u in ts) and int(round(t * 30)) in F: ts.append(t)
out = REPO / "out/synth/skaters/frames"; out.mkdir(parents=True, exist_ok=True)
x0, y0, x1, y1 = ROI; T0 = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.0]])
for t in sorted(ts):
    want = int(round(t * 30))
    for i, a in frames(t - 0.02, t + 0.2):
        if i in F and i >= want:
            H = np.r_[F[i][2], 1].reshape(3, 3)
            cv2.imwrite(str(out / f"{g}_{i}.jpg"), cv2.warpPerspective(a, T0 @ H, (x1 - x0, y1 - y0)), [cv2.IMWRITE_JPEG_QUALITY, 93])
            break
print(g, len(list(out.glob(f"{g}_*.jpg"))))
