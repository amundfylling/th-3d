"""Camera fitting against the rink model for the POV pipeline (steps 3 and 4).

Targets: thin dark lines in the image (pov_common.line_mask): the skater slot centrelines and the inner board
boundary (its dark foot strip). Each model point is matched to the nearest line pixel within a shrinking radius
(ICP), and the camera is refitted by robust least squares (soft-L1, 1.5 px scale) each round.
Intrinsics: f (square px), principal point fixed at the image centre (ASSUMED), radial k1, k2 (k3, p1, p2 = 0).
"""
import numpy as np
import cv2
from scipy.optimize import least_squares
from scipy.spatial import cKDTree

from pov_common import K_of, board_points, line_mask, project, slot_points, to3, W_PX, H_PX

SLOT3 = to3(slot_points(4.0))
BOARD3 = to3(board_points(6.0))
MODEL = np.r_[SLOT3, BOARD3]
RADII = (24, 16, 11, 8, 6, 5, 4, 4)


def dist_of(k):
    return np.array([k[0], k[1], 0, 0, 0], float)


class Target:
    def __init__(self, bgr, roi=None):
        """roi: optional bool mask; line pixels outside it are ignored (neighbouring tables, people)."""
        m = line_mask(bgr)
        if roi is not None:
            m &= roi
        ys, xs = np.nonzero(m)
        self.px = np.c_[xs, ys].astype(float)
        self.tree = cKDTree(self.px if len(self.px) else np.zeros((1, 2)))


class IceTarget:
    """Outer contour of the bright ice region that best overlaps a predicted ice mask: the coarse target for the
    board boundary (the rink's dark foot strip separates the ice from the white table around it)."""

    def __init__(self, bgr, pred_mask):
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        bright = ((hsv[..., 2] > 140) & (hsv[..., 1] < 70)).astype(np.uint8)
        bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        bright[line_mask(bgr)] = 0
        n, lab, stats, _ = cv2.connectedComponentsWithStats(bright, connectivity=4)
        ov = np.bincount(lab[pred_mask], minlength=n); ov[0] = 0
        k = int(np.argmax(ov))
        comp = (lab == k).astype(np.uint8)
        comp = cv2.morphologyEx(comp, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
        cs, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        c = max(cs, key=cv2.contourArea)[:, 0].astype(float)
        self.mask = comp.astype(bool)
        self.iou = float((self.mask & pred_mask).sum() / max((self.mask | pred_mask).sum(), 1))
        self.px = c
        self.tree = cKDTree(c)


def _match(tgt, q, rad):
    q = np.nan_to_num(q, nan=-1e6, posinf=-1e6, neginf=-1e6)
    inside = (q[:, 0] > 2) & (q[:, 0] < W_PX - 2) & (q[:, 1] > 2) & (q[:, 1] < H_PX - 2)
    d, k = tgt.tree.query(q, distance_upper_bound=rad)
    ok = np.isfinite(d) & inside
    return ok, k


def fit(targets, poses, intr, free_intr=True, radii=RADII, model=MODEL, return_stats=False):
    """targets: list of Target; poses: list of (rvec, tvec); intr: [f, k1, k2]. Returns poses, intr, stats."""
    poses = [(np.asarray(r, float).ravel(), np.asarray(t, float).ravel()) for r, t in poses]
    intr = np.asarray(intr, float)
    n = len(targets)
    for rad in radii:
        matches = []
        K, D = K_of(intr[0]), dist_of(intr[1:])
        for tgt, (rv, tv) in zip(targets, poses):
            q = project(model, rv, tv, K, D)
            ok, k = _match(tgt, q, rad)
            matches.append((ok, tgt.px[k[ok]] if ok.any() else np.zeros((0, 2))))

        def resid(x):
            it = x[:3] if free_intr else intr
            K, D = K_of(it[0]), dist_of(it[1:])
            off = 3 if free_intr else 0
            r = []
            for i, (ok, tp) in enumerate(matches):
                p = x[off + 6 * i: off + 6 * i + 6]
                q = project(model[ok], p[:3], p[3:], K, D)
                r.append(np.nan_to_num((q - tp).ravel(), nan=1e3, posinf=1e3, neginf=-1e3))
            if free_intr:  # weak prior keeps k1, k2 bounded when few points reach the frame edge
                r.append([x[1] * 2.0, x[2] * 2.0])
            return np.concatenate(r)

        x0 = np.concatenate(([intr] if free_intr else []) + [np.r_[rv, tv] for rv, tv in poses])
        sol = least_squares(resid, x0, loss="soft_l1", f_scale=1.5, x_scale="jac", max_nfev=200)
        x = sol.x
        if free_intr:
            intr = x[:3]
        off = 3 if free_intr else 0
        poses = [(x[off + 6 * i: off + 6 * i + 3], x[off + 6 * i + 3: off + 6 * i + 6]) for i in range(n)]
    # final stats with the last radius
    K, D = K_of(intr[0]), dist_of(intr[1:])
    stats = []
    for tgt, (rv, tv) in zip(targets, poses):
        q = np.nan_to_num(project(model, rv, tv, K, D), nan=-1e6, posinf=-1e6, neginf=-1e6)
        inside = (q[:, 0] > 2) & (q[:, 0] < W_PX - 2) & (q[:, 1] > 2) & (q[:, 1] < H_PX - 2)
        d, _ = tgt.tree.query(q[inside]) if inside.any() else (np.array([99.0]), None)
        stats.append({"median_px": float(np.median(d)), "p90_px": float(np.percentile(d, 90)),
                      "within2px": float(np.mean(d < 2.0)), "points_in_frame": int(inside.sum())})
    return poses, intr, stats


def solve_frame(bgr, pose0, intr, coarse=True):
    """Robust single-frame solve from a rough pose (a few degrees off): ice outline first, then slots + board on
    line pixels inside the (grown) ice region. Returns pose, stats dict."""
    from pov_common import ice_polygon_mask
    K, D = K_of(intr[0]), dist_of(intr[1:])
    pose = pose0
    if coarse:
        pred = ice_polygon_mask(pose[0], pose[1], K, D)
        it = IceTarget(bgr, pred)
        poses, _, _ = fit([it], [pose], intr, free_intr=False, radii=(80, 50, 30, 18, 10, 6), model=BOARD3)
        pose = poses[0]
    roi = cv2.dilate(ice_polygon_mask(pose[0], pose[1], K, D).astype(np.uint8), np.ones((21, 21), np.uint8)).astype(bool)
    poses, _, st = fit([Target(bgr, roi)], [pose], intr, free_intr=False, radii=(10, 6, 4, 3))
    pose = poses[0]
    q = project(BOARD3, pose[0], pose[1], K, D)
    st[0]["board_in_frame"] = float(np.mean((q[:, 0] >= 0) & (q[:, 0] < W_PX) & (q[:, 1] >= 0) & (q[:, 1] < H_PX)))
    return pose, st[0]
