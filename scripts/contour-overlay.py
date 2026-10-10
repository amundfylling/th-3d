"""Contour overlays for figure refinement: photo crop, then per model version the blue-part (helmet/collar) edges
(cyan), skin edges (magenta) and silhouette (yellow) of the preview mesh drawn through the frozen fitted camera
(painter's label render, scripts/figure_views.py projection).

    /root/venvs/blender/bin/python scripts/contour-overlay.py OUT.png CX,CY,CZ,R VIEW[,VIEW..] name=mesh.npz [...]
CX,CY,CZ,R: crop centre and radius in mold units. Meshes: out/figures/<kind>.npz from preview_molds.py (one per
version, copied aside). `--photo-skin` (round 11) also draws the photographed skin outline (white; largest warm
colour region in the crop, opened 3 px, closed 15 px and hole-filled against blur/compression/highlights) on every tile."""
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
PHOTO_SKIN = '--photo-skin' in sys.argv[4:]
vers = [a.split('=', 1) for a in sys.argv[4:] if a != '--photo-skin']


def photo_skin_edge(rgb, box):
    warm = fv.colour_classes(rgb)[2].astype(np.uint8)
    warm = cv2.morphologyEx(warm, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    warm = cv2.morphologyEx(warm, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    sub = np.zeros_like(warm)
    b = [max(0, q) for q in box]
    sub[b[1]:b[3], b[0]:b[2]] = warm[b[1]:b[3], b[0]:b[2]]
    n, lab, st, _ = cv2.connectedComponentsWithStats(sub, 8)
    m = np.zeros_like(sub)
    if n > 1:
        m[lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))] = 1
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)  # outer outline only (highlight holes filled)
    m = np.zeros_like(m)
    cv2.drawContours(m, cnts, -1, 1, -1)
    return cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
T = 300
rows = []
for v in views:
    rgb, s, crop, full = load(v)
    uv = proj(v, [c[:3], [c[0], c[1], c[2] + c[3]]]); r = abs(uv[1][1] - uv[0][1]); cx, cy = uv[0]
    box = (int(cx - r), int(cy - r), int(cx + r), int(cy + r))
    pe = photo_skin_edge(rgb, box) if PHOTO_SKIN else None
    if pe is not None:
        ph = rgb.copy(); ph[pe] = (255, 255, 255)
        tiles = [Image.fromarray(ph).crop(box).resize((T, T), Image.LANCZOS)]
    else:
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
        if pe is not None:
            viz[pe] = (255, 255, 255)
        t = Image.fromarray(viz).crop(box).resize((T, T), Image.NEAREST)
        ImageDraw.Draw(t).text((5, 5), name, fill=(255, 255, 255), font=F, stroke_width=2, stroke_fill=(0, 0, 0))
        tiles.append(t)
    row = Image.new('RGB', (T * len(tiles), T + 18), 'white'); d = ImageDraw.Draw(row)
    for i, t in enumerate(tiles): row.paste(t, (i * T, 18))
    d.text((4, 2), v + '   cyan = blue-part edges, magenta = skin edges, yellow = silhouette'
           + (', white = photo skin outline' if pe is not None else ''), fill=(0, 0, 0), font=F)
    rows.append(row)
o = Image.new('RGB', (rows[0].width, sum(r.height for r in rows)), 'white'); y = 0
for r in rows: o.paste(r, (0, y)); y += r.height
o.save(out); print('wrote', out)
