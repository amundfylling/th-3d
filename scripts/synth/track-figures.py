"""Track all twelve figures (slot position u and rotation) through an NM26 game with the synthetic-data models.

    /root/venvs/blender/bin/python scripts/synth/track-figures.py <game> [--fps 10] [--goal-fps 30]

Per sampled frame (registered to the reference frame):
- skaters: the kit-colour localiser of the label page finds each skater along its slot (difference from the game's rink
  plate, team colour, best slot position); a 200 x 200 crop around it goes to the skater model v2b
  (out/synth/skater-pose-v2b.pt), which places the pivot in the crop and reads the rotation. u follows from the pivot
  pixel; slot_dist_mm is how far that pixel lies from the slot (large = doubtful);
- goalies: the fixed goal-box crop and goalie model C (out/synth/goalie-pose-v2c.pt).
Frames: every 1/fps s over the game's video window, and every frame (goal-fps) from 8 s before to 1 s after each goal
(user goal moments where labelled, else the score-box time - 12 s .. box time).
Writes data/games/nm26-semifinal/<game>/figure-tracks.json (columns per figure: u, theta_deg, slot_dist_mm for skaters;
u, theta_deg for goalies; theta relative to the team's home heading, as the models). Skips a game whose file exists
(rerun after a container restart continues with the next game). Status: PROPOSED (model output, no smoothing).
"""
import importlib.util, json, math, sys, time
from pathlib import Path

import cv2
import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "scripts/synth"))
from nm26_common import frames, load, OUT  # noqa: E402

A = sys.argv[1:]; game = A[0]
def arg(n, d): return A[A.index(n) + 1] if n in A else d
FPS = float(arg("--fps", 10)); GFPS = float(arg("--goal-fps", 30))
dest = REPO / f"data/games/nm26-semifinal/{game}/figure-tracks.json"
if dest.exists() and "--force" not in A and "--test-seconds" not in A: print(game, "done already"); sys.exit()
torch.set_num_threads(int(arg("--threads", 4)))


def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    argv = sys.argv; sys.argv = [argv[0], "0"]; spec.loader.exec_module(m); sys.argv = argv; return m


ts = load_mod("ts", REPO / "scripts/synth/train-skater-pose.py"); tg = load_mod("tg", REPO / "scripts/synth/train-goalie-pose.py")
sk = ts.model(); sk.load_state_dict(torch.load(REPO / "out/synth/skater-pose-v2b.pt")); sk.eval()
gk = tg.model(); gk.load_state_dict(torch.load(REPO / "out/synth/goalie-pose-v2c.pt")); gk.eval()
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"]); BOX = CAM["goal_crop_boxes_video_px"]
ROI = (160, 360, 1900, 1000); x0, y0, x1, y1 = ROI; T0 = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.0]])
ORDER = ts.ORDER; SLOT = ts.SLOT
plate = cv2.imread(str(REPO / f"out/synth/skaters/plate_{game}.png"))


def proj3(P):
    X = np.atleast_2d(P) @ R.T + t; q = X @ K.T; return q[:, :2] / q[:, 2:] - [x0, y0]


def resample(P, step=3.0):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); acc = np.r_[0, np.cumsum(seg)]; s = np.arange(0, acc[-1], step)
    return np.c_[np.interp(s, acc, P[:, 0]), np.interp(s, acc, P[:, 1])]


ring = np.array([(r * np.cos(a), r * np.sin(a), z) for r in (0, 8) for a in np.linspace(0, 2 * np.pi, 8, endpoint=False) for z in (8, 18, 28, 38)])
CAND = {}
for pid in ORDER:  # projected body sample points for every slot position (precomputed)
    pts = resample(SLOT[pid]); q = np.stack([proj3(ring + [p[0], p[1], 0]) for p in pts]); CAND[pid] = (pts, np.round(q).astype(int), proj3(np.c_[pts, np.zeros(len(pts))]))


def team_mask(img, end):
    d = np.abs(img.astype(np.int16) - plate.astype(np.int16)).sum(-1) > 60
    h = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); H, Sa, V = h[..., 0], h[..., 1], h[..., 2]
    col = ((H >= 15) & (H <= 35) & (Sa > 110) & (V > 110)) if end == "E" else (((H >= 100) & (H <= 130) & (Sa > 100)) | ((Sa < 45) & (V > 185)))
    return cv2.blur((d & col).astype(np.float32), (3, 3))


