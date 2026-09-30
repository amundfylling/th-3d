"""Iteration 14: rigid body (torso, arms, legs, head) of the representative skater W-RD, as a PROVISIONAL
proxy matched to its only identified view (the official overhead's top silhouette of Finland no. 4).
The iteration-13 lower asset (blade, shaft, skates) is appended unchanged; one rigid object results.

    /root/venvs/blender/bin/python assets/blender/build_skater_body.py
Outputs: assets/figures/skater_W-RD.blend|.glb, validation/14-view-sheet.png (+ per-view PNGs),
validation/14-silhouette-top.png, validation/14-skater-body-report.json.
Body layout (pivot-local mm, +x forward, +y left, z up) is an operator interpretation of the top
silhouette plus generic STIGA skater proportions (unverified mold identity) - docs/figures.md.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

import bpy  # noqa: E402

g = sb.load_geometry()
VAL = sb.REPO / "validation"
OUT = sb.REPO / "assets" / "figures"

# ---- Body layout (mm) ------------------------------------------------------------------------------
BALLS = {  # name: (centre, radii xyz)
    "helmet": ((10.5, -8.8, 50.0), (8.5, 6.4, 6.8)),
    "face": ((15.0, -8.8, 45.5), (3.0, 3.6, 4.0)),
    "pelvis": ((-6.0, -7.0, 24.0), (7.5, 8.5, 6.0)),
    "torso": ((-2.0, -6.5, 35.0), (11.5, 10.5, 7.5)),
    "glove_left": ((4.3, 5.2, 21.0), (3.6, 3.2, 3.6)),
    "glove_right": ((-12.0, -15.5, 29.0), (3.8, 3.8, 3.8)),
    "boot_left": ((0.5, 4.5, 5.0), (6.0, 3.0, 3.0)),
    "boot_right": ((0.6, -25.5, 4.5), (3.0, 3.6, 3.0)),
}
CAPSULES = {  # name: (a, b, radius)
    "neck": ((3.0, -7.5, 41.0), (9.0, -8.5, 47.0), 3.6),
    "arm_left_upper": ((1.0, 2.5, 40.0), (5.0, 5.5, 30.0), 3.3),
    "arm_left_lower": ((5.0, 5.5, 30.0), (4.3, 5.2, 22.0), 3.0),
    "arm_right_upper": ((-2.0, -15.0, 40.0), (-8.0, -16.5, 34.0), 3.3),
    "arm_right_lower": ((-8.0, -16.5, 34.0), (-12.0, -15.5, 30.0), 3.0),
    "leg_left_thigh": ((-5.0, -2.0, 23.0), (2.0, 1.0, 14.0), 4.2),
    "leg_left_shin": ((2.0, 1.0, 14.0), (0.5, 4.5, 6.0), 3.4),
    "leg_right_thigh": ((-7.0, -11.0, 23.0), (-2.0, -18.0, 15.0), 4.2),
    "leg_right_shin": ((-2.0, -18.0, 15.0), (0.5, -24.5, 7.0), 3.2),
}
RES_MM = 0.25


# Calibrated (docs/figures.md): at threshold 0.6 / stiffness 2, an isolated element's surface lies at
# 0.575 x radius x size. Blender clamps metaball resolution to >= 0.005 units, so the metaball is built
# in MILLIMETRE units (1 unit = 1 mm) at 0.25 mm resolution and the mesh is scaled by 0.001 afterwards.
SURF = 0.575


def metaball_body():
    mb = bpy.data.metaballs.new("BodyMeta")
    mb.resolution = RES_MM
    mb.render_resolution = RES_MM
    mb.threshold = 0.6
    ob = bpy.data.objects.new("BodyMeta", mb)
    bpy.context.scene.collection.objects.link(ob)
    for c, r in BALLS.values():
        e = mb.elements.new(type="ELLIPSOID")
        e.co = c
        e.radius = 1.0
        e.size_x, e.size_y, e.size_z = [v / SURF for v in r]
        e.stiffness = 2.0
    for a, b, r in CAPSULES.values():
        va, vb = Vector(a), Vector(b)
        d = vb - va
        e = mb.elements.new(type="CAPSULE")
        e.co = (va + vb) / 2
        e.radius = r / SURF
        e.size_x = d.length / 2
        e.rotation = Vector((1, 0, 0)).rotation_difference(d.normalized())
        e.stiffness = 2.0
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.convert(target="MESH")
    body = bpy.context.view_layer.objects.active
    body.name = "Body"
    for v in body.data.vertices:  # the single mm -> m step for the body mesh (sb.m convention)
        v.co = v.co * sb.MM_TO_M
    body.data.update()
    zmin = min(v.co.z for v in body.data.vertices)
    return body, zmin * 1000


sb.reset_scene()
body, body_zmin = metaball_body()
bpy.ops.object.shade_smooth()
body.data.materials.append(sb.clay("clay_body", (0.78, 0.78, 0.8), 0.55))
with bpy.data.libraries.load(str(OUT / "skater_W-RD_lower.blend"), link=False) as (src, dst):
    dst.objects = ["SkaterLower.W-RD"]
lower = dst.objects[0]
bpy.context.scene.collection.objects.link(lower)
lower_verts_before = [tuple(round(c, 9) for c in v.co) for v in lower.data.vertices]

bpy.ops.object.select_all(action="DESELECT")
body.select_set(True)
lower.select_set(True)
bpy.context.view_layer.objects.active = lower
bpy.ops.object.join()
fig = bpy.context.view_layer.objects.active
fig.name = "Skater.W-RD"
fig.data.name = "Skater.W-RD"
assert tuple(fig.location) == (0, 0, 0)
lower_preserved = lower_verts_before == [tuple(round(c, 9) for c in fig.data.vertices[i].co) for i in range(len(lower_verts_before))]
zs = [v.co.z for v in fig.data.vertices]
height_mm = (max(zs) - min(zs)) * 1000
OUT.mkdir(parents=True, exist_ok=True)
sb.save_blend(OUT / "skater_W-RD.blend")
sb.export_glb(OUT / "skater_W-RD.glb", [fig])

# ---- Top silhouette check (orthographic, overhead scale, black on white) --------------------------
MMPP = sb.mm_per_px(g)
tr = next(t for t in g["image_traces"] if t["id"] == "trace.figure.W-RD.overhead.top_silhouette")
rep10 = json.loads((VAL / "10-contacts-report.json").read_text())
pv = sb.px_to_world(g, "map.overhead.preview", [rep10["pivot_px"]])[0]
h = math.radians(rep10["heading_deg"])
def to_local(p):
    x, y = sb.px_to_world(g, "map.overhead.preview", [p])[0]
    dx, dy = x - pv[0], y - pv[1]
    return (dx * math.cos(-h) - dy * math.sin(-h), dx * math.sin(-h) + dy * math.cos(-h))
sil_local = [to_local(p) for p in tr["points_px"]]
N = 260  # pixels per side; window 260 * 0.1796 = 46.7 mm
cx, cy = 1.5, -11.0  # window centre (local mm)
win = N * MMPP
sil_mat = bpy.data.materials.new("sil")
sil_mat.use_nodes = True
nt = sil_mat.node_tree
nt.nodes.clear()
em = nt.nodes.new("ShaderNodeEmission")
em.inputs["Color"].default_value = (0, 0, 0, 1)
out = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
saved = list(fig.data.materials)
fig.data.materials.clear()
fig.data.materials.append(sil_mat)
sb.set_world(1.0)
cam = sb.ortho_camera("TopSil", (sb.m(cx), sb.m(cy), 0.5), (0, 0, 0), sb.m(win))
sb.render(cam, VAL / "14-silhouette-top-render.png", (N, N), 1)
from PIL import Image, ImageDraw  # noqa: E402
rend = np.asarray(Image.open(VAL / "14-silhouette-top-render.png").convert("L")) < 128
ref_img = Image.new("L", (N, N), 0)
to_px = lambda p: ((p[0] - cx) / MMPP + N / 2, N / 2 - (p[1] - cy) / MMPP)
ImageDraw.Draw(ref_img).polygon([to_px(p) for p in sil_local], fill=255)
ref = np.asarray(ref_img) > 0
iou = float((rend & ref).sum() / (rend | ref).sum())
viz = np.full((N, N, 3), 255, np.uint8)
viz[ref & ~rend] = (230, 60, 60)      # reference only
viz[rend & ~ref] = (60, 90, 230)      # model only
viz[rend & ref] = (120, 120, 120)     # overlap
Image.fromarray(viz).resize((N * 3, N * 3), Image.NEAREST).save(VAL / "14-silhouette-top.png")
fig.data.materials.clear()
for m_ in saved:
    fig.data.materials.append(m_)

# ---- View sheet: front, back, left, right, overhead (orthographic, neutral light) -------------------
sb.set_world(0.5)
sb.add_sun(3.0, (40, 15, 35))
views = {
    "front": ((0.25, sb.m(-8), sb.m(28)), (90, 0, 90)),
    "back": ((-0.25, sb.m(-8), sb.m(28)), (90, 0, -90)),
    "left": ((sb.m(2), 0.25, sb.m(28)), (90, 0, 180)),
    "right": ((sb.m(2), -0.25, sb.m(28)), (90, 0, 0)),
    "overhead": ((sb.m(2), sb.m(-4), 0.5), (0, 0, 0)),
}
paths = {}
for name, (loc, rot) in views.items():
    c = sb.ortho_camera(f"V_{name}", loc, rot, sb.m(80))
    paths[name] = VAL / f"14-view-{name}.png"
    sb.render(c, paths[name], (700, 700), 32)
EVID = {"front": "NO W-RD evidence (provisional)", "back": "NO W-RD evidence (provisional)", "left": "NO W-RD evidence (provisional)", "right": "NO W-RD evidence (provisional)", "overhead": "EVIDENCE: official overhead, no. 4 (silhouette IoU below)"}
sheet = Image.new("RGB", (5 * 700, 780), "white")
d = ImageDraw.Draw(sheet)
for i, name in enumerate(views):
    sheet.paste(Image.open(paths[name]).convert("RGB"), (i * 700, 80))
    d.text((i * 700 + 12, 10), f"{name.upper()}", fill=(0, 0, 0))
    d.text((i * 700 + 12, 40), EVID[name], fill=(170, 0, 0) if "NO" in EVID[name] else (0, 110, 0))
sheet.save(VAL / "14-view-sheet.png")

report = {
    "blender": bpy.app.version_string,
    "top_silhouette_iou": round(iou, 4),
    "iou_threshold": 0.75,
    "height_mm": round(height_mm, 2),
    "height_target_mm": "approx. 57 +- 10% (catalog nominal, datum unknown)",
    "body_zmin_mm": round(body_zmin, 3),
    "lower_asset_preserved": lower_preserved,
    "resolution_mm": RES_MM,
    "evidence_by_view": EVID,
    "pass": iou >= 0.75 and 51.3 <= height_mm <= 62.7 and body_zmin >= 0 and lower_preserved,
}
(VAL / "14-skater-body-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=1))
