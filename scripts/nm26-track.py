"""Puck track for one NM 2026 game: choose one candidate (or none) per frame.

    /root/venvs/blender/bin/python scripts/nm26-track.py g1

Inputs: out/nm26/<game>/frames.json (scripts/nm26-detect.py), data/games/nm26-semifinal/<game>/calibration.json.
Output: data/games/nm26-semifinal/<game>/puck-track.json.

- Every candidate (disk or smudge) is mapped to the ice plane (world mm) with the calibration.
- Emission score (log-odds-like, clipped):
  - disks: how well the blob matches a puck at that place (area against the projected puck top, darkness, neutral
    colour, compactness);
  - smudges: neutral grey, darker than the ice, puck-sized or a streak along its motion.
  - A STATIC_PENALTY applies where candidates pile up over the whole game (logos, sticks resting on the boards), from a
    candidate-density map.
- Viterbi over {absent, candidate 1..n} per frame. Moving between candidates costs (d / SIGMA)^2 / 2 (d in mm,
  impossible above D_MAX per frame); entering or leaving "absent" costs SWITCH.
- Smudges are kept only inside a straight fast run (a flight): at least MIN_RUN of them in a row (gaps of up to 2
  frames; a disk row at either end may join) fitting constant velocity within RUN_TOL_MM at RUN_MIN_SPEED or faster.
  Lone or erratic smudges are figure blur.
- Disks partly over dark print (the centre logo) are judged by darkness and width only (only the part over the light
  ice differs from the background); their centre is biased toward the light part.
- Flight filling: between two kept rows up to FILL_MAX_GAP frames apart and at least FILL_MIN_DIST apart, the
  candidates of the frames in between that lie within FILL_TOL of a constant-velocity path from one to the other
  (straight, or with one bounce at a candidate near the boards) are added (kind "..._fill"), if they cover at least 40 %
  of the frames in between.
- No positions are interpolated: frames without a chosen candidate are "not seen".
"""
import sys

import cv2
import numpy as np

from nm26_common import OUT, H_STAB, W_STAB, game_dir, load, proj, save, FPS, CFG, REPO

GAME = sys.argv[1] if len(sys.argv) > 1 else "g1"
SIGMA, D_MAX, SWITCH = 45.0, 140.0, 4.0
STATIC_PENALTY = 2.5
R_PUCK = load(REPO / "data/geometry.json")["puck"]["diameter"]["value"] / 2
F = load(OUT / GAME / "frames.json")
H = np.array(load(game_dir(GAME) / "calibration.json")["H_world_mm_to_stab_px"])
Hi = np.linalg.inv(H)

# expected puck-top size in stab px at each candidate (projected 25.4 mm circle)
circ = R_PUCK * np.c_[np.cos(np.linspace(0, 2 * np.pi, 16)), np.sin(np.linspace(0, 2 * np.pi, 16))]


def expected_wh(xy_world):
    q = proj(H, xy_world + circ)
    return np.ptp(q[:, 0]), np.ptp(q[:, 1])


bgv = cv2.cvtColor(cv2.imread(str(game_dir(GAME) / "background.png")), cv2.COLOR_BGR2HSV)[..., 2]


def dark_under(x, y, r=22):
    """Fraction of dark background around a candidate (the puck partly over dark print, e.g. the centre logo)."""
    y0, y1, x0, x1 = max(0, int(y) - r), int(y) + r, max(0, int(x) - r), int(x) + r
    return float((bgv[y0:y1, x0:x1] < 80).mean())


# density of disk candidates over the game (static false spots)
dens = np.zeros((H_STAB, W_STAB), np.float32)
for f in F:
    for c in f[3]:
        dens[min(int(c[1]), H_STAB - 1), min(int(c[0]), W_STAB - 1)] += 1
dens = cv2.GaussianBlur(dens, (0, 0), 4) * 2 * np.pi * 16
STATIC_LIMIT = 0.08 * len(F)  # a spot holding a disk candidate in more than 8 % of all frames


