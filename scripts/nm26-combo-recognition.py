"""Combination recognition for the NM26 goals: classify each goal's setup into the playbook's attacking families.

    python3 scripts/nm26-combo-recognition.py [--puck <name>]

One command, re-runnable on new tracks. --puck picks the puck track file in each game folder (default puck-track.json;
e.g. --puck puck-track-synth.json once a better track exists). Pure numpy; no video needed.

Inputs (all PROPOSED model output except the labels):
- data/games/nm26-semifinal/<g>/figure-tracks-smooth.json (scripts/synth/smooth-tracks.py)
- data/games/nm26-semifinal/<g>/<puck> (scripts/nm26-track.py)
- data/games/nm26-semifinal/goal-labels.json (the user's labels of 25 goals: family, combination, goal moment)
- data/games/nm26-semifinal/timeline.json (every goal's score-box time and scoring end), data/geometry.json (slots)

Steps:
1. TEAM FRAME. Every position is turned into the scoring team's frame: the left end's (W) world frame, and for the
   right end (E) the world rotated by 180 degrees (the rink is point-symmetric), so every team attacks +x and its left
   wing plays on +y. Slot depth = distance along the slot from the figure's own-goal end. Rotations stay relative to
   the team's home heading, as in the tracks.
2. GOAL MOMENT. Labelled goals: the user's 'goal is now' mark. Unlabelled goals: estimated from the puck track. A HOLD
   is a run of at least 4 disk detections (gaps of at most 3 frames, steps under 15 mm). Holds at the centre spot, on
   static false spots (a place where the game has a 1 s hold that moves less than 1.5 mm, at least twice) and in the
   FALSE_SPOT box (a candidate at the near board of the left corner, about world (-240, -178) mm, that the track holds
   in five games while the real puck is elsewhere; found by inspection) are ignored.
   - REPLAY: the broadcast shows a replay of many goals about 5 s after the goal; it is found as the delay at which the
     moving puck's detections repeat (replay_match). The goal is the end of the matched live segment plus a constant.
   - Otherwise: box time minus the median lag of the labelled goals without a replay, snapped to the end of the last
     hold in the 3 s around it, plus a constant. The three constants are fitted on the labelled goals; the error is
     reported leave-one-out.
3. FEATURES at the goal moment (team frame):
   - the SET-UP SPOT: the end of the last hold in [t - 2.0 s, t + 0.1 s] (else the mean puck position in [t - 1.5, t]);
   - the HOLDER: the scoring team's skater whose blade point (mold point (12, 33) mm, scripts/nm26-figure-analysis.py)
     is nearest the set-up spot at the hold's end (the nearest opponent is recorded too, not used);
   - the scoring team's figures 0.5 s before the goal: centre depth and facing, right wing depth and facing, left wing
     depth and facing, both defenders' depth; the centre's total turning in the last 1.5 s.
4. CLASSIFIERS, all checked leave-one-out on the 25 labelled goals (each goal predicted by a model fitted without it):
   - TREE (primary, chosen before the results): a depth-3 decision tree (Gini) on the features;
   - 1-NN: nearest labelled goal on standardised features;
   - RULES: the playbook's description of each family written as rules on the set-up spot and holder (no fitting; the
     thresholds were set from the playbook text and the rink geometry, then checked on the same 25 goals, so its score
     is not a held-out score).
   Sub-families (Spade / Edwall long shovel, short / ordinary centrifuge) by 1-NN within the family, leave-one-out.
5. OUTPUT: data/games/nm26-semifinal/combo-labels.json: every goal's moment, features, the three predictions and the
   final label (user label for the 25 reviewed goals; PROPOSED tree prediction, with the rule and 1-NN votes, for the
   others), plus the leave-one-out report (per-family accuracy, confusion matrices).
Status: PROPOSED. Thresholds assumed; see docs/nm26-combinations.md.
"""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[1]; D = REPO / "data/games/nm26-semifinal"
PUCK = sys.argv[sys.argv.index("--puck") + 1] if "--puck" in sys.argv else "puck-track.json"
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
ACC = {p: np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))] for p, P in SLOT.items()}
ROLES = ["LW", "RW", "C", "LD", "RD"]; BLADE = np.array([12.0, 33.0]); FPS = 30.0
TL = json.loads((D / "timeline.json").read_text())["games"]
LAB = {r["id"]: r for r in json.loads((D / "goal-labels.json").read_text())["labels"]}
FAMILIES = ["shovel", "centrifuge", "centre", "defence", "wing", "rebound"]

