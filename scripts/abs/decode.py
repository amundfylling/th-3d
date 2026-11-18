"""Decode and register the pilot window (game 2, goal 3) to the reference frame: out/abs/<goal>/<frame>.png (E half, 1x, ref px)."""
import json, sys
from pathlib import Path
import cv2, numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from nm26_common import Registrar, frames, reference_frame
gid, f0, f1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
lab = {r["id"]: r for r in json.loads((REPO / "data/games/nm26-semifinal/goal-labels.json").read_text())["labels"]}[gid]
HALF = (900, 360, 1900, 1000)
od = REPO / "out/abs" / gid; od.mkdir(parents=True, exist_ok=True)
reg = Registrar(reference_frame(lab["game"]))
Hs = {}
for i, a in frames((f0 - 20) / 30, (f1 + 1) / 30):
    H, n = reg(a)
    if i < f0: continue
    Hs[i] = n
    x0, y0, x1, y1 = HALF
    w = cv2.warpPerspective(a, np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.0]]) @ H, (x1 - x0, y1 - y0), flags=cv2.INTER_CUBIC)
    cv2.imwrite(str(od / f"{i}.png"), w)
(od / "inliers.json").write_text(json.dumps(Hs)); print(len(Hs), "frames; min inliers", min(Hs.values()))
