"""Register and warp (stab px) the frames of each marked goal window: goal-2.5 s .. goal+0.5 s.
    python3 scripts/synth/streak/extract-goal-windows.py
Output: out/streak/goals/<goal id>/<frame>.jpg (JPEG q95) and index.json. Hypothesis experiment (docs/streak-puck.md)."""
import json, sys
from multiprocessing import Pool
from pathlib import Path
import cv2
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from nm26_common import CFG, DATA, T_ROI, W_STAB, H_STAB, Registrar, frames, reference_frame, REPO
DEST = REPO / "out/streak/goals"

def job(g):
    gid, game, t = g["id"], g["game"], g["goal_video_s"]
    d = DEST / gid; d.mkdir(parents=True, exist_ok=True)
    reg = Registrar(reference_frame(game)); idx = []
    for i, a in frames(t - 2.5, t + 0.5):
        H, n = reg(a)
        w = cv2.warpPerspective(a, T_ROI @ H, (W_STAB, H_STAB), flags=cv2.INTER_LINEAR)
        cv2.imwrite(str(d / f"{i}.jpg"), w, [cv2.IMWRITE_JPEG_QUALITY, 95]); idx.append([i, n])
    return gid, idx

if __name__ == "__main__":
    labels = json.loads((DATA / "goal-labels.json").read_text())["labels"]
    with Pool(4) as p:
        res = dict(p.map(job, labels))
    (DEST / "index.json").write_text(json.dumps(res))
    print({k: len(v) for k, v in res.items()})
