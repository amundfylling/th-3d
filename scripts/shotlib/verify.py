"""Contact check of a SAVED trace, from the trace file alone (CLAUDE.md "Contact physics").

    python3 scripts/verify-trace.py                      every trace in data/traces/
    python3 scripts/verify-trace.py data/traces/x.trace.json [--json]

Every script that writes a trace (scripts/shot22-trace.py, spjass-trace.py, nacka-trace.py, ikv-trace.py,
defence-trace.py, edwall-trace.py and the move engine, scripts/shotlib/build.py) runs its own overlap loop on its own
simulation objects and writes the result to a checks file; the tests and the Remotion gate then read that file. Nothing
ties a checks file to the trace bytes, so an edited or regenerated trace keeps a stale "no overlap".

This module is the one check that needs no generator. It reads a shot-trace/1 file, places the figures exactly as the
renderer does (src/model/trace.ts: monotone cubic arc, linear theta, linear puck; figures the trace does not list stand
in the static assembly pose) and measures the finite puck against all twelve figures' contact footprints
(data/figures/contact-footprints.json), the boards, the goal posts and the cages every 0.25 ms over the whole window,
with no phase exemptions. Overlap tolerance 0.1 mm. Exceptions are only the user's recorded ones
(`approved_overlap_exceptions` of the trace's inputs file), each limited to its obstacle, phase and depth.

It does not simulate and it changes no trace. It does not cover the slide rule: impact speeds come from the contact
events of a simulation, which a saved trace does not hold.

Not part of the engine identity (scripts/shotlib/identity.py NOT_ENGINE): editing it never invalidates a saved trace.
"""
import json
from pathlib import Path

import numpy as np
import shapely

from . import world as W

REPO = W.REPO
DT = W.DT            # 0.25 ms (CLAUDE.md: every 0.25 ms or finer)
PEN_TOL = W.PEN_TOL  # 0.1 mm
MAX_STEP_MM = 2.0    # a puck step between two samples above this is a jump (the limit the trace tests use)


# ---------------------------------------------------------------- evaluation (vector forms of world.Figure)
def pchip_eval(x, y, m, t):
    """world.pchip_eval for an array of times."""
    t = np.asarray(t, float)
    if len(x) == 1:
        return np.full(t.shape, float(y[0]))
    i = np.clip(np.searchsorted(x, t) - 1, 0, len(x) - 2)
    h = x[i + 1] - x[i]
    s = (np.clip(t, x[0], x[-1]) - x[i]) / h
    return ((2 * s**3 - 3 * s**2 + 1) * y[i] + (s**3 - 2 * s**2 + s) * h * m[i]
            + (-2 * s**3 + 3 * s**2) * y[i + 1] + (s**3 - s**2) * h * m[i + 1])


def figure_poses(f, t):
    """Pivot (N x 2 mm) and heading (N, deg) of a world.Figure or world.Static at times t."""
    t = np.asarray(t, float)
    if isinstance(f, W.Static):
        return np.tile(f.piv, (len(t), 1)), np.full(len(t), f.h)
    arc = np.clip(pchip_eval(f.ax, f.ay, f.am, t), 0.0, f.slot.length)
    piv = np.c_[np.interp(arc, f.slot.s, f.slot.P[:, 0]), np.interp(arc, f.slot.s, f.slot.P[:, 1])]
    theta = np.interp(t, f.tx, f.ty) if len(f.tx) > 1 else np.full(len(t), float(f.ty[0]))
    return piv, W.HOME[f.team] + theta


def figures_of(trace):
    """All twelve figures of a saved trace: the listed ones from their keyframes, the others in the assembly pose."""
    figs = []
    for pid in W.ALL_FIGURES:
        f = trace["figures"].get(pid)
        if isinstance(f, dict):
            for key in ("arc_keyframes", "theta_keyframes"):
                ts = [k["t"] for k in f[key]]
                if not ts or any(b <= a for a, b in zip(ts, ts[1:])):
                    raise ValueError(f"{pid}: {key} empty or not strictly increasing in time")
            figs.append(W.Figure(pid, f["arc_keyframes"], f["theta_keyframes"], f.get("status", "")))
        else:
            figs.append(W.assembly_figure(pid))
    unknown = [p for p, f in trace["figures"].items() if isinstance(f, dict) and p not in W.ALL_FIGURES]
    if unknown:
        raise ValueError(f"figures not on the table: {unknown}")
    return figs


_HULL = {}


