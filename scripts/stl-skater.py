"""Skater body from the Thingiverse STL (thing:6898521, MAVRIS, CC BY-SA) in the mold frame, and its colour regions.
PROPOSED, beside the parametric skater (docs/skater-stl.md). Steps (npm run players:stl runs them in order):

    /root/venvs/blender/bin/python scripts/stl-skater.py align    # needs out/figures/skater.npz (preview_molds.py skater)
    (fit-figure-views.py x3 and fit-figure-overhead.py with out/figures/skater-stl.npz, --out validation/players/stl)
    /root/venvs/blender/bin/python scripts/stl-skater.py finish   # scale, stick, runner
    /root/venvs/blender/bin/python scripts/stl-skater.py paint    # colour regions

align: the body STL (file mm) is placed in the mold frame (origin = fixture axis at the socket underside, +x facing, +y
  the figure's left). The axis is the centre of the STL's round base disc (the mount socket), the base underside is
  z = 0. Uniform scale and yaw are fitted to the parametric mold, so mold units and the fitted photo cameras keep their
  meaning. Writes data/figures/skater-stl.json (source, alignment) and out/figures/skater-stl.npz (for the fits).
finish: k from the overhead fit of the STL body; the wire stick with the traced blade kept in mm; a runner under the
  STL's right boot. The STL's own stick (a round printable rod at another angle) is not used.
paint: kit / blue / skin per triangle of the once-subdivided body, voted from the user's turntable frames at the cameras
  fitted to the STL (painter's z-buffer, weight = facing), skin only on the head, unseen triangles filled from
  neighbours, then smoothed. Writes data/figures/skater-stl-paint.json and validation/players/stl/paint-check.png.
"""
import base64
import json
import math
import struct
import sys
import zipfile
import zlib
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.optimize import minimize
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_views as fv  # noqa: E402

REPO = fv.REPO
ZIP = REPO / "references" / "models" / "thingiverse-6898521" / "STIGA HOCKEY PLAYER - 6898521.zip"
BODY = "files/STIGA_HOCKEY_PLAYER.stl"
SPEC_JSON = REPO / "data" / "figures" / "skater-stl.json"
MOLDS_JSON = REPO / "data" / "figure-molds.json"
PAINT_JSON = REPO / "data" / "figures" / "skater-stl-paint.json"
OUT = REPO / "out" / "figures"
VAL = REPO / "validation" / "players" / "stl"
SMOOTH_ITERS = 20
SKIN_MIN_Z = 36.0  # mold units: skin (face) only on the head
BASE_H = 0.2  # file mm: vertices this close to the lowest point form the base disc underside


def load_stl(name=BODY):
    """Binary STL from the reference zip -> (unique vertices, triangles)."""
    d = zipfile.ZipFile(ZIP).read(name)
    n = struct.unpack("<I", d[80:84])[0]
    a = np.frombuffer(d[84:84 + n * 50], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
    v, inv = np.unique(a["v"].reshape(-1, 3).astype(float).round(5), axis=0, return_inverse=True)
    return v, inv.reshape(-1, 3).astype(np.int32)


def load_spec():
    return json.loads(SPEC_JSON.read_text())


def to_mold(v, src):
    """File mm -> mold units with the alignment in data/figures/skater-stl.json."""
    a = src["alignment"]
    p = v - np.array(a["axis_file_mm"])
    p = np.c_[-p[:, 1], p[:, 0], p[:, 2]]  # file -y (the figure's facing) -> +x
    c, s = math.cos(math.radians(a["yaw_deg"])), math.sin(math.radians(a["yaw_deg"]))
    return a["scale_mold_units_per_file_mm"] * p @ np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]).T


def subdivide(V, T):
    """Midpoint subdivision (each triangle -> 4, shape unchanged): finer colour boundaries."""
    E, V = {}, list(map(tuple, V))
    out = []

    def mid(a, b):
        k = (min(a, b), max(a, b))
        if k not in E:
            E[k] = len(V)
            V.append(tuple((np.array(V[a]) + np.array(V[b])) / 2))
        return E[k]
    for a, b, c in T:
        ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
        out += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
    return np.array(V), np.array(out, np.int32)


