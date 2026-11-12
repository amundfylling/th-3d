"""Step 6: the POV figure model on real frames, against the step-5 baseline (docs/pov-videos.md).

    python3 scripts/pov/eval_pov_figures.py <video> <track.npz> <plate.png> <model.pt> <outdir> [--frames figures.json] [--run start n]

No labels exist yet (step 7 makes the first), so the measures are label-free:
- found: the localiser's best presence > 0.5 (the step-5 baseline: skater-v3's presence at the colour localiser's spot);
- frame-to-frame steadiness on a run of consecutive frames (--run): median change of the slot position (mm) and of
  the rotation (deg) between consecutive frames where the figure is found in both. Figures do move, so this is an
  upper bound on the noise; the same run is read by the step-5 pipeline (colour localiser + skater-v3, rotation
  corrected for the view direction) for comparison.
Writes <outdir>/pov-figures.json (per frame and figure), summary.json and figures-sheet.jpg (crops with the
predicted pivot and facing arrow).
"""
import json, math, os, sys
import numpy as np
import cv2
import torch

sys.path.insert(0, os.path.dirname(__file__))
import pov_figures as pf
from pov_common import K_of, read_frames
import camera_fit as cf
import rink_plate as rp

A = sys.argv[1:]
video, track, plate_path, model_path, outdir = A[:5]
os.makedirs(outdir, exist_ok=True); torch.set_num_threads(4)
T = np.load(track); R = T["rows"]; intr = T["intr"]; K, D = K_of(intr[0]), cf.dist_of(intr[1:])
net = pf.load(model_path)
L = {p: float(np.sum(np.linalg.norm(np.diff(pf.SL[p], axis=0), axis=1))) for p in pf.ORDER}


def read_all(idx):
    out = {}
    for k in range(0, len(idx), 40): out.update(read_frames(video, idx[k:k + 40]))
    return out


def new_pipeline(frames):
    rows = {}
    for n, i in enumerate(sorted(frames)):
        r = R[i]; res = pf.localise(net, frames[i], r[1:4], r[4:7], K, D)
        rows[i] = {p: {k: v for k, v in d.items() if k != "M"} | {"M": d["M"].tolist()} for p, d in res.items()}
        if n % 25 == 0: print("new", n, "/", len(frames), flush=True)
    return rows


def old_pipeline(frames):
    import baseline_models as bm
    sk = bm.skater_model(); plate = cv2.imread(plate_path); rows = {}
    for i in sorted(frames):
        r = R[i]; rv, tv = r[1:4], r[4:7]; img = frames[i]
        pv, inside = rp.plate_in_view(plate, rv, tv, K, D); C = -cv2.Rodrigues(rv)[0].T @ tv
        pp = lambda X, rv=rv, tv=tv: cf.project(X, rv, tv, K, D)
        masks = {e: bm.team_mask(img, pv, inside, e) for e in "WE"}; tens, meta = [], []
        for pid in bm.ORDER:
            foot, sc, vis = bm.locate(masks[pid[0]], pid, rv, tv, K, D)
            M, _, _ = bm.placement(pp, foot, np.array([100.0, 136.0]), "ground")
            tens.append(bm.skater_tensor(cv2.warpAffine(img, M, (200, 200), flags=cv2.INTER_AREA, borderMode=cv2.BORDER_REPLICATE), pid)); meta.append((pid, foot, M))
        with torch.no_grad(): P = sk(torch.stack(tens)).numpy()
        rows[i] = {}
        for (pid, foot, M), p in zip(meta, P):
            w = bm.backproject(bm.inv_affine(M, bm.net_to_px(p[:2])), rv, tv, K, D); u, d = bm.u_and_dist(pid, w)
            th = float(np.degrees(np.arctan2(p[2], p[3])) % 360)
            corr = (th + bm.view_azimuth(C, foot) - bm.view_azimuth(bm.C_REF, foot)) % 360
            rows[i][pid] = {"u": float(u), "theta_deg": float(corr), "presence": float(1 / (1 + np.exp(-p[4])))}
    return rows


