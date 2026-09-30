"""Iteration 15: rigid goalie asset W-G (Finland) - its own body, stick and origin (not a resized skater).

    /root/venvs/blender/bin/python assets/blender/build_goalie.py
Origin: the goalie's fixture axis at the ice plane (debug pivot, docs/figures.md); +x = facing, +y = left.
Outputs: assets/figures/goalie_W-G.blend|.glb, validation/15-goalie-{top,side,oblique}.png,
validation/15-goalie-silhouette-top.png, validation/15-goalie-report.json.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402
from mathutils import Vector  # noqa: E402

import bpy  # noqa: E402

g = sb.load_geometry()
VAL = sb.REPO / "validation"
OUT = sb.REPO / "assets" / "figures"
asset = next(a for a in g["figure_assets"] if a["id"] == "fig.W-G")
C = {c["id"]: c["geometry"]["points_mm"] for c in asset["contact_shapes"]}
H_TARGET = sb.preview(g, "goalie_height")

# Body layout (pivot-local mm), operator interpretation of the traced top silhouette + side A profile.
BALLS = {
    "helmet": ((-8.5, -12.4, 46.5), (6.5, 6.8, 6.3)),
    "mask": ((-3.5, -12.4, 43.5), (3.0, 4.5, 4.5)),
    "torso": ((-14.0, -13.5, 34.0), (9.0, 11.0, 8.0)),
    "pelvis": ((-13.0, -15.0, 23.0), (8.0, 10.0, 6.0)),
    "catcher": ((-7.8, 5.0, 22.0), (6.0, 4.5, 5.5)),
    "blocker": ((-1.5, -7.5, 19.0), (4.0, 6.0, 6.0)),
    "pad_left": ((-8.0, -2.0, 9.3), (5.5, 4.5, 9.0)),
    "pad_right": ((-1.0, -22.0, 9.3), (5.5, 4.5, 9.0)),
    "toe_right": ((0.5, -27.0, 3.6), (4.0, 4.0, 3.0)),
    "thigh_area": ((-11.0, -24.0, 16.0), (7.0, 6.0, 6.0)),
}
CAPSULES = {
    "neck": ((-12.0, -13.0, 40.0), (-9.0, -12.5, 44.0), 3.5),
    "arm_left": ((-12.0, -2.0, 38.0), (-8.0, 4.0, 24.0), 3.2),
    "arm_right": ((-13.0, -24.0, 38.0), (-2.0, -9.0, 21.0), 3.2),
    "thigh_left": ((-13.0, -8.0, 22.0), (-8.0, -3.0, 14.0), 4.5),
    "thigh_right": ((-13.0, -20.0, 22.0), (-3.0, -22.0, 14.0), 4.5),
}


def plate(name, a, b, thickness, z0, z1, mat):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L * thickness / 2, dx / L * thickness / 2
    base = [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]
    verts = [(sb.m(x), sb.m(y), sb.m(z0)) for x, y in base] + [(sb.m(x), sb.m(y), sb.m(z1)) for x, y in base]
    faces = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def rod(name, a, b, r, mat):
    va, vb = Vector([sb.m(v) for v in a]), Vector([sb.m(v) for v in b])
    d = vb - va
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=sb.m(r), depth=d.length, location=(va + vb) / 2)
    ob = bpy.context.active_object
    ob.name = name
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = d.to_track_quat("Z", "Y")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    ob.data.materials.append(mat)
    return ob


sb.reset_scene()
mat_stick = sb.clay("clay_goalie_stick", (0.8, 0.55, 0.35), 0.5)
mat_body = sb.clay("clay_goalie", (0.78, 0.78, 0.8), 0.55)
blade = C["contact.W-G.stick_blade"]
shaft = C["contact.W-G.stick_shaft"]
parts = [
    plate("StickBlade", blade[0][:2], blade[1][:2], 1.5, 0.0, max(p[2] for p in blade), mat_stick),
    rod("StickShaft", shaft[0], shaft[1], 1.6, mat_stick),
]
body = sb.metaball_mesh("GoalieBody", BALLS, CAPSULES)
bpy.ops.object.shade_smooth()
body.data.materials.append(mat_body)
body_zmin = min(v.co.z for v in body.data.vertices) * 1000
bpy.ops.object.select_all(action="DESELECT")
for o in [body, *parts]:
    o.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.join()
goalie = bpy.context.view_layer.objects.active
goalie.name = "Goalie.W-G"
goalie.data.name = "Goalie.W-G"
assert tuple(goalie.location) == (0, 0, 0)
zs = [v.co.z for v in goalie.data.vertices]
height = (max(zs) - min(zs)) * 1000
OUT.mkdir(parents=True, exist_ok=True)
sb.save_blend(OUT / "goalie_W-G.blend")
sb.export_glb(OUT / "goalie_W-G.glb", [goalie])

# ---- Top silhouette check against the traced body + stick outline -----------------------------------
rep15 = json.loads((VAL / "15-goalie-contacts-report.json").read_text())
pv = sb.px_to_world(g, "map.overhead.preview", [rep15["pivot_px"]])[0]
def local(p):
    x, y = sb.px_to_world(g, "map.overhead.preview", [p])[0]
    return (x - pv[0], y - pv[1])
polys = [[local(p) for p in next(t for t in g["image_traces"] if t["id"] == tid)["points_px"]] for tid in ("trace.figure.W-G.overhead.top_silhouette", "trace.figure.W-G.overhead.stick")]
iou = sb.silhouette_iou(goalie, polys, (-8.0, -8.0), 300, sb.mm_per_px(g), VAL / "15-goalie-silhouette-top.png", VAL / "15-goalie-silhouette-render.png")

# ---- Review renders: goalie in its goal region with the puck beside the stick ----------------------
bpy.ops.wm.open_mainfile(filepath=str(sb.REPO / "assets" / "scene" / "static_hardware.blend"))
with bpy.data.libraries.load(str(OUT / "goalie_W-G.blend"), link=False) as (src, dst):
    dst.objects = ["Goalie.W-G"]
gob = dst.objects[0]
bpy.context.scene.collection.objects.link(gob)
gob.location = (sb.m(pv[0]), sb.m(pv[1]), 0.0)  # heading 0: local axes = world axes
puck = bpy.data.objects["Puck"]
D = g["puck"]["diameter"]["value"]
mid = ((blade[0][0] + blade[1][0]) / 2, (blade[0][1] + blade[1][1]) / 2 + 4)
puck.location = (sb.m(pv[0] + mid[0] + 0.75 + D / 2 + 0.5), sb.m(pv[1] + mid[1]), 0.0)
world_contacts = {cid: [[round(pv[0] + p[0], 3), round(pv[1] + p[1], 3), p[2]] for p in pts] for cid, pts in C.items()}
if "Sun" not in bpy.data.objects:
    sb.add_sun(3.0, (40, 10, 30))
gx, gy = pv
top = sb.ortho_camera("GTop", (sb.m(gx - 10), sb.m(gy - 5), 0.5), (0, 0, 0), sb.m(110))
sb.render(top, VAL / "15-goalie-top.png", (1100, 1100), 32)
# Side view at ice level: the near boards and housing would hide the goalie's lower half, so they are
# hidden for this render only (ice, goal, goalie and puck remain).
side_hidden = [bpy.data.objects[n] for n in ("InnerBoards", "HousingBase", "HousingRim", "EndScreen.W", "EndScreen.E") if n in bpy.data.objects]
for o in side_hidden:
    o.hide_render = True
side = sb.ortho_camera("GSide", (sb.m(gx - 5), sb.m(gy) - 0.35, sb.m(28)), (90, 0, 0), sb.m(110))
sb.render(side, VAL / "15-goalie-side.png", (1400, 900), 32)
for o in side_hidden:
    o.hide_render = False
obl = sb.persp_camera("GOblique", (sb.m(gx + 170), sb.m(gy - 140), sb.m(120)), (sb.m(gx - 10), sb.m(gy - 5), sb.m(20)), 50)
sb.render(obl, VAL / "15-goalie-oblique.png", (1600, 1000), 48)

report = {
    "blender": bpy.app.version_string,
    "origin": "goalie fixture axis at the ice plane (debug pivot, assume.debug_contacts.W-G)",
    "pivot_world_mm": [round(v, 3) for v in pv],
    "heading_deg": 0,
    "world_contacts_mm": world_contacts,
    "top_silhouette_iou": round(iou, 4),
    "iou_threshold": 0.75,
    "height_mm": round(height, 2),
    "height_target_mm": f"{H_TARGET} +- 15% (assumed)",
    "body_zmin_mm": round(body_zmin, 3),
    "evidence_by_view": {"top": "EVIDENCE: overhead (identity certain)", "side": "EVIDENCE: side A profile (identity certain; pose differs)", "oblique": "EVIDENCE: oblique A (identity certain; pose differs)"},
    "pass": iou >= 0.75 and 0.85 * H_TARGET <= height <= 1.15 * H_TARGET and body_zmin >= -0.05,
}
(VAL / "15-goalie-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if k != "world_contacts_mm"}, indent=1))
