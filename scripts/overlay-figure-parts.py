"""Part-boundary overlay: the mold's visible part regions (helmet/face/jersey/blue/stick...) outlined on the photo
at each fitted camera - the working view for refining details (helmet, face, arms, gloves, pads).

    /root/venvs/blender/bin/python scripts/overlay-figure-parts.py skater|goalie [view ...] [--out FILE] [--px 700]
Mesh: out/figures/<kind>.npz (assets/blender/preview_molds.py). Cameras: validation/players/<kind>-fit.json and
<kind>-heldout-fit.json (kept fixed: the overlay shows how the current model departs from the photo).
Colours: kit = yellow, blue parts = cyan, skin = magenta, stick = white, silhouette = green.
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_views as fv  # noqa: E402

COL = {"kit": (255, 230, 0), "blue": (0, 255, 255), "skin": (255, 0, 255), "stick_metal": (255, 255, 255), "stick_tan": (255, 150, 60), "socket_bore": (255, 80, 80)}


def label_map(verts, tris, labels, params, target, shape, full, crop, s):
    uv, z = fv.project(verts, params, target, full, crop, s)
    R, C, _f = fv.camera(params, target)
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    n = np.cross(b - a, c - a)
    facing = (n * (C - (a + b + c) / 3)).sum(1) > 0
    depth = z[tris].mean(1)
    lab = np.full(shape, -1, np.int16)
    for i in np.argsort(-depth):
        if facing[i]:
            cv2.fillConvexPoly(lab, np.round(uv[tris[i]] * 4).astype(np.int32), int(labels[i]), shift=2)
    return lab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind")
    ap.add_argument("views", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--px", type=int, default=700)
    a = ap.parse_args()
    repo = fv.REPO
    d = np.load(repo / "out" / "figures" / f"{a.kind}.npz")
    keys = [str(k) for k in d["keys"]]
    cams = {}
    for f in (f"{a.kind}-fit.json", f"{a.kind}-heldout-fit.json"):
        p = repo / "validation" / "players" / f
        if p.exists():
            cams.update({k: v["params"] for k, v in json.loads(p.read_text())["views"].items()})
    tiles = []
    for vid in (a.views or list(cams)):
        rgb, s, crop, full = fv.load_view(vid, a.px)
        lab = label_map(d["verts"], d["tris"], d["labels"], np.array(cams[vid]), fv.TARGET[a.kind], rgb.shape[:2], full, crop, s)
        out = rgb.copy()
        for k, name in enumerate(keys):
            m = (lab == k).astype(np.uint8)
            if m.any():
                e = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
                out[e] = COL[name]
        sil = (lab >= 0).astype(np.uint8)
        e = cv2.morphologyEx(sil, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
        out[e] = (0, 255, 0)
        tiles.append(np.concatenate([rgb, out], 1))
    H = max(t.shape[0] for t in tiles)
    tiles = [np.pad(t, ((0, H - t.shape[0]), (0, 0), (0, 0))) for t in tiles]
    img = Image.fromarray(np.concatenate(tiles, 1))
    dst = Path(a.out) if a.out else repo / "out" / "figures" / f"overlay-{a.kind}.png"
    img.save(dst)
    print("wrote", dst, img.size)


main()
