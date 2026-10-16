"""Review sheet for the puck baseline: for sampled frames the POV frame around puck-v1's top peak (circle; red if
score > 0.5, yellow otherwise), so a reader can mark each as on the puck or not.
Usage: python3 scripts/pov/baseline_puck_sheet.py <video> <baseline outdir> <out.jpg> [n]
"""
import json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from pov_common import read_frames, W_PX, H_PX

video, d, out = sys.argv[1:4]
n = int(sys.argv[4]) if len(sys.argv) > 4 else 24
R = json.load(open(os.path.join(d, "puck.json")))["rows"]
sel = [R[j] for j in np.linspace(0, len(R) - 1, n).astype(int)]
frs = read_frames(video, [r["frame"] for r in sel])
tiles = []
for r in sel:
    c = r["cands"][0]; x, y = c["pov_px"]
    img = frs[r["frame"]]
    x0 = int(np.clip(x - 120, 0, W_PX - 240)); y0 = int(np.clip(y - 90, 0, H_PX - 180))
    t = img[y0:y0 + 180, x0:x0 + 240].copy()
    col = (0, 0, 255) if c["score"] > 0.5 else (0, 255, 255)
    cv2.circle(t, (int(x - x0), int(y - y0)), 9, col, 2)
    t = cv2.resize(t, (360, 270), interpolation=cv2.INTER_CUBIC)
    cv2.putText(t, f"f{r['frame']} s{c['score']:.2f} {int(c['dist_from_camera_mm'])}mm", (5, 20), 0, 0.6, (0, 255, 0), 2)
    tiles.append(t)
rows = [np.hstack(tiles[i:i + 6]) for i in range(0, len(tiles), 6)]
cv2.imwrite(out, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