# ---------------------------------------------------------------- data access


def mirror(end, xy):
    return np.asarray(xy, float) * (-1.0 if end == "E" else 1.0)


def pivot_world(pid, u):
    P, acc = SLOT[pid], ACC[pid]; s = float(u) * acc[-1]
    return np.array([np.interp(s, acc, P[:, 0]), np.interp(s, acc, P[:, 1])])


def own_end_u(pid):
    """u at the slot end nearest the figure's own goal (team frame x smallest)."""
    a, b = mirror(pid[0], SLOT[pid][0]), mirror(pid[0], SLOT[pid][-1])
    return 0.0 if a[0] < b[0] else 1.0


class Game:
    def __init__(self, g):
        T = json.loads((D / g / "figure-tracks-smooth.json").read_text()); C = T["columns"]; ci = {c: i for i, c in enumerate(C)}
        R = np.array([[np.nan if v is None else v for v in r] for r in T["rows"]], float)
        self.t = R[:, 0] / FPS
        self.fig = {c[:-2]: (R[:, ci[c]], R[:, ci[c[:-2] + "_theta_deg"]]) for c in C if c.endswith("_u")}
        P = json.loads((D / g / PUCK).read_text()); pc = P["columns"]; k = {c: pc.index(c) for c in ("frame", "video_t_s", "x_mm", "y_mm", "kind")}
        self.puck = [(int(r[k["frame"]]), r[k["video_t_s"]], r[k["x_mm"]], r[k["y_mm"]], r[k["kind"]]) for r in P["rows"] if r[k["x_mm"]] is not None]
        self.pk = {r[0]: (r[2], r[3]) for r in self.puck}
        self.holds_all = holds_of(self.puck, -1e9, 1e9)
        st = [h for h in self.holds_all if h["dur"] >= 1.0 and h["std"] < 1.5]
        self.static = [h["raw"] for h in st if sum(np.linalg.norm(o["raw"] - h["raw"]) < 15 for o in st) >= 2]

    def pose(self, pid, t):
        """(u, theta_deg) at video time t, nearest tracked frame within 0.25 s; None if unknown."""
        u, th = self.fig[pid]; j = int(np.argmin(np.abs(self.t - t)))
        if abs(self.t[j] - t) > 0.25 or np.isnan(u[j]): return None
        return float(u[j]), float(th[j])

    def turning(self, pid, a, b):
        u, th = self.fig[pid]; m = (self.t >= a) & (self.t <= b) & ~np.isnan(th)
        if m.sum() < 3: return None
        d = (np.diff(th[m]) + 180) % 360 - 180
        return float(np.abs(d).sum()), float(d.sum())


def holds_of(puck, a, b):
    rows = [r for r in puck if a <= r[1] <= b and r[4] == "disk"]; H, cur = [], []
    for r in rows:
        if cur and r[0] - cur[-1][0] <= 3 and np.hypot(r[2] - cur[-1][2], r[3] - cur[-1][3]) < 15: cur.append(r)
        else:
            if len(cur) >= 4: H.append(cur)
            cur = [r]
    if len(cur) >= 4: H.append(cur)
    out = []
    for h in H:
        xy = np.array([[r[2], r[3]] for r in h])
        out.append({"t0": h[0][1], "t1": h[-1][1], "raw": xy[-1], "dur": h[-1][1] - h[0][1], "std": float(xy.std(0).max())})
    return out


GAMES = {}


