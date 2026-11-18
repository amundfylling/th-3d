"""Black-box auto-tuning of a move's free parameters for robustness (CMA-ES), instead of hand tuning.

    python3 scripts/autotune-move.py <move-id> --params moves/<id>/autotune/params.json [--detune name=value ...]
        [--budget 300] [--target 10] [--seed 1] [--method cma|random] [--out out/autotune/<id>.json]

The objective is the move's own robustness check (scripts/shotlib/robustness.py: the 11 standard variants plus the
move's robustness-variants.json), evaluated in a process pool, one objective evaluation = one run of every variant.
Cost per variant: 0 when the outcome (goal + contact sequence) and the slide limits hold, plus a small smoothness term
(peak figure and wall impacts relative to the slide limits: gentler contacts are preferred); 1 + partial penalties
when it fails (wrong goal, wrong sequence, slide limits exceeded), so the search sees a gradient between "miss" and "near miss".
Total = sum over variants. Nothing in moves/ is changed: the result is a list of `--set` overrides
(`python3 scripts/build-move.py <id> --set k=v ... --robustness --scratch` re-checks it with the canonical code path).

params file: {"params": [{"name", "paths": [dotted move.json paths set to the value], "lo", "hi"}],
              "derived": [{"path", "expr"}]}   expr is evaluated with the parameter names (e.g. "t0 + dur").
The value of a parameter in the move file (its first path) is the nominal start; --detune name=value overrides it.
"""
import argparse, json, sys, time, math
import multiprocessing as mp
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shotlib import build, robustness as R  # noqa: E402


def get(spec, path):
    node = spec
    for p in path.split("."):
        node = node[int(p)] if isinstance(node, list) else node[p]
    return node


def apply(spec, P, vals):
    spec = json.loads(json.dumps(spec))
    env = dict(vals)
    for prm in P["params"]:
        for path in prm["paths"]:
            R._set(spec, path, float(vals[prm["name"]]))
    for d in P.get("derived", []):
        R._set(spec, d["path"], float(eval(d["expr"], {"__builtins__": {}}, env)))
    return spec


def variant_cost(r, rule, expect=None):
    pf, pw = r["peak_figure_impact_mm_s"], r["peak_wall_impact_mm_s"]
    if pf is None:
        return 2.0
    soft = 0.1 * 0.5 * (pf / rule["figure_impact_max_mm_s"] + pw / rule["wall_impact_max_mm_s"])
    if r["outcome_ok"] and r["slide_ok"]:
        return min(soft, 0.2)
    c = 1.0
    c += 0.5 * (0 if r["goal"] is not None else 1)
    c += 0.25 * (0 if r["sequence_as_expected"] else 1)
    if expect:  # progress along the expected contact chain: how many leading contacts happened in order
        k = 0
        for a_, b_ in zip(r.get("sequence", []), expect):
            if a_ != b_: break
            k += 1
        c += 1.0 * (1 - k / len(expect))
    c += 0.25 * min(1.0, max(0.0, pf / rule["figure_impact_max_mm_s"] - 1) + max(0.0, pw / rule["wall_impact_max_mm_s"] - 1))
    return c


