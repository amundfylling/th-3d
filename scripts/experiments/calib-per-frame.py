"""Experiment: does per-frame calibration refinement beat the static game calibration? (NM26 g1, PROPOSED)

    python3 scripts/experiments/calib-per-frame.py sample g1 2.0 out/experiments/calib/g1-samples.npz
    python3 scripts/experiments/calib-per-frame.py analyse out/experiments/calib/g1-samples.npz

sample: every STEP seconds the frame is registered (the repo's ORB Registrar), warped to the stab plane, and the repo's
slot centrelines, projected with the static calibration H, are matched to the dark slot pixels (as in nm26-calibrate.py).
Everything the analysis needs is saved: registration H, inlier count, the matched (model px, image px) pairs, slot ids.
analyse: see the functions below; numbers go to out/experiments/calib/results.json.
"""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nm26_common import CFG, REPO, T_ROI, W_STAB, H_STAB, Registrar, frames, game_dir, ice_mask, load, proj  # noqa: E402
import table_common  # noqa: E402

SL = {k: v for k, v in table_common.SLOT.items() if not k.endswith("-G")}
PIDS, SP, SID = [], [], []
for n, (pid, P) in enumerate(SL.items()):
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    for a in np.arange(5, s[-1] - 5, 4):
        SP.append([np.interp(a, s, P[:, 0]), np.interp(a, s, P[:, 1])]); SID.append(n)
SP, SID = np.array(SP), np.array(SID)


def dark_tree(w):
    hsv = cv2.cvtColor(w, cv2.COLOR_BGR2HSV)
    dark = (hsv[..., 2] < 100) & (hsv[..., 1] < 100) & ice_mask()
    ys, xs = np.where(dark)
    return cKDTree(np.c_[xs, ys]), np.c_[xs, ys].astype(float)


def icp(tree, XY, Hs, rads=(8, 6, 5, 5), thr=3.0):
    """Homography correction D (stab px -> stab px) so that D(proj(Hs, SP)) lies on dark pixels."""
    D = np.eye(3)
    for r in rads:
        P = proj(D @ Hs, SP)
        d, k = tree.query(P, distance_upper_bound=r)
        ok = np.isfinite(d)
        if ok.sum() < 60:
            break
        Dn, _ = cv2.findHomography(proj(Hs, SP)[ok], XY[k[ok]], cv2.RANSAC, thr)
        if Dn is None:
            break
        D = Dn
    return D


def sample_chunk(args):
    game, t0, t1, step = args
    Hs = np.array(load(game_dir(game) / "calibration.json")["H_world_mm_to_stab_px"])
    if "calibration_from" in CFG["games"][game]:
        Hs = np.array(load(game_dir(CFG["games"][game]["calibration_from"]) / "calibration.json")["H_world_mm_to_stab_px"])
    from nm26_common import reference_frame
    reg = Registrar(reference_frame(game))
    out = []
    nxt = t0
    for i, a in frames(t0 - 1.0, t1):
        H, n = reg(a)  # register every frame so the fallback chain behaves as in production
        t = i / 30.0
        if t < nxt - 1e-6:
            continue
        nxt += step
        w = cv2.warpPerspective(a, T_ROI @ H, (W_STAB, H_STAB), flags=cv2.INTER_LINEAR)
        tree, XY = dark_tree(w)
        P0 = proj(Hs, SP)
        d0, k0 = tree.query(P0)
        D = icp(tree, XY, Hs)
        P1 = proj(D @ Hs, SP)
        d1, _ = tree.query(P1)
        out.append(dict(i=i, n=n, H=H.ravel(), D=D.ravel(), d0=d0, d1=d1))
    return out


def sample(game, step, dst):
    T0, T1 = CFG["games"][game]["video_window_s"]
    edges = np.linspace(T0, T1, 5)
    # chunk starts are aligned to the step grid
    with Pool(4) as p:
        R = p.map(sample_chunk, [(game, edges[k], edges[k + 1], step) for k in range(4)])
    R = sorted([r for part in R for r in part], key=lambda r: r["i"])
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dst, i=[r["i"] for r in R], n=[r["n"] for r in R], H=[r["H"] for r in R], D=[r["D"] for r in R],
                        d0=[r["d0"] for r in R], d1=[r["d1"] for r in R])
    print("frames", len(R))


if __name__ == "__main__":
    if sys.argv[1] == "sample":
        sample(sys.argv[2], float(sys.argv[3]), sys.argv[4])


# ---------------------------------------------------------------- analysis
def undist(P, k1, k2, c):
    """Radial model applied to stab px: p' = c + (p - c) (1 + k1 r^2 + k2 r^4), r in units of 1000 px."""
    d = (P - c) / 1000.0
    r2 = (d ** 2).sum(1, keepdims=True)
    return c + 1000.0 * d * (1 + k1 * r2 + k2 * r2 ** 2)


