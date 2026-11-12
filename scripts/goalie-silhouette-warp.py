"""Warp the goalie mold toward the user's photo silhouettes with a smooth 3D displacement field (docs/goalie-warp.md).

    /root/venvs/blender/bin/python scripts/goalie-silhouette-warp.py fit [--iters 30] [--spacing 2.5]
    /root/venvs/blender/bin/python scripts/goalie-silhouette-warp.py apply   # out/figures/goalie.npz -> goalie-warp.npz

No 3D model of the STIGA goalie exists (unlike the skater, docs/skater-stl.md), so the hand-built parametric mold
(data/figure-molds.json) is kept and bent: a displacement field u(x) on a regular lattice (trilinear, mold units) moves
every vertex of the joined mold, x -> x + u(x). Parts, paint borders, ribs and holes ride along; the field is continuous,
so parts stay attached.

Fit: at each camera-matched view (cameras as scripts/fit-figure-views.py) the model's rim vertices (on the silhouette,
normal across the view ray) should lie on the photo's silhouette. Each gives one point-to-plane equation
n . u(x0) = -signed distance; all views are solved together with a lattice smoothness term (least squares), in small
steps, with the cameras refitted between steps. Held fixed: the mount socket (fixture axis), everything touching the ice
(z stays 0), the top of the mask (so the measured 54 mm height and the scale k are unchanged). The stick (paddle and blade)
is moved rigidly in plan (turned about z and slid on the ice; measured blade 26 x 5.5 mm unchanged).

Fitting views: the 8 fitting views + the 5 former held-out views without a finger in frame. The 6 finger frames and the
4 regression frames are NOT used here; fit-figure-views.py scores them afterwards.
Output: data/figures/goalie-warp.json (lattice + displacements + provenance), out/figures/goalie-warp.npz.
"""
import argparse
import importlib.util
import json
import math
import sys
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np
import scipy.sparse as sp
from scipy.optimize import minimize
from scipy.sparse.linalg import spsolve

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_views as fv  # noqa: E402

REPO = fv.REPO
SPEC = REPO / "data" / "figures" / "goalie-warp.json"
MESH = REPO / "out" / "figures" / "goalie.npz"
TARGET = fv.TARGET["goalie"]
WORK_PX = 420
F_PHOTO = 26 * math.hypot(4284, 5712) / 43.27
F_VIDEO = (2600.0, 3600.0)
# fitting views: (set, id). All are free of fingers (warm pixels kept in both masks).
FIT_VIEWS = {
    "fit": ["goalie-photo-front", "goalie-photo-front-oblique", "goalie-photo-back", "goalie-photo-side", "goalie-video-t00.50",
            "goalie-video-t05.00", "goalie-video-t07.75", "goalie-video-t12.25"],
    "heldout": ["goalie-photo-top", "goalie-video-t16.75", "goalie-photo-lying-back", "goalie-photo-lying-back-2",
                "goalie-photo-underside"],
}


def load_mesh(path=MESH):
    d = np.load(path)
    return d["verts"].astype(float), d["tris"], d["labels"], [str(k) for k in d["keys"]]


def start_cameras():
    cams = {}
    for tag, ids in FIT_VIEWS.items():
        f = REPO / "validation" / "players" / ("goalie-fit.json" if tag == "fit" else "goalie-heldout-fit.json")
        views = json.loads(f.read_text())["views"]
        for i in ids:
            cams[i] = list(views[i]["params"])
    return cams


class View:
    def __init__(self, vid):
        self.id = vid
        self.rgb, self.s, self.crop, self.full = fv.load_view(vid, WORK_PX)
        self.ref = fv.figure_mask(self.rgb, include_warm=True)
        r = self.ref.astype(np.uint8)
        # signed distance to the photo silhouette (px): > 0 outside the figure
        self.sd = cv2.distanceTransform(1 - r, cv2.DIST_L2, 5) - cv2.distanceTransform(r, cv2.DIST_L2, 5)
        self.gx = cv2.Sobel(self.sd, cv2.CV_32F, 1, 0, ksize=3) / 8
        self.gy = cv2.Sobel(self.sd, cv2.CV_32F, 0, 1, ksize=3) / 8
        self.video = "video" in vid

    def mask(self, verts, tris, keep, p):
        return fv.model_mask(verts, tris, keep, p, TARGET, self.ref.shape, self.full, self.crop, self.s)


