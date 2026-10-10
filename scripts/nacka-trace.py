"""Näcka: one contact-checked motion trace of the centre move described by the Norwegian Table Hockey Association
(references/combinations/puck-no-nacka.html, trick-nacka.png). No video exists: the motion is DESIGNED from the
description and illustration, with the set-up and physical rates of the measured spjass (trace.spjass.v1).

    /root/venvs/blender/bin/python scripts/nacka-trace.py

Inputs: shots/nacka/inputs.json, data/traces/spjass.trace.json and shots/spjass/checks.json (rest pose, ice friction),
plus the geometry and figure meshes used by scripts/spjass-trace.py (helpers imported from it).
Outputs: data/traces/nacka.trace.json, shots/nacka/checks.json, validation/nacka-trace.png.

Rules (no general simulator): the puck moves with its velocity, slowed by the ice friction fitted to the spjass slide;
where any figure (all 12), a goal post or the boards would overlap it, it is moved out to touching along the contact
normal and takes the resulting velocity (pushing contact); it stops against the back of the cage. Every change in its
motion therefore has a named cause. Checks: finite puck against every figure's low geometry, boards and posts, every
0.25 ms, overlap tolerance 0.1 mm, no exemptions.
"""
import importlib.util
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Point

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("spjass_trace", REPO / "scripts/spjass-trace.py")
sp = importlib.util.module_from_spec(_spec)
sys.argv = sys.argv[:1]
_spec.loader.exec_module(sp)  # helpers only (its main() is not run)

INP = json.loads((REPO / "shots/nacka/inputs.json").read_text())
if os.environ.get("NACKA_OVERRIDE"):  # parameter scans only (never for the saved trace)
    INP.update(json.loads(os.environ["NACKA_OVERRIDE"]))
SPJ = json.loads((REPO / "data/traces/spjass.trace.json").read_text())
SPJ_CHECKS = json.loads((REPO / "shots/spjass/checks.json").read_text())
OUT_TRACE = REPO / "data/traces/nacka.trace.json"
OUT_CHECKS = REPO / "shots/nacka/checks.json"
OUT_PNG = REPO / "validation/nacka-trace.png"
DT, EPS, PEN_TOL, R_PUCK = sp.DT, sp.EPS, sp.PEN_TOL, sp.R_PUCK
A_FRIC = SPJ_CHECKS["slide_fit"]["deceleration_mm_s2"]


def build():
    t0, t1 = INP["window_s"]
    rest_arc = SPJ_CHECKS["rest"]["arc_mm_used"]
    p_rest = np.array(SPJ_CHECKS["rest"]["puck_rest_mm"], float)
    th_rest = INP["heel_pass"]["theta_keyframes"][0][1]
    arcs = [{"t": t0, "arc_mm": rest_arc, "sigma_mm": None, "source": "rest arc of trace.spjass.v1 (puck within 0.1 mm of the heel)"}]
    for t, da in INP["shot"]["arc_keyframes"]:
        arcs.append({"t": t, "arc_mm": round(rest_arc + da, 3), "sigma_mm": None, "source": "ASSUMED step up the slot for the shot (inputs.json shot)"})
    thetas = [{"t": t0, "theta_deg": th_rest, "sigma_deg": None, "source": "rest heading of trace.spjass.v1"}]
    for t, th in INP["heel_pass"]["theta_keyframes"]:
        thetas.append({"t": t, "theta_deg": th, "sigma_deg": None, "source": "ASSUMED clockwise heel pass (inputs.json heel_pass)"})
    for t, th in INP["shot"]["theta_keyframes"]:
        thetas.append({"t": t, "theta_deg": th, "sigma_deg": None, "source": "ASSUMED counter-clockwise turn back for the shot (inputs.json shot)"})
    thetas = sorted({k["t"]: k for k in thetas}.values(), key=lambda k: k["t"])
    wc = sp.Figure("W-C", "W", "skater", arcs, thetas)
    # goalie on its slot at the chosen y
    eg_slot = sp.Slot("E-G")
    a_g = min(np.arange(0, eg_slot.length, 0.05), key=lambda a: abs(eg_slot.at(a)[1] - INP["goalie"]["y_mm"]))
    eg = sp.Static("E-G", "goalie", eg_slot.at(a_g), 180.0 + INP["goalie"]["theta_deg"])
    others = {pid: sp.Static(pid, "goalie" if f["position"] == "G" else "skater", f["pivot_mm"][:2], f["heading_deg"]) for pid, f in sp.ASM.items() if pid not in ("W-C", "E-G")}
    return t0, t1, p_rest, wc, eg, float(a_g), others


