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


def seg_track(segs, t0, key, step=0.002):
    """Value keyframes from holds and smootherstep moves (sampled every 2 ms). segs: [[t_start, duration, from, to], ...]."""
    ks = [(t0, segs[0][2])]
    for ts, d, a, b in segs:
        ks.append((ts, a))
        n = max(2, int(round(d / step)))
        for k in range(1, n + 1):
            ks.append((ts + d * k / n, a + (b - a) * smooth(k / n)))
    out = {}
    for t, v in ks:
        out[round(t, 5)] = v
    return [{"t": t, key: round(v, 4), "sigma_mm" if key == "arc_mm" else "sigma_deg": None, "source": "designed"} for t, v in sorted(out.items())]


def quintic(t0, t1, a0, v0, a1, v1, dt=0.005):
    """Arc keys (every 5 ms) of the quintic move with the given end positions (mm) and velocities (mm/s) and zero end
    accelerations."""
    T = t1 - t0
    A = np.array([[T**3, T**4, T**5], [3*T**2, 4*T**3, 5*T**4], [6*T, 12*T**2, 20*T**3]])
    c3, c4, c5 = np.linalg.solve(A, np.array([a1 - a0 - v0*T, v1 - v0, 0.0]))
    n = max(1, int(round(T / dt)))
    return [[round(t0 + T*k/n, 5), round(float(a0 + v0*(T*k/n) + c3*(T*k/n)**3 + c4*(T*k/n)**4 + c5*(T*k/n)**5), 4)] for k in range(1, n + 1)]


def arc_keys(fig_inp):
    """Designed arc keyframes: explicit keys plus quintic moves [t0, t1, a0, v0, a1, v1, why] (sampled every 5 ms)."""
    ks = [{"t": t, "arc_mm": a, "sigma_mm": None, "source": "designed: " + why} for t, a, why in fig_inp["arc_keys"]]
    for t0_, t1_, a0, v0, a1, v1, why in fig_inp.get("arc_moves", []):
        ks += [{"t": t, "arc_mm": a, "sigma_mm": None, "source": "designed: " + why} for t, a in quintic(t0_, t1_, a0, v0, a1, v1)]
    return sorted(ks, key=lambda k: k["t"])


_TAN = {}


def slot_tangent_deg(slot, a):
    """Direction of the slot centreline at arc a (deg), smoothed: central differences over +-10 mm, then a Gaussian
    (sigma 8 mm) along the arc - the traced centreline wiggles at the 3 mm vertex spacing."""
    if slot.id not in _TAN:
        aa = np.arange(0.0, slot.length + 1e-9, 0.5)
        d = np.array([slot.at(x + 10.0) - slot.at(x - 10.0) for x in aa])
        ang = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
        k = np.exp(-0.5 * (np.arange(-48, 49) * 0.5 / 8.0) ** 2); k /= k.sum()
        pad = np.r_[np.full(48, ang[0]), ang, np.full(48, ang[-1])]
        _TAN[slot.id] = (aa, np.degrees(np.convolve(pad, k, mode="valid")))
    aa, deg = _TAN[slot.id]
    return float(np.interp(a, aa, deg))


def lw_figure(t0, t1):
    """W-LW: arc moves and theta moves (smootherstep); from `follow_tangent_from_s` on, the player also turns the figure
    with the slot's tangent (the blade stays square to the curved boards) - a designed rod rotation, not an automatic one."""
    lw_ = INP["left_wing"]
    arcs = arc_keys(lw_)
    base = sp.Figure("W-LW", "W", "skater", arcs, theta_track(lw_["theta_segments"], t0))
    tc = lw_["follow_tangent_from_s"]
    tan0 = slot_tangent_deg(base.slot, base.arc(tc))
    t_end = max([s_[0] + s_[1] for s_ in lw_["theta_segments"]] + [k["t"] for k in arcs])
    times = sorted(set([round(t0, 5)] + [round(x, 5) for x in np.arange(min(s_[0] for s_ in lw_["theta_segments"]), t_end + 1e-9, 0.002)] + [round(t_end, 5), round(t1, 5)]))
    th = []
    for t in times:
        v = base.theta(t) + ((slot_tangent_deg(base.slot, base.arc(t)) - tan0) if t >= tc else 0.0)
        th.append({"t": t, "theta_deg": round(v, 4), "sigma_deg": None, "source": "designed" + (": turned with the slot tangent" if t >= tc else "")})
    return sp.Figure("W-LW", "W", "skater", arcs, th)