def angdiff(a, b): return abs((a - b + 180) % 360 - 180)


def steadiness(rows):
    out = {}
    fr = sorted(rows)
    for pid in pf.ORDER[:10] + pf.ORDER[10:]:
        du, dt = [], []
        for a, b in zip(fr[:-1], fr[1:]):
            if b != a + 1: continue
            x, y = rows[a].get(pid), rows[b].get(pid)
            if x and y and x["presence"] > 0.5 and y["presence"] > 0.5:
                du.append(abs(x["u"] - y["u"]) * L[pid]); dt.append(angdiff(x["theta_deg"], y["theta_deg"]))
        out[pid] = {"pairs": len(du), "slot_change_median_mm": round(float(np.median(du)), 1) if du else None,
                    "rotation_change_median_deg": round(float(np.median(dt)), 1) if dt else None}
    return out


summary = {"status": "PROPOSED", "model": os.path.basename(model_path), "track": os.path.basename(track)}
if "--frames" in A:
    ev = [r["frame"] for r in json.load(open(A[A.index("--frames") + 1]))["rows"]]
    ev = [i for i in ev if R[i, 11] > 0]
    F = read_all(ev); rows = new_pipeline(F)
    json.dump({"status": "PROPOSED", "rows": {str(k): v for k, v in rows.items()}}, open(os.path.join(outdir, "pov-figures.json"), "w"))
    summary["found_rate"] = {p: round(float(np.mean([rows[i][p]["presence"] > 0.5 for i in rows if p in rows[i]])), 3) for p in pf.ORDER}
    summary["frames"] = len(rows)
    # review sheet: 6 frames x 12 figures
    tiles = []
    for i in [sorted(rows)[k] for k in np.linspace(0, len(rows) - 1, 6).astype(int)]:
        for pid in pf.ORDER:
            d = rows[i].get(pid)
            if d is None: tiles.append(np.zeros((pf.CS, pf.CS, 3), np.uint8)); continue
            M = np.array(d["M"]); c = cv2.resize(pf.crop(F[i], M), None, fx=1.0, fy=1.0)
            q = M @ np.r_[d["px"], 1.0]; a = math.radians(d["theta_deg"])
            col = (0, 220, 0) if d["presence"] > 0.5 else (0, 0, 255)
            cv2.circle(c, (int(q[0]), int(q[1])), 3, col, -1)
            cv2.putText(c, f"{pid} {d['presence']:.2f}", (3, 12), 0, 0.38, col, 1, cv2.LINE_AA)
            cv2.putText(c, f"f{i}", (3, 155), 0, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            tiles.append(c)
    cv2.imwrite(os.path.join(outdir, "figures-sheet.jpg"), np.vstack([np.hstack(tiles[k:k + 12]) for k in range(0, len(tiles), 12)]), [cv2.IMWRITE_JPEG_QUALITY, 85])
if "--run" in A:
    s0, n = int(A[A.index("--run") + 1]), int(A[A.index("--run") + 2])
    idx = [i for i in range(s0, s0 + n) if R[i, 11] > 0]
    F = read_all(idx)
    rn, ro = new_pipeline(F), old_pipeline(F)
    summary["run"] = {"frames": [s0, s0 + n], "solved": len(idx), "new": steadiness(rn), "baseline": steadiness(ro),
                      "new_found_rate": {p: round(float(np.mean([rn[i][p]["presence"] > 0.5 for i in rn if p in rn[i]])), 3) for p in pf.ORDER},
                      "baseline_found_rate": {p: round(float(np.mean([ro[i][p]["presence"] > 0.5 for i in ro])), 3) for p in pf.ORDER[:10]}}
    json.dump({"new": {str(k): v for k, v in rn.items()}, "baseline": {str(k): v for k, v in ro.items()}}, open(os.path.join(outdir, "run.json"), "w"))
json.dump(summary, open(os.path.join(outdir, "summary.json"), "w"), indent=1)
print(json.dumps(summary, indent=1))