def game(g):
    if g not in GAMES: GAMES[g] = Game(g)
    return GAMES[g]


FALSE_SPOT = ((-275.0, -205.0), (-186.0, -170.0))  # world x, y range (mm); see the docstring, step 2


def false_spot(xy):
    return FALSE_SPOT[0][0] <= xy[0] <= FALSE_SPOT[0][1] and FALSE_SPOT[1][0] <= xy[1] <= FALSE_SPOT[1][1]


def valid_holds(gm, a, b):
    return [h for h in gm.holds_all if a <= h["t1"] <= b and not (abs(h["raw"][0]) < 35 and abs(h["raw"][1]) < 35)
            and not false_spot(h["raw"]) and not any(np.linalg.norm(h["raw"] - s) < 15 for s in gm.static)]


# ---------------------------------------------------------------- goal moment


def replay_match(gl):
    """The broadcast replay: the delay (3-10 s) at which the most puck detections reappear within 8 mm (moving puck
    only: not within 3 mm of its position 1 s earlier; not at the centre spot or the false spot). Original frames lie in
    [box - 16 s, box - 6 s] and after the previous goal's box time (its restart drop). Returns (delay_s, matched
    original frames)."""
    gm = game(gl["game"]); pk = gm.pk; best = (None, [])
    f0, f1 = int(max(gl["box_s"] - 16, gl["prev_box_s"] + 0.5) * FPS), int(gl["box_s"] * FPS)
    for dfr in range(90, 300):
        m = []
        for f in range(f0, min(f1 - dfr, int((gl["box_s"] - 6) * FPS))):
            a, b = pk.get(f), pk.get(f + dfr)
            if a is None or b is None or abs(a[0]) + abs(a[1]) < 40 or false_spot(a) or np.hypot(a[0] - b[0], a[1] - b[1]) >= 8: continue
            c = pk.get(f - 30)
            if c is not None and np.hypot(a[0] - c[0], a[1] - c[1]) < 3: continue
            m.append(f)
        if len(m) > len(best[1]): best = (dfr / FPS, m)
    return best


def moment_candidates(gl):
    """Raw ingredients of the goal-moment estimate: the replay (if one is found) and the holds near the box time."""
    d, m = replay_match(gl)
    rep = d is not None and REPLAY_DELAY[0] <= d <= REPLAY_DELAY[1] and len(m) >= REPLAY_MIN
    return {"replay_delay_s": d, "replay_matches": len(m), "replay": rep, "replay_orig_end_s": (m[-1] / FPS if rep else None)}


def estimate_moment(gl, c, p):
    """p: fitted constants (replay_offset, short_lag, hold_offset). Returns (t, method)."""
    if c["replay"]: return c["replay_orig_end_s"] + p["replay_offset"], "replay"
    t0 = gl["box_s"] - p["short_lag"]; hs = valid_holds(game(gl["game"]), t0 - 2.0, t0 + 1.0)
    if hs: return hs[-1]["t1"] + p["hold_offset"], "box_lag_snapped_to_hold"
    return t0, "box_lag"


def fit_moment(goals_lab, cand):
    r = [g["label"]["goal_video_s"] - cand[g["id"]]["replay_orig_end_s"] for g in goals_lab if cand[g["id"]]["replay"]]
    s = [g["box_s"] - g["label"]["goal_video_s"] for g in goals_lab if not cand[g["id"]]["replay"]]
    p = {"replay_offset": float(np.median(r)) if r else 0.2, "short_lag": float(np.median(s)) if s else 4.0}
    h = []
    for g in goals_lab:
        if cand[g["id"]]["replay"]: continue
        t0 = g["box_s"] - p["short_lag"]; hs = valid_holds(game(g["game"]), t0 - 2.0, t0 + 1.0)
        if hs: h.append(g["label"]["goal_video_s"] - hs[-1]["t1"])
    p["hold_offset"] = float(np.median(h)) if h else 0.2
    return p


