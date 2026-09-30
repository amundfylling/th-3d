"""Iteration 17: printed-ice texture from the official overhead (variant 71-1145-01).

    /root/venvs/blender/bin/python assets/blender/make_ice_texture.py
1. Rectify: each texel (world x, y on the ice plane, 0.1796 mm) samples the overhead through the INVERSE of
   the ASSUMED preview similarity (map.overhead.preview) - bicubic, no other warp.
2. Mask what must not be baked into the ice: 12 figures and their shadows, both goal cages and shadows,
   the puck and its shadow, and the slot/cut-out bands (holes in the geometry).
3. Reconstruct masked texels with OpenCV Telea inpainting (reported as reconstructed, not original print).
Outputs: assets/rink/textures/ice_basecolor.png, validation/17-ice-texture-mask.png,
validation/17-ice-texture-report.json.
"""
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

REPO = Path(__file__).resolve().parents[2]
Image.MAX_IMAGE_PIXELS = None
g = json.loads((REPO / "data" / "geometry.json").read_text())
M = next(m for m in g["image_to_world"] if m["id"] == "map.overhead.preview")["matrix"]
A = np.array([[M[0], M[1], M[2]], [M[3], M[4], M[5]], [0, 0, 1]])
Ainv = np.linalg.inv(A)
MMPP = math.hypot(M[0], M[3])
boundary = Polygon(g["board"]["inner_boundary"]["world"]["points_mm"])
x0, y0, x1, y1 = boundary.bounds
W = int(math.ceil((x1 - x0) / MMPP))
H = int(math.ceil((y1 - y0) / MMPP))

# ---- 1. Rectify -------------------------------------------------------------------------------------
over = next(s for s in g["source_images"] if s["source_id"] == "stiga_se_fi_overhead")
photo = Image.open(REPO / over["local_path"]).convert("RGB")
# texel (i, j) -> world (x0 + (i + 0.5) s, y1 - (j + 0.5) s) -> overhead px via Ainv; PIL affine takes the
# output->input matrix acting on output pixel coordinates (i, j).
T = Ainv @ np.array([[MMPP, 0, x0 + 0.5 * MMPP], [0, -MMPP, y1 - 0.5 * MMPP], [0, 0, 1]])
# PIL maps output pixel CENTRES? It uses (x + 0.5) conventions internally; account by shifting -0.5.
Tp = T @ np.array([[1, 0, -0.5], [0, 1, -0.5], [0, 0, 1]])
tex = photo.transform((W, H), Image.AFFINE, tuple(Tp[:2].ravel()), resample=Image.BICUBIC)
tex_np = np.asarray(tex).copy()

# ---- 2. Mask -------------------------------------------------------------------------------------
def to_tex(pw):
    return ((pw[0] - x0) / MMPP, (y1 - pw[1]) / MMPP)
def px_to_w(p):
    return (M[0] * p[0] + M[1] * p[1] + M[2], M[3] * p[0] + M[4] * p[1] + M[5])
shapes = {}
poses = json.loads((REPO / "validation" / "16-assembly-poses.json").read_text())["figures"]
SHADOW = (12.0, -4.0)  # mm: shadows fall toward +x/-y in the overhead (operator reading of soft shadows)
for p in poses:
    c = px_to_w(p["reference_px"])
    r = 30.0 if p["position"] == "G" else 26.0
    shapes[f"figure.{p['player_id']}"] = unary_union([Point(c).buffer(r), Point(c[0] + SHADOW[0], c[1] + SHADOW[1]).buffer(r)])
for t in ("W", "E"):
    cage = Polygon([px_to_w(q) for q in next(x for x in g["image_traces"] if x["id"] == f"trace.goal.{t}.cage.overhead")["points_px"]])
    shapes[f"goal.{t}"] = unary_union([cage.buffer(6.0), Polygon([(x + SHADOW[0], y + SHADOW[1]) for x, y in cage.exterior.coords]).buffer(6.0)])
    cut = Polygon([px_to_w(q) for q in next(x for x in g["image_traces"] if x["id"] == f"trace.goal.{t}.cutout.overhead")["points_px"]])
    shapes[f"cutout.{t}"] = cut.buffer(2.0)
