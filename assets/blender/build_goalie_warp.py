"""PROPOSED goalie assets: the parametric goalie mold bent toward the user's photo silhouettes
(data/figures/goalie-warp.json, scripts/goalie-silhouette-warp.py, docs/goalie-warp.md), beside the current goalie.

    /root/venvs/blender/bin/python assets/blender/build_goalie_warp.py
Same parts, paint, back print, scale k (measured 54 mm height) and frame as build_figures.py (origin = fixture axis at the
socket underside, +x facing, +y the figure's left; one rigid mesh object per asset, no armature). Only the vertex
positions change: x -> x + u(x) in mold units before scaling; the tan stick moves rigidly.
Outputs: assets/figures/goalie_warp_{SWE,FIN}.blend|.glb, validation/players/warp/figures-report.json,
validation/players/warp/figures-views.png (rows: current Sweden, warped Sweden, warped Finland),
validation/players/warp/figures-vs-photos.png (photo | current | warped at each shape's own fitted camera).
The current goalie assets, contact data and traces are not touched.
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
from PIL import Image, ImageDraw  # noqa: E402

import bpy  # noqa: E402

REPO = sb.REPO
_spec = importlib.util.spec_from_file_location("goalie_warp", REPO / "scripts" / "goalie-silhouette-warp.py")
gw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gw)

K = bf.KS["goalie"]
VAL = REPO / "validation" / "players" / "warp"
VIEWS = REPO / "out" / "figures" / "views-warp"
MATCH = ["goalie-photo-front", "goalie-photo-front-oblique", "goalie-photo-side", "goalie-photo-back", "goalie-video-t05.00",
         "goalie-video-t12.25"]


def build(team, warped=True):
    """Joined, scaled rigid goalie (metres) with the team's materials; warped or as the current mold."""
    ob = bf.build_mold("goalie", scale=False)
    me = ob.data
    if warped:
        v0 = np.array([v.co[:] for v in me.vertices]) * 1000.0
        tan_slot = [i for i, m in enumerate(me.materials) if m.name == f"slot_{fm.TAN}"][0]
        tan = np.unique([i for p in me.polygons if p.material_index == tan_slot for i in p.vertices])
        v = gw.warp_vertices(v0, rigid=[tan])
        me.vertices.foreach_set("co", (v / 1000.0).ravel())
    for v_ in me.vertices:
        v_.co = v_.co * K
    me.update()
    mats = bf.team_materials(team)
    for i, m in enumerate(me.materials):
        me.materials[i] = mats[m.name.replace("slot_", "")]
    ob.name = me.name = f"Goalie.{team}"
    ob["mold"] = "mold.goalie"
    ob["team_kit"] = team
    if warped:
        ob["shape_warp"] = "data/figures/goalie-warp.json"
    return ob


