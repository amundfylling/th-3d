"""Pick the most robust archive members of a run, replay them through the unmodified engine, write stills + JSON.
python3 scripts/combo_search/finalise.py --runs x1_gamble_s0,x1_gamble_s1 --attackers W-C --opp gamble_R_to_L --tag hjerpe_like"""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combo_search import env, analyse, validate, render  # noqa: E402

R = Path("/mnt/project-files/hypotheses/rl-combo-search")
ap = argparse.ArgumentParser()
ap.add_argument("--runs", required=True); ap.add_argument("--attackers", default="W-C"); ap.add_argument("--opp", required=True)
ap.add_argument("--tag", required=True); ap.add_argument("--top", type=int, default=3); ap.add_argument("--pool", type=int, default=12)
ap.add_argument("--free-start", action="store_true")
a = ap.parse_args()
if a.free_start:
    env.USE_FIXED["on"] = False
att = a.attackers.split(",")
cands = []
for run in a.runs.split(","):
    for f in (R / "runs").glob(f"{run}.archive.npy"):
        A = np.load(f)
        cands += [(run, g) for g in A[:: max(1, len(A) // a.pool)][: a.pool]]
    b = R / "runs" / f"{run}.best.npy"
    if b.exists():
        cands.append((run + "(best)", np.load(b)))
rows = []
for run, g in cands:
    rb = analyse.robustness(g, att, a.opp)
    r = env.rollout(g, a.opp, att)
    if not analyse.ok(r):
        continue
    gl = rb["goalie_variants"]
    rows.append((rb["physics_variants_ok"] + sum(x["ok"] for x in gl), -(rb["goal_y_spread_mm"] or 99), run, g, rb))
rows.sort(key=lambda x: (x[0], x[1]), reverse=True)
out = []
for rank, (sc, sp, run, g, rb) in enumerate(rows[: a.top]):
    d = analyse.descriptor(g, att, a.opp)
    rep = validate.replay(d)
    name = f"{a.tag}_{rank}"
    np.save(R / "runs" / f"{name}.npy", g)
    t_goal = d["t_goal"]
    first = d["groups"][0]["t0"] if d["groups"] else 0.0
    times = [0.0, first + 0.05, (first + t_goal) / 2, t_goal]
    render.strip(d, times, R / "stills" / f"{name}.png", f"{name}: {analyse.classify(d, att)}")
    out.append({"name": name, "from_run": run, "class": analyse.classify(d, att), "goal_y": d["goal_y"], "goalie_y": d["goalie_y"], "t_goal": t_goal, "goal_speed": d["goal_speed"],
                "peak_fig_mm_s": d["peak_fig"], "groups": d["groups"], "robust_physics": f'{rb["physics_variants_ok"]}/{rb["physics_variants"]}',
                "goal_y_spread_mm": rb["goal_y_spread_mm"], "goalie_variants_ok": sum(x["ok"] for x in rb["goalie_variants"]), "goalie_variants": len(rb["goalie_variants"]),
                "engine_replay": rep, "rows": rb["rows"]})
    print(name, out[-1]["class"], out[-1]["robust_physics"], "spread", rb["goal_y_spread_mm"], "replay dev", rep["max_dev_mm"], "peak", d["peak_fig"])
(R / "stills").mkdir(exist_ok=True)
json.dump(out, open(R / f"final_{a.tag}.json", "w"), indent=1, default=float)
