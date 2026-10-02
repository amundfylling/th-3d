"""Skater face envelope as one continuous lofted surface (pure numpy; used by figure_molds.py and by the face
fitting script). Round 11 (2026-10-02).

The face is described by a closed SIDE PROFILE in a local (u, z) frame - u forward from a pivot, z up (mold
units) - traced around the face: hidden top inside the helmet, brow under the helmet edge, front plane, chin,
jaw underside, hidden back inside the neck. Each profile point carries a half-width W (lateral extent) and an
edge rounding R. The surface is the profile extruded sideways with rounded edges:

    point(i, t) = Q_i - n_i * R_i * (1 - |cos t|^e) + v * W_i * sign(sin t) |sin t|^e,   t in [-pi/2, pi/2]

(Q_i profile point, n_i its outward normal in the (u, z) plane, v the lateral axis, e = 2/n superellipse
exponent: n > 2 keeps the cheek planes flat with rounded edges). The two side loops (t = +-pi/2) are closed with
fans. The frame is turned by `yaw_deg` about the vertical axis through `pivot` (x, y); `pitch_deg` leans the
profile about the pivot in its own plane. Small lateral asymmetry: `w_bias` scales W on the +v side.

Optional relief (kept subtle): a nose ridge and a mouth crease displace front-facing points along their
normal with smooth Gaussian bumps in (z, v); no separate primitives.
"""
from __future__ import annotations

import math

import numpy as np


def _resample(pts, n):
    p = np.asarray(pts, float)
    p = np.vstack([p, p[:1]])
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.r_[0, np.cumsum(seg)]
    t = np.linspace(0, s[-1], n, endpoint=False)
    out = np.stack([np.interp(t, s, p[:, k]) for k in range(p.shape[1])], 1)
    return out


def _smooth_closed(p, k=2, it=2):
    for _ in range(it):
        q = p.copy()
        for d in range(1, k + 1):
            q += np.roll(p, d, 0) + np.roll(p, -d, 0)
        p = q / (2 * k + 1)
    return p


