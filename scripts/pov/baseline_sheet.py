"""Review sheet for the step-5 baseline: per figure a row of crops as the model saw them (the to_tensor window),
with the predicted pivot (red dot), heading (arrow, raw output; 0 = the team's home heading) and presence.
Usage: python3 scripts/pov/baseline_sheet.py <baseline outdir> <out.jpg> [per_row]
"""
import math, os, pickle, sys
import numpy as np
import cv2

d, out = sys.argv[1], sys.argv[2]
per = int(sys.argv[3]) if len(sys.argv) > 3 else 8
C = pickle.load(open(os.path.join(d, "crops.pkl"), "rb"))
order = ["W-G", "W-LD", "W-RD", "E-LW", "E-RW", "W-C", "E-C", "E-LD", "E-RD", "W-LW", "W-RW", "E-G"]
rows = []
for pid in order:
    if pid not in C: continue
    tiles = []
    for i, crop, cxy, th, info in C[pid][:per]:
        t = cv2.resize(crop[20:190, 15:185], (170, 170))
        if cxy is not None:
            x, y = cxy[0] - 15, cxy[1] - 20
            cv2.circle(t, (int(x), int(y)), 4, (0, 0, 255), -1)
            cv2.putText(t, f"p{info['presence']:.2f} d{info['pivot_slot_dist_mm']:.0f}", (3, 165), 0, 0.42, (0, 255, 255), 1)
        else:
            cv2.putText(t, f"u{info['model_u']:.2f}/{info['loc_u']:.2f}", (3, 165), 0, 0.42, (0, 255, 255), 1)
        cv2.putText(t, f"{pid} f{i}", (3, 13), 0, 0.42, (0, 255, 255), 1)
        cv2.putText(t, f"{int(info['dist_from_camera_mm'])}mm th{th:.0f}", (3, 27), 0, 0.42, (0, 255, 255), 1)
        tiles.append(t)
    while len(tiles) < per: tiles.append(np.zeros_like(tiles[0]))
    rows.append(np.hstack(tiles))
cv2.imwrite(out, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