def score_disk(c, w):
    x, y, a, ww, hh, v, s, b_r, el, ang = c
    ew, eh = expected_wh(w)
    ra = a / (np.pi / 4 * ew * eh)
    sc = 3.0
    sc -= 2.5 * abs(np.log(max(ra, 1e-3)))          # puck-sized
    sc -= 1.5 * max(0.0, abs(np.log(ww / ew)) - 0.2) + 1.5 * max(0.0, abs(np.log(hh / eh)) - 0.25)
    sc -= 0.05 * max(0.0, v - 55)                    # dark
    sc -= 0.15 * max(0.0, abs(b_r) - 10)            # neutral (navy trousers are blue)
    partial = dark_under(x, y) > 0.15
    if partial:  # only the part over light ice differs from the background: judge darkness and width only
        sc = 3.0 - 1.5 * max(0.0, abs(np.log(ww / ew)) - 0.25) - 0.05 * max(0.0, v - 55) - 0.15 * max(0.0, abs(b_r) - 10) - 1.0
    else:
        sc -= 0.6 * max(0.0, el - 1.6)
    if dens[min(int(y), H_STAB - 1), min(int(x), W_STAB - 1)] > STATIC_LIMIT:
        sc -= STATIC_PENALTY
    return float(np.clip(sc, -6, 4))


def score_smudge(c, w):
    x, y, a, ww, hh, v, s, b_r, el, ang = c
    ew, eh = expected_wh(w)
    pa = np.pi / 4 * ew * eh
    sc = 1.5
    if a < 0.35 * pa:
        sc -= 2.0
    if a > 4.0 * pa:
        sc -= 2.0 * np.log(a / (4.0 * pa) + 1)
    sc -= 0.12 * max(0.0, abs(b_r) - 8)              # figure blur is tinted (blue, yellow)
    sc -= 0.03 * max(0.0, s - 35)
    return float(np.clip(sc, -6, 3))


rows_in = []
for f in F:
    cs = []
    for kind, lst, fn in (("disk", f[3], score_disk), ("smudge", f[4], score_smudge)):
        if not lst:
            continue
        P = np.array([[c[0], c[1]] for c in lst])
        Wd = proj(Hi, P)
        for c, w in zip(lst, Wd):
            cs.append((kind, float(w[0]), float(w[1]), fn(c, w), c[0], c[1]))
    rows_in.append((f[0], cs))

# Viterbi
prevS, prevXY, back = np.array([0.0]), np.zeros((0, 2)), []
for i, cs in rows_in:
    n = len(cs)
    S, B = np.zeros(n + 1), np.zeros(n + 1, int)
    opts = np.r_[prevS[0], prevS[1:] - SWITCH]
    S[0], B[0] = opts.max(), int(opts.argmax())
    if n:
        XY = np.array([[c[1], c[2]] for c in cs])
        em = np.array([c[3] for c in cs])
        for j in range(n):
            o = [prevS[0] - SWITCH]
            if len(prevXY):
                d = np.hypot(*(prevXY - XY[j]).T)
                t = prevS[1:] - 0.5 * (d / SIGMA) ** 2
                t[d > D_MAX] = -1e9
                o += list(t)
            k = int(np.argmax(o))
            S[j + 1], B[j + 1] = o[k] + em[j], k
        prevXY = XY
    else:
        prevXY = np.zeros((0, 2))
    back.append(B)
    prevS = S
st = int(np.argmax(prevS))
rows = []
for (i, cs), B in zip(reversed(rows_in), reversed(back)):
    if st > 0:
        k, x, y, sc, u, v = cs[st - 1]
        rows.append([i, round(i / FPS, 3), round(x, 1), round(y, 1), round(u, 1), round(v, 1), k, round(sc, 2)])
    st = B[st]
rows.reverse()

# smudges count only inside a straight fast run (a flight): at least MIN_RUN smudge rows in a row (gaps of up to 2
# frames, disk rows at either end allowed) that fit constant velocity within RUN_TOL_MM at RUN_MIN_SPEED or faster
MIN_RUN, RUN_TOL_MM, RUN_MIN_SPEED = 3, 18.0, 250.0


def fits_flight(seg):
    t = np.array([r[0] for r in seg], float) / FPS
    X = np.array([[r[2], r[3]] for r in seg])
    if len(seg) < MIN_RUN:
        return np.zeros(len(seg), bool)
    best = np.zeros(len(seg), bool)
    for a in range(len(seg)):
        for b in range(a + 1, len(seg)):
            v = (X[b] - X[a]) / (t[b] - t[a])
            if np.hypot(*v) < RUN_MIN_SPEED:
                continue
            inl = np.hypot(*(X - (X[a] + np.outer(t - t[a], v))).T) <= RUN_TOL_MM
            if inl.sum() > best.sum():
                best = inl
    return best if best.sum() >= MIN_RUN else np.zeros(len(seg), bool)


