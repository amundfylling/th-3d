"""Figures steered from the puck's state: the player meets the puck where it is and aims (move file `controls`).

A designed motion is open loop: every figure moves on a fixed clock, so a tiny change of an input changes where the
puck meets the blade, and a push that sweeps the blade fast turns that into a different direction (the v2 IKV shot left
at 37 or 45 deg depending on a 0.001 mm change). A controlled figure instead reads the puck's position and velocity every
control tick (2 ms) and sets its own next pose, as a player does by eye and feel:

    aimed_push: the blade face pushes the puck toward an aim point at a target speed.
      - push direction n = the direction of (v_target - v_puck): every touch then removes velocity error along n only,
        so the puck ends up travelling at the target speed toward the aim, whatever it arrived with;
      - heading: the face's outward normal points along n;
      - slot position: the face sits `closing` deeper than touching at the puck's predicted position, so the blade
        keeps closing on the puck at a low speed (a push of many small touches, CLAUDE.md "Slide or bounce");
      - release: once the puck moves at least as fast as the target along n, the figure stops pushing and slows
        down along its slot (the puck runs on alone).
    Turn rate, slot speed and slot acceleration are limited (move file); a figure that cannot reach the puck simply
    misses it, and the checks report that.

Keyframes are causal: the controller commits the pose two ticks ahead, so the monotone cubic (arc) and linear (theta)
playback of src/model/trace.ts reproduces, between any two keys, exactly the motion the puck was simulated against.
The trace stores only the resulting keyframes; the playback never runs the controller (CLAUDE.md rule 7).
"""
import math

import numpy as np
from shapely.geometry import Point
from shapely.geometry.polygon import orient

from . import motion
from . import world as W

TICK = 0.0005  # control tick (s): a key every 0.5 ms (two simulation steps)


class LiveFigure(W.Figure):
    """A figure whose keyframes are appended while the puck is simulated (scripts/shotlib/world.py Figure)."""

    def append(self, t, arc, theta, why):
        self.arcs.append({"t": round(t, 5), "arc_mm": round(float(arc), 4), "sigma_mm": None, "source": "controlled: " + why})
        self.thetas.append({"t": round(t, 5), "theta_deg": round(float(theta), 4), "sigma_deg": None, "source": "controlled: " + why})
        self.ax = np.append(self.ax, self.arcs[-1]["t"]); self.ay = np.append(self.ay, self.arcs[-1]["arc_mm"])
        self.tx = np.append(self.tx, self.thetas[-1]["t"]); self.ty = np.append(self.ty, self.thetas[-1]["theta_deg"])
        self.am = W.pchip_slopes(self.ax, self.ay)


def blade_boundary(kind, y_min, step=0.2):
    """Points of the blade's outline (figure frame, the part beyond local y = y_min: back face, tip, front face) every
    `step` mm, with their outward unit normals."""
    low = W.LOW[kind]
    poly = max(([low] if low.geom_type == "Polygon" else list(low.geoms)), key=lambda g: g.bounds[3])
    ring = np.array(orient(poly, 1.0).exterior.coords)[:-1]
    k0 = int(np.argmin(ring[:, 1]))
    ring = np.vstack([ring[k0:], ring[:k0], ring[k0:k0 + 1]])
    seg = np.diff(ring, axis=0)
    sl = np.hypot(seg[:, 0], seg[:, 1])
    s_ = np.r_[0, np.cumsum(sl)]
    ss = np.arange(0, s_[-1], step)
    pts = np.c_[np.interp(ss, s_, ring[:, 0]), np.interp(ss, s_, ring[:, 1])]
    # outward normal of a counter-clockwise ring: the edge direction turned clockwise; smoothed over +-0.3 mm
    d = np.gradient(pts, axis=0)
    nrm = np.c_[d[:, 1], -d[:, 0]]
    k = np.ones(7) / 7
    nrm = np.c_[np.convolve(np.r_[nrm[-3:, 0], nrm[:, 0], nrm[:3, 0]], k, "valid"), np.convolve(np.r_[nrm[-3:, 1], nrm[:, 1], nrm[:3, 1]], k, "valid")]
    nrm /= np.linalg.norm(nrm, axis=1)[:, None]
    keep = pts[:, 1] > y_min
    return pts[keep], nrm[keep]


