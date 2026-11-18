"""Hypothesis xg-shot-model, step 2: stats and charts from attempts.csv. Usage: python3 scripts/hypotheses/xg_analysis.py [outdir]"""
import sys, json, csv
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from xg_common import *
OUT = __import__("pathlib").Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/project-files/hypotheses/xg-shot-model")
rng = np.random.default_rng(7)
A = list(csv.DictReader(open(OUT / "attempts.csv")))
num = lambda k: np.array([np.nan if a[k] in ("", "None") else float(a[k]) for a in A])
y = num("is_goal"); game = num("game").astype(int); N = len(A)
res = {"n_attempts": N, "n_goals": int(y.sum()), "n_goals_total": len(GOALS)}

def wilson(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))

# --- 1. detection recall ------------------------------------------------------------------------------------------
ps_hit = 0
for gid, c in GOALS.items():
    g = int(c["game"][1]); goal = "W" if c["scoring_end"] == "E" else "E"; T = c["goal_moment_s"]
    ev = json.load(open(D / f"g{g}/passes-synth-v1.json"))["events"]
    ps_hit += any(e["kind"] == "shot" and e["goal_of"] == goal and e["t_release_s"] - 0.5 <= T <= e["t_reception_s"] + 1.0 for e in ev)
res["recall"] = {"passes_synth_v1_shot_events": ps_hit, "relaxed_detector": int(y.sum()), "goals": len(GOALS),
                 "n_shot_events_in_passes_synth_v1": sum(1 for g in range(1, 8) for e in json.load(open(D / f"g{g}/passes-synth-v1.json"))["events"] if e["kind"] == "shot")}
fam_all, fam_hit = {}, {}
for a in A:
    pass
allfam = {}
for l in json.load(open(D / "goal-labels.json"))["labels"]:
    allfam[l["id"]] = l["family"]
for gid, c in GOALS.items():
    allfam.setdefault(gid, (c.get("predictions") or {}).get("vote") or "?")
matched = {a["goal_id"] for a in A if a["goal_id"]}
for gid, f in allfam.items():
    fam_all[f] = fam_all.get(f, 0) + 1
    fam_hit[f] = fam_hit.get(f, 0) + (gid in matched)
res["goals_by_family_matched_of_total"] = {f: [fam_hit[f], fam_all[f]] for f in fam_all}
res["goals_by_game_matched_of_total"] = {}
for g in range(1, 8):
    tot = sum(1 for c in GOALS.values() if c["game"] == f"g{g}"); res["goals_by_game_matched_of_total"][f"g{g}"] = [int(sum(1 for a in A if a["game"] == str(g) and a["is_goal"] == "1")), tot]

# --- 2. conversion with Wilson CIs ----------------------------------------------------------------------------------
def conv(key):
    out = {}
    for v in sorted({a[key] for a in A}):
        m = np.array([a[key] == v for a in A]); k, n = int(y[m].sum()), int(m.sum())
        lo, hi = wilson(k, n); out[v] = dict(goals=k, attempts=n, rate=round(k / n, 3), ci95=[round(lo, 3), round(hi, 3)])
    return out
res["conversion"] = {k: conv(k) for k in ("player", "role", "attacker_end", "game")}
fam_attempts = {}
for a in A:
    if a["is_goal"] == "1": fam_attempts[a["family"]] = fam_attempts.get(a["family"], 0) + 1
res["family_goals_observed"] = fam_attempts

