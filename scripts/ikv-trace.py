"""Invers Kryssar med Velodrom: one contact-checked motion trace of the right-wing combination described by the NTHF
(references/combinations/puck-no-invers-kryssar-med-velodrom.html), following the reading the user approved on
2026-10-06 (validation/ikv-sketch.png). No recording exists: the figure motions are DESIGNED; the puck follows from them.

    /root/venvs/blender/bin/python scripts/ikv-trace.py

Inputs: shots/invers-kryssar-velodrom/inputs.json (figure motions, contact parameters), the geometry and figure meshes
(helpers from scripts/spjass-trace.py), the spjass ice friction. Outputs: data/traces/invers-kryssar-velodrom.trace.json,
shots/invers-kryssar-velodrom/checks.json, validation/ikv-trace.png.

Puck rules (no general simulator; every change in its motion has a named cause), every 0.25 ms:
- ice friction: constant deceleration (spjass slide fit);
- figure contact: where a figure's low geometry (all 12 figures) would overlap the puck, the puck is moved out to
  touching along the contact normal; if it approaches the figure's surface there (relative normal velocity < 0, the
  figure's own surface velocity from its pose change), it takes a collision impulse along the normal with restitution e
  (frictionless: the tangential velocity is kept);
- boards and goal posts: moved out to touching, the normal velocity removed (inelastic, the puck slides along them);
- goal net: the puck stops against the back of the cage.
Checks: finite puck against every figure, the boards and the posts, every 0.25 ms, overlap tolerance 0.1 mm.
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
_argv = sys.argv[:]
sys.argv = sys.argv[:1]
_spec.loader.exec_module(sp)  # helpers only
sys.argv = _argv

INP = json.loads((REPO / "shots/invers-kryssar-velodrom/inputs.json").read_text())
if os.environ.get("IKV_OVERRIDE"):  # parameter scans only (never for the saved trace): deep merge
    def _merge(a, b):
        for k, v in b.items():
            a[k] = _merge(dict(a.get(k, {})), v) if isinstance(v, dict) else v
        return a
    INP = _merge(INP, json.loads(os.environ["IKV_OVERRIDE"]))
SPJ_CHECKS = json.loads((REPO / "shots/spjass/checks.json").read_text())
SPJ = json.loads((REPO / "data/traces/spjass.trace.json").read_text())
OUT_TRACE = REPO / "data/traces/invers-kryssar-velodrom.trace.json"
OUT_CHECKS = REPO / "shots/invers-kryssar-velodrom/checks.json"
OUT_PNG = REPO / "validation/ikv-trace.png"
DT, EPS, PEN_TOL, R_PUCK = sp.DT, sp.EPS, sp.PEN_TOL, sp.R_PUCK
A_FRIC = SPJ_CHECKS["slide_fit"]["deceleration_mm_s2"]
INSET = sp.BOARD.buffer(-R_PUCK)
BLADE_MID = np.array([2.8, 33.1])
from shapely.geometry import LineString as _LS
from shapely.ops import unary_union as _union
# preview cage seen from outside: the two side nets and the back net (the mouth between the posts stays open; the posts
# are their own obstacles); depth and width from the hardware report
_CAGE_WALLS = [_LS([(sp.GX, sp.GY - sp.HALF), (sp.GX + sp.DEPTH, sp.GY - sp.HALF), (sp.GX + sp.DEPTH, sp.GY + sp.HALF), (sp.GX, sp.GY + sp.HALF)])]
CAGE_OUT = _union([w.buffer(R_PUCK, 32) for w in _CAGE_WALLS])


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def theta_track(segs, t0):
    """Theta keyframes: holds and smootherstep sweeps (sampled every 2 ms). segs: [[t_start, duration, theta_from, theta_to], ...]."""
    ks = [(t0, segs[0][2])]
    for ts, d, a, b in segs:
        ks.append((ts, a))
        n = max(2, int(round(d / 0.002)))
        for k in range(1, n + 1):
            ks.append((ts + d * k / n, a + (b - a) * smooth(k / n)))
    out = {}
    for t, th in ks:
        out[round(t, 5)] = th
    return [{"t": t, "theta_deg": round(th, 4), "sigma_deg": None, "source": "designed"} for t, th in sorted(out.items())]


def build():
    t0, t1 = INP["window_s"]
    rw_, lw_, wc_ = INP["right_wing"], INP["left_wing"], INP["centre"]
    rw_arcs = [{"t": t0, "arc_mm": rw_["arc_start_mm"], "sigma_mm": None, "source": "designed: start position"},
               {"t": rw_["slide"][0], "arc_mm": rw_["arc_start_mm"], "sigma_mm": None, "source": "designed: slide starts"},
               {"t": rw_["slide"][1], "arc_mm": rw_["arc_catch_mm"], "sigma_mm": None, "source": "designed: at the catch position"}]
    rw = sp.Figure("W-RW", "W", "skater", rw_arcs, theta_track(rw_["theta_segments"], t0))
    lw = sp.Figure("W-LW", "W", "skater", [{"t": t0, "arc_mm": lw_["arc_mm"], "sigma_mm": None, "source": "designed"}], theta_track(lw_["theta_segments"], t0))
    wc = sp.Static("W-C", "skater", sp.Slot("W-C").at(wc_["arc_mm"]), sp.HOME["W"] + wc_["theta_deg"])
    others = {pid: sp.Static(pid, "goalie" if f["position"] == "G" else "skater", f["pivot_mm"][:2], f["heading_deg"]) for pid, f in sp.ASM.items() if pid not in ("W-RW", "W-LW", "W-C", "E-G")}
    eg_slot = sp.Slot("E-G")
    a_g = min(np.arange(0, eg_slot.length, 0.05), key=lambda a: abs(eg_slot.at(a)[1] - INP["goalie"]["y_mm"]))
    others["E-G"] = sp.Static("E-G", "goalie", eg_slot.at(a_g), 180.0 + INP["goalie"]["theta_deg"])
    others["E-G"].arc_mm = float(a_g)
    # puck at rest touching the front of the right wing's blade at the contact heading of the pass sweep
    piv = rw.slot.at(rw_["arc_start_mm"]); h = sp.HOME["W"] + rw_["puck_rest_heading_deg"]
    p_rest = piv + sp.rot(h) @ (BLADE_MID + np.array([R_PUCK + EPS + 1.6, 0.0]))
    return t0, t1, p_rest, rw, lw, wc, others


def part_of(f, t, p):
    q = Point(*sp.to_local(f, t, p))
    return "stick/blade" if sp.STICK[f.kind].distance(q) <= sp.LOW[f.kind].distance(q) + 0.3 else "skate/body"


def run(t0, t1, p_rest, figs):
    e = INP["contact"]["restitution_figure"]
    p, v = p_rest.copy(), np.zeros(2)
    T, P, V, touching, impulses = [], [], [], [], []
    in_net = entered = False
    n = int(round((t1 - t0) / DT))
    for k in range(n + 1):
        t = t0 + k * DT
        hits = []
        if k and not in_net:
            s = float(np.linalg.norm(v))
            if s > 0:
                v = v * max(0.0, s - A_FRIC * DT) / s
            q = p + v * DT
            for _ in range(3):
                moved = False
                for f in figs:
                    loc = sp.to_local(f, t, q)
                    if not sp.LOW_OUT[f.kind].contains(Point(*loc)):
                        continue
                    best = min((r.interpolate(r.project(Point(*loc))) for r in sp.RINGS_OUT[f.kind]), key=lambda z: z.distance(Point(*loc)))
                    r_loc = np.array(best.coords[0])
                    q_new = sp.to_world(f, t, r_loc)
                    nrm = q_new - q
                    nn = float(np.linalg.norm(nrm))
                    nrm = nrm / nn if nn > 1e-12 else (q_new - sp.to_world(f, t, np.zeros(2))) / max(1e-9, float(np.linalg.norm(q_new - sp.to_world(f, t, np.zeros(2)))))
                    # surface velocity of the figure at the contact (pose change over one step)
                    v_fig = (sp.to_world(f, t, r_loc) - sp.to_world(f, t - DT, r_loc)) / DT
                    vn = float((v - v_fig) @ nrm)
                    if vn < 0:
                        v = v - (1 + e) * vn * nrm
                        impulses.append({"t": round(t, 5), "figure": f.pid, "part": part_of(f, t, q_new), "dv": round(float(-(1 + e) * vn), 1)})
                    q = q_new
                    hits.append(f"{f.pid}:{part_of(f, t, q)}")
                    moved = True
                for po in sp.POSTS:
                    dd = q - po
                    nd = float(np.linalg.norm(dd))
                    if nd < R_PUCK + sp.POST_R:
                        nrm = dd / nd
                        q = po + nrm * (R_PUCK + sp.POST_R + EPS)
                        vn = float(v @ nrm)
                        if vn < 0:
                            v = v - vn * nrm
                        hits.append("goal_post"); moved = True
                if not INSET.contains(Point(*q)):
                    b = INSET.exterior
                    qq = np.array(b.interpolate(b.project(Point(*q))).coords[0])
                    nrm = qq - q; nd = float(np.linalg.norm(nrm))
                    if nd > 1e-12:
                        nrm = nrm / nd
                        vn = float(v @ nrm)
                        if vn < 0:
                            v = v - vn * nrm
                    q = qq
                    hits.append("boards"); moved = True
                if not moved:
                    break
            # goal: enterable only through the mouth (crossing the goal line between the posts); from outside, the
            # cage (sides and back) is a wall the puck slides along; inside, the back net stops it
            if not entered and p[0] < sp.GX <= q[0] and abs(q[1] - sp.GY) < sp.HALF:
                entered = True
            if entered:
                lim = sp.HALF - R_PUCK  # side nets from inside
                if abs(q[1] - sp.GY) > lim:
                    q = np.array([q[0], sp.GY + math.copysign(lim, q[1] - sp.GY)]); v = np.array([v[0], 0.0])
                    hits.append("goal_net")
                if q[0] >= sp.BACK_X:
                    q = np.array([sp.BACK_X, q[1]]); v = np.zeros(2); in_net = True
                    hits.append("goal_net")
            else:
                cq = (CAGE_OUT.exterior if CAGE_OUT.geom_type == "Polygon" else max(CAGE_OUT.geoms, key=lambda g_: g_.area).exterior) if CAGE_OUT.contains(Point(*q)) and not (p[0] < sp.GX and abs(q[1] - sp.GY) < sp.HALF - R_PUCK) else None
                if cq is not None:
                    qq = np.array(cq.interpolate(cq.project(Point(*q))).coords[0])
                    nrm = qq - q; nd = float(np.linalg.norm(nrm))
                    if nd > 1e-12:
                        nrm = nrm / nd
                        vn = float(v @ nrm)
                        if vn < 0:
                            v = v - vn * nrm
                    q = qq
                    hits.append("goal_cage")
            p = q
        T.append(t); P.append(p.copy()); V.append(v.copy()); touching.append(tuple(sorted(set(hits))))
    return np.array(T), np.array(P), np.array(V), touching, impulses


def intervals(T, touching):
    iv = []
    for t, hs in zip(T, touching):
        for h in hs:
            if iv and iv[-1]["obstacle"] == h and t - iv[-1]["t1"] <= 4 * DT + 1e-9:
                iv[-1]["t1"] = float(t)
            elif not any(x["obstacle"] == h and t - x["t1"] <= 4 * DT + 1e-9 for x in iv[-3:]):
                iv.append({"obstacle": h, "t0": float(t), "t1": float(t)})
            else:
                for x in iv[-3:]:
                    if x["obstacle"] == h:
                        x["t1"] = float(t)
    return iv


def summary(T, P, V, touching):
    iv = intervals(T, touching)
    inm = (P[:, 0] >= sp.GX) & (np.abs(P[:, 1] - sp.GY) < sp.HALF) & (np.r_[True, P[:-1, 0] < sp.GX] | (P[:, 0] >= sp.GX))
    cross = [i for i in range(1, len(P)) if P[i - 1, 0] < sp.GX <= P[i, 0] and abs(P[i, 1] - sp.GY) < sp.HALF]
    i_goal = cross[0] if cross else None
    out = {"contacts": [(c["obstacle"], round(c["t0"], 4), round(c["t1"], 4)) for c in iv],
           "goal_y": round(float(P[i_goal, 1]), 2) if i_goal else None, "t_goal": round(float(T[i_goal]), 4) if i_goal else None}
    for name, tq in (("p_0.5", 0.5), ("p_0.8", 0.8), ("p_1.2", 1.2), ("p_1.6", 1.6), ("end", T[-1])):
        i = min(int(np.searchsorted(T, tq)), len(T) - 1)
        out[name] = [round(float(P[i, 0]), 1), round(float(P[i, 1]), 1), round(float(np.linalg.norm(V[i])), 0)]
    return out, iv


if __name__ == "__main__" and os.environ.get("IKV_OVERRIDE") is not None:
    t0, t1, p_rest, rw, lw, wc, others = build()
    T, P, V, touching, imp = run(t0, t1, p_rest, [rw, lw, wc, *others.values()])
    s, _ = summary(T, P, V, touching)
    if imp:
        i = min(int(np.searchsorted(T, imp[0]["t"] + 0.01)), len(T) - 1)
        s["after_first"] = [round(math.degrees(math.atan2(V[i, 1], V[i, 0])), 1), round(float(np.linalg.norm(V[i])), 0)]
    s["impulses"] = [(x["t"], x["figure"], x["part"], x["dv"]) for x in imp][:12]
    lw = [x for x in imp if x["figure"] == "W-LW"]
    if lw:
        i = min(int(np.searchsorted(T, lw[-1]["t"] + 0.006)), len(T) - 1)
        s["after_lw"] = [round(math.degrees(math.atan2(V[i, 1], V[i, 0])), 1), round(float(np.linalg.norm(V[i])), 0)]
    rw2 = [x for x in imp if x["figure"] == "W-RW" and x["t"] > 0.5]
    if rw2:
        i = min(int(np.searchsorted(T, rw2[-1]["t"] + 0.006)), len(T) - 1)
        s["after_rw"] = [round(math.degrees(math.atan2(V[i, 1], V[i, 0])), 1), round(float(np.linalg.norm(V[i])), 0), rw2[0]["t"]]
    print(json.dumps(s))
    raise SystemExit


def local_contact(f, t, p):
    q = Point(*sp.to_local(f, t, p))
    nb = sp.LOW[f.kind].boundary.interpolate(sp.LOW[f.kind].boundary.project(q))
    n = sp.rot(f.pose(t)[1]) @ (np.array(q.coords[0]) - np.array(nb.coords[0]))
    return [round(float(x), 2) for x in nb.coords[0]], round(math.degrees(math.atan2(n[1], n[0])), 2)


def main():
    t0, t1, p_rest, rw, lw, wc, others = build()
    figs = [rw, lw, wc, *others.values()]
    T, P, V, touching, imp = run(t0, t1, p_rest, figs)
    s, iv = summary(T, P, V, touching)
    deg = lambda v: round(math.degrees(math.atan2(v[1], v[0])), 2)
    vel = lambda tq: V[min(int(np.searchsorted(T, tq)), len(V) - 1)]
    at = lambda tq: np.array([np.interp(tq, T, P[:, 0]), np.interp(tq, T, P[:, 1])])
    rw_imp = [x for x in imp if x["figure"] == "W-RW"]
    lw_imp = [x for x in imp if x["figure"] == "W-LW"]
    pass_t = rw_imp[0]["t"]
    shot_imps = [x for x in rw_imp if x["t"] > 1.0]
    assert lw_imp and shot_imps, f"missing contacts: {s['contacts']}"
    lw_t0, lw_t1 = lw_imp[0]["t"], lw_imp[-1]["t"]
    sh_t0, sh_t1 = shot_imps[0]["t"], shot_imps[-1]["t"]
    boards = [c for c in iv if c["obstacle"] == "boards" and c["t0"] > lw_t1]
    net = [c for c in iv if c["obstacle"] == "goal_net"]
    assert net and s["goal_y"] is not None, "no goal"
    t_board0, t_board1 = boards[0]["t0"], boards[-1]["t1"]
    t_goal, t_net = s["t_goal"], net[0]["t0"]
    # phases
    def phase(t):
        if t < pass_t: return "rest_at_blade"
        if t <= pass_t + 0.004: return "pass_forehand"
        if t < lw_t0: return "cross_pass"
        if t <= lw_t1 + 0.004: return "lw_backhand"
        if t < t_board0: return "to_the_boards"
        if t <= t_board1: return "velodrome"
        if t < sh_t0: return "along_the_board"
        if t <= sh_t1 + 0.004: return "shot_backhand"
        if t < t_net: return "shot_free"
        return "in_goal"
    nodes = []
    for k in range(0, len(T), sp.NODE_EVERY):
        t = float(T[k])
        nodes.append({"t": round(t, 5), "x_mm": round(float(P[k, 0]), 4), "y_mm": round(float(P[k, 1]), 4), "phase": phase(t)})
    phases = []
    for n_ in nodes:
        if not phases or phases[-1]["id"] != n_["phase"]:
            if phases: phases[-1]["t"][1] = n_["t"]
            phases.append({"id": n_["phase"], "t": [n_["t"], None]})
    # checks on the saved trace (linear between nodes), every DT
    nt = np.array([n_["t"] for n_ in nodes]); nx = np.array([n_["x_mm"] for n_ in nodes]); ny = np.array([n_["y_mm"] for n_ in nodes])
    rows, viol, prev, max_step = {}, [], None, 0.0
    entered = False
    for tq in np.arange(t0, t1 + 1e-9, DT):
        p = np.array([np.interp(tq, nt, nx), np.interp(tq, nt, ny)])
        ph = nodes[min(max(int(np.searchsorted(nt, tq, side="right") - 1), 0), len(nodes) - 1)]["phase"]
        if prev is not None:
            max_step = max(max_step, float(np.linalg.norm(p - prev)))
            if prev[0] < sp.GX <= p[0] and abs(p[1] - sp.GY) < sp.HALF:
                entered = True
        prev = p
        cs = [(f.pid, sp.clearance(f, tq, p)) for f in figs] + [("boards", sp.BOARD.exterior.distance(Point(*p)) - R_PUCK)]
        cs += [(f"goal_post_{'pos' if k == 0 else 'neg'}_y", float(np.linalg.norm(p - po)) - R_PUCK - sp.POST_R) for k, po in enumerate(sp.POSTS)]
        if not entered:
            cs.append(("goal_cage", float(_CAGE_WALLS[0].distance(Point(*p))) - R_PUCK))
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
    loc_p, n_p = local_contact(rw, pass_t, at(pass_t))
    loc_l, n_l = local_contact(lw, lw_t0, at(lw_t0))
    loc_s, n_s = local_contact(rw, sh_t0, at(sh_t0))
    v_p, v_l, v_s = vel(pass_t + 0.006), vel(lw_t1 + 0.006), vel(sh_t1 + 0.006)
    events = [
        {"id": "pass.release", "t_estimate": round(pass_t, 5), "part": "W-RW:stick/blade (front, forehand)", "contact_point_local_mm": loc_p, "model_contact_normal_deg": n_p,
         "speed_mm_s": round(float(np.linalg.norm(v_p)), 1), "direction_deg": deg(v_p), "status": "derived (collision with the sweeping blade)"},
        {"id": "contact.lw_pass", "t_estimate": round(lw_t0, 5), "t_end": round(lw_t1, 5), "part": "W-LW:stick/blade (back, backhand)", "contact_point_local_mm": loc_l,
         "model_contact_normal_deg": n_l, "speed_mm_s": round(float(np.linalg.norm(v_l)), 1), "direction_deg": deg(v_l), "status": "derived (collision with the sweeping blade)"},
        {"id": "velodrome.start", "t_estimate": round(t_board0, 5), "status": "derived: first board contact after the left wing's pass"},
        {"id": "velodrome.end", "t_estimate": round(t_board1, 5), "status": "derived: the puck leaves the curved boards onto the straight -y board"},
        {"id": "turn.onset", "t_estimate": INP["right_wing"]["theta_segments"][1][0], "status": "designed: the right wing starts down his slot and turns round"},
        {"id": "contact.shot", "t_estimate": round(sh_t0, 5), "t_end": round(sh_t1, 5), "part": "W-RW:stick/blade (back, backhand first-time shot)", "contact_point_local_mm": loc_s,
         "model_contact_normal_deg": n_s, "speed_mm_s": round(float(np.linalg.norm(v_s)), 1), "direction_deg": deg(v_s),
         "heading_at_contact_deg": round(rw.theta(sh_t0), 2), "arc_at_contact_mm": round(rw.arc(sh_t0), 2), "status": "derived (collision with the sweeping blade)"},
        {"id": "goal_entry", "t_estimate": t_goal, "goal_line_y_mm": s["goal_y"], "status": "derived"},
        {"id": "goal_net", "t_estimate": round(t_net, 5), "status": "rule: the puck stops against the back of the preview cage"},
    ]
    eg = others["E-G"]
    fig_out = lambda f, status: {"player_id": f.pid, "team": f.team, "fixture_path_id": f.slot.id, "slot_length_mm": round(f.slot.length, 2), "status": status,
                                 "arc_keyframes": f.arcs, "theta_keyframes": f.thetas}
    static_out = lambda pid, arc, theta, status: {"player_id": pid, "team": pid[0], "fixture_path_id": sp.Slot(pid).id, "slot_length_mm": round(sp.Slot(pid).length, 2), "status": status,
                                                  "arc_keyframes": [{"t": t0, "arc_mm": round(arc, 3), "sigma_mm": None, "source": "assumed"}],
                                                  "theta_keyframes": [{"t": t0, "theta_deg": theta, "sigma_deg": None, "source": "assumed"}]}
    trace = {
        "schema": "shot-trace/1", "trace_id": "trace.invers-kryssar-velodrom.v1", "status": INP["status"], "shot": "Invers Kryssar med Velodrom (right wing, NTHF)",
        "geometry_version": sp.G["geometry_version"],
        "asset_refs": {**SPJ["asset_refs"], "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()},
        "source": {"description": "references/combinations/puck-no-invers-kryssar-med-velodrom.html", "approved_reading": "validation/ikv-sketch.png (user, 2026-10-06)",
                   "inputs": "shots/invers-kryssar-velodrom/inputs.json", "text": INP["source_text"]},
        "time_base": {"t": "designed time (s); no recording exists", "window_s": [t0, t1]},
        "interpolation": SPJ["interpolation"], "pose_convention": SPJ["pose_convention"],
        "figures": {"W-RW": fig_out(rw, "moving: passer and shooter (designed)"), "W-LW": fig_out(lw, "moving: velodrome pass (designed)"),
                    "W-C": static_out("W-C", INP["centre"]["arc_mm"], INP["centre"]["theta_deg"], "static: stands back on its slot (assumed)"),
                    "E-G": static_out("E-G", eg.arc_mm, INP["goalie"]["theta_deg"], "static: covers the left post (assumed)"),
                    "others": "static assembly pose (validation/16-assembly-poses.json), as the renderer shows them; included in the checks"},
        "puck": {"radius_mm": R_PUCK, "radius_status": "catalog_nominal", "thickness_mm": sp.PUCK_T, "thickness_status": "assumed (preview)",
                 "ice_friction_deceleration_mm_s2": A_FRIC, "ice_friction_status": "borrowed from the spjass slide fit",
                 "restitution_figure": INP["contact"]["restitution_figure"], "nodes": nodes, "phases": phases},
        "events": events,
        "limitations": INP["limitations"],
    }
    samp = []
    for tq in np.round(np.arange(t0, t1 + 1e-9, 0.02), 4):
        p = [float(np.interp(tq, nt, nx)), float(np.interp(tq, nt, ny))]
        samp.append({"t": float(tq), "W-RW": {"arc_mm": round(rw.arc(tq), 4), "theta_deg": round(rw.theta(tq), 4)},
                     "W-LW": {"arc_mm": round(lw.arc(tq), 4), "theta_deg": round(lw.theta(tq), 4)}, "puck": [round(p[0], 4), round(p[1], 4)]})
    trace["evaluation_samples"] = samp
    OUT_TRACE.write_text(json.dumps(trace, indent=1, ensure_ascii=False) + "\n")
    kinds = []
    for c in iv:
        if not kinds or kinds[-1] != c["obstacle"]:
            kinds.append(c["obstacle"])
    checks = {"trace_id": trace["trace_id"], "sampling_s": DT, "max_puck_step_mm": round(max_step, 3), "penetration_tolerance_mm": PEN_TOL,
              "contact_rule": "CLAUDE.md 'Contact physics': the puck may touch figures, boards and goal but never overlap them (every 0.25 ms, whole trace, all 12 figures, boards, posts, cage; no phase exemptions)",
              "min_clearance_by_obstacle_and_phase": [{"obstacle": k[0], "phase": k[1], **v} for k, v in sorted(rows.items()) if v["min_clearance_mm"] < 30],
              "unexpected_penetrations": [{"obstacle": k[0], "phase": k[1], **v} for k, v in vint.items()], "approved_exceptions": [],
              "contact_sequence": kinds, "impulses": imp, "unexplained_velocity_changes": unexplained[:20], "unexplained_count": len(unexplained),
              "goal_line": {"x_mm": sp.GX, "crossing_y_mm": s["goal_y"], "inside_mouth_window_y_mm": [round(sp.GY - sp.HALF + sp.POST_R + R_PUCK, 1), round(sp.GY + sp.HALF - sp.POST_R - R_PUCK, 1)]},
              "velodrome": {"t": [round(t_board0, 4), round(t_board1, 4)], "length_mm": round(float(np.sum(np.linalg.norm(np.diff(P[(T >= t_board0) & (T <= t_board1)], axis=0), axis=1))), 1),
                            "behind_goal_min_x_mm": round(float(P[(T >= t_board0) & (T <= t_board1) & (np.abs(P[:, 1]) < 60)][:, 0].min()), 1) if ((T >= t_board0) & (T <= t_board1) & (np.abs(P[:, 1]) < 60)).any() else None}}
    OUT_CHECKS.write_text(json.dumps(checks, indent=1, ensure_ascii=False) + "\n")
    sheet(rw, lw, figs, nt, nx, ny, events, t0)
    print(json.dumps({"events": events, "unexpected": checks["unexpected_penetrations"], "unexplained": len(unexplained), "goal": checks["goal_line"], "sequence": kinds,
                      "velodrome": checks["velodrome"], "close": [r for r in checks["min_clearance_by_obstacle_and_phase"] if r["min_clearance_mm"] < 1.5 and r["obstacle"] not in ("W-RW", "W-LW", "boards")]}, indent=1, ensure_ascii=False))


def sheet(rw, lw, figs, nt, nx, ny, events, t0):
    S, W_, H_ = 1.15, 560, 640
    P_ = lambda w: (W_ / 2 - w[1] * S, H_ - 25 - (w[0] + 120) * S)
    ev = {e["id"]: e["t_estimate"] for e in events}
    times = [("pass", ev["pass.release"]), ("left wing", ev["contact.lw_pass"]), ("velodrome", (ev["velodrome.start"] + ev["velodrome.end"]) / 2),
             ("shot", ev["contact.shot"]), ("goal", ev["goal_entry"]), ("net", ev["goal_net"])]
    tiles = []
    for name, tq in times:
        im = Image.new("RGB", (W_, H_), "white"); d = ImageDraw.Draw(im)
        d.line([P_(c) for c in sp.BOARD.exterior.coords], fill=(60, 60, 60), width=2)
        for po in sp.POSTS:
            c = P_(po); d.ellipse([c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3], fill=(200, 0, 0))
        d.line([P_(c) for c in _CAGE_WALLS[0].coords], fill=(200, 0, 0), width=2)
        for pid in ("W-RW", "W-LW", "W-C"):
            sl = sp.Slot(pid); d.line([P_(sl.at(a)) for a in np.arange(0, sl.length, 3)], fill=(90, 90, 90), width=4)
        for f in figs:
            poly = sp.world_polygon(f, tq)
            for g in ([poly] if poly.geom_type == "Polygon" else list(poly.geoms)):
                d.polygon([P_(c) for c in g.exterior.coords], fill=(150, 190, 255) if f.pid.startswith("W") else (255, 225, 120), outline=(30, 30, 30))
        trail = [P_((np.interp(x, nt, nx), np.interp(x, nt, ny))) for x in np.arange(t0, tq, 0.004)]
        if len(trail) > 1:
            d.line(trail, fill=(255, 150, 0), width=2)
        p = (np.interp(tq, nt, nx), np.interp(tq, nt, ny)); c = P_(p)
        d.ellipse([c[0] - R_PUCK * S, c[1] - R_PUCK * S, c[0] + R_PUCK * S, c[1] + R_PUCK * S], fill=(0, 0, 0))
        clr = min(sp.clearance(f, tq, np.array(p)) for f in figs)
        d.text((8, 6), f"{name}  t={tq:.4f} s", fill=(0, 0, 0), font=sp.FB)
        d.text((8, 30), f"RW arc {rw.arc(tq):.0f} th {rw.theta(tq):.0f}  LW th {lw.theta(tq):.0f}  clearance {clr:+.2f} mm", fill=(0, 120, 0) if clr >= -PEN_TOL else (200, 0, 0), font=sp.FS)
        tiles.append(im)
    out = Image.new("RGB", (W_ * 3, H_ * 2 + 40), "white")
    for i, im in enumerate(tiles):
        out.paste(im, ((i % 3) * W_, 40 + (i // 3) * H_))
    ImageDraw.Draw(out).text((10, 8), "trace.invers-kryssar-velodrom.v1 (designed) - top view, goal.E at the top, +y left; figures low geometry; puck path orange", fill=(0, 0, 0), font=sp.FB)
    out.save(OUT_PNG)


if __name__ == "__main__":
    main()