def figure_clearance(f, t, p, group=None, exact=False):
    """Signed distance puck edge -> the figure's footprint at each time (negative = overlap), as world.clearance.

    The footprints have thousands of vertices, so the exact distance is only measured where it can matter. The distance
    to the footprint's convex hull is cheap and never larger than the distance to the footprint. Per group (the puck
    phase of each sample; one group by default) the exact distance is taken at the sample nearest the hull, and then at
    every sample whose hull distance is not above that value or above the puck radius. So each group's minimum and
    every overlap are exact; the other samples carry the hull distance, a lower bound that is above both.
    exact=True measures every sample."""
    piv, head = figure_poses(f, t)
    h = np.radians(head)
    c, s = np.cos(h), np.sin(h)
    dx, dy = p[:, 0] - piv[:, 0], p[:, 1] - piv[:, 1]
    lx, ly = c * dx + s * dy, -s * dx + c * dy
    low = W.LOW[f.kind]
    if id(low) not in _HULL:
        _HULL[id(low)] = (low, low.convex_hull)  # keeps `low` alive, so its id stays its own
    out = shapely.distance(_HULL[id(low)][1], shapely.points(lx, ly))  # 0 inside the hull
    need = np.ones(len(out), bool) if exact else out <= W.R_PUCK + 1.0
    if not exact:
        group = np.zeros(len(out), int) if group is None else np.asarray(group)
        for g in np.unique(group):
            sel = np.flatnonzero(group == g)
            k = sel[np.argmin(out[sel])]
            q = shapely.Point(lx[k], ly[k])
            need[sel[out[sel] <= low.boundary.distance(q)]] = True  # an outside point: its exact distance bounds the minimum
    k = np.flatnonzero(need)
    # a puck at rest beside a figure at rest is one point measured once
    q, inv = np.unique(np.c_[lx[k], ly[k]], axis=0, return_inverse=True)
    d = shapely.distance(low.boundary, shapely.points(q[:, 0], q[:, 1]))
    out[k] = np.where(shapely.contains_xy(low, q[:, 0], q[:, 1]), -d, d)[inv.ravel()]
    return out - W.R_PUCK


# ---------------------------------------------------------------- the check
def contact_check(trace, exceptions=(), dt=DT):
    """Clearances of the saved puck against every obstacle over the whole trace window.

    exceptions: the user's approved overlaps ({"id", "obstacle", "phase", "max_overlap_mm", "approved_by"}); an
    exception never covers another obstacle, another phase or a deeper overlap.
    """
    if trace.get("schema") != "shot-trace/1":
        raise ValueError(f"unsupported trace schema {trace.get('schema')}")
    if dt > DT + 1e-12:
        raise ValueError(f"sampling {dt} s is coarser than {DT} s")
    nodes = trace["puck"]["nodes"]
    nt = np.array([n["t"] for n in nodes], float)
    if len(nt) < 2 or np.any(np.diff(nt) <= 0):
        raise ValueError("puck nodes: fewer than two, or times not strictly increasing")
    if abs(trace["puck"]["radius_mm"] - W.R_PUCK) > 1e-9:
        raise ValueError(f"trace puck radius {trace['puck']['radius_mm']} mm, geometry {W.R_PUCK} mm")
    t0, t1 = trace["time_base"]["window_s"]
    t = np.arange(t0, t1 + 1e-9, dt)
    p = np.c_[np.interp(t, nt, [n["x_mm"] for n in nodes]), np.interp(t, nt, [n["y_mm"] for n in nodes])]
    phase_of_node = [n["phase"] for n in nodes]
    ph = np.array(phase_of_node)[np.clip(np.searchsorted(nt, t, side="right") - 1, 0, len(nodes) - 1)]
    # Rows are named by the phase of the node before the sample, as the generators name them. The trace also records
    # phase intervals (puck.phases, half-open, the reading of src/model/trace.ts), and a boundary can fall between two
    # nodes, where the two readings differ for a few samples. An exception is scoped to a phase, so it covers an
    # overlap only where BOTH readings give its phase.
    ph_interval = ph.astype(object)
    for q in reversed(trace["puck"].get("phases") or []):  # where intervals overlap, the first listed wins
        a, b = q["t"]
        ph_interval[(t >= a) & (t < (np.inf if b is None else b))] = q["id"]
    step = np.hypot(*np.diff(p, axis=0).T) if len(p) > 1 else np.zeros(0)

    # the goal the puck enters (first crossing of a goal line between the posts): from then on its cage is not an
    # obstacle WHILE the puck centre is inside it (the net catches the puck and may give under it). A centre that
    # leaves the cage through a side or the back is measured against the walls again, so a puck through the net is
    # an overlap. The posts stay obstacles throughout.
    entered, k_in = None, len(t)
    for g in W.GOALS.values():
        beyond = g.sign * (p[:, 0] - g.x) >= 0
        cross = np.flatnonzero(~beyond[:-1] & beyond[1:] & (np.abs(p[1:, 1] - g.y) < g.half)) + 1
        if len(cross) and cross[0] < k_in:
            entered, k_in = g.end, int(cross[0])

    pts = shapely.points(p[:, 0], p[:, 1])
    phases = list(dict.fromkeys(phase_of_node))
    group = np.array([phases.index(x) for x in phase_of_node])[np.clip(np.searchsorted(nt, t, side="right") - 1, 0, len(nodes) - 1)]
    obstacles = {f.pid: figure_clearance(f, t, p, group) for f in figures_of(trace)}
    # outside the boards counts as an overlap of the boards, however far outside
    d_board = shapely.distance(W.BOARD.exterior, pts)
    obstacles["boards"] = np.where(shapely.contains_xy(W.BOARD, p[:, 0], p[:, 1]), d_board, -d_board) - W.R_PUCK
    for g in W.GOALS.values():
        for k, po in enumerate(g.posts):
            obstacles[f"goal_{g.end}_post_{'pos' if k == 0 else 'neg'}_y"] = np.hypot(p[:, 0] - po[0], p[:, 1] - po[1]) - W.R_PUCK - g.post_r
        cage = shapely.distance(g.walls, pts) - W.R_PUCK
        if entered == g.end:
            depth = g.sign * (p[:, 0] - g.x)
            inside = (depth >= 0) & (depth <= g.depth) & (np.abs(p[:, 1] - g.y) <= g.half)
            inside[:k_in] = False
            cage[inside] = np.inf
        obstacles[f"goal_{g.end}_cage"] = cage

    exc = [dict(e) for e in exceptions]
    rows, overlaps, used = [], [], {}
    for ob, c in obstacles.items():
        for name in phases:
            sel = np.flatnonzero((ph == name) & np.isfinite(c))
            if not len(sel):
                continue
            k = sel[np.argmin(c[sel])]
            rows.append({"obstacle": ob, "phase": name, "min_clearance_mm": round(float(c[k]), 3), "t_at_min": round(float(t[k]), 5)})
            bad = sel[c[sel] < -PEN_TOL]
            if not len(bad):
                continue
            item = {"obstacle": ob, "phase": name, "t0": round(float(t[bad[0]]), 5), "t1": round(float(t[bad[-1]]), 5), "worst_mm": round(float(c[bad].min()), 3)}
            e = next((e for e in exc if e.get("obstacle") == ob and e.get("phase") == name), None)
            if e and "user" in str(e.get("approved_by", "")) and item["worst_mm"] >= -float(e["max_overlap_mm"]) and np.all(ph_interval[bad] == name):
                used[e["id"]] = {**item, "max_overlap_mm": e["max_overlap_mm"], "approved_by": e["approved_by"]}
            else:
                overlaps.append(item)
    max_step = round(float(step.max()), 3) if len(step) else 0.0
    problems = [f"puck jumps {max_step} mm between two samples (limit {MAX_STEP_MM} mm)"] if max_step >= MAX_STEP_MM else []
    return {
        "trace_id": trace["trace_id"], "status": trace["status"], "window_s": [t0, t1], "sampling_s": dt, "samples": int(len(t)),
        "penetration_tolerance_mm": PEN_TOL, "figures_checked": len(W.ALL_FIGURES), "goal_entered": entered,
        "max_puck_step_mm": max_step, "phase_boundary_samples": int(np.sum(ph_interval != ph)), "unexpected_penetrations": overlaps, "approved_exceptions": used,
        "unused_exceptions": [e["id"] for e in exc if e["id"] not in used], "problems": problems,
        "min_clearance_by_obstacle_and_phase": rows, "passed": not overlaps and not problems,
    }


