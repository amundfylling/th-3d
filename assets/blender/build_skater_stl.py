"""PROPOSED skater assets from the Thingiverse STL body (data/figures/skater-stl.json, scripts/stl-skater.py), beside the
parametric skater: Sweden and Finland kits, back-print decals, checks and review renders.

    /root/venvs/blender/bin/python assets/blender/build_skater_stl.py
Body: the STL (thing:6898521, MAVRIS, CC BY-SA) once midpoint-subdivided, coloured per triangle from the user's
turntable frames (data/figures/skater-stl-paint.json). Wire stick, blade and right-skate runner from the spec. Scale k
from the overhead fit of the STL body. Same frame and conventions as build_figures.py (origin = fixture axis at the
socket underside, +x facing, +y the figure's left; one rigid mesh object per asset, no armature). The mount socket's key
bore is not modelled on this body (hidden underside).
Outputs: assets/figures/skater_stl_{SWE,FIN}.blend|.glb, validation/players/stl/figures-report.json,
validation/players/stl/figures-views.png (parametric | STL rows), validation/players/stl/figures-vs-photos.png.
The parametric assets, contact data and traces are not touched.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402
import figure_molds as fm  # noqa: E402
import stiga_blender as sb  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from PIL import Image  # noqa: E402

import bpy  # noqa: E402

REPO = sb.REPO
_spec = importlib.util.spec_from_file_location("stl_skater", REPO / "scripts" / "stl-skater.py")
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)

SPEC = ss.load_spec()
K = SPEC["scale"]["k_mm_per_mold_unit"]
VAL = REPO / "validation" / "players" / "stl"
VIEWS = REPO / "out" / "figures" / "views-stl"
REGION = {0: fm.KIT, 1: fm.BLUE, 2: fm.SKIN}


def build(team):
    """Joined, scaled rigid skater (metres) with the team's materials."""
    v, t = ss.load_stl()
    V, T = ss.subdivide(ss.to_mold(v, SPEC), t)
    lab = ss.paint_labels()
    assert len(lab) == len(T), "paint labels do not match the subdivided STL; rerun scripts/stl-skater.py paint"
    mats = bf.team_materials(team)
    body = fm.mesh_object("stl_body", V, [tuple(int(i) for i in f) for f in T])
    order = [fm.KIT, fm.BLUE, fm.SKIN, fm.METAL]
    for k in order:
        body.data.materials.append(mats[k])
    body.data.polygons.foreach_set("material_index", np.array([order.index(REGION[int(x)]) for x in lab], np.int32))
    s, r = SPEC["stick"], SPEC["runner"]
    parts = [fm.tube("stl_shaft", s["shaft"], s["shaft_r"]), fm.blade("stl_blade", s["blade"][0], s["blade"][1], s["blade_h"], s["blade_t"]),
             fm.blade("stl_runner", r["a"], r["b"], r["height"], r["thickness"])]
    for p in parts:
        p.data.materials.clear()
        p.data.materials.append(mats[fm.METAL])
    bpy.ops.object.select_all(action="DESELECT")
    for p in [body] + parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    for vv in ob.data.vertices:
        vv.co = vv.co * K
    bpy.ops.object.shade_smooth()
    ob.data.update()
    name = f"Skater.{team}"
    ob.name = ob.data.name = name
    ob["mold"] = "mold.skater"
    ob["mesh_source"] = SPEC["source"]["attribution"] + " (CC BY-SA)"
    ob["team_kit"] = team
    return ob


def measure(ob):
    me = ob.data
    V = np.array([v.co[:] for v in me.vertices]) * 1000
    s = SPEC["stick"]
    blade = np.array(s["blade"], float) * K
    disc = V[(V[:, 2] < 0.05) & (np.hypot(V[:, 0], V[:, 1]) < 10)]  # base underside (not the blade or runner)
    return {
        "height_mm": round(float(V[:, 2].max()), 2), "zmin_mm": round(float(V[:, 2].min()), 3),
        "footprint_x_mm": [round(float(V[:, 0].min()), 1), round(float(V[:, 0].max()), 1)],
        "footprint_y_mm": [round(float(V[:, 1].min()), 1), round(float(V[:, 1].max()), 1)],
        "socket_bottom_diameter_mm": round(float(2 * np.hypot(disc[:, 0], disc[:, 1]).max()), 2),
        "blade_heel_mm": [round(float(c), 2) for c in blade[0]], "blade_toe_mm": [round(float(c), 2) for c in blade[1]],
        "blade_length_mm": round(float(np.linalg.norm(blade[1] - blade[0])), 2), "blade_height_mm": round(s["blade_h"] * K, 2),
        "stick_side": "left (+y)" if blade[1][1] > 0 else "right (-y)",
        "triangles": sum(len(p.vertices) - 2 for p in me.polygons),
    }


