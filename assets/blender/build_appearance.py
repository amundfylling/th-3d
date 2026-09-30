"""Iteration 18: uniforms and materials on the existing W-RD skater, W-G goalie, puck and placeholders.

    /root/venvs/blender/bin/python assets/blender/build_appearance.py
Geometry is not touched: materials are assigned per face. Body faces take the colour of their nearest
layout element (helmet, torso, gloves, ...); separate mesh islands (blade, shaft, skate blocks, goalie
stick) are classified by position. Colours: validation/18-colour-samples.json (overhead photo samples).
Outputs: updated assets/figures/skater_W-RD.*, goalie_W-G.*, assets/puck/puck.*,
assets/scene/full_static_appearance.blend|.glb, validation/18-appearance-report.json.
Renders: assets/blender/render_appearance.py.
"""
import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import bpy  # noqa: E402

VAL = sb.REPO / "validation"
FIG = sb.REPO / "assets" / "figures"
samples = json.loads((VAL / "18-colour-samples.json").read_text())


def lin(srgb):
    c = np.asarray(srgb, float) / 255
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))


# Jersey white: the brightest (goalie) sample is used for both whites; the W-RD sample (207) is shaded.
COL = {
    "fin_blue": lin(samples["finland_blue"]["srgb"]), "white": lin(samples["goalie_white"]["srgb"]), "skin": lin(samples["skin"]["srgb"]),
    "metal": lin(samples["stick_metal"]["srgb"]), "swe_yellow": lin(samples["sweden_yellow"]["srgb"]), "swe_blue": lin(samples["sweden_blue"]["srgb"]),
    "tan": lin(samples["goalie_tan"]["srgb"]), "goalie_blue": lin(samples["goalie_blue"]["srgb"]), "puck": lin((28, 28, 30)),
}
ROUGH = {"metal": 0.3, "puck": 0.55, "skin": 0.45}


def mat(key):
    name = f"app_{key}"
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*COL[key], 1)
        b.inputs["Roughness"].default_value = ROUGH.get(key, 0.35)
        if key == "metal":
            b.inputs["Metallic"].default_value = 1.0
    return m


def layout(script):
    """BALLS / CAPSULES literals from a build script (parsed, not executed)."""
    tree = ast.parse((sb.REPO / "assets" / "blender" / script).read_text())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("BALLS", "CAPSULES"):
            out[node.targets[0].id] = ast.literal_eval(node.value)
    return out["BALLS"], out["CAPSULES"]


def element_distance(p, balls, caps):
    """Name of the layout element nearest to point p (mm), by normalised ellipsoid / capsule distance."""
    best, bn = 1e9, None
    for n, (c, r) in balls.items():
        d = np.linalg.norm((np.asarray(p) - np.asarray(c)) / np.asarray(r)) - 1
        d *= min(r)
        if d < best:
            best, bn = d, n
    for n, (a, b, r) in caps.items():
        a, b, p_ = map(np.asarray, (a, b, p))
        t = np.clip(np.dot(p_ - a, b - a) / np.dot(b - a, b - a), 0, 1)
        d = np.linalg.norm(p_ - (a + t * (b - a))) - r
        if d < best:
            best, bn = d, n
    return bn