keep = [True] * len(rows)
k = 0
while k < len(rows):
    if rows[k][6] != "smudge":
        k += 1
        continue
    j = k
    while j + 1 < len(rows) and rows[j + 1][6] == "smudge" and rows[j + 1][0] - rows[j][0] <= 3:
        j += 1
    lo = k - 1 if k > 0 and rows[k][0] - rows[k - 1][0] <= 3 else k
    hi = j + 1 if j + 1 < len(rows) and rows[j + 1][0] - rows[j][0] <= 3 else j
    seg = rows[lo:hi + 1]
    ok = fits_flight(seg)
    for m, r in enumerate(seg):
        if r[6] == "smudge" and not ok[m]:
            keep[lo + m] = False
    k = j + 1
dropped = sum(1 for x in keep if not x)
rows = [r for r, x in zip(rows, keep) if x]
# fill flights: between two consecutive kept rows that are far apart, look for the candidates of the frames in between
# that fit a constant-velocity path from one to the other, straight or with one board bounce
FILL_MAX_GAP, FILL_MIN_DIST, FILL_TOL = 30, 60.0, 22.0
from shapely.geometry import Point, Polygon
BOARD = Polygon(load(REPO / "data/geometry.json")["board"]["inner_boundary"]["world"]["points_mm"])
cand_at = {i: cs for i, cs in rows_in}
filled = []
for ra, rb in zip(rows, rows[1:]):
    ia, ib = ra[0], rb[0]
    A, B = np.array(ra[2:4]), np.array(rb[2:4])
    if not (2 <= ib - ia <= FILL_MAX_GAP) or np.hypot(*(B - A)) < FILL_MIN_DIST:
        continue
    mids = [(k, c) for k in range(ia + 1, ib) for c in cand_at.get(k, []) if c[3] > -3]
    if not mids:
        continue

    def path_fit(corners):
        """corners: list of (frame, xy) including A and B; returns {frame: candidate} of fitting candidates."""
        got = {}
        for k, c in mids:
            for (f0, p0), (f1, p1) in zip(corners, corners[1:]):
                if f0 <= k <= f1:
                    pr = p0 + (p1 - p0) * (k - f0) / max(f1 - f0, 1)
                    d = np.hypot(c[1] - pr[0], c[2] - pr[1])
                    if d <= FILL_TOL and (k not in got or d < got[k][0]):
                        got[k] = (d, c)
                    break
        return got

    best = path_fit([(ia, A), (ib, B)])
    for k, c in mids:  # one bounce at a candidate near the boards
        if BOARD.exterior.distance(Point(c[1], c[2])) < 45:
            g = path_fit([(ia, A), (k, np.array([c[1], c[2]])), (ib, B)])
            g[k] = (0.0, c)
            if len(g) > len(best) + 1:
                best = g
    if len(best) >= max(2, 0.4 * (ib - ia - 1)):
        for k, (d, c) in best.items():
            filled.append([k, round(k / FPS, 3), round(c[1], 1), round(c[2], 1), round(c[4], 1), round(c[5], 1), c[0] + "_fill", round(c[3], 2)])
have = {r[0] for r in rows}
rows = sorted(rows + [r for r in filled if r[0] not in have], key=lambda r: r[0])

t0, t1 = CFG["games"][GAME]["video_window_s"]
nf = len(F)
save(game_dir(GAME) / "puck-track.json", {
    "description": "Puck track (scripts/nm26-track.py): one row per frame where a candidate was chosen; other frames are not seen.",
    "columns": ["frame", "video_t_s", "x_mm", "y_mm", "u_stab_px", "v_stab_px", "kind", "score"],
    "position_note": "Blob centre projected onto the ice plane. The puck's top face is 12 mm above the ice (preview thickness), so a point shifts away from the camera (+y) by a few mm; not corrected.",
    "smudges_dropped_outside_flights": dropped,
    "tracker": {"min_run": MIN_RUN, "run_tol_mm": RUN_TOL_MM, "run_min_speed_mm_s": RUN_MIN_SPEED, "sigma_mm": SIGMA, "d_max_mm_per_frame": D_MAX, "switch_cost": SWITCH, "static_penalty": STATIC_PENALTY},
    "frames": nf, "seen_fraction": round(len(rows) / nf, 3),
    "seen_by_kind": {k: sum(1 for r in rows if r[6] == k) for k in ("disk", "smudge", "disk_fill", "smudge_fill")},
    "rows": rows,
}, indent=None)
print("frames", nf, "seen", len(rows), round(len(rows) / nf, 3), {k: sum(1 for r in rows if r[6] == k) for k in ("disk", "smudge", "disk_fill", "smudge_fill")})
