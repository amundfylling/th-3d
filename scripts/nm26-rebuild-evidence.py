"""Evidence pack for rebuilding a real NM26 goal in 3D (first target: Nygård's Edwall shovel hat-trick, game 2).

    /root/venvs/blender/bin/python scripts/nm26-rebuild-evidence.py <goal_id> [seconds_before]

From the user's goal label (data/games/nm26-semifinal/goal-labels.json: the moment the puck crosses the line), takes
the window goal - seconds_before (default 4) to goal + 0.5 s and writes:
- out/nm26/rebuild/<goal_id>/frames/<frame>.jpg: every frame, registered to the reference frame, attacking half;
- data/games/nm26-semifinal/rebuild/<goal_id>-evidence.json: the automatic puck track (PROPOSED) and the defending
  goalie's pose per frame from the synthetic-data model C (out/synth/goalie-pose-v2c.pt; PROPOSED);
- validation/rebuild-<goal_id>-sheet.jpg: every 0.2 s of the last 3 s, with the puck track drawn (cyan dots, the
  current position magenta) and the goalie's predicted facing (green arrow).
"""
import importlib.util, json, math, sys
from pathlib import Path

import cv2
import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "scripts/synth"))
from nm26_common import frames, load, OUT  # noqa: E402

gid = sys.argv[1]; before = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0
lab = {r["id"]: r for r in json.loads((REPO / "data/games/nm26-semifinal/goal-labels.json").read_text())["labels"]}[gid]
game, t_goal, end = lab["game"], lab["goal_video_s"], lab["scoring_end"]
defend = "E" if end == "W" else "W"
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"]); BOX = CAM["goal_crop_boxes_video_px"]
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
HOME = {"W": 0.0, "E": 180.0}
HALF = (900, 360, 1900, 1000) if defend == "E" else (160, 360, 1160, 1000)  # attacking half, reference px

spec = importlib.util.spec_from_file_location("tr", REPO / "scripts/synth/train-goalie-pose.py"); tr = importlib.util.module_from_spec(spec)
argv = sys.argv; sys.argv = [argv[0], "0"]; spec.loader.exec_module(tr); sys.argv = argv
net = tr.model(); net.load_state_dict(torch.load(REPO / "out/synth/goalie-pose-v2c.pt")); net.eval()


def proj(P):
    P = np.atleast_2d(P); X = np.c_[P, np.zeros(len(P))] @ R.T + t; q = X @ K.T; return q[:, :2] / q[:, 2:]


def arc_point(P, u):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = u * seg.sum(); acc = np.r_[0, np.cumsum(seg)]
    k = min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1); f = (s - acc[k]) / seg[k]
    return P[k] + f * (P[k + 1] - P[k])


t0, t1 = t_goal - before, t_goal + 0.5
F = {f[0]: f for f in load(OUT / game / "frames.json")}
P = json.loads((REPO / f"data/games/nm26-semifinal/{game}/puck-track.json").read_text())
puck = [dict(zip(P["columns"], r)) for r in P["rows"] if t0 <= r[1] <= t1]
od = OUT / "rebuild" / gid / "frames"; od.mkdir(parents=True, exist_ok=True)
x0, y0, x1, y1 = HALF; T0 = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.0]])
bx = BOX[defend]; TB = np.array([[1, 0, -bx[0]], [0, 1, -bx[1]], [0, 0, 1.0]])
goalie, imgs, H = [], {}, None
for i, a in frames(t0, t1):
    if i in F: H = np.r_[F[i][2], 1].reshape(3, 3)
    if H is None: continue
    im = cv2.warpPerspective(a, T0 @ H, (x1 - x0, y1 - y0)); cv2.imwrite(str(od / f"{i}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 92]); imgs[i] = im
    crop = cv2.warpPerspective(a, TB @ H, (bx[2] - bx[0], bx[3] - bx[1]))
    with torch.no_grad(): p = net(tr.to_tensor(crop, defend)[None])[0].numpy()
    u = float(np.clip(p[0], 0, 1)); th = float(np.degrees(np.arctan2(p[1], p[2])) % 360)
    goalie.append({"frame": i, "video_t_s": round(i / 30, 3), "u": round(u, 4), "theta_deg": round(th, 1), "facing_deg": round((HOME[defend] + th) % 360, 1)})
ev = {"description": f"Evidence for rebuilding {gid} in 3D (scripts/nm26-rebuild-evidence.py). Window {t0:.2f}-{t1:.2f} s video "
      f"time; goal moment {t_goal} s (user). Puck: automatic track (PROPOSED). Goalie {defend}-G: synthetic-data model C "
      "(PROPOSED; facing 0 = +x, counter-clockwise from above).", "goal": lab, "puck": puck, f"goalie_{defend}": goalie}
(REPO / "data/games/nm26-semifinal/rebuild").mkdir(parents=True, exist_ok=True)
(REPO / f"data/games/nm26-semifinal/rebuild/{gid}-evidence.json").write_text(json.dumps(ev, indent=1, ensure_ascii=False) + "\n")
# contact sheet: every 6th frame of the last 3 s
pk = {r["frame"]: r for r in puck}; gl = {g["frame"]: g for g in goalie}
keys = [i for i in sorted(imgs) if i / 30 >= t_goal - 3.0][::6]
tiles = []
for i in keys:
    im = imgs[i].copy()
    for r in puck:
        if r["frame"] <= i and r["x_mm"] is not None:
            q = proj([r["x_mm"], r["y_mm"]])[0] - [x0, y0]; cv2.circle(im, tuple(np.int32(q)), 2, (255, 255, 0), -1)
    if i in pk and pk[i]["x_mm"] is not None:
        q = proj([pk[i]["x_mm"], pk[i]["y_mm"]])[0] - [x0, y0]; cv2.circle(im, tuple(np.int32(q)), 7, (255, 0, 255), 2)
    if i in gl:
        g = gl[i]; pv = arc_point(SLOT[f"{defend}-G"], g["u"]); a = math.radians(g["facing_deg"])
        q0 = proj(pv)[0] - [x0, y0]; q1 = proj(pv + 40 * np.array([math.cos(a), math.sin(a)]))[0] - [x0, y0]
        cv2.arrowedLine(im, tuple(np.int32(q0)), tuple(np.int32(q1)), (0, 200, 0), 2, tipLength=0.3)
    cv2.putText(im, f"{i / 30 - t_goal:+.1f} s", (8, 28), 0, 0.9, (0, 0, 255), 2)
    tiles.append(cv2.resize(im, (500, 320)))
while len(tiles) % 3: tiles.append(np.zeros_like(tiles[0]))
cv2.imwrite(str(REPO / f"validation/rebuild-{gid}-sheet.jpg"), np.vstack([np.hstack(tiles[k:k + 3]) for k in range(0, len(tiles), 3)]), [cv2.IMWRITE_JPEG_QUALITY, 82])
print(gid, len(imgs), "frames,", len(puck), "puck rows,", len(goalie), "goalie poses")