VIEWS = {}
G = {}


def _init(ids):
    for i in ids:
        VIEWS[i] = View(i)


def refit(args):
    """Powell refinement of one camera from its current parameters (same bounds as fit-figure-views.py)."""
    vid, p0, verts, tris, keep, maxfev = args
    vw = VIEWS.get(vid) or VIEWS.setdefault(vid, View(vid))
    x0 = np.array(p0, float)
    scl = np.array([0.03, 0.03, 0.03, 0.006, 0.006, 0.02 * x0[5], 0.02 * x0[6]])

    def par(z):
        p = x0 + z * scl
        p[6] = min(max(p[6], F_VIDEO[0]), F_VIDEO[1]) if vw.video else F_PHOTO
        return p

    r = minimize(lambda z: 1 - fv.iou(vw.mask(verts, tris, keep, par(z)), vw.ref), np.zeros(7), method="Powell",
                 options={"xtol": 1e-3, "ftol": 1e-4, "maxfev": maxfev})
    p = par(r.x)
    return vid, p.tolist(), fv.iou(vw.mask(verts, tris, keep, p), vw.ref)


def vertex_normals(v, t):
    n = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    vn = np.zeros_like(v)
    for k in range(3):
        np.add.at(vn, t[:, k], n)
    return vn / (np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12)


class Lattice:
    def __init__(self, lo, hi, spacing):
        self.h = float(spacing)
        self.lo = np.asarray(lo, float) - 1.5 * self.h
        self.n = np.ceil((np.asarray(hi, float) + 1.5 * self.h - self.lo) / self.h).astype(int) + 1
        self.N = int(np.prod(self.n))

    def idx(self, i, j, k):
        return (i * self.n[1] + j) * self.n[2] + k

    def weights(self, x):
        """Sparse trilinear interpolation matrix (len(x) x N)."""
        g = (x - self.lo) / self.h
        i0 = np.clip(np.floor(g).astype(int), 0, self.n - 2)
        f = g - i0
        rows, cols, vals = [], [], []
        r = np.arange(len(x))
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1):
                    w = (f[:, 0] if a else 1 - f[:, 0]) * (f[:, 1] if b else 1 - f[:, 1]) * (f[:, 2] if c else 1 - f[:, 2])
                    rows.append(r)
                    cols.append(self.idx(i0[:, 0] + a, i0[:, 1] + b, i0[:, 2] + c))
                    vals.append(w)
        return sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(len(x), self.N))

    def laplacian(self):
        I, J, K = np.meshgrid(*[np.arange(m) for m in self.n], indexing="ij")
        rows, cols = [], []
        for ax in range(3):
            sl = [slice(None)] * 3
            sl[ax] = slice(0, -1)
            a = self.idx(I[tuple(sl)], J[tuple(sl)], K[tuple(sl)]).ravel()
            d = [0, 0, 0]
            d[ax] = 1
            b = self.idx(I[tuple(sl)] + d[0], J[tuple(sl)] + d[1], K[tuple(sl)] + d[2]).ravel()
            rows += [a, b]
            cols += [b, a]
        A = sp.csr_matrix((np.ones(sum(len(r) for r in rows)), (np.concatenate(rows), np.concatenate(cols))), shape=(self.N, self.N))
        return sp.diags(np.asarray(A.sum(1)).ravel()) - A


def kabsch(P, Q):
    """Rigid transform (R, t) taking points P onto Q (least squares)."""
    pc, qc = P.mean(0), Q.mean(0)
    U, _s, Vt = np.linalg.svd((P - pc).T @ (Q - qc))
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T
    return R, qc - R @ pc


