"""Puck track of one NM26 game with the synthetic puck detector (docs/synthetic-puck.md).

    /root/venvs/blender/bin/python scripts/synth/track-puck.py <game> [--model puck-det-v1] [--detect-only] [--track-only]
        [--t0 S --t1 S] [--tracker 1|2] [--out <file>] [--shot-completion]

1. Detect (four worker processes, time chunks): every frame of the game window is warped to stab px with the
   homography interpolated from out/nm26/<game>/H.npz (scripts/synth/puck-frames.py: every 6th frame registered);
   the detector (out/synth/<model>.pt) sees frames t-1, t, t+1 and the game's background and gives a heatmap for t;
   up to 6 peaks per frame with score >= 0.05 are kept (stab px, score; since 2026-10-11 also bgdiff, the colour
   difference from the empty rink at the blob) in out/nm26/<game>/puck-cands-<model>.json
   (cache, not committed).
2. Track: Viterbi over {absent, peak 1..n} per frame, as scripts/nm26-track.py but with the detector's score as the
   emission (logit of the score, clipped to [-4, 5]) and a faster motion limit (the detector sees blur):
   moving costs (d / SIGMA)^2 / 2 with d in mm per frame, impossible above D_MAX; entering or leaving "absent" costs
   SWITCH. No interpolation: frames without a chosen peak are "not seen".
   Positions: the detector's point is the puck's top-face centre, mapped to the ice through the reference camera on the
   plane 12 mm above the ice (the Blender puck's top), so x_mm, y_mm are the puck centre without the +y shift of the
   blob centre that puck-track.json carries (see docs/synthetic-puck.md).
Writes data/games/nm26-semifinal/<game>/puck-track-synth.json (same columns as puck-track.json; kind "det").
3. Tracker 2 (--tracker 2, docs/synthetic-puck.md section 8; writes puck-track-synth-v2.json by the runner): the same
   Viterbi, then still low-score runs (dark ice marks: the ISOVER logo's "o", the centre spot) are removed from the
   candidates and the Viterbi runs again. --bg-min drops candidates that match the empty rink (bgdiff, needs v2
   candidates; 0 = off). --shot-completion (off by default) adds weak peaks on a line into a goal mouth where the track
   stops, as kind "shot"; the review found them on the goalie or figures, not on the puck (section 8).
"""
import json, sys, time
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "scripts/synth"))
from nm26_common import CFG, OUT, T_ROI, W_STAB, H_STAB, X0, Y0, frames, game_dir, save, FPS  # noqa: E402

A = sys.argv[1:]; GAME = A[0]
def arg(n, d): return A[A.index(n) + 1] if n in A else d
MODEL = arg("--model", "puck-det-v1"); WORKERS = int(arg("--workers", 4))
T0, T1 = float(arg("--t0", CFG["games"][GAME]["video_window_s"][0])), float(arg("--t1", CFG["games"][GAME]["video_window_s"][1]))
CANDS = OUT / GAME / f"puck-cands-{MODEL}.json"
SIGMA, D_MAX, SWITCH = 60.0, float(arg("--dmax", 350.0)), 3.0
BIAS = float(arg("--bias", 1.0))  # added to every emission (1.0 chosen by the frame review, docs/synthetic-puck.md)
OUT_NAME = arg("--out", "puck-track-synth.json")
TOP_MM = 12.0
BLOB_DV = 8.8  # stab px: the dark blob's centre lies this far below the top-face centre (docs/synthetic-puck.md 2C)
DISK7 = np.hypot(*np.mgrid[-7:8, -7:8]) <= 7
# tracker 2 (--tracker 2, docs/synthetic-puck.md section 8; ASSUMED values, set on the v2 candidates):
TRACKER = int(arg("--tracker", 1))
BG_MIN = float(arg("--bg-min", 0.0))          # a candidate this close to the empty rink (bgdiff) is no puck
STATIC_N, STATIC_PX, STATIC_SCORE = 15, 5.0, 0.55  # a still run (>= 15 rows within 5 px) of median score < 0.55 is an ice mark
SHOT_MIN_SPEED, SHOT_REACH_MM, SHOT_MAX_GAP = 1500.0, 150.0, 4
SHOT_COMPLETION = "--shot-completion" in A   # off by default: its rows are not sightings (docs/synthetic-puck.md 8.4)
SHOT_MIN_SCORE = float(arg("--shot-min-score", 0.05)); SHOT_COS = np.cos(np.radians(20.0))
SHOT_QUIET = int(arg("--shot-quiet", 0))   # a completed shot is kept only if the track has no row for this many frames after it
G = json.loads((REPO / "data/geometry.json").read_text())
HW = json.loads((REPO / "validation/12-hardware-report.json").read_text())["goal"]
R_PUCK = G["puck"]["diameter"]["value"] / 2
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
Kc, Rc, tc = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
# plane z = TOP_MM: world (x, y) -> stab px
H_TOP = np.array([[1, 0, -X0], [0, 1, -Y0], [0, 0, 1.0]]) @ Kc @ np.c_[Rc[:, 0], Rc[:, 1], Rc[:, 2] * TOP_MM + tc]
H_TOP_INV = np.linalg.inv(H_TOP)


