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
    balls = {n: (tuple(e["centre"]), tuple(e["semi_axes"]), tuple(e.get("rot_deg", (0, 0, 0)))) for n, e in part.get("ellipsoids", {}).items()}
    caps = {n: (tuple(e["a"]), tuple(e["b"]), e["radius"]) for n, e in part.get("capsules", {}).items()}
    return balls, caps


def _euler_q(rot_deg):
    from mathutils import Euler
    return Euler([math.radians(a) for a in rot_deg], "XYZ").to_quaternion()


def rbox(name: str, centre, half, rot_deg=(0, 0, 0), bevel: float = 0.5, segments: int = 3):
    """Hard-surface rounded box (mm): moulded edges via a bevel; rotation XYZ Euler (deg)."""
    verts = [(sx * half[0], sy * half[1], sz * half[2]) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    ob = mesh_object(name, verts, faces)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = _euler_q(rot_deg)
    ob.location = Vector(centre) * sb.MM_TO_M
    _bevel_apply(ob, min(bevel, 0.95 * min(half)), segments)
    return ob


def cone(name: str, a, b, r_a: float, r_b: float, bevel: float = 0.3, n: int = 32):
    """Truncated cone (mm) from a (radius r_a) to b (radius r_b), closed, edges bevelled (cuffs, sleeves)."""
    va, vb = Vector(a), Vector(b)
    d = vb - va
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    verts = []
    for z, r in ((0.0, r_a), (d.length, r_b)):
        verts += [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), z) for k in range(n)]
    faces = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    faces += [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    ob = mesh_object(name, verts, faces)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = q
    ob.location = va * sb.MM_TO_M
    _bevel_apply(ob, min(bevel, 0.45 * min(r_a, r_b, d.length)), 2)
    return ob


def torus(name: str, centre, axis, R: float, r: float, scale_r=(1.0, 1.0), nu: int = 48, nv: int = 16, r_axial: float | None = None):
    """Smooth ring (mm) around `axis` through `centre`; scale_r stretches the ring (u, v) into an oval."""
    a = Vector(axis).normalized()
    q = Vector((0, 0, 1)).rotation_difference(a)
    verts, faces = [], []
    for i in range(nu):
        t = 2 * math.pi * i / nu
        cx, cy = R * scale_r[0] * math.cos(t), R * scale_r[1] * math.sin(t)
        for j in range(nv):
            s_ = 2 * math.pi * j / nv
            verts.append((cx + r * math.cos(s_) * math.cos(t), cy + r * math.cos(s_) * math.sin(t), (r_axial or r) * math.sin(s_)))
    for i in range(nu):
        for j in range(nv):
            a0, a1 = i * nv + j, i * nv + (j + 1) % nv
            b0, b1 = ((i + 1) % nu) * nv + j, ((i + 1) % nu) * nv + (j + 1) % nv
            faces.append((a0, b0, b1, a1))
    ob = mesh_object(name, verts, faces)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = q
    ob.location = Vector(centre) * sb.MM_TO_M
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.shade_smooth()
    return ob


def cuff(name: str, a, b, r_a: float, r_b: float, oval=(1.0, 1.0), up=(0, 0, 1), lip: float = 0.45,
         depth: float = 0.35, cut_deg: float = 0.0, n: int = 40):
    """Moulded gauntlet cuff (mm): a flared shell from the wrist `b` (radius r_b) to the open end `a` (radius r_a),
    oval cross-section (oval = scale along the cuff's side axis / up axis), a rounded rolled rim of thickness `lip`
    at the open end, and a recessed mouth `depth` x length deep (the forearm sits inside). cut_deg tilts the
    open end (the opening slants toward `up`). Built as one closed lathe surface."""
    va, vb = Vector(a), Vector(b)
    ax = (va - vb).normalized()  # from wrist to open end
    L = (va - vb).length
    u = Vector(up)
    u = (u - ax * u.dot(ax)).normalized()
    side = ax.cross(u).normalized()
    # profile (r, z) along the axis from the wrist (z=0) to the open end, then over the lip and into the mouth
    prof = []
    for t in [i / 10 for i in range(11)]:
        r = r_b + (r_a - r_b) * (t ** 1.4)  # slight trumpet flare
        prof.append((r, t * L))
    for k in range(1, 7):  # rolled rim: half circle over the lip
        th = math.pi * k / 6
        prof.append((r_a - lip / 2 + lip / 2 * math.cos(th), L + lip / 2 * math.sin(th) * 0.8))
    d = depth * L
    for t in [i / 6 for i in range(1, 7)]:
        prof.append(((r_a - lip) - (r_a - lip - 0.55 * r_b) * t ** 0.7, L - d * t))
    verts = []
    for r, z in prof:
        for k in range(n):
            phi = 2 * math.pi * k / n
            x, y = r * math.cos(phi) * oval[0], r * math.sin(phi) * oval[1]
            zz = z + (math.tan(math.radians(cut_deg)) * y if z > 0.6 * L else 0.0)
            verts.append(tuple(vb + side * x + u * y + ax * zz))
    m = len(prof)
    faces = []
    for i in range(m - 1):
        for k in range(n):
            a0, a1 = i * n + k, i * n + (k + 1) % n
            faces.append((a0, a1, a1 + n, a0 + n))
    c0 = len(verts)
    verts.append(tuple(vb))
    faces += [((k + 1) % n, k, c0) for k in range(n)]  # wrist cap
    c1 = len(verts)
    verts.append(tuple(vb + ax * (L - d)))
    faces += [((m - 1) * n + k, (m - 1) * n + (k + 1) % n, c1) for k in range(n)]  # mouth floor
    ob = mesh_object(name, verts, faces)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(50))
    return ob


