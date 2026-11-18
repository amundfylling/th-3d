"""Constrained 2-DoF refit of the NM26 figure tracks (docs/constrained-fit.md; hypothesis experiment, PROPOSED).

A Stiga figure sits on a rod: it has exactly two degrees of freedom, slot position u in [0, 1] (the track's arc
fraction) and a rotation theta about the rod. Per figure and per run of frames (split where frames are more than 6
apart) this fits u(t) and theta(t) with a robust (Huber) data term on the kept readings (src 0; interpolated and
unknown frames carry no data) plus a jerk prior (squared third divided difference, weight lam, in physical units),
then clips u to [0, 1]. Numpy only.
"""
import json
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
FPS = 30.0
SKATERS = ["W-LW", "E-LW", "W-RW", "E-RW", "W-C", "E-C", "W-LD", "E-LD", "W-RD", "E-RD"]


def jerk_op(t):
    """Third divided differences (times 3!) on times t (s): sparse (n-3) x n; each row is the jerk of 4 points."""
    import scipy.sparse as sp
    n = len(t); rows = []; cols = []; vals = []
    for j in range(4):
        others = [m for m in range(4) if m != j]
        d = np.ones(n - 3)
        for m in others:
            d = d * (t[j:n - 3 + j] - t[m:n - 3 + m])
        rows.append(np.arange(n - 3)); cols.append(np.arange(n - 3) + j); vals.append(6.0 / d)
    return sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n - 3, n))


def smooth(t, y, w, lam, delta, iters=8, lo=None, hi=None):
    """Minimise sum w*huber((x-y)/delta)*delta^2 + lam*sum jerk^2*dt  (jerk in unit/s^3). Returns x (n,)."""
    import scipy.sparse as sp
    from scipy.sparse.linalg import spsolve
    n = len(t); x = y.copy()
    if n < 4:
        return x
    A = jerk_op(t); wt = (t[3:] - t[:-3]) / 3
    P = lam * (A.T @ sp.diags(wt) @ A)
    wi = w.copy()
    for _ in range(iters):
        H = (sp.diags(wi + 1e-9) + P).tocsc()
        x = spsolve(H, wi * y + 1e-9 * y)
        r = np.abs(x - y) / delta
        wi = w * np.where(r <= 1, 1.0, 1.0 / np.maximum(r, 1e-9))  # Huber IRLS
    if lo is not None:
        x = np.clip(x, lo, hi)
    return x


def runs(fr, maxgap=6):
    cuts = np.where(np.diff(fr) > maxgap)[0] + 1
    return np.split(np.arange(len(fr)), cuts)


def fit_track(T, slot_len, lam_u, lam_th, du_mm=4.0, dth=8.0, use_interp=False):
    """T = loaded figure-tracks-v3 dict. Returns new rows (same columns, src column kept)."""
    C = T["columns"]; R = np.array(T["rows"], float); ci = {c: i for i, c in enumerate(C)}
    out = R.copy(); fr = R[:, 0]; t = fr / FPS
    for f in SKATERS + ["W-G", "E-G"]:
        L = slot_len[f]; src = R[:, ci[f + "_src"]]
        u = R[:, ci[f + "_u"]] * L; th = R[:, ci[f + "_theta_deg"]]
        ok = (src == 0) | ((src == 1) & use_interp)
        ok &= ~np.isnan(u) & ~np.isnan(th)
        for idx in runs(fr):
            if len(idx) < 4 or ok[idx].sum() < 4:
                continue
            tt = t[idx]; w = ok[idx].astype(float)
            uu = np.where(ok[idx], u[idx], np.nanmedian(u[idx][ok[idx]]))
            # unwrap rotation over valid readings only
            thv = th[idx].copy(); thv[~ok[idx]] = np.nan
            v = np.where(~np.isnan(thv))[0]; un = np.degrees(np.unwrap(np.radians(thv[v])))
            thu = np.interp(np.arange(len(idx)), v, un)
            xu = smooth(tt, uu, w, lam_u, du_mm, lo=0.0, hi=L)
            xt = smooth(tt, thu, w, lam_th, dth)
            keep = src[idx] != 2  # unknown stays unknown: no pose is invented where the tracker saw nothing
            out[idx[keep], ci[f + "_u"]] = xu[keep] / L; out[idx[keep], ci[f + "_theta_deg"]] = np.mod(xt, 360.0)[keep]
    return out, C


def impossible_counts(R, C, slot_len, v_max=2500.0, a_max=None, w_max=None):
    """Count dynamic violations between consecutive frames at <=1 frame spacing (dense) -- per skater-step."""
    ci = {c: i for i, c in enumerate(C)}; fr = R[:, 0]; dt = np.diff(fr) / FPS
    d1 = np.diff(fr) == 1
    res = dict(steps=0, slot_speed_over=0, rot_speed_over=0, flips=0)
    for f in SKATERS:
        L = slot_len[f]; u = R[:, ci[f + "_u"]] * L; th = R[:, ci[f + "_theta_deg"]]
        du = np.abs(np.diff(u)); dth = np.abs((np.diff(th) + 180) % 360 - 180)
        m = d1 & ~np.isnan(du) & ~np.isnan(dth)
        res["steps"] += int(m.sum())
        res["slot_speed_over"] += int((du[m] / dt[m] > v_max).sum())
        res["rot_speed_over"] += int((dth[m] / dt[m] > 5000).sum())  # 150 deg/frame
        res["flips"] += int((dth[m] > 90).sum())
    return res
