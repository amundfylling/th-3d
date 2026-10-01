"""Matched-camera close-up comparisons of the figure assets against the user's photos/videos.

    /root/venvs/blender/bin/python assets/blender/render_closeups.py [skater|goalie ...]
For every fitted view (validation/players/<kind>-fit.json), every former held-out view (<kind>-heldout-fit.json,
inspected while modelling since round 3, so now a fitting reference) and every INDEPENDENT frame
(<kind>-independent-fit.json: fresh frames, inspected only after the round's modelling) the Sweden asset is rendered with Cycles from
the fitted camera at the photo crop's framing. Feature windows (head, arms/torso, back print, mask, pads,
gloves) are projected from the mold frame into both images and cut identically.
Outputs: validation/players/closeups-<kind>.png (rows = views; full photo | full render | feature pairs),
out/figures/closeups/*.png (per-view renders).
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402
import build_figures as bf  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import bpy  # noqa: E402

REPO = sb.REPO
VAL = REPO / "validation" / "players"
OUT = REPO / "out" / "figures" / "closeups"
MAN = json.loads((REPO / "references" / "derived" / "players" / "manifest.json").read_text())["items"]
# Feature windows: centre (mold units) and radius (mold units); 'face' = direction the feature faces (None = any).
FEATURES = {
    "skater": {"head": ((7.5, -2.4, 41.5), 7.5, None), "arms/torso": ((2.0, -5.0, 29.0), 15.0, None),
               "back print": ((-6.4, -4.0, 32.0), 10.0, (-1, 0, 0.4)), "gloves": ((6.6, 0.0, 22.0), 9.0, (1, 0, 0))},
    "goalie": {"mask": ((1.5, 5.0, 41.5), 7.5, None), "pads": ((3.0, 5.0, 11.5), 13.0, (1, 0, 0)),
               "catcher": ((4.5, 17.5, 20.0), 7.5, (0.6, 0.8, 0)), "back print": ((-6.4, 5.0, 28.0), 10.0, (-1, 0, 0.2))},
}
TILE = 300
ONLY = None  # optional set of view ids (CLI: --views a,b)
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)


def scene_for(kind):
    """Indoor-like light (one soft overhead key + weak fill), neutral; per view the render is then matched to
    the photo's illuminant (table tint) and exposure (median figure luminance) - see match_photo()."""
    bpy.ops.wm.open_mainfile(filepath=str(REPO / "assets" / "figures" / f"{kind}_SWE.blend"))
    for o in [o for o in bpy.data.objects if o.type in ("LIGHT", "CAMERA")]:
        bpy.data.objects.remove(o)
    sb.set_world(0.18)
    key = bpy.data.lights.new("Key", "AREA")
    key.energy, key.size = 4.0, 0.25
    ko = bpy.data.objects.new("Key", key)
    ko.location = (0.02, 0.0, 0.25)
    bpy.context.scene.collection.objects.link(ko)
    bpy.context.scene.render.film_transparent = True


def match_photo(ren_rgba, photo):
    """Exposure + illuminant match of a neutral render to a photo (cameras auto-expose; the room light is warm):
    tint = table colour outside the figure (assumed near-neutral dark wood), gain = median luminance ratio of
    the figure pixels. Shape and relative colours are untouched."""
    import numpy as np
    import cv2
    sys.path.insert(0, str(REPO / "scripts"))
    import figure_views as fv
    P = np.asarray(photo).astype(float)
    m = fv.figure_mask(np.asarray(photo))
    far = ~cv2.dilate(m.astype(np.uint8), np.ones((31, 31), np.uint8)).astype(bool)
    tab = np.median(P[far], 0) if far.any() else np.array([1.0, 1.0, 1.0])
    tint = tab / tab.mean()
    R = np.asarray(ren_rgba).astype(float)
    a = R[..., 3:4] / 255
    rgb = R[..., :3] * tint
    fig = a[..., 0] > 0.5
    gain = np.median(P[m].mean(1)) / max(np.median(rgb[fig].mean(1)), 1) if fig.any() and m.any() else 1.0
    rgb = np.clip(rgb * gain, 0, 255)
    bg = np.array([38, 36, 34], float)
    out = rgb * a + bg * (1 - a)
    return Image.fromarray(out.astype(np.uint8))