# --- 3. univariate AUC ------------------------------------------------------------------------------------------------
def auc(x, y):
    m = ~np.isnan(x); x, y = x[m], y[m]
    if y.sum() == 0 or y.sum() == len(y): return np.nan
    r = np.argsort(np.argsort(x)) + 1.0
    # average ranks for ties
    _, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)
    cs = np.cumsum(cnt); avg = (cs - (cnt - 1) / 2.0)[inv]
    n1, n0 = y.sum(), len(y) - y.sum()
    return (avg[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
feats = ["speed_max", "speed_last", "aim_miss_mm", "angle_deg", "end_depth", "origin_depth", "goalie_gap_mm", "passes_before", "since_pass_s", "n_det"]
X = {f: num(f) for f in feats}
X["origin_abs_y"] = np.abs(num("origin_y")); feats.append("origin_abs_y")
res["univariate_auc"] = {}
for f in feats:
    x = X[f]; a0 = auc(x, y); bs = []
    for _ in range(2000):
        i = rng.integers(0, N, N)
        if y[i].sum() in (0, len(i)): continue
        bs.append(auc(x[i], y[i]))
    perm = [auc(x, rng.permutation(y)) for _ in range(2000)]
    p = float(np.mean(np.abs(np.array(perm) - 0.5) >= abs(a0 - 0.5)))
    res["univariate_auc"][f] = dict(auc=round(a0, 3), ci95=[round(float(np.nanpercentile(bs, 2.5)), 3), round(float(np.nanpercentile(bs, 97.5)), 3)], perm_p=round(p, 3),
                                    missing=int(np.isnan(x).sum()), mean_goal=round(float(np.nanmean(x[y == 1])), 1), mean_nongoal=round(float(np.nanmean(x[y == 0])), 1))

# --- 4. ridge logistic, leave-one-game-out ---------------------------------------------------------------------------
def fit(Xs, ys, lam):
    Z = np.c_[np.ones(len(Xs)), Xs]; b = np.zeros(Z.shape[1]); P = lam * np.eye(Z.shape[1]); P[0, 0] = 0
    for _ in range(50):
        p = 1 / (1 + np.exp(-Z @ b)); W = p * (1 - p) + 1e-9
        step = np.linalg.solve(Z.T @ (Z * W[:, None]) + P, Z.T @ (ys - p) - P @ b); b += step
        if np.abs(step).max() < 1e-8: break
    return b
def prob(b, Xs): return 1 / (1 + np.exp(-(np.c_[np.ones(len(Xs)), Xs] @ b)))
model_feats = ["speed_max", "aim_miss_mm", "end_depth", "goalie_gap_mm"]
M = np.c_[[X[f] for f in model_feats]].T; ok = ~np.isnan(M).any(1); M, yy, gg = M[ok], y[ok], game[ok]
mu, sd = M.mean(0), M.std(0); Zs = (M - mu) / sd
best = {}
for lam in (1.0, 5.0, 20.0):
    pred = np.zeros(len(yy))
    for g in range(1, 8):
        tr, te = gg != g, gg == g
        pred[te] = prob(fit(Zs[tr], yy[tr], lam), Zs[te])
    ll = -np.mean(yy * np.log(pred + 1e-12) + (1 - yy) * np.log(1 - pred + 1e-12))
    base = yy.mean(); lb = -np.mean(yy * np.log(base) + (1 - yy) * np.log(1 - base))
    best[lam] = dict(logo_auc=round(float(auc(pred, yy)), 3), logloss=round(float(ll), 4), logloss_base_rate=round(float(lb), 4))
res["ridge_logo"] = best
lam = 5.0; b = fit(Zs, yy, lam); bsb = []
for _ in range(500):
    i = rng.integers(0, len(yy), len(yy))
    if yy[i].sum() < 2: continue
    bsb.append(fit(Zs[i], yy[i], lam)[1:])
bsb = np.array(bsb)
res["ridge_coefficients_standardised"] = {f: dict(coef=round(float(b[k + 1]), 3), ci95=[round(float(np.percentile(bsb[:, k], 2.5)), 3), round(float(np.percentile(bsb[:, k], 97.5)), 3)]) for k, f in enumerate(model_feats)}
res["events_per_variable"] = round(float(yy.sum() / len(model_feats)), 2)
# --- 5. sample size ---------------------------------------------------------------------------------------------------
gper = y.sum() / 7
res["games_needed"] = {
    "observed_goals_per_game_now": round(float(gper), 2),
    "now_10_events_per_variable_for_4_features_games": round(40 / gper, 1),
    "now_10_epv_for_8_features_games": round(80 / gper, 1),
    "if_all_6_goals_per_game_observed_4_features": round(40 / (len(GOALS) / 7), 1),
    "if_all_6_goals_per_game_observed_8_features": round(80 / (len(GOALS) / 7), 1),
    "pass_chain_features_need_2x_more": True}
json.dump(res, open(OUT / "xg-results.json", "w"), indent=1)

# --- charts -------------------------------------------------------------------------------------------------------------
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
C0, C1, C2 = "#2a6f97", "#c8553d", "#8d99ae"
fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
lab = ["goals in\ncombo-labels", "found by\npasses-synth-v1\n'shot' events", "found by\nrelaxed\ndetector"]
v = [len(GOALS), ps_hit, int(y.sum())]
ax[0].bar(lab, v, color=[C2, C0, C0]); [ax[0].text(i, n + .5, str(n), ha="center") for i, n in enumerate(v)]; ax[0].set_title("How many of the 40 goals have a visible shot?")
gm = res["goals_by_game_matched_of_total"]; xs = np.arange(7)
ax[1].bar(xs, [gm[f"g{g}"][1] for g in range(1, 8)], color=C2, label="goals"); ax[1].bar(xs, [gm[f"g{g}"][0] for g in range(1, 8)], color=C0, label="found")
ax[1].set_xticks(xs, [f"g{g}" for g in range(1, 8)]); ax[1].legend(frameon=False); ax[1].set_title("Goals found per game")
fm = res["goals_by_family_matched_of_total"]; fs = sorted(fm, key=lambda k: -fm[k][1]); xs = np.arange(len(fs))
ax[2].bar(xs, [fm[f][1] for f in fs], color=C2); ax[2].bar(xs, [fm[f][0] for f in fs], color=C0); ax[2].set_xticks(xs, fs, rotation=30); ax[2].set_title("…and by attacking family")
plt.tight_layout(); plt.savefig(OUT / "chart-recall.png", dpi=140); plt.close()

fig, ax = plt.subplots(1, 2, figsize=(12, 4.4))
for a_, key, ttl in ((ax[0], "player", "Conversion by player"), (ax[1], "role", "Conversion by shooting figure (nearest rod at release)")):
    c = res["conversion"][key]; ks = list(c); ys_ = np.arange(len(ks))
    a_.errorbar([c[k]["rate"] for k in ks], ys_, xerr=[[c[k]["rate"] - c[k]["ci95"][0] for k in ks], [c[k]["ci95"][1] - c[k]["rate"] for k in ks]], fmt="o", color=C1, capsize=3)
    a_.set_yticks(ys_, [f"{k} ({c[k]['goals']}/{c[k]['attempts']})" for k in ks]); a_.set_xlim(0, 0.5); a_.set_title(ttl); a_.set_xlabel("goals / attempts, Wilson 95% CI")
plt.tight_layout(); plt.savefig(OUT / "chart-conversion.png", dpi=140); plt.close()

fig, ax = plt.subplots(figsize=(7.5, 4.6)); u = res["univariate_auc"]; ks = list(u); ys_ = np.arange(len(ks))
ax.errorbar([u[k]["auc"] for k in ks], ys_, xerr=[[u[k]["auc"] - u[k]["ci95"][0] for k in ks], [u[k]["ci95"][1] - u[k]["auc"] for k in ks]], fmt="o", color=C0, capsize=3)
ax.axvline(0.5, color="#888", ls="--"); ax.set_yticks(ys_, ks); ax.set_xlabel("AUC for 'goal' (0.5 = no information), bootstrap 95% CI"); ax.set_title(f"Single-feature AUC, {int(y.sum())} goals / {N} attempts")
plt.tight_layout(); plt.savefig(OUT / "chart-auc.png", dpi=140); plt.close()
print(json.dumps(res, indent=1))
