"""Iteration 11: static rink asset (ice with traced slots and goal cut-outs, inner boards, outer housing).

Run headless (docs/blender.md):
    /root/venvs/blender/bin/python assets/blender/build_rink.py
Outputs: assets/rink/rink.blend, assets/rink/rink.glb, validation/11-rink-overhead.png,
validation/11-rink-side.png, validation/11-rink-report.json. Neutral clay only; no goals, figures,
puck, graphics or animation.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402

import bpy  # noqa: E402

g = sb.load_geometry()
OUT = sb.REPO / "assets" / "rink"
VAL = sb.REPO / "validation"
board_h = sb.preview(g, "board_height_above_ice")
board_t = sb.preview(g, "board_wall_thickness")
ice_t = sb.preview(g, "ice_sheet_thickness")
housing_margin = sb.preview(g, "housing_margin_outside_ice")
housing_depth = sb.preview(g, "housing_depth_below_ice")

boundary = Polygon(g["board"]["inner_boundary"]["world"]["points_mm"])
assert boundary.is_valid, "inner boundary polygon invalid"
mmpp = sb.mm_per_px(g)

# Slots: visible slot centrelines (world mm, preview scale) buffered by their traced widths.
slots = []
widths = {}
for f in g["fixture_paths"]:
    tr = next(t for t in g["image_traces"] if t["id"] == f"trace.slot.{f['player_id']}.overhead")
    w = tr["stats"]["width_median_px"] * mmpp
    widths[f["player_id"]] = round(w, 2)
    slots.append(sb.slot_polygon(f["centreline"]["points_mm"], w))
# Goal cut-outs: bare-sheet outlines mapped into the overhead, then to world.
cutouts = [Polygon(sb.px_to_world(g, "map.overhead.preview", next(t for t in g["image_traces"] if t["id"] == f"trace.goal.{team}.cutout.overhead")["points_px"])) for team in ("W", "E")]
holes = sb.union(slots + cutouts)
ice_shape = boundary.difference(holes)

sb.reset_scene()
sb.set_world(0.4)
mat_ice = sb.clay("clay_ice", (0.82, 0.83, 0.85), 0.45)
mat_board = sb.clay("clay_boards", (0.45, 0.45, 0.47), 0.6)
mat_housing = sb.clay("clay_housing", (0.12, 0.12, 0.13), 0.55)

ice = sb.extrude("Ice", ice_shape, -ice_t, 0.0, mat_ice)
boards = sb.extrude("InnerBoards", boundary.buffer(board_t, join_style="round", quad_segs=16).difference(boundary), -ice_t, board_h, mat_board)
outer = boundary.buffer(housing_margin, join_style="round", quad_segs=16)
housing_base = sb.extrude("HousingBase", outer, -housing_depth, -ice_t, mat_housing)
housing_rim = sb.extrude("HousingRim", outer.difference(boundary.buffer(board_t, join_style="round", quad_segs=16)), -ice_t, 0.0, mat_housing)
objects = [ice, boards, housing_base, housing_rim]

# Cameras and lights for review stills.
minx, miny, maxx, maxy = outer.bounds
cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
span_x = (maxx - minx) * 1.04
res_over = (1800, 1000)
over_cam = sb.ortho_camera("OverheadOrtho", (sb.m(cx), sb.m(cy), 2.0), (0, 0, 0), sb.m(span_x))
side_cam = sb.persp_camera("SideOblique", (sb.m(cx), sb.m(cy) - 1.35, 0.42), (sb.m(cx), sb.m(cy), 0.0), 50)
sb.add_sun(3.0, (40, 0, 25))

sb.save_blend(OUT / "rink.blend")
sb.export_glb(OUT / "rink.glb", objects)
sb.render(over_cam, VAL / "11-rink-overhead.png", res_over, 32)
sb.render(side_cam, VAL / "11-rink-side.png", (1600, 900), 32)

# Unlit ID render for measurement (flat emission colours, no lights, no shadows): the lit still is for
# looking at; measuring extents on it is invalid because the boards shade the ice edge.
for obj, rgb in ((ice, (1, 1, 1)), (boards, (1, 0, 0)), (housing_base, (0, 0, 1)), (housing_rim, (0, 0, 1))):
    mat = bpy.data.materials.new(f"id_{obj.name}")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*rgb, 1)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
bpy.data.objects["Sun"].hide_render = True
sb.set_world(0.0)
sb.render(over_cam, VAL / "11-rink-overhead-id.png", res_over, 1)

report = {
    "blender": bpy.app.version_string,
    "command": "/root/venvs/blender/bin/python assets/blender/build_rink.py",
    "preview_parameters_mm": {"board_height": board_h, "board_wall_thickness": board_t, "ice_sheet_thickness": ice_t, "housing_margin": housing_margin, "housing_depth_below_ice": housing_depth},
    "slot_widths_mm_preview": widths,
    "ice_bounds_mm": [round(v, 2) for v in boundary.bounds],
    "housing_bounds_mm": [round(v, 2) for v in outer.bounds],
    "implied_housing_length_mm": round(maxx - minx, 1),
    "implied_housing_width_mm": round(maxy - miny, 1),
    "catalog_overall_claims_mm": {"stiga_sports": [960, 500], "stiga_canada": [940, 502]},
    "overhead_render": {"resolution": res_over, "ortho_scale_m": sb.m(span_x), "mm_per_px": round(span_x / res_over[0], 5), "centre_mm": [round(cx, 3), round(cy, 3)]},
    "ice_holes": len(ice_shape.interiors) if ice_shape.geom_type == "Polygon" else "multipolygon",
}
(VAL / "11-rink-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=1))
