"""Shared helpers for fitting figure molds to the user's photos (scripts/fit-figure-views.py).

Segmentation: STIGA figure plastic is strongly saturated (blue, yellow, tan/skin) against a dark, low-
saturation table with bright unsaturated wood-grain highlights; the skater's metal stick is unsaturated and
is excluded from both masks. Camera: pinhole in full-frame pixels, principal point at the frame centre.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
# Fixed camera aim point per mold (mold units): cameras stay valid when the layout changes.
TARGET = {"skater": np.array([2.0, 4.0, 24.0]), "goalie": np.array([2.0, 7.0, 24.0])}
MANIFEST = json.loads((REPO / "references" / "derived" / "players" / "manifest.json").read_text())["items"]


def colour_classes(rgb: np.ndarray):
    """Boolean masks (blue, yellow, warm) for an RGB uint8 image."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(int)  # H 0-179, S, V 0-255
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    blue = (h >= 95) & (h <= 125) & (s >= 90) & (v >= 60)
    yellow = (h >= 15) & (h <= 35) & (s >= 120) & (v >= 90)
    warm = (h <= 14) | (h >= 170)
    warm = warm & (s >= 70) & (v >= 90)  # skin, tan goalie stick, fingers
    return blue, yellow, warm


def load_view(view_id: str, work_px: int = 520):
    """Crop image resized so its longer side is `work_px`; returns (rgb, scale, crop_box, full_size)."""
    it = MANIFEST[view_id]
    im = Image.open(REPO / it["file"]).convert("RGB")
    s = work_px / max(im.size)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    return np.asarray(im), s, it["crop_box_px"], it["full_size_px"]


def figure_mask(rgb: np.ndarray, include_warm: bool = True, exclude_polys=(), keep_components: int = 1):
    blue, yellow, warm = colour_classes(rgb)
    m = (blue | yellow | (warm if include_warm else False)).astype(np.uint8)
    for poly in exclude_polys:
        cv2.fillPoly(m, [np.asarray(poly, np.int32)], 0)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    order = 1 + np.argsort(-stats[1:, cv2.CC_STAT_AREA])
    out = np.zeros_like(m)
    for k in order[:keep_components]:
        out[lab == k] = 1
    # fill interior holes (dark seams, printed numbers)
    cnts, _ = cv2.findContours(out, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    filled = np.zeros_like(out)
    cv2.drawContours(filled, cnts, -1, 1, -1)
    return filled.astype(bool)


def look_at(C, T, roll):
    f = (T - C) / np.linalg.norm(T - C)
    up = np.array([0.0, 0.0, 1.0])
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    R = np.stack([r, -u, f])  # camera x right, y down, z forward
    cr, sr = math.cos(roll), math.sin(roll)
    return np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]]) @ R


def camera(params, target):
    """params: azimuth, elevation, roll, pan, tilt (rad), distance (mm), focal (px)."""
    az, el, roll, pan, tilt, dist, f = params
    C = target + dist * np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    R = look_at(C, target, roll)
    cp, sp, ct, st = math.cos(pan), math.sin(pan), math.cos(tilt), math.sin(tilt)
    Rpan = np.array([[cp, 0, -sp], [0, 1, 0], [sp, 0, cp]])
    Rtilt = np.array([[1, 0, 0], [0, ct, -st], [0, st, ct]])
    return Rtilt @ Rpan @ R, C, f


def project(verts, params, target, full_size, crop_box, scale):
    R, C, f = camera(params, target)
    pc = (verts - C) @ R.T
    z = np.maximum(pc[:, 2], 1e-3)
    u = f * pc[:, 0] / z + full_size[0] / 2
    v = f * pc[:, 1] / z + full_size[1] / 2
    return np.stack([(u - crop_box[0]) * scale, (v - crop_box[1]) * scale], 1), pc[:, 2]


def model_mask(verts, tris, keep, params, target, shape, full_size, crop_box, scale):
    uv, _z = project(verts, params, target, full_size, crop_box, scale)
    pts = np.round(uv[tris[keep]] * 4).astype(np.int32)  # 2 fractional bits
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, list(pts), 1, lineType=cv2.LINE_8, shift=2)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    filled = np.zeros_like(m)
    cv2.drawContours(filled, cnts, -1, 1, -1)
    return filled.astype(bool)


PART_RGB = {"kit": (235, 185, 20), "blue": (50, 105, 200), "skin": (225, 160, 130), "stick_metal": (190, 190, 195),
            "stick_tan": (235, 150, 100), "socket_bore": (20, 20, 20)}


def shaded_render(verts, tris, labels, keys, params, target, shape, full_size, crop_box, scale, light=(0.3, -0.5, 0.8)):
    """Painter's-algorithm colour render (far-to-near triangles, Lambert + ambient) at the fitted camera."""
    uv, z = project(verts, params, target, full_size, crop_box, scale)
    R, C, _f = camera(params, target)
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    n = np.cross(b - a, c - a)
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    centre = (a + b + c) / 3
    view = C - centre
    facing = (n * view).sum(1) > 0
    L = np.asarray(light, float)
    L /= np.linalg.norm(L)
    shade = 0.45 + 0.55 * np.clip(n @ L, 0, 1)
    depth = z[tris].mean(1)
    img = np.zeros((*shape, 3), np.uint8)
    for i in np.argsort(-depth):
        if not facing[i]:
            continue
        col = np.asarray(PART_RGB[keys[labels[i]]], float) * shade[i]
        cv2.fillConvexPoly(img, np.round(uv[tris[i]] * 4).astype(np.int32), tuple(int(x) for x in col), lineType=cv2.LINE_AA, shift=2)
    return img


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0


def overlay(rgb, ref, mod):
    viz = (rgb.astype(float) * 0.45).astype(np.uint8)
    viz[ref & mod] = (0.5 * viz[ref & mod] + (70, 70, 70)).astype(np.uint8)
    viz[ref & ~mod] = (230, 60, 60)
    viz[mod & ~ref] = (60, 110, 240)
    edge = cv2.morphologyEx(mod.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
    viz[edge] = (255, 255, 255)
    return viz