def run(t0, t1, p_rest, wc, eg, others):
    figs = [wc, eg, *others.values()]
    p, v = p_rest.copy(), np.zeros(2)
    T, P, V, touching = [], [], [], []
    in_net = False
    n = int(round((t1 - t0) / DT))
    for k in range(n + 1):
        t = t0 + k * DT
        hits = []
        if k:
            sp_ = float(np.linalg.norm(v))
            if sp_ > 0:
                v = v * max(0.0, sp_ - A_FRIC * DT) / sp_
            q = p + v * DT
            for _ in range(3):
                moved = False
                for f in figs:
                    q2, pushed = sp.push_out(f, t, q)
                    if pushed:
                        loc = Point(*sp.to_local(f, t, q2))
                        part = "stick/blade" if sp.STICK[f.kind].distance(loc) <= sp.LOW[f.kind].distance(loc) + 0.3 else "skate/body"
                        hits.append(f"{f.pid}:{part}"); q = q2; moved = True
                q2, pushed = sp.push_posts(q)
                if pushed:
                    hits.append("goal_post"); q = q2; moved = True
                if not moved:
                    break
            if q[0] > sp.GX and abs(q[1] - sp.GY) < sp.HALF and q[0] >= sp.BACK_X:
                q = np.array([sp.BACK_X, q[1]])
                if not in_net:
                    hits.append("goal_net")
                in_net = True
            v = (q - p) / DT if hits else v
            if in_net:
                v = np.zeros(2)
            p = q
        T.append(t); P.append(p.copy()); V.append(v.copy()); touching.append(tuple(sorted(set(hits))))
    return np.array(T), np.array(P), np.array(V), touching


def contacts_of(T, touching):
    iv = []
    for t, hs in zip(T, touching):
        for h in hs:
            if iv and iv[-1]["obstacle"] == h and t - iv[-1]["t1"] <= 2 * DT + 1e-9:
                iv[-1]["t1"] = float(t)
            else:
                iv.append({"obstacle": h, "t0": float(t), "t1": float(t)})
    return iv


def summary(T, P, V, touching):
    iv = contacts_of(T, touching)
    i_goal = int(np.argmax(P[:, 0] >= sp.GX)) if (P[:, 0] >= sp.GX).any() else None
    out = {"contacts": [(c["obstacle"], round(c["t0"], 4), round(c["t1"], 4)) for c in iv],
           "goal_y": round(float(P[i_goal, 1]), 2) if i_goal else None, "t_goal": round(float(T[i_goal]), 4) if i_goal else None}
    for c in iv:
        i = int(np.searchsorted(T, c["t1"] + 4 * DT))
        if i < len(V):
            c["v_after"] = V[i]
    w = [c for c in iv if c["obstacle"].startswith("W-C")]
    if w:
        out["first_wc_contact_v"] = [round(float(np.linalg.norm(w[0]["v_after"])), 1), round(math.degrees(math.atan2(w[0]["v_after"][1], w[0]["v_after"][0])), 1)]
        out["last_wc_contact_v"] = [round(float(np.linalg.norm(w[-1]["v_after"])), 1), round(math.degrees(math.atan2(w[-1]["v_after"][1], w[-1]["v_after"][0])), 1)]
    return out, iv


