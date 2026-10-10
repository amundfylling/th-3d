"""Review sheets for frames where two figure tracks disagree (docs/tracker-v3.md).

    /root/venvs/blender/bin/python scripts/synth/tracker-v3-review.py <a.json pattern {game}> <b.json pattern {game}> [--n 48] [--name v2-v3]

Picks up to --n frames (spread over all seven games and all skaters, seeded) where the two tracks place a skater more
than 30 mm apart along its slot, or turn it more than 60 degrees apart, and draws each on the registered broadcast
frame: track A's pivot and facing in red, track B's in green (hollow = interpolated, no marker = unknown).
Writes validation/tracker-<name>-review-<k>.jpg (16 tiles each) and out/synth/v3/review-<name>.json (the cases, for
recording a verdict per tile: "a", "b", "neither" or "unclear"). The verdicts are a visual check of the broadcast, not
user labels.
"""
import importlib.util, json, math, random, sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("tv3", REPO / "scripts/synth/track-figures-v3.py"); tv3 = importlib.util.module_from_spec(spec)
_argv = sys.argv; sys.argv = [_argv[0], "-"]; spec.loader.exec_module(tv3); sys.argv = _argv
A = sys.argv[1:]; PA, PB = A[0], A[1]
def arg(n, d): return A[A.index(n) + 1] if n in A else d
N = int(arg("--n", 48)); NAME = arg("--name", "v2-v3")
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text()); K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
HOME = {"W": 0.0, "E": 180.0}; x0, y0 = tv3.x0, tv3.y0


def proj(p):
    q = K @ (R @ np.array([p[0], p[1], 0.0]) + t); return q[:2] / q[2] - [x0, y0]


def arc_point(P, u):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = u * seg.sum(); acc = np.r_[0, np.cumsum(seg)]
    k = min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1); f = (s - acc[k]) / seg[k]
    return P[k] + f * (P[k + 1] - P[k])


def load(p):
    T = json.loads(Path(p).read_text()); ci = {c: i for i, c in enumerate(T["columns"])}; return {r[0]: r for r in T["rows"]}, ci


def get(rc, f, pid):
    rows, ci = rc; r = rows.get(f)
    if r is None or r[ci[f"{pid}_u"]] is None: return None
    src = r[ci[f"{pid}_src"]] if f"{pid}_src" in ci else 0
    return (r[ci[f"{pid}_u"]], r[ci[f"{pid}_theta_deg"]], src) if src != 2 else None


cases = []
for g in [f"g{k}" for k in range(1, 8)]:
    if not (Path(PA.format(game=g)).exists() and Path(PB.format(game=g)).exists()): continue
    a, b = load(PA.format(game=g)), load(PB.format(game=g))
    for f in sorted(set(a[0]) & set(b[0])):
        for pid in tv3.ORDER:
            va, vb = get(a, f, pid), get(b, f, pid)
            if va is None and vb is None: continue
            if va is None or vb is None: cases.append((g, f, pid, va, vb, "one unknown")); continue
            ds = abs(va[0] - vb[0]) * tv3.SLOT_LEN[pid]; dth = abs((va[1] - vb[1] + 180) % 360 - 180)
            if ds > 30 or dth > 60: cases.append((g, f, pid, va, vb, f"{ds:.0f} mm, {dth:.0f} deg"))
rnd = random.Random(0); stats = {"disagreements": len(cases)}
by = {}
for c in cases: by.setdefault((c[0], c[2]), []).append(c)
pick = []
while len(pick) < N and any(by.values()):  # round robin over game and skater so one long stretch does not fill the sheet
    for k in sorted(by):
        if by[k] and len(pick) < N:
            c = by[k].pop(rnd.randrange(len(by[k])))
            if all(abs(c[1] - p[1]) > 60 or c[0] != p[0] for p in pick): pick.append(c)
pick.sort(key=lambda c: (c[0], c[1]))
imgs = {}
for g in sorted({c[0] for c in pick}):
    for i, img in tv3.registered([c[1] for c in pick if c[0] == g]): imgs[(g, i)] = img
tiles, out = [], []
for k, (g, f, pid, va, vb, why) in enumerate(pick):
    im = imgs[(g, f)].copy(); pts = []
    for v, col in ((va, (0, 0, 230)), (vb, (0, 200, 0))):
        if v is None: continue
        p = arc_point(tv3.SLOT[pid], v[0]); q = proj(p); a_ = math.radians(HOME[pid[0]] + v[1]); q1 = proj(p + 35 * np.array([math.cos(a_), math.sin(a_)]))
        cv2.circle(im, tuple(np.int32(q)), 6, col, -1 if v[2] == 0 else 2); cv2.arrowedLine(im, tuple(np.int32(q)), tuple(np.int32(q1)), col, 2, tipLength=0.3); pts.append(q)
    c = np.mean(pts, 0); cx = int(np.clip(c[0] - 150, 0, im.shape[1] - 300)); cy = int(np.clip(c[1] - 140, 0, im.shape[0] - 220))
    tile = im[cy:cy + 220, cx:cx + 300].copy()
    for s_, col, th in ((f"#{k} {g} {f} {pid}", (0, 0, 0), 3), (f"#{k} {g} {f} {pid}", (255, 255, 255), 1)): cv2.putText(tile, s_, (4, 16), 0, 0.5, col, th)
    tiles.append(tile); out.append({"k": k, "game": g, "frame": f, "pid": pid, "a": va, "b": vb, "why": why, "verdict": None})
for s in range(0, len(tiles), 16):
    T = tiles[s:s + 16] + [np.zeros_like(tiles[0])] * (16 - len(tiles[s:s + 16]))
    cv2.imwrite(str(REPO / f"validation/tracker-{NAME}-review-{s // 16 + 1}.jpg"), np.vstack([np.hstack(T[r:r + 4]) for r in range(0, 16, 4)]), [cv2.IMWRITE_JPEG_QUALITY, 82])
json.dump({"a": PA, "b": PB, "stats": stats, "cases": out}, open(REPO / f"out/synth/v3/review-{NAME}.json", "w"), indent=1)
print(stats, len(out))
