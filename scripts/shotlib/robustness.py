"""Robustness of a move: does it still work when the uncertain inputs are a little different?

A designed move is only as good as its margins. The contact rules are deterministic, but a push or a glancing contact
can turn a tiny change into a different outcome (a 0.000001 mm change of the figure geometry made the v2 IKV trace miss
the goal). Every value behind a move carries an uncertainty (footprint scale assumed, the puck's start placed by hand,
ice friction borrowed, restitution assumed), so the build reruns the move with each of them changed and reports whether
the outcome holds:
- the same goal (or none) and the expected contact sequence;
- the goal-line crossing (spread in mm);
- the slide limits (peak figure and wall impacts).

    /root/venvs/blender/bin/python scripts/build-move.py <move-id> --robustness

Output: validation/moves/<id>-robustness.json (scratch and --set runs: out/moves/<id>/robustness.json, never the saved one). The variants and their sizes are
ASSUMED (below); they are the questions "what if the model is off by this much", not measured uncertainties.
"""
import json
import multiprocessing as mp

import numpy as np

from . import build
from . import world as W

VARIANTS = [
    {"id": "nominal"},
    {"id": "geometry +0.001 mm (numerical conditioning)", "footprint": {"dx": 0.001}},
    {"id": "geometry -0.001 mm (numerical conditioning)", "footprint": {"dx": -0.001}},
    {"id": "figure footprint 2% larger (mold scale)", "footprint": {"scale": 1.02}},
    {"id": "figure footprint 2% smaller (mold scale)", "footprint": {"scale": 0.98}},
    {"id": "puck start +0.2 mm x", "puck_dx": [0.2, 0.0]},
    {"id": "puck start +0.2 mm y", "puck_dx": [0.0, 0.2]},
    {"id": "ice friction +25%", "physics": {"ice_deceleration_scale": 1.25}},
    {"id": "ice friction -25%", "physics": {"ice_deceleration_scale": 0.75}},
    {"id": "restitution 0.3", "physics": {"restitution_figure": 0.3}},
    {"id": "restitution 0.7", "physics": {"restitution_figure": 0.7}},
]


def _run(args):
    spec, var = args
    W.set_footprint_transform(**var.get("footprint", {}))
    spec = json.loads(json.dumps(spec))
    ph = {**build.DEFAULT_PHYSICS, **spec.get("physics", {})}
    vp = dict(var.get("physics", {}))
    if "ice_deceleration_scale" in vp:
        ph["ice_deceleration_mm_s2"] *= vp.pop("ice_deceleration_scale")
    ph.update(vp)
    spec["physics"] = ph
    if "puck_dx" in var:
        st = spec["puck"]["start"]
        if "at_mm" in st:
            st["at_mm"] = [st["at_mm"][0] + var["puck_dx"][0], st["at_mm"][1] + var["puck_dx"][1]]
        else:
            t0 = spec["window_s"][0]
            build.seed_meets(spec)
            f = build.figures_of(spec, *spec["window_s"])[st["against"]]
            p = W.to_world(f, t0, np.array(st["local_mm"], float)) + np.array(var["puck_dx"])
            st["local_mm"] = [float(x) for x in W.to_local(f, t0, p)]
    try:
        t0, t1, physics, figs, order, p0, (T, P, V, touching, imp, walls, entered) = build.simulate(spec)
    except build.MeetError as e:  # a figure cannot meet the puck at all in this variant: the move fails
        return {"variant": var["id"], "goal": None, "goal_y_mm": None, "sequence_as_expected": False, "sequence": [], "error": str(e),
                "peak_figure_impact_mm_s": None, "peak_wall_impact_mm_s": None, "slide_ok": False, "outcome_ok": False}
    iv = build.intervals(T, touching)
    eps = []
    for c in sorted(iv, key=lambda c: c["t0"]):
        pr = next((e for e in reversed(eps) if e["obstacle"] == c["obstacle"]), None)
        if pr and c["t0"] - pr["t1"] <= build.GROUP_GAP_S:
            pr["t1"] = max(pr["t1"], c["t1"])
        else:
            eps.append(dict(c))
    first_imp = imp[0]["t"] if imp else t1
    eps = [e for e in eps if not (e["t1"] < first_imp and e["obstacle"].split(":")[0] == spec["puck"]["start"].get("against"))]
    seq = [e["obstacle"] for e in eps]
    seq = [s for i, s in enumerate(seq) if i == 0 or s != seq[i - 1]]
    gi = build._goal_index(P, entered)
    rule = {**build.DEFAULT_SLIDE_RULE, **spec.get("slide_rule", {})}
    pf = max([x["impact_mm_s"] for x in imp] + [0.0]); pw = max([w["impact_mm_s"] for w in walls] + [0.0])
    exp = spec.get("expect", {})
    if "contact_sequence" in exp and entered and entered == exp.get("goal"):
        # the run ends at the move's window: a puck that crossed the goal line may not have reached the net yet
        # (a later shot), which is still the expected outcome
        want = exp["contact_sequence"]
        if seq == want[:-1] and want[-1] == "goal_net":
            seq = seq + ["goal_net"]
    return {"variant": var["id"], "goal": entered, "goal_y_mm": round(float(P[gi, 1]), 2) if gi is not None else None,
            "sequence_as_expected": seq == exp["contact_sequence"] if "contact_sequence" in exp else None, "sequence": seq,
            "peak_figure_impact_mm_s": pf, "peak_wall_impact_mm_s": pw,
            "slide_ok": pf <= rule["figure_impact_max_mm_s"] and pw <= rule["wall_impact_max_mm_s"],
            "outcome_ok": (entered == exp.get("goal", entered)) and (seq == exp["contact_sequence"] if "contact_sequence" in exp else True)}


