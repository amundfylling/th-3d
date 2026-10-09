"""Build the goalie-facing label page (real NM26 crops; the user taps where the goalie's chest points).

    /root/venvs/blender/bin/python scripts/synth/goalie-facing-page.py

Crops: the 120 evaluation crops (out/synth/real_val_candidates.json) plus 40 more per end from all seven games, 200 in
all. Each crop carries the pivot pixel of the model's predicted slot position, where the arrow starts. The page stores
the taps in its db (collection "facing": tap_px and pivot_px in crop px, or verdict "unsure"); the tap direction on the
ice (inverse of the camera's ground-plane homography) is the goalie's facing.
Writes validation/goalie-facing-review.html and data/games/nm26-semifinal/goalie-facing-crops.json (crop list, no images).
"""
import base64, json, random, sys
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fit_goalie import K, R, t, BOX, SLOT, arc_point  # noqa: E402
import importlib.util  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("tr", Path(__file__).resolve().parent / "train-goalie-pose.py")
tr = importlib.util.module_from_spec(spec); sys.argv = [sys.argv[0], "0"]; spec.loader.exec_module(tr)
net = tr.model(); net.load_state_dict(torch.load(REPO / "out/synth/goalie-pose.pt")); net.eval()

C = json.load(open(REPO / "out/synth/real_val_candidates.json"))
NPZ = {g: np.load(REPO / f"out/synth/real_{g}.npz") for g in sorted({c["game"] for c in C})}
rnd = random.Random(26)
crops = [dict(id=c["id"], game=c["game"], end=c["end"], k=c["k"], frame=int(c["frame"]), set="eval") for c in C]
for end in "WE":
    for i in range(40):
        g = f"g{i % 7 + 1}"; n = len(NPZ[g]["idx"]); used = [c["k"] for c in crops if c["game"] == g and c["end"] == end]
        while True:
            k = rnd.randrange(n)
            if all(abs(k - u) >= 20 for u in used): break
        crops.append(dict(id=f"{g}-{end}-{int(NPZ[g]['idx'][k])}", game=g, end=end, k=k, frame=int(NPZ[g]["idx"][k]), set="extra"))
rnd.shuffle(crops)


def project(p):
    q = K @ (R @ np.array([p[0], p[1], 0.0]) + t); return q[:2] / q[2]


imgs = [None] * len(crops)
for g in NPZ:  # each npz key decompresses the whole array: load each once
    for end in "WE":
        A = NPZ[g][end]
        for i, c in enumerate(crops):
            if c["game"] == g and c["end"] == end: imgs[i] = A[c["k"]].copy()
        del A
with torch.no_grad():
    P = net(torch.stack([tr.to_tensor(im, c["end"]) for im, c in zip(imgs, crops)])).numpy()
for c, im, p in zip(crops, imgs, P):
    u = float(np.clip(p[0], 0, 1)); q = project(arc_point(SLOT[f"{c['end']}-G"], u)) - BOX[c["end"]][:2]
    c["pivot_px"] = [round(float(q[0]), 1), round(float(q[1]), 1)]; c["model_u"] = round(u, 3)
    c["model_theta_deg"] = round(float(np.degrees(np.arctan2(p[1], p[2])) % 360), 1)
    ok, buf = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 90]); c["img"] = "data:image/jpeg;base64," + base64.b64encode(buf).decode()

meta = {"description": "Real NM26 goalie crops for the facing labels (docs/synthetic-goalie-pilot.md). Crop px = reference "
        "video px minus goal_crop_boxes_video_px[end] (data/games/nm26-semifinal/camera-ref.json). pivot_px: the model's "
        "predicted slot position projected on the ice.", "crops": [{k: v for k, v in c.items() if k != "img"} for c in crops]}
(REPO / "data/games/nm26-semifinal/goalie-facing-crops.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")
page = (Path(__file__).resolve().parent / "goalie-facing.template.html").read_text()
data = [{k: c[k] for k in ("id", "game", "end", "pivot_px", "img")} for c in crops]
(REPO / "validation/goalie-facing-review.html").write_text(page.replace("/*DATA*/[]", json.dumps(data, separators=(",", ":"))))
print(len(crops), "crops")