def locate(m, pid):
    pts, q, foot = CAND[pid]; hh, ww = m.shape
    ok = (q[..., 0] >= 0) & (q[..., 0] < ww) & (q[..., 1] >= 0) & (q[..., 1] < hh)
    sc = np.where(ok, m[np.clip(q[..., 1], 0, hh - 1), np.clip(q[..., 0], 0, ww - 1)], 0).sum(1)
    i = int(np.argmax(sc)); return foot[i], float(sc[i])


# frame list
T = json.loads((REPO / "data/games/nm26-semifinal/timeline.json").read_text())["games"][game]
CFG = json.loads((REPO / "data/games/nm26-semifinal/config.json").read_text())["games"][game]
w0, w1 = CFG["video_window_s"]
labs = {r["id"]: r for r in json.loads((REPO / "data/games/nm26-semifinal/goal-labels.json").read_text())["labels"]}
dense = []
for k, g in enumerate(T["goals"]):
    lab = labs.get(f"{game}-goal{k + 1}")
    if lab and lab.get("goal_video_s"): dense.append((lab["goal_video_s"] - 8, lab["goal_video_s"] + 1))
    elif g.get("overlay_change_s"): dense.append((g["overlay_change_s"] - 12, g["overlay_change_s"]))
step = int(round(30 / FPS)); gstep = int(round(30 / GFPS))
F = {f[0]: f for f in load(OUT / game / "frames.json")}
rows = []; H = None; t_start = time.time()
if "--test-seconds" in A: w0 = w0 + 120; w1 = w0 + float(arg("--test-seconds", 2)); dest = REPO / "out/synth/track-test.json"
for i, a in frames(w0, w1):
    tt = i / 30.0; dn = any(s <= tt <= e for s, e in dense)
    if i in F: H = np.r_[F[i][2], 1].reshape(3, 3)
    if H is None or (i % (gstep if dn else step)): continue
    img = cv2.warpPerspective(a, T0 @ H, (x1 - x0, y1 - y0))
    masks = {e: team_mask(img, e) for e in "WE"}; crops, origins, scores = [], [], []
    for pid in ORDER:
        foot, sc = locate(masks[pid[0]], pid)
        cx = int(round(foot[0] - 100)); cy = int(round(foot[1] - 136))
        cx = min(max(cx, 0), img.shape[1] - 200); cy = min(max(cy, 0), img.shape[0] - 200)
        crops.append(ts.to_tensor(img[cy:cy + 200, cx:cx + 200], pid)); origins.append((cx + x0, cy + y0)); scores.append(sc)
    gc = []
    for e in "WE":
        bx = BOX[e]; TB = np.array([[1, 0, -bx[0]], [0, 1, -bx[1]], [0, 0, 1.0]])
        gc.append(tg.to_tensor(cv2.warpPerspective(a, TB @ H, (bx[2] - bx[0], bx[3] - bx[1])), e))
    with torch.no_grad():
        P = sk(torch.stack(crops)).numpy(); Q = gk(torch.stack(gc)).numpy()
    row = [i, int(dn)]
    for pid, p, o, sc in zip(ORDER, P, origins, scores):
        u, d = ts.pivot_to_u(pid, ts.net_to_px(p[:2]), o)
        row += [round(float(u), 4), round(float(np.degrees(np.arctan2(p[2], p[3])) % 360), 1), round(float(d), 1)]
    for q in Q:
        row += [round(float(np.clip(q[0], 0, 1)), 4), round(float(np.degrees(np.arctan2(q[1], q[2])) % 360), 1)]
    rows.append(row)
    if len(rows) % 500 == 0: print(game, len(rows), "frames", round(time.time() - t_start), "s", flush=True)
cols = ["frame", "dense"] + [f"{p}_{c}" for p in ORDER for c in ("u", "theta_deg", "slot_dist_mm")] + [f"{e}-G_{c}" for e in "WE" for c in ("u", "theta_deg")]
out = {"description": f"Figure tracks for NM26 {game} (scripts/synth/track-figures.py): every {step} frames, and every frame "
       "around each goal (dense = 1). Skaters: model v2b on kit-colour-localised crops; goalies: model C. u = slot position "
       "0-1 along the slot centreline (data/geometry.json); theta_deg = rotation relative to the team's home heading (W 0, "
       "E 180); slot_dist_mm = how far the predicted pivot lies from the slot (large = doubtful). PROPOSED, unsmoothed.",
       "columns": cols, "rows": rows}
dest.write_text(json.dumps(out, separators=(",", ":")) + "\n")
print(game, "done", len(rows), "frames", round(time.time() - t_start), "s")