def rigid_groups(tris, labels, keys):
    """Vertex index sets that move rigidly: the tan stick."""
    tan = np.unique(tris[labels == keys.index("stick_tan")])
    return [tan] if len(tan) else []


def warp(v0, W, D, groups):
    v = v0 + W @ D
    for g in groups:  # the stick stays flat on the ice: rigid motion in plan only (turn about z, slide in x/y)
        P, Q = v0[g].copy(), v[g].copy()
        P[:, 2] = Q[:, 2] = 0.0
        R, t = kabsch(P, Q)
        z = v0[g, 2].copy()
        v[g] = v0[g] @ R.T + t
        v[g, 2] = z
    return v


def fixed_masks(v0, tris, labels, keys, socket):
    r = np.hypot(v0[:, 0], v0[:, 1])
    bore = np.zeros(len(v0), bool)
    bore[np.unique(tris[labels == keys.index("socket_bore")])] = True
    sock = bore | ((v0[:, 2] <= socket["height"] + 0.2) & (r <= socket["r_bottom"] + socket["flare"] + 0.3))
    ground = v0[:, 2] < 0.3
    top = v0[:, 2] > v0[:, 2].max() - 0.4
    return sock, ground, top


def rim_samples(vw, v, vn, tris, keep, p, max_px, min_align):
    """Rim vertices of the model silhouette at this view -> (vertex ids, unit normals, wanted normal shift in mold units)."""
    R, C, f = fv.camera(p, TARGET)
    uv, z = fv.project(v, p, TARGET, vw.full, vw.crop, vw.s)
    H, Wd = vw.ref.shape
    m = vw.mask(v, tris, keep, p).astype(np.uint8)
    din = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    x = np.clip(np.round(uv[:, 0]).astype(int), 0, Wd - 1)
    y = np.clip(np.round(uv[:, 1]).astype(int), 0, H - 1)
    inside = (uv[:, 0] > 2) & (uv[:, 0] < Wd - 3) & (uv[:, 1] > 2) & (uv[:, 1] < H - 3)
    view = C - v
    view /= np.linalg.norm(view, axis=1, keepdims=True)
    cosv = (vn * view).sum(1)
    rim = inside & (din[y, x] <= 2.0) & (np.abs(cosv) < 0.35)
    used = np.zeros(len(v), bool)
    used[np.unique(tris[keep])] = True
    rim &= used
    ids = np.nonzero(rim)[0]
    nc = vn[ids] @ R.T  # camera frame: x right, y down
    ni = nc[:, :2] / (np.linalg.norm(nc[:, :2], axis=1, keepdims=True) + 1e-9)
    sd = vw.sd[y[ids], x[ids]]
    align = vw.gx[y[ids], x[ids]] * ni[:, 0] + vw.gy[y[ids], x[ids]] * ni[:, 1]
    ok = (np.abs(sd) <= max_px) & (align >= min_align)
    px_per_unit = f * vw.s / z[ids]
    return ids[ok], vn[ids][ok], (-sd / px_per_unit)[ok], align[ok]


