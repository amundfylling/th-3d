"""Edwall long shovel (Nygård, NM26 game 2, goals 2-4): one contact-checked motion trace per goal, rebuilt from the
broadcast (figure tracks, puck readings) with the occluded moves designed. docs/rebuild-g2-edwall-v2.md.

    /root/venvs/blender/bin/python scripts/edwall-trace.py <goal_id> [--fit] [--quick]

Inputs:
- shots/edwall/<goal_id>.inputs.json: the window, the designed moves of the passer (W-RW) and the shooter (W-C) and
  their fitted parameters, the contact and slide-rule parameters;
- shots/edwall/puck-readings.json (hand readings; scripts/edwall-observe.py turns the pixel readings into world mm);
- the puck detector's track inputs.observations.puck_track (data/games/nm26-semifinal/g2/puck-track-synth.json, PROPOSED;
  x/y = the puck centre): when inputs.observations is set, its detections are the puck observations (hand readings only
  where it has none), and its slow detections before the play give the rest position (inputs.rest_mode "readings");
- the figure tracks (scripts/nm26_tracks.py: data/games/nm26-semifinal/g2/figure-tracks-v3.json, PROPOSED): all other
  figures, the rest poses, and (inputs.figure_constraints) the passer's and shooter's own readings inside their moves;
- geometry, preview goal, figure meshes (helpers from scripts/spjass-trace.py).
Outputs: data/traces/edwall-<goal_id>.trace.json, shots/edwall/<goal_id>.checks.json, validation/edwall-<goal_id>-trace.png.

Puck rules (as scripts/ikv-trace.py; no general simulator, every change in its motion has a named cause), every 0.25 ms:
ice friction (constant deceleration, spjass slide fit); figure contact (all 12 figures' low geometry: moved out to
touching, collision impulse along the normal with restitution e when approaching, frictionless); boards and posts
(inelastic, slides along them); goal cage from outside (inelastic), side nets from inside, back net stops it.
--fit: fits the designed parameters (Nelder-Mead) to the puck readings, the goal timing and the slide rule, and writes
them into the inputs file under "fitted". With inputs.figure_constraints the fit also matches the moving figure's own
track readings (src 0), with inputs.carry_force_weight it penalises carries that need a pull (carry_force_check), and
with inputs.shovel_part it penalises a shovel caught by another part of the centre. --quick: run and print the summary
only (no files).
"""
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
_spec = importlib.util.spec_from_file_location("spjass_trace", REPO / "scripts/spjass-trace.py")
sp = importlib.util.module_from_spec(_spec)
_argv = sys.argv[:]
sys.argv = sys.argv[:1]
_spec.loader.exec_module(sp)  # helpers only
sys.argv = _argv
from edwall_common import crop_to_world, tracks  # noqa: E402
from nm26_tracks import FIGURE_TRACKS, slow_flags  # noqa: E402

GID = sys.argv[1]
FIT, QUICK = "--fit" in sys.argv, "--quick" in sys.argv
STAGE = sys.argv[sys.argv.index("--fit") + 1] if FIT else None  # "pass" or "shot"
INP_PATH = REPO / f"shots/edwall/{GID}.inputs.json"
INP = json.loads(INP_PATH.read_text())
READ = json.loads((REPO / "shots/edwall/puck-readings.json").read_text())
SPJ = json.loads((REPO / "data/traces/spjass.trace.json").read_text())
SPJ_CHECKS = json.loads((REPO / "shots/spjass/checks.json").read_text())
OUT_TRACE = REPO / f"data/traces/edwall-{GID}.trace.json"
OUT_CHECKS = REPO / f"shots/edwall/{GID}.checks.json"
OUT_PNG = REPO / f"validation/edwall-{GID}-trace.png"
DT, EPS, PEN_TOL, R_PUCK = sp.DT, sp.EPS, sp.PEN_TOL, sp.R_PUCK
A_FRIC = SPJ_CHECKS["slide_fit"]["deceleration_mm_s2"]
INSET = sp.BOARD.buffer(-R_PUCK)
INSET_RING = INSET.exterior
CAGE_WALLS = LineString([(sp.GX, sp.GY - sp.HALF), (sp.GX + sp.DEPTH, sp.GY - sp.HALF), (sp.GX + sp.DEPTH, sp.GY + sp.HALF), (sp.GX, sp.GY + sp.HALF)])
CAGE_OUT = CAGE_WALLS.buffer(R_PUCK, 32)
CAGE_RING = CAGE_OUT.exterior
REACH = {k: max(math.hypot(x, y) for g in ([v] if v.geom_type == "Polygon" else v.geoms) for x, y in g.exterior.coords) + R_PUCK + 2.0 for k, v in sp.LOW.items()}
E_FIG = INP["contact"]["restitution_figure"]
LABEL = READ["goals"][GID]["label_frame"]
FPS = 30.0
F0 = LABEL + INP["window_frames"][0]  # trace time t = (frame - F0) / 30
T1 = (INP["window_frames"][1] - INP["window_frames"][0]) / FPS
fr_t = lambda f: (f - F0) / FPS
NSTEP = int(round(T1 / DT))
TGRID = np.arange(NSTEP + 1) * DT


