"""Fit the skater (and goalie) molds to the official overhead: absolute scale, figure poses, socket-on-slot check.

    /root/venvs/blender/bin/python scripts/fit-figure-overhead.py [--mesh-dir out/figures]
The overhead is calibrated only on the ice plane (map.overhead.preview, ASSUMED 0.1796 mm/px). Elevated
figure parts are displaced radially (relief), so the photo is modelled as a pinhole camera above the ice
at (cx, cy, H) (world mm, unknown, shared). Each figure stands with its mount socket ON its slot centreline
(arc position s, heading theta free); one scale k (mold units -> mm) is shared by all skaters.
Observations: Sweden skaters (yellow jersey + blue plastic segmented; metal stick excluded from both
masks) where the background is clean: E-LD, E-RD, E-C, E-LW. Finland W-RD (traced silhouette, white
jersey not separable by colour) and the goalies (W-G traced; E-G on yellow sponsor print) are checked
with the fitted camera: goalie scale k_g fitted separately to W-G.
Outputs: validation/players/overhead-fit.json, validation/players/overhead-fit.png.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_views as fv  # noqa: E402

REPO = fv.REPO
Image.MAX_IMAGE_PIXELS = None
g = json.loads((REPO / "data" / "geometry.json").read_text())
M = np.array(next(m for m in g["image_to_world"] if m["id"] == "map.overhead.preview")["matrix"], float).reshape(3, 3)[:2]
Minv = np.linalg.inv(np.vstack([M, [0, 0, 1]]))[:2]
ov = next(s for s in g["source_images"] if s["source_id"] == "stiga_se_fi_overhead")
IMG = np.asarray(Image.open(REPO / ov["local_path"]).convert("RGB"))
POSES = {f["player_id"]: f for f in json.loads((REPO / "validation" / "16-assembly-poses.json").read_text())["figures"]}
PATHS = {p["player_id"]: np.array(p["centreline"]["points_mm"], float) for p in g["fixture_paths"]}
MOLDS_DATA = json.loads((REPO / "data" / "figure-molds.json").read_text())
TRACES = {t["id"]: np.array(t["points_px"], float) for t in g["image_traces"]}
SKATERS = ["E-LD", "E-RD", "E-C", "E-LW"]
WIN = 300  # px half window


def arc(P):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    return d


def at(P, s):
    d = arc(P)
    s = min(max(s, 0), d[-1])
    i = min(np.searchsorted(d, s, side="right") - 1, len(P) - 2)
    t = (s - d[i]) / max(d[i + 1] - d[i], 1e-9)
    return P[i] + t * (P[i + 1] - P[i])


def s_of(P, q):
    """Arc position of the centreline point nearest to q."""
    d = arc(P)
    best = (1e18, 0)
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]
        t = np.clip(np.dot(q - a, b - a) / max(np.dot(b - a, b - a), 1e-9), 0, 1)
        e = np.linalg.norm(a + t * (b - a) - q)
        if e < best[0]:
            best = (e, d[i] + t * np.linalg.norm(b - a))
    return best[1]


def load_mesh(path):
    d = np.load(path)
    keys = [str(k) for k in d["keys"]]
    keep = d["labels"] != keys.index("stick_metal")
    return d["verts"], d["tris"][keep]


def to_px(W):
    return W[:, :2] @ Minv[:, :2].T + Minv[:, 2]


def model_px(verts, tris, pivot, theta, k, cam):
    cx, cy, H = cam
    c, s = math.cos(theta), math.sin(theta)
    x, y, z = verts[:, 0] * k, verts[:, 1] * k, verts[:, 2] * k
    X = pivot[0] + c * x - s * y
    Y = pivot[1] + s * x + c * y
    f = H / np.maximum(H - z, 1.0)  # relief: project onto the ice plane from the camera centre
    Xp = cx + (X - cx) * f
    Yp = cy + (Y - cy) * f
    return to_px(np.stack([Xp, Yp], 1))


def raster(px, tris, origin, shape):
    m = np.zeros(shape, np.uint8)
    pts = np.round((px[tris] - origin) * 4).astype(np.int32)
    cv2.fillPoly(m, list(pts), 1, shift=2)
    return m.astype(bool)


def photo_mask(pid):
    """Sweden figure in the overhead: yellow jersey component nearest the window centre, plus blue plastic
    and skin touching it; interior holes (printed number/name, seams) filled."""
    u, v = map(int, POSES[pid]["reference_px"])
    x0, y0 = u - WIN, v - WIN
    c = IMG[y0:y0 + 2 * WIN, x0:x0 + 2 * WIN]
    hsv = cv2.cvtColor(c, cv2.COLOR_RGB2HSV).astype(int)
    h, s_, v_ = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    yellow = (h >= 14) & (h <= 36) & (s_ >= 90) & (v_ >= 60)
    blue = (h >= 95) & (h <= 125) & (s_ >= 70) & (v_ >= 40)
    skin = ((h <= 14) | (h >= 170)) & (s_ >= 40) & (v_ >= 90) & (s_ <= 200)
    yel = cv2.morphologyEx(yellow.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, cents = cv2.connectedComponentsWithStats(yel, 8)
    cand = [i for i in range(1, n) if 3000 < st[i, 4] < 40000]  # a jersey (not a printed logo or circle)
    k = min(cand, key=lambda i: np.hypot(*(cents[i] - WIN))) if cand else 0
    jersey = lab == k
    near = cv2.dilate(jersey.astype(np.uint8), np.ones((71, 71), np.uint8)).astype(bool)
    m = (jersey | ((blue | skin) & near)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    n2, lab2, st2, _c2 = cv2.connectedComponentsWithStats(m, 8)
    out = lab2 == (lab2[jersey][0] if jersey.any() else -1)
    cnts, _h = cv2.findContours(out.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    filled = np.zeros_like(m)
    cv2.drawContours(filled, cnts, -1, 1, -1)
    return filled.astype(bool), np.array([x0, y0], float)


def trace_mask(trace_id, pid):
    u, v = map(int, POSES[pid]["reference_px"])
    origin = np.array([u - WIN, v - WIN], float)
    m = np.zeros((2 * WIN, 2 * WIN), np.uint8)
    cv2.fillPoly(m, [np.round(TRACES[trace_id] - origin).astype(np.int32)], 1)
    return m.astype(bool), origin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh-dir", default=str(REPO / "out" / "figures"))
    a = ap.parse_args()
    sk = load_mesh(Path(a.mesh_dir) / "skater.npz")
    go = load_mesh(Path(a.mesh_dir) / "goalie.npz")
    obs = {pid: photo_mask(pid) for pid in SKATERS}
    state = {pid: [s_of(PATHS[pid], np.array(POSES[pid]["pivot_mm"][:2])), math.radians(POSES[pid]["heading_deg"])] for pid in SKATERS}

    def iou_fig(pid, s, th, k, cam, mesh=sk, mask=None):
        ref, origin = mask if mask is not None else obs[pid]
        px = model_px(mesh[0], None, at(PATHS[pid], s), th, k, cam)
        mod = raster(px, mesh[1], origin, ref.shape)
        return fv.iou(mod, ref), mod

    glob = np.array([1.18, 0.0, 0.0, 1500.0])  # k, cx, cy, H

    def fit_figs(glob):
        for pid in SKATERS:
            s0, th0 = state[pid]
            best = None
            for ds in np.linspace(-14, 14, 8):
                for dth in np.radians([-30, -15, 0, 15, 30]):
                    sc = iou_fig(pid, s0 + ds, th0 + dth, glob[0], glob[1:])[0]
                    if best is None or sc > best[0]:
                        best = (sc, s0 + ds, th0 + dth)
            r = minimize(lambda z: -iou_fig(pid, best[1] + z[0], best[2] + z[1] * 0.1, glob[0], glob[1:])[0], [0, 0], method="Powell",
                         options={"xtol": 0.02, "ftol": 1e-4, "maxfev": 300})
            state[pid] = [best[1] + r.x[0], best[2] + r.x[1] * 0.1]

    def mean_iou(gl):
        return float(np.mean([iou_fig(pid, *state[pid], gl[0], gl[1:])[0] for pid in SKATERS]))

    for it in range(3):
        fit_figs(glob)
        scl = np.array([0.02, 20.0, 20.0, 100.0])
        r = minimize(lambda z: -mean_iou(glob + z * scl) + (0 if 400 < (glob + z * scl)[3] < 20000 else 10), np.zeros(4), method="Powell",
                     options={"xtol": 0.01, "ftol": 1e-4, "maxfev": 600})
        glob = glob + r.x * scl
        print("iter", it, "k", round(glob[0], 4), "cam", np.round(glob[1:], 1), "mean IoU", round(mean_iou(glob), 4))
    fit_figs(glob)
    # scale profile (camera fixed at the fit): how sharply does the IoU constrain k?
    prof = {}
    for kk in np.linspace(glob[0] * 0.9, glob[0] * 1.1, 9):
        st = dict(state)
        prof[round(float(kk), 4)] = round(mean_iou(np.r_[kk, glob[1:]]), 4)
    res = {"note": "Pinhole overhead camera above the ice (relief model); socket constrained to the slot centreline; preview scale ASSUMED (0.1796 mm/px).",
           "scale_k_mm_per_mold_unit": round(float(glob[0]), 4), "camera_mm": {"cx": round(float(glob[1]), 1), "cy": round(float(glob[2]), 1), "height": round(float(glob[3]), 1)},
           "k_profile_mean_iou": prof, "figures": {}}
    tiles = []
    for pid in SKATERS:
        s, th = state[pid]
        sc, mod = iou_fig(pid, s, th, glob[0], glob[1:])
        piv = at(PATHS[pid], s)
        res["figures"][pid] = {"iou": round(sc, 4), "pivot_mm": [round(float(c), 2) for c in piv], "s_mm": round(float(s), 2), "heading_deg": round(math.degrees(th) % 360, 2), "observation": "colour segmentation (Sweden)"}
        tiles.append((pid, obs[pid][0], mod, obs[pid][1]))
    # Finland W-RD: traced silhouette (includes nothing of the stick beyond the hands)
    trm = trace_mask("trace.figure.W-RD.overhead.top_silhouette", "W-RD")
    s0 = s_of(PATHS["W-RD"], np.array(POSES["W-RD"]["pivot_mm"][:2]))
    best = max(((iou_fig("W-RD", s0 + ds, math.radians(dth), glob[0], glob[1:], mask=trm)[0], s0 + ds, math.radians(dth)) for ds in np.linspace(-20, 20, 11) for dth in range(-40, 41, 10)))
    r = minimize(lambda z: -iou_fig("W-RD", best[1] + z[0], best[2] + z[1] * 0.1, glob[0], glob[1:], mask=trm)[0], [0, 0], method="Powell", options={"xtol": 0.02, "maxfev": 300})
    s, th = best[1] + r.x[0], best[2] + r.x[1] * 0.1
    sc, mod = iou_fig("W-RD", s, th, glob[0], glob[1:], mask=trm)
    res["figures"]["W-RD"] = {"iou": round(sc, 4), "pivot_mm": [round(float(c), 2) for c in at(PATHS["W-RD"], s)], "s_mm": round(float(s), 2), "heading_deg": round(math.degrees(th) % 360, 2), "observation": "traced silhouette (Finland), check only"}
    tiles.append(("W-RD", trm[0], mod, trm[1]))
    # Goalie: W-G traced silhouette; scale k_g fitted separately
    tgm = trace_mask("trace.figure.W-G.overhead.top_silhouette", "W-G")
    s0 = s_of(PATHS["W-G"], np.array(POSES["W-G"]["pivot_mm"][:2]))

    def gfit(kg):
        best = max(((iou_fig("W-G", s0 + ds, math.radians(dth), kg, glob[1:], mesh=go, mask=tgm)[0], s0 + ds, math.radians(dth)) for ds in np.linspace(-20, 20, 11) for dth in range(-40, 41, 10)))
        r = minimize(lambda z: -iou_fig("W-G", best[1] + z[0], best[2] + z[1] * 0.1, kg, glob[1:], mesh=go, mask=tgm)[0], [0, 0], method="Powell", options={"xtol": 0.02, "maxfev": 300})
        return -r.fun, best[1] + r.x[0], best[2] + r.x[1] * 0.1
    kg_best = max((gfit(kg) + (kg,) for kg in np.linspace(glob[0] * 0.9, glob[0] * 1.25, 15)), key=lambda t: t[0])
    res["goalie_only_best_scale_k"] = round(float(kg_best[3]), 4)
    res["goalie_only_best_iou"] = round(float(kg_best[0]), 4)
    # Goalie scale MEASURED by the user (height 54 mm): k_g = 54 / mold height (data/figure-molds.json goalie.scale).
    # Posed at the measured scale; the goalie-only best k at the assumed preview scale is an independent check
    # of that preview scale (ratio measured / best ~ 1 if the preview scale is right).
    gsc = MOLDS_DATA["goalie"].get("scale")
    kg_use = gsc["k_mm_per_mold_unit"] if gsc else glob[0]
    sc, s, th = gfit(kg_use)
    _sc, mod = iou_fig("W-G", s, th, kg_use, glob[1:], mesh=go, mask=tgm)
    res["goalie_scale_used_k"] = round(float(kg_use), 4)
    res["goalie_scale_used_status"] = gsc["status"] if gsc else "shared skater scale"
    res["goalie_measured_over_overhead_best"] = round(float(kg_use / kg_best[3]), 4) if gsc else None
    res["figures"]["W-G"] = {"iou": round(float(sc), 4), "pivot_mm": [round(float(c), 2) for c in at(PATHS["W-G"], s)], "s_mm": round(float(s), 2), "heading_deg": round(math.degrees(th) % 360, 2), "observation": "traced silhouette (Finland goalie), posed at the MEASURED goalie scale; goalie-only best scale reported as a check of the preview scale"}
    tiles.append(("W-G", tgm[0], mod, tgm[1]))
    # stick check: operator-read heel/toe (on the ice) in each fitted figure frame
    ks = json.loads((REPO / "data" / "figure-keypoints.json").read_text())["overhead_sticks"]
    loc = {}
    for pid, pts in ks["points_px"].items():
        if pid not in res["figures"]:
            continue
        f = res["figures"][pid]
        th = math.radians(f["heading_deg"])
        def to_local(px):
            w = M @ np.array([px[0], px[1], 1.0])
            d = w - np.array(f["pivot_mm"])
            return [round(math.cos(-th) * d[0] - math.sin(-th) * d[1], 2), round(math.sin(-th) * d[0] + math.cos(-th) * d[1], 2)]
        loc[pid] = {k: to_local(v) for k, v in pts.items()}
        if "toe" in loc[pid]:
            loc[pid]["blade_length_mm"] = round(float(np.hypot(*(np.array(loc[pid]["toe"]) - loc[pid]["heel"]))), 2)
    use = [p for p in loc if p not in ks["exclude_from_means"]]
    res["stick_check"] = {"local_mm": loc, "mean_heel_lateral_mm": round(float(np.mean([loc[p]["heel"][1] for p in use])), 2),
                          "mean_blade_length_mm": round(float(np.mean([loc[p]["blade_length_mm"] for p in use if "blade_length_mm" in loc[p]])), 2),
                          "note": "Figure frame from the fitted pivot (socket on the slot centreline) and heading; heading error rotates the heel along x."}
    out = REPO / "validation" / "players"
    out.mkdir(parents=True, exist_ok=True)
    (out / "overhead-fit.json").write_text(json.dumps(res, indent=2) + "\n")
    ims = []
    for pid, ref, mod, origin in tiles:
        x0, y0 = map(int, origin)
        rgb = IMG[y0:y0 + 2 * WIN, x0:x0 + 2 * WIN]
        viz = fv.overlay(rgb, ref, mod)
        t = Image.fromarray(np.concatenate([rgb, viz], 1))
        ImageDraw.Draw(t).text((6, 6), f"{pid} IoU {res['figures'][pid]['iou']:.3f}", fill=(0, 0, 0))
        ims.append(t)
    sheet = Image.new("RGB", (ims[0].width * 2, ims[0].height * math.ceil(len(ims) / 2)), "white")
    for i, t in enumerate(ims):
        sheet.paste(t, ((i % 2) * t.width, (i // 2) * t.height))
    sheet.save(out / "overhead-fit.png")
    print(json.dumps(res, indent=1))


main()