def aim_point(a):
    if isinstance(a, dict) and "goal" in a:
        g = W.GOALS[a["goal"]]
        return np.array([g.x, g.y + a.get("y_mm", 0.0)])
    return np.asarray(a, float)


def _slot_offsets(slot, w, near=None, span=80.0):
    """Vectorised scripts/shotlib/build.py _slot_offset: arcs and signed lateral offsets of the points w (N x 2); with
    `near`, only the part of the slot within `span` mm of that arc is searched."""
    i0, i1 = 0, len(slot.P) - 1
    if near is not None:
        i0 = max(0, int(np.searchsorted(slot.s, near - span)) - 1)
        i1 = min(len(slot.P) - 1, int(np.searchsorted(slot.s, near + span)) + 1)
    A, d = slot.P[i0:i1], slot.P[i0 + 1:i1 + 1] - slot.P[i0:i1]
    S = slot.s[i0:i1]
    L2 = (d * d).sum(1)
    rel = w[:, None, :] - A[None, :, :]
    u = np.clip((rel * d[None]).sum(2) / L2[None], 0.0, 1.0)
    q = A[None] + u[..., None] * d[None]
    dist2 = ((w[:, None, :] - q) ** 2).sum(2)
    i = np.argmin(dist2, axis=1)
    r = np.arange(len(w))
    arc = S[i] + u[r, i] * np.sqrt(L2[i])
    side = d[i, 0] * (w[:, 1] - q[r, i, 1]) - d[i, 1] * (w[:, 0] - q[r, i, 0])
    return arc, np.sign(side) * np.sqrt(dist2[r, i])