def fit(a):
    v0, tris, labels, keys = load_mesh()
    mold = json.loads((REPO / "data" / "figure-molds.json").read_text())["goalie"]
    keep = labels != keys.index("stick_metal")
    ids = [i for t in FIT_VIEWS.values() for i in t]
    _init(ids)
    cams = start_cameras()
    lat = Lattice(v0.min(0), v0.max(0), a.spacing)
    W = lat.weights(v0)
    L = lat.laplacian()
    LtL = (L.T @ L).tocsr()
    D = np.zeros((lat.N, 3))
    groups = rigid_groups(tris, labels, keys)
    sock, ground, top = fixed_masks(v0, tris, labels, keys, mold["socket"])
    Z = sp.csr_matrix((lat.N, lat.N))
    eye = sp.identity(lat.N, format="csr")

    def score(v):
        return {i: fv.iou(VIEWS[i].mask(v, tris, keep, cams[i]), VIEWS[i].ref) for i in ids}

    pool = Pool(4, initializer=_init, initargs=(ids,))

    def refit_all(v, maxfev):
        for vid, p, _s in pool.map(refit, [(i, cams[i], v, tris, keep, maxfev) for i in ids]):
            cams[vid] = p

    v = v0.copy()
    refit_all(v, 250)  # same start for the unwarped mold: cameras refined by this fitter first
    start = score(v)
    log = [{"iter": 0, "mean_iou": float(np.mean(list(start.values())))}]
    print("start", round(log[0]["mean_iou"], 4))
    for it in range(1, a.iters + 1):
        vn = vertex_normals(v, tris)
        rows_n, rows_i, rhs, wts = [], [], [], []
        for i in ids:
            vi, n, d, al = rim_samples(VIEWS[i], v, vn, tris, keep, cams[i], a.max_px, 0.4)
            rows_i.append(vi)
            rows_n.append(n)
            rhs.append(np.clip(d, -a.step, a.step))
            wts.append(al / math.sqrt(max(len(vi), 1)))  # every view counts the same
        vi, n, d, w = np.concatenate(rows_i), np.concatenate(rows_n), np.concatenate(rhs), np.concatenate(wts)
        w = w / w.mean()
        Ws = W[vi]
        A = sp.hstack([sp.diags(w * n[:, k]) @ Ws for k in range(3)]).tocsr()
        b = w * d
        # hard-ish constraints on the TOTAL field: socket fixed, ice contact and mask top keep their height
        cons, crhs = [], []
        Wk = W[sock]
        cur = Wk @ D
        for k in range(3):
            cons.append(sp.hstack([Wk if j == k else sp.csr_matrix(Wk.shape) for j in range(3)]))
            crhs.append(-cur[:, k])
        for msk in (ground, top):
            Wk = W[msk]
            cons.append(sp.hstack([sp.csr_matrix(Wk.shape), sp.csr_matrix(Wk.shape), Wk]))
            crhs.append(-(Wk @ D)[:, 2])
        Cm = sp.vstack(cons).tocsr() * a.w_fix
        cr = np.concatenate(crhs) * a.w_fix
        # smoothness and size of the total field D + dD
        Sm = sp.block_diag([LtL] * 3).tocsr() * (a.w_smooth * len(b) / lat.N)
        Mg = sp.identity(3 * lat.N, format="csr") * (a.w_size * len(b) / lat.N)
        Dv = D.T.ravel()  # component-major, matches hstack order
        lhs = (A.T @ A + Cm.T @ Cm + Sm + Mg).tocsc()
        rh = A.T @ b + Cm.T @ cr - Sm @ Dv - Mg @ Dv
        dD = spsolve(lhs, rh)
        D = D + dD.reshape(3, lat.N).T
        v = warp(v0, W, D, groups)
        if it % a.refit_every == 0 or it == a.iters:
            refit_all(v, 250 if it < a.iters else 500)
        sc = score(v)
        log.append({"iter": it, "mean_iou": float(np.mean(list(sc.values()))), "rim_samples": int(len(b)),
                    "rms_residual_units": float(np.sqrt(np.mean(d ** 2))), "max_shift_units": float(np.abs(W @ D).max())})
        print(it, {k: round(x, 4) if isinstance(x, float) else x for k, x in log[-1].items()}, flush=True)
    pool.close()
    final = score(v)
    u = W @ D
    spec = {
        "description": "Smooth displacement field that bends the parametric goalie mold toward the user's photo silhouettes "
                       "(scripts/goalie-silhouette-warp.py, docs/goalie-warp.md). x -> x + u(x), trilinear on the lattice, mold units; "
                       "the tan stick moves rigidly in plan (best planar rigid fit of its warped vertices; heights unchanged).",
        "status": "proposed",
        "source": "user photos IMG_2564-2572 and video IMG_2573 of the Sweden goalie no. 30 (references/players_images, frames in references/derived/players)",
        "frame": "goalie mold frame, mold units (data/figure-molds.json goalie)",
        "lattice": {"origin": lat.lo.round(6).tolist(), "spacing": lat.h, "shape": lat.n.tolist(), "order": "index = (i*ny + j)*nz + k"},
        "fixed": "mount socket (no shift); vertices on the ice (z shift 0); mask top (z shift 0: height and scale k unchanged)",
        "settings": {"iters": a.iters, "step_units": a.step, "max_px": a.max_px, "w_smooth": a.w_smooth, "w_size": a.w_size,
                     "w_fix": a.w_fix, "refit_every": a.refit_every, "work_px": WORK_PX},
        "fit_views": FIT_VIEWS,
        "result": {"mean_iou_before": round(log[0]["mean_iou"], 4), "mean_iou_after": round(float(np.mean(list(final.values()))), 4),
                   "iou_before": {k: round(x, 4) for k, x in start.items()}, "iou_after": {k: round(x, 4) for k, x in final.items()},
                   "shift_units": {"max": round(float(np.linalg.norm(u, axis=1).max()), 3), "mean": round(float(np.linalg.norm(u, axis=1).mean()), 3)},
                   "note": "cameras refitted by this script for both shapes; fit-figure-views.py gives the reported scores"},
        "log": log,
        "displacements": np.round(D, 4).tolist(),
    }
    SPEC.parent.mkdir(parents=True, exist_ok=True)
    SPEC.write_text(json.dumps(spec) + "\n")
    np.savez_compressed(REPO / "out" / "figures" / "goalie-warp.npz", verts=v, tris=tris, labels=labels, keys=np.array(keys))
    (REPO / "out" / "figures" / "goalie-warp-cameras.json").write_text(json.dumps(cams))
    print("mean IoU", spec["result"]["mean_iou_before"], "->", spec["result"]["mean_iou_after"], "shift", spec["result"]["shift_units"])


