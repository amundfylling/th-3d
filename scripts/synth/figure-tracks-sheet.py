"""Validation sheet for the figure tracks of a game: sampled frames with every figure's tracked pivot and facing drawn.

    /root/venvs/blender/bin/python scripts/synth/figure-tracks-sheet.py <game> [n_frames]

Reads data/games/nm26-semifinal/<game>/figure-tracks.json; draws, on the registered frame, a dot at each figure's
tracked pivot (slot position u) and a 30 mm arrow in its facing direction (white/blue end: blue; yellow end: orange;
a skater whose predicted pivot lies over 15 mm from its slot: red). Writes validation/figure-tracks-<game>.jpg.
"""
import json, math, sys
from pathlib import Path
import cv2, numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from nm26_common import frames, load, OUT  # noqa: E402

game = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
D = json.loads((REPO / f"data/games/nm26-semifinal/{game}/figure-tracks.json").read_text()); C = D["columns"]
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
HOME = {"W": 0.0, "E": 180.0}; ROI = (160, 360, 1900, 1000)
FIG = [c[:-2] for c in C if c.endswith("_u")]


def arc_point(P, u):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = u * seg.sum(); acc = np.r_[0, np.cumsum(seg)]
    k = min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1); f = (s - acc[k]) / seg[k]
    return P[k] + f * (P[k + 1] - P[k])


def proj(p):
    q = K @ (R @ np.array([p[0], p[1], 0.0]) + t); return q[:2] / q[2] - ROI[:2]


rows = [r for r in D["rows"] if not r[1]]; pick = [rows[int(k)] for k in np.linspace(len(rows) * 0.05, len(rows) * 0.95, n)]
F = {f[0]: f for f in load(OUT / game / "frames.json")}; tiles = []
for r in pick:
    i = r[0]; H = np.r_[F[i][2], 1].reshape(3, 3)
    img = next(a for j, a in frames(i / 30 - 0.01, i / 30 + 0.05) if j >= i)
    x0, y0, x1, y1 = ROI; im = cv2.warpPerspective(img, np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.0]]) @ H, (x1 - x0, y1 - y0))
    v = dict(zip(C, r))
    for f in FIG:
        u, th = v[f"{f}_u"], v[f"{f}_theta_deg"]; bad = v.get(f"{f}_slot_dist_mm", 0) > 15
        p = arc_point(SLOT[f], u); a = math.radians(HOME[f[0]] + th)
        col = (0, 0, 255) if bad else ((255, 120, 0) if f[0] == "W" else (0, 140, 255))
        q0 = proj(p); q1 = proj(p + 30 * np.array([math.cos(a), math.sin(a)]))
        cv2.circle(im, tuple(np.int32(q0)), 5, col, -1); cv2.arrowedLine(im, tuple(np.int32(q0)), tuple(np.int32(q1)), col, 3, tipLength=0.3)
    cv2.putText(im, f"{game} t={i / 30:.1f}s", (10, 34), 0, 1.1, (0, 0, 255), 3)
    tiles.append(cv2.resize(im, (870, 320)))
if len(tiles) % 2: tiles.append(np.zeros_like(tiles[0]))
cv2.imwrite(str(REPO / f"validation/figure-tracks-{game}.jpg"), np.vstack([np.hstack(tiles[k:k + 2]) for k in range(0, len(tiles), 2)]), [cv2.IMWRITE_JPEG_QUALITY, 82])
print(game, len(tiles), "frames")