def islands(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    seen, groups = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, grp = [f], []
        seen.add(f.index)
        while stack:
            x = stack.pop()
            grp.append(x.index)
            for e in x.edges:
                for y in e.link_faces:
                    if y.index not in seen:
                        seen.add(y.index)
                        stack.append(y)
        groups.append(grp)
    bm.free()
    return sorted(groups, key=len, reverse=True)


def paint(obj, element_colour, small_island_colour):
    me = obj.data
    me.materials.clear()
    keys = sorted(set(element_colour.values()) | set(small_island_colour(None, None, probe=True)))
    for k in keys:
        me.materials.append(mat(k))
    idx = {k: i for i, k in enumerate(keys)}
    groups = islands(me)
    body = set(groups[0])
    for f in me.polygons:
        c = f.center * 1000
        if f.index in body:
            key = element_colour[element_distance(c, *LAYOUT[obj["layout"]])]
        else:
            key = small_island_colour(f, c)
        f.material_index = idx[key]


SKATER_COLOURS = {"helmet": "fin_blue", "face": "skin", "neck": "skin", "torso": "white", "pelvis": "fin_blue",
                  "arm_left_upper": "white", "arm_left_lower": "white", "arm_right_upper": "white", "arm_right_lower": "white",
                  "glove_left": "fin_blue", "glove_right": "fin_blue", "leg_left_thigh": "fin_blue", "leg_right_thigh": "fin_blue",
                  "leg_left_shin": "white", "leg_right_shin": "white", "boot_left": "fin_blue", "boot_right": "fin_blue"}
GOALIE_COLOURS = {"helmet": "goalie_blue", "mask": "goalie_blue", "neck": "skin", "torso": "white", "pelvis": "goalie_blue",
                  "catcher": "goalie_blue", "blocker": "goalie_blue", "pad_left": "goalie_blue", "pad_right": "goalie_blue",
                  "toe_right": "goalie_blue", "thigh_area": "white", "arm_left": "white", "arm_right": "white",
                  "thigh_left": "goalie_blue", "thigh_right": "goalie_blue"}
LAYOUT = {"skater": layout("build_skater_body.py"), "goalie": layout("build_goalie.py")}


def skater_small(f, c, probe=False):
    if probe:
        return ["metal", "fin_blue"]
    return "fin_blue" if c.z <= 3.01 and abs(c.y) < 8 else "metal"  # skate blocks vs blade/shaft


def goalie_small(f, c, probe=False):
    return ["tan"] if probe else "tan"


def positions(obj):
    return [tuple(round(x, 9) for x in v.co) for v in obj.data.vertices]


def process_asset(blend, obj_name, kind, colours, small):
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    ob = bpy.data.objects[obj_name]
    before = positions(ob)
    ob["layout"] = kind
    paint(ob, colours, small)
    assert positions(ob) == before
    sb.save_blend(blend)
    sb.export_glb(blend.with_suffix(".glb"), [ob])
    return len(before)


n_sk = process_asset(FIG / "skater_W-RD.blend", "Skater.W-RD", "skater", SKATER_COLOURS, skater_small)
n_go = process_asset(FIG / "goalie_W-G.blend", "Goalie.W-G", "goalie", GOALIE_COLOURS, goalie_small)
bpy.ops.wm.open_mainfile(filepath=str(sb.REPO / "assets" / "puck" / "puck.blend"))
pk = bpy.data.objects["Puck"]
pk.data.materials.clear()
pk.data.materials.append(mat("puck"))
sb.save_blend(sb.REPO / "assets" / "puck" / "puck.blend")
sb.export_glb(sb.REPO / "assets" / "puck" / "puck.glb", [pk])

# ---- Full scene (iteration-17 materials) with figure appearance -------------------------------------
bpy.ops.wm.open_mainfile(filepath=str(sb.REPO / "assets" / "scene" / "full_static_materials.blend"))
scene_before = {o.name: positions(o) for o in bpy.data.objects if o.type == "MESH"}
for o in bpy.data.objects:
    if o.name == "Figure.W-RD":
        o["layout"] = "skater"
        paint(o, SKATER_COLOURS, skater_small)
    elif o.name == "Figure.W-G":
        o["layout"] = "goalie"
        paint(o, GOALIE_COLOURS, goalie_small)
    elif o.name == "Puck":
        o.data.materials.clear()
        o.data.materials.append(mat("puck"))
    elif o.name.startswith("Figure."):
        team = o.name.split(".")[1][0]
        body_key, head_key = ("white", "fin_blue") if team == "W" else ("swe_yellow", "swe_blue")
        o.data.materials.clear()
        o.data.materials.append(mat(body_key))
        o.data.materials.append(mat(head_key))
        h = max(v.co.z for v in o.data.vertices)
        for f in o.data.polygons:
            f.material_index = 1 if f.center.z > h - 0.012 else 0
scene_unchanged = scene_before == {o.name: positions(o) for o in bpy.data.objects if o.type == "MESH"}
sb.save_blend(sb.REPO / "assets" / "scene" / "full_static_appearance.blend")
sb.export_glb(sb.REPO / "assets" / "scene" / "full_static_appearance.glb", [o for o in bpy.data.objects if o.type == "MESH"])

report = {
    "colours_srgb": {k: samples[v]["srgb"] for k, v in {"fin_blue": "finland_blue", "white": "goalie_white", "skin": "skin", "metal": "stick_metal", "swe_yellow": "sweden_yellow", "swe_blue": "sweden_blue", "tan": "goalie_tan", "goalie_blue": "goalie_blue"}.items()},
    "colour_sources": "validation/18-colour-samples.json",
    "geometry_unchanged": {"skater_vertices": n_sk, "goalie_vertices": n_go, "scene": scene_unchanged},
    "unresolved_decals": ["jersey numbers (W-RD no. 4; goalie number unseen)", "'FINLAND' lettering on the backs", "Sweden lettering/numbers (placeholders)", "puck STIGA logo emboss", "helmet/mask details, face features", "stripe patterns on sleeves/socks"],
    "placeholders": "team two-tone (Finland white/blue, Sweden yellow/blue); still placeholders",
}
(VAL / "18-appearance-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=1))
