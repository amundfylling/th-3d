"""Refine a figure mold's body layout against the camera-matched photo silhouettes (multi-view shape fit).

    /root/venvs/blender/bin/python scripts/fit-figure-shape.py skater|goalie [--rounds 3] [--write]
Starts from data/figure-molds.json and the cameras of validation/players/<kind>-fit.json (fit-figure-views.py).
The metaball body is approximated by the union of its elements (ellipsoids; capsules as chains of spheres;
goalie boxes as boxes), rasterised per view. Coincident element points (capsule ends, ellipsoid centres
closer than 0.3 mm) form shared joints, so limbs stay connected. Variables: joint positions and per-element
size scales; fixed: the mount socket, the stick and the gloves (keypoint-anchored). Cost: mean(1 - IoU) over
the views + a weak prior (sigma 3 mm, 12 %) toward the starting layout, so silhouette-free directions stay
put. Cameras are re-fitted between shape passes. --write stores the result in data/figure-molds.json.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_views as fv  # noqa: E402

REPO = fv.REPO
MOLDS = REPO / "data" / "figure-molds.json"
FIXED_PARTS = {"skater": {"gloves"}, "goalie": set()}


def sphere_mesh(n_lat=7, n_lon=12):
    v = [(0, 0, 1)]
    for i in range(1, n_lat):
        th = math.pi * i / n_lat
        for j in range(n_lon):
            ph = 2 * math.pi * j / n_lon
            v.append((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)))
    v.append((0, 0, -1))
    t = []
    for j in range(n_lon):
        t.append((0, 1 + j, 1 + (j + 1) % n_lon))
    for i in range(n_lat - 2):
        for j in range(n_lon):
            a, b = 1 + i * n_lon + j, 1 + i * n_lon + (j + 1) % n_lon
            t += [(a, a + n_lon, b), (b, a + n_lon, b + n_lon)]
    last = len(v) - 1
    base = 1 + (n_lat - 2) * n_lon
    for j in range(n_lon):
        t.append((base + j, last, base + (j + 1) % n_lon))
    return np.array(v, float), np.array(t, np.int32)


SV, ST = sphere_mesh()
CUBE_V = np.array([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float)
CUBE_T = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)], np.int32)


class Layout:
    """Flattens a mold's parts into joints + elements; rebuilds the JSON from them."""

    def __init__(self, mold, kind):
        self.mold, self.kind = mold, kind
        self.joints, self.elems = [], []  # elems: (part, name, type, joint ids, size)

        def jid(p, fixed):
            p = np.asarray(p, float)
            for i, (q, f) in enumerate(self.joints):
                if np.linalg.norm(q - p) < 0.3:
                    self.joints[i] = (q, f or fixed)
                    return i
            self.joints.append((p, fixed))
            return len(self.joints) - 1

        for pn, part in mold["parts"].items():
            fixed = pn in FIXED_PARTS[kind]
            for en, e in part.get("ellipsoids", {}).items():
                self.elems.append((pn, en, "ell", [jid(e["centre"], fixed)], np.array(e["semi_axes"], float)))
            for en, e in part.get("capsules", {}).items():
                self.elems.append((pn, en, "cap", [jid(e["a"], fixed), jid(e["b"], fixed)], np.array([e["radius"]], float)))
        for bn, bx in mold.get("boxes", {}).items():
            self.elems.append(("__box__", bn, "box", [jid(bx["centre"], False)], np.array(bx["half_size"], float)))
        self.J0 = np.array([q for q, _ in self.joints])
        self.free = np.array([not f for _, f in self.joints])
        self.S0 = [e[4].copy() for e in self.elems]

    def mesh(self, J, S):
        vs, ts, n = [], [], 0
        for (pn, en, typ, ids, _s0), s in zip(self.elems, S):
            if typ == "ell":
                v = SV * s + J[ids[0]]
                vs.append(v)
                ts.append(ST + n)
                n += len(v)
            elif typ == "box":
                v = CUBE_V * s + J[ids[0]]
                vs.append(v)
                ts.append(CUBE_T + n)
                n += len(v)
            else:
                a, b, r = J[ids[0]], J[ids[1]], s[0]
                k = max(2, int(math.ceil(np.linalg.norm(b - a) / (0.45 * r))) + 1)
                for t in np.linspace(0, 1, k):
                    v = SV * r + (a + t * (b - a))
                    vs.append(v)
                    ts.append(ST + n)
                    n += len(v)
        return np.concatenate(vs), np.concatenate(ts)

    def write(self, J, S):
        m = self.mold
        for (pn, en, typ, ids, _), s in zip(self.elems, S):
            r = lambda x: [round(float(c), 2) for c in x]
            if typ == "ell":
                m["parts"][pn]["ellipsoids"][en] = {"centre": r(J[ids[0]]), "semi_axes": r(s)}
            elif typ == "cap":
                m["parts"][pn]["capsules"][en] = {"a": r(J[ids[0]]), "b": r(J[ids[1]]), "radius": round(float(s[0]), 2)}
            else:
                m["boxes"][en]["centre"], m["boxes"][en]["half_size"] = r(J[ids[0]]), r(s)
        return m