def warp_vertices(v0, tris=None, labels=None, keys=None, spec=None, rigid=None):
    """Apply data/figures/goalie-warp.json to mold-unit vertices (used by the Blender builders).
    rigid: list of vertex-index arrays that move rigidly (default: the tan stick from tris/labels)."""
    spec = spec or json.loads(SPEC.read_text())
    lat = Lattice.__new__(Lattice)
    lat.h = spec["lattice"]["spacing"]
    lat.lo = np.array(spec["lattice"]["origin"])
    lat.n = np.array(spec["lattice"]["shape"])
    lat.N = int(np.prod(lat.n))
    D = np.array(spec["displacements"])
    return warp(np.asarray(v0, float), lat.weights(np.asarray(v0, float)), D, rigid if rigid is not None else rigid_groups(tris, labels, keys))


def apply(_a):
    v0, tris, labels, keys = load_mesh()
    v = warp_vertices(v0, tris, labels, keys)
    np.savez_compressed(REPO / "out" / "figures" / "goalie-warp.npz", verts=v, tris=tris, labels=labels, keys=np.array(keys))
    print("warped", len(v), "vertices; bbox", v.min(0).round(2), v.max(0).round(2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fit", "apply"])
    ap.add_argument("--iters", type=int, default=30)
    ap.add_argument("--spacing", type=float, default=2.5)
    ap.add_argument("--step", type=float, default=0.6, help="largest wanted normal shift per iteration (mold units)")
    ap.add_argument("--max-px", type=float, default=16.0, help="ignore rim points farther than this from the photo silhouette")
    ap.add_argument("--w-smooth", type=float, default=0.4)
    ap.add_argument("--w-size", type=float, default=0.002)
    ap.add_argument("--w-fix", type=float, default=30.0)
    ap.add_argument("--refit-every", type=int, default=3)
    a = ap.parse_args()
    {"fit": fit, "apply": apply}[a.cmd](a)


if __name__ == "__main__":
    main()
