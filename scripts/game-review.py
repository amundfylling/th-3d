"""Review sheets for the match tracking: random frames with the tracked puck, and random possession episodes.

    /root/venvs/blender/bin/python scripts/game-review.py

Outputs: validation/game-puck-spotcheck.jpg (40 random match frames, fixed seed, tracked puck circled or "not seen"),
validation/game-possession-review.jpg (24 random possession episodes: the middle frame, the owner's exclusive area
outlined, the puck circled when seen). The judgements made from these sheets are recorded in
data/games/fylling-vs-moe-2022/review.json by hand.
"""
import cv2
import numpy as np

from game_common import FPS, GAME, MATCH_START_S, REPO, load, match_frames, proj, stabilised_crops, world_to_crop

tr = load(GAME / "puck-track.json")
po = load(GAME / "possession.json")
pos = {r[0]: r for r in tr["rows"]}
MF = list(match_frames())
rng = np.random.default_rng(23)
spot = sorted(rng.choice(MF, 40, replace=False).tolist())
eps = [e for e in po["episodes"] if e[0] != "nobody"]
rng2 = np.random.default_rng(5)
pick = sorted((eps[k] for k in rng2.choice(len(eps), min(24, len(eps)), replace=False)), key=lambda e: e[1])
epf = {int(round((MATCH_START_S + (e[1] + e[2]) / 2) * FPS)): e for e in pick}
want = set(spot) | set(epf)
Hc = world_to_crop()
tiles_a, tiles_b = {}, {}
for i, f in stabilised_crops():
    if i not in want:
        continue
    if i in spot:
        g = f[20:260, 30:770].copy()
        r = pos.get(i)
        if r:
            cv2.circle(g, (int(r[4]) - 30, int(r[5]) - 20), 12, (0, 255, 0), 2)
        cv2.putText(g, f"{spot.index(i)}: {i / FPS:.2f}s" + ("" if r else " not seen"), (5, 22), 0, 0.7, (0, 0, 255), 2)
        tiles_a[i] = g
    if i in epf:
        e = epf[i]
        g = f.copy()
        for q in po["exclusive_areas_mm"][e[0]]:
            cv2.polylines(g, [proj(Hc, q).astype(np.int32)], True, (0, 255, 255), 2)
        near = [j for j in range(i - 12, i + 13) if j in pos]
        if near:
            j = min(near, key=lambda j: abs(j - i))
            cv2.circle(g, (int(pos[j][4]), int(pos[j][5])), 12, (0, 255, 0), 2)
        cv2.putText(g, f"{pick.index(e)}: {e[0]} {e[1]:.1f}-{e[2]:.1f}s (video {i / FPS:.2f}s)", (5, 22), 0, 0.6, (0, 0, 255), 2)
        tiles_b[i] = g[0:280]


def sheet(tiles, path, cols=2):
    t = [tiles[k] for k in sorted(tiles)]
    while len(t) % cols:
        t.append(np.zeros_like(t[0]))
    cv2.imwrite(str(path), np.vstack([np.hstack(t[r:r + cols]) for r in range(0, len(t), cols)]), [cv2.IMWRITE_JPEG_QUALITY, 85])


sheet(tiles_a, REPO / "validation/game-puck-spotcheck.jpg")
sheet(tiles_b, REPO / "validation/game-possession-review.jpg")
print(len(tiles_a), len(tiles_b))
