"""Triangulate operator-read keypoints of the skater mold from the turntable frames (bundle adjustment).

    /root/venvs/blender/bin/python scripts/triangulate-figure-keypoints.py
Input: data/figure-keypoints.json (operator readings, crop px of references/derived/players/*.jpg).
Model: during 0-11 s of IMG_2574 the phone is still and the figure is turned on the table, so all frames
share one camera elevation, roll, distance and focal length; each frame has its own azimuth (figure turn)
and aim (pan/tilt, absorbing the small slide of the figure). Gauge: the socket base centre is the origin
(table plane z = 0); the camera distance is fixed at the silhouette-fit value (mold units ~ mm); azimuth of
the back view is free, the frame is later rotated so the face points +x.
Output: validation/players/skater-keypoints-3d.json (points, per-view residuals px).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_views as fv  # noqa: E402

REPO = fv.REPO
KP = json.loads((REPO / "data" / "figure-keypoints.json").read_text())["skater"]
views = KP["views"]
names = [n for n in KP["points"] if n != "socket"]
V = list(views)
FIT = json.loads((REPO / "out" / "figures" / "skater-fit.json").read_text())["views"]
TARGET = fv.TARGET["skater"]  # same aim point as fit-figure-views.py
DIST = FIT[KP["gauge_view"]]["camera"]["distance_mold_mm"]
F_FIXED = float(np.median([FIT[v]["camera"]["focal_px"] for v in views if v in FIT]))


def unpack(x):
    # focal fixed at the silhouette-fit value: with the distance as scale gauge, a free focal length trades
    # against point depth (it drifted to a near-orthographic, shrunken solution)
    el, roll, f = x[0], x[1], F_FIXED
    per = x[3:3 + 3 * len(V)].reshape(-1, 3)
    pts = x[3 + 3 * len(V):].reshape(-1, 3)
    P = {"socket": np.zeros(3)}
    P.update({n: pts[i] for i, n in enumerate(names)})
    return el, roll, f, per, P


def residuals(x):
    el, roll, f, per, P = unpack(x)
    r = []
    for i, v in enumerate(V):
        az, pan, tilt = per[i]
        it = fv.MANIFEST[v]
        params = [az, el, roll, pan, tilt, DIST, f]
        for n, uv in views[v].items():
            (u, w), = fv.project(P[n][None], params, TARGET, it["full_size_px"], it["crop_box_px"], 1.0)[0]
            r += [u - uv[0], w - uv[1]]
    return np.array(r)


def main():
    g = FIT[KP["gauge_view"]]["camera"]
    x0 = [math.radians(g["elevation_deg"]), math.radians(g["roll_deg"]), g["focal_px"]]
    for v in V:
        c = FIT[v]["camera"] if v in FIT else KP["init_cameras"][v]
        x0 += [math.radians(c["azimuth_deg"]), math.radians(c["pan_deg"]), math.radians(c["tilt_deg"])]
    for n in names:
        x0 += KP["points"][n]["guess_mm"]
    x0 = np.array(x0, float)
    sol = least_squares(residuals, x0, loss="soft_l1", f_scale=15.0, max_nfev=4000)
    el, roll, f, per, P = unpack(sol.x)
    # orient: face (chin) toward +x
    ch = P["chin"]
    rot = -math.atan2(ch[1], ch[0])
    Rz = np.array([[math.cos(rot), -math.sin(rot), 0], [math.sin(rot), math.cos(rot), 0], [0, 0, 1]])
    out = {"note": "Mold units ~ mm (gauge: camera distance fixed at the silhouette-fit value). Operator-read keypoints; see data/figure-keypoints.json.",
           "camera": {"elevation_deg": round(math.degrees(el), 2), "roll_deg": round(math.degrees(roll), 2), "focal_px": round(f, 1)},
           "frame_rotation_deg": round(math.degrees(rot), 2),
           "points_mm": {n: [round(float(c), 2) for c in Rz @ p] for n, p in P.items()},
           "views": {}}
    res = sol.fun.reshape(-1, 2)
    k = 0
    for i, v in enumerate(V):
        rr = {}
        for n in views[v]:
            rr[n] = round(float(np.hypot(*res[k])), 1)
            k += 1
        out["views"][v] = {"azimuth_deg": round(math.degrees(per[i][0]) + math.degrees(rot), 2), "residual_px": rr}
    out["rms_px"] = round(float(np.sqrt((res ** 2).sum(1).mean())), 2)
    dst = REPO / "validation" / "players"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "skater-keypoints-3d.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=1))


main()