def fixed_mesh(mold, kind):
    """Socket (lathe) + goalie stick as simple meshes, always part of the silhouette (not optimised)."""
    s = mold["socket"]
    n = 24
    ring = lambda r, z: [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), z) for k in range(n)]
    prof = [(s["r_bottom"], 0.0), (s["r_bottom"], 0.35)] + [(s["r_top"] + (s["r_bottom"] - s["r_top"]) * (1 - t) ** 2.2, 0.35 + (s["height"] - 0.35) * t) for t in np.linspace(0.125, 1, 8)]
    v = [p for r, z in prof for p in ring(r, z)] + [(0, 0, 0), (0, 0, s["height"])]
    t = []
    for i in range(len(prof) - 1):
        for k in range(n):
            a, b = i * n + k, i * n + (k + 1) % n
            t += [(a, b, b + n), (a, b + n, a + n)]
    for k in range(n):
        t += [(k, (k + 1) % n, len(v) - 2), ((len(prof) - 1) * n + k, (len(prof) - 1) * n + (k + 1) % n, len(v) - 1)]
    return np.array(v, float), np.array(t, np.int32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--sigma-mm", type=float, default=3.0)
    a = ap.parse_args()
    molds = json.loads(MOLDS.read_text())
    mold = molds[a.kind]
    L = Layout(mold, a.kind)
    fit = json.loads((REPO / "validation" / "players" / f"{a.kind}-fit.json").read_text())["views"]
    # view definitions (warm flag, exclusions) without running main(): read the VIEWS literal
    import ast
    tree = ast.parse((REPO / "scripts" / "fit-figure-views.py").read_text())
    VIEWS = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "VIEWS")[a.kind]
    target = fv.TARGET[a.kind]
    fvx, fvt = fixed_mesh(mold, a.kind)
    views = []
    for vid, (az0, el0, excl, warm) in VIEWS.items():
        if vid not in fit:
            continue
        rgb, s, crop, full = fv.load_view(vid, 300)
        ref = fv.figure_mask(rgb, include_warm=warm, exclude_polys=[[(x * 300 / 420, y * 300 / 420) for x, y in p] for p in excl])
        views.append({"id": vid, "ref": ref, "s": s, "crop": crop, "full": full, "p": np.array(fit[vid]["params"], float), "warm": warm})

    def render(v, J, S):
        mv, mt = L.mesh(J, S)
        verts = np.concatenate([mv, fvx])
        tris = np.concatenate([mt, fvt + len(mv)])
        uv, _ = fv.project(verts, v["p"], target, v["full"], v["crop"], v["s"])
        m = np.zeros(v["ref"].shape, np.uint8)
        cv2.fillPoly(m, list(np.round(uv[tris] * 4).astype(np.int32)), 1, shift=2)
        return m.astype(bool)

    def score(J, S):
        return float(np.mean([fv.iou(render(v, J, S), v["ref"]) for v in views]))

    J, S = L.J0.copy(), [s.copy() for s in L.S0]
    sig = a.sigma_mm
    print("start mean IoU (proxy)", round(score(J, S), 4))
    for rnd in range(a.rounds):
        # shape pass: coordinate descent over free joints (xyz) and element size scales
        for j in np.nonzero(L.free)[0]:
            def cj(d):
                JJ = J.copy()
                JJ[j] = J[j] + d
                return 1 - score(JJ, S) + 0.02 * np.sum(((JJ[j] - L.J0[j]) / sig) ** 2)
            r = minimize(cj, np.zeros(3), method="Powell", options={"xtol": 0.05, "ftol": 1e-4, "maxfev": 90})
            J[j] = J[j] + r.x
        for k, e in enumerate(L.elems):
            if e[0] in FIXED_PARTS[a.kind]:
                continue
            def cs(q):
                SS = list(S)
                SS[k] = S[k] * math.exp(q[0])
                return 1 - score(J, SS) + 0.02 * (math.log(SS[k][0] / L.S0[k][0]) / 0.12) ** 2
            r = minimize(cs, np.zeros(1), method="Powell", options={"xtol": 0.005, "ftol": 1e-4, "maxfev": 30})
            S[k] = S[k] * math.exp(r.x[0])
        # camera pass
        for v in views:
            p0 = v["p"].copy()
            scl = np.array([0.02, 0.02, 0.02, 0.005, 0.005, 0.01 * p0[5], 0.01 * p0[6]])
            def cc(z):
                v["p"] = p0 + z * scl
                if "photo" in v["id"]:
                    v["p"][6] = p0[6]
                return 1 - fv.iou(render(v, J, S), v["ref"])
            r = minimize(cc, np.zeros(7), method="Powell", options={"xtol": 1e-3, "ftol": 1e-4, "maxfev": 400})
            v["p"] = p0 + r.x * scl
            if "photo" in v["id"]:
                v["p"][6] = p0[6]
        print("round", rnd + 1, "mean IoU (proxy)", round(score(J, S), 4), "max joint move mm", round(float(np.abs(J - L.J0).max()), 2))
    per = {v["id"]: round(fv.iou(render(v, J, S), v["ref"]), 4) for v in views}
    print(json.dumps(per, indent=1))
    if a.write:
        fresh = json.loads(MOLDS.read_text())  # re-read: only this mold's parts/boxes are replaced
        new = L.write(J, S)
        fresh[a.kind]["parts"] = new["parts"]
        if "boxes" in new:
            fresh[a.kind]["boxes"] = new["boxes"]
        MOLDS.write_text(json.dumps(fresh, indent=1) + "\n")
        fitf = REPO / "validation" / "players" / f"{a.kind}-fit.json"
        d = json.loads(fitf.read_text())
        for v in views:
            d["views"][v["id"]]["params"] = v["p"].tolist()
        fitf.write_text(json.dumps(d, indent=2) + "\n")
        print("wrote", MOLDS)


main()
