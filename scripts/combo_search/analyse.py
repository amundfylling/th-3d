"""Robustness and descriptors for a found genome; tentative resemblance to named move families (heuristic)."""
import math
import numpy as np
from . import env, validate
from shotlib import world as W

# the repo's robustness variants (scripts/shotlib/robustness.py VARIANTS) as rollout perturbations
VARIANTS = [
    ("nominal", {}),
    ("footprint dx +0.001", {"footprint": {"dx": 0.001}}), ("footprint dx -0.001", {"footprint": {"dx": -0.001}}),
    ("footprint +2%", {"footprint": {"scale": 1.02}}), ("footprint -2%", {"footprint": {"scale": 0.98}}),
    ("puck +0.2 x", {"puck_dx": [0.2, 0.0]}), ("puck +0.2 y", {"puck_dx": [0.0, 0.2]}),
    ("ice +25%", {"ice_scale": 1.25}), ("ice -25%", {"ice_scale": 0.75}),
    ("restitution 0.3", {"restitution": 0.3}), ("restitution 0.7", {"restitution": 0.7}),
]
# goalie perturbations (ASSUMED): a slower / faster / earlier / later goalie than the one trained against
for nm, base in [("track_med", env.OPPONENTS["track_med"])]:
    for lab, kw in [("delay x0.5", {"delay": base["delay"] * 0.5}), ("delay x1.5", {"delay": base["delay"] * 1.5}),
                    ("vmax x1.3", {"vmax": base["vmax"] * 1.3}), ("vmax x0.7", {"vmax": base["vmax"] * 0.7})]:
        env.OPPONENTS[f"{nm}|{lab}"] = {**base, **kw}


def ok(r):
    return r["goal"] == "E" and r["peak_fig"] <= env.LIMITS["figure_impact_mm_s"] and r["peak_wall"] <= env.LIMITS["wall_impact_mm_s"] and r["min_group_n"] >= env.MIN_PUSH_TOUCHES


def robustness(g, att, opp):
    rows = []
    for lab, pt in VARIANTS:
        r = env.rollout(g, opp, att, perturb=pt)
        rows.append({"variant": lab, "goal": r["goal"], "ok": ok(r), "goal_y": r.get("goal_y")})
    n_phys = sum(x["ok"] for x in rows)
    gy = [x["goal_y"] for x in rows if x["goal_y"] is not None]
    out = {"physics_variants_ok": n_phys, "physics_variants": len(rows), "goal_y_spread_mm": (max(gy) - min(gy)) if gy else None, "rows": rows}
    gl = []
    if opp.startswith("track_med"):
        for lab in ["delay x0.5", "delay x1.5", "vmax x1.3", "vmax x0.7"]:
            r = env.rollout(g, f"track_med|{lab}", att)
            gl.append({"variant": "goalie " + lab, "ok": ok(r), "goal": r["goal"]})
    out["goalie_variants"] = gl
    return out


def descriptor(g, att, opp):
    r = env.rollout(g, opp, att, keep_path=True)
    imp = r["impulses"]
    groups = []
    for x in imp:
        if x["figure"] == "E-G" or x["figure"] not in att:
            pass
        if groups and groups[-1]["figure"] == x["figure"] and x["t"] - groups[-1]["t1"] < 0.06:
            groups[-1]["t1"] = x["t"]; groups[-1]["n"] += 1; groups[-1]["peak"] = max(groups[-1]["peak"], x["impact_mm_s"])
        else:
            groups.append({"figure": x["figure"], "t0": x["t"], "t1": x["t"], "n": 1, "peak": x["impact_mm_s"]})
    figs = {pid: env.figure_from_keys(pid, *k) for pid, k in r["keys"].items()}
    T, P = r["T"], r["P"]
    for gp in groups:
        if gp["figure"] in figs:
            f = figs[gp["figure"]]
            gp["theta0"], gp["theta1"] = f.theta(gp["t0"] - 0.01), f.theta(gp["t1"] + 0.01)
            gp["dtheta"] = gp["theta1"] - gp["theta0"]
            gp["heading_at_contact"] = (f.pose(gp["t0"])[1]) % 360
        i0 = int(np.searchsorted(T, gp["t1"]) + 8); i1 = min(i0 + 400, len(T) - 1)
        v = (P[min(i0 + 40, len(T) - 1)] - P[i0]) / (T[min(i0 + 40, len(T) - 1)] - T[i0] + 1e-9)
        gp["exit_speed"] = float(np.linalg.norm(v)); gp["exit_dir_deg"] = math.degrees(math.atan2(v[1], v[0]))
    r["groups"] = groups
    return r


def classify(r, att):
    """Heuristic resemblance (explicit rules, see report): by the attackers' contact groups, not by trajectories."""
    gs = [g for g in r["groups"] if g["figure"] in att]
    if r["goal"] != "E" or not gs:
        return "no goal"
    seq = [g["figure"] for g in gs]
    side = "right corner (-y)" if r["goal_y"] < r["goalie_y"] else "left corner (+y)"
    if len(set(seq)) == 1 and len(seq) == 1:
        g = gs[0]
        back = abs(((g["heading_at_contact"] + 180) % 360) - 180) > 120  # facing away from the E goal (back to goal)
        word = "Hjerpe-like" if (seq[0] == "W-C" and back) else "direct push"
        return f"{word}: one {seq[0]} push, {'ccw' if g['dtheta'] > 0 else 'cw'} turn {g['dtheta']:.0f} deg, into the {side}"
    if len(set(seq)) == 1 and len(seq) >= 2:
        return f"Nacka/spjass-like: {len(seq)} separate {seq[0]} contacts (pass or carry, then shot), into the {side}"
    return f"two-figure combination ({' -> '.join(seq)}; shovel/centrifuge-like), into the {side}"
