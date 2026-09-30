"""Static assembly of all 12 figures from validation/16-assembly-poses.json (pure pose functions).

    /root/venvs/blender/bin/python assets/blender/build_assembly.py
Every skater uses the shared skater mold and both goalies the goalie mold (user statement: all skaters are
identical; teams differ only in kit colour and the country name). Team W wears the Finland kit, team E the
Sweden kit (reference variant, D4). Figures of one kit share one mesh; each player gets its own back print
(country name + number, data/figure-molds.json 'prints') as a child decal mesh.
Outputs: assets/scene/full_static.blend|.glb, validation/16-overhead-labelled.png, validation/16-oblique.png,
validation/16-assembly-report.json.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402
import build_figures as bf  # noqa: E402
import figure_molds as fm  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import bpy  # noqa: E402

g = sb.load_geometry()
VAL = sb.REPO / "validation"
poses = json.loads((VAL / "16-assembly-poses.json").read_text())["figures"]
molds = fm.load_molds()
bpy.ops.wm.open_mainfile(filepath=str(sb.REPO / "assets" / "scene" / "static_hardware.blend"))


def load_kit(path_obj):
    path, name = path_obj.split("#")
    with bpy.data.libraries.load(str(sb.REPO / path), link=False) as (src, dst):
        dst.objects = [name]
    ob = dst.objects[0]
    me = ob.data  # the mesh (materials included); objects are created per player
    bpy.data.objects.remove(ob)
    return me


meshes = {}
figs = []
for p in poses:
    kind = "goalie" if p["position"] == "G" else "skater"
    if p["asset"] not in meshes:
        meshes[p["asset"]] = load_kit(p["asset"])
    ob = bpy.data.objects.new(f"Figure.{p['player_id']}", meshes[p["asset"]])
    bpy.context.scene.collection.objects.link(ob)
    M = p["matrix"]
    ob.matrix_world = Matrix(((M[0], M[1], M[2], sb.m(M[3])), (M[4], M[5], M[6], sb.m(M[7])), (M[8], M[9], M[10], sb.m(M[11])), (0, 0, 0, 1)))
    ob["player_id"] = p["player_id"]
    ob["asset_status"] = f"figure mold ({kind}), kit {p['kit']}"
    pr = molds["prints"][p["player_id"]]
    dec, _n = bf.decal(ob, kind, p["kit"], pr["number"] or "", f"Print.{p['player_id']}")
    dec["player_id"] = p["player_id"]
    figs.append((p, ob))
bpy.context.view_layer.update()

# ---- Checks -----------------------------------------------------------------------------------------
dg = bpy.context.evaluated_depsgraph_get()
# BVHTree.FromObject uses local coordinates; build world-space trees from evaluated meshes instead.
def world_tree(ob):
    me = ob.evaluated_get(dg).to_mesh()
    verts = [ob.matrix_world @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    t = BVHTree.FromPolygons(verts, polys)
    zmin = min(v.z for v in verts) * 1000
    ob.evaluated_get(dg).to_mesh_clear()
    return t, zmin
trees, zmins = {}, {}
for _p, ob in figs:
    trees[ob.name], zmins[ob.name] = world_tree(ob)
fixed = {n: world_tree(bpy.data.objects[n])[0] for n in ("Goal.W", "Goal.E", "InnerBoards", "EndScreen.W", "EndScreen.E", "Puck")}
intersections = []
names = list(trees)
for i, a in enumerate(names):
    for b in names[i + 1:]:
        if trees[a].overlap(trees[b]):
            intersections.append([a, b])
    for n, t in fixed.items():
        if trees[a].overlap(t):
            intersections.append([a, n])
axis_ok = all((ob.matrix_world.to_3x3() @ Vector((0, 0, 1)) - Vector((0, 0, 1))).length < 1e-9 for _p, ob in figs)
dets = {ob.name: round(ob.matrix_world.to_3x3().determinant(), 9) for _p, ob in figs}

sb.save_blend(sb.REPO / "assets" / "scene" / "full_static.blend")
sb.export_glb(sb.REPO / "assets" / "scene" / "full_static.glb", [o for o in bpy.data.objects if o.type == "MESH"])

# ---- Renders ------------------------------------------------------------------------------------------
if "Sun" not in bpy.data.objects:
    sb.add_sun(3.0, (35, 10, 30))
res = (1800, 1000)
scale_mm = 0.9312 * 1000
top = sb.ortho_camera("AsmTop", (0, 0, 1.0), (0, 0, 0), scale_mm / 1000)
sb.render(top, VAL / "16-overhead.png", res, 32)
obl = sb.persp_camera("AsmOblique", (sb.m(120), sb.m(-700), sb.m(430)), (0.0, sb.m(-20), 0.0), 35)
sb.render(obl, VAL / "16-oblique.png", (1600, 900), 48)
from PIL import Image, ImageDraw  # noqa: E402
im = Image.open(VAL / "16-overhead.png").convert("RGB")
d = ImageDraw.Draw(im)
mmpp = scale_mm / res[0]
for p, ob in figs:
    x, y = p["pivot_mm"][0], p["pivot_mm"][1]
    u, v = res[0] / 2 + x / mmpp, res[1] / 2 - y / mmpp
    d.ellipse((u - 4, v - 4, u + 4, v + 4), outline=(255, 0, 0), width=2)
    hx, hy = math.cos(math.radians(p["heading_deg"])), math.sin(math.radians(p["heading_deg"]))
    d.line((u, v, u + 30 * hx, v - 30 * hy), fill=(255, 0, 0), width=3)
    label = p["player_id"]
    d.text((u + 8, v + 8), label, fill=(0, 0, 0), stroke_width=2, stroke_fill=(255, 255, 255))
d.text((10, 10), "16 - static assembly (AI review). Red: fixture axis (mount socket) + heading. All figures: shared skater / goalie molds.", fill=(0, 0, 0), stroke_width=2, stroke_fill=(255, 255, 255))
im.save(VAL / "16-overhead-labelled.png")

report = {
    "figures": {"skaters": sum(1 for p, _ in figs if p["position"] != "G"), "goalies": sum(1 for p, _ in figs if p["position"] == "G")},
    "modelled": [p["player_id"] for p, _ in figs],
    "placeholders": [],
    "assets": sorted({p["asset"] for p, _ in figs}),
    "mounting_axes_vertical": axis_ok,
    "determinants": dets,
    "figure_zmin_mm": {k: round(v, 3) for k, v in zmins.items()},
    "intersections": intersections,
    "nothing_below_ice": all(v >= -0.05 for v in zmins.values()),
    "pass": not intersections and all(v >= -0.05 for v in zmins.values()) and axis_ok and all(abs(v - 1) < 1e-6 for v in dets.values()),
    "rods_handles_supports": "not added: their positions along the housing ends are not evidenced at the needed accuracy (oblique views only); no control mapping is implied by this static pose",
}
(VAL / "16-assembly-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=1))