def loft_cuff(name: str, mouth_c, mouth_n, mouth_long, mouth_r, wrist_c, wrist_r, lip: float = 0.5,
              depth: float = 1.2, flare: float = 1.4, base: float = 0.0, n: int = 56):
    """Moulded gauntlet cuff (mm) lofted between a wrist ring and an independently oriented oval mouth.
    The mouth ring lies in its own plane (normal `mouth_n`, long axis `mouth_long`, semi-axes mouth_r =
    (long, short)), so a broad, flat cuff can open upward while its body runs obliquely down to the wrist
    (`wrist_c`, semi-axes wrist_r = (along the mouth's long axis, across)). Rings in between: centre linear,
    offsets blended with t**flare (trumpet). A rolled rim of thickness `lip` crowns the mouth and the
    opening is recessed `depth` mm along the cuff (the forearm sits inside). `base` > 0 closes the wrist end
    with a rounded bottom that far beyond the wrist ring (a broad cuff the glove leaves at one side). One
    closed surface."""
    M, B = Vector(mouth_c), Vector(wrist_c)
    N = Vector(mouth_n).normalized()
    Lg = Vector(mouth_long)
    Lg = (Lg - N * Lg.dot(N)).normalized()
    Sh = N.cross(Lg)
    ax = (M - B).normalized()
    L = (M - B).length
    wl = (Lg - ax * Lg.dot(ax)).normalized()
    ws = ax.cross(wl)
    if ws.dot(Sh) < 0:
        ws = -ws
    phis = [2 * math.pi * k / n for k in range(n)]
    mo = [Lg * (mouth_r[0] * math.cos(p)) + Sh * (mouth_r[1] * math.sin(p)) for p in phis]
    wo = [wl * (wrist_r[0] * math.cos(p)) + ws * (wrist_r[1] * math.sin(p)) for p in phis]

    def ring(t, shrink=1.0):
        c = B + (M - B) * t
        f = t ** flare
        return [c + (w + (m - w) * f) * shrink for w, m in zip(wo, mo)]

    rings = []
    for k in range(5, 0, -1):  # rounded bottom below the wrist ring (quarter ellipse)
        if base > 0:
            th = math.pi / 2 * k / 5
            rings.append([B - ax * (base * math.sin(th)) + w * math.cos(th) for w in wo])
    rings += [ring(i / 14) for i in range(15)]
    for k in range(1, 7):  # rolled rim over the lip
        th = math.pi * k / 6
        rr = []
        for m in mo:
            rd = m.normalized()
            rr.append(M + rd * (m.length - lip / 2 + lip / 2 * math.cos(th)) + N * (lip / 2 * math.sin(th) * 0.8))
        rings.append(rr)
    for k in range(1, 6):  # recessed mouth: inner wall down the cuff
        t = 1 - (depth / L) * k / 5
        rings.append(ring(t, 1.0 - lip / max(min(mouth_r), 0.5) - 0.06 * k))
    verts = [tuple(v) for r in rings for v in r]
    m = len(rings)
    faces = []
    for i in range(m - 1):
        for k in range(n):
            a0, a1 = i * n + k, i * n + (k + 1) % n
            faces.append((a0, a1, a1 + n, a0 + n))
    c0 = len(verts)
    verts.append(tuple(B - ax * base))
    faces += [((k + 1) % n, k, c0) for k in range(n)]  # wrist cap
    c1 = len(verts)
    verts.append(tuple(B + (M - B) * (1 - depth / L)))
    faces += [((m - 1) * n + k, (m - 1) * n + (k + 1) % n, c1) for k in range(n)]  # mouth floor
    ob = mesh_object(name, verts, faces)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(50))
    return ob


