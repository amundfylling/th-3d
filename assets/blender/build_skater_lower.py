"""Iteration 13: contact-bearing lower part of the representative skater W-RD, built from the canonical
PROVISIONAL contact shapes (figure_assets[fig.W-RD].contact_shapes). One rigid object whose origin is
the fixture axis at the ice plane (preview originHeightMm = 0); +x = figure heading, +y = figure's left.

    /root/venvs/blender/bin/python assets/blender/build_skater_lower.py
Outputs: assets/figures/skater_W-RD_lower.blend|.glb, validation/13-contacts-top.png,
validation/13-contacts-side.png, validation/13-skater-lower-report.json.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import bpy  # noqa: E402

g = sb.load_geometry()
asset = next(a for a in g["figure_assets"] if a["id"] == "fig.W-RD")
C = {c["id"]: c for c in asset["contact_shapes"]}
P = lambda k: sb.preview(g, k)
blade_pts = C["contact.W-RD.blade"]["geometry"]["points_mm"]
shaft_pts = C["contact.W-RD.stick_shaft"]["geometry"]["points_mm"]
skates = [C["contact.W-RD.skate.left"]["geometry"]["points_mm"], C["contact.W-RD.skate.right"]["geometry"]["points_mm"]]
VAL = sb.REPO / "validation"
OUT = sb.REPO / "assets" / "figures"


def box_along(name, a, b, width, z0, z1, mat):
    """Box whose centre line on the ice runs a -> b (mm), `width` across, from z0 to z1."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L * width / 2, dx / L * width / 2
    base = [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]
    verts = [(sb.m(x), sb.m(y), sb.m(z0)) for x, y in base] + [(sb.m(x), sb.m(y), sb.m(z1)) for x, y in base]
    faces = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def rod(name, a, b, r, mat, verts=16):
    """Cylinder from a to b (mm) with radius r (mm)."""
    va, vb = Vector([sb.m(v) for v in a]), Vector([sb.m(v) for v in b])
    d = vb - va
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=sb.m(r), depth=d.length, location=(va + vb) / 2)
    ob = bpy.context.active_object
    ob.name = name
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = d.to_track_quat("Z", "Y")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # transform_apply moves the origin to the world origin (= fixture axis), which is what we want.
    ob.data.materials.append(mat)
    return ob


sb.reset_scene()
sb.set_world(0.45)
mat_blade = sb.clay("clay_blade", (0.12, 0.25, 0.55), 0.5)
mat_stick = sb.clay("clay_stick", (0.55, 0.55, 0.58), 0.4)
mat_skate = sb.clay("clay_skate", (0.2, 0.2, 0.22), 0.5)

# Blade: the stored contact polyline is the blade's OUTER face (bottom edge on the ice). The blade is
# thickened toward the figure so that face lies exactly on the mesh surface (checked below).
(b0, b1) = (blade_pts[0], blade_pts[1])
bt = P("blade_thickness")
dx, dy = b1[0] - b0[0], b1[1] - b0[1]
L = math.hypot(dx, dy)
inward = (dy / L, -dx / L) if (dy / L) * (-b0[0]) + (-dx / L) * (-b0[1]) > 0 else (-dy / L, dx / L)
a_mid = (b0[0] + inward[0] * bt / 2, b0[1] + inward[1] * bt / 2)
b_mid = (b1[0] + inward[0] * bt / 2, b1[1] + inward[1] * bt / 2)
blade_h = max(p[2] for p in blade_pts)
blade = box_along("Blade", a_mid, b_mid, bt, 0.0, blade_h, mat_blade)
# The stored shaft line starts on the ice at the blade; a rod of radius r centred on it would cut into the
# ice. The rod therefore starts where the line has risen to z = r (still exactly on the stored line).
r_sh = P("stick_shaft_radius")
s0, s1 = shaft_pts
t0 = r_sh / (s1[2] - s0[2])
shaft_start = [s0[k] + (s1[k] - s0[k]) * t0 for k in range(3)]
shaft = rod("Shaft", shaft_start, s1, r_sh, mat_stick, 64)
sk = [box_along(f"Skate{i}", s[0][:2], s[1][:2], P("skate_width"), 0.0, P("skate_height"), mat_skate) for i, s in enumerate(skates)]

bpy.ops.object.select_all(action="DESELECT")
for o in [blade, shaft, *sk]:
    o.select_set(True)
bpy.context.view_layer.objects.active = blade
bpy.ops.object.join()
lower = bpy.context.view_layer.objects.active
lower.name = "SkaterLower.W-RD"
lower.data.name = "SkaterLower.W-RD"
assert tuple(lower.location) == (0, 0, 0)

