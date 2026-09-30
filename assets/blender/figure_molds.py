"""Rigid STIGA Play Off figure molds (skater, goalie) - geometry builders shared by build_figures.py.

Figure-local frame (mm): origin = the mounting (fixture) axis at the underside of the mount socket (ice
plane); +z up along the axis; +x = the direction the figure faces (chest/face); +y = the figure's LEFT.
Molds are authored at MOLD scale (mm) and scaled uniformly by the fitted factor in build_figures.py.

Layouts live in data/figure-molds.json (evidence and status there and in docs/players.md).
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import stiga_blender as sb

# Material keys; team colours are resolved in build_figures.py (Sweden yellow <-> Finland white).
KIT, BLUE, SKIN, METAL, TAN, DARK = "kit", "blue", "skin", "stick_metal", "stick_tan", "socket_bore"

MOLDS_JSON = sb.REPO / "data" / "figure-molds.json"


def load_molds() -> dict:
    import json
    return json.loads(MOLDS_JSON.read_text())


def _elements(part):
    balls = {n: (tuple(e["centre"]), tuple(e["semi_axes"])) for n, e in part.get("ellipsoids", {}).items()}
    caps = {n: (tuple(e["a"]), tuple(e["b"]), e["radius"]) for n, e in part.get("capsules", {}).items()}
    return balls, caps


# ---------------------------------------------------------------------------------------------------
def metaball_part(name: str, balls: dict, capsules: dict, cubes: dict | None = None, res_mm: float = 0.3):
    """Smooth part (metres) from ellipsoids, capsules and rounded boxes (mm), cf. sb.metaball_mesh."""
    mb = bpy.data.metaballs.new(name + "Meta")
    mb.resolution = mb.render_resolution = res_mm
    mb.threshold = 0.6
    ob = bpy.data.objects.new(name + "Meta", mb)
    bpy.context.scene.collection.objects.link(ob)
    for c, r in balls.values():
        e = mb.elements.new(type="ELLIPSOID")
        e.co, e.radius, e.stiffness = c, 1.0, 2.0
        e.size_x, e.size_y, e.size_z = [v / sb.METABALL_SURFACE for v in r]
    for a, b, r in capsules.values():
        va, vb = Vector(a), Vector(b)
        d = vb - va
        e = mb.elements.new(type="CAPSULE")
        e.co, e.radius, e.stiffness = (va + vb) / 2, r / sb.METABALL_SURFACE, 2.0
        e.size_x = d.length / 2
        e.rotation = Vector((1, 0, 0)).rotation_difference(d.normalized())
    for c, half, rot in (cubes or {}).values():
        # Rounded box: CUBE element with a small radius; its surface ~ half + 0.575 * radius.
        rr = 1.2
        e = mb.elements.new(type="CUBE")
        e.co, e.radius, e.stiffness = c, rr / sb.METABALL_SURFACE, 2.0
        e.size_x, e.size_y, e.size_z = [max(h - rr, 0.05) for h in half]
        e.rotation = Matrix.Rotation(math.radians(rot), 4, "Z").to_quaternion()
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.convert(target="MESH")
    part = bpy.context.view_layer.objects.active
    part.name = name
    for v in part.data.vertices:
        v.co = v.co * sb.MM_TO_M
    part.data.update()
    return part


def mesh_object(name: str, verts_mm, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(sb.m(c) for c in v) for v in verts_mm], [], faces)
    me.validate()
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def socket(name: str, spec: dict, centre_xy=(0.0, 0.0), n: int = 48):
    """Bell-shaped mount socket: lathe profile from r_bottom (flared foot) to r_top, with a rectangular key
    bore opening downward at the axis. Closed, manifold mesh built directly (no booleans)."""
    rb, rt, h, fl = spec["r_bottom"], spec["r_top"], spec["height"], spec["flare"]
    bw, bl, bd = spec["bore"]
    # outer profile (r, z) from the bottom rim upward; the flare is a concave bell curve
    prof = [(rb, 0.0), (rb, 0.35)] + [(rt + (rb - rt) * (1 - t) ** 2.2, 0.35 + fl * 0 + (h - 0.35) * t) for t in [i / 8 for i in range(1, 9)]]
    cx, cy = centre_xy
    verts, faces = [], []
    ring = lambda r, z: [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n), z) for k in range(n)]
    for r, z in prof:
        verts += ring(r, z)
    rings = len(prof)
    for i in range(rings - 1):
        for k in range(n):
            a, b = i * n + k, i * n + (k + 1) % n
            faces.append((a, b, b + n, a + n))
    top = len(verts)
    verts.append((cx, cy, h))
    for k in range(n):
        faces.append(((rings - 1) * n + k, (rings - 1) * n + (k + 1) % n, top))
    # bottom annulus: outer ring 0 -> inner rectangle (bore mouth), then the bore walls and ceiling
    rect = [(bw / 2, bl / 2), (-bw / 2, bl / 2), (-bw / 2, -bl / 2), (bw / 2, -bl / 2)]
    mouth = len(verts)
    verts += [(cx + x, cy + y, 0.0) for x, y in rect]
    ceil = len(verts)
    verts += [(cx + x, cy + y, bd) for x, y in rect]
    # fan each outer bottom vertex to the nearest rectangle corner region
    def corner_of(k):
        ang = 2 * math.pi * k / n
        return int(((ang - math.atan2(bl / 2, bw / 2)) % (2 * math.pi)) // (math.pi / 2)) + 1
    for k in range(n):
        c0, c1 = corner_of(k) % 4, corner_of((k + 1) % n) % 4
        faces.append(((k + 1) % n, k, mouth + c0))
        if c0 != c1:
            faces.append(((k + 1) % n, mouth + c0, mouth + c1))
    for j in range(4):
        a, b = mouth + j, mouth + (j + 1) % 4
        faces.append((a, b, ceil + (j + 1) % 4, ceil + j))
    faces.append((ceil + 3, ceil + 2, ceil + 1, ceil + 0))
    return mesh_object(name, verts, faces)


def box_between(name: str, a_mm, b_mm, width_mm: float, thick_mm: float, thick_dir=(1, 0, 0)):
    """Flat bar whose centre line runs a -> b (mm): `thick` along thick_dir (made orthogonal to the bar),
    `width` across both (e.g. a goalie paddle facing forward: thick_dir = +x)."""
    a, b = Vector(a_mm), Vector(b_mm)
    d = (b - a).normalized()
    n = Vector(thick_dir)
    n = (n - d * n.dot(d)).normalized()
    w = n.cross(d).normalized()
    hw, ht = width_mm / 2, thick_mm / 2
    corners = [(+1, +1), (-1, +1), (-1, -1), (+1, -1)]
    verts = [tuple(p + w * sw * hw + n * sn * ht) for p in (a, b) for sw, sn in corners]
    faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    return mesh_object(name, verts, faces)


def blade(name: str, a_xy, b_xy, height: float, thick: float, z0: float = 0.0, round_toe: bool = True):
    """Upright plate on the ice from a to b (plan mm), height along z, `thick` across; slight toe round."""
    ax, ay = a_xy
    bx, by = b_xy
    L = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / L, (by - ay) / L
    nx, ny = -uy * thick / 2, ux * thick / 2
    prof = [(0.0, z0), (L - (0.8 if round_toe else 0), z0), (L, z0 + 0.8 if round_toe else z0), (L, z0 + height), (0.0, z0 + height)]
    verts = []
    for s in (+1, -1):
        verts += [(ax + ux * t + s * nx, ay + uy * t + s * ny, z) for t, z in prof]
    m = len(prof)
    faces = [tuple(range(m))[::-1], tuple(range(m, 2 * m))]
    for i in range(m):
        j = (i + 1) % m
        faces.append((i, j, m + j, m + i))
    return mesh_object(name, verts, faces)


def tube(name: str, pts_mm, r_mm: float, n: int = 12):
    """Round wire along a polyline (mm): Blender curve with a circular bevel, converted to a closed mesh."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = sb.m(r_mm)
    cu.bevel_resolution = n // 4
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts_mm) - 1)
    for p, q in zip(sp.points, pts_mm):
        p.co = (*[sb.m(c) for c in q], 1.0)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.convert(target="MESH")
    return bpy.context.view_layer.objects.active