REPLAY_DELAY, REPLAY_MIN = (4.0, 6.5), 12


# ---------------------------------------------------------------- features


def features(gl, t):
    gm = game(gl["game"]); end = gl["end"]; opp = "E" if end == "W" else "W"
    f = {}
    hs = valid_holds(gm, t - 2.0, t + 0.1)
    if hs:
        h = hs[-1]; spot = mirror(end, h["raw"]); th = h["t1"]; f["spot_from"] = "hold"; f["hold_to_goal_s"] = round(t - th, 2)
    else:
        pts = [mirror(end, (r[2], r[3])) for r in gm.puck if t - 1.5 <= r[1] <= t]
        spot = np.mean(pts, 0) if pts else np.array([np.nan, np.nan]); th = t - 0.3; f["spot_from"] = "mean" if pts else "none"
    f["spot_x"], f["spot_y"] = round(float(spot[0]), 1), round(float(spot[1]), 1)
    best = {end: (None, np.inf), opp: (None, np.inf)}
    for side in (end, opp):
        for r in ROLES:
            pid = f"{side}-{r}"; p = gm.pose(pid, th)
            if p is None: continue
            bp = mirror(end, pivot_world(pid, p[0]))  # pivot in the SCORING team's frame, whatever the figure's side
            head = p[1] + (0.0 if side == end else 180.0)  # heading in the scoring team's frame
            a = np.radians(head); c, s = np.cos(a), np.sin(a)
            bp = bp + np.array([c * BLADE[0] - s * BLADE[1], s * BLADE[0] + c * BLADE[1]])
            d = float(np.linalg.norm(bp - spot)) if not np.isnan(spot[0]) else np.inf
            if d < best[side][1]: best[side] = (("own-" if side == end else "opp-") + r, d)
    f["holder"], f["holder_dist_mm"] = best[end][0], (round(best[end][1], 1) if np.isfinite(best[end][1]) else None)
    f["nearest_opponent"], f["nearest_opponent_dist_mm"] = best[opp][0], (round(best[opp][1], 1) if np.isfinite(best[opp][1]) else None)
    for r in ROLES:
        pid = f"{end}-{r}"; p = gm.pose(pid, t - 0.5)
        if p is None: f[f"{r}_depth_mm"] = f[f"{r}_theta_deg"] = None; continue
        f[f"{r}_depth_mm"] = round(abs(p[0] - own_end_u(pid)) * ACC[pid][-1], 1); f[f"{r}_theta_deg"] = round(p[1] % 360, 1)
    tr = gm.turning(f"{end}-C", t - 1.5, t)
    f["C_turn_abs_deg"], f["C_turn_net_deg"] = (round(tr[0], 1), round(tr[1], 1)) if tr else (None, None)
    return f


NUM = ["spot_x", "spot_y", "C_depth_mm", "RW_depth_mm", "LW_depth_mm", "LD_depth_mm", "RD_depth_mm", "C_turn_abs_deg"]
ANG = ["C_theta_deg", "RW_theta_deg", "LW_theta_deg"]
HOLD = ["own-LW", "own-RW", "own-C", "own-LD", "own-RD"]


def vector(f):
    v = [f[k] if f[k] is not None else np.nan for k in NUM]
    for k in ANG:
        a = f[k]; v += [np.nan, np.nan] if a is None else [np.cos(np.radians(a)), np.sin(np.radians(a))]
    h = f["holder"]; v += [np.nan] * len(HOLD) if h is None else [float(h == k) for k in HOLD]
    return np.array(v, float)


VNAMES = NUM + [f"{k[:-4]}_{t}" for k in ANG for t in ("cos", "sin")] + [f"holder={k}" for k in HOLD]

# ---------------------------------------------------------------- classifiers


