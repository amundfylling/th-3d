"""Rigid STIGA figure assets from the fitted molds (data/figure-molds.json): skater and goalie, Sweden and
Finland kits, back-print decals, checks and camera-matched review renders.

    /root/venvs/blender/bin/python assets/blender/build_figures.py
Scale: mold units x k (validation/players/overhead-fit.json, skater fit on the official overhead at the
ASSUMED preview scale) -> mm; one k for both molds (Finland team pack: goalie and skaters stand equally tall;
the goalie-only overhead fit disagrees, see docs/players.md). Origin = mounting axis at the socket underside;
+x = facing, +y = the figure's left; one rigid mesh object per asset, no armature.
Outputs: assets/figures/{skater,goalie}_{SWE,FIN}.blend|.glb, assets/figures/textures/print_*.png,
validation/players/figures-report.json, validation/players/figures-views.png, validation/players/figures-vs-photos.png.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402
import figure_molds as fm  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import bmesh  # noqa: E402
import bpy  # noqa: E402

REPO = sb.REPO
OUT = REPO / "assets" / "figures"
TEX = OUT / "textures"
VAL = REPO / "validation" / "players"
VIEWS = REPO / "out" / "figures" / "views"  # per-view renders (sheets go to validation/players)
SAMPLES = json.loads((REPO / "validation" / "18-colour-samples.json").read_text())
FIT = json.loads((VAL / "overhead-fit.json").read_text())
MOLDS = fm.load_molds()
# Scale (mm per mold unit) per mold. Skater: fitted on the official overhead (ASSUMED preview scale). Goalie:
# from the user's measured height (data/figure-molds.json measurements; set by calibrate_goalie()).
KS = {"skater": FIT["scale_k_mm_per_mold_unit"], "goalie": FIT["scale_k_mm_per_mold_unit"]}
if MOLDS["goalie"].get("scale"):  # measured goalie scale (calibrate_goalie, data/figure-molds.json)
    KS["goalie"] = MOLDS["goalie"]["scale"]["k_mm_per_mold_unit"]
K = KS["skater"]
TEAMS = {"SWE": {"kit": "sweden_yellow", "name": "SVERIGE", "ink": (24, 22, 20), "outline": (40, 32, 18)},
         "FIN": {"kit": "goalie_white", "name": "FINLAND", "ink": (28, 88, 160), "outline": (28, 88, 160)}}
# Colours (sRGB) from the official overhead (validation/18-colour-samples.json). One blue for both teams: the
# median blue of all Finland and all Sweden figures agrees within 3 levels (docs/players.md).
COMMON = {fm.BLUE: "finland_blue", fm.SKIN: "skin", fm.METAL: "stick_metal", fm.TAN: "goalie_tan"}
# Numbers on the asset files' own decals: the user's Sweden skater no. 21 and goalie no. 30; Finland: the
# reference variant's W-RD no. 4 and an unseen goalie number (blank). Per-player numbers: build_assembly.py.
ASSET_NUMBERS = {("skater", "SWE"): "21", ("goalie", "SWE"): "30", ("skater", "FIN"): "4", ("goalie", "FIN"): ""}
# Back-print projector per mold (mold units): centre on the jersey back, direction (back -> front), size.
PRINT = {"skater": {"centre": (-6.4, -4.0, 31.6), "dir": (0.93, 0.0, -0.36), "size": (15.0, 13.0), "up": (0.36, 0.0, 0.93)},
         "goalie": {"centre": (-6.4, 5.0, 28.0), "dir": (1.0, 0.0, -0.12), "size": (16.0, 14.0), "up": (0.12, 0.0, 1.0)}}


def lin(srgb):
    c = np.asarray(srgb, float) / 255
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))


def material(name, srgb, rough=0.32, metallic=0.0, coat=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*lin(srgb), 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    return m


def team_materials(team):
    A = MOLDS["albedo_srgb"]  # data/figure-molds.json: calibrated plastic albedo
    return {fm.KIT: material(f"fig_kit_{team}", A[f"kit_{team}"], 0.32, coat=0.25),
            fm.BLUE: material("fig_blue", A["blue"], 0.3, coat=0.25),
            fm.SKIN: material("fig_skin", A["skin"], 0.42),
            fm.METAL: material("fig_stick_metal", A["stick_metal"], 0.3, metallic=1.0),
            fm.TAN: material("fig_stick_tan", A["stick_tan"], 0.4),
            fm.DARK: material("fig_recess", A["recess"], 0.6)}


def build_mold(kind, scale=True):
    """Joined, scaled rigid mesh (metres) with material slots keyed by the parts' material keys.
    scale=False keeps mold units (x 0.001) - used to measure the mold before calibration."""
    parts = fm.build_skater(MOLDS) if kind == "skater" else fm.build_goalie(MOLDS)
    keep_fine = {f"go_{n}" for r in MOLDS[kind].get("paint", []) for n in r.get("no_decimate", [])}
    for p in parts:
        if p.name in keep_fine:  # painted parts keep their full resolution (clean paint edges)
            continue
        if p.name.startswith(("sk_", "go_")) and len(p.data.vertices) > 3000:  # metaball parts only
            mod = p.modifiers.new("dec", "DECIMATE")
            mod.ratio = 0.3
            bpy.context.view_layer.objects.active = p
            bpy.ops.object.select_all(action="DESELECT")
            p.select_set(True)
            bpy.ops.object.modifier_apply(modifier="dec")
    keys = [fm.KIT, fm.BLUE, fm.SKIN, fm.METAL, fm.TAN, fm.DARK]
    slot = {k: bpy.data.materials.new(f"slot_{k}") for k in keys}
    for p in parts:
        p.data.materials.clear()
        p.data.materials.append(slot[p["material_key"]])
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    if MOLDS[kind].get("paint"):
        for k in keys:  # slots must exist on the joined mesh even if unused before painting
            if slot[k].name not in [m.name for m in ob.data.materials]:
                ob.data.materials.append(slot[k])
        fm.apply_paint(ob, MOLDS[kind], lambda k: f"slot_{k}")
    if scale:
        for v in ob.data.vertices:
            v.co = v.co * KS[kind]
    bpy.ops.object.shade_smooth()
    ob.data.update()
    return ob


def print_texture(kind, team, number):
    """RGBA back print: straight sans country name over collegiate block digits with gap + outline
    (assets/blender/print_glyphs.py; layout data/figure-molds.json print_layout)."""
    import print_glyphs as pg
    t = TEAMS[team]
    L = MOLDS["print_layout"][kind]
    size = PRINT[kind]["size"]
    im = pg.print_image(t["name"], number, t["ink"], t["outline"], size, L["digit_h"], L["name_cap"], L["name_y"],
                        L["name_y"] + L["name_cap"] + L["gap"], px_per_unit=72)
    TEX.mkdir(parents=True, exist_ok=True)
    p = TEX / f"print_{kind}_{team}_{number or 'blank'}.png"
    im.save(p)
    return p


def decal(fig, kind, team, number, name):
    """Thin decal shell over the jersey back: kit faces facing the projector, pushed out 0.04 mm, planar UVs."""
    pr = PRINT[kind]
    K = KS[kind]
    c = Vector(pr["centre"]) * K
    d = Vector(pr["dir"]).normalized()
    up = Vector(pr["up"])
    up = (up - d * up.dot(d)).normalized()
    right = d.cross(up).normalized()  # image u axis: the viewer's right when seen from behind (= figure's right)
    sw, sh = pr["size"][0] * K, pr["size"][1] * K
    me = fig.data
    kit_idx = [i for i, m in enumerate(me.materials) if m.name.startswith("fig_kit_")][0]
    bm = bmesh.new()
    bm.from_mesh(me)
    keep = []
    for f in bm.faces:
        if f.material_index != kit_idx or f.normal.dot(-d) < 0.25:
            continue
        p = f.calc_center_median() * 1000 - c
        u, v = p.dot(right), p.dot(up)
        if abs(u) <= sw / 2 and abs(v) <= sh / 2 and abs(p.dot(d)) < 8 * K:
            keep.append(f)
    out = bmesh.new()
    vmap = {}
    for f in keep:
        vs = []
        for v in f.verts:
            if v.index not in vmap:
                vmap[v.index] = out.verts.new(v.co + v.normal * 0.00004)
            vs.append(vmap[v.index])
        out.faces.new(vs)
    uvl = out.loops.layers.uv.new("UVMap")
    for f in out.faces:
        for lp in f.loops:
            p = lp.vert.co * 1000 - c
            lp[uvl].uv = (0.5 + p.dot(right) / sw, 0.5 + p.dot(up) / sh)
    dm = bpy.data.meshes.new(name)
    out.to_mesh(dm)
    bm.free()
    out.free()
    ob = bpy.data.objects.new(name, dm)
    bpy.context.scene.collection.objects.link(ob)
    tex = print_texture(kind, team, number)
    m = bpy.data.materials.new(f"print_{kind}_{team}_{number or 'blank'}")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.35
    tn = m.node_tree.nodes.new("ShaderNodeTexImage")
    tn.image = bpy.data.images.load(str(tex))
    tn.extension = "CLIP"
    m.node_tree.links.new(tn.outputs["Color"], b.inputs["Base Color"])
    m.node_tree.links.new(tn.outputs["Alpha"], b.inputs["Alpha"])
    m.blend_method = "BLEND" if hasattr(m, "blend_method") else m.blend_method
    m.surface_render_method = "BLENDED" if hasattr(m, "surface_render_method") else None
    dm.materials.append(m)
    ob.parent = fig
    return ob, len(keep)


def measure(ob, kind):
    me = ob.data
    V = np.array([v.co[:] for v in me.vertices]) * 1000
    mats = [m.name for m in me.materials]
    fi = np.array([p.material_index for p in me.polygons])
    tri = [list(p.vertices) for p in me.polygons]
    def verts_of(prefix):
        ids = sorted({i for p, mi in zip(tri, fi) if mats[mi].startswith(prefix) for i in p})
        return V[ids]
    stick = verts_of("fig_stick_")
    K = KS[kind]
    m = MOLDS[kind]
    s = m["stick"]
    blade = np.array(s["blade"], float) * K
    return {
        "height_mm": round(float(V[:, 2].max()), 2),
        "zmin_mm": round(float(V[:, 2].min()), 3),
        "footprint_x_mm": [round(float(V[:, 0].min()), 1), round(float(V[:, 0].max()), 1)],
        "footprint_y_mm": [round(float(V[:, 1].min()), 1), round(float(V[:, 1].max()), 1)],
        "socket_bottom_diameter_mm": round(2 * m["socket"]["r_bottom"] * K, 2),
        "socket_height_mm": round(m["socket"]["height"] * K, 2),
        "blade_heel_mm": [round(float(c), 2) for c in blade[0]],
        "blade_toe_mm": [round(float(c), 2) for c in blade[1]],
        "blade_length_mm": round(float(np.linalg.norm(blade[1] - blade[0])), 2),
        "blade_height_mm": round(s["blade_h"] * K, 2),
        "stick_zmin_mm": round(float(stick[:, 2].min()), 3),
        "stick_side": "left (+y)" if blade[1][1] > 0 else "right (-y)",
        "triangles": sum(len(p.vertices) - 2 for p in me.polygons),
    }


def cam_from_fit(view_id, kind, fit_json=None):
    """Blender camera reproducing a fitted photo camera (scripts/fit-figure-views.py) for the view's crop."""
    fitv = json.loads(Path(fit_json or VAL / f"{kind}-fit.json").read_text())["views"][view_id]
    man = json.loads((REPO / "references" / "derived" / "players" / "manifest.json").read_text())["items"][view_id]
    az, el, roll, pan, tilt, dist, f = fitv["params"]
    target = np.array({"skater": [2.0, 4.0, 24.0], "goalie": [2.0, 7.0, 24.0]}[kind])
    C = target + dist * np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    fwd = (target - C) / np.linalg.norm(target - C)
    r = np.cross(fwd, [0, 0, 1.0])
    r /= np.linalg.norm(r)
    u = np.cross(r, fwd)
    R = np.stack([r, -u, fwd])
    cr, sr = math.cos(roll), math.sin(roll)
    R = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]]) @ R
    cp, sp, ct, st = math.cos(pan), math.sin(pan), math.cos(tilt), math.sin(tilt)
    R = np.array([[1, 0, 0], [0, ct, -st], [0, st, ct]]) @ np.array([[cp, 0, -sp], [0, 1, 0], [sp, 0, cp]]) @ R
    x0, y0, x1, y1 = man["crop_box_px"]
    Wf, Hf = man["full_size_px"]
    cw, ch = x1 - x0, y1 - y0
    cam = bpy.data.cameras.new("Fit_" + view_id)
    cam.sensor_fit = "AUTO"
    cam.sensor_width = 36.0
    S = max(cw, ch)
    cam.lens = f * 36.0 / S
    cam.shift_x = ((x0 + cw / 2) - Wf / 2) / S
    cam.shift_y = -((y0 + ch / 2) - Hf / 2) / S
    cam.clip_start = 0.001
    ob = bpy.data.objects.new("Fit_" + view_id, cam)
    bpy.context.scene.collection.objects.link(ob)
    M3 = Matrix([list(R[0]), list(-R[1]), list(-R[2])]).transposed()
    ob.matrix_world = Matrix.Translation(Vector(C * KS[kind] / 1000)) @ M3.to_4x4()
    return ob, (cw, ch)


