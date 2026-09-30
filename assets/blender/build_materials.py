"""Iteration 17: rink, housing, goal and end-screen materials on the unchanged iteration-16 scene.

    /root/venvs/blender/bin/python assets/blender/build_materials.py
Figures and puck keep their clay materials (iteration 18). Fixed, restrained light: one sun + grey world.
Outputs: assets/scene/full_static_materials.blend|.glb, validation/17-overhead.png, validation/17-oblique.png,
validation/17-overhead-vs-reference.png, validation/17-materials-report.json.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import bpy  # noqa: E402

g = sb.load_geometry()
VAL = sb.REPO / "validation"
Image.MAX_IMAGE_PIXELS = None
tex_rep = json.loads((VAL / "17-ice-texture-report.json").read_text())
x0, y0, x1, y1 = tex_rep["bounds_mm"]


def srgb_to_linear(c):
    c = np.asarray(c, float) / 255
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# Goal red sampled from the photo's cage pixels (median of the red-mask pixels used for the cage trace).
ov = next(s for s in g["source_images"] if s["source_id"] == "stiga_se_fi_overhead")
arr = np.asarray(Image.open(sb.REPO / ov["local_path"]).convert("RGB").crop((880, 2470, 1212, 3110))).astype(int)
red = arr[(arr[..., 0] > 140) & (arr[..., 0] - arr[..., 1] > 60) & (arr[..., 0] - arr[..., 2] > 60)]
goal_srgb = np.median(red, axis=0)
housing_arr = np.asarray(Image.open(sb.REPO / next(s for s in g["source_images"] if s["source_id"] == "stiga_se_fi_side_a")["local_path"]).convert("RGB").crop((700, 2780, 900, 3000))).astype(int)
housing_srgb = np.median(housing_arr.reshape(-1, 3), axis=0)

bpy.ops.wm.open_mainfile(filepath=str(sb.REPO / "assets" / "scene" / "full_static.blend"))
before = {n: [tuple(round(c, 9) for c in v.co) for v in bpy.data.objects[n].data.vertices] for n in ("Ice", "InnerBoards", "HousingBase", "HousingRim")}


def principled(name, base=None, rough=0.5, **inputs):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    if base is not None:
        b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Roughness"].default_value = rough
    for k, v in inputs.items():
        b.inputs[k].default_value = v
    return mat, b


# Ice: printed texture with planar UVs from world millimetres (calibrated: 1 texel = 0.1796 mm).
ice = bpy.data.objects["Ice"]
me = ice.data
uv = me.uv_layers.new(name="UVMap")
for loop in me.loops:
    co = me.vertices[loop.vertex_index].co
    uv.data[loop.index].uv = ((co.x * 1000 - x0) / (x1 - x0), (co.y * 1000 - y0) / (y1 - y0))
mat_ice, b = principled("ice_printed", rough=0.25)
img = bpy.data.images.load(str(sb.REPO / "assets" / "rink" / "textures" / "ice_basecolor.png"))
tn = mat_ice.node_tree.nodes.new("ShaderNodeTexImage")
tn.image = img
tn.interpolation = "Cubic"
mat_ice.node_tree.links.new(tn.outputs["Color"], b.inputs["Base Color"])
ice.data.materials.clear()
ice.data.materials.append(mat_ice)

mat_housing, _ = principled("housing_black_plastic", tuple(srgb_to_linear(housing_srgb)), 0.35)
for n in ("HousingBase", "HousingRim"):
    bpy.data.objects[n].data.materials.clear()
    bpy.data.objects[n].data.materials.append(mat_housing)
mat_boards, _ = principled("boards_printed_placeholder", tuple(srgb_to_linear((205, 205, 208))), 0.4)
bpy.data.objects["InnerBoards"].data.materials.clear()
bpy.data.objects["InnerBoards"].data.materials.append(mat_boards)
mat_goal, _ = principled("goal_red_plastic", tuple(srgb_to_linear(goal_srgb)), 0.35)
for n in ("Goal.W", "Goal.E"):
    bpy.data.objects[n].data.materials.clear()
    bpy.data.objects[n].data.materials.append(mat_goal)
mat_screen, bs = principled("screen_clear_plastic", (1.0, 1.0, 1.0), 0.03)
bs.inputs["Transmission Weight"].default_value = 1.0
bs.inputs["IOR"].default_value = 1.49
for n in ("EndScreen.W", "EndScreen.E"):
    bpy.data.objects[n].data.materials.clear()
    bpy.data.objects[n].data.materials.append(mat_screen)

# Fixed, restrained light.
for o in [o for o in bpy.data.objects if o.type == "LIGHT"]:
    bpy.data.objects.remove(o)
sb.set_world(0.55)
sb.add_sun(2.2, (30, 5, 25))
after = {n: [tuple(round(c, 9) for c in v.co) for v in bpy.data.objects[n].data.vertices] for n in before}
geometry_unchanged = before == after
sb.save_blend(sb.REPO / "assets" / "scene" / "full_static_materials.blend")
sb.export_glb(sb.REPO / "assets" / "scene" / "full_static_materials.glb", [o for o in bpy.data.objects if o.type == "MESH"])
# The iteration-16 benchmark cameras, recreated with identical parameters (build_assembly.py).
top_cam = sb.ortho_camera("AsmTop", (0, 0, 1.0), (0, 0, 0), 0.9312)
obl_cam = sb.persp_camera("AsmOblique", (sb.m(120), sb.m(-700), sb.m(430)), (0.0, sb.m(-20), 0.0), 35)
sb.save_blend(sb.REPO / "assets" / "scene" / "full_static_materials.blend")
sb.render(top_cam, VAL / "17-overhead.png", (1800, 1000), 64)
sb.render(obl_cam, VAL / "17-oblique.png", (1600, 900), 96)

# Side-by-side: render vs the reference overhead cropped to the same world window (uniform scale).
cam = top_cam.data
win_w = cam.ortho_scale * 1000
win_h = win_w * 1000 / 1800
M = next(m for m in g["image_to_world"] if m["id"] == "map.overhead.preview")["matrix"]
Ainv = np.linalg.inv(np.array([[M[0], M[1], M[2]], [M[3], M[4], M[5]], [0, 0, 1]]))
corners = [Ainv @ np.array([x, y, 1]) for x, y in ((-win_w / 2, win_h / 2), (win_w / 2, -win_h / 2))]
photo = Image.open(sb.REPO / ov["local_path"]).convert("RGB")
ref = photo.crop((int(corners[0][0]), int(corners[0][1]), int(corners[1][0]), int(corners[1][1]))).resize((1800, 1000))
rend = Image.open(VAL / "17-overhead.png").convert("RGB")
sheet = Image.new("RGB", (1800, 2000), "white")
sheet.paste(rend, (0, 0))
sheet.paste(ref, (0, 1000))
sheet.save(VAL / "17-overhead-vs-reference.png")

report = {
    "geometry_unchanged": geometry_unchanged,
    "ice_texture": "assets/rink/textures/ice_basecolor.png - sponsor-free (D6; validation/drop-sponsors-report.json), from ice_basecolor_reference.png (validation/17-ice-texture-report.json)",
    "uv": "planar from world mm over the inner-boundary bounds; 1 texel = %.6f mm" % tex_rep["texel_mm"],
    "goal_red_srgb_from_photo": [int(v) for v in goal_srgb],
    "housing_black_srgb_from_side_a": [int(v) for v in housing_srgb],
    "boards": "PLACEHOLDER light grey; no sponsors (user decision D6)",
    "screens": "clear plastic, transmission 1, IOR 1.49 (assumed)",
    "light": "sun 2.2 at (30, 5, 25) deg + grey world 0.55; Cycles, fixed seed",
    "gaps_and_mismatches": [
        "boards plain placeholder grey (sponsors dropped by user decision D6); black top rail not reconstructed",
        "housing 'PLAY OFF 21 / STIGA' print and legs not modelled",
        "ice: sponsor artwork dropped (D6, drop_sponsors.py); figure/goal areas reconstructed (iteration 17)",
        "ice: photo lighting, vignetting and board reflections near the edge remain baked into the texture",
        "ice: lens bow/keystone not corrected (<= about 16 px = about 3 mm at the preview scale)",
        "goal colour from the overhead includes photo lighting; plastic gloss assumed",
        "screen thickness, edge profile and mounting clips not modelled",
    ],
}
(VAL / "17-materials-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if k != "gaps_and_mismatches"}, indent=1))