def smooth(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * u * (u * (u * 6 - 15) + 10)


# ---------------------------------------------------------------- observations
OBS = []
for f, x, y, kind in READ["goals"][GID]["readings"]:
    if x is None:
        continue
    w = crop_to_world([x, y], READ["z_mm"])[0]
    OBS.append({"frame": f, "t": round(fr_t(f), 5), "px": [x, y], "world_mm": [round(float(w[0]), 2), round(float(w[1]), 2)], "kind": kind})
OBS_CFG = INP.get("observations")
if OBS_CFG:  # the detector track: its detections replace the hand readings on the same frames
    _PT = json.loads((REPO / OBS_CFG["puck_track"]).read_text()); _pc = _PT["columns"]
    _slow = dict(zip((r[0] for r in _PT["rows"]), slow_flags(_PT)))
    a, b = LABEL + OBS_CFG["frames"][0], LABEL + OBS_CFG["frames"][1]
    det = [r for r in _PT["rows"] if a <= r[0] <= b and r[_pc.index("score")] >= OBS_CFG["min_score"]]
    dfr = {r[0] for r in det}
    OBS = [o for o in OBS if o["frame"] not in dfr]
    for r in det:
        OBS.append({"frame": r[0], "t": round(fr_t(r[0]), 5), "px": [r[_pc.index("u_stab_px")], r[_pc.index("v_stab_px")]],
                    "world_mm": [r[_pc.index("x_mm")], r[_pc.index("y_mm")]], "kind": "det_rest" if _slow[r[0]] else "det", "score": r[_pc.index("score")]})
    OBS.sort(key=lambda o: o["frame"])
REST = [o for o in OBS if o["kind"] in ("rest", "det_rest") and LABEL + INP["rest_from_frame"] <= o["frame"] < LABEL + INP.get("rest_to_frame", 0)]
MOVING = [o for o in OBS if o["kind"] in ("streak", "flight", "det") and o["frame"] <= LABEL + INP.get("obs_to_frame", 10 ** 6)]
PASS_TO = LABEL + INP.get("pass_obs_to_frame", 10 ** 6)  # moving observations after this frame belong to the shot stage
HIDDEN = [f for f, x, y, k in READ["goals"][GID]["readings"] if x is None]


def obs_weight(o):
    if o["kind"] == "streak":
        return INP["fit"]["weight_streak"]
    if o["kind"] == "det":
        return 1.0 if o["score"] >= OBS_CFG["full_weight_score"] else OBS_CFG["weight_low_score"]
    return 1.0


# ---------------------------------------------------------------- figures
# v1 inputs (no trace_version) keep the figure tracks they were fitted on; v2 reads the selected tracks
FIG_FILE = INP.get("figure_tracks", FIGURE_TRACKS if INP.get("trace_version") else "figure-tracks-smooth.json")
TR = tracks(GID, FIG_FILE)
SLOTS = {pid: sp.Slot(pid) for pid in sp.ASM}


def tracked_keys(pid):
    """Arc and theta keyframes from the cleaned tracks inside the window (frames with a known u)."""
    arcs, ths = [], []
    for f in sorted(TR):
        t = fr_t(f)
        if t < -1e-9 or t > T1 + 1e-9:
            continue
        u, th, src = TR[f][pid]
        if u is None:
            continue
        a = min(max(u, 0.0), 1.0) * SLOTS[pid].length
        why = "figure track (model reading, cleaned)" if src == 0 else "figure track (interpolated over a rejected reading)"
        arcs.append({"t": round(t, 5), "arc_mm": round(a, 3), "sigma_mm": None, "source": why})
        ths.append({"t": round(t, 5), "theta_deg": round(th, 2), "sigma_deg": None, "source": why})
    # theta continuity (tracks are wrapped to 0..360)
    for i in range(1, len(ths)):
        d = ths[i]["theta_deg"] - ths[i - 1]["theta_deg"]
        ths[i]["theta_deg"] = round(ths[i]["theta_deg"] - 360.0 * round(d / 360.0), 2)
    return arcs, ths


def track_median(pid, f_from, f_to):
    us = [TR[f][pid][0] for f in TR if f_from <= f <= f_to and TR[f][pid][0] is not None and TR[f][pid][2] == 0]
    ths = [TR[f][pid][1] for f in TR if f_from <= f <= f_to and TR[f][pid][0] is not None and TR[f][pid][2] == 0]
    return float(np.median(us)) * SLOTS[pid].length, float(np.median(ths))


def keys_from_profile(times, values, key, why):
    sk = "sigma_mm" if key == "arc_mm" else "sigma_deg"
    return [{"t": round(float(t), 5), key: round(float(v), 4), sk: None, "source": why} for t, v in zip(times, values)]


def profile(t0, segs, v0, step=0.002):
    """Holds and smootherstep moves: segs [[t_start, duration, to_value], ...] from v0. Returns (times, values)."""
    ts, vs = [0.0], [v0]
    cur = v0
    for s0, d, v1 in segs:
        ts.append(s0); vs.append(cur)
        n = max(2, int(round(d / step)))
        for k in range(1, n + 1):
            ts.append(s0 + d * k / n); vs.append(cur + (v1 - cur) * float(smooth(k / n)))
        cur = v1
    ts.append(T1); vs.append(cur)
    out = {}
    for t, v in zip(ts, vs):
        out[round(t, 5)] = v
    tt = sorted(out)
    return tt, [out[t] for t in tt]


def designed(p):
    """W-RW and W-C keyframes from the parameter vector p (dict)."""
    rw_a0, rw_th0 = p["rw_arc0"], p["rw_theta0"]
    t_back = max(p["rw_t_lunge"] + p["rw_d_lunge"], p["rw_t_release"]) + 0.02
    ta, va = profile(0, [[p["rw_t_lunge"], p["rw_d_lunge"], rw_a0 + p["rw_lunge_mm"]], [t_back, INP["rw_return"]["duration_s"], p["rw_arc_end"]]], rw_a0)
    t_tb = max(p["rw_t_turn"] + p["rw_d_turn"], p["rw_t_release"]) + 0.02
    tt, vt = profile(0, [[p["rw_t_turn"], p["rw_d_turn"], rw_th0 + p["rw_turn_deg"]], [t_tb, INP["rw_return"]["duration_s"], p["rw_theta_end"]]], rw_th0)
    rw = sp.Figure("W-RW", "W", "skater", keys_from_profile(ta, va, "arc_mm", "designed: lunge up the slot (smootherstep), fitted to the puck readings; then back to the tracked arc after the goal"),
                   keys_from_profile(tt, vt, "theta_deg", "designed: counter-clockwise turn that sweeps the puck off the board (smootherstep), fitted; then on to the tracked rotation after the goal"))
    wc_a0, wc_th0 = p["wc_arc0"], p["wc_theta0"]
    ta, va = profile(0, [[p["wc_t_lunge"], p["wc_d_lunge"], p["wc_arc1"]]], wc_a0)
    tt, vt = profile(0, [[p["wc_t_turn0"], p["wc_d_turn0"], wc_th0 + p["wc_turn0_deg"]], [p["wc_t_turn0"] + p["wc_d_turn0"] + p["wc_gap"], p["wc_d_shot"], wc_th0 + p["wc_turn0_deg"] + p["wc_shot_deg"]]], wc_th0)
    wc = sp.Figure("W-C", "W", "skater", keys_from_profile(ta, va, "arc_mm", "designed: lunge from the back to the front of the slot (smootherstep, stops at the travel stop)"),
                   keys_from_profile(tt, vt, "theta_deg", "designed: turn to meet the pass, then the shovel turn (smootherstep), fitted"))
    return rw, wc


def tracked_figures():
    figs = {}
    for pid in sp.ASM:
        if pid in ("W-RW", "W-C"):
            continue
        a, th = tracked_keys(pid)
        figs[pid] = sp.Figure(pid, pid[0], "goalie" if pid.endswith("-G") else "skater", a, th)
    return figs


class Sampled:
    """Pose of a figure sampled on the simulation grid (pivot, heading) for fast contact tests."""
    def __init__(self, f):
        self.f, self.pid, self.kind = f, f.pid, f.kind
        a = np.array([f.arc(t) for t in TGRID]); h = np.array([sp.HOME[f.team] + f.theta(t) for t in TGRID])
        P = f.slot.P; s = f.slot.s
        self.piv = np.c_[np.interp(np.clip(a, 0, f.slot.length), s, P[:, 0]), np.interp(np.clip(a, 0, f.slot.length), s, P[:, 1])]
        self.h = np.radians(h)

    def local(self, k, w):
        c, s_ = math.cos(self.h[k]), math.sin(self.h[k]); d = w - self.piv[k]
        return np.array([c * d[0] + s_ * d[1], -s_ * d[0] + c * d[1]])

    def world(self, k, loc):
        c, s_ = math.cos(self.h[k]), math.sin(self.h[k])
        return self.piv[k] + np.array([c * loc[0] - s_ * loc[1], s_ * loc[0] + c * loc[1]])


def part_of(kind, loc):
    q = Point(*loc)
    return "stick/blade" if sp.STICK[kind].distance(q) <= sp.LOW[kind].distance(q) + 0.3 else "skate/body"


# ---------------------------------------------------------------- simulation
def simulate(S, p_rest, k_end=None, carries=()):
    """carries: [{"pid", "t_from", "t_release"}]: inside [t_from, t_release) the first contact with that figure starts a
    groove carry (the puck stays at the touching point of the figure's frame and moves with it; the catch is logged as a
    touch with its relative normal speed); at t_release the puck leaves with that point's velocity. A carry from t = 0
    starts at rest (the puck already touching)."""
    k_end = NSTEP if k_end is None else k_end
    p, v = p_rest.copy(), np.zeros(2)
    P = np.zeros((k_end + 1, 2)); V = np.zeros((k_end + 1, 2)); touching = [()] * (k_end + 1)
    impulses, walls, carry_log = [], [], []
    in_net = entered = False
    P[0] = p
    byid = {g.pid: g for g in S}
    carry = None  # (figure, local point, release step)
    for c in carries:
        if c["t_from"] <= 0.0:
            g = byid[c["pid"]]; carry = (g, g.local(0, p), int(round(c["t_release"] / DT)))
            carry_log.append({"figure": g.pid, "t_catch": 0.0, "t_release": c["t_release"], "catch_impact_mm_s": 0.0, "local_mm": [round(float(x), 3) for x in carry[1]], "part": part_of(g.kind, carry[1])})
    for k in range(1, k_end + 1):
        hits = []
        if carry is not None:
            g, rl, kr = carry
            q = g.world(k, rl)
            if k >= kr:
                v = (g.world(k, rl) - g.world(k - 1, rl)) / DT
                carry = None
            else:
                v = (q - p) / DT
            hits.append(f"{g.pid}:{part_of(g.kind, rl)}")
            p = q
            P[k] = p; V[k] = v; touching[k] = tuple(hits)
            continue
        if not in_net:
            sp_ = math.hypot(v[0], v[1])
            if sp_ > 0:
                v = v * max(0.0, sp_ - A_FRIC * DT) / sp_
            q = p + v * DT
            for _ in range(3):
                moved = False
                for g in S:
                    if (q[0] - g.piv[k][0]) ** 2 + (q[1] - g.piv[k][1]) ** 2 > REACH[g.kind] ** 2:
                        continue
                    loc = g.local(k, q)
                    if not sp.LOW_OUT[g.kind].contains(Point(*loc)):
                        continue
                    best = min((r.interpolate(r.project(Point(*loc))) for r in sp.RINGS_OUT[g.kind]), key=lambda z: z.distance(Point(*loc)))
                    r_loc = np.array(best.coords[0])
                    q_new = g.world(k, r_loc)
                    nrm = q_new - q; nn = math.hypot(nrm[0], nrm[1])
                    nrm = nrm / nn if nn > 1e-12 else (q_new - g.piv[k]) / max(1e-9, float(np.linalg.norm(q_new - g.piv[k])))
                    v_fig = (g.world(k, r_loc) - g.world(k - 1, r_loc)) / DT
                    vn = float((v - v_fig) @ nrm)
                    t = k * DT
                    cw = next((c for c in carries if c["pid"] == g.pid and c["t_from"] <= t < c["t_release"]), None)
                    if cw is not None and not any(x["figure"] == g.pid and x["t_catch"] > 0 for x in carry_log):
                        impulses.append({"t": round(t, 5), "figure": g.pid, "part": part_of(g.kind, r_loc), "impact_mm_s": round(max(0.0, -vn), 1), "dv": None, "catch": True})
                        carry = (g, r_loc, int(round(cw["t_release"] / DT)))
                        carry_log.append({"figure": g.pid, "t_catch": round(t, 5), "t_release": cw["t_release"], "catch_impact_mm_s": round(max(0.0, -vn), 1),
                                          "relative_speed_mm_s": round(float(np.linalg.norm(v - v_fig)), 1), "local_mm": [round(float(x), 3) for x in r_loc], "part": part_of(g.kind, r_loc)})
                        v = v_fig
                        q = q_new; hits.append(f"{g.pid}:{part_of(g.kind, r_loc)}"); moved = False
                        break
                    if vn < 0:
                        v = v - (1 + E_FIG) * vn * nrm
                        impulses.append({"t": round(t, 5), "figure": g.pid, "part": part_of(g.kind, r_loc), "impact_mm_s": round(-vn, 1), "dv": round(-(1 + E_FIG) * vn, 1)})
                    q = q_new
                    hits.append(f"{g.pid}:{part_of(g.kind, r_loc)}")
                    moved = True
                if carry is not None:
                    break
                for po in sp.POSTS:
                    dd = q - po; nd = math.hypot(dd[0], dd[1])
                    if nd < R_PUCK + sp.POST_R:
                        nrm = dd / nd; q = po + nrm * (R_PUCK + sp.POST_R + EPS)
                        vn = float(v @ nrm)
                        if vn < 0:
                            v = v - vn * nrm; walls.append({"t": round(k * DT, 5), "obstacle": "goal_post", "impact_mm_s": round(-vn, 1)})
                        hits.append("goal_post"); moved = True
                if not INSET.contains(Point(*q)):
                    qq = np.array(INSET_RING.interpolate(INSET_RING.project(Point(*q))).coords[0])
                    nrm = qq - q; nd = math.hypot(nrm[0], nrm[1])
                    if nd > 1e-12:
                        nrm = nrm / nd; vn = float(v @ nrm)
                        if vn < 0:
                            v = v - vn * nrm; walls.append({"t": round(k * DT, 5), "obstacle": "boards", "impact_mm_s": round(-vn, 1)})
                    q = qq; hits.append("boards"); moved = True
                if not moved:
                    break
            if not entered and p[0] < sp.GX <= q[0] and abs(q[1] - sp.GY) < sp.HALF:
                entered = True
            if entered:
                lim = sp.HALF - R_PUCK
                if abs(q[1] - sp.GY) > lim:
                    q = np.array([q[0], sp.GY + math.copysign(lim, q[1] - sp.GY)]); v = np.array([v[0], 0.0]); hits.append("goal_net")
                if q[0] >= sp.BACK_X:
                    q = np.array([sp.BACK_X, q[1]]); v = np.zeros(2); in_net = True; hits.append("goal_net")
            elif CAGE_OUT.contains(Point(*q)) and not (p[0] < sp.GX and abs(q[1] - sp.GY) < sp.HALF - R_PUCK):
                qq = np.array(CAGE_RING.interpolate(CAGE_RING.project(Point(*q))).coords[0])
                nrm = qq - q; nd = math.hypot(nrm[0], nrm[1])
                if nd > 1e-12:
                    nrm = nrm / nd; vn = float(v @ nrm)
                    if vn < 0:
                        v = v - vn * nrm; walls.append({"t": round(k * DT, 5), "obstacle": "goal_cage", "impact_mm_s": round(-vn, 1)})
                q = qq; hits.append("goal_cage")
            p = q
        P[k] = p; V[k] = v; touching[k] = tuple(sorted(set(hits)))
    return P, V, touching, impulses, walls, carry_log


# ---------------------------------------------------------------- rest pose
def rest_setup(p, others_S):
    """Puck at rest: the mean rest reading; with rest_mode "board" (v1) moved onto the board (touching the inset
    boundary). W-RW at rest: the tracked rotation; the arc is backed off along the slot until the puck just touches the
    figure (clearance 0.0-0.3 mm)."""
    m = np.mean([o["world_mm"] for o in REST], axis=0)
    if INP.get("rest_mode") == "readings":
        assert INSET.contains(Point(*m)), "rest reading overlaps the board"
        return np.array(m, float)
    q = np.array(INSET_RING.interpolate(INSET_RING.project(Point(*m))).coords[0])
    nrm = q - np.asarray(sp.BOARD.centroid.coords[0]); nrm = nrm / max(1e-9, np.linalg.norm(nrm))
    p_rest = q - nrm * 0.02  # just inside the inset: touching the board
    return p_rest


def solve_rw_arc(theta0, p_rest, a_guess):
    """Largest arc behind the puck (the figure faces back up the slot, the puck behind its skate on the goal side) at
    which the puck clears the figure by 0-0.2 mm."""
    def clr(a):
        return sp.clearance(sp.Static("W-RW", "skater", SLOTS["W-RW"].at(a), sp.HOME["W"] + theta0), 0, p_rest)
    lo, hi = a_guess - 60.0, a_guess + 60.0
    grid = np.arange(lo, hi, 0.25)
    c = np.array([clr(a) for a in grid])
    ok = [a for a, cc in zip(grid, c) if cc >= 0.0]
    # the touching arc nearest the guess on the side of the slot behind the puck
    cand = [a for i, a in enumerate(grid[:-1]) if c[i] >= 0 > c[i + 1]]
    if not cand:
        raise SystemExit(f"no touching rest arc near {a_guess:.1f} for theta {theta0}: clearance range {c.min():.1f}..{c.max():.1f}")
    a = min(cand, key=lambda x: abs(x - a_guess))
    lo, hi = a, a + 0.25
    for _ in range(30):
        mid = (lo + hi) / 2
        if clr(mid) >= 0.05: lo = mid
        else: hi = mid
    return lo


# ---------------------------------------------------------------- run, objective
_OTHERS = tracked_figures()
_OTHERS_S = [Sampled(f) for f in _OTHERS.values()]


def params():
    p = dict(INP["designed"]); p.update(INP.get("fitted", {}).get("values", {}))
    return p


def build(p):
    p = dict(p)
    p_rest = rest_setup(p, _OTHERS_S)
    fe = INP["rw_return"]["track_frames"]
    a_end, th_end = track_median("W-RW", LABEL + fe[0], LABEL + fe[1])
    th0 = p["rw_theta0"] + p["rw_turn_deg"]
    p.setdefault("rw_arc_end", a_end)
    p.setdefault("rw_theta_end", th_end - 360.0 * round((th_end - th0) / 360.0))
    if p.get("rw_arc0") is None:
        p["rw_arc0"] = solve_rw_arc(p["rw_theta0"], p_rest, INP["rw_arc_guess"])
    rw, wc = designed(p)
    return p, p_rest, rw, wc


def run(p, k_end=None):
    p, p_rest, rw, wc = build(p)
    S = [Sampled(rw), Sampled(wc)] + _OTHERS_S
    carries = [{"pid": "W-RW", "t_from": 0.0, "t_release": p["rw_t_release"]}, {"pid": "W-C", "t_from": p["wc_t_lunge"], "t_release": p["wc_t_release"]}]
    P, V, touching, imp, walls, clog = simulate(S, p_rest, k_end, carries)
    return p, p_rest, rw, wc, S, P, V, touching, imp, walls, clog


def goal_cross(P):
    for k in range(1, len(P)):
        if P[k - 1, 0] < sp.GX <= P[k, 0] and abs(P[k, 1] - sp.GY) < sp.HALF:
            return k
    return None


def score(p, verbose=False, stage=None):
    if stage == "pass":
        k_end = int(round((max(o["t"] for o in MOVING if o["frame"] <= PASS_TO) + 0.01) / DT))
    else:
        k_end = int(round((fr_t(LABEL) + INP["goal_window_frames"][1] / FPS + 0.08) / DT))
    p, p_rest, rw, wc, S, P, V, touching, imp, walls, clog = run(p, min(k_end, NSTEP))
    err = []
    for o in MOVING:
        if stage == "pass" and o["frame"] > PASS_TO:
            continue
        k = int(round(o["t"] / DT))
        if k >= len(P):
            continue
        err.append(obs_weight(o) * float(np.sum((P[k] - o["world_mm"]) ** 2)))
    J = sum(err)
    J += figure_penalty(rw if stage != "shot" else wc, "W-RW" if stage != "shot" else "W-C") if stage else 0.0
    cw = INP.get("carry_force_weight")
    if cw and stage:
        pid = "W-RW" if stage == "pass" else "W-C"
        c = next((c for c in clog if c["figure"] == pid), None)
        if c is not None:
            J += cw * pull_check(next(g for g in S if g.pid == pid), c, P)["share_needing_pull"]
    kg = goal_cross(P)
    if stage == "pass":
        kg = 0
    tg0, tg1 = fr_t(LABEL + INP["goal_window_frames"][0]), fr_t(LABEL + INP["goal_window_frames"][1])
    if stage == "pass":
        pass
    elif kg is None:
        tgt = np.array([sp.GX, INP["fit"]["goal_y_target_mm"]])
        J += 4000.0 + 30.0 * float(np.min(np.linalg.norm(P - tgt, axis=1)))
    else:
        tg = kg * DT
        J += 2.0e5 * (max(0.0, tg0 - tg) ** 2 + max(0.0, tg - tg1) ** 2)
        y_target = INP["fit"]["goal_y_target_mm"]
        J += INP["fit"]["weight_goal_y"] * (P[kg, 1] - y_target) ** 2
    if stage == "shot":
        # the shooter reaches the front of its slot when the broadcast shows it there; no overlap with the goalie,
        # the defenders or the goal while the puck is carried (carried steps skip the collision handling)
        t_front = fr_t(LABEL + INP["wc_front_frame"])
        J += 2.0e4 * (max(0.0, p["wc_t_lunge"] + p["wc_d_lunge"] - t_front - 0.02)) ** 2
        k0 = int(round(p["wc_t_lunge"] / DT))
        for k in range(k0, len(P), 4):
            for g in S[2:]:
                if (P[k, 0] - g.piv[k][0]) ** 2 + (P[k, 1] - g.piv[k][1]) ** 2 > REACH[g.kind] ** 2:
                    continue
                q = Point(*g.local(k, P[k])); low = sp.LOW[g.kind]
                c = (-low.boundary.distance(q) if low.contains(q) else low.boundary.distance(q)) - R_PUCK
                if c < 0:
                    J += 200.0 * c * c + 50.0
            for po in sp.POSTS:
                c = float(np.linalg.norm(P[k] - po)) - R_PUCK - sp.POST_R
                if c < 0:
                    J += 200.0 * c * c + 50.0
        if not any(x.get("catch") and x["figure"] == "W-C" for x in imp):
            J += 3000.0
        want = INP.get("shovel_part")
        if want and any(x.get("catch") and x["figure"] == "W-C" and x["part"] != want for x in imp):
            J += INP.get("shovel_part_penalty", 2000.0)
    lim_f, lim_w = INP["slide_rule"]["figure_impact_max_mm_s"], INP["slide_rule"]["wall_impact_max_mm_s"]
    J += sum(0.05 * (x["impact_mm_s"] - 0.9 * lim_f) ** 2 for x in imp if x["impact_mm_s"] > 0.9 * lim_f)
    J += sum(0.05 * (x["impact_mm_s"] - 0.9 * lim_w) ** 2 for x in walls if x["impact_mm_s"] > 0.9 * lim_w and x["obstacle"] != "goal_net")
    # the passer must not touch the puck again after the pass, the shooter only once (one contact episode each)
    if verbose:
        return J, P, V, imp, walls, kg, p
    return J


def pull_check(g, c, P, contact_mm=1.0, friction_deg=17.0, h=8):
    """Can the figure hold the puck as the carry needs? Within contact_mm of the puck rim the figure's low outline offers
    contact normals (one for a flat face, a fan of them in the heel groove). Every step of the carry the force the puck
    needs (its acceleration plus the ice friction) must lie inside that fan widened by a friction angle; otherwise the
    figure would have to pull the puck. friction_deg (17 deg, mu about 0.3) is ASSUMED."""
    loc = np.array(c["local_mm"]); bd = sp.LOW[g.kind].boundary
    pts = [np.array(bd.interpolate(d).coords[0]) for d in np.arange(0, bd.length, 0.25)]
    ns = [loc - q for q in pts if np.linalg.norm(loc - q) <= R_PUCK + contact_mm]
    ang = np.unwrap(sorted(math.atan2(n[1], n[0]) for n in ns)) if ns else np.array([])
    if len(ang):  # the fan: the smallest arc covering all normal directions
        a = np.sort(np.mod(ang, 2 * math.pi)); gaps = np.diff(np.r_[a, a[0] + 2 * math.pi]); i = int(np.argmax(gaps))
        lo, span = a[(i + 1) % len(a)], 2 * math.pi - gaps[i]
    k0, k1 = int(round(c["t_catch"] / DT)) + h, int(round(c["t_release"] / DT)) - h
    bad = tot = 0; worst = 0.0
    for k in range(max(k0, h), min(k1, len(P) - h - 1), 4):
        acc = (P[k + h] - 2 * P[k] + P[k - h]) / (h * DT) ** 2
        vel = (P[k + h] - P[k - h]) / (2 * h * DT); sv = float(np.linalg.norm(vel))
        F = acc + (A_FRIC * vel / sv if sv > 1 else 0)
        if np.linalg.norm(F) < 3 * A_FRIC:
            continue
        tot += 1
        fl = math.atan2(F[1], F[0]) - g.h[k]  # force direction in the figure frame
        if not len(ang):
            bad += 1; continue
        d = (fl - lo) % (2 * math.pi); fr = math.radians(friction_deg)
        out = 0.0 if d <= span else min(d - span, 2 * math.pi - d)
        out = max(0.0, out - fr)
        if out > 0:
            bad += 1; worst = max(worst, math.degrees(out))
    return {"normal_fan_deg": round(math.degrees(span), 1) if len(ang) else 0.0, "friction_angle_deg_assumed": friction_deg,
            "steps_checked": tot, "steps_needing_pull": bad, "share_needing_pull": round(bad / tot, 3) if tot else 0.0, "worst_outside_fan_deg": round(worst, 1)}


FC = INP.get("figure_constraints")


def figure_readings(pid):
    """The figure's own track readings (src 0) inside inputs.figure_constraints.frames[pid] (relative to the label)."""
    if not FC or pid not in FC["frames"]:
        return []
    a, b = (LABEL + x for x in FC["frames"][pid])
    return [(fr_t(f), TR[f][pid][0] * SLOTS[pid].length, TR[f][pid][1]) for f in sorted(TR)
            if a <= f <= b and TR[f][pid][0] is not None and TR[f][pid][2] == 0]


def figure_penalty(fig, pid):
    """Robust squared misfit of the designed move against the figure's readings: weight * min(cap, (d_arc / sigma_arc)^2 +
    (d_theta / sigma_theta)^2) per reading."""
    if not FC:
        return 0.0
    J = 0.0
    for t, a, th in figure_readings(pid):
        dth = (fig.theta(t) - th + 180.0) % 360.0 - 180.0
        J += FC["weight"] * min(FC["cap"], ((fig.arc(t) - a) / FC["sigma_arc_mm"]) ** 2 + (dth / FC["sigma_theta_deg"]) ** 2)
    return J


def figure_fit(fig, pid):
    out = []
    for t, a, th in figure_readings(pid):
        out.append({"frame": int(round(F0 + t * FPS)), "track_arc_mm": round(a, 1), "trace_arc_mm": round(fig.arc(t), 1), "track_theta_deg": round(th, 1),
                    "trace_theta_deg": round(fig.theta(t) % 360.0, 1), "theta_error_deg": round((fig.theta(t) - th + 180.0) % 360.0 - 180.0, 1)})
    return out


def summary(P, V, imp, walls, kg):
    out = {"obs": [(o["frame"], o["kind"], [round(float(x), 1) for x in P[int(round(o["t"] / DT))]], o["world_mm"]) for o in MOVING]}
    out["goal"] = None if kg is None else {"t": round(kg * DT, 4), "frame": round(F0 + kg * DT * FPS, 2), "y": round(float(P[kg, 1]), 1)}
    out["max_fig"] = max(((x["impact_mm_s"], x["t"], x["figure"], x["part"]) for x in imp), default=None)
    out["max_wall"] = max(((x["impact_mm_s"], x["t"], x["obstacle"]) for x in walls), default=None)
    out["figs_touched"] = sorted(set(x["figure"] for x in imp))
    return out


KEYS = INP["fit"]["keys"][STAGE] if STAGE else []


def _obj(z):
    p = dict(_P0); p.update({k: float(v) for k, v in zip(KEYS, z)})
    try:
        return score(p, stage=STAGE)
    except SystemExit:
        return 1e9


_P0 = params() if FIT else None  # module level: the fit's worker processes may be spawned (re-import), not forked


def fit():
    """Global search (differential evolution inside the bounds of inputs.fit.bounds), then a Nelder-Mead polish inside the same bounds."""
    global _P0
    from scipy.optimize import differential_evolution, minimize
    _P0 = params()
    bounds = [tuple(INP["fit"]["bounds"][k]) for k in KEYS]
    lo, hi = np.array([b[0] for b in bounds], float), np.array([b[1] for b in bounds], float)
    x0 = np.clip([_P0[k] for k in KEYS], lo + 1e-6 * (hi - lo), hi - 1e-6 * (hi - lo))
    r = differential_evolution(_obj, bounds, x0=x0, maxiter=INP["fit"].get(f"de_maxiter_{STAGE}", INP["fit"]["de_maxiter"]), popsize=INP["fit"]["de_popsize"], tol=1e-6, seed=1, workers=4, updating="deferred", polish=False, init="sobol")
    print("DE", r.fun, dict(zip(KEYS, np.round(r.x, 4))), flush=True)
    r2 = minimize(_obj, r.x, method="Nelder-Mead", bounds=bounds, options={"maxfev": INP["fit"]["maxfev"], "xatol": 1e-4, "fatol": 0.5})
    xb, Jb = (r2.x, r2.fun) if r2.fun < r.fun else (r.x, r.fun)
    vals = {k: round(float(v), 5) for k, v in zip(KEYS, xb)}
    cur = json.loads(INP_PATH.read_text())  # re-read: the file may have been edited while the fit ran
    old = cur.get("fitted", {})
    INP["fitted"] = cur["fitted"] = {"method": "two stages (scripts/edwall-trace.py --fit pass|shot), each a differential-evolution search inside fit.bounds and a Nelder-Mead polish: pass = the passer's rest rotation, lunge and turn against the puck readings (streak weight %s) and the slide-rule limits; shot = the shooter's lunge and turns against the goal window, the goal-line target and the slide-rule limits" % INP["fit"]["weight_streak"],
                     "objective": {**old.get("objective", {}), STAGE: round(float(Jb), 2)}, "evaluations": {**old.get("evaluations", {}), STAGE: int(r.nfev + r2.nfev)}, "values": {**old.get("values", {}), **vals}}
    INP_PATH.write_text(json.dumps(cur, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(INP["fitted"], indent=1))


if __name__ == "__main__" and FIT:
    fit()
    raise SystemExit
if __name__ == "__main__" and QUICK:
    J, P, V, imp, walls, kg, p = score(params(), verbose=True)
    print("J", round(J, 1), "rw_arc0", round(p["rw_arc0"], 2))
    print(json.dumps(summary(P, V, imp, walls, kg)))
    _, _, rw_, wc_ = build(params())
    print("figure fit W-RW", figure_fit(rw_, "W-RW")); print("figure fit W-C", figure_fit(wc_, "W-C"))
    big = [(x["t"], x["figure"], x["part"], x["impact_mm_s"]) for x in imp if x["impact_mm_s"] > 150]
    print("big impacts", big[:20])
    print("walls>100", [(w["t"], w["obstacle"], w["impact_mm_s"]) for w in walls if w["impact_mm_s"] > 100][:20])
    raise SystemExit


# ---------------------------------------------------------------- outputs
def local_contact(g, k, p):
    loc = g.local(k, p)
    q = Point(*loc)
    nb = sp.LOW[g.kind].boundary.interpolate(sp.LOW[g.kind].boundary.project(q))
    n = np.array(loc) - np.array(nb.coords[0]); h = g.h[k]
    nw = np.array([math.cos(h) * n[0] - math.sin(h) * n[1], math.sin(h) * n[0] + math.cos(h) * n[1]])
    return [round(float(x), 2) for x in nb.coords[0]], round(math.degrees(math.atan2(nw[1], nw[0])), 2)


def groups_of(imp, gap=0.06):
    out = {}
    for x in imp:
        g = out.setdefault(x["figure"], [])
        if g and x["t"] - g[-1][-1]["t"] <= gap:
            g[-1].append(x)
        else:
            g.append([x])
    return out


def main():
    p, p_rest, rw, wc, S, P, V, touching, imp, walls, clog = run(params())
    T = TGRID
    figs_by = {g.pid: g for g in S}
    kg = goal_cross(P)
    assert kg is not None, "no goal: refit"
    grp = groups_of(imp)
    rw_c = next((c for c in clog if c["figure"] == "W-RW"), None)
    wc_c = next((c for c in clog if c["figure"] == "W-C"), None)
    assert rw_c and wc_c, f"missing carries: {clog}"
    rw_imp = [x for x in imp if x["figure"] == "W-RW"]
    wc_imp = [x for x in imp if x["figure"] == "W-C"]
    pass_t0, pass_t1 = round(p["rw_t_lunge"], 5), round(rw_c["t_release"], 5)
    sh_t0 = wc_c["t_catch"]
    sh_t1 = round(max([wc_c["t_release"]] + [x["t"] for x in wc_imp if x["t"] < wc_c["t_release"] + 0.03]), 5)
    pass_g = [x for x in rw_imp if x["t"] <= pass_t1 + 0.004] or [{"t": pass_t0, "figure": "W-RW", "part": rw_c["part"], "impact_mm_s": 0.0}]
    shot_g = [x for x in wc_imp if x["t"] <= sh_t1 + 0.004]
    net = [k for k in range(len(T)) if "goal_net" in touching[k]]
    t_goal = round(kg * DT, 5); t_net = round(net[0] * DT, 5) if net else None
    others = sorted({x["figure"] for x in imp} - {"W-RW", "W-C"})

    def phase(t):
        if t < pass_t0: return "rest_at_blade"
        if t <= pass_t1: return "pass_carry"
        if t < sh_t0: return "pass_slide"
        if t <= sh_t1: return "shovel_carry"
        if t_net is None or t < t_net: return "shot_slide"
        return "in_goal"
    nodes = [{"t": round(float(T[k]), 5), "x_mm": round(float(P[k, 0]), 4), "y_mm": round(float(P[k, 1]), 4), "phase": phase(float(T[k]))} for k in range(0, len(T), sp.NODE_EVERY)]
    phases = []
    for n_ in nodes:
        if not phases or phases[-1]["id"] != n_["phase"]:
            if phases: phases[-1]["t"][1] = n_["t"]
            phases.append({"id": n_["phase"], "t": [n_["t"], None]})
    # whole-trace checks on the saved nodes (linear between nodes), every DT, all 12 figures, boards, posts, cage
    nt = np.array([n_["t"] for n_ in nodes]); nx = np.array([n_["x_mm"] for n_ in nodes]); ny = np.array([n_["y_mm"] for n_ in nodes])
    rows, viol, prev, max_step, entered = {}, [], None, 0.0, False
    for k in range(len(T)):
        tq = float(T[k]); pq = np.array([np.interp(tq, nt, nx), np.interp(tq, nt, ny)])
        ph = phase(tq)
        if prev is not None:
            max_step = max(max_step, float(np.linalg.norm(pq - prev)))
            if prev[0] < sp.GX <= pq[0] and abs(pq[1] - sp.GY) < sp.HALF:
                entered = True
        prev = pq
        cs = []
        for g in S:
            if np.hypot(*(pq - g.piv[k])) > REACH[g.kind] + 20:
                continue
            q = Point(*g.local(k, pq)); low = sp.LOW[g.kind]; dd = low.boundary.distance(q)
            cs.append((g.pid, (-dd if low.contains(q) else dd) - R_PUCK))
        cs.append(("boards", sp.BOARD.exterior.distance(Point(*pq)) - R_PUCK))
        cs += [(f"goal_post_{'pos' if i == 0 else 'neg'}_y", float(np.linalg.norm(pq - po)) - R_PUCK - sp.POST_R) for i, po in enumerate(sp.POSTS)]
        if not entered:
            cs.append(("goal_cage", float(CAGE_WALLS.distance(Point(*pq))) - R_PUCK))
        for ob, c in cs:
            r = rows.setdefault((ob, ph), {"min_clearance_mm": 1e9, "t_at_min": None})
            if c < r["min_clearance_mm"]:
                r.update(min_clearance_mm=round(float(c), 3), t_at_min=round(tq, 5))
            if c < -PEN_TOL:
                viol.append((ob, ph, round(tq, 5), round(float(c), 3)))
    vint = {}
    for ob, ph, tq, c in viol:
        a = vint.setdefault((ob, ph), {"t0": tq, "t1": tq, "worst_mm": c}); a["t1"] = tq; a["worst_mm"] = min(a["worst_mm"], c)
    unexplained = [round(float(T[i]), 5) for i in range(2, len(T)) if not touching[i] and float(np.linalg.norm(V[i] - V[i - 1])) > A_FRIC * DT + 1e-6]
    lim_f, lim_w = INP["slide_rule"]["figure_impact_max_mm_s"], INP["slide_rule"]["wall_impact_max_mm_s"]
    f_bad = [x for x in imp if x["impact_mm_s"] > lim_f]
    w_bad = [w for w in walls if w["impact_mm_s"] > lim_w]
    peak = lambda g: round(max(x["impact_mm_s"] for x in g), 1)
    named = [("pass", pass_g), ("shovel", shot_g)]
    slide_check = {"rule": "CLAUDE.md 'Slide or bounce': every contact must leave the puck flat on the ice; the net catching the puck is exempt",
                   "figure_impact_max_mm_s": lim_f, "wall_impact_max_mm_s": lim_w, "limits_status": INP["slide_rule"]["status"],
                   "per_contact": [{"contact": n, "figure": g[0]["figure"], "t": [g[0]["t"], g[-1]["t"]], "touches": len(g), "peak_impact_mm_s": peak(g)} for n, g in named]
                                  + [{"contact": f"other ({g[0]['figure']})", "figure": g[0]["figure"], "t": [g[0]["t"], g[-1]["t"]], "touches": len(g), "peak_impact_mm_s": peak(g)}
                                     for k_, gs in grp.items() for g in gs if k_ not in ("W-RW", "W-C")],
                   "carries": [{**c, "pull_check": pull_check(figs_by[c["figure"]], c, P)} for c in clog],
                   "peak_board_impact_mm_s": round(max([w["impact_mm_s"] for w in walls if w["obstacle"] == "boards"] + [0.0]), 1),
                   "peak_post_impact_mm_s": round(max([w["impact_mm_s"] for w in walls if w["obstacle"] == "goal_post"] + [0.0]), 1),
                   "peak_cage_impact_mm_s": round(max([w["impact_mm_s"] for w in walls if w["obstacle"] == "goal_cage"] + [0.0]), 1),
                   "figure_violations": f_bad, "wall_violations": w_bad, "passed": not f_bad and not w_bad}
    kat = lambda t: min(int(round(t / DT)), len(T) - 1)
    vel = lambda t: V[kat(t)]
    deg = lambda v: round(math.degrees(math.atan2(v[1], v[0])), 2)
    loc_p, n_p = local_contact(figs_by["W-RW"], kat(pass_t0), P[kat(pass_t0)])
    loc_r, n_r = local_contact(figs_by["W-RW"], kat(pass_t1), P[kat(pass_t1)])
    loc_s, n_s = local_contact(figs_by["W-C"], kat(sh_t0), P[kat(sh_t0)])
    loc_e, n_e = local_contact(figs_by["W-C"], kat(sh_t1), P[kat(sh_t1)])
    v_p, v_s = vel(pass_t1 + 0.006), vel(sh_t1 + 0.006)
    fit_res = [{"frame": o["frame"], "kind": o["kind"], "t": o["t"], "observed_mm": o["world_mm"], "trace_mm": [round(float(x), 2) for x in P[kat(o["t"])]],
                "error_mm": round(float(np.linalg.norm(P[kat(o["t"])] - o["world_mm"])), 2), **({"score": o["score"]} if "score" in o else {})} for o in OBS]
    events = [
        {"id": "pass.start", "t_estimate": pass_t0, "part": "W-RW:" + rw_c["part"], "contact_point_local_mm": rw_c["local_mm"], "model_contact_normal_deg": n_p,
         "status": "derived: the right wing starts its lunge with the puck resting in the heel groove of its stick " + ("at the rest readings" if INP.get("rest_mode") == "readings" else "by the board")},
        {"id": "pass.release", "t_estimate": pass_t1, "t_start": pass_t0, "part": "W-RW:" + rw_c["part"], "contact_point_local_mm": rw_c["local_mm"], "model_contact_normal_deg": n_r,
         "peak_impact_mm_s": peak(pass_g), "touches": len(pass_g), "speed_mm_s": round(float(np.linalg.norm(v_p)), 1), "direction_deg": deg(v_p),
         "status": "derived (heel-groove carry: the right wing lunges up its slot with the puck in the heel groove and turns counter-clockwise; the puck leaves with the groove's velocity)"},
        {"id": "contact.shot", "t_estimate": sh_t0, "t_end": sh_t1, "part": "W-C:" + wc_c["part"], "contact_point_local_mm": wc_c["local_mm"], "model_contact_normal_deg": n_s,
         "end_contact_point_local_mm": loc_e, "peak_impact_mm_s": peak(shot_g), "touches": len(shot_g), "speed_mm_s": round(float(np.linalg.norm(v_s)), 1), "direction_deg": deg(v_s),
         "heading_at_contact_deg": round(math.degrees(figs_by["W-C"].h[kat(sh_t0)]), 2), "arc_at_contact_mm": round(wc.arc(sh_t0), 2),
         "catch_relative_normal_speed_mm_s": wc_c["catch_impact_mm_s"], "catch_relative_speed_mm_s": wc_c.get("relative_speed_mm_s"),
         "status": "derived (the centre lunges to the front of its slot, catches the pass in the heel groove moving with it, and shovels it with a turn; hidden in the broadcast: DESIGNED)"},
        {"id": "goal_entry", "t_estimate": t_goal, "frame": round(F0 + t_goal * FPS, 2), "goal_line_y_mm": round(float(P[kg, 1]), 2), "user_goal_frame": LABEL,
         "status": "derived (hidden in the broadcast; the user's goal moment is the label frame)"},
    ] + ([{"id": "goal_net", "t_estimate": t_net, "status": "rule: the puck stops against the back of the preview cage"}] if t_net else [])
    fig_out = lambda g, status: {"player_id": g.pid, "team": g.f.team, "fixture_path_id": g.f.slot.id, "slot_length_mm": round(g.f.slot.length, 2), "status": status,
                                 "arc_keyframes": g.f.arcs, "theta_keyframes": g.f.thetas}
    figures = {"W-RW": fig_out(figs_by["W-RW"], "moving: passer (rest pose from the track's rotation, solved to touch the puck; lunge and turn DESIGNED and fitted to the puck readings)"),
               "W-C": fig_out(figs_by["W-C"], "moving: shooter (rest pose from the track; the lunge and shovel turn are hidden in the broadcast: DESIGNED and fitted to the goal)")}
    for pid in sp.ASM:
        if pid not in figures:
            figures[pid] = fig_out(figs_by[pid], f"moving: {'cleaned ' if FIG_FILE == 'figure-tracks-smooth.json' else ''}figure track (model output, PROPOSED; data/games/nm26-semifinal/g2/{FIG_FILE})")
    trace = {
        "schema": "shot-trace/1", "trace_id": f"trace.edwall-{GID}.{INP.get('trace_version', 'v1')}", "status": INP["status"],
        "shot": f"Edwallskyffel lang (Nygård, NM26 semi-final game 2, {GID}): right wing pass from the board, long centre shovel",
        "geometry_version": sp.G["geometry_version"],
        "asset_refs": {**SPJ["asset_refs"], "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()},
        "source": {"description": "NM26 broadcast (data/games/nm26-semifinal/config.json video), game 2; user goal label " + GID,
                   "inputs": f"shots/edwall/{GID}.inputs.json", "puck_readings": "shots/edwall/puck-readings.json", "figure_tracks": f"data/games/nm26-semifinal/g2/{FIG_FILE}",
                   **({"puck_track": OBS_CFG["puck_track"]} if OBS_CFG else {})},
        "time_base": {"t": f"seconds from broadcast frame {F0} (video time {F0 / FPS:.3f} s); frame = {F0} + 30 t", "window_s": [0.0, round(T1, 5)], "video_frame_at_t0": F0, "user_goal_frame": LABEL},
        "interpolation": SPJ["interpolation"], "pose_convention": SPJ["pose_convention"],
        "figures": figures,
        "puck": {"radius_mm": R_PUCK, "radius_status": "catalog_nominal", "thickness_mm": sp.PUCK_T, "thickness_status": "assumed (preview)",
                 "ice_friction_deceleration_mm_s2": A_FRIC, "ice_friction_status": "borrowed from the spjass slide fit",
                 "restitution_figure": E_FIG, "rest_mm": [round(float(x), 3) for x in p_rest], "nodes": nodes, "phases": phases},
        "events": events,
        "limitations": INP["limitations"],
    }
    samp = []
    for tq in np.round(np.arange(0, T1 + 1e-9, 0.02), 4):
        samp.append({"t": float(tq), "W-RW": {"arc_mm": round(rw.arc(tq), 4), "theta_deg": round(rw.theta(tq), 4)}, "W-C": {"arc_mm": round(wc.arc(tq), 4), "theta_deg": round(wc.theta(tq), 4)},
                     "puck": [round(float(np.interp(tq, nt, nx)), 4), round(float(np.interp(tq, nt, ny)), 4)]})
    trace["evaluation_samples"] = samp
    OUT_TRACE.write_text(json.dumps(trace, indent=1, ensure_ascii=False) + "\n")
    checks = {"trace_id": trace["trace_id"], "sampling_s": DT, "max_puck_step_mm": round(max_step, 3), "penetration_tolerance_mm": PEN_TOL,
              "contact_rule": "CLAUDE.md 'Contact physics': the puck may touch figures, boards and goal but never overlap them (every 0.25 ms, whole trace, all 12 figures, boards, posts, cage; no phase exemptions)",
              "min_clearance_by_obstacle_and_phase": [{"obstacle": k[0], "phase": k[1], **v} for k, v in sorted(rows.items()) if v["min_clearance_mm"] < 30],
              "unexpected_penetrations": [{"obstacle": k[0], "phase": k[1], **v} for k, v in vint.items()], "approved_exceptions": [], "slide_check": slide_check,
              "other_figures_touched": others, "impulses": imp, "unexplained_velocity_changes": unexplained[:20], "unexplained_count": len(unexplained),
              "goal_line": {"x_mm": sp.GX, "crossing_y_mm": round(float(P[kg, 1]), 2), "inside_mouth_window_y_mm": [round(sp.GY - sp.HALF + sp.POST_R + R_PUCK, 1), round(sp.GY + sp.HALF - sp.POST_R - R_PUCK, 1)],
                            "frame": round(F0 + t_goal * FPS, 2), "user_goal_frame": LABEL},
              "carry_force_check": {"rule": "this rebuild's own plausibility check (not a CLAUDE.md rule): during a heel-groove carry the force the puck needs must lie inside the contact-normal fan of the figure's low outline at the carry point, widened by an ASSUMED 17 deg friction angle; otherwise the stick would have to pull the puck",
                                    "carries": [{"figure": c["figure"], "t": [c["t_catch"], c["t_release"]], **pull_check(figs_by[c["figure"]], c, P)} for c in clog],
                                    "passed": all(pull_check(figs_by[c["figure"]], c, P)["steps_needing_pull"] == 0 for c in clog)},
              "observation_fit": fit_res, **({"figure_fit": {"rule": "the passer's and shooter's designed moves against their own track readings (src 0) in inputs.figure_constraints.frames", "W-RW": figure_fit(rw, "W-RW"), "W-C": figure_fit(wc, "W-C")}} if FC else {}),
              "fitted": INP.get("fitted"),
              "passed": not vint and not f_bad and not w_bad and not unexplained}
    OUT_CHECKS.write_text(json.dumps(checks, indent=1, ensure_ascii=False) + "\n")
    sheet(S, P, nt, nx, ny, events)
    print(json.dumps({"passed": checks["passed"], "carry_force_check": checks["carry_force_check"]["passed"], "events": events, "slide": {k: slide_check[k] for k in ("per_contact", "peak_board_impact_mm_s", "peak_post_impact_mm_s", "passed")},
                      "unexpected": checks["unexpected_penetrations"], "unexplained": len(unexplained), "fit": fit_res, "others": others}, indent=1, ensure_ascii=False))


def sheet(S, P, nt, nx, ny, events):
    SC = 1.5
    W_, H_ = int(470 * SC), int(480 * SC)
    px = lambda w: ((w[0] + 90) * SC, (240 - w[1]) * SC)
    ev = {e["id"]: e["t_estimate"] for e in events}
    times = [("rest", max(0.0, ev["pass.start"] - 0.1)), ("pass push", (ev["pass.start"] + ev["pass.release"]) / 2), ("pass released", ev["pass.release"]),
             ("shovel starts", ev["contact.shot"]), ("shovel ends", ev["contact.shot"] + (([e for e in events if e["id"] == "contact.shot"][0]["t_end"] - ev["contact.shot"]))), ("goal", ev["goal_entry"])]
    tiles = []
    for name, tq in times:
        k = min(int(round(tq / DT)), len(P) - 1)
        im = Image.new("RGB", (W_, H_), "white"); d = ImageDraw.Draw(im)
        d.line([px(c) for c in sp.BOARD.exterior.coords], fill=(60, 60, 60), width=2)
        for po in sp.POSTS:
            c = px(po); d.ellipse([c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3], fill=(200, 0, 0))
        d.line([px(c) for c in CAGE_WALLS.coords], fill=(200, 0, 0), width=2)
        for pid in ("W-RW", "W-C"):
            sl = sp.Slot(pid); d.line([px(sl.at(a)) for a in np.arange(0, sl.length, 3)], fill=(205, 205, 205), width=4)
        for g in S:
            pol = sp.affinity.translate(sp.affinity.rotate(sp.LOW[g.kind], math.degrees(g.h[k]), origin=(0, 0)), g.piv[k][0], g.piv[k][1])
            for gg in ([pol] if pol.geom_type == "Polygon" else list(pol.geoms)):
                d.polygon([px(c) for c in gg.exterior.coords], fill=(150, 190, 255) if g.pid.startswith("W") else (255, 225, 120), outline=(30, 30, 30))
        tr = [px((np.interp(x, nt, nx), np.interp(x, nt, ny))) for x in np.arange(0, tq, 0.004)]
        if len(tr) > 1:
            d.line(tr, fill=(255, 140, 0), width=2)
        for o in OBS:
            c = px(o["world_mm"]); d.ellipse([c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3], fill=(220, 0, 220) if o["kind"] not in ("rest", "det_rest") else (170, 120, 220))
        c = px(P[k]); r = R_PUCK * SC
        d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=(0, 0, 0))
        d.text((8, 6), f"{name}  t={tq:.4f} s  (frame {F0 + tq * FPS:.1f})", fill=(0, 0, 0), font=sp.FB)
        tiles.append(im)
    out = Image.new("RGB", (W_ * 3, H_ * 2 + 40), "white")
    for i, im in enumerate(tiles):
        out.paste(im, ((i % 3) * W_, 40 + (i // 3) * H_))
    ImageDraw.Draw(out).text((10, 8), f"trace.edwall-{GID}.{INP.get('trace_version', 'v1')} (PROPOSED) - top view, goal.E right; figures' low geometry; puck path orange; puck readings magenta (rest: lilac)", fill=(0, 0, 0), font=sp.FB)
    out.save(OUT_PNG)


if __name__ == "__main__":
    main()