def calibrate_goalie():
    """Goalie scale and stick blade from the user's ruler measurements: k = measured height / mold height
    (mask top to socket underside); blade length (heel bend -> toe, lower edge) and plank height set in mold
    units from k; the paddle meets the blade top. Writes the stick back to data/figure-molds.json."""
    meas = MOLDS.get("measurements", {}).get("goalie")
    if not meas:
        return None
    sb.reset_scene()
    ob = build_mold("goalie", scale=False)
    zs = [v.co.z * 1000 for v in ob.data.vertices]
    h = max(zs) - min(zs)
    k = meas["height_mm"] / h
    st = MOLDS["goalie"]["stick"]
    heel = st["blade"][0]
    st["blade"] = [heel, [heel[0], round(heel[1] + meas["blade_length_mm"] / k, 3)]]
    st["blade_h"] = round(meas["blade_height_mm"] / k, 3)
    pa = st["paddle"]
    pa[1] = [pa[1][0], round(heel[1] + 1.2, 3), round(0.75 * st["blade_h"], 3)]
    MOLDS["goalie"]["stick"] = st
    MOLDS["goalie"]["scale"] = {"k_mm_per_mold_unit": round(k, 5), "mold_height_units": round(h, 3), "status": "measured",
                                "source_id": meas["source_id"], "note": "k = measured height / mold height; the blade is set from the measured length and height."}
    import json as _j
    data = _j.loads(fm.MOLDS_JSON.read_text())
    data["goalie"]["stick"], data["goalie"]["scale"] = st, MOLDS["goalie"]["scale"]
    fm.MOLDS_JSON.write_text(_j.dumps(data, indent=1) + "\n")
    KS["goalie"] = k
    return k


