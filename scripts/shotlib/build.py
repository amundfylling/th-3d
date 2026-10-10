"""Build one move of the shot encyclopedia from its move file: figures -> puck -> checks -> trace.

    /root/venvs/blender/bin/python scripts/build-move.py <move-id> [--set key.path=value ...] [--scratch]

A move file (moves/<id>/move.json, format in docs/shot-encyclopedia.md) says what the figures do; the puck follows from
the contact rules (scripts/shotlib/puck.py). The build always writes its full result to out/moves/<id>/ and, only when
every check passes (no overlap, slide check, no unexplained motion change, the move file's expectations), writes
data/traces/<id>.trace.json, shots/<id>/checks.json and validation/moves/<id>-sheet.png (CLAUDE.md: a trace that fails
is not saved).
"""
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Point

from . import motion, puck
from . import world as W

REPO = W.REPO
SPJ_CHECKS = json.loads((REPO / "shots/spjass/checks.json").read_text())
MANIFEST = json.loads((REPO / "remotion/asset-manifest.json").read_text())
DEFAULT_PHYSICS = {
    "restitution_figure": 0.5,
    "restitution_figure_status": "assumed: blade/skate-puck collisions keep half the approach speed (frictionless); as trace.invers-kryssar-velodrom.v2",
    "ice_deceleration_mm_s2": SPJ_CHECKS["slide_fit"]["deceleration_mm_s2"],
    "ice_deceleration_status": "borrowed from the spjass slide fit (shots/spjass/checks.json slide_fit)",
    "boards_posts": "inelastic: the normal velocity is removed, the puck slides along",
}
DEFAULT_SLIDE_RULE = {"figure_impact_max_mm_s": 500.0, "wall_impact_max_mm_s": 300.0,
                      "status": "assumed (CLAUDE.md 'Slide or bounce', user rule 2026-10-06)"}
GROUP_GAP_S = 0.06  # figure touches closer than this are one contact (a push is many small touches)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_move(move_id, sets=()):
    path = REPO / "moves" / move_id / "move.json"
    spec = json.loads(path.read_text())
    for s in sets:  # parameter scans only; the saved trace records them
        key, val = s.split("=", 1)
        node, parts = spec, key.split(".")
        for p_ in parts[:-1]:
            node = node[int(p_)] if isinstance(node, list) else node[p_]
        last = parts[-1]
        val = json.loads(val)
        if isinstance(node, list):
            node[int(last)] = val
        else:
            node[last] = val
    return path, spec


def figures_of(spec, t0, t1):
    figs = {}
    for pid in W.ALL_FIGURES:
        fs = spec["figures"].get(pid, {"static": "assembly"})
        figs[pid] = motion.build_figure(pid, fs, t0, t1)
    return figs


def contact_groups(impulses):
    groups = {}
    for x in impulses:
        g = groups.setdefault(x["figure"], [])
        if g and x["t"] - g[-1][-1]["t"] <= GROUP_GAP_S:
            g[-1].append(x)
        else:
            g.append([x])
    return groups


def intervals(T, touching):
    iv = []
    for t, hs in zip(T, touching):
        for h in hs:
            if iv and iv[-1]["obstacle"] == h and t - iv[-1]["t1"] <= 4 * W.DT + 1e-9:
                iv[-1]["t1"] = float(t)
            elif not any(x["obstacle"] == h and t - x["t1"] <= 4 * W.DT + 1e-9 for x in iv[-3:]):
                iv.append({"obstacle": h, "t0": float(t), "t1": float(t)})
            else:
                for x in iv[-3:]:
                    if x["obstacle"] == h:
                        x["t1"] = float(t)
    return iv


