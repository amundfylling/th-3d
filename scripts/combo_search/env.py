"""Move-engine environment for automatic combination search (hypothesis experiment 2026-11-18, PROPOSED).

Wraps scripts/shotlib (the engine every designed move uses) as `rollout(genome, opponent, perturb) -> dict`:

  action   keyframes for the attacking figures (W-C, W-RW, W-LW): at each of K times the slot arc and the rotation
           (deg). Decoded from normalised increments in [-1, 1], so a rod's rotation speed and a figure's slot speed
           can never exceed LIMITS (plausibility by construction).
  world    the real engine rules (scripts/shotlib/puck.py): ice friction, figure footprints, boards, posts, cage.
           `fast_run` is puck.run with two changes that do not alter the physics: (1) far-away figures are skipped
           (a figure whose pivot is farther than its footprint radius from the puck cannot touch it); (2) the run
           stops 40 ms after the puck is in the net, or when it rests. `validate.py` replays genomes through the
           unmodified puck.run and compares the puck paths.
  opponent a reactive goalie (reaction delay, speed and acceleration limits, tracks the puck's predicted goal-line
           crossing) or a scripted one (static, or a gamble: slides to another y at a fixed time). Other defenders
           stand in the static assembly pose.
  reward   scenario score from the outcome (goal, margin, shaping) minus plausibility penalties (slide-or-bounce rule).

Every number below that is not from the repository is ASSUMED (LIMITS, OPPONENTS).
"""
import math
import sys
from bisect import bisect_right
from pathlib import Path

import numpy as np
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shotlib import build, puck  # noqa: E402
from shotlib import world as W  # noqa: E402

PHYS = dict(build.DEFAULT_PHYSICS)
T0, T1 = 0.0, 1.0
K = 10                                   # keyframes per attacker (t = 0, 0.1 ... 0.9; held after the last)
KT = [round(0.1 * k, 3) for k in range(K)]
LIMITS = {                               # ASSUMED (the repo has no measured rod limits; designed turns so far <= 430 deg/s)
    "turn_deg_s": 500.0,
    "slot_mm_s": 1500.0,
    "figure_impact_mm_s": 500.0,         # CLAUDE.md slide rule
    "wall_impact_mm_s": 300.0,
}
MIN_PUSH_TOUCHES = 5
ANGLE_K = 0.3                            # ASSUMED: angle-cover factor of the reactive goalie
ATTACKERS = ["W-C", "W-RW", "W-LW"]
G_E = W.GOALS["E"]
SLOTS = {p: W.Slot(p) for p in W.ALL_FIGURES}
RADIUS = {k: max(math.hypot(*c) for r in W.RINGS_OUT[k] for c in r.coords) for k in ("skater", "goalie")}

OPPONENTS = {
    "track_med": {"kind": "track", "delay": 0.08, "vmax": 450.0, "amax": 6000.0},
    "track_slow": {"kind": "track", "delay": 0.12, "vmax": 350.0, "amax": 4000.0},
    "track_fast": {"kind": "track", "delay": 0.05, "vmax": 600.0, "amax": 9000.0},
    "static_c": {"kind": "static", "y": 0.5},
    "static_r": {"kind": "static", "y": -12.0},
    "static_l": {"kind": "static", "y": 12.0},
    # gamble: covers one side (y0) and commits to the other post (y1) the moment the puck first moves (a goalie that
    # expects a Hjerpe and has already decided; moves/hjerpefinte: covers the right, slides to the left post)
    "gamble_R_to_L": {"kind": "gamble", "y0": -12.0, "y1": 28.0, "delay": 0.0, "vmax": 450.0, "amax": 6000.0},
    "gamble_L_to_R": {"kind": "gamble", "y0": 12.0, "y1": -28.0, "delay": 0.0, "vmax": 450.0, "amax": 6000.0},
}