def _bevel_apply(ob, width_mm: float, segments: int):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if width_mm > 0.01:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = sb.m(width_mm)
        mod.segments = segments
        mod.limit_method = "NONE"
        bpy.ops.object.modifier_apply(modifier="bevel")
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))


def build_part(prefix: str, pname: str, part: dict):
    """All geometry of one mold part (one material): metaball elements as one smooth mesh, plus any
    hard-surface rounded boxes and cones as separate meshes (joined later)."""
    out = []
    balls, caps = _elements(part)
    negs = {n: (tuple(e["centre"]), tuple(e["semi_axes"]), tuple(e.get("rot_deg", (0, 0, 0)))) for n, e in part.get("negative_ellipsoids", {}).items()}
    # metaball rounded boxes (blend with the other elements): centre, half_size, XYZ rot_deg, edge round
    mbox = {n: (tuple(e["centre"]), tuple(e["half_size"]), tuple(e.get("rot_deg", (0, 0, 0))), e.get("round", 1.0)) for n, e in part.get("mboxes", {}).items()}
    if balls or caps or mbox:
        out.append(metaball_part(f"{prefix}_{pname}", balls, caps, mbox, res_mm=part.get("res", 0.3), negs=negs))
    for n, e in part.get("rboxes", {}).items():
        out.append(rbox(f"{prefix}_{pname}_{n}", e["centre"], e["half_size"], e.get("rot_deg", (0, 0, 0)), e.get("bevel", 0.5)))
    for n, e in part.get("tori", {}).items():
        out.append(torus(f"{prefix}_{pname}_{n}", e["centre"], e["axis"], e["R"], e["r"], tuple(e.get("scale_r", (1.0, 1.0))), r_axial=e.get("r_axial")))
    for n, e in part.get("cuffs", {}).items():
        out.append(cuff(f"{prefix}_{pname}_{n}", e["a"], e["b"], e["r_a"], e["r_b"], tuple(e.get("oval", (1, 1))), tuple(e.get("up", (0, 0, 1))),
                        e.get("lip", 0.45), e.get("depth", 0.35), e.get("cut_deg", 0.0)))
    for n, e in part.get("lofts", {}).items():
        out.append(loft_cuff(f"{prefix}_{pname}_{n}", e["mouth_c"], e["mouth_n"], e["mouth_long"], e["mouth_r"], e["wrist_c"], e["wrist_r"],
                             e.get("lip", 0.5), e.get("depth", 1.2), e.get("flare", 1.4), e.get("base", 0.0)))
    for n, e in part.get("cones", {}).items():
        out.append(cone(f"{prefix}_{pname}_{n}", e["a"], e["b"], e["r_a"], e["r_b"], e.get("bevel", 0.3)))
    for o in out:
        o["material_key"] = part["material"]
    return out


