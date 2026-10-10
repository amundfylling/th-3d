"""Sheet of skater-v3 training samples as the network sees them (docs/tracker-v3.md): composited renders with the
target skater's name, presence and (when present) its pivot and facing. Checks the re-targeting and the hard-example
labels by eye. Writes validation/tracker-v3-training-samples.jpg.

    /root/venvs/blender/bin/python scripts/synth/tracker-v3-samples.py
"""
import importlib.util, json, math, random, sys
from pathlib import Path
import cv2, numpy as np

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("tv", REPO / "scripts/synth/train-skater-v3.py"); tv = importlib.util.module_from_spec(spec)
_argv = sys.argv; sys.argv = [_argv[0], "0"]; spec.loader.exec_module(tv); sys.argv = _argv
L = []
for d in ("train", "hard"):
    D = REPO / "out/synth/skaters" / d
    for l in map(json.loads, open(D / "labels.jsonl")):
        l["path"] = str(D / f"{l['seed']}.png"); L.append(l)
rnd = random.Random(3); E = tv.entries(rnd.sample(L, 300), rnd)
pick = [e for e in E if e[0].get("kind", "base") == "base" and e[1] != e[0]["pid"]][:8] + [e for e in E if e[0].get("kind") in ("offset", "hidden")][:4] + \
       [e for e in E if e[0].get("kind") == "hard"][:4]
ds = tv.DS(pick, False); tiles = []
for k in range(len(pick)):
    x, y = ds[k]; img = (x[:3].numpy().transpose(1, 2, 0) * tv.ts.STD + tv.ts.MEAN)[..., ::-1]; img = np.ascontiguousarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    img = cv2.resize(img, (240, 240)); l, pid, piv, th, pres = pick[k]
    if pres:
        px, py = y[0].item() * 240, y[1].item() * 240; a = math.atan2(y[2].item(), y[3].item())
        cv2.circle(img, (int(px), int(py)), 5, (0, 0, 255), -1)
    tag = f"{pid} {'present' if pres else 'ABSENT'} {l.get('kind', 'base')}{'' if pid == l['pid'] else ' (re-targeted)'}"
    cv2.putText(img, tag, (3, 14), 0, 0.4, (0, 0, 0), 3); cv2.putText(img, tag, (3, 14), 0, 0.4, (255, 255, 255), 1); tiles.append(img)
tiles += [np.zeros_like(tiles[0])] * (-len(tiles) % 4)
cv2.imwrite(str(REPO / "validation/tracker-v3-training-samples.jpg"), np.vstack([np.hstack(tiles[r:r + 4]) for r in range(0, len(tiles), 4)]), [cv2.IMWRITE_JPEG_QUALITY, 85])
print(len(pick))
