"""Iteration 12: reusable goal, end screen and puck assets, assembled into the static rink.

    /root/venvs/blender/bin/python assets/blender/build_hardware.py
Asset origins (docs/blender.md):
  goal   - centre of the goal mouth on the ice (goal line, z = 0); +x out of the goal into the rink,
           +y to the left looking out, +z up. Configuration: no insert, no goal cup (user, D5).
  screen - on the ice at the end-centre of the W end, on the outer face of the boards; +x into the rink.
  puck   - bottom centre (ice contact), +z up.
Outputs: assets/goal|screen|puck/*.blend|.glb, assets/scene/static_hardware.blend|.glb,
validation/12-goal-oblique.png, validation/12-puck-side.png, validation/12-hardware-report.json.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402
import numpy as np  # noqa: E402
from shapely.geometry import LineString, Point, Polygon  # noqa: E402

import bpy  # noqa: E402

g = sb.load_geometry()
VAL = sb.REPO / "validation"
P = lambda k: sb.preview(g, k)
lm = {l["id"]: l for l in g["landmarks"]}
w = lambda px: sb.px_to_world(g, "map.overhead.preview", [px])[0]

# ---- Goal dimensions from traced evidence (elevated features, preview scale) --------------------
mouth = {t: math.dist(w(lm[f"lm.goal.{t}.post_top.pos_y"]["px"]), w(lm[f"lm.goal.{t}.post_top.neg_y"]["px"]) ) for t in ("W", "E")}
MOUTH_W = (mouth["W"] + mouth["E"]) / 2  # two views of the same part (7111-0526-01); difference reported
cage = {t: [w(p) for p in next(x for x in g["image_traces"] if x["id"] == f"trace.goal.{t}.cage.overhead")["points_px"]] for t in ("W", "E")}
def goal_line_x(t, y):
    a, b = w(lm[f"lm.board.goal_line.{t}.top"]["px"]), w(lm[f"lm.board.goal_line.{t}.bottom"]["px"])
    return a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
centre_y = {t: (w(lm[f"lm.goal.{t}.post_top.pos_y"]["px"])[1] + w(lm[f"lm.goal.{t}.post_top.neg_y"]["px"])[1]) / 2 for t in ("W", "E")}
mouth_x = {t: goal_line_x(t, centre_y[t]) for t in ("W", "E")}
depth = {"W": mouth_x["W"] - min(p[0] for p in cage["W"]), "E": max(p[0] for p in cage["E"]) - mouth_x["E"]}
DEPTH = (depth["W"] + depth["E"]) / 2
H, R_POST, R_BAR, TOP_FRAC = P("goal_height"), P("goal_post_radius"), P("goal_bar_radius"), g["preview_parameters"]["goal_top_depth_fraction"]["value"]


def outline(d, width, n=41):
    """Open U-shaped outline (mm, goal-local), exact parametric: from the +y post straight back, a
    quarter arc, the straight back, a quarter arc, straight forward to the -y post. Resampled evenly."""
    r = min(0.45 * d, 0.3 * width)
    pts = [(0.0, width / 2), (-(d - r), width / 2)]
    pts += [(-(d - r) + r * math.cos(a), width / 2 - r + r * math.sin(a)) for a in np.linspace(math.pi / 2, math.pi, 12)[1:]]
    pts += [(-d, -(width / 2 - r))]
    pts += [(-(d - r) + r * math.cos(a), -(width / 2 - r) + r * math.sin(a)) for a in np.linspace(math.pi, 1.5 * math.pi, 12)[1:]]
    pts += [(0.0, -width / 2)]
    line = LineString(pts)
    return [(p.x, p.y) for p in (line.interpolate(t, normalized=True) for t in np.linspace(0, 1, n))]


def tube(name, pts_mm, radius_mm, mat):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = sb.m(radius_mm)
    cu.bevel_resolution = 3
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts_mm) - 1)
    for p, q in zip(sp.points, pts_mm):
        p.co = (sb.m(q[0]), sb.m(q[1]), sb.m(q[2]), 1)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def build_goal():
    mat = sb.clay("clay_goal", (0.55, 0.30, 0.28), 0.5)
    bottom = outline(DEPTH, MOUTH_W)
    top = [(x * TOP_FRAC, y) for x, y in bottom]
    parts = [
        tube("post_pos", [(0, MOUTH_W / 2, 0), (0, MOUTH_W / 2, H)], R_POST, mat),
        tube("post_neg", [(0, -MOUTH_W / 2, 0), (0, -MOUTH_W / 2, H)], R_POST, mat),
        tube("crossbar", [(0, MOUTH_W / 2, H), (0, -MOUTH_W / 2, H)], R_POST, mat),
        tube("frame_bottom", [(x, y, R_BAR) for x, y in bottom], R_BAR, mat),
        tube("frame_top", [(x, y, H) for x, y in top], R_BAR, mat),
    ]
    for i in range(1, len(bottom) - 1, 3):  # sloping ribs from the top frame to the bottom frame
        parts.append(tube(f"rib{i}", [(top[i][0], top[i][1], H), (bottom[i][0], bottom[i][1], R_BAR)], R_BAR, mat))
    for k in (0.25, 0.5, 0.75):  # horizontal mesh bars
        z = H * k
        f = TOP_FRAC + (1 - TOP_FRAC) * (1 - k)
        parts.append(tube(f"bar{k}", [(x * f, y, z) for x, y in bottom], R_BAR, mat))
    for y in np.linspace(-MOUTH_W / 2, MOUTH_W / 2, 7)[1:-1]:  # top mesh from the crossbar back
        back = min(top, key=lambda q: abs(q[1] - y) + (0 if q[0] < -1 else 1e6))
        parts.append(tube(f"top{y:.0f}", [(0, y, H), (back[0], y, H)], R_BAR, mat))
    return join(parts, "Goal")


def build_screen():
    mat = sb.clay("clay_screen", (0.85, 0.88, 0.9), 0.1)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Alpha"].default_value = 0.35
    mat.blend_method = "BLEND" if hasattr(mat, "blend_method") else None
    boundary = Polygon(g["board"]["inner_boundary"]["world"]["points_mm"])
    t = P("screen_thickness")
    ring = LineString(list(boundary.buffer(P("board_wall_thickness") + t / 2, join_style="round", quad_segs=24).exterior.coords))
    # End-centre of the W end: the ring point with minimum x near y = 0.
    L = ring.length
    s_c = min(np.linspace(0, L, 4000), key=lambda s: ring.interpolate(s).x + 10 * abs(ring.interpolate(s).y))
    length = g["end_screens"][0]["length"]["value"]  # catalog approx. 622 mm, ASSUMED to be the developed length
    height = g["end_screens"][0]["height"]["value"]  # catalog approx. 70 mm
    ss = np.linspace(s_c - length / 2, s_c + length / 2, 160) % L
    pts = [ring.interpolate(s) for s in ss]
    ox, oy = ring.interpolate(s_c).x, ring.interpolate(s_c).y
    local = [(p.x - ox, p.y - oy) for p in pts]
    sheet = LineString(local).buffer(t / 2, cap_style="flat", join_style="round")
    ob = sb.extrude("EndScreen", sheet, 0.0, height, mat)
    return ob, (ox, oy), length, height


def build_puck():
    D, T, R = g["puck"]["diameter"]["value"], P("puck_thickness"), P("puck_edge_radius")
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=sb.m(D / 2), depth=sb.m(T), location=(0, 0, 0))
    ob = bpy.context.active_object
    # Origin at the bottom centre (ice contact): shift the mesh data up, keep the object at the origin.
    for v in ob.data.vertices:
        v.co.z += sb.m(T / 2)
    ob.name = "Puck"
    ob.data.name = "Puck"
    bev = ob.modifiers.new("round", "BEVEL")
    bev.width = sb.m(R)
    bev.segments = 5
    bpy.ops.object.modifier_apply(modifier="round")
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(sb.clay("clay_puck", (0.05, 0.05, 0.05), 0.5))
    return ob, D, T


def save_asset(obj, folder, name):
    out = sb.REPO / "assets" / folder
    sb.save_blend(out / f"{name}.blend")
    sb.export_glb(out / f"{name}.glb", [obj])


# ---- Individual assets (each in its own clean scene, origin at the documented point) ------------
sb.reset_scene(); goal = build_goal(); save_asset(goal, "goal", "goal")
sb.reset_scene(); screen, screen_origin_w, screen_len, screen_h = build_screen(); save_asset(screen, "screen", "end_screen")
sb.reset_scene(); puck, puck_d, puck_t = build_puck(); save_asset(puck, "puck", "puck")

# Reference puck position: centroid of the black disc lying on the W-C slot in the official overhead.
from PIL import Image  # noqa: E402
Image.MAX_IMAGE_PIXELS = None
ov = next(s for s in g["source_images"] if s["source_id"] == "stiga_se_fi_overhead")
arr = np.asarray(Image.open(sb.REPO / ov["local_path"]).convert("RGB").crop((3230, 2760, 3440, 2960))).astype(int)
ys, xs = np.nonzero(arr.max(axis=2) < 60)
puck_px = (3230 + xs.mean() + 0.5, 2760 + ys.mean() + 0.5)
puck_w = w(puck_px)

# ---- Assembly into the static rink ---------------------------------------------------------------
bpy.ops.wm.open_mainfile(filepath=str(sb.REPO / "assets" / "rink" / "rink.blend"))
rink_objs = [o for o in bpy.data.objects if o.type == "MESH"]
rink_hash = {o.name: sum(v.co.length for v in o.data.vertices) for o in rink_objs}


def append(folder, name, obj_name):
    with bpy.data.libraries.load(str(sb.REPO / "assets" / folder / f"{name}.blend"), link=False) as (src, dst):
        dst.objects = [obj_name]
    ob = dst.objects[0]
    bpy.context.scene.collection.objects.link(ob)
    return ob


placed = []
for t, rot in (("W", 0.0), ("E", math.pi)):
    gob = append("goal", "goal", "Goal")
    gob.name = f"Goal.{t}"
    gob.location = (sb.m(mouth_x[t]), sb.m(centre_y[t]), 0.0)
    gob.rotation_euler = (0, 0, rot)
    placed.append(gob)
    sob = append("screen", "end_screen", "EndScreen")
    sob.name = f"EndScreen.{t}"
    sob.location = (sb.m(screen_origin_w[0] * (1 if t == "W" else -1)), sb.m(screen_origin_w[1] * (1 if t == "W" else -1)), 0.0)
    sob.rotation_euler = (0, 0, rot)
    placed.append(sob)
pob = append("puck", "puck", "Puck")
pob.location = (sb.m(puck_w[0]), sb.m(puck_w[1]), 0.0)
placed.append(pob)
bpy.context.view_layer.update()
unchanged = all(abs(sum(v.co.length for v in o.data.vertices) - rink_hash[o.name]) < 1e-9 for o in rink_objs)

# Screen fit at the E end (asset built from the W end, placed by a 180 deg rotation): distance of the
# screen sheet from the E board outer face.
boundary = Polygon(g["board"]["inner_boundary"]["world"]["points_mm"])
outer_face = LineString(list(boundary.buffer(P("board_wall_thickness") + P("screen_thickness") / 2, join_style="round", quad_segs=24).exterior.coords))
e_screen = bpy.data.objects["EndScreen.E"]
mw = e_screen.matrix_world
e_pts = [mw @ v.co for v in e_screen.data.vertices if abs(v.co.z) < 1e-9]
e_gap = max(outer_face.distance(Point(p.x * 1000, p.y * 1000)) for p in e_pts)

sb.save_blend(sb.REPO / "assets" / "scene" / "static_hardware.blend")
sb.export_glb(sb.REPO / "assets" / "scene" / "static_hardware.glb", rink_objs + placed)

# ---- Review renders ------------------------------------------------------------------------------
gx, gy = mouth_x["W"], centre_y["W"]
cam = sb.persp_camera("GoalOblique", (sb.m(gx + 170), sb.m(gy - 150), sb.m(110)), (sb.m(gx - 15), sb.m(gy), sb.m(20)), 50)
sb.render(cam, VAL / "12-goal-oblique.png", (1600, 1000), 48)
over_cam = sb.persp_camera("Overview", (sb.m(-150), sb.m(-620), sb.m(420)), (0.0, 0.0, 0.0), 35)
sb.render(over_cam, VAL / "12-overview.png", (1600, 900), 24)
# Side puck/ice-clearance view: a render-only copy of the puck in the W goal mouth, camera at ice level.
review = pob.copy(); review.data = pob.data; bpy.context.scene.collection.objects.link(review)
review.location = (sb.m(gx + 20), sb.m(gy + 15), 0.0)
cam2 = sb.persp_camera("PuckSide", (sb.m(gx + 20), sb.m(gy - 170), sb.m(6)), (sb.m(gx + 5), sb.m(gy), sb.m(12)), 85)
sb.render(cam2, VAL / "12-puck-side.png", (1600, 900), 48)
bpy.data.objects.remove(review)

report = {
    "goal": {"mouth_width_mm": round(MOUTH_W, 2), "mouth_width_per_goal_mm": {k: round(v, 2) for k, v in mouth.items()}, "depth_mm": round(DEPTH, 2), "depth_per_goal_mm": {k: round(v, 2) for k, v in depth.items()}, "height_mm": H, "post_radius_mm": R_POST, "bar_radius_mm": R_BAR, "top_depth_fraction": TOP_FRAC, "configuration": g["goal_setup"]["configuration"], "placement_mm": {t: [round(mouth_x[t], 2), round(centre_y[t], 2)] for t in ("W", "E")}},
    "screen": {"length_mm_catalog": screen_len, "height_mm_catalog": screen_h, "thickness_mm": P("screen_thickness"), "origin_W_mm": [round(v, 2) for v in screen_origin_w], "E_end_max_gap_to_board_face_mm": round(e_gap, 2)},
    "puck": {"diameter_mm_catalog": puck_d, "thickness_mm_preview": puck_t, "edge_radius_mm": P("puck_edge_radius"), "reference_position_px": [round(v, 1) for v in puck_px], "reference_position_mm": [round(v, 2) for v in puck_w]},
    "rink_meshes_unchanged": unchanged,
}
(VAL / "12-hardware-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=1))