def homographies():
    z = np.load(OUT / GAME / "H.npz")
    f, H8 = z["frame"], z["H8"]
    Hn = np.c_[H8, np.ones(len(H8))]
    return f, Hn


def H_at(i, f, Hn):
    k = np.searchsorted(f, i)
    if k < len(f) and f[k] == i: return Hn[k].reshape(3, 3)
    if k == 0: return Hn[0].reshape(3, 3)
    if k >= len(f): return Hn[-1].reshape(3, 3)
    a, b = f[k - 1], f[k]; w = (i - a) / (b - a)
    return ((1 - w) * Hn[k - 1] + w * Hn[k]).reshape(3, 3)


def detect(chunk):
    import torch
    torch.set_num_threads(1)
    tp = __import__("importlib").import_module("train_puck_detector_mod")
    net = tp.PuckNet(); net.load_state_dict(torch.load(REPO / f"out/synth/{MODEL}.pt")); net.eval()
    bg = cv2.imread(str(game_dir(GAME) / "background.png"))
    bgh = cv2.resize(bg, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    f, Hn = homographies()
    t0, t1 = chunk
    buf, out = [], []
    bgf = bgh.astype(np.int16)
    def bgdiff(img, u, v):
        """Mean colour difference from the empty rink in a 7 px (half-res) disk at the dark blob (8.8 px below the
        detected top-face centre, stab px): a puck differs; a dark ice logo that the detector mistakes for one does not."""
        x, y = int(round(u / 2)), int(round((v + BLOB_DV) / 2))
        if not (7 <= x < img.shape[1] - 7 and 7 <= y < img.shape[0] - 7): return 99.0
        d = np.abs(img[y - 7:y + 8, x - 7:x + 8].astype(np.int16) - bgf[y - 7:y + 8, x - 7:x + 8]).max(2)
        return float(d[DISK7].mean())
    def run(batch):
        x = torch.from_numpy(np.stack(batch["x"]))
        with torch.no_grad():
            lg, of = net(x)
        v, iy, ix = tp.peaks(lg[:, 0], k=6)
        for b, i in enumerate(batch["i"]):
            c = []
            for j in range(v.shape[1]):
                s = float(v[b, j])
                if s < 0.05: continue
                yy, xx = int(iy[b, j]), int(ix[b, j])
                pu, pv = (xx + float(of[b, 0, yy, xx])) * tp.STRIDE, (yy + float(of[b, 1, yy, xx])) * tp.STRIDE
                c.append([round(pu, 1), round(pv, 1), round(s, 4), round(bgdiff(batch["img"][b], pu, pv), 1)])
            out.append([i, c])
    batch = {"x": [], "i": [], "img": []}
    for i, a in frames(max(T0, t0 - 1 / FPS - 1e-3), min(T1, t1 + 1 / FPS + 1e-3)):
        w = cv2.warpPerspective(a, T_ROI @ H_at(i, f, Hn), (W_STAB, H_STAB), flags=cv2.INTER_LINEAR)
        buf.append((i, cv2.resize(w, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)))
        if len(buf) > 3: buf.pop(0)
        if len(buf) == 3 and buf[2][0] - buf[0][0] == 2 and t0 <= buf[1][0] / FPS < t1:
            x = np.concatenate([buf[0][1], buf[1][1], buf[2][1], bgh], 2).astype(np.float32) / 255.0 - 0.5
            batch["x"].append(x.transpose(2, 0, 1).copy()); batch["i"].append(buf[1][0]); batch["img"].append(buf[1][1])
            if len(batch["i"]) == 8:
                run(batch); batch = {"x": [], "i": [], "img": []}
    if batch["i"]: run(batch)
    return out


def candidates(C):
    rows_in = []
    for i, cs in C:
        if not cs: rows_in.append((i, [])); continue
        P = np.array([[c[0], c[1]] for c in cs])
        q = np.c_[P, np.ones(len(P))] @ H_TOP_INV.T; Wd = q[:, :2] / q[:, 2:]
        rows_in.append((i, [(float(w[0]), float(w[1]), float(np.clip(np.log(c[2] / (1 - c[2] + 1e-6)), -4, 5) + BIAS), c[0], c[1], c[2],
                             c[3] if len(c) > 3 else None) for c, w in zip(cs, Wd)]))
    return rows_in


def track(C):
    return viterbi(candidates(C))


def viterbi(rows_in):
    prevS, prevXY, prevI, back = np.array([0.0]), np.zeros((0, 2)), None, []
    for i, cs in rows_in:
        gap = 1 if prevI is None else max(1, i - prevI); prevI = i
        n = len(cs)
        S, B = np.zeros(n + 1), np.zeros(n + 1, int)
        opts = np.r_[prevS[0], prevS[1:] - SWITCH]
        S[0], B[0] = opts.max(), int(opts.argmax())
        if n:
            XY = np.array([[c[0], c[1]] for c in cs]); em = np.array([c[2] for c in cs])
            for j in range(n):
                o = [prevS[0] - SWITCH]
                if len(prevXY):
                    d = np.hypot(*(prevXY - XY[j]).T) / gap
                    tt = prevS[1:] - 0.5 * (d / SIGMA) ** 2
                    tt[d > D_MAX] = -1e9
                    o += list(tt)
                k = int(np.argmax(o)); S[j + 1], B[j + 1] = o[k] + em[j], k
            prevXY = XY
        else:
            prevXY = np.zeros((0, 2))
        back.append(B); prevS = S
    st = int(np.argmax(prevS)); rows = []
    for (i, cs), B in zip(reversed(rows_in), reversed(back)):
        if st > 0:
            x, y, em, u, v, s = cs[st - 1][:6]
            rows.append([i, round(i / FPS, 3), round(x, 1), round(y, 1), round(u, 1), round(v, 1), "det", round(s, 3)])
        st = B[st]
    rows.reverse()
    return rows


def static_runs(rows):
    """Index ranges of still runs (STATIC_N rows or more, gaps <= 3 frames, all within STATIC_PX of the first) whose median
    score is under STATIC_SCORE: in the v1 track these are dark ice marks (the 'o' of the near ISOVER logo, the centre
    spot), not a resting puck, which scores 0.7-0.99 (docs/synthetic-puck.md section 8)."""
    out, i = [], 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and rows[j + 1][0] - rows[j][0] <= 3 and np.hypot(rows[j + 1][4] - rows[i][4], rows[j + 1][5] - rows[i][5]) < STATIC_PX:
            j += 1
        if j - i + 1 >= STATIC_N and np.median([r[7] for r in rows[i:j + 1]]) < STATIC_SCORE:
            out.append((i, j))
        i = j + 1
    return out


def goal_entry(p, q):
    """Goal id if the step p -> q (world mm) heads into a goal mouth, as scripts/nm26-passes.py goal_entry: it moves toward
    that goal, ends within SHOT_REACH_MM in front of the goal line or beyond it, and its extension crosses the line between
    the posts."""
    for g in ("W", "E"):
        gx, gy = HW["placement_mm"][g]; half = HW["mouth_width_per_goal_mm"][g] / 2; sgn = -1 if g == "W" else 1
        if (q[0] - p[0]) * sgn <= 1e-6 or (gx - q[0]) * sgn > SHOT_REACH_MM:
            continue
        y = p[1] + (q[1] - p[1]) * ((gx - p[0]) / (q[0] - p[0]))
        if abs(y - gy) <= half + R_PUCK:
            return g
    return None


def track_v2(C):
    """Tracker 2: (1) drop candidates that do not differ from the empty rink (bgdiff < BG_MIN); (2) Viterbi as tracker 1;
    (3) drop the candidates of still low-score runs (ice marks) and run the Viterbi again, so that the real puck, if seen
    elsewhere, can take over; (4) shot completion: where the track stops, a weak candidate (score >= SHOT_MIN_SCORE) in
    the next SHOT_MAX_GAP frames that the puck reaches at SHOT_MIN_SPEED or faster (up to D_MAX per frame) on a path into
    a goal mouth is added as kind 'shot', and the search continues from it. Returns rows and a log of each step."""
    rows_in = candidates(C)
    n0 = sum(len(cs) for _, cs in rows_in)
    rows_in = [(i, [c for c in cs if c[6] is None or c[6] >= BG_MIN]) for i, cs in rows_in]
    n1 = sum(len(cs) for _, cs in rows_in)
    rows = viterbi(rows_in)
    runs = static_runs(rows)
    drop = {}
    for a, b in runs:
        for r in rows[a:b + 1]:
            drop.setdefault(r[0], []).append((r[4], r[5]))
    rows_in = [(i, [c for c in cs if not any(np.hypot(c[3] - u, c[4] - v) < STATIC_PX for u, v in drop.get(i, []))]) for i, cs in rows_in]
    rows = viterbi(rows_in)
    runs2 = static_runs(rows)   # a second pass can leave new still runs: these rows are dropped without re-tracking
    kill = {k for a, b in runs2 for k in range(a, b + 1)}
    rows = [r for k, r in enumerate(rows) if k not in kill]
    # shot completion
    by_i = dict(rows_in); have = {r[0]: r for r in rows}; added = []
    for r in (list(rows) if SHOT_COMPLETION else []):
        if r[0] + 1 in have: continue
        cur, vel, chain = r, None, []
        while True:
            best = None
            for i in range(cur[0] + 1, cur[0] + 1 + SHOT_MAX_GAP):
                if i in have: break
                for c in by_i.get(i, []):
                    if c[5] < SHOT_MIN_SCORE: continue
                    gap = i - cur[0]; st = np.array([c[0] - cur[2], c[1] - cur[3]]) / gap; d = float(np.hypot(*st))
                    if not (SHOT_MIN_SPEED / FPS <= d <= D_MAX): continue
                    g = goal_entry((cur[2], cur[3]), (c[0], c[1]))
                    if g is None: continue
                    if vel is not None:   # a later row continues the flight: same direction and a similar speed
                        cosang = float(st @ vel) / (d * float(np.hypot(*vel)))
                        if cosang < SHOT_COS or not (0.5 <= d / float(np.hypot(*vel)) <= 1.5): continue
                    if best is None or c[5] > best[1][5]: best = (i, c, st, g)
                if best: break
            if not best: break
            i, c, vel, g = best
            nr = [i, round(i / FPS, 3), round(c[0], 1), round(c[1], 1), round(c[3], 1), round(c[4], 1), "shot", round(c[5], 3)]
            have[i] = nr; chain.append(nr); cur = nr
            gx = HW["placement_mm"][g][0]
            if (c[0] - gx) * (1 if g == "E" else -1) >= 0: break   # on or past the goal line: in the goal
        if chain and SHOT_QUIET and any(k in have for k in range(chain[-1][0] + 1, chain[-1][0] + 1 + SHOT_QUIET)):
            for q in chain: del have[q[0]]          # the puck is seen again at once: no shot into the goal
            chain = []
        added += chain
    rows = sorted(have.values(), key=lambda r: r[0])
    log = {"candidates": n0, "after_bg_filter": n1, "still_runs_retracked": len(runs), "rows_in_still_runs": sum(b - a + 1 for a, b in runs),
           "still_runs_dropped_after": len(runs2), "rows_dropped_after": len(kill), "shot_rows_added": len(added)}
    return rows, log


if __name__ == "__main__":
    if "--track-only" not in A:
        import importlib.util
        spec = importlib.util.spec_from_file_location("train_puck_detector_mod", REPO / "scripts/synth/train-puck-detector.py")
        mod = importlib.util.module_from_spec(spec); sys.modules["train_puck_detector_mod"] = mod
        argv = sys.argv; sys.argv = [argv[0]]; spec.loader.exec_module(mod); sys.argv = argv
        t = time.time()
        edges = np.linspace(T0, T1, WORKERS + 1)
        with Pool(WORKERS) as p:
            R = p.map(detect, [(edges[k], edges[k + 1]) for k in range(WORKERS)])
        C = sorted({r[0]: r for part in R for r in part}.values(), key=lambda r: r[0])
        save(CANDS, C)
        print(GAME, "frames", len(C), "with a peak >= 0.5:", sum(1 for c in C if c[1] and c[1][0][2] >= 0.5), "minutes", round((time.time() - t) / 60, 1), flush=True)
    if "--detect-only" in A: sys.exit()
    C = json.loads(CANDS.read_text())
    log = None
    if TRACKER == 2:
        rows, log = track_v2(C)
    else:
        rows = track(C)
    nf = len(C)
    save(game_dir(GAME) / OUT_NAME, {
        "description": "Puck track from the synthetic puck detector (scripts/synth/track-puck.py, docs/synthetic-puck.md). One row per frame where a peak was chosen; other frames are not seen. PROPOSED.",
        "columns": ["frame", "video_t_s", "x_mm", "y_mm", "u_stab_px", "v_stab_px", "kind", "score"],
        "position_note": "x_mm, y_mm: the puck centre, from the detected top-face centre mapped through the reference camera onto the plane 12 mm above the ice (the Blender puck's top; real thickness unknown). puck-track.json maps the blob centre onto the ice plane instead, which puts it about 13 mm further +y (away from the camera). u/v_stab_px: the detected top-face centre.",
        "model": MODEL, "tracker": {"sigma_mm": SIGMA, "d_max_mm_per_frame": D_MAX, "switch_cost": SWITCH, "emission": "logit(score) clipped to [-4, 5], plus bias", "bias": BIAS,
                                     **({"version": 2, "bg_min": BG_MIN, "still_run": {"rows": STATIC_N, "px": STATIC_PX, "median_score_below": STATIC_SCORE},
                                         "shot_completion": {"on": SHOT_COMPLETION, "min_speed_mm_s": SHOT_MIN_SPEED, "reach_mm": SHOT_REACH_MM, "max_gap_frames": SHOT_MAX_GAP, "min_score": SHOT_MIN_SCORE, "continue_within_deg": 20.0, "continue_speed_ratio": [0.5, 1.5], "quiet_frames_after": SHOT_QUIET},
                                         "log": log} if TRACKER == 2 else {})},
        "frames": nf, "seen_fraction": round(len(rows) / max(nf, 1), 3),
        "rows": rows,
    })
    print(GAME, "frames", nf, "seen", len(rows), round(len(rows) / max(nf, 1), 3))
