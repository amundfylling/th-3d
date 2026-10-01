"""Shared helpers for the headless Blender (bpy) asset builds.

Units: canonical data is in millimetres (data/geometry.json). The ONLY mm -> m conversion is `m()`
below; Blender scenes use metres with the world axes unchanged (x toward goal.E, y toward the
overhead's image top, z up). The glTF exporter's +Y-up option performs the single axis conversion.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import bpy
import mapbox_earcut as earcut
import numpy as np
from shapely.geometry import LineString, Polygon, MultiPolygon
from shapely.ops import unary_union

REPO = Path(__file__).resolve().parents[2]
MM_TO_M = 0.001


def m(v_mm: float) -> float:
    """The single millimetre -> metre conversion used by every build."""
    return v_mm * MM_TO_M


def load_geometry() -> dict:
    return json.loads((REPO / "data" / "geometry.json").read_text())


def preview(g: dict, key: str) -> float:
    q = g["preview_parameters"][key]
    assert q["status"] == "assumed" and q["unit"] == "mm", key
    return float(q["value"])


def px_to_world(g: dict, mapping_id: str, pts):
    mat = next(x for x in g["image_to_world"] if x["id"] == mapping_id)["matrix"]
    return [(mat[0] * u + mat[1] * v + mat[2], mat[3] * u + mat[4] * v + mat[5]) for u, v in pts]


def mm_per_px(g: dict, mapping_id: str = "map.overhead.preview") -> float:
    mat = next(x for x in g["image_to_world"] if x["id"] == mapping_id)["matrix"]
    return math.hypot(mat[0], mat[3])


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0


def clay(name: str, rgb, roughness: float = 0.6):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def _rings(poly: Polygon):
    ext = list(poly.exterior.coords)[:-1]
    holes = [list(r.coords)[:-1] for r in poly.interiors]
    # earcut expects exterior CCW and holes CW for consistent winding; shapely orient does that.
    from shapely.geometry.polygon import orient
    p = orient(Polygon(ext, holes), sign=1.0)
    return [list(p.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in p.interiors]


def extrude(name: str, shape, z0_mm: float, z1_mm: float, material=None):
    """Extrudes a shapely (Multi)Polygon (mm) between z0 and z1 (mm) into one closed mesh object (m)."""
    polys = list(shape.geoms) if isinstance(shape, MultiPolygon) else [shape]
    verts, faces = [], []
    for poly in polys:
        rings = _rings(poly)
        flat = np.array([p for r in rings for p in r], dtype=np.float64)
        ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
        tri = earcut.triangulate_float64(flat, ends).reshape(-1, 3)
        n = len(flat)
        base = len(verts)
        verts += [(m(x), m(y), m(z0_mm)) for x, y in flat] + [(m(x), m(y), m(z1_mm)) for x, y in flat]
        faces += [tuple(base + n + i for i in t) for t in tri]  # top (CCW seen from +z)
        faces += [tuple(base + i for i in t[::-1]) for t in tri]  # bottom
        start = 0
        for e in ends:
            for i in range(start, int(e)):
                j = start + (i - start + 1) % (int(e) - start)
                faces.append((base + i, base + j, base + n + j, base + n + i))
            start = int(e)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def slot_polygon(centreline_mm, width_mm: float):
    return LineString(centreline_mm).buffer(width_mm / 2, cap_style="round", join_style="round", quad_segs=12)


def add_sun(strength: float = 3.0, angle_deg=(35, 0, 30)):
    light = bpy.data.lights.new("Sun", type="SUN")
    light.energy = strength
    light.angle = math.radians(8)
    obj = bpy.data.objects.new("Sun", light)
    obj.rotation_euler = tuple(math.radians(a) for a in angle_deg)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def studio_world(strength: float = 0.6, name: str = "interior", rotate_deg: float = 0.0):
    """Image-based world: one of Blender's bundled studio-light HDRIs (datafiles/studiolights/world/<name>.exr,
    shipped with Blender), so glossy plastic and the metal stick have something to reflect. Not copied into
    the repository."""
    path = Path(bpy.utils.system_resource("DATAFILES", path="studiolights/world")) / f"{name}.exr"
    world = bpy.data.worlds.new("StudioWorld")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(path), check_existing=True)
    mp = nt.nodes.new("ShaderNodeMapping")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp.inputs["Rotation"].default_value[2] = math.radians(rotate_deg)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    bpy.context.scene.world = world
    return path


def set_world(grey: float = 0.35):
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (grey, grey, grey, 1)
    bpy.context.scene.world = world


def ortho_camera(name: str, location_m, rotation_deg, ortho_scale_m: float):
    cam = bpy.data.cameras.new(name)
    cam.type = "ORTHO"
    cam.ortho_scale = ortho_scale_m
    cam.clip_end = 20
    obj = bpy.data.objects.new(name, cam)
    obj.location = location_m
    obj.rotation_euler = tuple(math.radians(a) for a in rotation_deg)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def persp_camera(name: str, location_m, look_at_m, lens_mm: float = 50):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens_mm
    cam.clip_start = 0.01
    cam.clip_end = 20
    obj = bpy.data.objects.new(name, cam)
    obj.location = location_m
    bpy.context.scene.collection.objects.link(obj)
    direction = np.array(look_at_m) - np.array(location_m)
    from mathutils import Vector
    obj.rotation_euler = Vector(direction.tolist()).to_track_quat("-Z", "Y").to_euler()
    return obj


def render(camera, path: Path, res=(1600, 900), samples: int = 32) -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.seed = 1
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.camera = camera
    scene.render.filepath = str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)


def export_glb(path: Path, objects) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_yup=True, export_apply=True, export_animations=False)


def save_blend(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))


def union(shapes):
    return unary_union(list(shapes))


# ---- Calibrated metaball bodies (docs/figures.md) --------------------------------------------------
METABALL_SURFACE = 0.575  # isolated element surface at 0.575 x radius x size (threshold 0.6, stiffness 2)


def metaball_mesh(name: str, balls: dict, capsules: dict, res_mm: float = 0.25):
    """Smooth body mesh (metres) from ellipsoids {name: (centre_mm, semi_axes_mm)} and capsules
    {name: (a_mm, b_mm, radius_mm)}. Built in millimetre units because Blender clamps metaball
    resolution to >= 0.005 units, then scaled by MM_TO_M."""
    from mathutils import Vector
    mb = bpy.data.metaballs.new(name + "Meta")
    mb.resolution = res_mm
    mb.render_resolution = res_mm
    mb.threshold = 0.6
    ob = bpy.data.objects.new(name + "Meta", mb)
    bpy.context.scene.collection.objects.link(ob)
    for c, r in balls.values():
        e = mb.elements.new(type="ELLIPSOID")
        e.co = c
        e.radius = 1.0
        e.size_x, e.size_y, e.size_z = [v / METABALL_SURFACE for v in r]
        e.stiffness = 2.0
    for a, b, r in capsules.values():
        va, vb = Vector(a), Vector(b)
        d = vb - va
        e = mb.elements.new(type="CAPSULE")
        e.co = (va + vb) / 2
        e.radius = r / METABALL_SURFACE
        e.size_x = d.length / 2
        e.rotation = Vector((1, 0, 0)).rotation_difference(d.normalized())
        e.stiffness = 2.0
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.convert(target="MESH")
    body = bpy.context.view_layer.objects.active
    body.name = name
    for v in body.data.vertices:
        v.co = v.co * MM_TO_M
    body.data.update()
    return body


def silhouette_iou(obj, polygons_local_mm, centre_mm, n_px: int, mm_per_px: float, out_png: Path, render_png: Path) -> float:
    """Orthographic top render of `obj` (black emission) vs the union of reference polygons (local mm)."""
    from PIL import Image, ImageDraw
    mat = bpy.data.materials.new("silhouette")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0, 0, 0, 1)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    saved = list(obj.data.materials)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    hidden = [o for o in bpy.context.scene.objects if o is not obj and o.type == "MESH" and not o.hide_render]
    for o in hidden:
        o.hide_render = True
    set_world(1.0)
    cam = ortho_camera("SilTop", (m(centre_mm[0]), m(centre_mm[1]), 0.5), (0, 0, 0), m(n_px * mm_per_px))
    render(cam, render_png, (n_px, n_px), 1)
    rend = np.asarray(Image.open(render_png).convert("L")) < 128
    ref_img = Image.new("L", (n_px, n_px), 0)
    to_px = lambda p: ((p[0] - centre_mm[0]) / mm_per_px + n_px / 2, n_px / 2 - (p[1] - centre_mm[1]) / mm_per_px)
    for poly in polygons_local_mm:
        ImageDraw.Draw(ref_img).polygon([to_px(p) for p in poly], fill=255)
    ref = np.asarray(ref_img) > 0
    iou = float((rend & ref).sum() / (rend | ref).sum())
    viz = np.full((n_px, n_px, 3), 255, np.uint8)
    viz[ref & ~rend] = (230, 60, 60)
    viz[rend & ~ref] = (60, 90, 230)
    viz[rend & ref] = (120, 120, 120)
    Image.fromarray(viz).resize((n_px * 3, n_px * 3), Image.NEAREST).save(out_png)
    obj.data.materials.clear()
    for s_ in saved:
        obj.data.materials.append(s_)
    for o in hidden:
        o.hide_render = False
    bpy.data.objects.remove(cam)
    return iou
