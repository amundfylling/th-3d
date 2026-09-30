"""User decision D6 (docs/decisions.md): drop all sponsor artwork from the printed ice.

    /root/venvs/blender/bin/python assets/blender/drop_sponsors.py
Input:  assets/rink/textures/ice_basecolor_reference.png (iteration-17 texture, reference-variant print)
Output: assets/rink/textures/ice_basecolor.png (sponsor-free; used by build_materials.py),
        validation/drop-sponsors-report.json, validation/drop-sponsors-compare.png

Removed (whole regions): the fills and logos of the four face-off circles (gyproc, isover, weber, Lidl),
the yellow Byggmax crease fills, the grey Hydroscand centre disc, and the Scandic, Gigant, WD-40 and
Gorilla logos. Filled with a smooth ice shade fitted to clean ice (cubic polynomial per channel).
Kept / redrawn (hockey markings): the five straight lines, the four face-off circle rings with their
hash marks, both crease outlines (arc beyond the goal line), the referee crease and the four neutral-zone
spots. Rings and arcs are redrawn from circles fitted to their own red pixels; hash marks and spots keep
their original pixels. The centre red line is continued across the former disc (inferred: its only gap
was the sponsor disc).
"""
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
Image.MAX_IMAGE_PIXELS = None
TEX = REPO / "assets" / "rink" / "textures"
ref = np.asarray(Image.open(TEX / "ice_basecolor_reference.png").convert("RGB")).astype(np.int32)
H, W = ref.shape[:2]
g = json.loads((REPO / "data" / "geometry.json").read_text())
trep = json.loads((REPO / "validation" / "17-ice-texture-report.json").read_text())
x0, y0, x1, y1 = trep["bounds_mm"]
MMPP = trep["texel_mm"]
yy, xx = np.mgrid[0:H, 0:W]
R, G, B = ref[..., 0], ref[..., 1], ref[..., 2]
RED = (R > 180) & (R - G > 70) & (np.abs(G - B) < 40)

# Ice region (texels inside the inner boundary).
M = next(m for m in g["image_to_world"] if m["id"] == "map.overhead.preview")["matrix"]
to_tex = lambda p: ((p[0] - x0) / MMPP, (y1 - p[1]) / MMPP)
inside = np.zeros((H, W), np.uint8)
cv2.fillPoly(inside, [np.array([to_tex(q) for q in g["board"]["inner_boundary"]["world"]["points_mm"]], np.int32)], 255)
inside = inside > 0


def fit_circle(x, y):
    A = np.c_[2 * x, 2 * y, np.ones(len(x))]
    (cx, cy, c), *_ = np.linalg.lstsq(A, x ** 2 + y ** 2, rcond=None)
    return cx, cy, math.sqrt(c + cx * cx + cy * cy)


def fit_ring(cx, cy, r, side=None):
    d = np.hypot(xx - cx, yy - cy)
    sel = RED & (np.abs(d - r) < 0.1 * r)
    if side == "+x":
        sel &= xx > cx + 15
    elif side == "-x":
        sel &= xx < cx - 15
    x, y = xx[sel].astype(float), yy[sel].astype(float)
    for _ in range(5):
        fx, fy, fr = fit_circle(x, y)
        dd = np.hypot(x - fx, y - fy)
        k = np.abs(dd - fr) < max(7, 2.5 * np.std(dd - fr))
        x, y = x[k], y[k]
    dd = np.hypot(x - fx, y - fy)
    return {"centre": [fx, fy], "r": fr, "width": float(np.percentile(dd, 97) - np.percentile(dd, 3)), "n": int(len(x))}


# Operator seeds (texture px, from gridded views); fitted precisely below.
CIRCLES = {"faceoff.W.pos_y": (1216, 531, 286), "faceoff.E.pos_y": (3469, 531, 286), "faceoff.W.neg_y": (1227, 2082, 286), "faceoff.E.neg_y": (3473, 2082, 287)}
CREASES = {"crease.W": ((740, 1305, 435), "+x"), "crease.E": ((3975, 1300, 435), "-x")}
REF_CREASE = (2353, 2606, 187)
SPOTS = [(1944, 525), (2730, 525), (1956, 2079), (2739, 2079)]
LOGO_BOXES = {"scandic": (4060, 440, 4285, 935), "gigant": (345, 1610, 545, 2115), "wd40": (4065, 1925, 4430, 2310), "gorilla": (290, 380, 610, 720)}

fits = {k: fit_ring(*v) for k, v in CIRCLES.items()}
fits.update({k: fit_ring(*v[0], side=v[1]) for k, v in CREASES.items()})
fits["referee_crease"] = fit_ring(*REF_CREASE)
disc = trep["centre_disc"]

# ---- Regions to wipe --------------------------------------------------------------------------------
wipe = np.zeros((H, W), bool)
for k in CIRCLES:
    f = fits[k]
    wipe |= np.hypot(xx - f["centre"][0], yy - f["centre"][1]) < f["r"] + f["width"] / 2 + 6