def stick_mesh(s):
    """A wire stick spec (shaft polyline + blade, mold units) as a coarse silhouette mesh (boxes)."""
    vs, ts = [], []

    def box(a, b, w, h0, h1):
        a, b = np.array(a, float), np.array(b, float)
        d = b - a
        d /= np.linalg.norm(d)
        n = np.cross(d, [0, 0, 1.0])
        n = n / (np.linalg.norm(n) + 1e-12) * w / 2
        up = np.cross(n, d)
        up = up / (np.linalg.norm(up) + 1e-12)
        o = len(vs)
        for p in (a, b):
            for sx, sz in ((-1, h0), (1, h0), (1, h1), (-1, h1)):
                vs.append(p + sx * n + sz * up)
        for f in ((0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)):
            ts.append([o + i for i in f])
    sh = s["shaft"]
    for a, b in zip(sh[:-1], sh[1:]):
        box(a, b, 2 * s["shaft_r"], -s["shaft_r"], s["shaft_r"])
    h, t = s["blade"]
    box([h[0], h[1], s["blade_h"] / 2], [t[0], t[1], s["blade_h"] / 2], s["blade_t"], -s["blade_h"] / 2, s["blade_h"] / 2)
    return np.array(vs), np.array(ts, np.int32)


def write_npz(spec, stick):
    """out/figures/skater-stl.npz: STL body (mold units) + a wire stick, labelled like preview_molds.py (for the fits)."""
    keys = ["kit", "blue", "skin", "stick_metal", "stick_tan", "socket_bore"]
    v, t = load_stl()
    P = to_mold(v, spec)
    sv, st = stick_mesh(stick)
    lab = np.r_[np.full(len(t), keys.index("kit")), np.full(len(st), keys.index("stick_metal"))].astype(np.int8)
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / "skater-stl.npz", verts=np.r_[P, sv], tris=np.r_[t, st + len(P)], labels=lab, keys=np.array(keys))
    return P


def align():
    """Axis, yaw and a provisional scale (mold units) from the parametric mold; writes the spec's source and alignment."""
    molds = json.loads(MOLDS_JSON.read_text())
    v, t = load_stl()
    z0 = v[:, 2].min()
    disc = v[v[:, 2] < z0 + BASE_H]
    axis = [(disc[:, 0].min() + disc[:, 0].max()) / 2, (disc[:, 1].min() + disc[:, 1].max()) / 2, z0]
    d = np.load(OUT / "skater.npz")
    keys = [str(k) for k in d["keys"]]
    mv = d["verts"][np.unique(d["tris"][d["labels"] != keys.index("stick_metal")])]
    tree = cKDTree(mv)
    h0 = (mv[:, 2].max() - mv[:, 2].min()) / (v[:, 2].max() - z0)
    samp = v[::3]

    def place(p, pts):
        return to_mold(pts, {"alignment": {"axis_file_mm": axis, "yaw_deg": p[1], "scale_mold_units_per_file_mm": p[0]}})

    def cost(p):
        q = place(p, samp)
        d1, _ = tree.query(q)
        d2, _ = cKDTree(q).query(mv[::2])
        return float(np.mean(np.minimum(d1, 3) ** 2) + np.mean(np.minimum(d2, 3) ** 2))
    best = min((minimize(cost, [h0, y0], method="Powell") for y0 in (-30, 0, 30, 60)), key=lambda r: r.fun)
    s, yaw = float(best.x[0]), float(best.x[1])
    P = place(best.x, v)
    d1, _ = tree.query(P)
    d2, _ = cKDTree(P).query(mv)
    spec = {
        "schema": "skater-stl/1",
        "description": "Skater body from a third-party STL in the mold frame (scripts/stl-skater.py): origin = fixture axis at the socket "
                       "underside, +x facing, +y the figure's left; mold units x scale.k_mm_per_mold_unit = mm. PROPOSED: the assets "
                       "assets/figures/skater_stl_*.glb sit beside the parametric skater; contacts, footprints and traces still use the parametric mold.",
        "source": {"reference_id": "thingiverse_6898521_stiga_hockey_player", "file": str(ZIP.relative_to(REPO)), "member": BODY,
                   "license": "CC BY-SA", "attribution": "STIGA HOCKEY PLAYER by MAVRIS, https://www.thingiverse.com/thing:6898521",
                   "status": "traced",
                   "note": "A sculpt of the STIGA skater mold: same pose and handedness as the user's skater no. 21. Used for the body only; "
                           "its round printable stick is replaced by the traced wire stick."},
        "alignment": {"axis_file_mm": [round(c, 4) for c in axis], "yaw_deg": round(yaw, 3), "scale_mold_units_per_file_mm": round(s, 5),
                      "method": "axis = centre of the base disc (file z < min + 0.2 mm), underside -> z = 0; scale and yaw fitted to the "
                                "parametric mold (symmetric nearest-point distance clipped at 3 units, stick excluded), so mold units and "
                                "the fitted photo cameras keep their meaning",
                      "residual_mold_units": {"stl_to_mold_median": round(float(np.median(d1)), 3), "stl_to_mold_p90": round(float(np.percentile(d1, 90)), 3),
                                              "mold_to_stl_median": round(float(np.median(d2)), 3), "mold_to_stl_p90": round(float(np.percentile(d2, 90)), 3)},
                      "file_height_mm": round(float(v[:, 2].max() - z0), 3), "body_height_mold_units": round(float(P[:, 2].max()), 3)}}
    SPEC_JSON.write_text(json.dumps(spec, indent=1) + "\n")
    write_npz(spec, molds["skater"]["stick"])
    print(json.dumps(spec["alignment"], indent=1))


