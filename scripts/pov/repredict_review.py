"""Step 7: re-run a POV figure model on the facing-review crops, so a new model is scored on the same taps.

    python3 scripts/pov/repredict_review.py <video> <model.pt> <facing-review-crops.json> <out.json>

Each crop's frame and stored camera are read again, the model's localiser runs for that crop's figure, and the
crop's "model" answer is replaced; everything else (the affine the taps refer to) stays. Score with score_facing.py.
"""
import json, os, sys
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(__file__))
import pov_figures as pf
from pov_common import K_of, read_frames
import camera_fit as cf

video, model_path, cj, out = sys.argv[1:5]
torch.set_num_threads(4)
net = pf.load(model_path); C = json.load(open(cj)); crops = C["crops"]
idx = sorted({c["frame"] for c in crops}); F = {}
for k in range(0, len(idx), 40): F.update(read_frames(video, idx[k:k + 40]))
for c in crops:
    K, D = K_of(c["lens"]["f"]), cf.dist_of([c["lens"]["k1"], c["lens"]["k2"]])
    r = pf.localise(net, F[c["frame"]], np.array(c["rv"]), np.array(c["tv"]), K, D, pids=[c["pid"]])[c["pid"]]
    c["model"] = {"xy_mm": [round(v, 1) for v in r["xy_mm"]], "theta_deg": round(r["theta_deg"], 1), "presence": round(r["presence"], 3),
                  "file": os.path.basename(model_path)}
json.dump(C, open(out, "w"), indent=1)
print(len(crops), "crops re-predicted")
