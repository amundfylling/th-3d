"""Goalie dimension check: orthographic (exact) front render of assets/figures/goalie_SWE.blend with the measured
dimensions drawn at the asset's own extents (height, stick blade length heel->toe, blade height), next to the
user's measurement sketch. Output: validation/players/goalie-dimensions.png

    /root/venvs/blender/bin/python assets/blender/render_goalie_dims.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stiga_blender as sb  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import bpy  # noqa: E402

REPO = sb.REPO
VAL = REPO / "validation" / "players"
molds = json.loads((REPO / "data" / "figure-molds.json").read_text())
meas = molds["measurements"]["goalie"]
rep = json.loads((VAL / "figures-report.json").read_text())["assets"]["goalie_SWE"]
bpy.ops.wm.open_mainfile(filepath=str(REPO / "assets" / "figures" / "goalie_SWE.blend"))
for o in [o for o in bpy.data.objects if o.type in ("LIGHT", "CAMERA")]:
    bpy.data.objects.remove(o)
sb.set_world(0.6)
sb.add_sun(3.0, (40, 10, 30))
W = 70.0  # mm ortho window
cy, cz = 10.0, 27.0  # window centre (y, z) mm
cam = sb.ortho_camera("Front", (0.3, sb.m(cy), sb.m(cz)), (90, 0, 90), sb.m(W))
N = 900
p = VAL / "goalie-dimensions-render.png"
sb.render(cam, p, (N, N), 48)
im = Image.open(p).convert("RGB")
d = ImageDraw.Draw(im)
f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
# front view from +x: image right = +y (the goalie's left, blade side), image up = +z
px = lambda y, z: (N / 2 + (y - cy) / W * N, N / 2 - (z - cz) / W * N)
red = (210, 20, 20)
hy, ty = rep["blade_heel_mm"][1], rep["blade_toe_mm"][1]  # blade runs along +y
H, bh = rep["height_mm"], rep["blade_height_mm"]
x0 = px(-16.5, 0)[0]
d.line([px(-15, 0), (x0, px(0, 0)[1]), (x0, px(0, H)[1]), px(-15, H)], fill=red, width=3)
d.text((x0 + 6, px(0, H)[1] - 30), f"{H:.1f} mm (meas. {meas['height_mm']:g})", fill=red, font=f)
yb = px(0, -3.0)[1]
d.line([(px(hy, 0)[0], px(0, 0)[1]), (px(hy, 0)[0], yb), (px(ty, 0)[0], yb), (px(ty, 0)[0], px(0, 0)[1])], fill=red, width=3)
d.text(((px(hy, 0)[0] + px(ty, 0)[0]) / 2 - 150, yb + 6), f"{rep['blade_length_mm']:.1f} mm (meas. {meas['blade_length_mm']:g})", fill=red, font=f)
xt = px(ty, 0)[0] + 14
d.line([(xt, px(0, 0)[1]), (xt, px(0, bh)[1])], fill=red, width=3)
d.text((xt - 200, px(0, bh)[1] - 60), f"{bh:.1f} mm (meas. {meas['blade_height_mm']:g})", fill=red, font=f)
sk = Image.open(REPO / meas["sketch"]).convert("RGBA")
sk = sk.resize((sk.width * 3, sk.height * 3))
bg = Image.new("RGBA", sk.size, "white")
sk = Image.alpha_composite(bg, sk).convert("RGB")
out = Image.new("RGB", (N + sk.width + 20, max(N, sk.height)), "white")
out.paste(im, (0, 0))
out.paste(sk, (N + 20, 40))
ImageDraw.Draw(out).text((N + 20, 5), "user's measurement sketch", fill=(0, 0, 0), font=f)
out.save(VAL / "goalie-dimensions.png")
p.unlink()
print("wrote", VAL / "goalie-dimensions.png")