def finish():
    """Scale = the STL file's own size (user decision 2026-10-12), the wire stick with the traced blade kept in mm
    (data/geometry.json contact blade) and a runner under the STL's right boot; rewrites the fitting mesh. The overhead fit
    of the STL body (validation/players/stl/overhead-fit.json) is kept as a check."""
    spec = load_spec()
    molds = json.loads(MOLDS_JSON.read_text())
    g = json.loads((REPO / "data" / "geometry.json").read_text())
    ov = json.loads((VAL / "overhead-fit.json").read_text())
    k_old = json.loads((REPO / "validation" / "players" / "overhead-fit.json").read_text())["scale_k_mm_per_mold_unit"]
    k_ov = ov["scale_k_mm_per_mold_unit"]
    k = round(1.0 / spec["alignment"]["scale_mold_units_per_file_mm"], 5)  # file mm = asset mm
    a = next(x for x in g["figure_assets"] if x["kind"] == "skater")
    blade_mm = next(c for c in a["contact_shapes"] if c["kind"] == "blade")["geometry"]["points_mm"]
    heel, toe = np.array(blade_mm[0][:2]), np.array(blade_mm[1][:2])
    old = molds["skater"]["stick"]
    h_old = np.array(old["blade"][0])
    r = k_old / k  # parametric mold units -> STL mold units for lengths given in mm
    heel_u, toe_u = heel / k, toe / k
    shaft = [old["shaft"][0]] + [[*(heel_u + (np.array(p[:2]) - h_old) * r), p[2] * r] for p in old["shaft"][1:]]
    stick = {"shaft": [[round(float(c), 4) for c in p] for p in shaft], "shaft_r": round(old["shaft_r"] * r, 4),
             "blade": [[round(float(c), 4) for c in heel_u], [round(float(c), 4) for c in toe_u]],
             "blade_h": round(float(blade_mm[2][2]) / k, 4), "blade_t": round(old["blade_t"] * r, 4),
             "note": "Blade heel/toe and height kept in mm from the traced contact blade (data/geometry.json, official overhead); "
                     "shaft top in the upper glove (parametric mold point, same mold units); wire radius and blade thickness kept in mm."}
    v, _t = load_stl()
    P = to_mold(v, spec)
    far = P[np.hypot(P[:, 0], P[:, 1]) > 8]  # the right (pushing) boot, away from the socket
    z0 = float(far[:, 2].min())
    b = far[far[:, 2] < z0 + 0.6][:, :2]
    c = b.mean(0)
    dirn = np.linalg.svd(b - c)[2][0]
    tt = (b - c) @ dirn
    ends = sorted([c + dirn * tt.min(), c + dirn * tt.max()], key=lambda p: p[0])
    runner = {"a": [round(float(x), 3) for x in ends[0]], "b": [round(float(x), 3) for x in ends[1]],
              "height": round(z0 + 0.3, 3), "thickness": molds["skater"]["runner"]["thickness"],
              "note": "Metal runner from the ice up into the STL's right boot (boot underside z0 + 0.3 units overlap); ends from the boot "
                      "underside (vertices within 0.6 units of its lowest point, principal axis). The STL boot floats above the ice by about "
                      "the runner height."}
    spec["scale"] = {"k_mm_per_mold_unit": k, "status": "traced",
                     "source": "user decision 2026-10-12 ('Use the measurement from thingiverse, 57 mm'): the STL file's own size, file mm = asset mm",
                     "body_height_mm": round(float(P[:, 2].max() * k), 2), "file_scale": round(spec["alignment"]["scale_mold_units_per_file_mm"] * k, 4),
                     "uncertainty_mm": None,
                     "checks": {"overhead_fit_k": k_ov, "overhead_fit_body_height_mm": round(float(P[:, 2].max() * k_ov), 2),
                                "parametric_overhead_k": k_old, "catalog_height": "approx. 57 mm (datum unspecified)"},
                     "note": "Not a ruler measurement of the user's skater. The overhead fit with the STL shape (ASSUMED preview scale) gives "
                             f"{P[:, 2].max() * k_ov:.1f} mm, within 1% of the file; the parametric mold gave 51.1 mm."}
    base = P[(P[:, 2] < 0.05) & (np.hypot(P[:, 0], P[:, 1]) < 9)]
    socket = {"r_bottom": round(float(np.hypot(base[:, 0], base[:, 1]).max()), 3), "height": 3.0,
              "note": "The STL's round base disc (the mount socket) at the ice; height read from its radius profile (the boot starts "
                      "about 3 units up). The key bore is not modelled on the STL body."}
    spec["stick"], spec["runner"], spec["socket"] = stick, runner, socket
    SPEC_JSON.write_text(json.dumps(spec, indent=1) + "\n")
    write_npz(spec, stick)
    print(json.dumps({"scale": spec["scale"], "stick": stick, "runner": runner}, indent=1))


