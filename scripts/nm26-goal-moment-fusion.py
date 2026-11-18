#!/usr/bin/env python3
"""NM26: estimate every goal's moment by fusing puck-track, replay and broadcast-audio evidence (experiment, PROPOSED).

Why: combination recognition is 23/25 with the user's "goal is now" mark but 20/25 with the estimated moment
(docs/nm26-combinations.md), so the moment estimate is the weak link for the 15 unreviewed goals.

Method (docs/nm26-goal-moment-fusion.md):
 1. Candidates: every last puck detection before a gap of >= 0.8 s with no detection (the puck went into the goal, or
    play stopped), in [box - 16 s, box - 1 s]. Ice-mark false spots and static spots are dropped first, so they do not
    break the gap (box = the score overlay's change time, timeline.json; it lags the goal by 3-13 s).
 2. Features per candidate: log gap, team-frame x and x-velocity of the last 0.4 s, replay evidence (the puck path of
    the last 1.2 s reappears 3.3-7.2 s later = this is the original; or it appeared 3.3-7.2 s earlier = this is the
    replay copy), lag to the box, and the crowd/commentary rise in the broadcast audio (mean 100 ms RMS in
    [t+0.3, t+1.5] over [t-1.5, t], log).
 3. A ridge logistic regression picks the candidate; the estimate is the candidate time plus the median offset of the
    training goals. Leave-one-out over the 25 user-labelled goals.

Run:  python3 scripts/nm26-goal-moment-fusion.py            (needs out/dl/nm26.webm: npm run ... fetch, ~660 MB; the audio
      envelope is cached in out/nm26-audio-env.npy)
Writes validation/nm26-goal-moments-fused.json ({"moments": {goal id: seconds}, "loo": ...}) which
`scripts/nm26-combo-recognition.py --moments <file>` can read.
"""
import json, subprocess, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[1]; D = REPO / "data/games/nm26-semifinal"
sys.path.insert(0, str(REPO / "scripts"))
import nm26_tracks  # noqa: E402

FPS = 30.0
VIDEO = REPO / "out/dl/nm26.webm"; ENV_CACHE = REPO / "out/nm26-audio-env.npy"; OUT = REPO / "validation/nm26-goal-moments-fused.json"
# world mm ((x lo, x hi), (y lo, y hi)), as in nm26-combo-recognition.py. NM26_WIDE_MASK=1 (sensitivity run only) uses x -275..-186,
# y -205..-170, the box the first prototype used by mistake.
FALSE_SPOT = ((-275.0, -186.0), (-205.0, -170.0)) if __import__("os").environ.get("NM26_WIDE_MASK") == "1" else ((-275.0, -205.0), (-186.0, -170.0))
MIN_GAP = 0.8; HIT = 0.3
FEATURES = ["loggap", "x", "vx", "rep_f", "rep_b", "lag_ok", "lag", "rise"]
TL = json.loads((D / "timeline.json").read_text())["games"]
LAB = {r["id"]: r for r in json.loads((D / "goal-labels.json").read_text())["labels"]}


def audio_env():
    """100 ms RMS envelope of the broadcast audio (mono, 16 kHz); cached."""
    if ENV_CACHE.exists(): return np.load(ENV_CACHE)
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VIDEO), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True)
    x = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768; h = 1600; m = len(x) // h
    env = np.sqrt((x[:m * h].reshape(m, h) ** 2).mean(1)); ENV_CACHE.parent.mkdir(exist_ok=True); np.save(ENV_CACHE, env); return env


ENV = audio_env()


def env(a, b): return ENV[max(0, int(a * 10)):max(1, int(b * 10))]


def goal_list():
    out = []
    for g, v in TL.items():
        prev = v["start_signal_s"]
        for k, x in enumerate(v["goals"]):
            if x.get("overlay_change_s") is None: continue
            gid = f"{g}-goal{k + 1}"; L = LAB.get(gid)
            out.append(dict(id=gid, game=g, end="W" if x["scorer"] == v["left_end_player"] else "E", B=x["overlay_change_s"], P=prev,
                            G=(L["goal_video_s"] if L and L.get("goal_video_s") is not None else None)))
            prev = x["overlay_change_s"]
    return out