def rules(f):
    """The playbook families as rules on the set-up spot and holder (docs/table-hockey-playbook.md 3.3). Version 2,
    revised after the first leave-one-out run (v1 also called a goal 'rebound' when an opponent's blade was nearest;
    near-board wings are often mislocated, so that fired on centrifuges): its score is in-sample, not held out.
    Team frame: the attacked goal line is at x ~ +250 mm, the near (right-wing) board at y ~ -230, the far (left-wing)
    board at y ~ +230; the centre slot ends about 95 mm before the goal line."""
    x, y, h = f["spot_x"], f["spot_y"], f["holder"] or ""
    if np.isnan(x): return "unknown"
    if x < -60: return "defence"                                   # set up in the own half: a defender's shot
    if y < -110: return "shovel"                                   # right-wing lane: the RW passes across
    if y > 110 or x > 300: return "centrifuge"                     # left-wing lane or behind the goal
    if y < -80 and h == "own-RW": return "shovel"                  # between lanes: the nearest figure decides
    if y > 80 and h == "own-LW": return "centrifuge"
    return "centre"                                                # in front of goal: a centre trick


def tree_fit(X, y, depth=3, min_leaf=1):
    cls = sorted(set(y)); y = np.asarray(y)

    def gini(m):
        if m.sum() == 0: return 0.0
        p = np.array([(y[m] == c).mean() for c in cls]); return 1 - (p ** 2).sum()

    def build(m, d):
        maj = Counter(y[m]).most_common(1)[0][0]
        if d == 0 or len(set(y[m])) == 1: return maj
        best = None; g0 = gini(m) * m.sum()
        for j in range(X.shape[1]):
            xs = X[m, j]; ok = ~np.isnan(xs); vals = np.unique(xs[ok])
            for a, b in zip(vals[:-1], vals[1:]):
                thr = (a + b) / 2; L = m & (np.nan_to_num(X[:, j], nan=-1e9) <= thr); R = m & ~L
                if L.sum() < min_leaf or R.sum() < min_leaf: continue
                gain = g0 - gini(L) * L.sum() - gini(R) * R.sum()
                if best is None or gain > best[0] + 1e-12: best = (gain, j, thr, L, R)
        if best is None or best[0] <= 1e-9: return maj
        return (best[1], best[2], build(best[3], d - 1), build(best[4], d - 1))
    return build(np.ones(len(y), bool), depth)


def tree_pred(node, x):
    """None when the goal lacks a feature the tree asks for (e.g. no puck seen)."""
    while isinstance(node, tuple):
        j, thr, L, R = node
        if np.isnan(x[j]): return None
        node = L if x[j] <= thr else R
    return node


def tree_text(node, ind=""):
    if not isinstance(node, tuple): return [f"{ind}-> {node}"]
    j, thr, L, R = node
    return [f"{ind}{VNAMES[j]} <= {thr:.2f}"] + tree_text(L, ind + "  ") + [f"{ind}{VNAMES[j]} > {thr:.2f}"] + tree_text(R, ind + "  ")


def nn_pred(X, y, x):
    mu, sd = np.nanmean(X, 0), np.nanstd(X, 0); sd[sd == 0] = 1
    Z = (X - mu) / sd; z = (x - mu) / sd
    d = np.nanmean((Z - z) ** 2, 1)  # mean over the features both goals have
    return y[int(np.nanargmin(d))]


# ---------------------------------------------------------------- run

goals = []
for g, v in TL.items():
    prev = v["start_signal_s"]
    for k, x in enumerate(v["goals"]):
        if x.get("overlay_change_s") is None: continue
        gid = f"{g}-goal{k + 1}"; end = "W" if x["scorer"] == v["left_end_player"] else "E"
        goals.append({"id": gid, "game": g, "end": end, "scoring_player": x["scorer"], "box_s": x["overlay_change_s"], "prev_box_s": prev, "label": LAB.get(gid)})
        prev = x["overlay_change_s"]

