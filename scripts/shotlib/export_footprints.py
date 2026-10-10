"""Contact footprints of the two figure molds: the part of each mold below the puck top (z < puck thickness), seen from
above, in the figure's local frame (mm, pivot at the origin, the frame of docs/pose.md). The move engine
(scripts/shotlib) uses only this file, so building a trace needs no Blender and no mesh files.

    /root/venvs/blender/bin/python assets/blender/preview_molds.py     # out/figures/{skater,goalie}.npz (Blender)
    /root/venvs/blender/bin/python scripts/shotlib/export_footprints.py

Same construction as scripts/spjass-trace.py (low_polygon, stick_polygon): every mesh triangle whose lowest vertex is
below the puck thickness, projected and united. Output: data/figures/contact-footprints.json.
Re-export after any change to the molds, the figure scale or the puck thickness; the engine refuses a footprint file
whose recorded inputs no longer match (scripts/shotlib/world.py).
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

REPO = Path(__file__).resolve().parents[2]
HW = json.loads((REPO / "validation/12-hardware-report.json").read_text())
FIG = json.loads((REPO / "validation/players/figures-report.json").read_text())
PUCK_T = HW["puck"]["thickness_mm_preview"]
SCALE = {"skater": FIG["scale_k_mm_per_mold_unit"], "goalie": FIG["scales"]["goalie"]}
OUT = REPO / "data/figures/contact-footprints.json"
# everything that decides the footprints: the mold data and the code that builds the meshes (out/figures/*.npz, not
# committed), the figure scale and the puck thickness. The engine and the tests refuse the file when any of them changed.
INPUTS = ["data/figure-molds.json", "assets/blender/figure_molds.py", "assets/blender/face_sections.py", "assets/blender/stiga_blender.py",
          "assets/blender/preview_molds.py", "scripts/shotlib/export_footprints.py", "validation/players/figures-report.json", "validation/12-hardware-report.json"]


def sha(p):
    return hashlib.sha256((REPO / p).read_bytes()).hexdigest()


def footprint(kind, stick_only):
    d = np.load(REPO / f"out/figures/{kind}.npz")
    keys = [str(x) for x in d["keys"]]
    V, T, L = d["verts"] * SCALE[kind], d["tris"], d["labels"]
    sel = V[T][:, :, 2].min(1) < PUCK_T
    if stick_only:
        sel &= np.isin(L, [keys.index(x) for x in ("stick_metal", "stick_tan") if x in keys])
    raw = [Polygon(V[t][:, :2]) for t in T[sel]]
    if stick_only:  # as stick_polygon: area filter after the 0.01 mm buffer
        return unary_union([q for q in (p.buffer(0.01) for p in raw) if q.area > 1e-6]).buffer(0)
    return unary_union([p.buffer(0.01) for p in raw if p.area > 1e-6]).buffer(0)  # as low_polygon


def to_json(poly):
    gs = [poly] if poly.geom_type == "Polygon" else list(poly.geoms)
    r = lambda ring: [[float(x), float(y)] for x, y in ring.coords]  # full precision: the contact rules amplify tiny geometry changes
    return [{"exterior": r(g.exterior), "interiors": [r(i) for i in g.interiors]} for g in gs]


def main():
    out = {"schema": "contact-footprints/1",
           "description": "Figure footprints for puck contact: mold geometry below the puck top, projected on the ice, local mm (pivot at the origin; +y toward the blade, docs/pose.md). 'low' = everything the puck can touch, 'stick' = the stick and blade part of it (used to name a contact 'stick/blade' rather than 'skate/body').",
           "status": "derived from the AI-modelled molds at the assumed preview scale (docs/players.md); not measured",
           "puck_thickness_mm": PUCK_T, "puck_thickness_status": "assumed (preview)",
           "scale_mm_per_mold_unit": SCALE, "inputs_sha256": {p: sha(p) for p in INPUTS},
           "meshes_sha256": {f"out/figures/{k}.npz": sha(f"out/figures/{k}.npz") for k in ("skater", "goalie")},
           "meshes_note": "the generated meshes the footprints were cut from (not committed; regenerate with preview_molds.py and compare when present)",
           "made_by": "scripts/shotlib/export_footprints.py from out/figures/<kind>.npz (assets/blender/preview_molds.py)",
           "figures": {}}
    for kind in ("skater", "goalie"):
        low, stick = footprint(kind, False), footprint(kind, True)
        out["figures"][kind] = {"low": to_json(low), "stick": to_json(stick), "low_area_mm2": round(low.area, 3), "low_bounds_mm": [round(b, 3) for b in low.bounds]}
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    print(OUT, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
