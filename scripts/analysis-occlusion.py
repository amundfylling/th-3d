"""Puck visibility in an analysis video: per frame, sight lines from the camera to the puck (top centre and four rim
points) are ray-cast against the real posed figure meshes (out/figures/*.npz at the asset scale). Reports, per
segment, the frames where less than half of the puck's sight lines are clear.

    node scripts/analysis-occlusion-dump.ts <analysis.json> <trace.json> out/occl.json
    /root/venvs/blender/bin/python scripts/analysis-occlusion.py out/occl.json [report.json]
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
FIG = json.loads((REPO / "validation/players/figures-report.json").read_text())
R_PUCK = json.loads((REPO / "data/geometry.json").read_text())["puck"]["diameter"]["value"] / 2
MESH = {}
for kind, k in (("skater", FIG["scale_k_mm_per_mold_unit"]), ("goalie", FIG["scales"]["goalie"])):
    d = np.load(REPO / f"out/figures/{kind}.npz")
    V = d["verts"] * k
    T = d["tris"]
    MESH[kind] = (V[T[:, 0]], V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]], float(np.linalg.norm(V[:, :2], axis=1).max()))


def hits(kind, pivot, heading, o, d):
    """Does the segment o -> o + d (world mm) hit the posed figure mesh? (Moller-Trumbore, vectorised; local frame)."""
    a0, e1, e2, rad = MESH[kind]
    c, s = math.cos(math.radians(heading)), math.sin(math.radians(heading))
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
    ol = R.T @ (o - np.array([pivot[0], pivot[1], 0.0]))
    dl = R.T @ d
    # quick reject: segment far from the figure's vertical axis
    tt = np.clip(-(ol[:2] @ dl[:2]) / max(dl[:2] @ dl[:2], 1e-9), 0, 1)
    if np.linalg.norm(ol[:2] + tt * dl[:2]) > rad + 1:
        return False
    p = np.cross(dl, e2)
    det = np.einsum("ij,ij->i", e1, p)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
    tv = ol - a0
    u = np.einsum("ij,ij->i", tv, p) * inv
    q = np.cross(tv, e1)
    v = (q @ dl) * inv
    t = np.einsum("ij,ij->i", e2, q) * inv
    return bool(np.any(ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6) & (t < 0.995)))


def main():
    data = json.loads(Path(sys.argv[1]).read_text())
    rows = {}
    for fr in data["frames"]:
        cam = np.array(fr["camera"], float)
        px, py = fr["puck"][0], fr["puck"][1]
        targets = [np.array([px, py, 12.0])] + [np.array([px + R_PUCK * 0.8 * math.cos(a), py + R_PUCK * 0.8 * math.sin(a), 6.0]) for a in (0, math.pi / 2, math.pi, 3 * math.pi / 2)]
        clear, by = 0, set()
        for tg in targets:
            blocked = [f["id"] for f in fr["figures"] if hits(f["kind"], f["pivot"], f["heading"], cam, tg - cam)]
            if not blocked:
                clear += 1
            by.update(blocked)
        r = rows.setdefault(fr["segment"], {"frames": 0, "poor": [], "min_visible": 1.0, "occluders": set()})
        r["frames"] += 1
        vis = clear / len(targets)
        r["min_visible"] = min(r["min_visible"], vis)
        if vis < 0.5:
            r["poor"].append(fr["frame"]); r["occluders"].update(by)
    out = {k: {"frames": v["frames"], "frames_puck_mostly_hidden": len(v["poor"]), "min_visible_fraction": v["min_visible"],
               "first_poor_frames": v["poor"][:6], "occluders": sorted(v["occluders"])} for k, v in rows.items()}
    for k, v in out.items():
        print(f"{k:16s} hidden {v['frames_puck_mostly_hidden']:3d}/{v['frames']:3d}  min visible {v['min_visible_fraction']:.1f}  {','.join(v['occluders'])}")
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