def eval_trigger(name, tr, spec, figs, T, P, imp):
    """First time a trigger condition holds in a puck run (None if never).
    - {"type": "puck_near", "figure": pid, "local_mm": [x, y], "within_mm": d, "after_s": t}: the puck centre comes
      within d of a point fixed to the figure (e.g. the middle of its blade);
    - {"type": "puck_line", "axis": "x"|"y", "ge"|"le": v, "after_s": t}: the puck centre crosses a line;
    - {"type": "contact", "figure": pid, "group": i, "edge": "start"|"end"}: a touch group of a figure (as `contacts`)."""
    after = tr.get("after_s", -1e9)
    if tr["type"] == "contact":
        gs = contact_groups(imp).get(tr["figure"], [])
        gs = [g for g in gs if g[0]["t"] >= after]
        try:
            g = gs[tr.get("group", 0)]
        except IndexError:
            return None
        return g[0]["t"] if tr.get("edge", "start") == "start" else g[-1]["t"]
    for k in range(len(T)):
        t = T[k]
        if t < after:
            continue
        if tr["type"] == "puck_near":
            f = figs[tr["figure"]]
            if np.linalg.norm(W.to_world(f, t, np.array(tr["local_mm"], float)) - P[k]) <= tr["within_mm"]:
                return float(t)
        elif tr["type"] == "puck_line":
            v = P[k, 0 if tr["axis"] == "x" else 1]
            if ("ge" in tr and v >= tr["ge"]) or ("le" in tr and v <= tr["le"]):
                return float(t)
    return None


def simulate(spec, max_rounds=8, tol_s=0.001):
    """Figures -> puck. With triggers: start from each trigger's guess, run the puck, read the trigger times off the run,
    rebuild the figures and run again until no trigger moves by more than one step (a trigger only shifts motion that
    starts at it, so later triggers settle after earlier ones)."""
    t0, t1 = spec["window_s"]
    physics = {**DEFAULT_PHYSICS, **spec.get("physics", {})}
    trigs = spec.get("triggers", {})
    motion.TRIG.clear()
    motion.TRIG.update({k: v["guess_s"] for k, v in trigs.items()})
    history = []
    for rnd in range(max_rounds if trigs else 1):
        figs = figures_of(spec, t0, t1)
        order = [figs[p] for p in spec["figures"] if p in figs] + [f for p, f in figs.items() if p not in spec["figures"]]
        p0 = puck.start_position(spec["puck"]["start"], order, t0)
        res = puck.run(t0, t1, p0, order, physics, spec["puck"].get("start", {}).get("velocity_mm_s", (0.0, 0.0)))
        if not trigs:
            break
        T, P, V, touching, imp, walls, entered = res
        new = {}
        for name, tr in trigs.items():
            tt = eval_trigger(name, tr, spec, figs, T, P, imp)
            new[name] = round(tt, 5) if tt is not None else motion.TRIG[name]
        history.append({"used": dict(motion.TRIG), "read": new})
        if all(abs(new[k] - motion.TRIG[k]) <= tol_s for k in new) or rnd == max_rounds - 1:
            break
        motion.TRIG.update(new)
    # the trace is the last run (its figures used `used`); `read` is what that run's puck would ask for
    physics = {**physics, "triggers": history[-1] if history else None, "trigger_rounds": len(history),
               "trigger_residual_s": max([abs(history[-1]["read"][k] - history[-1]["used"][k]) for k in trigs] + [0.0]) if history else 0.0}
    return t0, t1, physics, figs, order, p0, res


def quick_summary(spec):
    """For scans: goal, contact groups, slide peaks (no files written)."""
    t0, t1, physics, figs, order, p0, (T, P, V, touching, imp, walls, entered) = simulate(spec)
    groups = contact_groups(imp)
    i_goal = _goal_index(P, entered)
    return {"goal": entered, "goal_y_mm": round(float(P[i_goal, 1]), 2) if i_goal is not None else None,
            "groups": {k: [[g[0]["t"], g[-1]["t"], len(g), max(x["impact_mm_s"] for x in g)] for g in v] for k, v in groups.items()},
            "peak_wall": max([w["impact_mm_s"] for w in walls] + [0.0]), "end_mm": [round(float(x), 1) for x in P[-1]]}


def _goal_index(P, entered):
    if entered is None:
        return None
    g = W.GOALS[entered]
    return next((i for i in range(1, len(P)) if g.crossed(P[i - 1], P[i])), None)


