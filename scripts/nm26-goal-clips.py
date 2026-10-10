"""Short video clips of every NM26 goal for the user's goal review page (docs/nm26-game-patterns.md, open question 3).

    /root/venvs/blender/bin/python scripts/nm26-goal-clips.py [goal_id ...]

For each goal in data/games/nm26-semifinal/timeline.json with a score-box time, the clip runs from 30 s before the box
change to 1 s after it (the goal itself happens a few seconds before the box changes). Frames are warped to the
reference frame with the game's frames.json homography (so the rink is framed the same in every game) and cropped to
the rink (reference px ROI); 1024 x 376, 30 fps, H.264 (CRF 30, small enough for a phone). Writes out/nm26/goal-clips/<goal_id>.mp4 and
out/nm26/goal-clips/clips.json (goal_id, game, scorer, end, box time, clip start in video seconds).
"""
import json, sys
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nm26_common import frames, load, OUT  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
T = json.loads((REPO / "data/games/nm26-semifinal/timeline.json").read_text())["games"]
CFG = json.loads((REPO / "data/games/nm26-semifinal/config.json").read_text())
ROI = (160, 360, 1900, 1000); SIZE = (1024, 376); BEFORE, AFTER = 30.0, 1.0
D = OUT / "goal-clips"; D.mkdir(parents=True, exist_ok=True)

goals = []
for g, v in T.items():
    for k, x in enumerate(v["goals"]):
        if x.get("overlay_change_s") is None: continue
        scorer_end = "W" if x["scorer"] == v["left_end_player"] else "E"
        goals.append({"id": f"{g}-goal{k + 1}", "game": g, "n": k + 1, "scorer": x["scorer"], "end": scorer_end,
                      "box_s": x["overlay_change_s"], "game_time_s": x.get("game_time_s"), "in_regulation": x.get("in_regulation"),
                      "clip_start_s": x["overlay_change_s"] - BEFORE})
want = set(sys.argv[1:])
x0, y0, x1, y1 = ROI; T0 = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.0]])
Fs = {}
for gl in goals:
    if want and gl["id"] not in want: continue
    g = gl["game"]
    if g not in Fs: Fs[g] = {f[0]: f for f in load(OUT / g / "frames.json")}
    F = Fs[g]; H = None
    c = av.open(str(D / f"{gl['id']}.mp4"), "w", options={"movflags": "+faststart"})
    s = c.add_stream("libx264", rate=30); s.width, s.height = SIZE; s.pix_fmt = "yuv420p"
    s.options = {"crf": "30", "preset": "veryfast"}; s.time_base = Fraction(1, 30)
    n = 0
    for i, a in frames(gl["clip_start_s"], gl["box_s"] + AFTER):
        if i in F: H = np.r_[F[i][2], 1].reshape(3, 3)
        img = cv2.warpPerspective(a, T0 @ H, (x1 - x0, y1 - y0)) if H is not None else a[y0:y1, x0:x1]
        fr = av.VideoFrame.from_ndarray(cv2.resize(img, SIZE, interpolation=cv2.INTER_AREA), format="bgr24"); fr.pts = n; n += 1
        for p in s.encode(fr): c.mux(p)
    for p in s.encode(): c.mux(p)
    c.close(); gl["frames"] = n
    print(gl["id"], n, round((D / f"{gl['id']}.mp4").stat().st_size / 1e6, 2), "MB", flush=True)
(D / "clips.json").write_text(json.dumps([{k: v for k, v in x.items() if k != "frames"} for x in goals], indent=1) + "\n")