def lens_fit():
    """Static homography vs homography + radial term on the game background (the empty rink), held out by slot."""
    from scipy.optimize import least_squares
    G = load(REPO / "data/geometry.json")
    bg = cv2.imread(str(game_dir("g1") / "background.png"))
    tree, XY = dark_tree(bg)
    Hs = np.array(load(game_dir("g1") / "calibration.json")["H_world_mm_to_stab_px"])
    c = np.array([W_STAB / 2, H_STAB / 2], float)
    # matches from the static calibration (radius 5 px, as the calibration itself)
    P0 = proj(Hs, SP)
    d, k = tree.query(P0, distance_upper_bound=5.0)
    ok = np.isfinite(d)
    A, B = SP[ok], XY[k[ok]]
    sid = SID[ok]
    rng = np.random.default_rng(0)
    folds = rng.integers(0, 2, sid.max() + 1)
    res = {}
    for name, use_k in (("homography", False), ("homography+k1", True), ("homography+k1+k2", "k2")):
        errs = []
        for f in (0, 1):
            tr, te = folds[sid] != f, folds[sid] == f

            def model(p, X):
                H = np.r_[p[:8], 1].reshape(3, 3)
                Q = proj(H, X)
                return undist(Q, p[8], p[9] if len(p) > 9 else 0.0, c) if len(p) > 8 else Q
            p0 = np.r_[(Hs / Hs[2, 2]).ravel()[:8], 0.0, 0.0] if use_k else (Hs / Hs[2, 2]).ravel()[:8]
            if use_k is True:
                p0 = p0[:9]
            fun = lambda p: (model(p, A[tr]) - B[tr]).ravel()  # noqa: E731
            sol = least_squares(fun, p0, loss="soft_l1", f_scale=1.5, x_scale="jac")
            e = np.linalg.norm(model(sol.x, A[te]) - B[te], axis=1)
            errs.append(e)
            if f == 0:
                res.setdefault(name, {})["params_tail"] = [float(v) for v in sol.x[8:]]
        e = np.concatenate(errs)
        res[name].update(heldout_median_px=float(np.median(e)), heldout_mean_px=float(e.mean()),
                         heldout_within1px=float((e < 1).mean()), n=int(len(e)))
    return res


def mm_per_px(Hs, pts):
    """Local mm per stab px along x and y at world points (for the stab-px -> mm conversion of shifts)."""
    return Hs


def analyse(npz):
    z = np.load(npz)
    Hs = np.array(load(game_dir("g1") / "calibration.json")["H_world_mm_to_stab_px"])
    Hinv = np.linalg.inv(Hs)
    R = {}
    n = z["n"]
    R["frames"] = int(len(n))
    R["registration_fallback_frames"] = int((n == 0).sum())
    R["registration_inliers_median"] = float(np.median(n[n > 0]))
    # shake: registration homography acting on the rink corners (reference video px -> where the frame has them)
    ref_pts = np.array([(300, 520), (1760, 520), (300, 880), (1760, 880), (1030, 700)], float)
    disp = []
    scale = []
    for h in z["H"]:
        H = (h / h[8]).reshape(3, 3)
        q = proj(np.linalg.inv(H), ref_pts)
        disp.append(np.linalg.norm(q - ref_pts, axis=1))
        J = np.linalg.det(H[:2, :2])
        scale.append(J)
    disp = np.array(disp)
    R["frame_shake_px_at_rink_points"] = dict(median=float(np.median(disp)), p95=float(np.percentile(disp, 95)), max=float(disp.max()))
    scale = np.array(scale)
    R["frame_scale_drift"] = dict(median=float(np.median(scale)), min=float(scale.min()), max=float(scale.max()),
                                  std=float(scale.std()))
    R["scale_drift_over_time"] = [float(np.mean(scale[a:a + 30])) for a in range(0, len(scale), 30)]
    # per-frame residual of the static calibration, and after per-frame refinement (fitted on the same samples)
    d0, d1 = z["d0"], z["d1"]
    R["static_residual_px"] = dict(median=float(np.median(np.median(d0, 1))), within2=float((d0 < 2).mean()), within4=float((d0 < 4).mean()))
    R["per_frame_refined_residual_px"] = dict(median=float(np.median(np.median(d1, 1))), within2=float((d1 < 2).mean()), within4=float((d1 < 4).mean()))
    # correction D in mm at puck-relevant world points
    P = np.array([[-350, 0], [0, 0], [350, 0], [-350, 180], [350, -180], [0, 180], [0, -180]], float)
    shifts = []
    for d in z["D"]:
        D = d.reshape(3, 3)
        a = proj(Hs, P)
        b = proj(D @ Hs, P)
        shifts.append(np.linalg.norm(proj(Hinv, b) - P, axis=1))
    shifts = np.array(shifts)
    R["correction_D_mm_at_points"] = dict(median=float(np.median(shifts)), p95=float(np.percentile(shifts, 95)), max=float(shifts.max()))
    # parallax of the puck height: 12 mm above the ice, camera at about the NM26 reference
    R["lens_fit_background"] = lens_fit()
    out = Path(npz).parent / "results.json"
    out.write_text(json.dumps(R, indent=1))
    print(json.dumps(R, indent=1))


if __name__ == "__main__" and sys.argv[1] == "analyse":
    analyse(sys.argv[2])