class AimedPush:
    def __init__(self, spec, fig, t_start):
        self.spec, self.f = spec, fig
        self.L, self.N = blade_boundary(fig.kind, spec.get("blade_from_y_mm", 20.0))
        self.angN = np.arctan2(self.N[:, 1], self.N[:, 0])
        self.aim = aim_point(spec["aim"])
        self.speed = spec["speed_mm_s"]
        self.closing = spec.get("closing_mm_s", [5.0, 60.0])
        self.approach_max = spec.get("approach_max_mm_s", 80.0)    # closing speed allowed at touching...
        self.gain = spec.get("approach_gain_1_s", 150.0)            # ...plus this much per mm of gap
        self.w_max = spec.get("max_turn_deg_s", 300.0)          # near the puck (a turn moves the blade into it)
        self.w_far = spec.get("max_turn_far_deg_s", self.w_max)  # with at least `w_far_gap` mm to the puck
        self.w_far_gap = spec.get("turn_far_gap_mm", 3.0)
        self.ramp = spec.get("speed_ramp_mm_s")                 # None: aim straight at the target velocity
        self.v_max = spec.get("max_arc_speed_mm_s", 2000.0)
        self.a_max = spec.get("max_arc_accel_mm_s2", 200000.0)
        self.a_stop = spec.get("stop_accel_mm_s2", 100000.0)
        self.tol = spec.get("release_tol_mm_s", 20.0)
        self.tol_rel = spec.get("release_tol_rel", 0.05)
        self.t_end = t_start + spec.get("max_duration_s", 0.25)
        self.t_s = t_start
        # the designed motion runs to t_start; one key a tick later continues it (so the slope at t_start is the
        # design's), then the controller takes over
        a0, h0 = fig.arc(t_start), fig.theta(t_start)
        v0 = (fig.arc(t_start) - fig.arc(t_start - 1e-4)) / 1e-4
        fig.arcs = [k for k in fig.arcs if k["t"] < t_start - 1e-9]; fig.thetas = [k for k in fig.thetas if k["t"] < t_start - 1e-9]
        LiveFigure.__init__(fig, fig.pid, fig.arcs, fig.thetas, fig.status)
        fig.append(t_start, a0, h0, "takes over at the meet")
        fig.append(t_start + TICK, a0 + v0 * TICK, h0, "takes over at the meet")
        self.j = 0                      # next tick to decide: key j + 2
        self.released, self.done = None, False
        self.design = None
        self.log = []

    def step(self, t, p, v):
        """Called before every simulation step at time t with the puck state at t - DT."""
        if self.done:
            return
        while not self.done and t > self.t_s + self.j * TICK - 1e-9:
            self._decide(self.t_s + self.j * TICK, p, v)
            self.j += 1

    def _pose_for(self, q, n, th_prev, a_prev):
        """Theta and arc that put a point of the blade outline at q (world) with its outward normal along n: for every
        outline point the heading is fixed by the normal, and the pivot must lie on the slot centreline; the root
        nearest the current pose wins (None if the blade cannot reach)."""
        f = self.f
        phi = math.atan2(n[1], n[0]) - self.angN
        c, s_ = np.cos(phi), np.sin(phi)
        piv = q[None, :] - np.c_[c * self.L[:, 0] - s_ * self.L[:, 1], s_ * self.L[:, 0] + c * self.L[:, 1]]
        arc, lat = _slot_offsets(f.slot, piv, a_prev)
        th = np.degrees(phi) - W.HOME[f.team]
        th = th_prev + ((th - th_prev + 180.0) % 360.0 - 180.0)
        best = None
        for i in np.nonzero(lat[:-1] * lat[1:] <= 0)[0]:
            if abs(th[i + 1] - th[i]) > 5 or not (0.0 < arc[i] < f.slot.length):
                continue
            w = lat[i] / (lat[i] - lat[i + 1]) if lat[i] != lat[i + 1] else 0.0
            cand = (th[i] + w * (th[i + 1] - th[i]), arc[i] + w * (arc[i + 1] - arc[i]))
            cost = abs(cand[0] - th_prev) / self.w_max + abs(cand[1] - a_prev) / self.v_max
            if best is None or cost < best[0]:
                best = (cost, cand)
        return best[1] if best else None

    def _clear(self, a, h, q):
        """Clearance (mm) between the puck at q and the figure posed at arc a, theta h (world.clearance)."""
        f = self.f
        loc = W.rot(W.HOME[f.team] + h).T @ (q - f.slot.at(a))
        pt = Point(*loc)
        low = W.LOW[f.kind]
        d = low.boundary.distance(pt)
        return (-d if low.contains(pt) else d) - W.R_PUCK

    def _arc_for_gap(self, h, q, gap, a_guess):
        """Arc nearest a_guess at which the clearance to the puck at q is `gap` (a_guess if none within 20 mm)."""
        g = lambda a: self._clear(a, h, q) - gap
        grid = a_guess + np.arange(-20.0, 20.01, 0.5)
        grid = grid[(grid >= 0) & (grid <= self.f.slot.length)]
        vals = [g(a) for a in grid]
        roots = [i for i in range(len(grid) - 1) if vals[i] * vals[i + 1] <= 0]
        if not roots:
            return a_guess
        i = min(roots, key=lambda i: abs(grid[i] - a_guess))
        lo, hi, glo = grid[i], grid[i + 1], vals[i]
        for _ in range(30):
            mid = 0.5 * (lo + hi)
            gm = g(mid)
            if gm * glo <= 0:
                hi = mid
            else:
                lo, glo = mid, gm
        return 0.5 * (lo + hi)

    def _decide(self, tj, p, v):
        f = self.f
        tk = tj + 2 * TICK
        a1, a0 = f.ay[-1], f.ay[-2]
        h1 = f.ty[-1]
        v_prev = (a1 - a0) / TICK
        why = self.spec.get("why", "aimed push")
        if self.released is None:
            u = self.aim - p
            u = u / np.linalg.norm(u)
            # the target speed is approached in steps of `ramp`, so the direction is set before the speed (the blade
            # cannot remove a sideways error once the puck is already as fast as the target)
            v_des = u * (self.speed if self.ramp is None else min(self.speed, max(float(v @ u), 0.0) + self.ramp))
            dv = v_des - v
            # done when the puck is within the tolerance of the target velocity, or when what is left could only be
            # removed by pushing across or against the aim (the blade pushes from behind, it does not flick)
            if np.linalg.norm(dv) < max(self.tol, self.tol_rel * self.speed) or float(dv @ u) <= np.cos(np.radians(75.0)) * float(np.linalg.norm(dv)) or tj >= self.t_end:
                self.released = round(tj, 5)
            else:
                n = dv / np.linalg.norm(dv)
                # the blade may close on the puck at most `approach_max` and press at most `closing` deeper than touching
                p_mid = p + v * (tk - TICK - tj + W.DT)
                gap = W.clearance(f, tk - TICK, p_mid)
                # gentler as the error shrinks: a touch adds up to (1 + e) x the closing speed, so the last touches
                # stay below the remaining error instead of overshooting it
                err = float(np.linalg.norm(dv))
                close = min(self.closing[1], max(self.closing[0], 0.25 * err))
                approach = min(self.approach_max, 0.25 * err)
                g_t = max(gap - (approach + self.gain * max(gap, 0.0)) * TICK, -close * TICK)
                p_hat = p + v * (tk - tj + W.DT)
                pose = None
                # the blade cannot push every way from where it is (a puck against the boards can only be pushed at a
                # shallow angle off them): push along the nearest direction it can reach that still reduces the error
                n0 = math.atan2(n[1], n[0])
                for dk in [0] + [s_ * k for k in range(1, 31) for s_ in (1, -1)]:
                    a_ = n0 + math.radians(2.0 * dk)
                    m = np.array([math.cos(a_), math.sin(a_)])
                    if float(m @ dv) <= 0 or float(m @ u) < np.cos(np.radians(75.0)):
                        continue
                    pose = self._pose_for(p_hat - m * (W.R_PUCK + W.EPS + g_t), m, h1, a1)
                    if pose:
                        n = m
                        break
                if pose is None:
                    # no push the blade can reach from where it is would bring the puck nearer the target: let it go
                    # (before 2026-10-11 the blade kept chasing the gap and struck the puck sideways)
                    self.released = round(tj, 5)
                    return self._decide(tj, p, v)
                h_t, a_t = pose
                w_lim = self.w_max if gap < self.w_far_gap else self.w_far   # turn fast only clear of the puck
                h = h1 + max(-w_lim * TICK, min(w_lim * TICK, h_t - h1))
                # with the heading it can reach, the slot position that leaves exactly the planned gap to the puck
                a_t = self._arc_for_gap(h, p_hat, g_t, a_t)
                v_new = (a_t - a1) / TICK
                v_new = max(v_prev - self.a_max * TICK, min(v_prev + self.a_max * TICK, v_new))
                v_new = max(-self.v_max, min(self.v_max, v_new))
                f.append(tk, a1 + v_new * TICK, h, why)
                self.log.append({"t": round(tk, 5), "push_dir_deg": round(math.degrees(math.atan2(n[1], n[0])), 2),
                                 "velocity_error_mm_s": round(float(np.linalg.norm(dv)), 1), "reached": pose is not None,
                                 "gap_mm": round(gap, 3), "planned_gap_mm": round(g_t, 3), "theta_deg": round(h, 3), "arc_speed_mm_s": round(v_new, 1)})
                return
        # released: the figure slows down along its slot and holds its heading
        dv_ = max(-self.a_stop * TICK, min(self.a_stop * TICK, -v_prev))
        v_new = v_prev + dv_
        f.append(tk, a1 + v_new * TICK, h1, "slows down after the release")
        if abs(v_new) < 1e-6:
            self.done = round(tk, 5)
            self._hand_back(tk, f.ay[-1], h1)

    def _hand_back(self, tk, arc, theta):
        """The design goes on from where the controller left the figure (motion.CTRL_END): its keys after tk."""
        if self.design is None:
            return
        motion.CTRL_END[self.f.pid] = {"t": round(tk, 5), "arc_mm": float(arc), "theta_deg": float(theta)}
        g = motion.build_figure(self.f.pid, self.design, *self.window)
        ka = [k for k in g.arcs if k["t"] > tk + 1e-9]
        kt = [k for k in g.thetas if k["t"] > tk + 1e-9]
        f = self.f
        f.arcs += ka; f.thetas += kt
        LiveFigure.__init__(f, f.pid, f.arcs, f.thetas, f.status)


TYPES = {"aimed_push": AimedPush}


def make(spec, figs, only=None):
    """Controllers for a move file's `controls`; each turns its figure into a LiveFigure from its start time on and
    hands it back to the design when it is done."""
    out = []
    for c in spec.get("controls", []):
        if only is not None and c["figure"] not in only:
            continue
        f = figs[c["figure"]]
        f.__class__ = LiveFigure
        ctl = TYPES[c["type"]](c, f, round(motion.tv(c["start"]), 5))
        ctl.design, ctl.window = spec["figures"][c["figure"]], spec["window_s"]
        out.append(ctl)
    return out