class Objective:
    def __init__(self, move, P, variants, pool, base, rule, target):
        self.move, self.P, self.variants, self.pool, self.base, self.rule = move, P, variants, pool, base, rule
        self.names = [p["name"] for p in P["params"]]
        self.lo = np.array([p["lo"] for p in P["params"]], float)
        self.hi = np.array([p["hi"] for p in P["params"]], float)
        self.n = 0
        self.log = []
        self.best = None
        self.t0 = time.time()
        self.target = target
        self.expect = base.get("expect", {}).get("contact_sequence")

    def vals(self, u):
        x = self.lo + np.clip(u, 0, 1) * (self.hi - self.lo)
        return dict(zip(self.names, map(float, x)))

    def __call__(self, u):
        v = self.vals(u)
        spec = apply(self.base, self.P, v)
        try:
            rows = self.pool.map(R._run, [(spec, var) for var in self.variants])
        except Exception as e:  # a parameter set that cannot be built at all
            rows = [{"variant": var["id"], "goal": None, "sequence_as_expected": False, "peak_figure_impact_mm_s": None,
                     "peak_wall_impact_mm_s": None, "slide_ok": False, "outcome_ok": False} for var in self.variants]
        cost = sum(variant_cost(r, self.rule, self.expect) for r in rows)
        npass = sum(1 for r in rows if r["outcome_ok"] and r["slide_ok"])
        self.n += 1
        self.log.append({"n": self.n, "t": round(time.time() - self.t0, 1), "cost": round(cost, 3), "passed": npass})
        if self.best is None or (npass, -cost) > (self.best["passed"], -self.best["cost"]):
            self.best = {"n": self.n, "cost": cost, "passed": npass, "vals": v,
                         "failed": [r["variant"] for r in rows if not (r["outcome_ok"] and r["slide_ok"])]}
            print(f'[{self.n:4d} {time.time()-self.t0:6.0f}s] {npass}/{len(rows)} cost {cost:.3f}', flush=True)
        return cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("move")
    ap.add_argument("--params", required=True)
    ap.add_argument("--detune", nargs="*", default=[])
    ap.add_argument("--set", action="append", default=[], help="move-file override before tuning (as build-move --set)")
    ap.add_argument("--budget", type=int, default=300, help="objective evaluations (each runs every variant)")
    ap.add_argument("--target", type=int, default=10, help="stop when this many variants pass")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--method", default="cma", choices=["cma", "random"])
    ap.add_argument("--sigma", type=float, default=0.25)
    ap.add_argument("--popsize", type=int, default=8)
    ap.add_argument("--out")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    P = json.loads(Path(a.params).read_text())
    spec0 = build.load_move(a.move, a.set)[1]
    extra_path = R.W.REPO / "moves" / a.move / "robustness-variants.json"
    variants = R.VARIANTS + (json.loads(extra_path.read_text())["variants"] if extra_path.exists() else [])
    rule = {**build.DEFAULT_SLIDE_RULE, **spec0.get("slide_rule", {})}
    nominal = {p["name"]: float(p["x0"] if "x0" in p else get(spec0, p["paths"][0])) for p in P["params"]}
    start = dict(nominal)
    for d in a.detune:
        k, v = d.split("="); start[k] = float(v)
    pool = mp.get_context("fork").Pool(a.workers)
    f = Objective(a.move, P, variants, pool, spec0, rule, a.target)
    u0 = np.clip((np.array([start[n] for n in f.names]) - f.lo) / (f.hi - f.lo), 0, 1)
    print(f"{a.move}: {len(variants)} variants, {len(f.names)} params, start {start}", flush=True)
    c0 = f(u0); start_res = dict(f.best); f.n = 0; f.log = []; f.best = None; f.t0 = time.time()
    print(f"start: {start_res['passed']}/{len(variants)} cost {c0:.3f}", flush=True)
    rng = np.random.default_rng(a.seed)
    if a.method == "cma":
        import cma
        es = cma.CMAEvolutionStrategy(u0, a.sigma, {"bounds": [0, 1], "popsize": a.popsize, "seed": a.seed, "verbose": -9})
        while f.n < a.budget and not es.stop() and not (f.best and f.best["passed"] >= a.target):
            xs = es.ask()
            es.tell(xs, [f(x) for x in xs])
    else:
        while f.n < a.budget and not (f.best and f.best["passed"] >= a.target):
            f(rng.random(len(f.names)))
    b = f.best
    sets = {}
    final = apply(spec0, P, b["vals"])
    for prm in P["params"]:
        for path in prm["paths"]: sets[path] = get(final, path)
    for d in P.get("derived", []): sets[d["path"]] = get(final, d["path"])
    res = {"move": a.move, "method": a.method, "seed": a.seed, "variants": len(variants), "target": a.target,
           "start": {"values": start, "passed": start_res["passed"], "cost": c0},
           "best": {**b, "set": {k: round(v, 6) for k, v in sets.items()}}, "evaluations": f.n,
           "wall_s": round(time.time() - f.t0, 1), "reached_target": b["passed"] >= a.target, "log": f.log}
    print(json.dumps({k: v for k, v in res.items() if k != "log"}, indent=1))
    print("re-check: python3 scripts/build-move.py", a.move, " ".join(f"--set {k}={round(v, 6)}" for k, v in sets.items()), "--robustness --scratch")
    out = Path(a.out or f"out/autotune/{a.move}-{a.method}-s{a.seed}.json")
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