def local_contact(f, t, p):
    q = Point(*sp.to_local(f, t, p))
    nb = sp.LOW[f.kind].boundary.interpolate(sp.LOW[f.kind].boundary.project(q))
    n = sp.rot(f.pose(t)[1]) @ (np.array(q.coords[0]) - np.array(nb.coords[0]))
    return [round(float(x), 2) for x in nb.coords[0]], round(math.degrees(math.atan2(n[1], n[0])), 2)


def main():
    t0, t1, p_rest, wc, eg, a_g, others = build()
    T, P, V, touching = run(t0, t1, p_rest, wc, eg, others)
    s, iv = summary(T, P, V, touching)
    heel = [c for c in iv if c["obstacle"] == "W-C:skate/body"]
    blade = [c for c in iv if c["obstacle"] == "W-C:stick/blade"]
    net = [c for c in iv if c["obstacle"] == "goal_net"]
    assert heel and blade and net, f"unexpected contacts {s['contacts']}"
    t_h0, t_h1, t_b0, t_b1, t_net = heel[0]["t0"], heel[-1]["t1"], blade[0]["t0"], blade[-1]["t1"], net[0]["t0"]
    at = lambda tq: np.array([np.interp(tq, T, P[:, 0]), np.interp(tq, T, P[:, 1])])
    vel = lambda tq: V[min(int(np.searchsorted(T, tq)), len(V) - 1)]
    loc_h, n_h = local_contact(wc, t_h0, at(t_h0))
    loc_b, n_b = local_contact(wc, t_b0, at(t_b0))
    v_h, v_b = vel(t_h1 + 4 * DT), vel(t_b1 + 4 * DT)
    i_goal = int(np.argmax(P[:, 0] >= sp.GX))
    y_goal, t_goal = float(P[i_goal, 1]), float(T[i_goal])
    # nodes and phases
    nodes = []
    for k in range(0, len(T), sp.NODE_EVERY):
        t = float(T[k])
        ph = ("rest_at_heel" if t < t_h0 else "heel_pass" if t <= t_h1 else "slide" if t < t_b0 else "shot_blade" if t <= t_b1
              else "shot_free" if t < t_net else "in_goal")
        nodes.append({"t": round(t, 5), "x_mm": round(float(P[k, 0]), 4), "y_mm": round(float(P[k, 1]), 4), "phase": ph})
    phases = []
    for n_ in nodes:
        if not phases or phases[-1]["id"] != n_["phase"]:
            if phases:
                phases[-1]["t"][1] = n_["t"]
            phases.append({"id": n_["phase"], "t": [n_["t"], None]})
    # checks on the saved trace (linear between nodes), every DT
    nt = np.array([n_["t"] for n_ in nodes]); nx = np.array([n_["x_mm"] for n_ in nodes]); ny = np.array([n_["y_mm"] for n_ in nodes])
    movers = [wc, eg, *others.values()]
    rows, viol, prev, max_step = {}, [], None, 0.0
    for tq in np.arange(t0, t1 + 1e-9, DT):
        p = np.array([np.interp(tq, nt, nx), np.interp(tq, nt, ny)])
        ph = nodes[min(max(int(np.searchsorted(nt, tq, side="right") - 1), 0), len(nodes) - 1)]["phase"]
        if prev is not None:
            max_step = max(max_step, float(np.linalg.norm(p - prev)))
        prev = p
        cs = [(f.pid, sp.clearance(f, tq, p)) for f in movers] + [("boards", sp.BOARD.exterior.distance(Point(*p)) - R_PUCK)]
        cs += [(f"goal_post_{'pos' if k == 0 else 'neg'}_y", float(np.linalg.norm(p - po)) - R_PUCK - sp.POST_R) for k, po in enumerate(sp.POSTS)]
        for ob, c in cs:
            r = rows.setdefault((ob, ph), {"min_clearance_mm": 1e9, "t_at_min": None})
            if c < r["min_clearance_mm"]:
                r.update(min_clearance_mm=round(float(c), 3), t_at_min=round(float(tq), 5))
            if c < -PEN_TOL:
                viol.append((ob, ph, round(float(tq), 5), round(float(c), 3)))
    vint = {}
    for ob, ph, tq, c in viol:
        a = vint.setdefault((ob, ph), {"t0": tq, "t1": tq, "worst_mm": c}); a["t1"] = tq; a["worst_mm"] = min(a["worst_mm"], c)
    unexplained = [round(float(T[i]), 5) for i in range(2, len(T)) if not touching[i] and float(np.linalg.norm(V[i] - V[i - 1])) > A_FRIC * DT + 1e-6]
    deg = lambda v: round(math.degrees(math.atan2(v[1], v[0])), 2)
    events = [
        {"id": "turn.onset", "t_estimate": INP["heel_pass"]["theta_keyframes"][0][0], "status": "assumed (the spjass onset)"},
        {"id": "contact.heel_pass", "t_estimate": round(t_h0, 5), "t_end": round(t_h1, 5), "part": "W-C:skate/body (back of the right skate)",
         "contact_point_local_mm": loc_h, "model_contact_normal_deg": n_h, "speed_mm_s": round(float(np.linalg.norm(v_h)), 1), "direction_deg": deg(v_h), "status": "derived (pushing contact)"},
        {"id": "turn_back.onset", "t_estimate": INP["shot"]["theta_keyframes"][0][0], "status": "assumed"},
        {"id": "contact.shot", "t_estimate": round(t_b0, 5), "t_end": round(t_b1, 5), "part": "W-C:stick/blade", "contact_point_local_mm": loc_b,
         "model_contact_normal_deg": n_b, "speed_mm_s": round(float(np.linalg.norm(v_b)), 1), "direction_deg": deg(v_b),
         "heading_at_contact_deg": round(wc.theta(t_b0), 2), "arc_at_contact_mm": round(wc.arc(t_b0), 2), "status": "derived (pushing contact)"},
        {"id": "goal_entry", "t_estimate": round(t_goal, 5), "goal_line_y_mm": round(y_goal, 2), "status": "derived"},
        {"id": "goal_net", "t_estimate": round(t_net, 5), "status": "rule: the puck stops against the back of the preview cage"},
    ]
    pass_vec = at(t_b0) - p_rest
    trace = {
        "schema": "shot-trace/1", "trace_id": "trace.nacka.v1", "status": INP["status"], "shot": "Näcka (centre move, NTHF)",
        "geometry_version": sp.G["geometry_version"],
        "asset_refs": {**SPJ["asset_refs"], "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()},
        "source": {"description": "references/combinations/puck-no-nacka.html", "illustration": "references/combinations/trick-nacka.png", "inputs": "shots/nacka/inputs.json",
                   "borrowed": "data/traces/spjass.trace.json (rest pose), shots/spjass/checks.json (ice friction)", "text": INP["source_text"]},
        "time_base": {"t": "source time in seconds on the spjass time base (no recording of Näcka exists)", "window_s": [t0, t1]},
        "interpolation": SPJ["interpolation"], "pose_convention": SPJ["pose_convention"],
        "figures": {
            "W-C": {"player_id": "W-C", "team": "W", "fixture_path_id": wc.slot.id, "slot_length_mm": round(wc.slot.length, 2), "status": "moving: Näcka (designed)",
                    "arc_keyframes": wc.arcs, "theta_keyframes": wc.thetas},
            "E-G": {"player_id": "E-G", "team": "E", "fixture_path_id": sp.Slot("E-G").id, "slot_length_mm": round(sp.Slot("E-G").length, 2), "status": "static (assumed pose, inputs.json goalie)",
                    "arc_keyframes": [{"t": t0, "arc_mm": round(a_g, 2), "sigma_mm": None, "source": "assumed: inputs.json goalie"}],
                    "theta_keyframes": [{"t": t0, "theta_deg": INP["goalie"]["theta_deg"], "sigma_deg": None, "source": "assumed: inputs.json goalie"}]},
            "others": "static assembly pose (validation/16-assembly-poses.json), as the renderer shows them; included in the checks"},
        "puck": {"radius_mm": R_PUCK, "radius_status": "catalog_nominal", "thickness_mm": sp.PUCK_T, "thickness_status": "assumed (preview)",
                 "ice_friction_deceleration_mm_s2": A_FRIC, "ice_friction_status": "borrowed from the spjass slide fit", "nodes": nodes, "phases": phases},
        "events": events,
        "comparison_with_illustration": {"pass_mm": [round(float(x), 1) for x in pass_vec], "pass_length_mm": round(float(np.linalg.norm(pass_vec)), 1),
                                         "pass_direction_deg": deg(pass_vec), "illustration_pass_length_mm": INP["illustration_readings"]["pass_length_mm"],
                                         "illustration_pass_direction_deg": INP["illustration_readings"]["pass_direction_deg"],
                                         "shot_direction_deg": deg(v_b), "illustration_shot_direction_deg": INP["illustration_readings"]["shot_direction_deg"]},
        "limitations": [
            "No recording of Näcka: the whole motion is DESIGNED from the NTHF description and illustration; timing and rates are borrowed from the measured spjass (same set-up).",
            "The heel pass direction follows from the AI-modelled skate (about -44 deg); the NTHF illustration (schematic) shows about -69 deg, so the puck ends further forward and W-C steps 43 mm up its slot to strike it square.",
            "Goalie pose assumed (shifted toward the left post); with the assembly pose the right corner is closed.",
            "Blade, skate and stick geometry are the AI-modelled mold at the assumed preview scale; puck thickness and goal size are preview values.",
        ],
    }
    samp = []
    for tq in np.round(np.arange(t0, t1 + 1e-9, 0.02), 4):
        p = [float(np.interp(tq, nt, nx)), float(np.interp(tq, nt, ny))]
        samp.append({"t": float(tq), "W-C": {"arc_mm": round(wc.arc(tq), 4), "theta_deg": round(wc.theta(tq), 4)}, "puck": [round(p[0], 4), round(p[1], 4)]})
    trace["evaluation_samples"] = samp
    OUT_TRACE.write_text(json.dumps(trace, indent=1, ensure_ascii=False) + "\n")
    checks = {"trace_id": trace["trace_id"], "sampling_s": DT, "max_puck_step_mm": round(max_step, 3), "penetration_tolerance_mm": PEN_TOL,
              "contact_rule": "CLAUDE.md 'Contact physics': the puck may touch figures, boards and goal but never overlap them (every 0.25 ms, whole trace, all 12 figures, no phase exemptions)",
              "min_clearance_by_obstacle_and_phase": [{"obstacle": k[0], "phase": k[1], **v} for k, v in sorted(rows.items()) if v["min_clearance_mm"] < 30],
              "unexpected_penetrations": [{"obstacle": k[0], "phase": k[1], **v} for k, v in vint.items()], "approved_exceptions": [],
              "contacts": [{"obstacle": c["obstacle"], "t0": round(c["t0"], 5), "t1": round(c["t1"], 5)} for c in iv],
              "unexplained_velocity_changes": unexplained[:20], "unexplained_count": len(unexplained),
              "goal_line": {"x_mm": sp.GX, "crossing_y_mm": round(y_goal, 2), "inside_mouth_window_y_mm": [round(sp.GY - sp.HALF + sp.POST_R + R_PUCK, 1), round(sp.GY + sp.HALF - sp.POST_R - R_PUCK, 1)]},
              "comparison_with_illustration": trace["comparison_with_illustration"]}
    OUT_CHECKS.write_text(json.dumps(checks, indent=1, ensure_ascii=False) + "\n")
    sheet(wc, movers, nt, nx, ny, nodes, events, t0)
    print(json.dumps({"events": events, "unexpected": checks["unexpected_penetrations"], "unexplained": len(unexplained), "goal": checks["goal_line"],
                      "comparison": trace["comparison_with_illustration"], "close": [r for r in checks["min_clearance_by_obstacle_and_phase"] if r["min_clearance_mm"] < 2]}, indent=1, ensure_ascii=False))


def sheet(wc, movers, nt, nx, ny, nodes, events, t0):
    S, W_, H_ = 2.3, 560, 640
    P_ = lambda w: (W_ / 2 - w[1] * S, H_ - 30 - (w[0] - 115) * S)
    ev = {e["id"]: e["t_estimate"] for e in events}
    times = [("rest", 4.0), ("heel pass", ev["contact.heel_pass"]), ("slide", (ev["contact.heel_pass"] + ev["contact.shot"]) / 2), ("shot", ev["contact.shot"]),
             ("goal", ev["goal_entry"]), ("net", ev["goal_net"])]
    tiles = []
    for name, tq in times:
        im = Image.new("RGB", (W_, H_), "white"); d = ImageDraw.Draw(im)
        for po in sp.POSTS:
            c = P_(po); d.ellipse([c[0] - 4, c[1] - 4, c[0] + 4, c[1] + 4], fill=(200, 0, 0))
        d.line([P_((sp.GX, sp.GY - sp.HALF)), P_((sp.GX, sp.GY + sp.HALF))], fill=(200, 0, 0), width=2)
        sl = sp.Slot("W-C"); d.line([P_(sl.at(a)) for a in np.arange(150, sl.length, 2)], fill=(60, 60, 60), width=6)
        for f in movers:
            poly = sp.world_polygon(f, tq)
            for g in ([poly] if poly.geom_type == "Polygon" else list(poly.geoms)):
                pts_ = [P_(c) for c in g.exterior.coords]
                if min(p_[1] for p_ in pts_) < H_ and max(p_[1] for p_ in pts_) > 0:
                    d.polygon(pts_, fill=(150, 190, 255) if f.pid == "W-C" else (255, 225, 120), outline=(30, 30, 30))
        trail = [P_((np.interp(x, nt, nx), np.interp(x, nt, ny))) for x in np.arange(max(t0, tq - 0.25), tq, 0.002)]
        if len(trail) > 1:
            d.line(trail, fill=(255, 150, 0), width=2)
        p = (np.interp(tq, nt, nx), np.interp(tq, nt, ny)); c = P_(p)
        d.ellipse([c[0] - R_PUCK * S, c[1] - R_PUCK * S, c[0] + R_PUCK * S, c[1] + R_PUCK * S], outline=(0, 0, 0), width=2)
        clr = min(sp.clearance(f, tq, np.array(p)) for f in movers)
        d.text((8, 6), f"{name}  t={tq:.4f} s", fill=(0, 0, 0), font=sp.FB)
        d.text((8, 30), f"W-C arc {wc.arc(tq):.1f} mm  theta {wc.theta(tq):.1f} deg   min clearance {clr:+.2f} mm", fill=(0, 120, 0) if clr >= -PEN_TOL else (200, 0, 0), font=sp.FS)
        tiles.append(im)
    out = Image.new("RGB", (W_ * 3, H_ * 2 + 40), "white")
    for i, im in enumerate(tiles):
        out.paste(im, ((i % 3) * W_, 40 + (i // 3) * H_))
    ImageDraw.Draw(out).text((10, 8), "trace.nacka.v1 (designed) - top view (goal.E up, +y left): W-C blue, others yellow (low geometry), puck black, recent path orange", fill=(0, 0, 0), font=sp.FB)
    out.save(OUT_PNG)


if __name__ == "__main__":
    if os.environ.get("NACKA_OVERRIDE"):
        t0, t1, p_rest, wc, eg, a_g, others = build()
        T, P, V, touching = run(t0, t1, p_rest, wc, eg, others)
        s, iv = summary(T, P, V, touching)
        for tq in (4.24, 4.30, t1):
            i = min(int(np.searchsorted(T, tq)), len(T) - 1)
            s[f"puck_at_{tq}"] = [round(float(x), 1) for x in P[i]] + [round(float(np.linalg.norm(V[i])), 0)]
        print(json.dumps(s))
    else:
        main()
