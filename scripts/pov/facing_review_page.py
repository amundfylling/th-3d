"""Step 7: the facing-angle review page for the figures nearest the head camera (docs/pov-videos.md).

    python3 scripts/pov/facing_review_page.py <video> <track.npz> <segments.json> <model.pt> <out.html> <crops.json> [per_figure=60]

Figures: W-G, W-LD, W-RD (the camera's end) and E-LW, E-RW (the far team's wings, which attack that end). Frames:
usable frames (segments.json) spread evenly over the game, a different set per figure. The crop (200 x 200, upright,
1.25 crop px per mm at the figure's distance, as the POV model's crop but larger) is centred on the POV model's
localiser result for that figure, and the page draws the figure's slot centreline so the right figure is clear. The
model's own answer is NOT shown, so the taps are an independent test. The user taps the feet, then a point on the ice
in the facing direction; the page stores both in crop px (db collection "pov_facing"). crops.json keeps per crop the
frame, the camera (rv, tv), the lens and the 2 x 3 frame-to-crop affine, so a tap converts to a world rotation:
both taps back-projected onto the ice, theta = atan2 of the difference minus the end's home heading (W 0, E 180).
"""
import base64, json, os, sys
import numpy as np
import cv2
import torch

sys.path.insert(0, os.path.dirname(__file__))
import pov_figures as pf
from pov_common import K_of, read_frames, project
import camera_fit as cf

video, track, segs, model_path, out_html, out_json = sys.argv[1:7]
N = int(sys.argv[7]) if len(sys.argv) > 7 else 60
NEAR = ["W-G", "W-LD", "W-RD", "E-LW", "E-RW"]
NAME = {"G": "Goalie", "LD": "Left defence", "RD": "Right defence", "LW": "Left wing", "RW": "Right wing"}
KIT = {"W": "white/blue, your end", "E": "yellow, far team"}
S, PXMM = 200, 1.25
torch.set_num_threads(4)
T = np.load(track); R = T["rows"]; intr = T["intr"]; K, D = K_of(intr[0]), cf.dist_of(intr[1:])
net = pf.load(model_path)
seg = json.load(open(segs)); seg = seg["segments"] if isinstance(seg, dict) else seg
usable = [i for s in seg for i in range(int(s["start_frame"]), int(s["end_frame"]) + 1) if R[i, 11] > 0]
pick = np.array(usable)[np.linspace(0, len(usable) - 1, N * len(NEAR)).astype(int)]
frames = {}
for k in range(0, len(pick), 40): frames.update(read_frames(video, pick[k:k + 40]))
crops = []
for j, i in enumerate(pick):
    pid = NEAR[j % len(NEAR)]; r = R[i]; rv, tv = r[1:4], r[4:7]
    res = pf.localise(net, frames[i], rv, tv, K, D, pids=[pid])[pid]
    M = pf.crop_M(res["xy_mm"], rv, tv, K, D)
    if M is None: continue
    # the review crop: same orientation, 200 px wide at PXMM px/mm, figure at (100, 125)
    Mr = M.copy(); Mr[:, :2] *= PXMM / pf.CROP_PX_PER_MM; Mr[:, 2] = M[:, 2] * PXMM / pf.CROP_PX_PER_MM
    a = Mr @ np.r_[res["px"], 1.0]; Mr[:, 2] += np.array([100.0, 125.0]) - a
    img = cv2.warpAffine(frames[i], Mr, (S, S), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
    P = pf.resample(pf.SL[pid], 6.0); q = project(np.c_[P, np.zeros(len(P))], rv, tv, K, D)
    slot = [[round(float(x), 1), round(float(y), 1)] for x, y in (np.c_[q, np.ones(len(q))] @ Mr.T)]
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    crops.append({"id": f"{pid}-f{int(i)}", "pid": pid, "frame": int(i), "rv": [float(v) for v in rv], "tv": [float(v) for v in tv],
                  "lens": {"f": float(intr[0]), "k1": float(intr[1]), "k2": float(intr[2])}, "M_frame_to_crop": Mr.round(6).tolist(),
                  "model": {"xy_mm": [round(v, 1) for v in res["xy_mm"]], "theta_deg": round(res["theta_deg"], 1), "presence": round(res["presence"], 3)},
                  "slot": slot, "img": "data:image/jpeg;base64," + base64.b64encode(buf).decode()})
crops.sort(key=lambda c: (NEAR.index(c["pid"]), c["frame"]))
json.dump({"status": "PROPOSED", "description": "POV facing review crops (scripts/pov/facing_review_page.py). Crop px = "
           "M_frame_to_crop @ LRF frame px. model = the POV model's answer, not shown on the page.",
           "crops": [{k: v for k, v in c.items() if k not in ("img", "slot")} for c in crops]}, open(out_json, "w"), indent=1)
page = open(os.path.join(os.path.dirname(__file__), "facing-review.template.html")).read()
labels = {p: f"{NAME[p[2:]]} · {KIT[p[0]]}" for p in NEAR}
data = [{"id": c["id"], "pid": c["pid"], "frame": c["frame"], "slot": c["slot"], "img": c["img"]} for c in crops]
page = page.replace("/*DATA*/[]", json.dumps(data, separators=(",", ":"))).replace("/*LABELS*/{}", json.dumps(labels))
open(out_html, "w").write(page)
print(len(crops), "crops")
