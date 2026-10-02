"""Helmet-registered face overlays (round 12). The whole-figure camera fits place the head up to ~3 mold units off in
some frames (the head sits differently on the body than in the model), so face outlines are compared in the frame
of the frozen, rigid helmet: per view, the model's upper helmet is shifted in the image to best overlap the
photographed blue helmet (exhaustive integer search, IoU), and the same shift is applied to every model version.

    /root/venvs/blender/bin/python scripts/face-helmet-overlay.py OUT.png VIEW[,VIEW..] name=mesh.npz [...] [--shifts=OUT.json]

Meshes: preview meshes (out/figures/skater.npz from preview_molds.py). Face = skin triangles in front of the neck
(centroid x > 9.3); helmet = blue triangles entirely above z 40.6. Drawn: white = photographed skin outline (largest
warm region touching the model face, opened 3 px, closed 11 px), cyan = model helmet, magenta = model face.
Shifts are reported in pixels of a 2000-px work image and in mold units."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_views as fv  # noqa: E402

VAL = fv.REPO / "validation" / "players"
FN = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
WORK = 2000
T_ = 300


def cam(view):
    for t in ("", "-heldout", "-independent"):
        d = json.loads((VAL / f"skater{t}-fit.json").read_text())["views"]
        if view in d:
            return d[view]["params"]
    raise KeyError(view)


def labels(npz, view, rgb, s, crop, full):
    d = np.load(npz)
    V, T, L0, K = d["verts"], d["tris"], d["labels"], [str(k) for k in d["keys"]]
    L = L0.astype(int).copy()
    L[(L0 == K.index("blue")) & (V[T][:, :, 2].min(1) > 40.6)] = 60  # helmet
    L[(L0 == K.index("skin")) & (V[T].mean(1)[:, 0] > 9.3)] = 61  # face
    uv, z = fv.project(V, cam(view), fv.TARGET["skater"], full, crop, s)
    img = np.full(rgb.shape[:2], 255, np.int32)
    pts = np.round(uv[T] * 4).astype(np.int32)
    for i in np.argsort(-z[T].mean(1)):
        cv2.fillPoly(img, [pts[i]], int(L[i]), shift=2)
    return img


def shifted(m, dx, dy):
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(m.astype(np.uint8), M, (m.shape[1], m.shape[0]), flags=cv2.INTER_NEAREST).astype(bool)


def helmet_shift(hm, blue):
    ys, xs = np.nonzero(hm)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    roi = np.zeros_like(hm)
    roi[max(0, y0 - 120):int(y0 + 0.7 * (y1 - y0)), max(0, x0 - 120):x1 + 120] = True  # upper helmet only
    pb = blue & roi

    def iou(dx, dy):
        a = shifted(hm, dx, dy) & roi
        return (a & pb).sum() / max(1, (a | pb).sum())
    best = max(((iou(dx, dy), dx, dy) for dy in range(-100, 101, 4) for dx in range(-100, 101, 4)))
    _, bx, by = best
    best = max(((iou(dx, dy), dx, dy) for dy in range(by - 3, by + 4) for dx in range(bx - 3, bx + 4)))
    return best


def edge(m):
    return cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)


def main():
    out, views = sys.argv[1], sys.argv[2].split(",")
    vers = [a.split("=", 1) for a in sys.argv[3:] if not a.startswith("--")]
    shifts_out = next((a.split("=", 1)[1] for a in sys.argv[3:] if a.startswith("--shifts=")), None)
    rows, report = [], {}
    for v in views:
        rgb, s, crop, full = fv.load_view(v, WORK)
        blue, _, warm = fv.colour_classes(rgb)
        blue = cv2.morphologyEx(blue.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8)).astype(bool)
        warm = cv2.morphologyEx(cv2.morphologyEx(warm.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)),
                                cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
        imgs = [labels(npz, v, rgb, s, crop, full) for _, npz in vers]
        iou, dx, dy = helmet_shift(imgs[0] == 60, blue)  # the helmet is the same frozen part in every version
        p = fv.project(np.array([[12, -1, 38], [12, -1, 39]]), cam(v), fv.TARGET["skater"], full, crop, s)[0]
        pu = abs(p[1][1] - p[0][1])
        report[v] = {"shift_px": [int(dx), int(dy)], "shift_units": [round(dx / pu, 2), round(dy / pu, 2)], "helmet_iou": round(float(iou), 3)}
        fm0 = shifted(imgs[-1] == 61, dx, dy)
        n, lab, _, _ = cv2.connectedComponentsWithStats(warm, 8)
        k = 1 + int(np.argmax([((lab == j) & fm0).sum() for j in range(1, n)])) if n > 1 else 0
        pf = lab == k if k else np.zeros_like(fm0)
        cy, cx = np.argwhere(fm0).mean(0) if fm0.any() else (rgb.shape[0] / 2, rgb.shape[1] / 2)
        r = int(4.6 * pu)
        box = (int(cx - r), int(cy - r), int(cx + r), int(cy + r))
        tiles = [Image.fromarray(rgb).crop(box).resize((T_, T_), Image.LANCZOS)]
        for (name, _), img in zip(vers, imgs):
            viz = rgb.copy()
            viz[edge(pf)] = (255, 255, 255)
            viz[edge(shifted(img == 60, dx, dy))] = (0, 255, 255)
            viz[edge(shifted(img == 61, dx, dy))] = (255, 0, 255)
            t = Image.fromarray(viz).crop(box).resize((T_, T_), Image.NEAREST)
            ImageDraw.Draw(t).text((4, 4), name, fill=(255, 255, 255), font=FN, stroke_width=2, stroke_fill=(0, 0, 0))
            tiles.append(t)
        row = Image.new("RGB", (T_ * len(tiles), T_ + 18), "white")
        for i, t in enumerate(tiles):
            row.paste(t, (i * T_, 18))
        ImageDraw.Draw(row).text((4, 2), f"{v}  helmet shift {dx:+d},{dy:+d}px ({dx / pu:+.1f},{dy / pu:+.1f} u)  white photo skin, "
                                 "cyan model helmet, magenta model face", fill=(0, 0, 0), font=FN)
        rows.append(row)
    o = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)), "white")
    y = 0
    for r in rows:
        o.paste(r, (0, y))
        y += r.height
    o.save(out)
    if shifts_out:
        Path(shifts_out).write_text(json.dumps({"note": "per-view image shift of the frozen model helmet onto the photographed "
                                                "helmet (2000-px work image); the residual local camera error at the head",
                                                "views": report}, indent=1) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
