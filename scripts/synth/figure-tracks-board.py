"""Top-down tactics board from the figure tracks: what the overnight output looks like as data.

    python3 scripts/synth/figure-tracks-board.py <goal_id> [seconds_before ...]

Reads data/games/nm26-semifinal/rebuild/<goal_id>-figures.json (every frame of the goal window) and the puck track,
and draws the rink from above (inner board boundary, slot centrelines, goal lines) at the given times before the user's
goal moment (default -2.0 -1.2 -0.6 -0.3 -0.1 0.0 s): each figure as a dot at its tracked pivot with an arrow in its
facing direction (white/blue end blue, yellow end orange, goalies larger), the puck (black) when detected in that
frame. Writes validation/board-<goal_id>.png. The tracks are model output (PROPOSED, unsmoothed).
"""
import json, math, sys
from pathlib import Path
import cv2, numpy as np

REPO = Path(__file__).resolve().parents[2]; D = REPO / "data/games/nm26-semifinal"
gid = sys.argv[1]; times = [float(x) for x in sys.argv[2:]] or [-2.0, -1.2, -0.6, -0.3, -0.1, 0.0]
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
BOARD = np.array(G["board"]["inner_boundary"]["world"]["points_mm"])
HOME = {"W": 0.0, "E": 180.0}
lab = {r["id"]: r for r in json.loads((D / "goal-labels.json").read_text())["labels"]}[gid]
T = json.loads((D / "rebuild" / f"{gid}-figures.json").read_text()); C = T["columns"]; rows = T["rows"]
P = json.loads((D / lab["game"] / "puck-track.json").read_text()); pc = P["columns"]
puck = {int(r[pc.index("frame")]): (r[pc.index("x_mm")], r[pc.index("y_mm")]) for r in P["rows"] if r[pc.index("kind")] == "disk"}
FIG = [c[:-2] for c in C if c.endswith("_u")]
S = 1.2; W, H = int(870 * S), int(470 * S)


def px(p): return (int(round((p[0] + 435) * S)), int(round((235 - p[1]) * S)))  # +y (far board) up


def arc_point(Pts, u):
    seg = np.linalg.norm(np.diff(Pts, axis=0), axis=1); s = u * seg.sum(); acc = np.r_[0, np.cumsum(seg)]
    k = min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1); f = (s - acc[k]) / seg[k]
    return Pts[k] + f * (Pts[k + 1] - Pts[k])


tiles = []
for dt in times:
    f0 = int(round((lab["goal_video_s"] + dt) * 30)); r = min(rows, key=lambda r: abs(r[0] - f0)); v = dict(zip(C, r))
    im = np.full((H, W, 3), 250, np.uint8)
    cv2.polylines(im, [np.array([px(p) for p in BOARD], np.int32)], True, (60, 60, 60), 2)
    for x, col in ((0, (60, 60, 220)), (-120, (200, 120, 40)), (120, (200, 120, 40))):  # centre line, blue lines (nominal)
        cv2.line(im, px((x, -205)), px((x, 205)), col, 1)
    for pid, Pts in SLOT.items(): cv2.polylines(im, [np.array([px(p) for p in Pts], np.int32)], False, (205, 205, 205), 2)
    for f in FIG:
        p = arc_point(SLOT[f], v[f"{f}_u"]); a = math.radians(HOME[f[0]] + v[f"{f}_theta_deg"]); gk = f.endswith("-G")
        col = (200, 90, 20) if f[0] == "W" else (0, 150, 240)
        cv2.circle(im, px(p), 9 if gk else 6, col, -1)
        cv2.arrowedLine(im, px(p), px(p + (34 if gk else 28) * np.array([math.cos(a), math.sin(a)])), col, 2, tipLength=0.35)
        cv2.putText(im, f.split("-")[1], (px(p)[0] + 7, px(p)[1] - 7), 0, 0.42, col, 1)
    fr = r[0]; q = next((puck[k] for k in (fr, fr - 1, fr + 1) if k in puck), None)
    if q and q[0] is not None: cv2.circle(im, px(q), 7, (20, 20, 20), -1)
    cv2.putText(im, f"{gid}  {dt:+.1f} s", (10, 26), 0, 0.7, (0, 0, 0), 2)
    tiles.append(im)
while len(tiles) % 2: tiles.append(np.full_like(tiles[0], 255))
cv2.imwrite(str(REPO / f"validation/board-{gid}.png"), np.vstack([np.hstack(tiles[k:k + 2]) for k in range(0, len(tiles), 2)]))
print("validation/board-" + gid + ".png")
