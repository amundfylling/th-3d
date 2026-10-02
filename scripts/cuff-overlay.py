"""Upper-cuff boundary overlay (skater right gauntlet): photo crop with the photo's blue-plastic boundary (white,
segmented with scripts/figure_views.colour_classes) and hand-marked rim points, and per model version the
visible cuff region (magenta outline) and the other blue parts (cyan) drawn through the frozen fitted camera.

    /root/venvs/blender/bin/python scripts/cuff-overlay.py OUT.png VIEW[,VIEW..] name=mesh.npz,cuff.npz [...]
mesh.npz: preview mesh (preview_molds.py); cuff.npz: the gauntlet_r loft alone (same units) - triangles of the
preview mesh closer than 0.3 mold units to it are labelled cuff. Rim marks: data/cuff-marks-r10.json (optional).
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_views as fv  # noqa: E402

REPO = fv.REPO
VAL = REPO / "validation" / "players"
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
WORK = 1800
CENTRE, RAD = (5.5, -9.0, 29.0), 9.5
MARKS = REPO / "data" / "cuff-marks-r10.json"


def cam(view):
    for t in ("", "-heldout", "-independent"):
        f = VAL / f"skater{t}-fit.json"
        if f.exists() and view in json.loads(f.read_text())["views"]:
            return json.loads(f.read_text())["views"][view]["params"]
    raise KeyError(view)


def labels(view, mesh, cuff):
    p = cam(view)
    rgb, s, crop, full = fv.load_view(view, WORK)
    d = np.load(mesh)
    V, T, L, K = d["verts"], d["tris"], d["labels"].astype(int).copy(), [str(k) for k in d["keys"]]
    cv_ = np.load(cuff)["verts"]
    near = cKDTree(cv_).query(V[T].mean(1))[0] < 0.3
    L[near & (L == K.index("blue"))] = 99
    uv, z = fv.project(V, p, fv.TARGET["skater"], full, crop, s)
    img = np.full(rgb.shape[:2], 255, np.uint8)
    pts = np.round(uv[T] * 4).astype(np.int32)
    for i in np.argsort(-z[T].mean(1)):
        cv2.fillPoly(img, [pts[i]], int(L[i]), lineType=cv2.LINE_8, shift=2)
    return rgb, img, K, (s, crop, full, p)


def edge(m, k=3):
    return cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((k, k), np.uint8)).astype(bool)


def main():
    out, views = sys.argv[1], sys.argv[2].split(",")
    vers = [(a.split("=", 1)[0], *a.split("=", 1)[1].split(",")) for a in sys.argv[3:]]
    marks = json.loads(MARKS.read_text())["views"] if MARKS.exists() else {}
    T_ = 340
    rows = []
    for v in views:
        tiles = []
        for j, (name, mesh, cuff) in enumerate(vers):
            rgb, img, K, (s, crop, full, p) = labels(v, mesh, cuff)
            uv = fv.project(np.array([CENTRE, [CENTRE[0], CENTRE[1], CENTRE[2] + RAD]]), p, fv.TARGET["skater"], full, crop, s)[0]
            r = abs(uv[1][1] - uv[0][1]); cx, cy = uv[0]
            box = (int(cx - r), int(cy - r), int(cx + r), int(cy + r))
            blue = fv.colour_classes(rgb)[0]
            blue = cv2.morphologyEx(blue.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool)
            if j == 0:
                ph = rgb.copy(); ph[edge(blue, 3)] = (255, 255, 255)
                t = Image.fromarray(ph).crop(box).resize((T_, T_), Image.LANCZOS)
                dr = ImageDraw.Draw(t)
                for line in marks.get(v, {}).get("rim", []):
                    q = [((x - box[0]) * T_ / (box[2] - box[0]), (y - box[1]) * T_ / (box[3] - box[1])) for x, y in line]
                    dr.line(q, fill=(255, 210, 0), width=3)
                dr.text((5, 5), "PHOTO: white = blue plastic edge, orange = rim (marked)", fill=(255, 255, 255), font=F, stroke_width=2, stroke_fill=(0, 0, 0))
                tiles.append(t)
            viz = (rgb * 0.75).astype(np.uint8)
            viz[edge(blue, 3)] = (255, 255, 255)
            viz[edge(img == K.index("blue"), 3)] = (0, 230, 255)
            viz[edge(img == 99, 5)] = (255, 0, 255)
            t = Image.fromarray(viz).crop(box).resize((T_, T_), Image.NEAREST)
            ImageDraw.Draw(t).text((5, 5), f"{name}: magenta = model cuff, cyan = other blue", fill=(255, 255, 255), font=F, stroke_width=2, stroke_fill=(0, 0, 0))
            tiles.append(t)
        row = Image.new("RGB", (T_ * len(tiles), T_ + 18), "white")
        ImageDraw.Draw(row).text((4, 2), v, fill=(0, 0, 0), font=F)
        for i, t in enumerate(tiles):
            row.paste(t, (i * T_, 18))
        rows.append(row)
    o = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)), "white")
    y = 0
    for r in rows:
        o.paste(r, (0, y)); y += r.height
    o.save(out)
    print("wrote", out, o.size)


main()