class Live(W.Figure):
    """Goalie figure whose arc keys are appended while the puck runs (pchip slopes updated locally, same maths as
    world.pchip_slopes on the final key list, so the saved keys replay identically)."""

    def __init__(self, pid, arc0, theta0):
        super().__init__(pid, [{"t": T0, "arc_mm": arc0}], [{"t": T0, "theta_deg": theta0}])
        self.x, self.y, self.m = [T0], [arc0], [0.0]

    def append(self, t, arc):
        x, y, m = self.x, self.y, self.m
        x.append(t); y.append(arc); m.append(0.0)
        n = len(x)
        if n == 2:
            m[0] = m[1] = (y[1] - y[0]) / (x[1] - x[0])
            return
        i = n - 2
        h0, h1 = x[i] - x[i - 1], x[i + 1] - x[i]
        d0, d1 = (y[i] - y[i - 1]) / h0, (y[i + 1] - y[i]) / h1
        if d0 * d1 > 0:
            w1, w2 = 2 * h1 + h0, h1 + 2 * h0
            m[i] = (w1 + w2) / (w1 / d0 + w2 / d1)
        else:
            m[i] = 0.0
        m[-1] = W._end_slope(h1, h0, d1, d0)
        if n == 3:
            m[0] = W._end_slope(x[1] - x[0], x[2] - x[1], (y[1] - y[0]) / (x[1] - x[0]), (y[2] - y[1]) / (x[2] - x[1]))

    def arc(self, t):
        x, y, m = self.x, self.y, self.m
        if t <= x[0]:
            return y[0]
        if t >= x[-1]:
            return y[-1]
        i = bisect_right(x, t) - 1
        h = x[i + 1] - x[i]
        s = (t - x[i]) / h
        return (2 * s**3 - 3 * s**2 + 1) * y[i] + (s**3 - 2 * s**2 + s) * h * m[i] + (-2 * s**3 + 3 * s**2) * y[i + 1] + (s**3 - s**2) * h * m[i + 1]

    def theta(self, t):
        return float(self.ty[0])

    def keys(self):
        return [{"t": round(t, 5), "arc_mm": round(float(a), 4)} for t, a in zip(self.x, self.y)]


class GoalieCtl:
    """Reactive goalie. Every TICK it commits the arc two ticks ahead (causal), from the puck state `delay` ago."""
    TICK = 0.005

    def __init__(self, fig, opp, slot):
        self.f, self.o, self.slot = fig, opp, slot
        self.hist, self.t_commit = [], None
        self.arc, self.vel, self.j = fig.y[0], 0.0, 0

    def _target_arc(self, t, st):
        o = self.o
        if o["kind"] == "static":
            return self.slot.arc_of_y(o["y"], 0.25)
        if o["kind"] == "gamble":
            if self.t_commit is None and st is not None and float(st[1] @ st[1]) > 100.0 ** 2:
                self.t_commit = t
            return self.slot.arc_of_y(o["y1"] if self.t_commit is not None else o["y0"], 0.25)
        if st is None:
            return self.slot.arc_of_y(0.5, 0.25)
        p, v = st
        y = G_E.y + ANGLE_K * (p[1] - G_E.y)             # puck not shot yet: cover the angle (a fraction of the puck's offset)
        if v[0] > 50.0:                                  # shot: predicted goal-line crossing
            tt = (G_E.x - W.R_PUCK - p[0]) / v[0]
            if 0 < tt < 1.0:
                y = p[1] + v[1] * tt
        y = float(np.clip(y, G_E.y - G_E.half, G_E.y + G_E.half))
        return self.slot.arc_of_y(y, 0.25)

    def step(self, t, p, v):
        self.hist.append((t, p.copy(), v.copy()))
        while t > self.j * self.TICK - 1e-9:
            self._decide(self.j * self.TICK)
            self.j += 1

    def _decide(self, tn):
        o = self.o
        st = None
        tt = tn - o.get("delay", 0.0)
        for t_, p_, v_ in reversed(self.hist):
            if t_ <= tt:
                st = (p_, v_)
                break
        tgt = self._target_arc(tn, st)
        vmax, amax = (o["vmax"], o["amax"]) if o["kind"] != "static" else (900.0, 12000.0)
        vdes = max(-vmax, min(vmax, (tgt - self.arc) * 40.0))
        self.vel += max(-amax * self.TICK, min(amax * self.TICK, vdes - self.vel))
        self.arc = min(max(self.arc + self.vel * self.TICK, 0.0), self.slot.length)
        self.f.append(round(tn + 2 * self.TICK, 5), self.arc)