# goal moment: fit the constants on the labelled goals; leave-one-out error
cand = {gl["id"]: moment_candidates(gl) for gl in goals}
lab = [gl for gl in goals if gl["label"] and gl["label"].get("goal_video_s") is not None]
PM = fit_moment(lab, cand)
loo_err, methods = [], []
for i, gl in enumerate(lab):
    t, meth = estimate_moment(gl, cand[gl["id"]], fit_moment(lab[:i] + lab[i + 1:], cand))
    loo_err.append(t - gl["label"]["goal_video_s"]); methods.append(meth)
loo_err = np.abs(np.array(loo_err))
moment_report = {"constants": {k: round(v, 2) for k, v in PM.items()}, "replay_rule": {"delay_s": REPLAY_DELAY, "min_matched_frames": REPLAY_MIN},
                 "labelled_goals": len(lab), "loo_abs_error_s": {"median": round(float(np.median(loo_err)), 2), "p90": round(float(np.percentile(loo_err, 90)), 2),
                 "within_0.5s": int((loo_err <= 0.5).sum()), "within_1s": int((loo_err <= 1.0).sum()), "max": round(float(loo_err.max()), 2)},
                 "by_method": {m: {"n": methods.count(m), "median_abs_error_s": round(float(np.median([e for e, mm in zip(loo_err, methods) if mm == m])), 2)} for m in sorted(set(methods))},
                 "per_goal_abs_error_s": {gl["id"]: round(float(e), 2) for gl, e in zip(lab, loo_err)}}

for gl in goals:
    t_est, meth = estimate_moment(gl, cand[gl["id"]], PM)
    gl["moment_est_s"] = round(t_est, 2); gl["moment_method"] = meth; gl["replay"] = cand[gl["id"]]
    gl["moment_s"] = gl["label"]["goal_video_s"] if gl["label"] and gl["label"].get("goal_video_s") is not None else gl["moment_est_s"]
    gl["moment_source"] = "user" if gl["label"] else "estimated"
    gl["features"] = features(gl, gl["moment_s"])
    gl["features_at_estimate"] = features(gl, gl["moment_est_s"]) if gl["label"] else gl["features"]

L = [gl for gl in goals if gl["label"]]; U = [gl for gl in goals if not gl["label"]]
y = np.array([gl["label"]["family"] for gl in L]); X = np.array([vector(gl["features"]) for gl in L])
Xe = np.array([vector(gl["features_at_estimate"]) for gl in L])


def loo(Xa):
    out = {"tree": [], "1nn": [], "rules": []}
    for i in range(len(L)):
        m = np.arange(len(L)) != i
        t_ = tree_pred(tree_fit(X[m], y[m]), Xa[i]); out["tree"].append(t_ if t_ is not None else nn_pred(X[m], y[m], Xa[i]))
        out["1nn"].append(nn_pred(X[m], y[m], Xa[i]))
    out["rules"] = [rules(gl["features"] if Xa is X else gl["features_at_estimate"]) for gl in L]
    return out


def report(pred):
    pred = np.array(pred); fams = [c for c in FAMILIES if c in set(y) | set(pred)] + sorted(set(pred) - set(FAMILIES))
    conf = {a: {b: int(((y == a) & (pred == b)).sum()) for b in fams} for a in fams if (y == a).any()}
    per = {a: {"n": int((y == a).sum()), "correct": int(((y == a) & (pred == a)).sum()), "recall": round(float((pred[y == a] == a).mean()), 2),
               "precision": (round(float((y[pred == a] == a).mean()), 2) if (pred == a).any() else None)} for a in fams if (y == a).any()}
    return {"accuracy": round(float((pred == y).mean()), 3), "correct": int((pred == y).sum()), "n": len(y), "per_family": per, "confusion_true_by_pred": conf}


res_user = loo(X); res_est = loo(Xe)
lo = {"at_user_moment": {k: report(v) for k, v in res_user.items()}, "at_estimated_moment": {k: report(v) for k, v in res_est.items()},
      "majority_baseline": round(float(Counter(y).most_common(1)[0][1] / len(y)), 3)}