# ---- Numerical check: stored contact geometry lies on the mesh surface ----------------------------
dg = bpy.context.evaluated_depsgraph_get()
bvh = BVHTree.FromObject(lower, dg)
def surf_dist(p):
    loc, _n, _i, d = bvh.find_nearest(Vector([sb.m(v) for v in p]))
    return d * 1000
def densify(pts, n=20):
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        out += [[a[k] + (b[k] - a[k]) * t / n for k in range(3)] for t in range(n)]
    return out + [pts[-1]]
checks = {
    "blade_face": max(surf_dist(p) for p in densify(blade_pts)),
    "shaft_axis_to_surface_minus_radius": max(abs(surf_dist(p) - r_sh) for p in densify([shaft_start, s1])[1:-1]),
    "skate_left_on_bottom_face": max(surf_dist(p) for p in densify(skates[0])),
    "skate_right_on_bottom_face": max(surf_dist(p) for p in densify(skates[1])),
}
checks = {k: round(v, 4) for k, v in checks.items()}
bb = [lower.matrix_world @ Vector(c) for c in lower.bound_box]
bounds_mm = [round(min(v[i] for v in bb) * 1000, 3) for i in range(3)] + [round(max(v[i] for v in bb) * 1000, 3) for i in range(3)]

OUT.mkdir(parents=True, exist_ok=True)
sb.save_blend(OUT / "skater_W-RD_lower.blend")
sb.export_glb(OUT / "skater_W-RD_lower.glb", [lower])

# ---- Review renders: small ice plane, pivot axes, contact outlines, puck ---------------------------
mat_ice = sb.clay("clay_ice", (0.85, 0.86, 0.88), 0.45)
bpy.ops.mesh.primitive_plane_add(size=0.2, location=(0, 0, -0.00005))
bpy.context.active_object.data.materials.append(mat_ice)
axis_mats = {k: sb.clay(f"axis_{k}", c, 0.9) for k, c in (("x", (0.85, 0.05, 0.05)), ("y", (0.05, 0.6, 0.05)), ("z", (0.05, 0.05, 0.05)))}
rod("AxisX", (0, 0, 0.3), (25, 0, 0.3), 0.35, axis_mats["x"], 8)
rod("AxisY", (0, 0, 0.3), (0, 15, 0.3), 0.35, axis_mats["y"], 8)
rod("AxisZ", (0, 0, 0), (0, 0, 57), 0.35, axis_mats["z"], 8)
mat_outline = sb.clay("contact_outline", (1.0, 0.55, 0.0), 0.9)
for cid, c in C.items():
    pts = c["geometry"]["points_mm"]
    for i, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
        rod(f"Outline.{cid}.{i}", a, b, 0.25, mat_outline, 8)
with bpy.data.libraries.load(str(sb.REPO / "assets" / "puck" / "puck.blend"), link=False) as (src, dst):
    dst.objects = ["Puck"]
puck = dst.objects[0]
bpy.context.scene.collection.objects.link(puck)
D = g["puck"]["diameter"]["value"]
bm = ((b0[0] + b1[0]) / 2, (b0[1] + b1[1]) / 2)
out_n = (-inward[0], -inward[1])
puck.location = (sb.m(bm[0] + out_n[0] * (D / 2 + 1.0)), sb.m(bm[1] + out_n[1] * (D / 2 + 1.0)), 0)
sb.add_sun(3.0, (35, 10, 30))
top = sb.ortho_camera("Top", (sb.m(8), sb.m(25), 0.5), (0, 0, 0), sb.m(95))
sb.render(top, VAL / "13-contacts-top.png", (1400, 1400), 48)
# Side view looking along +x (from behind the figure): local y (the figure's left) runs left to right,
# the blade at y 32-43 mm is separated from the skates at y +-5 mm and is not hidden by the puck, which
# lies on the blade's forward face.
side = sb.ortho_camera("Side", (sb.m(-250), sb.m(24), sb.m(14)), (90, 0, -90), sb.m(80))
sb.render(side, VAL / "13-contacts-side.png", (1600, 900), 48)

report = {
    "blender": bpy.app.version_string,
    "origin": "fixture axis at the ice plane (preview originHeightMm = 0)",
    "source": "figure_assets[fig.W-RD].contact_shapes (status assumed, provisional)",
    "build_sizes_mm": {"blade_thickness": bt, "shaft_radius": P("stick_shaft_radius"), "skate_width": P("skate_width"), "skate_height": P("skate_height"), "blade_height": blade_h},
    "contact_on_surface_max_mm": checks,
    "tolerance_mm": 0.01,
    "bounds_mm_xyz_min_max": bounds_mm,
    "shaft_built_from_mm": [round(v, 3) for v in shaft_start],
    "nothing_below_ice": bounds_mm[2] >= -1e-6,
    "pass": all(v <= 0.01 for v in checks.values()) and bounds_mm[2] >= -1e-6,
}
(VAL / "13-skater-lower-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=1))