def is_false(w): return FALSE_SPOT[0][0] <= w[0] <= FALSE_SPOT[0][1] and FALSE_SPOT[1][0] <= w[1] <= FALSE_SPOT[1][1]


def static_spots(R):
    runs, i, n = [], 0, len(R)
    while i < n:
        j = i
        while j + 1 < n and R[j + 1, 0] - R[j, 0] < 0.2 and np.hypot(*(R[j + 1, 1:3] - R[i, 1:3])) < 1.5: j += 1
        if R[j, 0] - R[i, 0] >= 1.0: runs.append(R[i:j + 1, 1:3].mean(0))
        i = j + 1
    return [r for r in runs if sum(np.hypot(*(r - o)) < 15 for o in runs) >= 2]


GAMES = {}


def game(g):
    """Cleaned puck rows (t, x, y) and a dense per-frame array for replay matching."""
    if g not in GAMES:
        P = json.loads((D / g / nm26_tracks.PUCK_TRACK).read_text()); c = P["columns"]
        R = np.array([[r[c.index("video_t_s")], r[c.index("x_mm")], r[c.index("y_mm")]] for r in P["rows"] if r[c.index("x_mm")] is not None], float)
        st = static_spots(R)
        R = R[[not is_false(r[1:3]) and not any(np.hypot(*(r[1:3] - s)) < 15 for s in st) for r in R]]
        dense = np.full((int(R[-1, 0] * FPS) + 400, 2), np.nan); dense[np.round(R[:, 0] * FPS).astype(int)] = R[:, 1:3]
        GAMES[g] = (R, dense)
    return GAMES[g]


def replay_score(dense, ti, sign):
    """Matched frames (of the 37 in [ti - 1.2 s, ti]) whose position (within 8 mm) reappears sign * 100..214 frames later."""
    f0 = int((ti - 1.2) * FPS); a = dense[f0:f0 + 37]; best = 0
    for d in (range(100, 215) if sign > 0 else range(-214, -99)):
        if f0 + d < 0: continue
        b = dense[f0 + d:f0 + d + 37]
        if len(b) < 37: continue
        best = max(best, int((np.hypot(*(a - b).T) < 8).sum()))
    return best


def candidates(g, lo, hi):
    """Last detection before a >= 0.8 s gap, with last detection time in [lo, hi]."""
    R, dense = game(g["game"]); t = R[:, 0]; sg = 1 if g["end"] == "W" else -1; out = []
    for i in range(len(t)):
        if not lo <= t[i] <= hi: continue
        nxt = t[i + 1] if i + 1 < len(t) else 1e9
        if nxt - t[i] < MIN_GAP: continue
        j = np.where((t >= t[i] - 0.4) & (t <= t[i]))[0]
        vx = sg * (R[j[-1], 1] - R[j[0], 1]) / (t[j[-1]] - t[j[0]]) if len(j) >= 2 else 0.0
        ti = t[i]
        out.append(dict(t=float(ti), gap=float(nxt - ti), x=float(sg * R[i, 1]), y=float(sg * R[i, 2]), vx=float(vx),
                        rep_f=replay_score(dense, ti, +1), rep_b=replay_score(dense, ti, -1),
                        rise=float(np.log(env(ti + 0.3, ti + 1.5).mean() / (env(ti - 1.5, ti).mean() + 1e-6)))))
    return out


def fv(c, B=None, names=None):
    lag = (B - c["t"]) if B is not None else 0.0
    f = {"loggap": np.log(c["gap"]), "rep_f": float(c["rep_f"] >= 10), "rep_b": float(c["rep_b"] >= 10), "x": c["x"] / 300, "vx": np.clip(c["vx"], -3000, 3000) / 3000,
         "lag_ok": float(2.5 <= lag <= 13.5), "lag": min(lag, 14) / 14, "rise": c["rise"]}
    return np.array([f[k] for k in (names or FEATURES)])