# sub-families (user combination names) by 1-NN within the true family, leave-one-out
sub = {}
for fam, names in (("shovel", ("Spade", "Edwallskyffel lang")), ("centrifuge", ("Short centrifuge", None))):
    idx = [i for i, gl in enumerate(L) if gl["label"]["family"] == fam and (gl["label"]["combination"] in names or None in names)]
    ys = np.array([L[i]["label"]["combination"] or "ordinary" for i in idx]); Xs = X[idx]
    if len(set(ys)) < 2: continue
    pr = [nn_pred(np.delete(Xs, k, 0), np.delete(ys, k), Xs[k]) for k in range(len(idx))]
    sub[fam] = {"goals": [L[i]["id"] for i in idx], "true": ys.tolist(), "pred": [str(p) for p in pr], "correct": int((np.array(pr) == ys).sum()), "n": len(idx)}
lo["subfamily_1nn"] = sub

full_tree = tree_fit(X, y)
labels_out = []
for gl in goals:
    x = vector(gl["features"]); fam_names = {}
    p = {"tree": tree_pred(full_tree, x), "1nn": str(nn_pred(X, y, x)), "rules": rules(gl["features"])}
    r = {"id": gl["id"], "game": gl["game"], "scoring_end": gl["end"], "scoring_player": gl["scoring_player"], "box_s": gl["box_s"],
         "goal_moment_s": round(gl["moment_s"], 2), "goal_moment_source": gl["moment_source"], "goal_moment_estimate_s": gl["moment_est_s"],
         "goal_moment_method": gl["moment_method"], "replay": gl["replay"], "features": gl["features"], "predictions": p}
    if gl["label"]:
        r.update({"status": "user_label", "family": gl["label"]["family"], "combination": gl["label"]["combination"],
                  "loo": {k: str(res_user[k][L.index(gl)]) for k in res_user}})
    else:
        fam = p["tree"] if p["tree"] is not None else p["1nn"]; comb = None
        if p["tree"] is None: fam_names["note"] = "no set-up spot (puck not seen): 1-NN on the figure features only"
        if fam in ("shovel", "centrifuge"):
            idx = [i for i, g2 in enumerate(L) if g2["label"]["family"] == fam]
            nb = L[idx[int(np.nanargmin([np.nanmean(((X[i] - x) / (np.nanstd(X, 0) + 1e-9)) ** 2) for i in idx]))]]
            comb = nb["label"]["combination"]; fam_names = {"nearest_labelled_goal": nb["id"]}
        r.update({"status": "PROPOSED", "family": fam, "combination": comb, "agreement": f"{sum(v == fam for v in p.values())}/3", **fam_names})
    labels_out.append(r)

out = {"description": "Combination recognition for the NM26 goals (scripts/nm26-combo-recognition.py): every goal's moment, set-up "
       "features in the scoring team's frame, and its attacking family. status user_label = the user's review; PROPOSED = the "
       "decision tree's prediction (rules and 1-NN votes alongside). See docs/nm26-combinations.md.",
       "puck_track": PUCK, "status": "PROPOSED", "goal_moment": moment_report, "leave_one_out": lo,
       "tree_all_labels": tree_text(full_tree), "feature_names": VNAMES, "goals": labels_out}
(D / "combo-labels.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")

print("goal moment:", json.dumps(moment_report["loo_abs_error_s"]), moment_report["constants"], moment_report["by_method"])
for k in ("tree", "1nn", "rules"):
    a, b = lo["at_user_moment"][k], lo["at_estimated_moment"][k]
    print(f"{k:6s} LOO user moment {a['correct']}/{a['n']}  estimated moment {b['correct']}/{b['n']}")
print("majority baseline", lo["majority_baseline"]); print("subfamilies", {k: f"{v['correct']}/{v['n']}" for k, v in sub.items()})
print("\n".join(out["tree_all_labels"]))
for r in labels_out:
    print(r["id"], r["status"], r["family"], r["combination"], r["predictions"], r.get("loo"), {k: r["features"][k] for k in ("spot_x", "spot_y", "holder", "C_depth_mm")})
