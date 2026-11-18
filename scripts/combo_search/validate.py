"""Replay a rollout through the UNMODIFIED engine (shotlib.puck.run, all 12 figures, saved keyframes only) and compare."""
import numpy as np
from . import env
from shotlib import puck
from shotlib import world as W


def replay(r, perturb=None):
    perturb = perturb or {}
    W.set_footprint_transform(**perturb.get("footprint", {}))
    try:
        figs = {}
        for pid in W.ALL_FIGURES:
            if pid in r["keys"]:
                figs[pid] = env.figure_from_keys(pid, *r["keys"][pid])
            elif pid == "E-G":
                gk = r["goalie_keys"]
                figs[pid] = W.Figure(pid, [{"t": k["t"], "arc_mm": k["arc_mm"]} for k in gk], [{"t": 0.0, "theta_deg": 0.0}])
            else:
                figs[pid] = W.assembly_figure(pid)
        physics = dict(env.PHYS)
        if "ice_scale" in perturb:
            physics["ice_deceleration_mm_s2"] *= perturb["ice_scale"]
        if "restitution" in perturb:
            physics["restitution_figure"] = perturb["restitution"]
        T, P, V, touching, imp, walls, entered = puck.run(env.T0, r["T"][-1], r["p0"], list(figs.values()), physics)
    finally:
        W.set_footprint_transform()
    n = min(len(P), len(r["P"]))
    dev = float(np.abs(P[:n] - r["P"][:n]).max())
    return {"max_dev_mm": dev, "goal_engine": entered, "goal_fast": r["goal"], "n": n, "impulses_engine": len(imp), "impulses_fast": len(r["impulses"]),
            "peak_engine": max([x["impact_mm_s"] for x in imp if x["figure"] != "E-G"] + [0.0])}
