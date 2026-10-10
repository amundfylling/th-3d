"""Build the skater label page: real NM26 crops, the user taps the skater's feet and then the direction it faces.

    /root/venvs/blender/bin/python scripts/synth/skater-facing-page.py

Uses the frames of scripts/synth/skater-frames.py. Per skater (10 slots) 40 crops from different frames, spread over the
seven games. The skater is found along its slot centreline by its kit colour where the frame differs from a per-game
median plate; the 200 x 200 crop is centred on it, and the page draws the slot centreline so the right figure is clear.
Order: wings, then centres, then defenders. The page stores taps in its db (collection "skaters": feet_px and dir_px in
crop px, or verdict "unsure"). Writes validation/skater-facing-review.html and
data/games/nm26-semifinal/skater-facing-crops.json (crop list with crop origins in reference video px; no images).
"""
import base64, json, random, re, sys
from pathlib import Path
import cv2, numpy as np

REPO = Path(__file__).resolve().parents[2]
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
ROI = (160, 360)  # skater-frames.py crop origin in reference video px
ORDER = ["W-LW", "E-LW", "W-RW", "E-RW", "W-C", "E-C", "W-LD", "E-LD", "W-RD", "E-RD"]
NAME = {"LW": "Left wing", "RW": "Right wing", "C": "Centre", "LD": "Left defence", "RD": "Right defence"}
KIT = {"W": "white/blue", "E": "yellow"}
N, S = 40, 200


def proj(P):
    P = np.atleast_2d(P); X = P @ R.T + t; q = X @ K.T; return q[:, :2] / q[:, 2:] - ROI


def resample(P, step=3.0):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); acc = np.r_[0, np.cumsum(seg)]; s = np.arange(0, acc[-1], step)
    return np.c_[np.interp(s, acc, P[:, 0]), np.interp(s, acc, P[:, 1])], s / acc[-1]


files = sorted((REPO / "out/synth/skaters/frames").glob("g*_*.jpg"))
byg = {}
for f in files: byg.setdefault(f.stem.split("_")[0], []).append(f)
plates = {g: np.median(np.stack([cv2.imread(str(f)) for f in fs]), 0).astype(np.uint8) for g, fs in byg.items()}


def team_mask(img, plate, end):
    d = np.abs(img.astype(np.int16) - plate.astype(np.int16)).sum(-1) > 60
    h = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); H, Sa, V = h[..., 0], h[..., 1], h[..., 2]
    col = ((H >= 15) & (H <= 35) & (Sa > 110) & (V > 110)) if end == "E" else (((H >= 100) & (H <= 130) & (Sa > 100)) | ((Sa < 45) & (V > 185)))
    return (d & col).astype(np.float32)


ring = np.array([(r * np.cos(a), r * np.sin(a), z) for r in (0, 8) for a in np.linspace(0, 2 * np.pi, 8, endpoint=False) for z in (8, 18, 28, 38)])
crops = []; rnd = random.Random(2026)
for pid in ORDER:
    end = pid[0]; pts, us = resample(SLOT[pid])
    games = sorted(byg); pick = []
    for i in range(N):  # spread over games: round robin, random frame within the game
        g = games[i % len(games)]; f = rnd.choice([x for x in byg[g] if x not in pick]); pick.append(f)
    for f in pick:
        g = f.stem.split("_")[0]; img = cv2.imread(str(f)); m = cv2.blur(team_mask(img, plates[g], end), (3, 3))
        best, bi = -1, 0
        for i, p in enumerate(pts):
            q = np.round(proj(ring + [p[0], p[1], 0])).astype(int)
            ok = (q[:, 0] >= 0) & (q[:, 0] < m.shape[1]) & (q[:, 1] >= 0) & (q[:, 1] < m.shape[0])
            sc = m[q[ok, 1], q[ok, 0]].sum() if ok.any() else 0
            if sc > best: best, bi = sc, i
        foot = proj(np.r_[pts[bi], 0])[0]
        cx, cy = int(round(foot[0] - S / 2)), int(round(foot[1] - S * 0.68))
        cx = min(max(cx, 0), img.shape[1] - S); cy = min(max(cy, 0), img.shape[0] - S)
        crop = img[cy:cy + S, cx:cx + S]
        line = proj(np.c_[pts[::4], np.zeros(len(pts[::4]))]) - [cx, cy]
        ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 84])
        crops.append({"id": f"{pid}-{f.stem}", "player_id": pid, "game": g, "frame": int(f.stem.split("_")[1]),
                      "crop_origin_ref_px": [cx + ROI[0], cy + ROI[1]], "found_u": round(float(us[bi]), 3), "found_score": float(best),
                      "slot_px": [[round(float(a), 1), round(float(b), 1)] for a, b in line],
                      "img": "data:image/jpeg;base64," + base64.b64encode(buf).decode()})
meta = {"description": "Real NM26 skater crops for the user's feet and facing taps (scripts/synth/skater-facing-page.py). "
        "Crop px + crop_origin_ref_px = reference video px (data/games/nm26-semifinal/camera-ref.json). found_u: the "
        "slot position where the kit colour was strongest (used only to centre the crop).",
        "crops": [{k: v for k, v in c.items() if k not in ("img", "slot_px")} for c in crops]}
(REPO / "data/games/nm26-semifinal/skater-facing-crops.json").write_text(json.dumps(meta, indent=1) + "\n")
data = [{"id": c["id"], "pid": c["player_id"], "game": c["game"], "slot": c["slot_px"], "img": c["img"]} for c in crops]
page = (Path(__file__).resolve().parent / "skater-facing.template.html").read_text()
labels = {pid: f"{NAME[pid[2:]]} · {'left' if pid[0] == 'W' else 'right'} end, {KIT[pid[0]]}" for pid in ORDER}
page = page.replace("/*DATA*/[]", json.dumps(data, separators=(",", ":"))).replace("/*LABELS*/{}", json.dumps(labels))
(REPO / "validation/skater-facing-review.html").write_text(page)
print(len(crops), "crops")