def build(move_id, sets=(), scratch=False):
    move_path, spec = load_move(move_id, sets)
    t0, t1, physics, figs, order, p0, (T, P, V, touching, imp, walls, entered) = simulate(spec)
    moving = [p for p, fs in spec["figures"].items() if "static" not in fs]
    groups = contact_groups(imp)
    iv = intervals(T, touching)
    deg = lambda v: round(math.degrees(math.atan2(v[1], v[0])), 2)
    vel = lambda tq: V[min(int(np.searchsorted(T, tq)), len(V) - 1)]
    at = lambda tq: np.array([np.interp(tq, T, P[:, 0]), np.interp(tq, T, P[:, 1])])
    peak = lambda g: round(max(x["impact_mm_s"] for x in g), 1)
    problems = []

    # ---- named contacts (move file `contacts`: which touch group of which figure is which part of the move)
    named = []
    for c in spec.get("contacts", []):
        gs = groups.get(c["figure"], [])
        try:
            g = gs[c.get("group", 0)]
        except IndexError:
            problems.append(f"contact '{c['id']}': {c['figure']} has only {len(gs)} touch groups")
            continue
        named.append((c, g))
    named.sort(key=lambda cg: cg[1][0]["t"])
    goal_i = _goal_index(P, entered)
    t_goal = float(T[goal_i]) if goal_i is not None else None
    nets = [c for c in iv if c["obstacle"] == "goal_net"]
    t_net = nets[0]["t0"] if nets else None

    # ---- events
    events = []
    for c, g in named:
        # a puck resting against the blade registers zero-speed touches before the move: the contact starts at the
        # first touch of at least 1 mm/s
        ta, tb = next((x["t"] for x in g if x["impact_mm_s"] >= 1.0), g[0]["t"]), g[-1]["t"]
        f = figs[c["figure"]]
        loc, nrm = W.local_contact(f, ta, at(ta))
        v_after = vel(tb + 0.006)
        ev = {"id": f"contact.{c['id']}", "t_estimate": round(ta, 5), "t_end": round(tb, 5), "figure": c["figure"],
              "part": f"{c['figure']}:{g[0]['part']}" + (f" ({c['part']})" if c.get("part") else ""), "contact_point_local_mm": loc,
              "model_contact_normal_deg": nrm, "touches": len(g), "first_impact_mm_s": g[0]["impact_mm_s"], "peak_impact_mm_s": peak(g),
              "speed_after_mm_s": round(float(np.linalg.norm(v_after)), 1), "direction_after_deg": deg(v_after),
              "heading_at_contact_deg": round(f.pose(ta)[1], 2), "arc_at_contact_mm": round(f.arc(ta), 2) if hasattr(f, "arc") else None,
              "status": "derived from the designed figure motion (contact rules, scripts/shotlib/puck.py)"}
        events.append(ev)
    for e in spec.get("events", []):  # designed moments (turn onsets...) the video can point at
        events.append({"id": e["id"], "t_estimate": e["t"], "status": "designed: " + e.get("why", "")})
    if t_goal is not None:
        events.append({"id": "goal_entry", "t_estimate": round(t_goal, 5), "goal": entered, "goal_line_y_mm": round(float(P[goal_i, 1]), 2), "status": "derived"})
    if t_net is not None:
        events.append({"id": "goal_net", "t_estimate": round(t_net, 5), "status": "rule: the puck stops against the back of the preview cage"})
    events.sort(key=lambda e: e["t_estimate"])

    # ---- phases: rest, each named contact, free between them, in the goal
    bounds = [(next((x["t"] for x in g if x["impact_mm_s"] >= 1.0), g[0]["t"]), g[-1]["t"] + 0.004, c.get("phase", c["id"]), c.get("after", f"after_{c['id']}")) for c, g in named]

    def phase(t):
        if t_net is not None and t >= t_net:
            return "in_goal"
        name = spec["puck"].get("start_phase", "rest")
        for a, b, during, after in bounds:
            if t < a:
                return name
            if t <= b:
                return during
            name = after
        return name

    nodes = [{"t": round(float(T[k]), 5), "x_mm": round(float(P[k, 0]), 4), "y_mm": round(float(P[k, 1]), 4), "phase": phase(float(T[k]))}
             for k in range(0, len(T), W.NODE_EVERY)]
    if nodes[-1]["t"] < round(float(T[-1]), 5):
        nodes.append({"t": round(float(T[-1]), 5), "x_mm": round(float(P[-1, 0]), 4), "y_mm": round(float(P[-1, 1]), 4), "phase": phase(float(T[-1]))})
    phases = []
    for n_ in nodes:
        if not phases or phases[-1]["id"] != n_["phase"]:
            if phases:
                phases[-1]["t"][1] = n_["t"]
            phases.append({"id": n_["phase"], "t": [n_["t"], None]})

    # ---- contact check on the SAVED trace (linear between nodes), every DT: all figures, boards, posts, cages
    nt = np.array([n_["t"] for n_ in nodes]); nx = np.array([n_["x_mm"] for n_ in nodes]); ny = np.array([n_["y_mm"] for n_ in nodes])
    rows, viol, prev, max_step, inside = {}, [], None, 0.0, None
    for tq in np.arange(t0, t1 + 1e-9, W.DT):
        p = np.array([np.interp(tq, nt, nx), np.interp(tq, nt, ny)])
        ph = nodes[min(max(int(np.searchsorted(nt, tq, side="right") - 1), 0), len(nodes) - 1)]["phase"]
        if prev is not None:
            max_step = max(max_step, float(np.linalg.norm(p - prev)))
            for g in W.GOALS.values():
                if inside is None and g.crossed(prev, p):
                    inside = g.end
        prev = p
        cs = [(f.pid, W.clearance(f, tq, p)) for f in order] + [("boards", W.BOARD.exterior.distance(Point(*p)) - W.R_PUCK)]
        for g in W.GOALS.values():
            cs += [(f"goal_{g.end}_post_{'pos' if k == 0 else 'neg'}_y", float(np.linalg.norm(p - po)) - W.R_PUCK - g.post_r) for k, po in enumerate(g.posts)]
            if inside != g.end:
                cs.append((f"goal_{g.end}_cage", float(g.walls.distance(Point(*p))) - W.R_PUCK))
        for ob, c in cs:
            r = rows.setdefault((ob, ph), {"min_clearance_mm": 1e9, "t_at_min": None})
            if c < r["min_clearance_mm"]:
                r.update(min_clearance_mm=round(float(c), 3), t_at_min=round(float(tq), 5))
            if c < -W.PEN_TOL:
                viol.append((ob, ph, round(float(tq), 5), round(float(c), 3)))
    vint = {}
    for ob, ph, tq, c in viol:
        a = vint.setdefault((ob, ph), {"t0": tq, "t1": tq, "worst_mm": c}); a["t1"] = tq; a["worst_mm"] = min(a["worst_mm"], c)
    unexplained = [round(float(T[i]), 5) for i in range(2, len(T)) if not touching[i] and float(np.linalg.norm(V[i] - V[i - 1])) > physics["ice_deceleration_mm_s2"] * W.DT + 1e-6]

    # ---- slide or bounce (CLAUDE.md, user rule 2026-10-06)
    rule = {**DEFAULT_SLIDE_RULE, **spec.get("slide_rule", {})}
    f_bad = [x for x in imp if x["impact_mm_s"] > rule["figure_impact_max_mm_s"]]
    w_bad = [w for w in walls if w["impact_mm_s"] > rule["wall_impact_max_mm_s"]]
    named_ids = {id(g): c["id"] for c, g in named}
    wall_peak = lambda ob: round(max([w["impact_mm_s"] for w in walls if w["obstacle"] == ob] + [0.0]), 1)
    slide_check = {"rule": "CLAUDE.md 'Slide or bounce': every contact must leave the puck flat on the ice; the net catching the puck is exempt",
                   "figure_impact_max_mm_s": rule["figure_impact_max_mm_s"], "wall_impact_max_mm_s": rule["wall_impact_max_mm_s"], "limits_status": rule["status"],
                   "per_contact": [{"contact": named_ids.get(id(g), f"other ({g[0]['figure']})"), "figure": g[0]["figure"], "t": [g[0]["t"], g[-1]["t"]], "touches": len(g), "peak_impact_mm_s": peak(g)}
                                   for gs in groups.values() for g in gs],
                   "peak_board_impact_mm_s": wall_peak("boards"), "peak_post_impact_mm_s": wall_peak("goal_post"), "peak_cage_impact_mm_s": wall_peak("goal_cage"),
                   "figure_violations": f_bad, "wall_violations": w_bad, "passed": not f_bad and not w_bad}
    slide_check["per_contact"].sort(key=lambda c: c["t"][0])

    # ---- contact episodes (one obstacle, gaps up to 60 ms merged); the resting touch before the first move is dropped
    eps = []
    for c in sorted(iv, key=lambda c: c["t0"]):
        pr = next((e for e in reversed(eps) if e["obstacle"] == c["obstacle"]), None)
        if pr and c["t0"] - pr["t1"] <= GROUP_GAP_S:
            pr["t1"] = max(pr["t1"], c["t1"])
        else:
            eps.append(dict(c))
    first_imp = imp[0]["t"] if imp else t1
    eps = [e for e in eps if not (e["t1"] < first_imp and e["obstacle"].split(":")[0] == spec["puck"]["start"].get("against"))]
    seq = [e["obstacle"] for e in eps]
    seq_dedup = [s for i, s in enumerate(seq) if i == 0 or s != seq[i - 1]]

    # ---- the move file's expectations
    exp = spec.get("expect", {})
    expectations = []
    if "goal" in exp:
        expectations.append({"what": "goal", "expected": exp["goal"], "got": entered, "passed": entered == exp["goal"]})
    if "goal_y_mm" in exp and goal_i is not None:
        lo, hi = exp["goal_y_mm"]; y = round(float(P[goal_i, 1]), 2)
        expectations.append({"what": "goal_y_mm", "expected": exp["goal_y_mm"], "got": y, "passed": lo <= y <= hi})
    if "contact_sequence" in exp:
        expectations.append({"what": "contact_sequence", "expected": exp["contact_sequence"], "got": seq_dedup, "passed": seq_dedup == exp["contact_sequence"]})
    for c, g in named:
        lim = c.get("max_peak_impact_mm_s")
        if lim is not None:
            expectations.append({"what": f"contact.{c['id']} peak impact", "expected": f"<= {lim}", "got": peak(g), "passed": peak(g) <= lim})
        if c.get("min_touches") is not None:
            expectations.append({"what": f"contact.{c['id']} touches (a push, not a strike)", "expected": f">= {c['min_touches']}", "got": len(g), "passed": len(g) >= c["min_touches"]})

    passed = (not vint and slide_check["passed"] and not unexplained and not problems and all(x["passed"] for x in expectations))
    trace_id = spec["trace_id"]
    geo = W.G["geometry_version"]
    asset_refs = {k: sha(REPO / p) for k, p in MANIFEST["asset_files"].items()}
    asset_refs.update(skater_scale_k=W.FOOT["scale_mm_per_mold_unit"]["skater"], goalie_scale_k=W.FOOT["scale_mm_per_mold_unit"]["goalie"],
                      git_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip())
    fig_out = {}
    for pid in [*spec["figures"], *[p for p in W.ALL_FIGURES if p not in spec["figures"]]]:
        f = figs[pid]
        if isinstance(f, W.Figure):
            fig_out[pid] = {"player_id": pid, "team": f.team, "fixture_path_id": f.slot.id, "slot_length_mm": round(f.slot.length, 2), "status": spec["figures"][pid].get("status", "designed"),
                            "arc_keyframes": f.arcs, "theta_keyframes": f.thetas}
    fig_out["others"] = "static assembly pose (validation/16-assembly-poses.json), as the renderer shows them; included in the checks"
    trace = {
        "schema": "shot-trace/1", "trace_id": trace_id, "status": spec["status"], "shot": spec["name"], "geometry_version": geo, "asset_refs": asset_refs,
        "source": {"move_file": str(move_path.relative_to(REPO)), "move_file_sha256": sha(move_path), "overrides": list(sets), "kind": spec.get("kind", "designed"),
                   "text": spec.get("source_text"), "references": spec.get("references", []), "approved_reading": spec.get("approved_reading")},
        "engine": {"path": "scripts/shotlib", "contact_footprints": "data/figures/contact-footprints.json", "contact_footprints_sha256": sha(REPO / "data/figures/contact-footprints.json")},
        "time_base": {"t": "designed time (s); no recording" if spec.get("kind", "designed") == "designed" else spec.get("time_base", "source time (s)"), "window_s": [t0, t1]},
        "interpolation": {"arc_mm": "Fritsch-Carlson monotone cubic Hermite through arc_keyframes (held outside)", "theta_deg": "linear between theta_keyframes (held outside)",
                          "puck": "linear between puck.nodes (held outside)", "implementation": "src/model/trace.ts traceEvaluator (mirrors scripts/shotlib/world.py)"},
        "pose_convention": "docs/pose.md: pivot on the slot centreline at arc_mm; heading = team home (W 0, E 180 deg) + theta_deg; assume.fixture_axis_on_slot_centreline",
        "figures": fig_out,
        "puck": {"radius_mm": W.R_PUCK, "radius_status": "catalog_nominal", "thickness_mm": W.PUCK_T, "thickness_status": "assumed (preview)",
                 "ice_friction_deceleration_mm_s2": physics["ice_deceleration_mm_s2"], "ice_friction_status": physics["ice_deceleration_status"],
                 "restitution_figure": physics["restitution_figure"], "restitution_status": physics["restitution_figure_status"], "nodes": nodes, "phases": phases},
        "events": events,
        "limitations": spec.get("limitations", []),
    }
    samp = []
    for tq in np.round(np.arange(t0, t1 + 1e-9, 0.02), 4):
        s_ = {"t": float(tq)}
        for pid in moving:
            s_[pid] = {"arc_mm": round(figs[pid].arc(tq), 4), "theta_deg": round(figs[pid].theta(tq), 4)}
        s_["puck"] = [round(float(np.interp(tq, nt, nx)), 4), round(float(np.interp(tq, nt, ny)), 4)]
        samp.append(s_)
    trace["evaluation_samples"] = samp
    checks = {"trace_id": trace_id, "passed": passed, "sampling_s": W.DT, "max_puck_step_mm": round(max_step, 3), "penetration_tolerance_mm": W.PEN_TOL,
              "contact_rule": "CLAUDE.md 'Contact physics': the puck may touch figures, boards and goal but never overlap them (every 0.25 ms, whole trace, all 12 figures, boards, posts, cages; no phase exemptions)",
              "min_clearance_by_obstacle_and_phase": [{"obstacle": k[0], "phase": k[1], **v} for k, v in sorted(rows.items()) if v["min_clearance_mm"] < 30],
              "unexpected_penetrations": [{"obstacle": k[0], "phase": k[1], **v} for k, v in vint.items()], "approved_exceptions": [],
              "slide_check": slide_check, "unexplained_velocity_changes": unexplained[:20], "unexplained_count": len(unexplained),
              "contact_sequence": seq, "contact_sequence_merged": seq_dedup, "contact_episodes": [{"obstacle": e["obstacle"], "t": [round(e["t0"], 5), round(e["t1"], 5)]} for e in eps],
              "expectations": expectations, "problems": problems, "impulses": imp, "walls": walls,
              "goal_line": {"goal": entered, "crossing_y_mm": round(float(P[goal_i, 1]), 2) if goal_i is not None else None,
                            "inside_mouth_window_y_mm": W.GOALS[entered].mouth_window() if entered else None}}
    out_dir = REPO / "out/moves" / move_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "trace.json").write_text(json.dumps(trace, indent=1, ensure_ascii=False) + "\n")
    (out_dir / "checks.json").write_text(json.dumps(checks, indent=1, ensure_ascii=False) + "\n")
    sheet(spec, figs, order, nt, nx, ny, events, t0, t1, out_dir / "sheet.png")
    saved = []
    if spec.get("legacy"):  # an older script owns the saved trace: compare, never overwrite
        saved.append(equivalence(move_id, spec, trace, out_dir))
    elif passed and not scratch and not sets:
        (REPO / "data/traces").mkdir(exist_ok=True)
        (REPO / f"shots/{move_id}").mkdir(parents=True, exist_ok=True)
        (REPO / "validation/moves").mkdir(parents=True, exist_ok=True)
        for src, dst in ((out_dir / "trace.json", f"data/traces/{move_id}.trace.json"), (out_dir / "checks.json", f"shots/{move_id}/checks.json"),
                         (out_dir / "sheet.png", f"validation/moves/{move_id}-sheet.png")):
            (REPO / dst).write_bytes(src.read_bytes())
            saved.append(dst)
    report = {"move": move_id, "passed": passed, "saved": saved, "scratch": str(out_dir.relative_to(REPO)),
              "goal": checks["goal_line"], "contacts": [{k: e.get(k) for k in ("id", "t_estimate", "t_end", "part", "touches", "peak_impact_mm_s", "speed_after_mm_s", "direction_after_deg")} for e in events if e["id"].startswith("contact.")],
              "sequence": seq_dedup, "overlaps": checks["unexpected_penetrations"], "slide_passed": slide_check["passed"],
              "slide_violations": (f_bad + w_bad)[:5], "unexplained": len(unexplained), "failed_expectations": [x for x in expectations if not x["passed"]], "problems": problems}
    return report


