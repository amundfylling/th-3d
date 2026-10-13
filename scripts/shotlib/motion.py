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

Solved meets (`meets` in the move file, scripts/shotlib/build.py solve_meets): the figure meets the puck where the puck
really is. A meet names a point on the figure (local mm) where the puck centre must be at the meet; the build finds the
time and slot position at which that holds on the puck's actual path. Values may then refer to the meet:
- a time {"meet": name, "offset": s} (the meet time plus offset);
- an arc {"meet": name, "offset": mm} (the slot position at the meet plus offset);
- a slot speed {"meet": name, "puck_along_slot": true, "scale": k, "offset": mm/s} (k times the puck's velocity along
  the slot at the meet, plus offset: e.g. a give-way or a push that starts just faster than the puck slides).

Controlled contacts (`controls`, scripts/shotlib/control.py) take a figure over from the design for one contact; the
design goes on from where the controller left the figure: a time, arc or heading {"control_end": pid, "offset": x}.
"""
import numpy as np

from . import world as W


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


TRIG = {}  # resolved trigger times (s), set by build.simulate
MEET = {}  # solved meets: name -> {"t", "arc_mm", "puck_along_slot_mm_s"}, set by build.solve_meets
CTRL_END = {}  # where a controlled figure was left: pid -> {"t", "arc_mm", "theta_deg"}, set by scripts/shotlib/control.py


def tv(x, start=None):
    """A time value: a number, {"trigger": name, "offset": s}, {"meet": name, "offset": s} or, for an end, {"dur": s}
    after `start`."""
    if isinstance(x, dict):
        if "dur" in x:
            return start + x["dur"]
        if "meet" in x:
            return MEET[x["meet"]]["t"] + x.get("offset", 0.0)
        if "control_end" in x:
            return CTRL_END[x["control_end"]]["t"] + x.get("offset", 0.0)
        return TRIG[x["trigger"]] + x.get("offset", 0.0)
    return x


def thv(x):
    """A heading value (deg): a number or {"control_end": pid, "offset": deg} (where the controller left it)."""
    if isinstance(x, dict):
        return CTRL_END[x["control_end"]]["theta_deg"] + x.get("offset", 0.0)
    return x


def av(x):
    """An arc value (mm): a number or {"meet": name, "offset": mm}."""
    if isinstance(x, dict):
        if "control_end" in x:
            return CTRL_END[x["control_end"]]["arc_mm"] + x.get("offset", 0.0)
        return MEET[x["meet"]]["arc_mm"] + x.get("offset", 0.0)
    return x


def vv(x):
    """A slot speed (mm/s): a number or {"meet": name, "puck_along_slot": true, "scale": k, "offset": mm/s}."""
    if isinstance(x, dict):
        m = MEET[x["meet"]]
        return x.get("scale", 1.0) * (m["puck_along_slot_mm_s"] if x.get("puck_along_slot") else 0.0) + x.get("offset", 0.0)
    return x


def _turns(th):
    segs = th.get("turns", th.get("segments", []))
    return [[tv(s[0]), s[1], thv(s[2]), thv(s[3])] + [s[4] if len(s) > 4 else "designed turn"] for s in segs]


def theta_keys(th, t0):
    """Theta keyframes: holds and smootherstep turns, sampled every 2 ms (scripts/ikv-trace.py theta_track)."""
    segs = _turns(th)
    if not segs:
        return [{"t": t0, "theta_deg": thv(th["start"]), "sigma_deg": None, "source": "designed: held"}]
    ks = [(t0, thv(th.get("start", segs[0][2])), "designed: start heading")]
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
    ks = [{"t": round(tv(k[0]), 5), "arc_mm": round(av(k[1]), 4), "sigma_mm": None, "source": "designed: " + (k[2] if len(k) > 2 else "held")} for k in arc.get("keys", [])]
    for t0_, t1_, a0, v0, a1, v1, *why in arc.get("moves", []):
        t0_ = tv(t0_); t1_ = tv(t1_, t0_)
        ks += [{"t": t, "arc_mm": a, "sigma_mm": None, "source": "designed: " + (why[0] if why else "slot move")} for t, a in quintic(t0_, t1_, av(a0), vv(v0), av(a1), vv(v1))]
    ks = sorted(ks, key=lambda k: k["t"])
    for a, b in zip(ks, ks[1:]):
        if b["t"] <= a["t"]:
            raise ValueError(f"arc keys out of order or repeated at t = {b['t']} s (a meet moved a key past another one)")
    return ks


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
