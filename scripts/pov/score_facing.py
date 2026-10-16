"""Step 7: turn the user's facing taps into world rotations and score the POV model (docs/pov-videos.md).

    python3 scripts/pov/score_facing.py <facing-review-crops.json> <taps_dir> <out.json>

<taps_dir>: one JSON per tap document (the review page's db collection "pov_facing"). Per tapped crop: both taps go
back to LRF frame px through the stored frame-to-crop affine and onto the ice (z = 0) with the stored camera; the
user's theta = atan2 of the difference minus the end's home heading (W 0, E 180). Feet tap vs model pivot: distance
on the ice. Model theta: the POV model's answer stored with the crop (not shown on the page).
"""
import glob, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from pov_common import K_of
import camera_fit as cf
from pov_figures import backproject, inv_affine, HOME

crops = {c["id"]: c for c in json.load(open(sys.argv[1]))["crops"]}
taps = [json.load(open(f)) for f in glob.glob(os.path.join(sys.argv[2], "*.json"))]
taps = [t.get("data", t) for t in taps]
rows = []
for t in taps:
    c = crops.get(t["id"])
    if c is None: continue
    if t["verdict"] != "facing": rows.append({"id": t["id"], "pid": c["pid"], "verdict": t["verdict"]}); continue
    K, D = K_of(c["lens"]["f"]), cf.dist_of([c["lens"]["k1"], c["lens"]["k2"]]); M = np.array(c["M_frame_to_crop"])
    f = backproject(inv_affine(M, t["feet_px"]), c["rv"], c["tv"], K, D); d = backproject(inv_affine(M, t["dir_px"]), c["rv"], c["tv"], K, D)
    th = (math.degrees(math.atan2(d[1] - f[1], d[0] - f[0])) - HOME[c["pid"][0]]) % 360
    m = c["model"]; err = (m["theta_deg"] - th + 180) % 360 - 180
    rows.append({"id": t["id"], "pid": c["pid"], "frame": c["frame"], "verdict": "facing", "user_theta_deg": round(th, 1),
                 "user_feet_mm": [round(float(v), 1) for v in f], "model_theta_deg": m["theta_deg"], "model_presence": m["presence"],
                 "theta_err_deg": round(err, 1), "feet_vs_model_mm": round(float(np.linalg.norm(f - np.array(m["xy_mm"]))), 1)})
summ = {}
for pid in sorted({r["pid"] for r in rows}):
    R = [r for r in rows if r["pid"] == pid and r["verdict"] == "facing"]; e = np.abs([r["theta_err_deg"] for r in R]); p = np.array([r["feet_vs_model_mm"] for r in R])
    summ[pid] = {"tapped": len(R), "cant_see": sum(r["verdict"] != "facing" for r in rows if r["pid"] == pid)}
    if R: summ[pid] |= {"theta_err_median_deg": round(float(np.median(e)), 1), "theta_err_p90_deg": round(float(np.percentile(e, 90)), 1),
                        "within_15deg": round(float(np.mean(e <= 15)), 3), "within_30deg": round(float(np.mean(e <= 30)), 3),
                        "feet_vs_model_median_mm": round(float(np.median(p)), 1), "feet_vs_model_p90_mm": round(float(np.percentile(p, 90)), 1),
                        "user_theta_range_deg": [round(float(np.percentile([r["user_theta_deg"] for r in R], q)), 1) for q in (5, 95)]}
json.dump({"status": "PROPOSED", "summary": summ, "rows": rows}, open(sys.argv[3], "w"), indent=1)
print(json.dumps(summ, indent=1))
for r in sorted([r for r in rows if r["verdict"] == "facing"], key=lambda r: -abs(r["theta_err_deg"]))[:10]: print(r)