def equivalence(move_id, spec, trace, out_dir):
    """Engine build of a ported move against the trace its own script saved: puck nodes and figure keyframes."""
    old = json.loads((REPO / spec["legacy"]["trace"]).read_text())
    a, b = old["puck"]["nodes"], trace["puck"]["nodes"]
    n = min(len(a), len(b))
    dp = max(max(abs(x["x_mm"] - y["x_mm"]), abs(x["y_mm"] - y["y_mm"])) for x, y in zip(a[:n], b[:n]))
    figs = {}
    for pid, f in old["figures"].items():
        if not isinstance(f, dict) or pid not in trace["figures"]:
            continue
        g = trace["figures"][pid]
        da = max(abs(x["arc_mm"] - y["arc_mm"]) + abs(x["t"] - y["t"]) for x, y in zip(f["arc_keyframes"], g["arc_keyframes"])) if len(f["arc_keyframes"]) == len(g["arc_keyframes"]) else None
        dt = max(abs(x["theta_deg"] - y["theta_deg"]) + abs(x["t"] - y["t"]) for x, y in zip(f["theta_keyframes"], g["theta_keyframes"])) if len(f["theta_keyframes"]) == len(g["theta_keyframes"]) else None
        figs[pid] = {"arc_keyframes": [len(f["arc_keyframes"]), len(g["arc_keyframes"])], "max_arc_diff": da, "theta_keyframes": [len(f["theta_keyframes"]), len(g["theta_keyframes"])], "max_theta_diff": dt}
    rep = {"move": move_id, "legacy_trace": spec["legacy"]["trace"], "legacy_script": spec["legacy"]["script"], "engine_trace": str((out_dir / "trace.json").relative_to(REPO)),
           "puck_nodes": [len(a), len(b)], "max_puck_node_diff_mm": round(dp, 6), "figures": figs,
           "identical_within_0_01_mm": len(a) == len(b) and dp <= 0.01 and all(v["max_arc_diff"] is not None and v["max_arc_diff"] <= 0.01 and v["max_theta_diff"] is not None and v["max_theta_diff"] <= 0.01 for v in figs.values())}
    dst = REPO / f"validation/moves/{move_id}-equivalence.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(rep, indent=1) + "\n")
    return str(dst.relative_to(REPO))