# ----------------------------------------------------------------------------------------------- genome
def n_params(attackers=ATTACKERS):
    return len(attackers) * (2 + 2 * (K - 1))


FIXED_START = {"W-C": (184.0, 181.0)}   # the NTHF centre stance (moves/hjerpefinte: arc 184 mm, heading 181 deg); None = free start
USE_FIXED = {"on": True}


def decode(g, attackers=ATTACKERS):
    """g in [-1, 1]^n -> {pid: (arc keys mm, theta keys deg)}. Per attacker: start arc (-1..1 -> slot range), start
    theta (g*180 deg), then K-1 increments limited by LIMITS (slot speed, rotation speed)."""
    out, i = {}, 0
    dt = KT[1] - KT[0]
    for pid in attackers:
        L = SLOTS[pid].length
        a = np.empty(K); th = np.empty(K)
        a[0] = (g[i] + 1) / 2 * L; th[0] = g[i + 1] * 180.0
        if USE_FIXED["on"] and pid in FIXED_START:
            a[0], th[0] = FIXED_START[pid]
        for k in range(1, K):
            a[k] = np.clip(a[k - 1] + g[i + 2 * k] * LIMITS["slot_mm_s"] * dt, 0.0, L)
            th[k] = th[k - 1] + g[i + 2 * k + 1] * LIMITS["turn_deg_s"] * dt
        out[pid] = (a, th)
        i += 2 + 2 * (K - 1)
    return out


def figure_from_keys(pid, a, th):
    return W.Figure(pid, [{"t": t, "arc_mm": float(x)} for t, x in zip(KT, a)], [{"t": t, "theta_deg": float(x)} for t, x in zip(KT, th)])


def make_figures(g, opp_name, attackers):
    keys = decode(g, attackers)
    figs = {}
    for pid in W.ALL_FIGURES:
        if pid in keys:
            figs[pid] = figure_from_keys(pid, *keys[pid])
        elif pid != "E-G":
            figs[pid] = W.assembly_figure(pid)
    opp = OPPONENTS[opp_name]
    slot = SLOTS["E-G"]
    gf = Live("E-G", slot.arc_of_y(opp.get("y", opp.get("y0", 0.5)), 0.25), 0.0)
    figs["E-G"] = gf
    return figs, [GoalieCtl(gf, opp, slot)], gf, keys


DEFAULT_START = {"against": "W-C", "local_mm": [-10.0, 26.8]}   # at rest against W-C's blade (the Hjerpe stance, moves/hjerpefinte)


def start_puck(figs, start):
    if "at_mm" in start:
        return np.array(start["at_mm"], float)
    return puck.start_position(start, [figs[start["against"]]], T0)