def measure(ob):
    me = ob.data
    V = np.array([v.co[:] for v in me.vertices]) * 1000
    tan_slot = [i for i, m in enumerate(me.materials) if m.name.startswith("fig_stick_tan")]
    ids = np.unique([i for p in me.polygons if p.material_index in tan_slot for i in p.vertices])
    T = V[ids]
    blade = T[T[:, 2] < 5.6]
    d = blade[:, :2] - blade[:, :2].mean(0)
    ax = np.linalg.svd(d, full_matrices=False)[2][0]
    t = d @ ax
    r = np.hypot(V[:, 0], V[:, 1])
    disc = V[(V[:, 2] < 0.05) & (r < 9)]
    return {
        "height_mm": round(float(V[:, 2].max()), 2), "zmin_mm": round(float(V[:, 2].min()), 3),
        "footprint_x_mm": [round(float(V[:, 0].min()), 1), round(float(V[:, 0].max()), 1)],
        "footprint_y_mm": [round(float(V[:, 1].min()), 1), round(float(V[:, 1].max()), 1)],
        "socket_bottom_diameter_mm": round(float(2 * np.hypot(disc[:, 0], disc[:, 1]).max()), 2),
        "stick_zmin_mm": round(float(T[:, 2].min()), 3),
        "stick_y_extent_mm": [round(float(T[:, 1].min()), 2), round(float(T[:, 1].max()), 2)],
        "stick_low_part_extent_along_blade_mm": round(float(t.max() - t.min()), 2),
        "blade_toe_xy_mm": [round(float(c), 2) for c in blade[np.argmax(blade[:, 1]), :2]],
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
        cam = sb.ortho_camera(f"V_{vn}", tuple(c + d * 0.3), rot, 0.075)
        p = VIEWS / f"{prefix}_{vn}.png"
        sb.render(cam, p, (420, 420), 32)
        out.append(p)
    return out


def matched(prefix, fit_json):
    for vid in MATCH:
        cam, (cw, ch) = bf.cam_from_fit(vid, "goalie", fit_json)
        s = 620 / max(cw, ch)
        sb.render(cam, VIEWS / f"{prefix}_{vid}.png", (round(cw * s), round(ch * s)), 64)


def main():
    VAL.mkdir(parents=True, exist_ok=True)
    VIEWS.mkdir(parents=True, exist_ok=True)
    spec = json.loads(gw.SPEC.read_text())
    report = {"status": "PROPOSED (beside the current goalie; contacts, footprints and traces unchanged)",
              "scale_k_mm_per_mold_unit": K, "warp": {k: spec[k] for k in ("description", "fixed", "settings", "fit_views", "result")},
              "assets": {}}
    c = Vector((0.004, 0.006, 0.026))
    rows = {}
    for team in ("SWE", "FIN"):
        sb.reset_scene()
        ob = build(team)
        dec, nfaces = bf.decal(ob, "goalie", team, bf.ASSET_NUMBERS[("goalie", team)], f"Print.goalie.{team}")
        rep = measure(ob)
        rep["decal_faces"] = nfaces
        report["assets"][f"goalie_warp_{team}"] = rep
        sb.save_blend(bf.OUT / f"goalie_warp_{team}.blend")
        sb.export_glb(bf.OUT / f"goalie_warp_{team}.glb", [ob, dec])
        rows[f"warp_{team}"] = ortho_views(f"warp_{team}", c)
        if team == "SWE":
            matched("warp", VAL / "goalie-fit.json")
    sb.reset_scene()
    ob = build("SWE", warped=False)
    bf.decal(ob, "goalie", "SWE", bf.ASSET_NUMBERS[("goalie", "SWE")], "Print.goalie.SWE")
    rep = measure(ob)
    report["current_goalie_same_measures"] = rep
    rows["current_SWE"] = ortho_views("current_SWE", c)
    matched("current", VAL / "base" / "goalie-fit.json")
    (VAL / "figures-report.json").write_text(json.dumps(report, indent=2) + "\n")
    order = ["current_SWE", "warp_SWE", "warp_FIN"]
    sheet = Image.new("RGB", (5 * 420, len(order) * 420), "white")
    for r_, key in enumerate(order):
        for ci, p in enumerate(rows[key]):
            sheet.paste(Image.open(p).convert("RGB"), (ci * 420, r_ * 420))
        ImageDraw.Draw(sheet).text((8, r_ * 420 + 6), key.replace("_", " "), fill=(0, 0, 0))
    sheet.save(VAL / "figures-views.png")
    man = json.loads((REPO / "references" / "derived" / "players" / "manifest.json").read_text())["items"]
    trip = []
    for vid in MATCH:
        cur = Image.open(VIEWS / f"current_{vid}.png").convert("RGB")
        new = Image.open(VIEWS / f"warp_{vid}.png").convert("RGB")
        ph = Image.open(REPO / man[vid]["file"]).convert("RGB").resize(new.size)
        trip.append((ph, cur.resize(new.size), new))
    W = max(3 * t[0].width for t in trip)
    H = max(t[0].height for t in trip) + 22
    sheet = Image.new("RGB", (W * 2, H * math.ceil(len(trip) / 2)), "white")
    dr = ImageDraw.Draw(sheet)
    for i, t in enumerate(trip):
        x, y = (i % 2) * W, (i // 2) * H
        for j, (im, lab) in enumerate(zip(t, ("photo", "current model", "new (warped) model"))):
            sheet.paste(im, (x + j * im.width, y + 22))
            dr.text((x + j * im.width + 6, y + 5), f"{lab}  {MATCH[i] if j == 0 else ''}", fill=(0, 0, 0))
    sheet.save(VAL / "figures-vs-photos.png")
    print(json.dumps(report["assets"], indent=1))


if __name__ == "__main__":
    main()