def robustness(move_id, spec, canonical=True):
    """canonical=False (scratch or --set runs): the report goes to out/moves/<id>/ and never replaces the saved one."""
    with mp.get_context("fork").Pool(min(4, len(VARIANTS))) as pool:
        rows = pool.map(_run, [(spec, v) for v in VARIANTS])
    ys = [r["goal_y_mm"] for r in rows if r["goal_y_mm"] is not None]
    ok = [r for r in rows if r["outcome_ok"] and r["slide_ok"]]
    rep = {"move": move_id, "trace_id": spec["trace_id"],
           "rule": "the move must keep its outcome (goal, contact sequence) and the slide limits under every variant; variant sizes ASSUMED",
           "variants_passed": f"{len(ok)}/{len(rows)}", "robust": len(ok) == len(rows),
           "goal_y_spread_mm": [min(ys), max(ys)] if ys else None, "rows": rows}
    rep["move_file_sha256"] = build.sha(W.REPO / "moves" / move_id / "move.json")
    rep["canonical"] = canonical
    out = W.REPO / (f"validation/moves/{move_id}-robustness.json" if canonical else f"out/moves/{move_id}/robustness.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
    return rep


# How far can each input change before the move misses? Each ladder is walked in both directions from the nominal
# value; the margin is the largest step for which that step and every smaller one still hold (outcome and slide
# limits). Step sizes are ASSUMED, chosen to span "numerical noise" to "clearly a different table".
LADDERS = [
    {"input": "puck start x", "unit": "mm", "steps": [0.01, 0.03, 0.1, 0.3, 1.0, 3.0],
     "variant": lambda s: {"puck_dx": [s, 0.0]}},
    {"input": "puck start y", "unit": "mm", "steps": [0.01, 0.03, 0.1, 0.3, 1.0, 3.0],
     "variant": lambda s: {"puck_dx": [0.0, s]}},
    {"input": "figure footprint scale", "unit": "%", "steps": [0.25, 0.5, 1.0, 2.0, 5.0],
     "variant": lambda s: {"footprint": {"scale": 1.0 + s / 100.0}}},
    {"input": "ice friction", "unit": "%", "steps": [5.0, 10.0, 25.0, 50.0],
     "variant": lambda s: {"physics": {"ice_deceleration_scale": 1.0 + s / 100.0}}},
    {"input": "figure restitution", "unit": "(absolute, nominal 0.5)", "steps": [0.05, 0.1, 0.2, 0.3],
     "variant": lambda s: {"physics": {"restitution_figure": 0.5 + s}}},
]


def margins(move_id, spec, canonical=True):
    """For each LADDERS input: the largest change (each direction) the move survives. Output beside the robustness
    report: validation/moves/<id>-margins.json (scratch: out/moves/<id>/margins.json)."""
    jobs = []
    for li, lad in enumerate(LADDERS):
        for sign in (1, -1):
            for s in lad["steps"]:
                jobs.append((li, sign, s, {"id": f'{lad["input"]} {sign * s:+g} {lad["unit"]}', **lad["variant"](sign * s)}))
    with mp.get_context("fork").Pool(4) as pool:
        rows = pool.map(_run, [(spec, j[3]) for j in jobs])
    out_rows = []
    for li, lad in enumerate(LADDERS):
        m = {}
        for sign, name in ((1, "up"), (-1, "down")):
            held = None
            res = [(s, r) for (l, sg, s, _), r in zip(jobs, rows) if l == li and sg == sign]
            for s, r in res:
                if r["outcome_ok"] and r["slide_ok"]:
                    held = s
                else:
                    break
            first_fail = next(((s, r) for s, r in res if not (r["outcome_ok"] and r["slide_ok"])), None)
            m[name] = {"holds_up_to": held, "first_miss": first_fail[0] if first_fail else None,
                       "first_miss_why": None if not first_fail else
                       (first_fail[1].get("error") or ("slide limits" if first_fail[1]["outcome_ok"] else f'goal {first_fail[1]["goal"]}, sequence {first_fail[1]["sequence"]}'))}
        # the ladder is not monotone (a small change can miss where a larger one holds), so every step is listed
        steps = [{"change": sg * s, "scores": r["outcome_ok"], "slide_ok": r["slide_ok"], "goal_y_mm": r["goal_y_mm"],
                  "peak_wall_impact_mm_s": r["peak_wall_impact_mm_s"], "peak_figure_impact_mm_s": r["peak_figure_impact_mm_s"]}
                 for (l, sg, s, _), r in zip(jobs, rows) if l == li]
        out_rows.append({"input": lad["input"], "unit": lad["unit"], "steps_tried": lad["steps"], **m,
                         "steps_holding": f'{sum(x["scores"] and x["slide_ok"] for x in steps)}/{len(steps)}',
                         "steps_scoring": f'{sum(x["scores"] for x in steps)}/{len(steps)}', "steps": sorted(steps, key=lambda x: x["change"])})
    rep = {"move": move_id, "trace_id": spec["trace_id"],
           "rule": "holds_up_to: largest change of one input (all smaller steps included) that keeps the outcome and the slide "
                   "limits; null = the smallest step already misses. steps_holding / steps_scoring count every step "
                   "(scoring = goal and contact sequence, ignoring the slide limits). Step sizes ASSUMED",
           "margins": out_rows, "rows": rows, "move_file_sha256": build.sha(W.REPO / "moves" / move_id / "move.json"),
           "canonical": canonical}
    out = W.REPO / (f"validation/moves/{move_id}-margins.json" if canonical else f"out/moves/{move_id}/margins.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
    return rep