# ----------------------------------------------------------------------------------------------- fast run
def fast_run(p0, figs, physics, controls, t1=T1, stop_after_goal=0.04):
    e, a_fric, dt = physics["restitution_figure"], physics["ice_deceleration_mm_s2"], W.DT
    p, v = np.asarray(p0, float).copy(), np.zeros(2)
    order = list(figs.values())
    static_piv = {f.pid: (f.piv.copy() if isinstance(f, W.Static) else None) for f in order}
    T, P, impulses, walls = [], [], [], []
    in_net, entered, t_enter, rest_since = False, None, None, None
    n = int(round((t1 - T0) / dt))
    for k in range(n + 1):
        t = T0 + k * dt
        for c in controls:
            c.step(t, p, v)
        if k and not in_net:
            s = float(np.linalg.norm(v))
            if s > 0:
                v = v * max(0.0, s - a_fric * dt) / s
            q = p + v * dt
            for _ in range(3):
                moved = False
                for f in order:
                    sp = static_piv[f.pid]
                    piv = sp if sp is not None else f.pose(t)[0]
                    R = RADIUS[f.kind] + 2
                    if abs(q[0] - piv[0]) > R or abs(q[1] - piv[1]) > R:
                        continue
                    loc = W.to_local(f, t, q)
                    if not W.LOW_OUT[f.kind].contains(Point(*loc)):
                        continue
                    best = min((r.interpolate(r.project(Point(*loc))) for r in W.RINGS_OUT[f.kind]), key=lambda z: z.distance(Point(*loc)))
                    r_loc = np.array(best.coords[0])
                    q_new = W.to_world(f, t, r_loc)
                    nrm = q_new - q
                    nn = float(np.linalg.norm(nrm))
                    if nn > 1e-6:
                        nrm = nrm / nn
                    else:
                        lb = W.LOW[f.kind].boundary
                        nb = np.array(lb.interpolate(lb.project(Point(*r_loc))).coords[0])
                        nrm = W.rot(f.pose(t)[1]) @ (r_loc - nb)
                        nrm = nrm / max(1e-12, float(np.linalg.norm(nrm)))
                    v_fig = (W.to_world(f, t, r_loc) - W.to_world(f, t - dt, r_loc)) / dt
                    vn = float((v - v_fig) @ nrm)
                    if vn < 0:
                        v = v - (1 + e) * vn * nrm
                        impulses.append({"t": round(t, 5), "figure": f.pid, "part": W.part_of(f, t, q_new), "impact_mm_s": float(-vn)})
                    q = q_new
                    moved = True
                for po in G_E.posts:
                    dd = q - po
                    nd = float(np.linalg.norm(dd))
                    if nd < W.R_PUCK + G_E.post_r:
                        nrm = dd / nd
                        q = po + nrm * (W.R_PUCK + G_E.post_r + W.EPS)
                        vn = float(v @ nrm)
                        if vn < 0:
                            v = v - vn * nrm
                            walls.append({"t": round(t, 5), "obstacle": "goal_post", "impact_mm_s": float(-vn)})
                        moved = True
                if not W.INSET.contains(Point(*q)):
                    b = W.INSET.exterior
                    qq = np.array(b.interpolate(b.project(Point(*q))).coords[0])
                    q, v = puck._wall(q, v, qq, "boards", t, walls)
                    moved = True
                if not moved:
                    break
            for g in (G_E, W.GOALS["W"]):
                if entered is None and g.crossed(p, q):
                    entered, t_enter = g.end, t
                if entered == g.end:
                    lim = g.half - W.R_PUCK
                    if abs(q[1] - g.y) > lim:
                        q = np.array([q[0], g.y + math.copysign(lim, q[1] - g.y)]); v = np.array([v[0], 0.0])
                    if g.sign * (q[0] - g.back_x) >= 0:
                        q = np.array([g.back_x, q[1]]); v = np.zeros(2); in_net = True
                elif g.cage_out.contains(Point(*q)) and not ((not g.beyond_line(p[0])) and abs(q[1] - g.y) < g.half - W.R_PUCK):
                    cq = g.cage_out.exterior if g.cage_out.geom_type == "Polygon" else max(g.cage_out.geoms, key=lambda x: x.area).exterior
                    qq = np.array(cq.interpolate(cq.project(Point(*q))).coords[0])
                    q, v = puck._wall(q, v, qq, "goal_cage", t, walls)
            p = q
        T.append(t); P.append(p.copy())
        if entered is not None and t - t_enter > stop_after_goal:
            break
        if float(v @ v) < 1e-12 and k > 10 and t > 0.45:
            rest_since = t if rest_since is None else rest_since
            if t - rest_since > 0.12:
                break
        else:
            rest_since = None
    return np.array(T), np.array(P), impulses, walls, entered, t_enter


