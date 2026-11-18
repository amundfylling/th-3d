"""CMA-ES over keyframe genomes.

  python3 scripts/combo_search/search.py --name e1 --attackers W-C --opps gamble_R_to_L --gens 60 --seed 0
  --robust   every opponent is also run with perturbed physics (ice +-25 %, puck start +0.2 mm, footprints +-2 %): the
             objective is the mean score, so a knife-edge goal is worth less than a goal that survives the perturbations
  --x0 f.npy start from a genome with a small sigma (refinement)
Every genome whose scenarios all score as goals within the slide rules is appended to <name>.archive.npy.
"""
import argparse, json, sys, time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import cma

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combo_search import env  # noqa: E402

OUT = Path("/mnt/project-files/hypotheses/rl-combo-search/runs")
PERTURB5 = [{}, {"ice_scale": 1.25}, {"ice_scale": 0.75}, {"puck_dx": [0.2, 0.0]}, {"footprint": {"scale": 1.02}}]
_A = {}


def _init(att, opps, robust):
    _A.update(att=att, scen=[(o, pt) for o in opps for pt in (PERTURB5 if robust else [{}])])


def good(r):
    return r["goal"] == "E" and r["peak_fig"] <= env.LIMITS["figure_impact_mm_s"] and r["peak_wall"] <= env.LIMITS["wall_impact_mm_s"] and r["min_group_n"] >= env.MIN_PUSH_TOUCHES


def evaluate(g):
    sc, ok = [], []
    for o, pt in _A["scen"]:
        r = env.rollout(g, o, _A["att"], perturb=pt)
        sc.append(env.score(r)); ok.append(good(r))
    return float(np.mean(sc)), float(np.mean(ok)), ok[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--attackers", default="W-C")
    ap.add_argument("--opps", default="track_med")
    ap.add_argument("--gens", type=int, default=60)
    ap.add_argument("--pop", type=int, default=40)
    ap.add_argument("--sigma", type=float, default=0.4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--x0", default=None)
    ap.add_argument("--robust", action="store_true")
    ap.add_argument("--free-start", action="store_true")
    a = ap.parse_args()
    if a.free_start:
        env.USE_FIXED["on"] = False
    att = a.attackers.split(","); opps = a.opps.split(",")
    n = env.n_params(att)
    rng = np.random.default_rng(a.seed)
    x0 = np.load(a.x0) if a.x0 else rng.uniform(-0.5, 0.5, n)
    es = cma.CMAEvolutionStrategy(x0, a.sigma, {"bounds": [-1, 1], "popsize": a.pop, "seed": a.seed + 1, "verbose": -9})
    OUT.mkdir(parents=True, exist_ok=True)
    log, best, archive = [], (-1e9, None, None), []
    t0 = time.time(); n_eval = 0
    nsc = len(opps) * (len(PERTURB5) if a.robust else 1)
    with Pool(a.procs, initializer=_init, initargs=(att, opps, a.robust)) as pool:
        for gen in range(a.gens):
            X = es.ask()
            R = pool.map(evaluate, X)
            n_eval += len(X) * nsc
            es.tell(X, [-r[0] for r in R])
            i = int(np.argmax([r[0] for r in R]))
            if R[i][0] > best[0]:
                best = (R[i][0], X[i].copy(), R[i][1])
            for x, r in zip(X, R):
                if r[1] >= 0.999 and len(archive) < 400:
                    archive.append(np.array(x))
            log.append({"gen": gen, "best": R[i][0], "mean": float(np.mean([r[0] for r in R])), "n_all_goal": int(sum(r[1] >= 0.999 for r in R)), "sigma": float(es.sigma), "t": time.time() - t0})
            if gen % 5 == 0 or gen == a.gens - 1:
                print(f"{a.name} gen {gen} best {R[i][0]:.3f} mean {log[-1]['mean']:.3f} all-goal {log[-1]['n_all_goal']}/{len(X)} sigma {es.sigma:.3f} cum best {best[0]:.3f} {time.time()-t0:.0f}s", flush=True)
            if es.sigma < 1e-3:
                break
    np.save(OUT / f"{a.name}.best.npy", best[1])
    if archive:
        np.save(OUT / f"{a.name}.archive.npy", np.array(archive))
    json.dump({"args": vars(a), "best_score": best[0], "best_goal_fraction": best[2], "archive": len(archive), "log": log, "evals": n_eval, "seconds": time.time() - t0},
              open(OUT / f"{a.name}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
