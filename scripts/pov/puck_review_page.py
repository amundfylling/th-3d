"""Step 8: the near-end puck tap page (docs/pov-videos.md).

    python3 scripts/pov/puck_review_page.py <video> <track.npz> <segments.json> <out.html> <crops.json> [n=150]

Frames: usable frames (segments.json) spread evenly over the game (no detector picks them, so the set is not biased
toward easy pucks). Each picture is the near half of the table (ice x <= 0: the head camera's end), cut from the LRF
frame and enlarged 2x. The user taps the puck's centre, or says it is not in this half, or can't find it (db
collection "pov_puck"). crops.json keeps per picture the frame, camera, lens and the crop's origin and scale, so a tap
converts back to frame px (frame = origin + tap / scale) and onto the ice. These taps are the first real POV puck
labels: the hard cases (under a blade, at the boards) are the taps near a figure or a board.
"""
import base64, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from pov_common import K_of, read_frames, project, W_PX, H_PX
import camera_fit as cf

video, track, segs, out_html, out_json = sys.argv[1:6]
N = int(sys.argv[6]) if len(sys.argv) > 6 else 150
SC = 2.0
T = np.load(track); R = T["rows"]; intr = T["intr"]; K, D = K_of(intr[0]), cf.dist_of(intr[1:])
seg = json.load(open(segs))["segments"]
usable = [i for s in seg for i in range(int(s["start_frame"]), int(s["end_frame"]) + 1) if R[i, 11] > 0]
pick = np.array(usable)[np.linspace(0, len(usable) - 1, N).astype(int)]
frames = {}
for k in range(0, len(pick), 40): frames.update(read_frames(video, pick[k:k + 40]))
HALF = np.array([(x, y, z) for x in np.linspace(-430, 10, 12) for y in (-245, 245) for z in (0.0, 40.0)])
items = []
for i in pick:
    r = R[i]; q = project(HALF, r[1:4], r[4:7], K, D)
    x0, y0 = np.clip(np.floor(q.min(0)) - 6, 0, [W_PX, H_PX]).astype(int); x1, y1 = np.clip(np.ceil(q.max(0)) + 6, 0, [W_PX, H_PX]).astype(int)
    if x1 - x0 < 50 or y1 - y0 < 50: continue
    img = cv2.resize(frames[i][y0:y1, x0:x1], None, fx=SC, fy=SC, interpolation=cv2.INTER_CUBIC)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    items.append({"id": f"f{int(i)}", "frame": int(i), "rv": [float(v) for v in r[1:4]], "tv": [float(v) for v in r[4:7]],
                  "lens": {"f": float(intr[0]), "k1": float(intr[1]), "k2": float(intr[2])}, "origin_px": [int(x0), int(y0)], "scale": SC,
                  "w": int(img.shape[1]), "h": int(img.shape[0]), "img": "data:image/jpeg;base64," + base64.b64encode(buf).decode()})
json.dump({"status": "PROPOSED", "description": "Near-end puck tap pictures (scripts/pov/puck_review_page.py). frame px = origin_px + tap_px / scale.",
           "pictures": [{k: v for k, v in c.items() if k != "img"} for c in items]}, open(out_json, "w"), indent=1)
page = open(os.path.join(os.path.dirname(__file__), "puck-review.template.html")).read()
data = [{"id": c["id"], "frame": c["frame"], "w": c["w"], "h": c["h"], "img": c["img"]} for c in items]
open(out_html, "w").write(page.replace("/*DATA*/[]", json.dumps(data, separators=(",", ":"))))
print(len(items), "pictures")