def render_view(kind, vid, fit_json):
    cam, (cw, ch) = bf.cam_from_fit(vid, kind, fit_json)
    s = 900 / max(cw, ch)
    res = (round(cw * s), round(ch * s))
    p = OUT / f"{kind}_{vid}.png"
    scn = bpy.context.scene
    sb.render(cam, p, res, 64)
    scn.render.film_transparent = True
    photo = Image.open(REPO / MAN[vid]["file"]).convert("RGB").resize(res, Image.LANCZOS)
    ren = match_photo(Image.open(p).convert("RGBA"), photo)
    feats = []
    for name, (c, r, facing) in FEATURES[kind].items():
        cw_ = Vector(c) * bf.KS[kind] / 1000
        if facing is not None:
            to_cam = (cam.matrix_world.translation - cw_).normalized()
            if to_cam.dot(Vector(facing).normalized()) < 0.15:
                continue
        q = world_to_camera_view(scn, cam, cw_)
        right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))
        q2 = world_to_camera_view(scn, cam, cw_ + right * (r * bf.KS[kind] / 1000))
        u, v = q.x * res[0], (1 - q.y) * res[1]
        rad = max(20, abs(q2.x - q.x) * res[0])
        box = (int(u - rad), int(v - rad), int(u + rad), int(v + rad))
        inside = max(0, min(box[2], res[0]) - max(box[0], 0)) * max(0, min(box[3], res[1]) - max(box[1], 0)) / max(1, (box[2] - box[0]) * (box[3] - box[1]))
        if q.z <= 0 or inside < 0.5:
            continue
        feats.append((name, photo.crop(box).resize((TILE, TILE), Image.LANCZOS), ren.crop(box).resize((TILE, TILE), Image.LANCZOS)))
    return photo, ren, feats


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    global ONLY
    args = [a for a in sys.argv[1:] if not a.startswith("--views=")]
    for a in sys.argv[1:]:
        if a.startswith("--views="):
            ONLY = set(a.split("=", 1)[1].split(","))
    for kind in (args or ["skater", "goalie"]):
        scene_for(kind)
        rows = []
        for tag, fjson in (("fitted", VAL / f"{kind}-fit.json"), ("inspected", VAL / f"{kind}-heldout-fit.json"),
                           ("INDEPENDENT", VAL / f"{kind}-independent-fit.json")):
            if not fjson.exists():
                continue
            fit = json.loads(fjson.read_text())["views"]
            for vid, fv in fit.items():
                if ONLY and vid not in ONLY:
                    continue
                photo, ren, feats = render_view(kind, vid, fjson)
                rows.append((f"{vid}  [{tag}]  IoU {fv['iou']:.3f}", photo, ren, feats))
        W = 2 * TILE + 4 * 2 * TILE
        sheet = Image.new("RGB", (W, len(rows) * (TILE + 34)), "white")
        d = ImageDraw.Draw(sheet)
        for i, (label, photo, ren, feats) in enumerate(rows):
            y = i * (TILE + 34)
            d.text((6, y + 6), label + "   (each pair: photo | model, same camera and crop; render exposure/tint matched to the photo)", fill=(170, 0, 0) if "INDEPENDENT" in label else (0, 0, 0), font=FONT)
            for j, im in enumerate((photo, ren)):
                t = im.copy()
                t.thumbnail((TILE, TILE))
                sheet.paste(t, (j * TILE, y + 32))
            for k, (name, a, b) in enumerate(feats[:4]):
                x = 2 * TILE + k * 2 * TILE
                sheet.paste(a, (x, y + 32))
                sheet.paste(b, (x + TILE, y + 32))
                d.text((x + 6, y + 36), name, fill=(255, 255, 255), font=FONT, stroke_width=2, stroke_fill=(0, 0, 0))
        dst = VAL / f"closeups-{kind}.png" if not ONLY else OUT / f"closeups-{kind}-partial.png"
        sheet.save(dst)
        print("wrote", dst, sheet.size)


main()