# ---------------------------------------------------------------- review sheet
FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
FS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)


def sheet(spec, figs, order, nt, nx, ny, events, t0, t1, path):
    """Top view at the start, at every named contact, at the goal and at the end: goal.E up, +y left; moving figures
    blue, others yellow (footprints), the puck black with its path in orange."""
    moving = [p for p, fs in spec["figures"].items() if "static" not in fs]
    pts = [np.array([x, y]) for x, y in zip(nx, ny)] + [figs[p].pose(t)[0] for p in moving for t in np.linspace(t0, t1, 20)]
    pts = np.array(pts)
    lo, hi = pts.min(0) - 70, pts.max(0) + 70
    W_, H_ = 560, 640
    S = min((W_ - 20) / (hi[1] - lo[1]), (H_ - 60) / (hi[0] - lo[0]))
    cy = (lo[1] + hi[1]) / 2
    P_ = lambda w: (W_ / 2 - (w[1] - cy) * S, H_ - 20 - (w[0] - lo[0]) * S)
    times = [("start", t0)] + [(e["id"].replace("contact.", ""), e["t_estimate"]) for e in events if e["id"].startswith("contact.")]
    times += [(e["id"], e["t_estimate"]) for e in events if e["id"] == "goal_entry"] + [("end", t1)]
    tiles = []
    for name, tq in times:
        im = Image.new("RGB", (W_, H_), "white"); d = ImageDraw.Draw(im)
        d.line([P_(c) for c in W.BOARD.exterior.coords], fill=(60, 60, 60), width=2)
        for g in W.GOALS.values():
            for po in g.posts:
                c = P_(po); d.ellipse([c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3], fill=(200, 0, 0))
            d.line([P_(c) for c in g.walls.coords], fill=(200, 0, 0), width=2)
        for pid in moving:
            sl = figs[pid].slot; d.line([P_(sl.at(a)) for a in np.arange(0, sl.length, 3)], fill=(150, 150, 150), width=4)
        for f in order:
            poly = W.world_polygon(f, tq)
            for g in ([poly] if poly.geom_type == "Polygon" else list(poly.geoms)):
                d.polygon([P_(c) for c in g.exterior.coords], fill=(150, 190, 255) if f.pid in moving else (255, 225, 120), outline=(30, 30, 30))
        trail = [P_((np.interp(x, nt, nx), np.interp(x, nt, ny))) for x in np.arange(t0, tq, 0.004)]
        if len(trail) > 1:
            d.line(trail, fill=(255, 150, 0), width=2)
        p = (np.interp(tq, nt, nx), np.interp(tq, nt, ny)); c = P_(p)
        d.ellipse([c[0] - W.R_PUCK * S, c[1] - W.R_PUCK * S, c[0] + W.R_PUCK * S, c[1] + W.R_PUCK * S], fill=(0, 0, 0))
        clr = min(W.clearance(f, tq, np.array(p)) for f in order)
        d.text((8, 6), f"{name}  t={tq:.4f} s", fill=(0, 0, 0), font=FB)
        d.text((8, 30), f"min clearance {clr:+.2f} mm", fill=(0, 120, 0) if clr >= -W.PEN_TOL else (200, 0, 0), font=FS)
        tiles.append(im)
    cols = 3
    rows_ = (len(tiles) + cols - 1) // cols
    out = Image.new("RGB", (W_ * cols, H_ * rows_ + 40), "white")
    for i, im in enumerate(tiles):
        out.paste(im, ((i % cols) * W_, 40 + (i // cols) * H_))
    ImageDraw.Draw(out).text((10, 8), f"{spec['trace_id']} ({spec['status']}, {spec.get('kind', 'designed')}) - top view, goal.E up, +y left; moving figures blue; puck path orange",
                             fill=(0, 0, 0), font=FB)
    out.save(path)
