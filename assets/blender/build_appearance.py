"""Iteration 18 (updated for the figure molds): puck material and the appearance scene.

    /root/venvs/blender/bin/python assets/blender/build_appearance.py
Geometry is not touched. Figures carry their own materials and back prints (build_figures.py,
build_assembly.py); only the puck is coloured here. Colours: validation/18-colour-samples.json.
Outputs: assets/puck/puck.*, assets/scene/full_static_appearance.blend|.glb, validation/18-appearance-report.json.
Renders: assets/blender/render_appearance.py.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402
import numpy as np  # noqa: E402

import bpy  # noqa: E402

VAL = sb.REPO / "validation"
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


def positions(obj):
    return [tuple(round(x, 9) for x in v.co) for v in obj.data.vertices]


# Figures: the rigid mold assets (build_figures.py) carry their own materials and back prints since the
# figure-mold update; nothing is repainted here.
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
    if o.name == "Puck":
        o.data.materials.clear()
        o.data.materials.append(mat("puck"))
scene_unchanged = scene_before == {o.name: positions(o) for o in bpy.data.objects if o.type == "MESH"}
sb.save_blend(sb.REPO / "assets" / "scene" / "full_static_appearance.blend")
sb.export_glb(sb.REPO / "assets" / "scene" / "full_static_appearance.glb", [o for o in bpy.data.objects if o.type == "MESH"])

report = {
    "colours_srgb": {k: samples[v]["srgb"] for k, v in {"fin_blue": "finland_blue", "white": "goalie_white", "skin": "skin", "metal": "stick_metal", "swe_yellow": "sweden_yellow", "swe_blue": "sweden_blue", "tan": "goalie_tan", "goalie_blue": "goalie_blue"}.items()},
    "colour_sources": "validation/18-colour-samples.json",
    "geometry_unchanged": {"scene": scene_unchanged},
    "figures": "rigid mold assets with their own materials and per-player back prints (build_figures.py, build_assembly.py); not repainted here",
    "unresolved_decals": ["puck STIGA logo emboss", "face features (eyes, mouth) not painted", "print fonts approximate the moulded print"],
}
(VAL / "18-appearance-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=1))
