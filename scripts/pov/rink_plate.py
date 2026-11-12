"""Empty-rink plate for one POV game (step 5): the ice seen from straight above at 1 px/mm, as the per-pixel median
of many solved frames warped onto the ice plane. Figures move along their slots during a game, so the median shows
the empty ice in most places; figures that rarely move (goalies) and the plexiglass reflections stay partly.
The plate stands in for NM26's background.png: per frame it is warped back into the POV camera (plate_in_view) to
give the colour difference that the localiser and the puck detector use.
Usage: python3 scripts/pov/rink_plate.py <video> <track.npz> <out.png> [n_frames]
"""
import os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from pov_common import K_of, read_frames, project, W_PX, H_PX
import camera_fit as cf

X0, X1, Y0, Y1 = -430, 430, -242, 242       # plate extent, world mm (inner boundary is +-422.7 x +-234.9)
PW, PH = X1 - X0, Y1 - Y0


def plate_grid():
    u, v = np.meshgrid(np.arange(PW) + 0.5, np.arange(PH) + 0.5)
    return np.c_[(X0 + u).ravel(), (Y1 - v).ravel(), np.zeros(u.size)]   # image row 0 = +y side


GRID = plate_grid()


def to_plate(img, rv, tv, K, D):
    q = project(GRID, rv, tv, K, D).reshape(PH, PW, 2).astype(np.float32)
    return cv2.remap(img, q[..., 0], q[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0), \
        ((q[..., 0] >= 0) & (q[..., 0] < W_PX - 1) & (q[..., 1] >= 0) & (q[..., 1] < H_PX - 1))


def world_of_pixels(rv, tv, K, D, z=0.0):
    """World point on the plane z for every image pixel (H x W x 2) and a validity mask."""
    u, v = np.meshgrid(np.arange(W_PX, dtype=np.float64), np.arange(H_PX, dtype=np.float64))
    n = cv2.undistortPoints(np.c_[u.ravel(), v.ravel()].reshape(-1, 1, 2), K, D)[:, 0]
    Rm = cv2.Rodrigues(np.asarray(rv, float))[0]
    C = -Rm.T @ np.asarray(tv, float)
    d = np.c_[n, np.ones(len(n))] @ Rm
    s = (z - C[2]) / d[:, 2]
    P = C[:2] + s[:, None] * d[:, :2]
    return P.reshape(H_PX, W_PX, 2), (s > 0).reshape(H_PX, W_PX)


def plate_in_view(plate, rv, tv, K, D):
    P, ok = world_of_pixels(rv, tv, K, D)
    mx = (P[..., 0] - X0 - 0.5).astype(np.float32); my = (Y1 - P[..., 1] - 0.5).astype(np.float32)
    out = cv2.remap(plate, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    inside = ok & (mx >= 0) & (mx < PW - 1) & (my >= 0) & (my < PH - 1)
    return out, inside


if __name__ == "__main__":
    video, track, out = sys.argv[1:4]
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 120
    T = np.load(track); A = T["rows"]; intr = T["intr"]
    K, D = K_of(intr[0]), cf.dist_of(intr[1:])
    good = A[(A[:, 11] > 0) & (A[:, 13] >= 0.98)]
    sel = good[np.linspace(0, len(good) - 1, n).astype(int)]
    frs = read_frames(video, sel[:, 0].astype(int))
    stack, masks = [], []
    for r in sel:
        w, m = to_plate(frs[int(r[0])], r[1:4], r[4:7], K, D)
        stack.append(w); masks.append(m)
    S = np.array(stack, np.float32); M = np.array(masks)
    S[~M] = np.nan
    plate = np.nan_to_num(np.nanmedian(S, axis=0)).astype(np.uint8)
    cv2.imwrite(out, plate)
    print("plate from", len(sel), "frames ->", out)
