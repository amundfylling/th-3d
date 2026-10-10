"""Figure motion from a move file: holds, smooth turns, slot moves and turning with the slot.

Every figure is rigid (CLAUDE.md rule 5): a slot position (arc, mm) and a rotation (theta, deg, relative to the team's
home heading). The primitives below only write keyframes; src/model/trace.ts plays them back exactly (monotone cubic
for the arc, linear for theta, so turns are sampled every 2 ms and slot moves every 5 ms).

Move-file forms (moves/<id>/move.json, `figures.<pid>`), all times in s, arcs in mm, angles in deg:
- {"static": {"arc_mm": a, "theta_deg": th}}           a figure that does not move
- {"static": {"y_mm": y, "theta_deg": th}}             the same, placed by its y (goalies)
- {"static": "assembly"}                               the static assembly pose (validation/16-assembly-poses.json)
- moving:
  "arc": {"keys": [[t, arc, why], ...],                held positions (monotone cubic between them)
          "moves": [[t0, t1, a0, v0, a1, v1, why], ...]}  a quintic slot move: end positions, end speeds (mm/s),
                                                          zero end accelerations, sampled every 5 ms
  "theta": {"start": th0,                              heading before the first turn (default: the first turn's from)
            "turns": [[t_start, duration, from, to, why], ...]}  smootherstep turns (sampled every 2 ms)
  "follow_tangent_from_s": t                           from t on, the player also turns the figure with the slot's
                                                          tangent (a designed rod rotation, not an automatic one; rule 6)
Older files may give a turn without `why` and `theta.segments` instead of `theta.turns`.

Reactive timing: any start time (a key's t, a move's t0, a turn's t_start, follow_tangent_from_s) may instead be
{"trigger": name, "offset": s}, and a move's end {"dur": s}: the figure then starts when something happens to the puck,
as a player reacts (scripts/shotlib/build.py resolves the triggers by re-running the puck until they settle).
"""
import numpy as np

from . import world as W


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


TRIG = {}  # resolved trigger times (s), set by build.simulate


def tv(x, start=None):
    """A time value: a number, {"trigger": name, "offset": s} or, for an end, {"dur": s} after `start`."""
    if isinstance(x, dict):
        if "dur" in x:
            return start + x["dur"]
        return TRIG[x["trigger"]] + x.get("offset", 0.0)
    return x


def _turns(th):
    segs = th.get("turns", th.get("segments", []))
    return [[tv(s[0])] + list(s[1:4]) + [s[4] if len(s) > 4 else "designed turn"] for s in segs]


def theta_keys(th, t0):
    """Theta keyframes: holds and smootherstep turns, sampled every 2 ms (scripts/ikv-trace.py theta_track)."""
    segs = _turns(th)
    if not segs:
        return [{"t": t0, "theta_deg": th["start"], "sigma_deg": None, "source": "designed: held"}]
    ks = [(t0, th.get("start", segs[0][2]), "designed: start heading")]
    for ts, d, a, b, why in segs:
        ks.append((ts, a, "designed: " + why))
        n = max(2, int(round(d / 0.002)))
        for k in range(1, n + 1):
            ks.append((ts + d * k / n, a + (b - a) * smooth(k / n), "designed: " + why))
    out = {}
    for t, v, why in ks:
        out[round(t, 5)] = (v, why)
    return [{"t": t, "theta_deg": round(v, 4), "sigma_deg": None, "source": why} for t, (v, why) in sorted(out.items())]


def quintic(t0, t1, a0, v0, a1, v1, dt=0.005):
    """Arc keys (every 5 ms) of the quintic move with the given end positions (mm) and velocities (mm/s) and zero end
    accelerations."""
    T = t1 - t0
    A = np.array([[T**3, T**4, T**5], [3 * T**2, 4 * T**3, 5 * T**4], [6 * T, 12 * T**2, 20 * T**3]])
    c3, c4, c5 = np.linalg.solve(A, np.array([a1 - a0 - v0 * T, v1 - v0, 0.0]))
    n = max(1, int(round(T / dt)))
    return [[round(t0 + T * k / n, 5), round(float(a0 + v0 * (T * k / n) + c3 * (T * k / n) ** 3 + c4 * (T * k / n) ** 4 + c5 * (T * k / n) ** 5), 4)] for k in range(1, n + 1)]


def arc_keys(arc):
    ks = [{"t": tv(k[0]), "arc_mm": k[1], "sigma_mm": None, "source": "designed: " + (k[2] if len(k) > 2 else "held")} for k in arc.get("keys", [])]
    for t0_, t1_, a0, v0, a1, v1, *why in arc.get("moves", []):
        t0_ = tv(t0_); t1_ = tv(t1_, t0_)
        ks += [{"t": t, "arc_mm": a, "sigma_mm": None, "source": "designed: " + (why[0] if why else "slot move")} for t, a in quintic(t0_, t1_, a0, v0, a1, v1)]
    return sorted(ks, key=lambda k: k["t"])


def build_figure(pid, spec, t0, t1):
    """One figure of a move file -> world.Figure (moving or static on its slot) or world.Static (assembly pose)."""
    status = spec.get("status", "")
    st = spec.get("static")
    if st == "assembly":
        return W.assembly_figure(pid)
    if st is not None:
        slot = W.Slot(pid)
        a = st["arc_mm"] if "arc_mm" in st else slot.arc_of_y(st["y_mm"])
        src = "designed: " + st.get("why", "static")
        return W.Figure(pid, [{"t": t0, "arc_mm": round(float(a), 3), "sigma_mm": None, "source": src}],
                        [{"t": t0, "theta_deg": st["theta_deg"], "sigma_deg": None, "source": src}], status or "static (designed)")
    arcs = arc_keys(spec["arc"]) if "arc" in spec else [{"t": t0, "arc_mm": spec["arc_mm"], "sigma_mm": None, "source": "designed: held"}]
    thetas = theta_keys(spec["theta"], t0)
    base = W.Figure(pid, arcs, thetas, status)
    tc = spec.get("follow_tangent_from_s")
    tc = tv(tc) if tc is not None else None
    if tc is None:
        return base
    # the player turns the figure with the slot tangent from tc on (scripts/ikv-trace.py lw_figure)
    segs = _turns(spec["theta"])
    tan0 = base.slot.tangent_deg(base.arc(tc))
    t_end = max([s_[0] + s_[1] for s_ in segs] + [k["t"] for k in arcs])
    grid = np.arange(min(s_[0] for s_ in segs), t_end + 1e-9, 0.002)
    times = sorted(set([round(t0, 5)] + [round(x, 5) for x in grid] + [round(t_end, 5), round(t1, 5)]))
    th = []
    for t in times:
        v = base.theta(t) + ((base.slot.tangent_deg(base.arc(t)) - tan0) if t >= tc else 0.0)
        th.append({"t": t, "theta_deg": round(v, 4), "sigma_deg": None, "source": "designed" + (": turned with the slot tangent" if t >= tc else "")})
    return W.Figure(pid, arcs, th, status)