def tag(ob, key: str):
    ob["material_key"] = key
    return ob


def build_skater(mold: dict | None = None):
    """Skater mold parts (see data/figure-molds.json 'skater')."""
    m = (mold or load_molds())["skater"]
    parts = [tag(metaball_part(f"sk_{n}", *_elements(p)), p["material"]) for n, p in m["parts"].items()]
    parts.append(tag(socket("sk_socket", m["socket"]), BLUE))
    r = m["runner"]
    parts.append(tag(blade("sk_runner", r["a"], r["b"], r["height"], r["thickness"]), METAL))
    s = m["stick"]
    parts.append(tag(tube("sk_shaft", s["shaft"], s["shaft_r"]), METAL))
    parts.append(tag(blade("sk_blade", s["blade"][0], s["blade"][1], s["blade_h"], s["blade_t"], z0=0.0), METAL))
    return parts


def build_goalie(mold: dict | None = None):
    """Goalie mold parts (see data/figure-molds.json 'goalie')."""
    m = (mold or load_molds())["goalie"]
    parts = [tag(metaball_part(f"go_{n}", *_elements(p)), p["material"]) for n, p in m["parts"].items()]
    by_mat = {}
    for n, bx in m["boxes"].items():
        by_mat.setdefault(bx["material"], {})[n] = (tuple(bx["centre"]), tuple(bx["half_size"]), bx["rot_z_deg"])
    for k, cubes in by_mat.items():
        parts.append(tag(metaball_part(f"go_boxes_{k}", {}, {}, cubes), k))
    parts.append(tag(socket("go_socket", m["socket"]), BLUE))
    s = m["stick"]
    parts.append(tag(box_between("go_paddle", s["paddle"][0], s["paddle"][1], s["paddle_w"], s["paddle_t"]), TAN))
    parts.append(tag(blade("go_blade", s["blade"][0], s["blade"][1], s["blade_h"], s["blade_t"]), TAN))
    return parts
