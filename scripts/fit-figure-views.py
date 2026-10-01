"""Fit a pinhole camera per photo/frame to a figure mold and report silhouette IoU (camera-matched overlays).

    /root/venvs/blender/bin/python scripts/fit-figure-views.py skater|goalie [--mesh out/figures/<kind>.npz] [--out DIR]
The mold mesh comes from assets/blender/preview_molds.py or build_figures.py (npz: verts mm, tris,
labels). Per view the camera azimuth/elevation/roll, aim (pan/tilt), distance and (video) focal length are
optimised to maximise the IoU between the model silhouette (metal stick excluded) and the segmented photo
(scripts/figure_views.py). Scale is not observable here (distance absorbs it).
Outputs (default validation/players): <kind>-fit.json and <kind>-fit.png (per view: photo | red = photo only,
blue = model only | shaded model render at the fitted camera).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_views as fv  # noqa: E402

F_PHOTO = 26 * math.hypot(4284, 5712) / 43.27  # iPhone 15, 26 mm (35 mm-equivalent, diagonal) -> px
F_VIDEO = (2600.0, 3600.0)  # 4K video: stabilisation crop unknown -> fitted in this range
# view id: (initial camera azimuth deg (0 = camera in front of the figure, +90 = on the figure's LEFT),
#           initial elevation deg, exclusion polygons in work px, include warm pixels)
VIEWS = {
    "skater": {
        "skater-video-t00.00": (-10, 40, [], True),
        "skater-video-t03.00": (-60, 35, [], False),
        "skater-video-t04.50": (-85, 30, [], False),
        "skater-video-t06.00": (-150, 35, [], True),
        "skater-video-t07.25": (180, 35, [], True),
        "skater-video-t08.50": (150, 35, [], True),
        "skater-video-t10.75": (20, 40, [], True),
        # lying on its back, filmed from above: a near-orthographic FRONT view (modelling reference)
        "skater-video-t13.25": (0, 8, [], True),
    },
    "goalie": {
        "goalie-photo-front": (0, 25, [], True),
        "goalie-photo-front-oblique": (-20, 25, [], True),
        "goalie-photo-back": (180, 45, [], True),
        "goalie-photo-side": (-90, 30, [], True),
        "goalie-video-t00.50": (-10, 45, [], True),
        "goalie-video-t05.00": (-90, 45, [], True),
        "goalie-video-t07.75": (180, 45, [], True),
        "goalie-video-t12.25": (-10, 20, [], True),
    },
}


PREV = {}
FIXED = False  # --fixed: score the stored cameras without refitting (consistent before/after comparisons)


# Views NOT used for any shape fitting (held out): cameras fitted only to compare the final model.
# Optional 5th value: initial camera roll (deg) for views of a figure lying on the table.
HELDOUT = {
    "skater": {
        "skater-video-t01.50": (-5, 38, [], False),
        "skater-video-t14.50": (10, 0, [], False),  # 1.25 s after t13.25, re-posed in the hand: similar viewpoint
        "skater-video-t22.60": (10, 35, [], False),
        # round-4 independent frames, inspected since: cameras fitted once on the round-3 model, frozen
        "skater-video-t02.25": (-20, 21, [], False, 0, 40),
        "skater-video-t05.25": (-112, 20, [], False, 0, 40),
        "skater-video-t09.25": (83, 37, [], False, 0, 40),
        "skater-video-t10.25": (44, 37, [], False, 0, 40),
    },
    "goalie": {
        "goalie-video-t02.50": (-20, 45, [], False),  # rotation video, finger at the edge
        "goalie-video-t10.00": (110, 40, [], False, 0, 20),  # left-back: back print visible; motion blur, az held within 20 deg
        "goalie-photo-top": (180, 72, [], True),
        "goalie-video-t16.75": (0, 72, [], True),
        "goalie-photo-lying-back": (180, 5, [], True, 180),
        "goalie-photo-lying-back-2": (200, 10, [], True, 60),
        "goalie-photo-underside": (180, -55, [], True, 0),
        "goalie-video-t03.75": (-65, 47, [], False, 0, 40),
        "goalie-video-t06.25": (-133, 49, [], False, 0, 40),
        "goalie-video-t09.00": (130, 54, [], False, 0, 40),
        "goalie-video-t11.00": (60, 55, [], False, 0, 60),
    },
}


# Fresh turntable frames (scripts/extract-player-frames.py) reserved as INDEPENDENT checks (round 5 set; the
# round-4 set has been inspected and moved to HELDOUT with its frozen cameras). Initial
# azimuth/elevation interpolated in time between the neighbouring fitted turntable cameras. Their cameras are
# fitted ONCE against the model before the round, then frozen (--fixed) - this favours the old shape, never the
# new one. The former held-out views (HELDOUT) have since been inspected and count as fitting references.
INDEPENDENT = {
    "skater": {
        "skater-video-t00.75": (15, 25, [], False, 0, 40),
        "skater-video-t03.75": (-72, 18, [], False, 0, 40),
        "skater-video-t06.75": (-150, 22, [], False, 0, 40),
        "skater-video-t08.00": (150, 28, [], False, 0, 40),
    },
    "goalie": {
        # turntable camera height changes slowly (fitted neighbours 45-58 deg): elevation held within 15 deg
        "goalie-video-t01.25": (-25, 40, [], False, 0, 40, 15),
        "goalie-video-t07.25": (-172, 49, [], False, 0, 40, 15),  # replaces 4.25 s (camera fit failed: elevation ran to the bound, IoU 0.65)
        "goalie-video-t06.75": (-168, 49, [], False, 0, 40, 15),
        "goalie-video-t08.40": (178, 48, [], False, 0, 40, 15),
    },
}


def fit_view(mesh, view_id, init, work_px=420):
    az0, el0, excl, warm = init[:4]
    roll0 = math.radians(init[4]) if len(init) > 4 else 0.0
    az_tol = init[5] if len(init) > 5 else 60.0  # deg: allowed departure from the known view direction
    el_tol = init[6] if len(init) > 6 else None  # deg: optional bound on the elevation (turntable frames)
    rgb, s, crop, full = fv.load_view(view_id, work_px)
    ref = fv.figure_mask(rgb, include_warm=warm, exclude_polys=excl)
    verts, tris, labels, keys = mesh
    keep = labels != list(keys).index("stick_metal")
    if not warm:  # a finger touches the figure: drop warm pixels (skin, finger, tan stick) from both masks
        keep &= labels != list(keys).index("skin")
        keep &= labels != list(keys).index("stick_tan")
    target = fv.TARGET["skater" if view_id.startswith("skater") else "goalie"]
    video = "video" in view_id
    f0 = 3000.0 if video else F_PHOTO
    ys, xs = np.nonzero(ref)
    ref_c = np.array([xs.mean(), ys.mean()])
    ref_h = ys.max() - ys.min()
    size_mm = verts[:, 2].max() - verts[:, 2].min()

    def mask_of(p):
        return fv.model_mask(verts, tris, keep, p, target, ref.shape, full, crop, s)

    def aligned(az, el, roll=0.0):
        # distance from the apparent height, then pan/tilt to put the model centroid on the photo centroid
        dist = f0 * s * size_mm / ref_h
        # aim at the photo centroid (full-frame px) first: pan > 0 moves the image left, tilt > 0 moves it up
        fx, fy = crop[0] + ref_c[0] / s - full[0] / 2, crop[1] + ref_c[1] / s - full[1] / 2
        p = [az, el, roll, -math.atan2(fx, f0), -math.atan2(fy, f0), dist, f0]
        for _ in range(4):
            m = mask_of(p)
            if m.sum() < 10:
                break
            yy, xx = np.nonzero(m)
            du, dv = (ref_c - [xx.mean(), yy.mean()]) / s
            p[3] -= math.atan2(du, f0)
            p[4] -= math.atan2(dv, f0)
            p[5] *= (yy.max() - yy.min()) / ref_h
        return p

    best = None
    prev = PREV.get(view_id)
    if prev is not None:
        p = list(prev)
        p[6] = f0 if not video else p[6]
        best = (fv.iou(mask_of(p), ref), p)
    for daz in ((-30, -15, 0, 15, 30) if prev is None else ()):
        for delv in (-15, 0, 15):
            p = aligned(math.radians(az0 + daz), math.radians(min(max(el0 + delv, -85), 85)), roll0)
            sc = fv.iou(mask_of(p), ref) - max(0.0, abs((math.degrees(p[0]) - az0 + 180) % 360 - 180) - az_tol) / 60
            if best is None or sc > best[0]:
                best = (sc, p)
    x0 = np.array(best[1])
    scl = np.array([0.05, 0.05, 0.05, 0.01, 0.01, 0.03 * x0[5], 0.03 * x0[6]])

    def cost(z):
        p = x0 + z * scl
        if not video:
            p[6] = f0
        else:
            p[6] = min(max(p[6], F_VIDEO[0]), F_VIDEO[1])
        # the azimuth must stay within 60 deg of the known view direction: front and back silhouettes of a
        # figure filmed flat are near mirror images, so the IoU alone can flip a view
        flip = max(0.0, abs((math.degrees(p[0]) - az0 + 180) % 360 - 180) - az_tol) / 60
        # a figure standing on the table is never seen from below the table plane
        below = max(0.0, 2.0 - math.degrees(p[1])) / 20 if el0 >= 0 else 0.0
        elev = max(0.0, abs(math.degrees(p[1]) - el0) - el_tol) / 20 if el_tol is not None else 0.0
        return 1 - fv.iou(mask_of(p), ref) + flip + below + elev

    if FIXED and prev is not None:
        p = x0.copy()
    else:
        r = minimize(cost, np.zeros(7), method="Powell", options={"xtol": 1e-3, "ftol": 1e-4, "maxfev": 1500})
        p = x0 + r.x * scl
    p[6] = f0 if not video else min(max(p[6], F_VIDEO[0]), F_VIDEO[1])
    mod = mask_of(p)
    col = fv.shaded_render(verts, tris, labels, keys, p, target, ref.shape, full, crop, s)
    return {"iou": round(fv.iou(mod, ref), 4), "camera": {"azimuth_deg": round(math.degrees(p[0]), 2), "elevation_deg": round(math.degrees(p[1]), 2),
            "roll_deg": round(math.degrees(p[2]), 2), "pan_deg": round(math.degrees(p[3]), 2), "tilt_deg": round(math.degrees(p[4]), 2),
            "distance_mold_mm": round(p[5], 2), "focal_px": round(p[6], 1)}, "params": p.tolist()}, np.concatenate([fv.overlay(rgb, ref, mod), col], 1), rgb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind")
    ap.add_argument("--mesh")
    ap.add_argument("--out", default=str(fv.REPO / "validation" / "players"))
    ap.add_argument("--only")
    ap.add_argument("--heldout", action="store_true", help="fit cameras for the held-out views -> <kind>-heldout-fit.*")
    ap.add_argument("--independent", action="store_true", help="fresh frames reserved as independent checks -> <kind>-independent-fit.*")
    ap.add_argument("--reuse", action="store_true", help="start from the cameras in the previous <kind>-fit.json")
    ap.add_argument("--fixed", action="store_true", help="keep the stored cameras (implies --reuse): score only")
    a = ap.parse_args()
    global FIXED
    FIXED = a.fixed
    a.reuse = a.reuse or a.fixed
    tag = "-independent" if a.independent else "-heldout" if a.heldout else ""
    prevf = Path(a.out) / f"{a.kind}{tag}-fit.json"
    if a.reuse and prevf.exists():
        PREV.update({k: v["params"] for k, v in json.loads(prevf.read_text())["views"].items()})
    d = np.load(a.mesh or fv.REPO / "out" / "figures" / f"{a.kind}.npz")
    mesh = (d["verts"], d["tris"], d["labels"], [str(k) for k in d["keys"]])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res, tiles = {}, []
    for vid, init in (INDEPENDENT if a.independent else HELDOUT if a.heldout else VIEWS)[a.kind].items():
        if a.only and a.only not in vid:
            continue
        r, viz, rgb = fit_view(mesh, vid, init)
        res[vid] = r
        print(vid, r["iou"], r["camera"])
        pair = Image.fromarray(np.concatenate([rgb, viz], 1))
        ImageDraw.Draw(pair).text((6, 6), f"{vid}  IoU {r['iou']:.3f}", fill=(255, 255, 255))
        tiles.append(pair)
    W = max(t.width for t in tiles)
    H = max(t.height for t in tiles)
    cols = 2
    sheet = Image.new("RGB", (W * cols, H * math.ceil(len(tiles) / cols)), "black")
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * W, (i // cols) * H))
    sheet.save(out / f"{a.kind}{tag}-fit.png")
    summary = {"kind": a.kind, "mean_iou": round(float(np.mean([r["iou"] for r in res.values()])), 4), "views": res}
    summary["held_out"] = bool(a.heldout or a.independent)
    if a.independent:
        summary["independent"] = True
    elif a.heldout:
        summary["note"] = "Former held-out views: inspected while modelling since round 3, so they are fitting references now; see <kind>-independent-fit.json for unseen frames."
    summary["cameras"] = "fixed (scored only)" if a.fixed else "fitted"
    (out / f"{a.kind}{tag}-fit.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("mean IoU", summary["mean_iou"])


main()