# ---------------------------------------------------------------------------------------------------
def metaball_part(name: str, balls: dict, capsules: dict, cubes: dict | None = None, res_mm: float = 0.3, negs: dict | None = None):
    """Smooth part (metres) from ellipsoids, capsules and rounded boxes (mm), cf. sb.metaball_mesh."""
    mb = bpy.data.metaballs.new(name + "Meta")
    mb.resolution = mb.render_resolution = res_mm
    mb.threshold = 0.6
    ob = bpy.data.objects.new(name + "Meta", mb)
    bpy.context.scene.collection.objects.link(ob)
    for c, r, *rot in balls.values():
        e = mb.elements.new(type="ELLIPSOID")
        e.co, e.radius, e.stiffness = c, 1.0, 2.0
        e.size_x, e.size_y, e.size_z = [v / sb.METABALL_SURFACE for v in r]
        if rot and any(rot[0]):
            e.rotation = _euler_q(rot[0])
    for a, b, r in capsules.values():
        va, vb = Vector(a), Vector(b)
        d = vb - va
        e = mb.elements.new(type="CAPSULE")
        e.co, e.radius, e.stiffness = (va + vb) / 2, r / sb.METABALL_SURFACE, 2.0
        e.size_x = d.length / 2
        e.rotation = Vector((1, 0, 0)).rotation_difference(d.normalized())
    for c, r, *rot in (negs or {}).values():  # carving elements (eye hollows, glove pocket)
        e = mb.elements.new(type="ELLIPSOID")
        e.co, e.radius, e.stiffness = c, 1.0, 2.0
        e.size_x, e.size_y, e.size_z = [v / sb.METABALL_SURFACE for v in r]
        e.use_negative = True
        if rot and any(rot[0]):
            e.rotation = _euler_q(rot[0])
    for c, half, rot, *rnd in (cubes or {}).values():
        # Rounded box: CUBE element with a small radius; its surface ~ half + 0.575 * radius.
        rr = rnd[0] if rnd else 1.2
        e = mb.elements.new(type="CUBE")
        e.co, e.radius, e.stiffness = c, rr / sb.METABALL_SURFACE, 2.0
        e.size_x, e.size_y, e.size_z = [max(h - rr, 0.05) for h in half]
        e.rotation = _euler_q(rot) if isinstance(rot, (tuple, list)) else Matrix.Rotation(math.radians(rot), 4, "Z").to_quaternion()
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


def apply_paint(ob, mold: dict, slot_name) -> int:
    """Two-colour moulding detail painted on the joined mesh (before scaling, mold units): faces of material
    `from` whose centre, seen from `origin`, falls inside an (azimuth, elevation) polygon in degrees get
    material `to` (e.g. the skin seen through the gaps between a goalie's mask and its back plate).
    Faces crossed by a region boundary are first subdivided `refine` times (default 3), so the colour edge
    follows the polygon instead of stepping along the mesh faces. slot_name(key) -> material name of that
    key on `ob`. Returns the number of repainted faces."""
    from shapely.geometry import Point, Polygon
    from shapely.prepared import prep
    names = [m.name for m in ob.data.materials]
    n = 0
    for reg in mold.get("paint", []):
        src, dst = names.index(slot_name(reg["from"])), names.index(slot_name(reg["to"]))
        o = Vector(reg["origin"])
        polys = [prep(Polygon(poly)) for poly in reg["polygons_az_el_deg"]]

        def inside(co):
            d = co * 1000.0 - o
            az = math.degrees(math.atan2(d.y, d.x))
            el = math.degrees(math.atan2(d.z, math.hypot(d.x, d.y)))
            return any(pp.contains(Point(az, el)) for pp in polys)

        levels = reg.get("refine", 3)
        if levels:
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            for _ in range(levels):
                flag = {}
                edges = set()
                for f in bm.faces:
                    if f.material_index != src:
                        continue
                    fl = [flag.setdefault(v.index, inside(v.co)) for v in f.verts]
                    if any(fl) and not all(fl):
                        edges.update(f.edges)
                if not edges:
                    break
                bmesh.ops.subdivide_edges(bm, edges=list(edges), cuts=1, use_grid_fill=True)
                bm.verts.index_update()
            bm.to_mesh(ob.data)
            bm.free()
        for f in ob.data.polygons:
            if f.material_index == src and inside(f.center):
                f.material_index = dst
                n += 1
    return n


def tag(ob, key: str):
    ob["material_key"] = key
    return ob


def build_skater(mold: dict | None = None):
    """Skater mold parts (see data/figure-molds.json 'skater')."""
    m = (mold or load_molds())["skater"]
    parts = [o for n, p in m["parts"].items() for o in build_part("sk", n, p)]
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
    parts = [o for n, p in m["parts"].items() for o in build_part("go", n, p)]
    by_mat = {}
    for n, bx in m["boxes"].items():
        by_mat.setdefault(bx["material"], {})[n] = (tuple(bx["centre"]), tuple(bx["half_size"]), bx["rot_z_deg"], bx.get("round", 1.2))
    for k, cubes in by_mat.items():
        parts.append(tag(metaball_part(f"go_boxes_{k}", {}, {}, cubes), k))
    parts.append(tag(socket("go_socket", m["socket"]), BLUE))
    s = m["stick"]
    parts.append(tag(box_between("go_paddle", s["paddle"][0], s["paddle"][1], s["paddle_w"], s["paddle_t"]), TAN))
    parts.append(tag(blade("go_blade", s["blade"][0], s["blade"][1], s["blade_h"], s["blade_t"]), TAN))
    return parts