def ortho_views(prefix, c):
    sb.set_world(0.55)
    sb.add_sun(3.0, (40, 10, 35))
    out = []
    views = {"front": (90, 0, 90), "left": (90, 0, 180), "back": (90, 0, -90), "right": (90, 0, 0), "top": (0, 0, -90)}
    for vn, rot in views.items():
        e = [math.radians(a) for a in rot]
        d = Matrix.Rotation(e[2], 3, "Z") @ Matrix.Rotation(e[0], 3, "X") @ Vector((0, 0, 1))
        cam = sb.ortho_camera(f"V_{vn}", tuple(c + d * 0.3), rot, 0.08)
        p = VIEWS / f"{prefix}_{vn}.png"
        sb.render(cam, p, (420, 420), 32)
        out.append(p)
    return out


def main():
    VAL.mkdir(parents=True, exist_ok=True)
    bf.KS["skater"] = K  # decals and fitted cameras at this asset's scale
    report = {"status": "PROPOSED (beside the parametric skater; contacts, footprints and traces unchanged)",
              "scale_k_mm_per_mold_unit": K, "scale_source": SPEC["scale"]["source"], "mesh_source": SPEC["source"], "assets": {}}
    c = Vector((0.004, 0.008, 0.029))
    rows = {}
    for team in ("SWE", "FIN"):
        sb.reset_scene()
        ob = build(team)
        dec, nfaces = bf.decal(ob, "skater", team, bf.ASSET_NUMBERS[("skater", team)], f"Print.skater.{team}")
        rep = measure(ob)
        rep["decal_faces"] = nfaces
        rep["number_on_asset_decal"] = bf.ASSET_NUMBERS[("skater", team)] or None
        report["assets"][f"skater_stl_{team}"] = rep
        sb.save_blend(bf.OUT / f"skater_stl_{team}.blend")
        sb.export_glb(bf.OUT / f"skater_stl_{team}.glb", [ob, dec])
        rows[f"stl_{team}"] = ortho_views(f"stl_{team}", c)
        if team == "SWE":
            for vid in ("skater-video-t00.00", "skater-video-t07.25", "skater-video-t04.50", "skater-video-t03.00", "skater-video-t10.75", "skater-video-t13.25"):
                cam, (cw, ch) = bf.cam_from_fit(vid, "skater", VAL / "skater-fit.json")
                s = 520 / max(cw, ch)
                sb.render(cam, VIEWS / f"match_{vid}.png", (round(cw * s), round(ch * s)), 48)
    # the parametric Sweden skater at its own scale, same cameras (for the comparison rows)
    sb.reset_scene()
    bpy.ops.import_scene.gltf(filepath=str(bf.OUT / "skater_SWE.glb"))
    rows["parametric_SWE"] = ortho_views("parametric_SWE", c)
    (VAL / "figures-report.json").write_text(json.dumps(report, indent=2) + "\n")
    order = ["parametric_SWE", "stl_SWE", "stl_FIN"]
    sheet = Image.new("RGB", (5 * 420, len(order) * 420), "white")
    for r_, key in enumerate(order):
        for ci, p in enumerate(rows[key]):
            sheet.paste(Image.open(p).convert("RGB"), (ci * 420, r_ * 420))
    sheet.save(VAL / "figures-views.png")
    man = json.loads((REPO / "references" / "derived" / "players" / "manifest.json").read_text())["items"]
    pairs = []
    for vid in ("skater-video-t00.00", "skater-video-t07.25", "skater-video-t04.50", "skater-video-t03.00", "skater-video-t10.75", "skater-video-t13.25"):
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
