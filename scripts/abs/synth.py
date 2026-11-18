"""Analysis-by-synthesis core: soft-silhouette rendering of the repo's figure meshes with the NM26 reference camera.

Figure pose = slot position u (fraction of centreline arc length) + heading theta (deg) about the fixture axis
(docs/pose.md, scripts/table_common.py). Everything here is plain PyTorch on CPU.
"""
import sys, json
from pathlib import Path
import numpy as np, torch, trimesh
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import table_common as tc

HALF = (900, 360, 1900, 1000)  # crop of the reference frame (E half)
K, R, t = [torch.tensor(a, dtype=torch.float32) for a in tc.ref_camera()]
_mesh = {}


def points(kind, n=6000, seed=0):
    """Dense surface samples of the skater / goalie mold in pivot-local mm (+x heading, +y left, +z up)."""
    if (kind, n) in _mesh: return _mesh[(kind, n)]
    f = {"skater": "skater_stl_SWE", "goalie": "goalie_SWE"}[kind]
    m = trimesh.load(REPO / f"assets/figures/{f}.glb").to_geometry()
    P, _ = trimesh.sample.sample_surface(m, n, seed=seed)       # gltf Y-up metres
    L = np.c_[P[:, 0], -P[:, 2], P[:, 1]] * 1000.0               # -> pivot-local mm, z up
    _mesh[(kind, n)] = torch.tensor(L, dtype=torch.float32)
    return _mesh[(kind, n)]


class Slot:
    def __init__(self, pid):
        P = torch.tensor(tc.SLOT[pid], dtype=torch.float32); seg = (P[1:] - P[:-1]).norm(dim=1)
        self.P, self.acc = P, torch.cat([torch.zeros(1), seg.cumsum(0)]); self.L = float(self.acc[-1])

    def at(self, u):
        s = torch.clamp(u, 0.0, 1.0) * self.L
        k = torch.clamp(torch.searchsorted(self.acc, s.detach().reshape(-1), right=True) - 1, 0, len(self.acc) - 2)
        f = (s.reshape(-1) - self.acc[k]) / (self.acc[k + 1] - self.acc[k])
        return self.P[k] + f[:, None] * (self.P[k + 1] - self.P[k])


SLOTS = {p: Slot(p) for p in tc.SLOT}


def world_points(fid, u, theta_deg, n=6000):
    kind = "goalie" if fid.endswith("G") else "skater"
    V = points(kind, n)
    h = torch.deg2rad(tc.HOME[fid[0]] + theta_deg).reshape(())
    c, s = torch.cos(h), torch.sin(h)
    Rz = torch.stack([torch.stack([c, -s]), torch.stack([s, c])])
    xy = V[:, :2] @ Rz.T + SLOTS[fid].at(u.reshape(1))[0]
    return torch.cat([xy, V[:, 2:]], 1)


def project(W):
    X = W @ R.T + t; q = X @ K.T
    return q[:, :2] / q[:, 2:3]


def splat(q, shape, sigma=1.0):
    """Differentiable coverage: bilinear splat of the projected points, blurred, then 1-exp(-k d). q in crop px (x, y)."""
    H, Wd = shape
    x, y = q[:, 0], q[:, 1]
    x0, y0 = torch.floor(x), torch.floor(y); fx, fy = x - x0, y - y0
    img = torch.zeros(H * Wd)
    for dx, dy, w in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xi, yi = (x0 + dx).long(), (y0 + dy).long()
        ok = (xi >= 0) & (xi < Wd) & (yi >= 0) & (yi < H)
        img = img.index_add(0, (yi * Wd + xi)[ok], w[ok])
    img = img.reshape(1, 1, H, Wd)
    rad = int(3 * sigma); g = torch.exp(-torch.arange(-rad, rad + 1).float() ** 2 / (2 * sigma ** 2)); g = g / g.sum()
    img = torch.nn.functional.conv2d(img, g.view(1, 1, 1, -1), padding=(0, rad))
    img = torch.nn.functional.conv2d(img, g.view(1, 1, -1, 1), padding=(rad, 0))
    return 1 - torch.exp(-3.0 * img[0, 0])


def render(poses, shape, n=6000, sigma=1.0):
    """poses: {fid: (u, theta_deg)} (tensors). Returns the union soft silhouette (crop shape) and each figure's own."""
    per = {}
    for fid, (u, th) in poses.items():
        q = project(world_points(fid, u, th, n)) - torch.tensor(HALF[:2], dtype=torch.float32)
        per[fid] = splat(q, shape, sigma)
    S = 1 - torch.stack([1 - s for s in per.values()]).prod(0)
    return S, per