# ---------------------------------------------------------------- saved traces and what was recorded for them
def saved_traces():
    return sorted((REPO / "data/traces").glob("*.trace.json"))


def recorded_for(trace_id):
    """(checks path, inputs path or None) of the checks file a generator saved for this trace id, or (None, None).
    The inputs file beside it holds the user's approved overlap exceptions, if any."""
    for c in sorted((REPO / "shots").glob("*/*checks.json")):
        if json.loads(c.read_text()).get("trace_id") == trace_id:
            i = c.with_name(c.name.replace("checks.json", "inputs.json"))
            return c, (i if i.exists() else None)
    return None, None


def approved_exceptions(trace_id):
    _, inputs = recorded_for(trace_id)
    return json.loads(inputs.read_text()).get("approved_overlap_exceptions", []) if inputs else []


def verify_file(path):
    """contact_check of one saved trace file, with its approved exceptions, plus the comparison with the checks file its
    generator saved: both must say "no unexpected overlap"."""
    path = Path(path)
    trace = json.loads(path.read_text())
    r = contact_check(trace, approved_exceptions(trace["trace_id"]))
    r["trace"] = str(path.resolve().relative_to(REPO)) if path.resolve().is_relative_to(REPO) else str(path)
    cpath, _ = recorded_for(trace["trace_id"])
    if cpath is None:
        r["problems"].append("no saved checks file names this trace id")
    else:
        saved = json.loads(cpath.read_text())
        r["recorded_checks"] = str(cpath.relative_to(REPO))
        if saved.get("unexpected_penetrations"):
            r["problems"].append(f"{r['recorded_checks']} records overlaps")
    r["passed"] = not r["unexpected_penetrations"] and not r["problems"]
    return r