def build():
    t0, t1 = INP["window_s"]
    rw_, wc_ = INP["right_wing"], INP["centre"]
    rw_arcs = arc_keys(rw_)
    rw = sp.Figure("W-RW", "W", "skater", rw_arcs, theta_track(rw_["theta_segments"], t0))
    lw = lw_figure(t0, t1)
    wc = sp.Static("W-C", "skater", sp.Slot("W-C").at(wc_["arc_mm"]), sp.HOME["W"] + wc_["theta_deg"])
    others = {pid: sp.Static(pid, "goalie" if f["position"] == "G" else "skater", f["pivot_mm"][:2], f["heading_deg"]) for pid, f in sp.ASM.items() if pid not in ("W-RW", "W-LW", "W-C", "E-G")}
    eg_slot = sp.Slot("E-G")
    a_g = min(np.arange(0, eg_slot.length, 0.05), key=lambda a: abs(eg_slot.at(a)[1] - INP["goalie"]["y_mm"]))
    others["E-G"] = sp.Static("E-G", "goalie", eg_slot.at(a_g), 180.0 + INP["goalie"]["theta_deg"])
    others["E-G"].arc_mm = float(a_g)
    # puck at rest JUST TOUCHING the front face of the right wing's blade (mid blade) at the start heading of the pass push
    piv, h = rw.pose(t0)
    p_rest = piv + sp.rot(h) @ (BLADE_MID + np.array([R_PUCK - 2.0, 0.0]))
    p_rest, _ = sp.push_out(rw, t0, p_rest)
    return t0, t1, p_rest, rw, lw, wc, others


def part_of(f, t, p):
    q = Point(*sp.to_local(f, t, p))
    return "stick/blade" if sp.STICK[f.kind].distance(q) <= sp.LOW[f.kind].distance(q) + 0.3 else "skate/body"


