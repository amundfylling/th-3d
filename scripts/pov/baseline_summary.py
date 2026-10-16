"""Summarise the step-5 baseline (figures.json, puck.json) by figure and by distance from the camera.
Usage: python3 scripts/pov/baseline_summary.py <baseline outdir>
"""
import json, os, sys
import numpy as np

d = sys.argv[1]
F = json.load(open(os.path.join(d, "figures.json")))["rows"]
SK = ["W-LD", "W-RD", "E-LW", "E-RW", "W-C", "E-C", "E-LD", "E-RD", "W-LW", "W-RW"]
BANDS = [(0, 600), (600, 800), (800, 1000), (1000, 2000)]
out = {"frames": len(F), "skaters": {}, "skaters_by_distance": {}, "goalies": {}}


def stats(v):
    v = [x for x in v if x["loc_visible"] >= 0.9]
    if not v: return None
    a = lambda k: np.array([x[k] for x in v], float)
    pres, sd, vl = a("presence"), a("pivot_slot_dist_mm"), a("model_vs_loc_mm")
    return {"n": len(v), "dist_from_camera_median_mm": round(float(np.median(a("dist_from_camera_mm")))),
            "crop_zoom_median": round(float(np.median(a("crop_zoom"))), 2),
            "presence_median": round(float(np.median(pres)), 3), "presence_over_0.5": round(float(np.mean(pres > 0.5)), 3),
            "pivot_on_slot_within_6mm": round(float(np.mean(sd <= 6)), 3),
            "model_vs_localiser_median_mm": round(float(np.median(vl)), 1),
            "held": round(float(np.mean((pres > 0.5) & (sd <= 6) & (vl <= 20))), 3)}


for pid in SK:
    out["skaters"][pid] = stats([r["skaters"][pid] for r in F])
allv = [r["skaters"][p] for r in F for p in SK]
for lo, hi in BANDS:
    out["skaters_by_distance"][f"{lo}-{hi} mm"] = stats([x for x in allv if lo <= x["dist_from_camera_mm"] < hi])
for e in ("W", "E"):
    allk = [x for x in allv if True]
for g in ("W-G", "E-G"):
    v = [r["goalies"][g] for r in F]
    a = lambda k: np.array([x[k] for x in v], float)
    good = a("loc_score") > 3
    out["goalies"][g] = {"n": len(v), "dist_from_camera_median_mm": round(float(np.median(a("dist_from_camera_mm")))),
                         "model_u_spread_p10_p90": [round(float(np.percentile(a("model_u"), 10)), 3), round(float(np.percentile(a("model_u"), 90)), 3)],
                         "localiser_u_spread_p10_p90": [round(float(np.percentile(a("loc_u")[good], 10)), 3), round(float(np.percentile(a("loc_u")[good], 90)), 3)] if good.any() else None,
                         "model_vs_localiser_median_mm_where_colour_found": round(float(np.median(a("model_vs_loc_mm")[good])), 1) if good.any() else None,
                         "colour_found_fraction": round(float(good.mean()), 3),
                         "corr_model_u_vs_localiser_u": round(float(np.corrcoef(a("model_u")[good], a("loc_u")[good])[0, 1]), 3) if good.sum() > 5 else None}
P = os.path.join(d, "puck.json")
if os.path.exists(P):
    R = json.load(open(P))["rows"]
    top = [r["cands"][0] for r in R]
    s = np.array([c["score"] for c in top]); dist = np.array([c["dist_from_camera_mm"] for c in top])
    out["puck"] = {"frames": len(R), "top_score_over_0.5": round(float(np.mean(s > 0.5)), 3),
                   "top_score_over_0.3": round(float(np.mean(s > 0.3)), 3),
                   "top_score_median": round(float(np.median(s)), 3),
                   "by_distance_top_over_0.5": {f"{lo}-{hi} mm": int(np.sum((s > 0.5) & (dist >= lo) & (dist < hi))) for lo, hi in BANDS}}
json.dump(out, open(os.path.join(d, "summary.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
