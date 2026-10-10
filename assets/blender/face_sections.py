"""Skater face as a stack of horizontal cross-sections (pure numpy; used by figure_molds.py and the review scripts).
Round 12 (2026-10-02); replaces the round-11 side-profile extrusion (face_loft.py), which carried the nose-height
projection across the whole width of the face.

Local frame: u forward along the face centreline from `pivot` (x, y), v lateral (+v = the figure's left), z up
(mold units). Each level is a closed superellipse in (u, v): centre ((front + back) / 2, 0), half-depth
(front - back) / 2, half-width `half_width`, exponent `n_front` on the front half and `n_back` on the hidden back
half. The front therefore recedes continuously from the centreline toward the cheeks at every height; depth and
width vary independently. Level parameters are interpolated in z and smoothed.

Bottom: the lowest level is closed by a rounded edge of radius `bottom_round` (the section is inset in its own
plane while z drops), then capped. `pitch_deg` tilts the whole stack rigidly about
`pitch_origin` (u, z) in the (u, z) plane, front up: the photographed jaw line runs down from the chin to the
neck. (A shear of the lowest levels was tried
and rejected: it folds the cheek into a diagonal seam.) Top: capped inside the helmet (hidden).

`w_left` scales the half-width on the figure's left (+v) side only.

Relief (optional, kept on the centreline): `nose` {z0, z1, h, sigma}: forward bump between z0 and z1 with a
Gaussian lateral falloff, so it vanishes toward the cheeks; `mouth` {z, h, sz, sigma}: shallow crease.
The frame is turned by `yaw_deg` about the vertical through the pivot.
"""
from __future__ import annotations

import math

import numpy as np

KEYS = ("front", "back", "half_width", "n_front", "n_back")


def _levels(spec, dz=0.12):
    L = sorted(spec["levels"], key=lambda q: q["z"])
    zs = np.array([q["z"] for q in L])
    zf = np.arange(zs[0], zs[-1] + 1e-6, dz)
    cols = {}
    for k in KEYS:
        vals, last = [], spec.get(k, 2.0)
        for q in L:  # a level without a key inherits the previous level's value (or the spec default)
            last = q.get(k, last)
            vals.append(last)
        vals = np.array(vals, float)
        y = np.interp(zf, zs, vals)
        w = max(1, int(round(spec.get("z_smooth", 0.5) / dz)))  # moving-average smoothing, ends held
        if w > 1:
            pad = np.r_[np.full(w, y[0]), y, np.full(w, y[-1])]
            ker = np.ones(2 * w + 1) / (2 * w + 1)
            y = np.convolve(pad, ker, mode="same")[w:-w]
        cols[k] = y
    return zf, cols


def _section(F, B, W, nf, nb, m):
    t = np.linspace(0, 2 * math.pi, m, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    uc, a = (F + B) / 2, (F - B) / 2
    ef = np.where(c >= 0, 2.0 / nf, 2.0 / nb)
    u = uc + a * np.sign(c) * np.abs(c) ** ef
    v = W * np.sign(s) * np.abs(s) ** ef
    return np.stack([u, v], 1)


def _inset(P, d):
    """Offset a closed counter-clockwise (u, v) curve inward by d."""
    tg = np.roll(P, -1, 0) - np.roll(P, 1, 0)
    tg /= np.linalg.norm(tg, axis=1, keepdims=True)
    nrm = np.stack([tg[:, 1], -tg[:, 0]], 1)  # outward for counter-clockwise
    return P - nrm * d


def face_section_mesh(spec: dict, m: int = 72):
    """Returns verts (N, 3) in mold units and faces (quads + cap triangles), outward wound."""
    zf, C = _levels(spec)
    rel = spec.get("relief", {})
    nose, mouth = rel.get("nose"), rel.get("mouth")
    rings = []
    for i, z in enumerate(zf):
        P = _section(C["front"][i], C["back"][i], C["half_width"][i], C["n_front"][i], C["n_back"][i], m)
        P[:, 1] = np.where(P[:, 1] > 0, P[:, 1] * spec.get("w_left", 1.0), P[:, 1])  # lateral asymmetry
        rings.append((P, z, C["front"][i]))
    # rounded bottom edge: inset the lowest section while z drops (quarter circle of radius r)
    r = spec.get("bottom_round", 0.5)
    P0, z0, F0 = rings[0]
    low = []
    for phi in np.linspace(0, math.pi / 2, 7)[1:]:
        low.append((_inset(P0, r * (1 - math.cos(phi))), z0 - r * math.sin(phi), F0))
    rings = low[::-1] + rings
    zb = rings[0][1]
    yaw = math.radians(spec.get("yaw_deg", 0.0))
    pitch = math.radians(spec.get("pitch_deg", 0.0))
    cp, sp = math.cos(pitch), math.sin(pitch)
    pu0, pz0 = spec.get("pitch_origin", [0.0, zb])
    px, py = spec["pivot"]
    verts = []
    for P, z, F in rings:
        for (u, v) in P:
            uu = u
            if nose and u > 0:
                zt = (z - nose["z0"]) / max(1e-6, nose["z1"] - nose["z0"])
                if -0.4 < zt < 1.4:
                    prof = math.sin(math.pi * min(1.0, max(0.0, zt))) ** 0.6 if 0 <= zt <= 1 else 0.0
                    uu += nose["h"] * prof * math.exp(-(v / nose["sigma"]) ** 2)
            if mouth and u > 0:
                uu -= mouth["h"] * math.exp(-((z - mouth["z"]) / mouth["sz"]) ** 2 - (v / mouth["sigma"]) ** 2)
            zz = z
            if pitch:  # rigid tilt in the (u, z) plane about `pitch_origin` (front up / back down for pitch > 0)
                du, dzz = uu - pu0, zz - pz0
                uu, zz = pu0 + du * cp - dzz * sp, pz0 + dzz * cp + du * sp
            x = px + uu * math.cos(yaw) - v * math.sin(yaw)
            y = py + uu * math.sin(yaw) + v * math.cos(yaw)
            verts.append((x, y, zz))
    verts = np.array(verts)
    n = len(rings)
    faces = []
    for i in range(n - 1):
        for k in range(m):
            k2 = (k + 1) % m
            faces.append((i * m + k, i * m + k2, (i + 1) * m + k2, (i + 1) * m + k))
    for ring, top in ((0, False), (n - 1, True)):
        c = len(verts)
        idx = [ring * m + k for k in range(m)]
        verts = np.vstack([verts, verts[idx].mean(0)])
        for k in range(m):
            a, b = idx[k], idx[(k + 1) % m]
            faces.append((a, b, c) if top else (b, a, c))
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