def run(t0, t1, p_rest, figs):
    e = INP["contact"]["restitution_figure"]
    p, v = p_rest.copy(), np.zeros(2)
    T, P, V, touching, impulses, walls = [], [], [], [], [], []
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
                        impulses.append({"t": round(t, 5), "figure": f.pid, "part": part_of(f, t, q_new), "impact_mm_s": round(float(-vn), 1), "dv": round(float(-(1 + e) * vn), 1)})
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
                            walls.append({"t": round(t, 5), "obstacle": "goal_post", "impact_mm_s": round(float(-vn), 1)})
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
                            walls.append({"t": round(t, 5), "obstacle": "boards", "impact_mm_s": round(float(-vn), 1)})
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
                            walls.append({"t": round(t, 5), "obstacle": "goal_cage", "impact_mm_s": round(float(-vn), 1)})
                    q = qq
                    hits.append("goal_cage")
            p = q
        T.append(t); P.append(p.copy()); V.append(v.copy()); touching.append(tuple(sorted(set(hits))))
    return np.array(T), np.array(P), np.array(V), touching, impulses, walls


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
    T, P, V, touching, imp, walls = run(t0, t1, p_rest, [rw, lw, wc, *others.values()])
    s, _ = summary(T, P, V, touching)
    spd = np.linalg.norm(V, axis=1)
    s["max_figure_impact"] = max(((x["impact_mm_s"], x["t"], x["figure"]) for x in imp), default=None)
    s["max_wall_impact"] = max(((x["impact_mm_s"], x["t"], x["obstacle"]) for x in walls), default=None)
    s["big_impacts"] = [(x["t"], x["figure"], x["impact_mm_s"]) for x in imp if x["impact_mm_s"] > 100][:10]
    s["big_walls"] = [(x["t"], x["obstacle"], x["impact_mm_s"]) for x in walls if x["impact_mm_s"] > 100][:10]
    s["speed"] = {str(tq): round(float(spd[min(int(np.searchsorted(T, tq)), len(T) - 1)]), 0) for tq in (0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 1.9, 2.1)}
    s["pos"] = {str(tq): [round(float(x), 0) for x in P[min(int(np.searchsorted(T, tq)), len(T) - 1)]] for tq in (0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 1.9, 2.1)}
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
    T, P, V, touching, imp, walls = run(t0, t1, p_rest, figs)
    s, iv = summary(T, P, V, touching)
    deg = lambda v: round(math.degrees(math.atan2(v[1], v[0])), 2)
    vel = lambda tq: V[min(int(np.searchsorted(T, tq)), len(V) - 1)]
    at = lambda tq: np.array([np.interp(tq, T, P[:, 0]), np.interp(tq, T, P[:, 1])])
    # contacts: impulses grouped per figure (a new group after a gap of more than 60 ms)
    groups = {}
    for x in imp:
        g = groups.setdefault(x["figure"], [])
        if g and x["t"] - g[-1][-1]["t"] <= 0.06:
            g[-1].append(x)
        else:
            g.append([x])
    rw_g, lw_g = groups.get("W-RW", []), groups.get("W-LW", [])
    assert len(rw_g) >= 2 and len(lw_g) >= 2, f"missing contacts: {[(k, [(g[0]['t'], g[-1]['t']) for g in v]) for k, v in groups.items()]}"
    pass_g, shot_g = rw_g[0], rw_g[-1]
    catch_g, push_g = lw_g[0], lw_g[-1]
    pass_t0, pass_t = pass_g[0]["t"], pass_g[-1]["t"]
    lw_t0, lw_t1 = catch_g[0]["t"], catch_g[-1]["t"]
    push_t0, push_t1 = push_g[0]["t"], push_g[-1]["t"]
    sh_t0, sh_t1 = shot_g[0]["t"], shot_g[-1]["t"]
    boards = [c for c in iv if c["obstacle"] == "boards"]
    b_catch = [c for c in boards if lw_t1 < c["t0"] < push_t0]
    b_velo = [c for c in boards if c["t1"] > push_t1 and c["t0"] < sh_t0]
    net = [c for c in iv if c["obstacle"] == "goal_net"]
    assert net and s["goal_y"] is not None and b_catch and b_velo, "no goal or missing board contacts"
    t_board_catch = b_catch[0]["t0"]
    t_board0, t_board1 = max(b_velo[0]["t0"], push_t1), b_velo[-1]["t1"]
    t_goal, t_net = s["t_goal"], net[0]["t0"]
    # phases
    def phase(t):
        if t < pass_t0: return "rest_at_blade"
        if t <= pass_t + 0.004: return "pass_push"
        if t < lw_t0: return "cross_pass"
        if t <= lw_t1 + 0.004: return "lw_reception"
        if t < t_board_catch: return "to_the_boards"
        if t < push_t0: return "along_the_board"
        if t <= push_t1 + 0.004: return "lw_push"
        if t < sh_t0: return "velodrome"
        if t <= sh_t1 + 0.004: return "shot_push"
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
    loc_p, n_p = local_contact(rw, pass_t0, at(pass_t0))
    loc_l, n_l = local_contact(lw, lw_t0, at(lw_t0))
    loc_u, n_u = local_contact(lw, push_t0, at(push_t0))
    loc_s, n_s = local_contact(rw, sh_t0, at(sh_t0))
    t_mid = min((x["t"] for x in push_g), key=lambda tq: abs(lw.pose(tq)[1] + 45.0))
    loc_m, n_m = local_contact(lw, t_mid, at(t_mid))
    v_p, v_l, v_u, v_s = vel(pass_t + 0.006), vel(lw_t1 + 0.006), vel(push_t1 + 0.006), vel(sh_t1 + 0.006)
    peak = lambda g: round(max(x["impact_mm_s"] for x in g), 1)
    w_catch = [w for w in walls if w["obstacle"] == "boards" and abs(w["t"] - t_board_catch) < 0.01]
    events = [
        {"id": "pass.start", "t_estimate": round(pass_t0, 5), "status": "designed: the right wing starts the forehand push with the puck resting against the blade"},
        {"id": "pass.release", "t_estimate": round(pass_t, 5), "t_start": round(pass_t0, 5), "part": "W-RW:stick/blade (front, forehand push)", "contact_point_local_mm": loc_p,
         "model_contact_normal_deg": n_p, "peak_impact_mm_s": peak(pass_g), "speed_mm_s": round(float(np.linalg.norm(v_p)), 1), "direction_deg": deg(v_p),
         "status": "derived (sustained push by the turning blade; the puck separates as the blade slows)"},
        {"id": "contact.lw_catch", "t_estimate": round(lw_t0, 5), "t_end": round(lw_t1, 5), "part": "W-LW:stick (front, low on the shaft just above the heel; soft reception while turning to face forward)",
         "contact_point_local_mm": loc_l, "model_contact_normal_deg": n_l, "peak_impact_mm_s": peak(catch_g), "speed_mm_s": round(float(np.linalg.norm(v_l)), 1),
         "direction_deg": deg(v_l), "status": "derived (contact with the turning blade)"},
        {"id": "board.after_catch", "t_estimate": round(t_board_catch, 5), "impact_mm_s": round(max([w["impact_mm_s"] for w in w_catch] + [0.0]), 1),
         "status": "derived: the received puck runs onto the +y board at a glancing angle and slides along it"},
        {"id": "contact.lw_push", "t_estimate": round(push_t0, 5), "t_end": round(push_t1, 5), "part": "W-LW:stick/blade (front, forward push into the corner)",
         "contact_point_local_mm": loc_u, "model_contact_normal_deg": n_u, "first_impact_mm_s": push_g[0]["impact_mm_s"], "peak_impact_mm_s": peak(push_g),
         "touches": len(push_g), "release_speed_mm_s": round(float(np.linalg.norm(v_u)), 1), "release_direction_deg": deg(v_u),
         "status": "derived (the left wing skates up its slot and through the curve, the front of the blade behind the puck)"},
        {"id": "lw_push.corner", "t_estimate": t_mid, "part": "W-LW:stick/blade (front)", "contact_point_local_mm": loc_m, "model_contact_normal_deg": n_m,
         "heading_deg": round(lw.pose(t_mid)[1], 2), "arc_mm": round(lw.arc(t_mid), 2), "puck_speed_mm_s": round(float(np.linalg.norm(vel(t_mid))), 1),
         "status": "derived: a push touch in the middle of the curve (figure heading nearest -45 deg)"},
        {"id": "velodrome.start", "t_estimate": round(t_board0, 5), "status": "derived: the left wing lets the puck go along the end board"},
        {"id": "velodrome.end", "t_estimate": round(t_board1, 5), "status": "derived: last board contact before the shot"},
        {"id": "turn.onset", "t_estimate": INP["right_wing"]["theta_segments"][1][0], "status": "designed: the right wing turns round to face his own end"},
        {"id": "contact.shot", "t_estimate": round(sh_t0, 5), "t_end": round(sh_t1, 5), "part": "W-RW:stick/blade (back, first-time backhand push)", "contact_point_local_mm": loc_s,
         "model_contact_normal_deg": n_s, "peak_impact_mm_s": peak(shot_g), "speed_mm_s": round(float(np.linalg.norm(v_s)), 1), "direction_deg": deg(v_s),
         "heading_at_contact_deg": round(rw.theta(sh_t0), 2), "arc_at_contact_mm": round(rw.arc(sh_t0), 2),
         "status": "derived (the right wing gives way down his slot as the puck arrives, then turns the back of the blade through it)"},
        {"id": "goal_entry", "t_estimate": t_goal, "goal_line_y_mm": s["goal_y"], "status": "derived"},
        {"id": "goal_net", "t_estimate": round(t_net, 5), "status": "rule: the puck stops against the back of the preview cage"},
    ]
    # slide-or-bounce check (CLAUDE.md, user rule 2026-10-06)
    lim_f, lim_w = INP["slide_rule"]["figure_impact_max_mm_s"], INP["slide_rule"]["wall_impact_max_mm_s"]
    f_bad = [x for x in imp if x["impact_mm_s"] > lim_f]
    w_bad = [w for w in walls if w["impact_mm_s"] > lim_w]
    slide_check = {"rule": "CLAUDE.md 'Slide or bounce': every contact must leave the puck flat on the ice; the net catching the puck is exempt",
                   "figure_impact_max_mm_s": lim_f, "wall_impact_max_mm_s": lim_w, "limits_status": INP["slide_rule"]["status"],
                   "per_contact": [{"contact": name, "figure": g[0]["figure"], "t": [g[0]["t"], g[-1]["t"]], "touches": len(g), "peak_impact_mm_s": peak(g)}
                                   for name, g in (("pass", pass_g), ("lw_catch", catch_g), ("lw_push", push_g), ("shot", shot_g))]
                                  + [{"contact": f"other ({g[0]['figure']})", "figure": g[0]["figure"], "t": [g[0]["t"], g[-1]["t"]], "touches": len(g), "peak_impact_mm_s": peak(g)}
                                     for k, gs in groups.items() for g in gs if not any(g is x for x in (pass_g, catch_g, push_g, shot_g))],
                   "peak_board_impact_mm_s": round(max([w["impact_mm_s"] for w in walls if w["obstacle"] == "boards"] + [0.0]), 1),
                   "peak_post_impact_mm_s": round(max([w["impact_mm_s"] for w in walls if w["obstacle"] == "goal_post"] + [0.0]), 1),
                   "peak_cage_impact_mm_s": round(max([w["impact_mm_s"] for w in walls if w["obstacle"] == "goal_cage"] + [0.0]), 1),
                   "figure_violations": f_bad, "wall_violations": w_bad, "passed": not f_bad and not w_bad}
    eg = others["E-G"]
    fig_out = lambda f, status: {"player_id": f.pid, "team": f.team, "fixture_path_id": f.slot.id, "slot_length_mm": round(f.slot.length, 2), "status": status,
                                 "arc_keyframes": f.arcs, "theta_keyframes": f.thetas}
    static_out = lambda pid, arc, theta, status: {"player_id": pid, "team": pid[0], "fixture_path_id": sp.Slot(pid).id, "slot_length_mm": round(sp.Slot(pid).length, 2), "status": status,
                                                  "arc_keyframes": [{"t": t0, "arc_mm": round(arc, 3), "sigma_mm": None, "source": "assumed"}],
                                                  "theta_keyframes": [{"t": t0, "theta_deg": theta, "sigma_deg": None, "source": "assumed"}]}
    trace = {
        "schema": "shot-trace/1", "trace_id": "trace.invers-kryssar-velodrom.v2", "status": INP["status"], "shot": "Invers Kryssar med Velodrom (right wing, NTHF)",
        "geometry_version": sp.G["geometry_version"],
        "asset_refs": {**SPJ["asset_refs"], "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()},
        "source": {"description": "references/combinations/puck-no-invers-kryssar-med-velodrom.html", "approved_reading": "validation/ikv-sketch.png (user, 2026-10-06)",
                   "inputs": "shots/invers-kryssar-velodrom/inputs.json", "text": INP["source_text"]},
        "time_base": {"t": "designed time (s); no recording exists", "window_s": [t0, t1]},
        "interpolation": SPJ["interpolation"], "pose_convention": SPJ["pose_convention"],
        "figures": {"W-RW": fig_out(rw, "moving: passer and shooter (designed)"), "W-LW": fig_out(lw, "moving: soft reception, then a forward push along its slot into the corner (designed)"),
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
    # contact episodes: intervals of one obstacle closer than 60 ms merged, ordered by start (the puck can touch the
    # board and the pushing blade at the same time, so episodes may overlap)
    eps = []
    for c in sorted(iv, key=lambda c: c["t0"]):
        prev_ = next((e for e in reversed(eps) if e["obstacle"] == c["obstacle"]), None)
        if prev_ and c["t0"] - prev_["t1"] <= 0.06:
            prev_["t1"] = max(prev_["t1"], c["t1"])
        else:
            eps.append(dict(c))
    eps = [e for e in eps if not (e["obstacle"].startswith("W-RW") and e["t1"] < pass_t0)]  # resting against the blade before the pass
    kinds = [e["obstacle"] for e in eps]
    checks = {"trace_id": trace["trace_id"], "sampling_s": DT, "max_puck_step_mm": round(max_step, 3), "penetration_tolerance_mm": PEN_TOL,
              "contact_rule": "CLAUDE.md 'Contact physics': the puck may touch figures, boards and goal but never overlap them (every 0.25 ms, whole trace, all 12 figures, boards, posts, cage; no phase exemptions)",
              "min_clearance_by_obstacle_and_phase": [{"obstacle": k[0], "phase": k[1], **v} for k, v in sorted(rows.items()) if v["min_clearance_mm"] < 30],
              "unexpected_penetrations": [{"obstacle": k[0], "phase": k[1], **v} for k, v in vint.items()], "approved_exceptions": [], "slide_check": slide_check,
              "contact_sequence": kinds, "contact_episodes": [{"obstacle": e["obstacle"], "t": [round(e["t0"], 5), round(e["t1"], 5)]} for e in eps], "impulses": imp, "unexplained_velocity_changes": unexplained[:20], "unexplained_count": len(unexplained),
              "goal_line": {"x_mm": sp.GX, "crossing_y_mm": s["goal_y"], "inside_mouth_window_y_mm": [round(sp.GY - sp.HALF + sp.POST_R + R_PUCK, 1), round(sp.GY + sp.HALF - sp.POST_R - R_PUCK, 1)]},
              "velodrome": {"t": [round(t_board0, 4), round(t_board1, 4)], "length_mm": round(float(np.sum(np.linalg.norm(np.diff(P[(T >= t_board0) & (T <= t_board1)], axis=0), axis=1))), 1),
                            "behind_goal_min_x_mm": round(float(P[(T >= t_board0) & (T <= t_board1) & (np.abs(P[:, 1]) < 60)][:, 0].min()), 1) if ((T >= t_board0) & (T <= t_board1) & (np.abs(P[:, 1]) < 60)).any() else None}}
    OUT_CHECKS.write_text(json.dumps(checks, indent=1, ensure_ascii=False) + "\n")
    sheet(rw, lw, figs, nt, nx, ny, events, t0)
    print(json.dumps({"events": events, "slide_check": {k: slide_check[k] for k in ("per_contact", "peak_board_impact_mm_s", "peak_post_impact_mm_s", "peak_cage_impact_mm_s", "passed")}, "unexpected": checks["unexpected_penetrations"], "unexplained": len(unexplained), "goal": checks["goal_line"], "sequence": kinds,
                      "velodrome": checks["velodrome"], "close": [r for r in checks["min_clearance_by_obstacle_and_phase"] if r["min_clearance_mm"] < 1.5 and r["obstacle"] not in ("W-RW", "W-LW", "boards")]}, indent=1, ensure_ascii=False))


def sheet(rw, lw, figs, nt, nx, ny, events, t0):
    S, W_, H_ = 1.15, 560, 640
    P_ = lambda w: (W_ / 2 - w[1] * S, H_ - 25 - (w[0] + 120) * S)
    ev = {e["id"]: e["t_estimate"] for e in events}
    times = [("pass", ev["pass.release"]), ("left wing catch", ev["contact.lw_catch"]), ("left wing push", (ev["contact.lw_push"] + ev["velodrome.start"]) / 2),
             ("velodrome", (ev["velodrome.start"] + ev["velodrome.end"]) / 2), ("shot", ev["contact.shot"]), ("goal", ev["goal_entry"])]
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
    ImageDraw.Draw(out).text((10, 8), "trace.invers-kryssar-velodrom.v2 (designed) - top view, goal.E at the top, +y left; figures low geometry; puck path orange", fill=(0, 0, 0), font=sp.FB)
    out.save(OUT_PNG)


if __name__ == "__main__":
    main()
