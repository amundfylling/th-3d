"""Development preview of the figure molds: joined mesh -> out/figures/<kind>.npz (for fit-figure-views.py)
and four quick views -> out/figures/<kind>-views.png.

    /root/venvs/blender/bin/python assets/blender/preview_molds.py [skater|goalie ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402
import figure_molds as fm  # noqa: E402
import numpy as np  # noqa: E402

import bpy  # noqa: E402

OUT = sb.REPO / "out" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
PREVIEW_RGB = {fm.KIT: (0.62, 0.42, 0.0), fm.BLUE: (0.03, 0.13, 0.32), fm.SKIN: (0.58, 0.29, 0.24), fm.METAL: (0.6, 0.6, 0.62),
               fm.TAN: (0.78, 0.34, 0.17), fm.DARK: (0.02, 0.02, 0.02)}
KEYS = [fm.KIT, fm.BLUE, fm.SKIN, fm.METAL, fm.TAN, fm.DARK]


def join(parts, name):
    mats = {k: sb.clay(f"prev_{k}", PREVIEW_RGB[k], 0.4) for k in KEYS}
    for p in parts:
        p.data.materials.clear()
        p.data.materials.append(mats[p["material_key"]])
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob


def dump(ob, path, ratio=0.06):
    """Decimated copy (fitting only needs the silhouette) -> npz."""
    tmp = ob.copy()
    tmp.data = ob.data.copy()
    bpy.context.scene.collection.objects.link(tmp)
    mod = tmp.modifiers.new("dec", "DECIMATE")
    mod.ratio = ratio
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = tmp
    tmp.select_set(True)
    bpy.ops.object.modifier_apply(modifier="dec")
    me = tmp.data
    me.calc_loop_triangles()
    v = np.array([vv.co[:] for vv in me.vertices]) * 1000.0
    tris = np.array([t.vertices[:] for t in me.loop_triangles], dtype=np.int32)
    key_of_slot = [m.name.replace("prev_", "") for m in me.materials]
    lab = np.array([KEYS.index(key_of_slot[t.material_index]) for t in me.loop_triangles], dtype=np.int8)
    np.savez_compressed(path, verts=v, tris=tris, labels=lab, keys=np.array(KEYS))
    bpy.data.objects.remove(tmp)
    print("fit mesh triangles", len(tris))
    return v


for kind in (sys.argv[1:] or ["skater", "goalie"]):
    sb.reset_scene()
    parts = fm.build_skater() if kind == "skater" else fm.build_goalie()
    ob = join(parts, f"Mold.{kind}")
    v = dump(ob, OUT / f"{kind}.npz")
    print(kind, "verts", len(v), "bbox mm", v.min(0).round(2), v.max(0).round(2))
    sb.set_world(0.6)
    sb.add_sun(3.0, (40, 10, 30))
    c = (v.min(0) + v.max(0)) / 2
    tiles = []
    for i, yaw in enumerate((0, 90, 180, 270)):
        import math
        a = math.radians(yaw)
        d, el = 0.35, math.radians(25)
        loc = (sb.m(c[0]) + d * math.cos(a) * math.cos(el), sb.m(c[1]) + d * math.sin(a) * math.cos(el), sb.m(c[2]) + d * math.sin(el))
        cam = sb.ortho_camera(f"C{i}", loc, (0, 0, 0), sb.m(64))
        from mathutils import Vector
        cam.rotation_euler = (Vector((sb.m(c[0]), sb.m(c[1]), sb.m(c[2]))) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        p = OUT / f"{kind}-v{yaw}.png"
        sb.render(cam, p, (500, 500), 16)
        tiles.append(p)
    from PIL import Image
    sheet = Image.new("RGB", (2000, 500))
    for i, p in enumerate(tiles):
        sheet.paste(Image.open(p).convert("RGB"), (i * 500, 0))
    sheet.save(OUT / f"{kind}-views.png")
