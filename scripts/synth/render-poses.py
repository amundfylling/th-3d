"""Render the goalie alone at listed poses (for checking pose labels): <poses.json> <out_dir>; poses [{name, end, u, theta}]."""
import json, sys, math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix
sys.argv += []  # noqa
REPO = Path(__file__).resolve().parents[2]
spec = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
poses = json.loads(Path(spec[0]).read_text()); OUT = Path(spec[1]); OUT.mkdir(parents=True, exist_ok=True)
src = (REPO / "scripts/synth/render-goalie-crops.py").read_text()
# reuse the camera, slot and placement helpers of the batch renderer
exec(src.split("set_camera()\nsc.render.engine")[0].replace("OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)\nSEED0, COUNT = int(sys.argv[2]), int(sys.argv[3])", ""))
set_camera()
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 8; sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"; sc.render.film_transparent = True
sc.render.image_settings.color_mode = "RGBA"; sc.render.use_border = True; sc.render.use_crop_to_border = True
bpy.data.objects["Ice"].is_shadow_catcher = True
for o in bpy.data.objects:
    if o.type == "MESH" and o.name.startswith(("Goal.", "InnerBoards", "EndScreen", "Housing")): o.is_holdout = True
    if o.name.startswith(("Figure.", "Print.")) or o.name == "Puck": o.hide_render = True
bpy.data.materials["fig_kit_SWE"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.80, 0.56, 0.01, 1)
W, H = CAM["image_size"]
for p in poses:
    end = p["end"]; x0, y0, x1, y1 = BOX[end]
    sc.render.border_min_x, sc.render.border_max_x, sc.render.border_min_y, sc.render.border_max_y = x0 / W, x1 / W, 1 - y1 / H, 1 - y0 / H
    for e in "WE":
        bpy.data.objects[f"Figure.{e}-G"].hide_render = e != end
        for c in bpy.data.objects[f"Figure.{e}-G"].children: c.hide_render = e != end
    place(bpy.data.objects[f"Figure.{end}-G"], f"{end}-G", p["u"], p["theta"])
    sc.render.filepath = str(OUT / f"{p['name']}.png"); bpy.ops.render.render(write_still=True)
