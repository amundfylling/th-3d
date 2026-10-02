"""Contour overlays for figure refinement: photo crop, then per model version the blue-part (helmet/collar) edges
(cyan), skin edges (magenta) and silhouette (yellow) of the preview mesh drawn through the frozen fitted camera
(painter's label render, scripts/figure_views.py projection).

    /root/venvs/blender/bin/python scripts/contour-overlay.py OUT.png CX,CY,CZ,R VIEW[,VIEW..] name=mesh.npz [...]
CX,CY,CZ,R: crop centre and radius in mold units. Meshes: out/figures/<kind>.npz from preview_molds.py (one per
version, copied aside)."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_views as fv  # noqa: E402

VAL = fv.REPO / "validation" / "players"
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
WORK = 1800


def cam(view):
    kind = view.split("-")[0]
    for t in ("", "-heldout", "-independent"):
        f = VAL / f"{kind}{t}-fit.json"
        if f.exists() and view in json.loads(f.read_text())["views"]:
            return kind, json.loads(f.read_text())["views"][view]["params"]
    raise KeyError(view)


def load(view):
    return fv.load_view(view, WORK)


def proj(view, pts):
    kind, p = cam(view)
    rgb, s, crop, full = load(view)
    return fv.project(np.asarray(pts, float), p, fv.TARGET[kind], full, crop, s)[0]


def label_render(view, npz):
    kind, p = cam(view)
    rgb, s, crop, full = load(view)
    d = np.load(npz)
    V, T, L = d["verts"], d["tris"], d["labels"]
    uv, z = fv.project(V, p, fv.TARGET[kind], full, crop, s)
    img = np.full(rgb.shape[:2], 255, np.uint8)
    pts = np.round(uv[T] * 4).astype(np.int32)
    for i in np.argsort(-z[T].mean(1)):  # far to near
        cv2.fillPoly(img, [pts[i]], int(L[i]), lineType=cv2.LINE_8, shift=2)
    return img, [str(k) for k in d["keys"]]


out = sys.argv[1]; c = [float(x) for x in sys.argv[2].split(',')]; views = sys.argv[3].split(',')
vers = [a.split('=', 1) for a in sys.argv[4:]]
T = 300
rows = []
for v in views:
    rgb, s, crop, full = load(v)
    uv = proj(v, [c[:3], [c[0], c[1], c[2] + c[3]]]); r = abs(uv[1][1] - uv[0][1]); cx, cy = uv[0]
    box = (int(cx - r), int(cy - r), int(cx + r), int(cy + r))
    tiles = [Image.fromarray(rgb).crop(box).resize((T, T), Image.LANCZOS)]
    for name, npz in vers:
        img, keys = label_render(v, npz)
        viz = rgb.copy()
        for k, col in (('blue', (0, 255, 255)), ('skin', (255, 0, 255))):
            m = (img == keys.index(k)).astype(np.uint8)
            e = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
            viz[e] = col
        sil = (img != 255).astype(np.uint8)
        viz[cv2.morphologyEx(sil, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)] = (255, 255, 0)
        t = Image.fromarray(viz).crop(box).resize((T, T), Image.NEAREST)
        ImageDraw.Draw(t).text((5, 5), name, fill=(255, 255, 255), font=F, stroke_width=2, stroke_fill=(0, 0, 0))
        tiles.append(t)
    row = Image.new('RGB', (T * len(tiles), T + 18), 'white'); d = ImageDraw.Draw(row)
    for i, t in enumerate(tiles): row.paste(t, (i * T, 18))
    d.text((4, 2), v + '   cyan = blue-part edges, magenta = skin edges, yellow = silhouette', fill=(0, 0, 0), font=F)
    rows.append(row)
o = Image.new('RGB', (rows[0].width, sum(r.height for r in rows)), 'white'); y = 0
for r in rows: o.paste(r, (0, y)); y += r.height
o.save(out); print('wrote', out)