def main():
    VAL.mkdir(parents=True, exist_ok=True)
    kg = calibrate_goalie()
    report = {"scale_k_mm_per_mold_unit": K, "scale_source": "validation/players/overhead-fit.json (4 Sweden skaters, official overhead, ASSUMED preview scale)",
              "scales": dict(KS), "scale_sources": {"skater": "official overhead fit (ASSUMED preview scale), status traced",
                                                    "goalie": ("user ruler measurement: height 54 mm (data/figure-molds.json measurements), status measured" if kg else "shared skater scale")},
              "assets": {}}
    renders = []
    for kind in ("skater", "goalie"):
        for team in ("SWE", "FIN"):
            sb.reset_scene()
            ob = build_mold(kind)
            mats = team_materials(team)
            for i, m in enumerate(ob.data.materials):
                ob.data.materials[i] = mats[m.name.replace("slot_", "")]
            name = f"{kind.capitalize()}.{team}"
            ob.name = ob.data.name = name
            ob["mold"] = f"mold.{kind}"
            ob["team_kit"] = team
            dec, nfaces = decal(ob, kind, team, ASSET_NUMBERS[(kind, team)], f"Print.{kind}.{team}")
            rep = measure(ob, kind)
            rep["decal_faces"] = nfaces
            rep["number_on_asset_decal"] = ASSET_NUMBERS[(kind, team)] or None
            report["assets"][f"{kind}_{team}"] = rep
            sb.save_blend(OUT / f"{kind}_{team}.blend")
            sb.export_glb(OUT / f"{kind}_{team}.glb", [ob, dec])
            # review renders: five orthographic views
            sb.set_world(0.55)
            sb.add_sun(3.0, (40, 10, 35))
            views = {"front": (90, 0, 90), "left": (90, 0, 180), "back": (90, 0, -90), "right": (90, 0, 0), "top": (0, 0, -90)}
            c = Vector((0.004, 0.008 if kind == "skater" else 0.006, 0.026))
            for vn, rot in views.items():
                e = [math.radians(a) for a in rot]
                d = Matrix.Rotation(e[2], 3, "Z") @ Matrix.Rotation(e[0], 3, "X") @ Vector((0, 0, 1))
                cam = sb.ortho_camera(f"V_{vn}", tuple(c + d * 0.3), rot, 0.075)
                p = VIEWS / f"{kind}_{team}_{vn}.png"
                sb.render(cam, p, (420, 420), 32)
                renders.append(p)
            # camera-matched renders against the user's photos (Sweden only)
            if team == "SWE":
                for vid in {"skater": ["skater-video-t00.00", "skater-video-t07.25", "skater-video-t04.50"],
                            "goalie": ["goalie-photo-front", "goalie-photo-back", "goalie-photo-side"]}[kind]:
                    cam, (cw, ch) = cam_from_fit(vid, kind)
                    s = 520 / max(cw, ch)
                    sb.render(cam, VIEWS / f"match_{vid}.png", (round(cw * s), round(ch * s)), 48)
    (VAL / "figures-report.json").write_text(json.dumps(report, indent=2) + "\n")
    # sheets
    rows = []
    for kind in ("skater", "goalie"):
        for team in ("SWE", "FIN"):
            rows.append([Image.open(VIEWS / f"{kind}_{team}_{vn}.png").convert("RGB") for vn in ("front", "left", "back", "right", "top")])
    sheet = Image.new("RGB", (5 * 420, 4 * 420), "white")
    for r, row in enumerate(rows):
        for cidx, im in enumerate(row):
            sheet.paste(im, (cidx * 420, r * 420))
    sheet.save(VAL / "figures-views.png")
    pairs = []
    man = json.loads((REPO / "references" / "derived" / "players" / "manifest.json").read_text())["items"]
    for vid in ["skater-video-t00.00", "skater-video-t07.25", "skater-video-t04.50", "goalie-photo-front", "goalie-photo-back", "goalie-photo-side"]:
        ren = Image.open(VIEWS / f"match_{vid}.png").convert("RGB")
        ph = Image.open(REPO / man[vid]["file"]).convert("RGB").resize(ren.size)
        pairs.append((ph, ren))
    W = max(p.width + r.width for p, r in pairs)
    H = max(p.height for p, r in pairs)
    sheet = Image.new("RGB", (W * 3, H * 2), "white")
    for i, (p, r) in enumerate(pairs):
        x, y = (i % 3) * W, (i // 3) * H
        sheet.paste(p, (x, y))
        sheet.paste(r, (x + p.width, y))
    sheet.save(VAL / "figures-vs-photos.png")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