def fit(X, y, l2=1.0):
    X = np.c_[np.ones(len(X)), X]; w = np.zeros(X.shape[1])
    for _ in range(400):
        p = 1 / (1 + np.exp(-X @ w)); gr = X.T @ (p - y) + l2 * np.r_[0, w[1:]]
        w -= np.linalg.solve((X.T * (p * (1 - p))) @ X + l2 * np.eye(len(w)) + 1e-6 * np.eye(len(w)), gr)
    return w


def train(goals, C, names=None):
    X, y, off = [], [], []
    for h in goals:
        for c in C[h["id"]]:
            pos = abs(c["t"] - h["G"]) <= HIT; X.append(fv(c, h["B"], names)); y.append(float(pos))
            if pos: off.append(h["G"] - c["t"])
    return fit(np.array(X), np.array(y)), float(np.median(off))


def pick(w, off, g, cs, names=None):
    s = [np.r_[1, fv(c, g["B"], names)] @ w for c in cs]; k = int(np.argmax(s)); return cs[k]["t"] + off, float(1 / (1 + np.exp(-s[k])))


def false_positives(goals, C):
    """Unconditional goal detector (no box time, so no lag features) over every game window; counts detections that are not a
    known goal. Positives: candidates within 0.3 s of the user's mark. Scores of positives are leave-one-goal-out."""
    names = ["loggap", "x", "vx", "rep_f", "rep_b", "rise"]; lab = [g for g in goals if g["G"] is not None]
    wins = {}
    for g, v in TL.items():
        ends = [x["overlay_change_s"] for x in v["goals"] if x.get("overlay_change_s") is not None]
        wins[g] = (v["start_signal_s"] + 3.5, max(v["start_signal_s"] + 300, max(ends, default=0) + 1))
    allc = {g: candidates({"game": g, "end": "W"}, *wins[g]) for g in TL}  # team frame fixed below per candidate
    # the team frame depends on the scoring end: score both ends' frames, keep the better one per candidate
    allc2 = {g: {e: candidates({"game": g, "end": e}, *wins[g]) for e in "WE"} for g in TL}
    known = {g["id"]: (g["G"] if g["G"] is not None else MOMS.get(g["id"])) for g in goals}
    def is_near_goal(g, t, pre=0.4, post=0.4): return any(abs(t - known[i["id"]]) <= (pre if True else 0) for i in goals if i["game"] == g and known[i["id"]] is not None)
    def is_copy(g, t): return any(3.3 <= t - known[i["id"]] <= 7.5 for i in goals if i["game"] == g and known[i["id"]] is not None)
    # train positives from goal windows only, negatives from the goal windows too (all candidates not at the goal)
    Xp, yp = [], []
    for h in lab:
        for c in C[h["id"]]: Xp.append(fv(c, None, names)); yp.append(float(abs(c["t"] - h["G"]) <= HIT))
    res = {}
    out = {}
    for e_mode in ("both",):
        pass
    # leave-one-goal-out positive scores
    pos = []
    for h in lab:
        X = [fv(c, None, names) for g2 in lab if g2["id"] != h["id"] for c in C[g2["id"]]]; y = [float(abs(c["t"] - g2["G"]) <= HIT) for g2 in lab if g2["id"] != h["id"] for c in C[g2["id"]]]
        w = fit(np.array(X), np.array(y)); ok = [np.r_[1, fv(c, None, names)] @ w for c in C[h["id"]] if abs(c["t"] - h["G"]) <= HIT]
        if ok: pos.append(max(ok))
    w = fit(np.array(Xp), np.array(yp))
    thr = float(np.percentile(pos, 10)) if pos else 0.0  # 90% of labelled goals' true candidates pass
    mins = {g: (wins[g][1] - wins[g][0]) / 60 for g in TL}; fp_rows = []
    for g in TL:
        # candidates in both team frames, a candidate is a detection when either frame scores above the threshold
        ts = {}
        for e in "WE":
            for c in allc2[g][e]:
                sc = float(np.r_[1, fv(c, None, names)] @ w); ts[round(c["t"], 3)] = max(ts.get(round(c["t"], 3), -9), sc)
        for t, sc in ts.items():
            if sc >= thr: fp_rows.append((g, t, sc))
    tp = sum(any(abs(t - known[i["id"]]) <= 0.5 for g2, t, _ in fp_rows if g2 == i["game"]) for i in goals if known[i["id"]] is not None)
    fps = [(g, t, sc) for g, t, sc in fp_rows if not is_near_goal(g, t, 0.5)]
    fps_nocopy = [(g, t, sc) for g, t, sc in fps if not is_copy(g, t)]
    minutes = sum(mins.values())
    return {"features": names, "threshold_logit": round(thr, 2), "game_minutes": round(minutes, 1), "known_goals": sum(v is not None for v in known.values()),
            "goals_detected_within_0.5s": tp, "detections_total": len(fp_rows), "false_positives": len(fps),
            "false_positives_excluding_replay_copies": len(fps_nocopy), "false_positives_per_minute": round(len(fps) / minutes, 2),
            "per_game_false_positives": {g: sum(1 for x in fps if x[0] == g) for g in TL}}