for k in CREASES:  # whole crease disc: its sponsor fill also runs behind the goal line
    f = fits[k]
    wipe |= np.hypot(xx - f["centre"][0], yy - f["centre"][1]) < f["r"] + f["width"] / 2 + 6
wipe |= np.hypot(xx - disc["centre_tex_px"][0], yy - disc["centre_tex_px"][1]) < disc["radius_px"] + 8
# Coloured smudges from the sponsor fills just outside rings/creases (left by the iteration-17 inpainting).
sat0 = ref.max(axis=2) - ref.min(axis=2)
near = np.zeros((H, W), bool)
for k in list(CIRCLES) + list(CREASES):
    f = fits[k]
    near |= np.hypot(xx - f["centre"][0], yy - f["centre"][1]) < f["r"] + 90
smudge = near & (sat0 > 30)  # rings, lines, hash marks and spots are redrawn or restored afterwards
wipe |= cv2.dilate(smudge.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
logo = np.zeros((H, W), bool)
for (a, b, c, d) in LOGO_BOXES.values():
    logo[b:d, a:c] = True
logo &= inside
wipe &= inside
wipe &= ~logo  # logo boxes are filled by local inpainting (below), not the global shade

# Keep original pixels for hash marks and spots (thin red features near rings / at spot seeds).
keep = np.zeros((H, W), bool)
for k in CIRCLES:
    f = fits[k]
    cx, cy, r = f["centre"][0], f["centre"][1], f["r"]
    dist = np.hypot(xx - cx, yy - cy)
    keep |= RED & (np.abs(xx - cx) < 12) & (dist > r) & (dist < r + 70)
for sx, sy in SPOTS:
    keep |= RED & (np.hypot(xx - sx, yy - sy) < 30)

# ---- Smooth ice shade from clean ice -------------------------------------------------------------
lum = ref.mean(axis=2)
sat = ref.max(axis=2) - ref.min(axis=2)
clean = inside & ~wipe & (sat < 18) & (lum > 200)
cleanE = cv2.erode(clean.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
sy_, sx_ = np.nonzero(cleanE)
pick = np.random.default_rng(1).choice(len(sx_), min(200000, len(sx_)), replace=False)
u, v = sx_[pick] / W, sy_[pick] / H
terms = lambda u, v: np.stack([u ** i * v ** j for i in range(4) for j in range(4 - i)], axis=-1)
A = terms(u, v)
coef = [np.linalg.lstsq(A, ref[sy_[pick], sx_[pick], c].astype(float), rcond=None)[0] for c in range(3)]
wy, wx = np.nonzero(wipe)
Aw = terms(wx / W, wy / H)
out = ref.copy().astype(float)
shade = np.stack([Aw @ coef[c] for c in range(3)], axis=-1)
out[wy, wx] = shade
resid = np.std(ref[sy_[pick], sx_[pick]] - np.stack([A @ coef[c] for c in range(3)], axis=-1), axis=0)

# Local shading correction: the residual (reference - global shade) on clean ice is inpainted into the
# wiped areas at quarter resolution and added, so fills match the local vignette/lighting (no seams).
q = 4
hq, wq = H // q, W // q
gy, gx = np.mgrid[0:hq, 0:wq]
shade_q = np.stack([terms((gx * q + q / 2) / W, (gy * q + q / 2) / H) @ coef[c] for c in range(3)], axis=-1)
ref_q = cv2.resize(ref.astype(np.float32), (wq, hq), interpolation=cv2.INTER_AREA)
clean_q = cv2.resize(cleanE.astype(np.uint8), (wq, hq), interpolation=cv2.INTER_NEAREST) > 0
res_q = np.clip(ref_q - shade_q + 128, 0, 255).astype(np.uint8)
res_q[~clean_q] = 128
fill_q = cv2.inpaint(res_q, (~clean_q).astype(np.uint8) * 255, 10, cv2.INPAINT_TELEA).astype(np.float32) - 128
fill_q = cv2.GaussianBlur(fill_q, (0, 0), 3)
corr = cv2.resize(fill_q, (W, H), interpolation=cv2.INTER_LINEAR)
out[wy, wx] += corr[wy, wx]

# Feather the wipe boundary over 6 px so no seam shows.
wf = cv2.GaussianBlur(wipe.astype(np.float32), (0, 0), 3)
full_shade = np.zeros_like(out)
bb = (wf > 0.01) & inside
by, bx = np.nonzero(bb)
full_shade[by, bx] = np.stack([terms(bx / W, by / H) @ coef[c] for c in range(3)], axis=-1)
out[bb] = (1 - wf[bb, None]) * ref[bb] + wf[bb, None] * (full_shade[bb] + corr[bb])

# Logo boxes sit in shaded ice near the boards: inpaint them from their own surroundings.
bgr = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
filled = cv2.cvtColor(cv2.inpaint(bgr, logo.astype(np.uint8) * 255, 25, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB).astype(float)
lf = cv2.GaussianBlur(logo.astype(np.float32), (0, 0), 4)
out = (1 - lf[..., None]) * out + lf[..., None] * filled
out[logo] = filled[logo]
wipe |= logo

# ---- Redraw markings ----------------------------------------------------------------------------
ring_col = np.array(json.loads(json.dumps(trep["redrawn_lines"]["centre_line"]["colour_rgb"])), float)
def ring(cx, cy, r, w, colour, half=None):
    m = np.zeros((H, W), np.uint8)
    cv2.circle(m, (int(round(cx * 16)), int(round(cy * 16))), int(round(r * 16)), 255, thickness=max(1, int(round(w))), shift=4, lineType=cv2.LINE_AA)
    mm = m.astype(float) / 255
    if half is not None:
        mm *= half
    out[:] = (1 - mm[..., None]) * out + mm[..., None] * colour
for k in CIRCLES:
    f = fits[k]
    ring(f["centre"][0], f["centre"][1], f["r"], 14, ring_col)
for k, (_, side) in CREASES.items():
    f = fits[k]
    half = ((xx > f["centre"][0]) if side == "+x" else (xx < f["centre"][0])).astype(float)
    ring(f["centre"][0], f["centre"][1], f["r"], 11, np.array(trep["redrawn_lines"][f"goal_line.{k[-1]}"]["colour_rgb"], float), half)
out[keep] = ref[keep]
lm = {l["id"]: l["px"] for l in g["landmarks"]}
px_to_w = lambda p: (M[0] * p[0] + M[1] * p[1] + M[2], M[3] * p[0] + M[4] * p[1] + M[5])
line_redraw = {}
for name, info in trep["redrawn_lines"].items():
    a = np.array(to_tex(px_to_w(lm[f"lm.board.{name}.top"])))
    b = np.array(to_tex(px_to_w(lm[f"lm.board.{name}.bottom"])))
    d = (b - a) / np.linalg.norm(b - a)
    m = np.zeros((H, W), np.uint8)
    cv2.line(m, tuple(np.round(a - 80 * d).astype(int)), tuple(np.round(b + 80 * d).astype(int)), 255, thickness=info["width_px"], lineType=cv2.LINE_AA)
    sel = (m > 0) & wipe
    mm = m.astype(float) / 255 * sel
    out[:] = (1 - mm[..., None]) * out + mm[..., None] * np.array(info["colour_rgb"], float)
    line_redraw[name] = int(sel.sum())
out = np.clip(out, 0, 255).astype(np.uint8)
out[~inside] = ref[~inside]
Image.fromarray(out).save(TEX / "ice_basecolor.png", optimize=True)

small = lambda a: Image.fromarray(a.astype(np.uint8)).resize((W // 3, H // 3))
cmp_ = Image.new("RGB", (W // 3, 2 * (H // 3) + 10), "white")
cmp_.paste(small(ref), (0, 0))
cmp_.paste(small(out), (0, H // 3 + 10))
cmp_.save(REPO / "validation" / "drop-sponsors-compare.png")
report = {
    "decision": "D6 (user, 2026-09-30): drop the sponsors",
    "removed": sorted(list(CIRCLES) + list(CREASES) + ["centre_disc"] + [f"logo.{k}" for k in LOGO_BOXES]),
    "wiped_fraction_of_ice": round(float(wipe.sum() / inside.sum()), 4),
    "ice_shade_fit": {"model": "cubic polynomial per channel over clean ice + inpainted local residual (1/4 res)", "residual_std_rgb": [round(float(x), 2) for x in resid]},
    "fitted_markings_tex_px": {k: {kk: (round(vv, 1) if isinstance(vv, float) else [round(x, 1) for x in vv] if isinstance(vv, list) else vv) for kk, vv in v.items()} for k, v in fits.items()},
    "faceoff_circle_radius_mm_preview": round(float(np.mean([fits[k]["r"] for k in CIRCLES])) * MMPP, 2),
    "crease_radius_mm_preview": round(float(np.mean([fits[k]["r"] for k in CREASES])) * MMPP, 2),
    "line_texels_redrawn_in_wiped_regions": line_redraw,
    "inferences": [
        "centre red line continued across the former sponsor disc (gap existed only because of the disc)",
        "crease interiors left plain ice (their sponsor-yellow fill removed; the game's real crease colour is not evidenced)",
        "face-off circle centre spots not drawn (hidden under logos in the reference; not evidenced)",
        "all four face-off rings drawn in one red (centre-line colour); reference rings were tinted by their sponsor fills",
    ],
    "boards": "boards were already plain placeholders; no board sponsor artwork exists in the model",
}
(REPO / "validation" / "drop-sponsors-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: report[k] for k in ("wiped_fraction_of_ice", "ice_shade_fit", "faceoff_circle_radius_mm_preview", "crease_radius_mm_preview")}, indent=1))