def paint_classes(rgb):
    """Colour classes for painting: wider than fv.colour_classes (which are tuned for clean silhouettes) so that shaded
    yellow (lower back, under the arms) and the face still vote; hues as in figure_views.py."""
    import cv2
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(int)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    blue = (h >= 95) & (h <= 128) & (s >= 70) & (v >= 40)
    yellow = (h >= 15) & (h <= 35) & (s >= 80) & (v >= 50)
    warm = ((h <= 14) | (h >= 170)) & (s >= 50) & (v >= 70)
    return blue, yellow, warm


def fitted_cameras():
    cams = {}
    for f in ("skater-fit", "skater-heldout-fit", "skater-independent-fit"):
        cams.update(json.loads((VAL / f"{f}.json").read_text())["views"])
    return cams


def paint(min_iou=0.85):
    import cv2
    v, t = load_stl()
    V, T = subdivide(to_mold(v, load_spec()), t)
    d = np.load(OUT / "skater-stl.npz")
    keys = [str(k) for k in d["keys"]]
    SV, ST = d["verts"][len(v):], d["tris"][len(t):] - len(v)
    AV, AT = np.r_[V, SV], np.r_[T, ST + len(V)]
    tri = V[T]
    cen = tri.mean(1)
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    votes = np.zeros((len(T), 3))  # kit, blue, skin
    used = []
    for vid, fit in fitted_cameras().items():
        if fit["iou"] < min_iou:
            continue
        it = fv.MANIFEST[vid]
        im = np.asarray(Image.open(REPO / it["file"]).convert("RGB"))
        s = 1000 / max(im.shape[:2])
        im = cv2.resize(im, (round(im.shape[1] * s), round(im.shape[0] * s)), interpolation=cv2.INTER_AREA)
        p = fit["params"]
        uv, z = fv.project(AV, p, fv.TARGET["skater"], it["full_size_px"], it["crop_box_px"], s)
        _R, C, _f = fv.camera(p, fv.TARGET["skater"])
        buf = np.zeros((*im.shape[:2], 3), np.uint8)
        pts = np.round(uv[AT] * 4).astype(np.int32)
        for i in np.argsort(-z[AT].mean(1)):  # painter's algorithm, far to near
            c = int(i) + 1
            cv2.fillPoly(buf, [pts[i]], (c & 255, (c >> 8) & 255, (c >> 16) & 255), shift=2)
        ids = buf[..., 0].astype(int) + (buf[..., 1].astype(int) << 8) + (buf[..., 2].astype(int) << 16) - 1
        blue, yellow, warm = paint_classes(im)
        cls = np.full(ids.shape, -1)
        cls[yellow], cls[blue], cls[warm] = 0, 1, 2
        view = cen - C
        view /= np.linalg.norm(view, axis=1, keepdims=True)
        facing = np.clip(-(nrm * view).sum(1), 0, 1)
        m = (ids >= 0) & (ids < len(T)) & (cls >= 0)
        np.add.at(votes, (ids[m], cls[m]), facing[ids[m]])
        used.append(vid)
    votes[cen[:, 2] < SKIN_MIN_Z, 2] = 0
    nbs = [[] for _ in range(len(T))]
    E = {}
    for i, tr in enumerate(T):
        for a, b in ((tr[0], tr[1]), (tr[1], tr[2]), (tr[2], tr[0])):
            k = (min(a, b), max(a, b))
            if k in E:
                nbs[i].append(E[k])
                nbs[E[k]].append(i)
            else:
                E[k] = i
    nbs = [np.array(n, int) for n in nbs]
    tot = votes.sum(1)
    lab = np.where(tot > 0.5, votes.argmax(1), -1)
    unseen = int((lab < 0).sum())
    while (lab < 0).any():  # fill unseen triangles from labelled neighbours
        new = lab.copy()
        for i in np.nonzero(lab < 0)[0]:
            c = lab[nbs[i]]
            c = c[c >= 0]
            if len(c):
                new[i] = np.bincount(c, minlength=3).argmax()
        if (new == lab).all():
            new[new < 0] = 1
        lab = new
    pr = votes / (tot[:, None] + 1e-9)
    for _ in range(SMOOTH_ITERS):  # smoothing: own vote share + neighbourhood majority
        oh = np.eye(3)[lab]
        sc = 0.6 * pr + np.stack([oh[n].mean(0) for n in nbs])
        sc[cen[:, 2] < SKIN_MIN_Z, 2] = -1
        lab = sc.argmax(1)
    names = ["kit", "blue", "skin"]
    PAINT_JSON.write_text(json.dumps({
        "schema": "skater-stl-paint/1",
        "description": "Colour region per triangle of the once-midpoint-subdivided STL body (scripts/stl-skater.py paint), in subdivision order: "
                       "0 = kit, 1 = blue, 2 = skin. Base64 of zlib-compressed uint8.",
        "status": "traced", "source_views": used, "min_camera_iou": min_iou, "triangles": int(len(T)),
        "unseen_triangles_filled": unseen, "counts": {n: int((lab == i).sum()) for i, n in enumerate(names)},
        "labels_b64_zlib": base64.b64encode(zlib.compress(lab.astype(np.uint8).tobytes(), 9)).decode()}, indent=1) + "\n")
    # check sheet: photo | painted STL at the fitted camera
    lk = {"kit": keys.index("kit"), "blue": keys.index("blue"), "skin": keys.index("skin")}
    labels = np.r_[np.array([lk[names[i]] for i in lab]), np.full(len(ST), keys.index("stick_metal"))].astype(np.int8)
    tiles = []
    cams = fitted_cameras()
    for vid in ("skater-video-t00.00", "skater-video-t03.00", "skater-video-t07.25", "skater-video-t10.75",
                "skater-video-t13.25", "skater-video-t08.50", "skater-video-t05.25", "skater-video-t01.10"):
        rgb, s, crop, full = fv.load_view(vid, 420)
        col = fv.shaded_render(AV, AT, labels, keys, cams[vid]["params"], fv.TARGET["skater"], rgb.shape[:2], full, crop, s)
        tiles.append(np.concatenate([rgb, col], 1))
    H, W = max(x.shape[0] for x in tiles), max(x.shape[1] for x in tiles)
    sheet = np.zeros((H * 4, W * 2, 3), np.uint8)
    for i, x in enumerate(tiles):
        sheet[(i // 2) * H:(i // 2) * H + x.shape[0], (i % 2) * W:(i % 2) * W + x.shape[1]] = x
    VAL.mkdir(parents=True, exist_ok=True)
    Image.fromarray(sheet).save(VAL / "paint-check.png")
    print("paint", {n: int((lab == i).sum()) for i, n in enumerate(names)}, "unseen", unseen, "views", len(used))


def paint_labels():
    """Per-triangle colour region names of the subdivided STL body (data/figures/skater-stl-paint.json)."""
    d = json.loads(PAINT_JSON.read_text())
    return np.frombuffer(zlib.decompress(base64.b64decode(d["labels_b64_zlib"])), np.uint8)


if __name__ == "__main__":
    {"align": align, "finish": finish, "paint": paint}[sys.argv[1]]()