hw = json.loads((REPO / "validation" / "12-hardware-report.json").read_text())
pk = hw["puck"]["reference_position_mm"]
shapes["puck"] = unary_union([Point(pk).buffer(17.0), Point(pk[0] + SHADOW[0], pk[1] + SHADOW[1]).buffer(15.0)])
for f in g["fixture_paths"]:
    tr = next(t for t in g["image_traces"] if t["id"] == f"trace.slot.{f['player_id']}.overhead")
    w_mm = tr["stats"]["width_median_px"] * MMPP
    shapes[f"slot.{f['player_id']}"] = LineString(f["centreline"]["points_mm"]).buffer(w_mm / 2 + 1.5, cap_style="round")
mask = np.zeros((H, W), np.uint8)
for shp in shapes.values():
    polys = list(shp.geoms) if shp.geom_type == "MultiPolygon" else [shp]
    for poly in polys:
        pts = np.array([to_tex(q) for q in poly.exterior.coords], np.int32)
        cv2.fillPoly(mask, [pts], 255)
# Operator boxes (texture px, read from a gridded view of the rectified texture) covering each figure's
# body, metal stick and soft shadow, which the automatic discs above missed (sticks reach 30-40 mm).
FIGURE_BOXES_TEX = {
    "E-RW": (150, 165, 345, 516), "E-LW": (0, 1035, 465, 1284), "goal.W+W-G": (450, 1005, 1050, 1605),
    "E-C": (1200, 1035, 1395, 1395), "E-LD+W-RD": (1800, 1560, 2250, 1980), "W-LD+E-RD": (2442, 630, 2862, 1035),
    "puck": (2772, 1305, 2937, 1470), "W-C": (3297, 1200, 3477, 1575), "goal.E+E-G": (3627, 1020, 4272, 1620),
    "W-LW": (4242, 1335, 4707, 1605), "W-RW": (4257, 2115, 4557, 2430),
}
for bx in FIGURE_BOXES_TEX.values():
    cv2.rectangle(mask, (bx[0], bx[1]), (bx[2], bx[3]), 255, thickness=-1)
inside = np.zeros((H, W), np.uint8)
cv2.fillPoly(inside, [np.array([to_tex(q) for q in boundary.exterior.coords], np.int32)], 255)
mask &= inside

# ---- 3. Reconstruct -------------------------------------------------------------------------------
# Outside the ice boundary the rectified photo shows boards; replace it by the median unmasked ice colour
# first so inpainting cannot pull board pixels into the ice (repair 2).
ice_px = tex_np[(inside > 0) & (mask == 0)]
ice_colour = np.median(ice_px, axis=0).astype(np.uint8)
lm = {l["id"]: l["px"] for l in g["landmarks"]}

# Straight markings (goal, blue, centre lines): measure width, colour and where the line is PRESENT in the
# original print (sampled along the line on unmasked texels; e.g. the centre line is absent under the grey
# centre disc).
lines = {}
for name in ("goal_line.W", "blue_line.W", "centre_line", "blue_line.E", "goal_line.E"):
    a = np.array(to_tex(px_to_w(lm[f"lm.board.{name}.top"])))
    b = np.array(to_tex(px_to_w(lm[f"lm.board.{name}.bottom"])))
    L = np.linalg.norm(b - a)
    d = (b - a) / L
    n = np.array([-d[1], d[0]])
    ts = np.arange(-60.0, L + 60.0, 4.0)
    present = np.full(len(ts), -1)  # -1 unknown (masked/outside), 0 absent, 1 present
    widths, cols = [], []
    for i, t in enumerate(ts):
        c = a + t * d
        ci, cj = int(round(c[0])), int(round(c[1]))
        if not (0 <= ci < W and 0 <= cj < H) or mask[cj, ci] or not inside[cj, ci]:
            continue
        prof = [tex_np[int(round(c[1] + k * n[1])), int(round(c[0] + k * n[0]))].astype(int) for k in range(-25, 26)]
        sat = np.array([int(p_.max()) - int(p_.min()) for p_ in prof])
        on = sat[20:31] > 60
        present[i] = 1 if on.sum() >= 3 else 0
        if present[i] == 1:
            full_on = sat > 60
            widths.append(int(full_on.sum()))
            cols += [prof[k] for k in np.nonzero(full_on)[0]]
    lines[name] = dict(a=a, d=d, n=n, ts=ts, present=present, w=int(np.median(widths)), col=np.median(np.array(cols), axis=0).astype(np.uint8))