MOMS = {}


def main():
    goals = goal_list(); C = {g["id"]: candidates(g, max(g["B"] - 16, 0), g["B"] - 1.0) for g in goals}
    lab = [g for g in goals if g["G"] is not None and C[g["id"]]]
    loo, rows = {}, {}
    for g in lab:
        w, off = train([h for h in lab if h["id"] != g["id"]], C); t, p = pick(w, off, g, C[g["id"]]); loo[g["id"]] = t; rows[g["id"]] = round(p, 2)
    err = np.array([abs(loo[g["id"]] - g["G"]) if g["id"] in loo else 99.0 for g in goals if g["G"] is not None])
    w, off = train(lab, C)
    moments = {g["id"]: (round(loo[g["id"]], 2) if g["id"] in loo else None) if g["G"] is not None else (round(pick(w, off, g, C[g["id"]])[0], 2) if C[g["id"]] else None) for g in goals}
    res = {"description": "Goal moments from the fusion estimator (scripts/nm26-goal-moment-fusion.py). Labelled goals: leave-one-out estimate; others: fitted on all 25. PROPOSED.",
           "features": FEATURES, "moments": moments,
           "loo": {"n": int(len(err)), "within_0.2s": int((err <= 0.2).sum()), "within_0.3s": int((err <= 0.3).sum()), "within_0.5s": int((err <= 0.5).sum()),
                   "within_1s": int((err <= 1).sum()), "median_abs_s": round(float(np.median(err)), 3),
                   "misses": {g["id"]: (round(loo[g["id"]] - g["G"], 2) if g["id"] in loo else "no candidate") for g in goals if g["G"] is not None and (g["id"] not in loo or abs(loo[g["id"]] - g["G"]) > 0.2)},
                   "oracle_candidate_within_0.3s": int(sum(any(abs(c["t"] + off - g["G"]) <= 0.3 for c in C[g["id"]]) for g in goals if g["G"] is not None))},
           "weights_all_25": dict(zip(["bias"] + FEATURES, [round(float(v), 2) for v in w])), "offset_s": round(off, 3)}
    MOMS.update({k: v for k, v in moments.items() if v is not None})
    if "--false-positives" in sys.argv: res["false_positives"] = false_positives(goals, C); print(json.dumps(res["false_positives"], indent=1))
    if "--no-write" not in sys.argv: OUT.write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res["loo"], indent=1))


if __name__ == "__main__": main()