# ----------------------------------------------------------------------------------------------- scoring
def rollout(g, opp_name="track_med", attackers=ATTACKERS, start=None, perturb=None, keep_path=False):
    perturb = perturb or {}
    start = start or DEFAULT_START
    W.set_footprint_transform(**perturb.get("footprint", {}))
    physics = dict(PHYS)
    if "ice_scale" in perturb:
        physics["ice_deceleration_mm_s2"] *= perturb["ice_scale"]
    if "restitution" in perturb:
        physics["restitution_figure"] = perturb["restitution"]
    try:
        figs, ctls, gf, keys = make_figures(g, opp_name, attackers)
        p0 = start_puck(figs, start)
        if "puck_dx" in perturb:
            p0 = p0 + np.array(perturb["puck_dx"])
        T, P, imp, walls, entered, t_enter = fast_run(p0, figs, physics, ctls)
    finally:
        W.set_footprint_transform()
    return summarise(T, P, imp, walls, entered, t_enter, gf, keys, keep_path, p0)


def summarise(T, P, imp, walls, entered, t_enter, gf, keys, keep_path, p0):
    touched = []
    for x in imp:
        if not touched or touched[-1] != x["figure"]:
            touched.append(x["figure"])
    groups = []                                      # attacker contact groups: touches closer than 60 ms are one contact
    for x in imp:
        if x["figure"] not in ATTACKERS:
            continue
        if groups and groups[-1][0] == x["figure"] and x["t"] - groups[-1][2] < 0.06:
            groups[-1][2] = x["t"]; groups[-1][1] += 1
        else:
            groups.append([x["figure"], 1, x["t"]])
    res = {
        "min_group_n": min([g[1] for g in groups] + [10**9]), "n_groups": len(groups),
        "goal": entered, "t_goal": t_enter, "touch_seq": touched,
        "peak_fig": max([x["impact_mm_s"] for x in imp if x["figure"] != "E-G"] + [0.0]),
        "peak_wall": max([x["impact_mm_s"] for x in walls] + [0.0]),
        "n_touch": len(imp), "saved": any(x["figure"] == "E-G" for x in imp), "end": P[-1].tolist(),
    }
    if entered == "E":
        i = min(int(np.searchsorted(T, t_enter)), len(P) - 1)
        i0, i1 = max(i - 1, 0), min(i + 1, len(P) - 1)
        res["goal_y"] = float(P[i, 1])
        res["goal_speed"] = float(np.linalg.norm((P[i1] - P[i0]) / (T[i1] - T[i0])))
        res["goalie_y"] = float(gf.pose(t_enter)[0][1])
    else:
        res["min_d_goal"] = float(np.hypot(P[:, 0] - G_E.x, P[:, 1] - G_E.y).min())
    if keep_path:
        res.update({"T": T, "P": P, "keys": keys, "goalie_keys": gf.keys(), "impulses": imp, "walls": walls, "p0": p0})
    return res


def score(r):
    """Scenario score: 1 + margin bonus for a goal, shaped closeness otherwise, minus slide-rule penalties."""
    if r["goal"] == "E":
        marg = min(abs(r["goal_y"] - r["goalie_y"]) - 14.0, 20.0)
        s = 1.0 + 0.25 * max(marg, 0.0) / 20.0
        if r["saved"]:
            s -= 0.5
    elif r["goal"] == "W":
        s = -1.0
    else:
        s = 0.6 * (1.0 - min(r["min_d_goal"], 800.0) / 800.0) - 0.2 - (0.1 if r["saved"] else 0.0)
    s -= max(0.0, r["peak_fig"] - LIMITS["figure_impact_mm_s"]) / LIMITS["figure_impact_mm_s"]
    s -= max(0.0, r["peak_wall"] - LIMITS["wall_impact_mm_s"]) / LIMITS["wall_impact_mm_s"]
    if r["n_touch"] == 0:
        s -= 0.2
    # a push is a sustained contact (moves/*/move.json `min_touches: 5`; CLAUDE.md 'Slide or bounce'): a single sharp
    # touch is a strike, which the slide rule excludes in spirit even when its impact speed is under the limit
    if r["min_group_n"] < MIN_PUSH_TOUCHES:
        s -= 0.3 + 0.1 * (MIN_PUSH_TOUCHES - r["min_group_n"])
    return s
