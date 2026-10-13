"""The puck between contacts: the rules every designed move uses (no general simulator, CLAUDE.md rule 8).

Every 0.25 ms (world.DT):
- ice friction: constant deceleration;
- figure contact (optionally inelastic below a low impact speed, see run()): where a figure's footprint (all 12 figures) would overlap the puck, the puck is moved out to touching
  along the contact normal; if it approaches the figure's surface there (relative normal velocity < 0; the surface
  velocity comes from the figure's pose change over one step), it takes a collision impulse along the normal with
  restitution e (frictionless: the tangential velocity is kept). A push (blade moving with the puck) is a run of many
  small touches;
- boards and goal posts: moved out to touching, the normal velocity removed (inelastic: the puck slides along them);
- goal cages: from outside, the side and back nets are walls; a puck that crosses a goal line between the posts is in
  the goal, the side nets hold it and the back net stops it.
So every change in the puck's motion has a named cause. Same rules as scripts/ikv-trace.py, for both goals.
"""
import math

import numpy as np
from shapely.geometry import Point

from . import world as W


def start_position(start, figs, t0):
    """Puck start: {"at_mm": [x, y]} or {"against": pid, "local_mm": [x, y]} (a point in that figure's frame; the puck
    is then moved out to just touching it)."""
    if "at_mm" in start:
        return np.array(start["at_mm"], float)
    f = next(f for f in figs if f.pid == start["against"])
    p = W.to_world(f, t0, np.array(start["local_mm"], float))
    loc = W.to_local(f, t0, p)
    if W.LOW_OUT[f.kind].contains(Point(*loc)):
        best = min((r.interpolate(r.project(Point(*loc))) for r in W.RINGS_OUT[f.kind]), key=lambda z: z.distance(Point(*loc)))
        p = W.to_world(f, t0, np.array(best.coords[0]))
    return p


def _wall(q, v, qq, obstacle, t, walls):
    nrm = qq - q
    nd = float(np.linalg.norm(nrm))
    if nd > 1e-12:
        nrm = nrm / nd
        vn = float(v @ nrm)
        if vn < 0:
            v = v - vn * nrm
            walls.append({"t": round(t, 5), "obstacle": obstacle, "impact_mm_s": round(float(-vn), 1)})
    return qq, v


def run(t0, t1, p0, figs, physics, v0=(0.0, 0.0), controls=()):
    """Returns T, P, V (arrays), touching (obstacle names per step), impulses (figure touches) and walls (board, post,
    cage touches with their normal impact speed), goal (the end whose goal the puck entered, or None).
    `controls` (scripts/shotlib/control.py): figures steered from the puck's state; each is called before every step
    with the state at the end of the previous step and only ever adds keyframes after the time being simulated."""
    e, a_fric, dt = physics["restitution_figure"], physics["ice_deceleration_mm_s2"], W.DT
    # optional low-speed restitution: a touch slower than `low_speed_mm_s` is inelastic in the normal direction (the
    # puck stays against the blade and slides along it), so a push is a contact, not a series of micro-bounces
    e_low, v_low = physics.get("restitution_figure_low_speed"), physics.get("low_speed_mm_s", 0.0)
    p, v = np.asarray(p0, float).copy(), np.asarray(v0, float).copy()
    T, P, V, touching, impulses, walls = [], [], [], [], [], []
    in_net, entered = False, None
    n = int(round((t1 - t0) / dt))
    for k in range(n + 1):
        t = t0 + k * dt
        hits = []
        for c in controls:
            c.step(t, p, v)
        if k and not in_net:
            s = float(np.linalg.norm(v))
            if s > 0:
                v = v * max(0.0, s - a_fric * dt) / s
            q = p + v * dt
            for _ in range(3):
                moved = False
                for f in figs:
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
                        # the puck already sits on the contact ring (a push-out of zero length): the normal is the
                        # footprint's outward normal there (from its nearest solid point), not a direction of rounding
                        # noise (before 2026-10-11 this fell back to the pivot -> puck direction, which gave impulses in
                        # wrong directions on blades far from the pivot)
                        lb = W.LOW[f.kind].boundary
                        nb = np.array(lb.interpolate(lb.project(Point(*r_loc))).coords[0])
                        nrm = W.rot(f.pose(t)[1]) @ (r_loc - nb)
                        nrm = nrm / max(1e-12, float(np.linalg.norm(nrm)))
                    v_fig = (W.to_world(f, t, r_loc) - W.to_world(f, t - dt, r_loc)) / dt
                    vn = float((v - v_fig) @ nrm)
                    if vn < 0:
                        e_ = e if (e_low is None or -vn > v_low) else e_low
                        v = v - (1 + e_) * vn * nrm
                        impulses.append({"t": round(t, 5), "figure": f.pid, "part": W.part_of(f, t, q_new), "impact_mm_s": round(float(-vn), 1), "dv": round(float(-(1 + e_) * vn), 1)})
                    q = q_new
                    hits.append(f"{f.pid}:{W.part_of(f, t, q)}")
                    moved = True
                for g in W.GOALS.values():
                    for po in g.posts:
                        dd = q - po
                        nd = float(np.linalg.norm(dd))
                        if nd < W.R_PUCK + g.post_r:
                            nrm = dd / nd
                            q = po + nrm * (W.R_PUCK + g.post_r + W.EPS)
                            vn = float(v @ nrm)
                            if vn < 0:
                                v = v - vn * nrm
                                walls.append({"t": round(t, 5), "obstacle": "goal_post", "impact_mm_s": round(float(-vn), 1)})
                            hits.append("goal_post"); moved = True
                if not W.INSET.contains(Point(*q)):
                    b = W.INSET.exterior
                    qq = np.array(b.interpolate(b.project(Point(*q))).coords[0])
                    q, v = _wall(q, v, qq, "boards", t, walls)
                    hits.append("boards"); moved = True
                if not moved:
                    break
            for g in W.GOALS.values():
                if entered is None and g.crossed(p, q):
                    entered = g.end
                if entered == g.end:
                    lim = g.half - W.R_PUCK  # side nets from inside
                    if abs(q[1] - g.y) > lim:
                        q = np.array([q[0], g.y + math.copysign(lim, q[1] - g.y)]); v = np.array([v[0], 0.0])
                        hits.append("goal_net")
                    if g.sign * (q[0] - g.back_x) >= 0:
                        q = np.array([g.back_x, q[1]]); v = np.zeros(2); in_net = True
                        hits.append("goal_net")
                elif g.cage_out.contains(Point(*q)) and not ((not g.beyond_line(p[0])) and abs(q[1] - g.y) < g.half - W.R_PUCK):
                    cq = g.cage_out.exterior if g.cage_out.geom_type == "Polygon" else max(g.cage_out.geoms, key=lambda x: x.area).exterior
                    qq = np.array(cq.interpolate(cq.project(Point(*q))).coords[0])
                    q, v = _wall(q, v, qq, "goal_cage", t, walls)
                    hits.append("goal_cage")
            p = q
        T.append(t); P.append(p.copy()); V.append(v.copy()); touching.append(tuple(sorted(set(hits))))
    return np.array(T), np.array(P), np.array(V), touching, impulses, walls, entered