def face_loft_mesh(spec: dict, n_profile: int = 120, n_lat: int = 24):
    """spec: profile [[u, z, W, R], ...] (closed, ordered), pivot [x, y], yaw_deg, pitch_deg, exponent n,
    w_bias, relief (optional). Returns verts (N, 3) mold units and quad/tri faces (list of tuples)."""
    prof = np.asarray(spec["profile"], float)
    P = _resample(prof, n_profile)
    P = _smooth_closed(P, k=2, it=spec.get("smooth", 2))
    # widths and roundings get a stronger smoothing than the outline: a kink in W along the profile would
    # otherwise show as a radial crease across the cheek
    WR = _smooth_closed(P[:, 2:].copy(), k=4, it=spec.get("w_smooth", 4))
    uz, W, R = P[:, :2], WR[:, 0], WR[:, 1]
    # outward normal of the closed (u, z) curve (counter-clockwise -> outward = rotate tangent by -90 deg)
    tang = np.roll(uz, -1, 0) - np.roll(uz, 1, 0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    area = 0.5 * np.sum(uz[:, 0] * np.roll(uz[:, 1], -1) - np.roll(uz[:, 0], -1) * uz[:, 1])
    nrm = np.stack([tang[:, 1], -tang[:, 0]], 1) * (1 if area > 0 else -1)
    e = 2.0 / spec.get("exponent", 3.0)
    ts = np.linspace(-math.pi / 2, math.pi / 2, n_lat)
    pitch = math.radians(spec.get("pitch_deg", 0.0))
    yaw = math.radians(spec.get("yaw_deg", 0.0))
    px, py = spec["pivot"]
    pz = spec.get("pivot_z", 38.0)
    bias = spec.get("w_bias", 1.0)
    rel = spec.get("relief", {})
    verts = []
    for i in range(len(P)):
        for t in ts:
            c, s = abs(math.cos(t)) ** e, math.copysign(abs(math.sin(t)) ** e, t)
            inset = R[i] * (1 - c)
            u, z = uz[i] - nrm[i] * inset
            w = W[i] * (bias if s > 0 else 1.0)
            v = w * s
            # relief: only on front-facing profile points (normal mostly +u), fading toward the sides
            if rel and nrm[i][0] > 0.6:
                d = 0.0
                for b in rel.get("bumps", []):  # {z, v, sz, sv, h}: + outward, - inward (crease)
                    d += b["h"] * math.exp(-((z - b["z"]) / b["sz"]) ** 2 - ((v - b["v"]) / b["sv"]) ** 2)
                u += d * nrm[i][0] * c
                z += d * nrm[i][1] * c
            # pitch about (0, pz) in the (u, z) plane, then yaw about the vertical through the pivot
            uu = u * math.cos(pitch) - (z - pz) * math.sin(pitch)
            zz = pz + u * math.sin(pitch) + (z - pz) * math.cos(pitch)
            x = px + uu * math.cos(yaw) - v * math.sin(yaw)
            y = py + uu * math.sin(yaw) + v * math.cos(yaw)
            verts.append((x, y, zz))
    verts = np.array(verts)
    n, m = len(P), n_lat
    faces = []
    for i in range(n):
        j = (i + 1) % n
        for k in range(m - 1):
            faces.append((i * m + k, j * m + k, j * m + k + 1, i * m + k + 1))
    # side caps: concentric rings shrinking toward the loop centre, bulging slightly outward (a gently domed
    # cheek on a regular grid; a fan to the centroid creases under smooth shading)
    J = int(spec.get("cap_rings", 6))
    dome = spec.get("cheek_dome", 0.35)
    for k in (0, m - 1):
        ring = np.array([i * m + k for i in range(n)])
        edge = verts[ring]
        sgn = 1.0 if k == m - 1 else -1.0
        # local frame: lateral axis (unit, after yaw) and the loop centre
        lat = np.array([-math.sin(yaw), math.cos(yaw), 0.0])
        ctr = edge.mean(0)
        prev = ring
        for j in range(1, J + 1):
            sj = 1.0 - j / (J + 0.5)
            off = (edge - ctr) @ lat
            plane = edge - np.outer(off, lat)
            mid = (plane - ctr) * sj + ctr
            # round the inner rings progressively (a cone over a cornered loop creases along its corners)
            mid = _smooth_closed(mid, k=3, it=3 * j)
            lat_off = off * sj ** 2 + off.mean() * (1 - sj ** 2) + sgn * dome * (1 - sj ** 2)
            pts = mid + np.outer(lat_off, lat)
            base = len(verts)
            verts = np.vstack([verts, pts])
            cur = np.arange(base, base + n)
            for i in range(n):
                a, b = (i + 1) % n, i
                q = (prev[b], prev[a], cur[a], cur[b])
                faces.append(q[::-1] if k == 0 else q)
            prev = cur
        c = len(verts)
        verts = np.vstack([verts, verts[prev].mean(0)])
        for i in range(n):
            a, b = prev[i], prev[(i + 1) % n]
            faces.append((b, a, c) if k == 0 else (a, b, c))
    # outward-facing winding (positive enclosed volume) regardless of the profile direction or yaw
    T = triangulate(faces)
    a, b, c = verts[T[:, 0]], verts[T[:, 1]], verts[T[:, 2]]
    if np.einsum("ij,ij->i", a, np.cross(b, c)).sum() < 0:
        faces = [tuple(reversed(f)) for f in faces]
    return verts, faces


def triangulate(faces):
    tris = []
    for f in faces:
        if len(f) == 3:
            tris.append(f)
        else:
            tris += [(f[0], f[1], f[2]), (f[0], f[2], f[3])]
    return np.array(tris, np.int32)