# Mask line bands near masked areas too, so inpainting cannot bleed line colour sideways (repair 3).
near = cv2.dilate(mask, np.ones((81, 81), np.uint8))
band_all = np.zeros_like(mask)
for ln in lines.values():
    pa = ln["a"] + ln["ts"][0] * ln["d"]
    pb = ln["a"] + ln["ts"][-1] * ln["d"]
    cv2.line(band_all, tuple(np.round(pa).astype(int)), tuple(np.round(pb).astype(int)), 255, thickness=ln["w"] + 10)
mask_inpaint = mask | (band_all & near)

# Outside the ice boundary the rectified photo shows boards; replace it by the median unmasked ice colour
# first so inpainting cannot pull board pixels into the ice (repair 2).
work = tex_np.copy()
work[inside == 0] = ice_colour
bgr = cv2.cvtColor(work, cv2.COLOR_RGB2BGR)
filled = cv2.inpaint(bgr, mask_inpaint | (255 - inside), 12, cv2.INPAINT_TELEA)
out = cv2.cvtColor(filled, cv2.COLOR_BGR2RGB)

# Grey centre disc: fit its circle to unmasked edge texels and restore its outline inside masked areas
# (inpainting otherwise bulges disc grey into the ice).
lum = tex_np.astype(int).mean(axis=2)
sat = tex_np.astype(int).max(axis=2) - tex_np.astype(int).min(axis=2)
cxy = np.array(to_tex((0.0, 0.0)))
yy, xx = np.mgrid[0:H, 0:W]
near_c = (xx - cxy[0]) ** 2 + (yy - cxy[1]) ** 2 < 450 ** 2
disc_px = near_c & (lum > 175) & (lum < 218) & (sat < 18) & (mask_inpaint == 0)
edge = disc_px & ~cv2.erode(disc_px.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
ey, ex = np.nonzero(edge)
def fit_circle(x, y):
    Am = np.c_[2 * x, 2 * y, np.ones(len(x))]
    (cx_, cy_, c0_), *_ = np.linalg.lstsq(Am, x ** 2 + y ** 2, rcond=None)
    return cx_, cy_, math.sqrt(c0_ + cx_ ** 2 + cy_ ** 2)
dcx, dcy, dr = fit_circle(ex, ey)
for _ in range(3):  # keep only the OUTER edge (logo-box edges inside the disc pull the fit inward)
    dist = np.hypot(ex - dcx, ey - dcy)
    keep = np.abs(dist - np.percentile(dist, 90)) < 6
    dcx, dcy, dr = fit_circle(ex[keep], ey[keep])
rr = np.sqrt((xx - dcx) ** 2 + (yy - dcy) ** 2)
in_disc = rr <= dr
disc_colour = np.median(tex_np[disc_px & in_disc], axis=0).astype(np.uint8)
# Two-source inpainting: masked texels inside the disc from disc texels only, outside from ice only.
m_all = (mask_inpaint > 0) & (inside > 0)
src_in = work.copy(); src_in[~in_disc] = disc_colour
src_out = work.copy(); src_out[in_disc] = ice_colour
fill_in = cv2.cvtColor(cv2.inpaint(cv2.cvtColor(src_in, cv2.COLOR_RGB2BGR), ((m_all & in_disc) * 255).astype(np.uint8), 12, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB)
fill_out = cv2.cvtColor(cv2.inpaint(cv2.cvtColor(src_out, cv2.COLOR_RGB2BGR), ((m_all & ~in_disc) * 255).astype(np.uint8) | (255 - inside), 12, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB)
out[m_all & in_disc] = fill_in[m_all & in_disc]
out[m_all & ~in_disc] = fill_out[m_all & ~in_disc]
m_in, m_ring = m_all & in_disc, m_all & ~in_disc
disc_report = {"centre_tex_px": [round(float(dcx), 1), round(float(dcy), 1)], "radius_px": round(dr, 1), "radius_mm": round(dr * MMPP, 2), "restored_texels": int(m_in.sum() + m_ring.sum())}

# Redraw each line across inpainted texels, but only over gaps bounded by PRESENT samples on both sides.
line_report = {}
for name, ln in lines.items():
    pres = ln["present"]
    known = np.nonzero(pres >= 0)[0]
    draw_mask = np.zeros_like(mask)
    for k0, k1 in zip(known[:-1], known[1:]):
        if pres[k0] == 1 and pres[k1] == 1:
            pa = ln["a"] + ln["ts"][k0] * ln["d"]
            pb = ln["a"] + ln["ts"][k1] * ln["d"]
            cv2.line(draw_mask, tuple(np.round(pa).astype(int)), tuple(np.round(pb).astype(int)), 255, thickness=ln["w"])
    sel = (draw_mask > 0) & (mask_inpaint > 0) & (inside > 0)
    out[sel] = ln["col"]
    line_report[name] = {"width_px": ln["w"], "colour_rgb": ln["col"].tolist(), "redrawn_texels": int(sel.sum()), "absent_samples": int((pres == 0).sum())}
out[inside == 0] = (200, 200, 200)  # outside the ice (never visible on the ice mesh)
(REPO / "assets" / "rink" / "textures").mkdir(parents=True, exist_ok=True)
Image.fromarray(out).save(REPO / "assets" / "rink" / "textures" / "ice_basecolor.png", optimize=True)
viz = out.copy()
viz[mask_inpaint > 0] = (0.5 * viz[mask_inpaint > 0] + 0.5 * np.array([255, 0, 255])).astype(np.uint8)
Image.fromarray(viz).resize((W // 3, H // 3)).save(REPO / "validation" / "17-ice-texture-mask.png")
Image.fromarray(tex_np).resize((W // 3, H // 3)).save(REPO / "validation" / "17-ice-texture-rectified-raw.png")
report = {
    "source_image_id": over["source_id"],
    "variant": "Sweden vs Finland 71-1145-01 (current gallery artwork); bare-sheet print NOT used",
    "texel_mm": round(MMPP, 6),
    "size_px": [W, H],
    "uv": "planar from world mm: u = (x - x0) / (x1 - x0), v = (y - y0) / (y1 - y0) over the inner-boundary bounds",
    "bounds_mm": [round(v, 3) for v in (x0, y0, x1, y1)],
    "rectification": "inverse of the ASSUMED preview similarity (map.overhead.preview), bicubic; lens bow up to about 10 px and keystone not corrected (docs/board-trace.md)",
    "masked_fraction_of_ice": round(float(((mask_inpaint > 0) & (inside > 0)).sum() / (inside > 0).sum()), 4),
    "masked_regions": sorted(shapes) + [f"box.{k}" for k in FIGURE_BOXES_TEX],
    "reconstruction": "OpenCV Telea inpainting, radius 12 px, after filling outside-ice texels with the median ice colour; line bands near masks also inpainted, then straight markings redrawn only across gaps bounded by line presence in the original: masked texels are RECONSTRUCTED, not original print",
    "redrawn_lines": line_report,
    "centre_disc": disc_report,
    "known_gaps": ["Byggmax crease logos (both goals) partly reconstructed under goals/goalies", "Gorilla logo (top-left) partly reconstructed under E-RW", "WD-40 logo edge under W-RW", "photo lighting/shading and board reflections along the ice edge remain baked in", "lens bow/keystone not corrected (<= about 16 px)"],
}
(REPO / "validation" / "17-ice-texture-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=1))
