"""Iteration 18 review renders of assets/scene/full_static_appearance.blend (benchmark light from 17).

    /root/venvs/blender/bin/python assets/blender/render_appearance.py
Intended output: the full-rink oblique at 1920x1080. Close-ups: skater front/side/back, blade + puck,
goalie front. Cameras are inside the rink (the near boards would hide the figures).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402

import bpy  # noqa: E402

VAL = sb.REPO / "validation"
bpy.ops.wm.open_mainfile(filepath=str(sb.REPO / "assets" / "scene" / "full_static_appearance.blend"))
# ---- Renders: intended output + close-ups (benchmark light from iteration 17) ----------------------
obl = sb.persp_camera("AsmOblique", (sb.m(120), sb.m(-700), sb.m(430)), (0.0, sb.m(-20), 0.0), 35)
sb.render(obl, VAL / "18-oblique-1080p.png", (1920, 1080), 96)
wrd = bpy.data.objects["Figure.W-RD"].matrix_world.translation
wg = bpy.data.objects["Figure.W-G"].matrix_world.translation
views = {
    "18-skater-front.png": ((wrd.x + 0.16, wrd.y - 0.01, 0.03), (wrd.x, wrd.y - 0.008, 0.028), 60),
    "18-skater-side.png": ((wrd.x, wrd.y - 0.12, 0.03), (wrd.x, wrd.y - 0.008, 0.028), 45),
    "18-skater-back.png": ((wrd.x - 0.16, wrd.y - 0.01, 0.035), (wrd.x, wrd.y - 0.008, 0.028), 60),
    "18-blade-puck.png": ((wrd.x + 0.09, wrd.y + 0.09, 0.06), (wrd.x + 0.004, wrd.y + 0.03, 0.005), 50),
    "18-goalie-front.png": ((wg.x + 0.17, wg.y - 0.02, 0.04), (wg.x - 0.005, wg.y - 0.01, 0.025), 60),
}
puck_obj = bpy.data.objects["Puck"]
review_puck = puck_obj.copy()
bpy.context.scene.collection.objects.link(review_puck)
g = sb.load_geometry()
blade = next(c for c in next(a for a in g["figure_assets"] if a["id"] == "fig.W-RD")["contact_shapes"] if c["kind"] == "blade")["geometry"]["points_mm"]
bm_mm = ((blade[0][0] + blade[1][0]) / 2, (blade[0][1] + blade[1][1]) / 2)
review_puck.location = (wrd.x + sb.m(bm_mm[0] + 0.6 + 12.7 + 0.5), wrd.y + sb.m(bm_mm[1]), 0.0)
for name, (loc, look, lens) in views.items():
    cam = sb.persp_camera(name, loc, look, lens)
    sb.render(cam, VAL / name, (1000, 1000), 64)
