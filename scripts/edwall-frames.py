"""Registered broadcast frames around Nygård's Edwall hat-trick goals (game 2, goals 2-4), for reading the puck by eye.

    /root/venvs/blender/bin/python scripts/edwall-frames.py <goal_id> [seconds_before] [seconds_after]

Decodes out/dl/nm26.webm (config.json video), registers every frame to the game's reference frame (nm26_common.Registrar)
and writes the attacking (E) half at 2x: out/edwall/<goal_id>/<frame>.png (cache, not committed), plus
out/edwall/<goal_id>/homographies.json (video px -> reference px per frame). World mm -> reference px is the reference
camera (camera-ref.json, zoom 1.006 for g2 folded in by the registration).
"""
import json, sys
from pathlib import Path
import cv2, numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from nm26_common import Registrar, frames, reference_frame  # noqa: E402

gid = sys.argv[1]; before = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0; after = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
lab = {r["id"]: r for r in json.loads((REPO / "data/games/nm26-semifinal/goal-labels.json").read_text())["labels"]}[gid]
HALF = (900, 360, 1900, 1000)  # attacking half (E), reference px
x0, y0, x1, y1 = HALF; T0 = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.0]]); S = np.diag([2.0, 2.0, 1.0])
od = REPO / "out/edwall" / gid; od.mkdir(parents=True, exist_ok=True)
reg = Registrar(reference_frame(lab["game"]))
t_goal = lab["goal_video_s"]; Hs = {}
# warm the registrar on a few frames before the window (it keeps the previous homography when a frame fails)
for i, a in frames(t_goal - before - 0.3, t_goal + after):
    H, n = reg(a)
    if i / 30 < t_goal - before: continue
    Hs[i] = {"H": [round(float(x), 8) for x in H.ravel()[:8]], "inliers": n}
    cv2.imwrite(str(od / f"{i}.png"), cv2.warpPerspective(a, S @ T0 @ H, (2 * (x1 - x0), 2 * (y1 - y0)), flags=cv2.INTER_CUBIC))
(od / "homographies.json").write_text(json.dumps({"half_ref_px": HALF, "scale": 2, "frames": Hs}))
print(gid, len(Hs), "frames ->", od)
