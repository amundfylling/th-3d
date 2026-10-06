"""Spjass: one contact-checked motion trace of the centre move from the user's TikTok (take 1).

    /root/venvs/blender/bin/python scripts/spjass-trace.py

Inputs: shots/spjass/observations.json (scripts/spjass-observe.py), shots/spjass/inputs.json (reconstruction choices),
data/geometry.json, validation/12-hardware-report.json (preview goal), validation/16-assembly-poses.json (figures not in
the trace), out/figures/{skater,goalie}.npz and validation/players/figures-report.json (figure meshes).
Outputs: data/traces/spjass.trace.json, shots/spjass/checks.json, validation/spjass-trace.png.

Reconstruction (no general simulator):
- W-C: slot arc (Fritsch-Carlson cubic through arc keyframes) and rotation (linear between theta keyframes). Read from
  the blade-toe poses where the frames are sharp; the rest arc is backed off until the puck just touches the heel; the
  blurred clockwise spin is a smooth profile between the last sharp frame before (128) and the first after (133),
  sampled every 1 ms; the lunge up the slot is a cubic between the turn arc and the frame-133 arc.
- E-G: static at its observed blade pose (frame 100), moved onto its slot. Figures not in the trace stand in the
  static assembly pose (as the renderer shows them) and are checked too.
- Puck: starts at rest at the observed rest position. Every 0.25 ms it moves with its velocity, slowed by ice
  friction (constant deceleration fitted to the observed slide); where any figure, the goal or the boards would overlap
  it, it is moved out to touching along the contact normal and takes the resulting velocity (pushing contact, as in
  iteration 22). It stops against the back of the cage (goal net). Every change in its motion therefore has a named
  cause: blade/skate contact, ice friction, goal net.
- Checks: finite puck against every figure's low geometry (all 12), the boards and the goal posts, every 0.25 ms.
"""
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

REPO = Path(__file__).resolve().parents[1]
OBS = json.loads((REPO / "shots/spjass/observations.json").read_text())
INP = json.loads((REPO / "shots/spjass/inputs.json").read_text())
if os.environ.get("SPJASS_OVERRIDE"):  # parameter scans only (never for the saved trace): deep-merge a JSON override into inputs.json
    def _merge(a, b):
        for k, v in b.items():
            a[k] = _merge(a.get(k, {}), v) if isinstance(v, dict) else v
        return a
    INP = _merge(INP, json.loads(os.environ["SPJASS_OVERRIDE"]))
G = json.loads((REPO / "data/geometry.json").read_text())
HW = json.loads((REPO / "validation/12-hardware-report.json").read_text())
FIG = json.loads((REPO / "validation/players/figures-report.json").read_text())
ASM = {f["player_id"]: f for f in json.loads((REPO / "validation/16-assembly-poses.json").read_text())["figures"]}
OUT_TRACE = REPO / "data/traces/spjass.trace.json"
OUT_CHECKS = REPO / "shots/spjass/checks.json"
OUT_PNG = REPO / "validation/spjass-trace.png"
FPS = OBS["source"]["fps"]
R_PUCK = G["puck"]["diameter"]["value"] / 2
PUCK_T = HW["puck"]["thickness_mm_preview"]
DT = 0.00025
NODE_EVERY = 2  # nodes every 0.5 ms
EPS = 0.05
PEN_TOL = 0.1
HOME = {"W": 0.0, "E": 180.0}
FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
FS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)


def fr(k):
    return k / FPS


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rot(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s], [s, c]])


# ---------------------------------------------------------------- geometry
class Slot:
    def __init__(self, pid):
        p = next(x for x in G["fixture_paths"] if x["player_id"] == pid)
        self.P = np.array(p["centreline"]["points_mm"], float)
        self.s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(self.P, axis=0), axis=1))]
        self.length = float(self.s[-1])
        self.id = p["id"]

    def at(self, a):
        a = min(max(a, 0.0), self.length)
        return np.array([np.interp(a, self.s, self.P[:, 0]), np.interp(a, self.s, self.P[:, 1])])


def low_polygon(kind, k):
    """Union of the figure mesh below the puck top (z < puck thickness), local mm, pivot at the origin."""
    d = np.load(REPO / f"out/figures/{kind}.npz")
    V, T = d["verts"] * k, d["tris"]
    sel = T[V[T][:, :, 2].min(1) < PUCK_T]
    polys = [Polygon(V[t][:, :2]) for t in sel]
    return unary_union([p.buffer(0.01) for p in polys if p.area > 1e-6]).buffer(0)


K_SK = FIG["scale_k_mm_per_mold_unit"]
K_GO = FIG["scales"]["goalie"]
LOW = {"skater": low_polygon("skater", K_SK), "goalie": low_polygon("goalie", K_GO)}


def stick_polygon(kind, k):
    d = np.load(REPO / f"out/figures/{kind}.npz")
    keys = [str(x) for x in d["keys"]]
    V, T, L = d["verts"] * k, d["tris"], d["labels"]
    is_stick = np.isin(L, [keys.index(x) for x in ("stick_metal", "stick_tan") if x in keys])
    sel = T[(V[T][:, :, 2].min(1) < PUCK_T) & is_stick]
    return unary_union([q for q in (Polygon(V[t][:, :2]).buffer(0.01) for t in sel) if q.area > 1e-6]).buffer(0)


STICK = {"skater": stick_polygon("skater", K_SK), "goalie": stick_polygon("goalie", K_GO)}
LOW_OUT = {k: v.buffer(R_PUCK + EPS, 64) for k, v in LOW.items()}


def rings(poly):
    gs = [poly] if poly.geom_type == "Polygon" else list(poly.geoms)
    return [r for g in gs for r in [g.exterior, *g.interiors]]


RINGS_OUT = {k: rings(v) for k, v in LOW_OUT.items()}


# ---------------------------------------------------------------- interpolation (mirrored in src/model/trace.ts)
def end_slope(h0, h1, d0, d1):
    m = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
    if m * d0 <= 0:
        return 0.0
    if d0 * d1 <= 0 and abs(m) > abs(3 * d0):
        return 3 * d0
    return m


def pchip_slopes(x, y):
    n = len(x)
    h = np.diff(x)
    dl = np.diff(y) / h
    m = np.zeros(n)
    if n == 2:
        m[:] = dl[0]
        return m
    for i in range(1, n - 1):
        if dl[i - 1] * dl[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / dl[i - 1] + w2 / dl[i])
    m[0] = end_slope(h[0], h[1], dl[0], dl[1])
    m[-1] = end_slope(h[-1], h[-2], dl[-1], dl[-2])
    return m


def pchip_eval(x, y, m, t):
    if t <= x[0]:
        return float(y[0])
    if t >= x[-1]:
        return float(y[-1])
    i = int(np.searchsorted(x, t) - 1)
    h = x[i + 1] - x[i]
    s = (t - x[i]) / h
    return float((2 * s**3 - 3 * s**2 + 1) * y[i] + (s**3 - 2 * s**2 + s) * h * m[i] + (-2 * s**3 + 3 * s**2) * y[i + 1] + (s**3 - s**2) * h * m[i + 1])


class Figure:
    def __init__(self, pid, team, kind, arcs, thetas):
        self.pid, self.team, self.kind = pid, team, kind
        self.slot = Slot(pid)
        self.arcs = sorted(arcs, key=lambda k: k["t"])
        self.thetas = sorted(thetas, key=lambda k: k["t"])
        self.ax = np.array([k["t"] for k in self.arcs]); self.ay = np.array([k["arc_mm"] for k in self.arcs])
        self.am = pchip_slopes(self.ax, self.ay) if len(self.ax) > 1 else np.zeros(1)
        self.tx = np.array([k["t"] for k in self.thetas]); self.ty = np.array([k["theta_deg"] for k in self.thetas])

    def arc(self, t):
        return pchip_eval(self.ax, self.ay, self.am, t) if len(self.ax) > 1 else float(self.ay[0])

    def theta(self, t):
        return float(np.interp(t, self.tx, self.ty)) if len(self.tx) > 1 else float(self.ty[0])

    def pose(self, t):
        return self.slot.at(self.arc(t)), HOME[self.team] + self.theta(t)


class Static:
    """A figure in a fixed pose (pivot mm, heading deg)."""
    def __init__(self, pid, kind, pivot, heading):
        self.pid, self.kind, self.piv, self.h = pid, kind, np.asarray(pivot, float), float(heading)

    def pose(self, t):
        return self.piv, self.h


def to_local(f, t, w):
    piv, h = f.pose(t)
    return rot(h).T @ (np.asarray(w) - piv)


def to_world(f, t, loc):
    piv, h = f.pose(t)
    return piv + rot(h) @ np.asarray(loc)


def clearance(f, t, w):
    """Signed distance puck edge -> low geometry (negative = overlap)."""
    q = Point(*to_local(f, t, w))
    low = LOW[f.kind]
    d = low.boundary.distance(q)
    return (-d if low.contains(q) else d) - R_PUCK


def push_out(f, t, p):
    """Pushing contact: if the puck centre p is closer than the puck radius to figure f at time t, move it to the nearest
    position where it just touches. Returns (p, pushed)."""
    q = Point(*to_local(f, t, p))
    if not LOW_OUT[f.kind].contains(q):
        return np.asarray(p, float), False
    best = min((r.interpolate(r.project(q)) for r in RINGS_OUT[f.kind]), key=lambda z: z.distance(q))
    return to_world(f, t, np.array(best.coords[0])), True


def world_polygon(f, t):
    piv, h = f.pose(t)
    return affinity.translate(affinity.rotate(LOW[f.kind], h, origin=(0, 0)), piv[0], piv[1])


# ---------------------------------------------------------------- goal (preview cage)
GX, GY = HW["goal"]["placement_mm"]["E"]
HALF = HW["goal"]["mouth_width_per_goal_mm"]["E"] / 2
DEPTH = HW["goal"]["depth_per_goal_mm"]["E"]
POST_R = HW["goal"]["post_radius_mm"]
POSTS = [np.array([GX, GY + HALF]), np.array([GX, GY - HALF])]
BACK_X = GX + DEPTH - R_PUCK  # puck centre against the back of the cage
BOARD = Polygon(G["board"]["inner_boundary"]["world"]["points_mm"])


def push_posts(p):
    pushed = False
    for po in POSTS:
        d = p - po
        n = float(np.linalg.norm(d))
        if n < R_PUCK + POST_R:
            p = po + d / n * (R_PUCK + POST_R + EPS)
            pushed = True
    return p, pushed


# ---------------------------------------------------------------- build
def main():
    # alignment of the recorded table to the canonical slot layout: puck observations offset in y (inputs.json, reported)
    dy_align = INP.get("alignment", {}).get("puck_y_offset_mm", 0.0)
    obs_p = {r["frame"]: np.array(r["world_mm"]) + np.array([0.0, dy_align]) for r in OBS["puck_take1"]}
    poses = {r["frame"]: r["chosen"] for r in OBS["w_c_blade_poses"] if "chosen" in r}
    rest = INP["rest"]
    p_rest = np.mean([obs_p[k] for k in range(rest["puck_frames"][0], rest["puck_frames"][1] + 1)], axis=0)
    t0, t1 = INP["window_s"]
    # ---- ice friction from the observed slide (straight line, constant deceleration)
    sf = INP["slide_fit_frames"]
    pts = np.array([obs_p[k] for k in range(sf[0], sf[1] + 1)])
    u = pts[-1] - pts[0]; u /= np.linalg.norm(u)
    s = (pts - pts[0]) @ u
    tt = np.array([fr(k) for k in range(sf[0], sf[1] + 1)]) - fr(sf[0])
    A = np.c_[np.ones_like(tt), tt, -0.5 * tt ** 2]
    c0, v0, a_fric = np.linalg.lstsq(A, s, rcond=None)[0]
    slide = {"frames": sf, "direction_deg": round(math.degrees(math.atan2(u[1], u[0])), 2), "speed_at_first_frame_mm_s": round(float(v0), 1),
             "deceleration_mm_s2": round(float(a_fric), 1), "rms_mm": round(float(np.sqrt(np.mean((A @ [c0, v0, a_fric] - s) ** 2))), 2)}
    # flick: the observed slide line through the rest position; the impulse time where the fitted slide reaches the rest point
    s_rest = float((p_rest - pts[0]) @ u)
    tau_f = (v0 - math.sqrt(v0 ** 2 + 2 * a_fric * (c0 - s_rest))) / a_fric
    t_flick = fr(sf[0]) + tau_f
    v_flick_obs = (v0 - a_fric * tau_f) * u
    off_line = float(abs((p_rest - pts[0]) @ np.array([-u[1], u[0]])))
    slide.update({"flick_time_s": round(t_flick, 5), "flick_frame": round(t_flick * FPS, 2), "flick_speed_mm_s": round(float(np.linalg.norm(v_flick_obs)), 1),
                  "rest_point_off_the_slide_line_mm": round(off_line, 2)})
    # ---- E-G at its observed blade pose, on its slot
    eg_o = OBS["e_g_blade_pose"]
    eg_slot = Slot("E-G")
    eg = Static("E-G", "goalie", eg_slot.at(eg_o["nearest_arc_mm"]), eg_o["heading_deg"])
    # ---- W-C keyframes
    turn = INP["turn"]
    spin = INP["spin"]

    def make_wc(a_rest, spin_par):
        a_turn = INP["turn"]["arc_mm"]
        arcs = [{"t": round(t0, 4), "arc_mm": a_rest, "sigma_mm": None, "source": "rest arc: the read pose backed off until the resting puck is within rest.gap_mm of the heel"},
                {"t": round(fr(turn["start_frame"]), 4), "arc_mm": a_rest, "sigma_mm": None, "source": "rest until the turn onset"},
                {"t": round(fr(124), 4), "arc_mm": a_turn, "sigma_mm": 1.0, "source": "turn arc: mean of the frame 124-128 blade poses (207.1-207.9 mm); W-C slides up its slot by the difference while it turns"},
                {"t": round(fr(spin_par["lunge_start_frame"]), 4), "arc_mm": a_turn, "sigma_mm": 1.0, "source": "held through the turn (frames 124-128)"}]
        for k, a in spin_par.get("lunge_extra_keyframes", []):
            arcs.append({"t": round(fr(k), 4), "arc_mm": a, "sigma_mm": None, "source": "assumed lunge timing (motion-blurred frames 129-132): nearly complete when the blade meets the puck"})
        for k in spin_par["lunge_arc_frames"]:
            arcs.append({"t": round(fr(k), 4), "arc_mm": poses[k]["arc_mm"], "sigma_mm": 3.0, "source": f"frame {k} blade pose (toe mark)"})
        thetas = [{"t": round(t0, 4), "theta_deg": rest["theta_deg"], "sigma_deg": 5.0, "source": "frame-100 blade pose"},
                  {"t": round(fr(turn["start_frame"]), 4), "theta_deg": rest["theta_deg"], "sigma_deg": None, "source": "turn onset (frames 121-122 show the first movement)"}]
        for k, th in turn["keyframes"].items():
            thetas.append({"t": round(fr(float(k)), 4), "theta_deg": th, "sigma_deg": None if k in turn["assumed"] else 4.0,
                           "source": "assumed (blurred frame; between the onset and frame 124)" if k in turn["assumed"] else f"frame {k} blade pose (toe mark)"})
        # clockwise spin: built in main() through the touching pose at the strike (monotone cubic, sampled every 1 ms)
        tb = fr(spin_par["end_frame"])
        th_b = poses[spin_par["end_frame"]]["heading_deg"] - 360.0
        thetas.append({"t": round(tb, 4), "theta_deg": round(th_b, 3), "sigma_deg": 5.0, "source": f"frame {spin_par['end_frame']} blade pose (toe mark), unwrapped clockwise"})
        for k in spin_par["after_frames"]:
            thetas.append({"t": round(fr(k), 4), "theta_deg": round(poses[k]["heading_deg"] - 360.0, 3), "sigma_deg": 5.0, "source": f"frame {k} blade pose (toe mark), unwrapped clockwise"})
        return Figure("W-C", "W", "skater", arcs, thetas)

    # rest arc: back off from the reading until the resting puck just touches (clearance >= 0)
    a_read = rest["arc_mm_reading"]
    a_rest = a_read
    probe = Static("W-C", "skater", Slot("W-C").at(a_read), HOME["W"] + rest["theta_deg"])
    while clearance(probe, 0, p_rest) < INP["rest"]["gap_mm"]:
        a_rest -= 0.05
        probe = Static("W-C", "skater", Slot("W-C").at(a_rest), HOME["W"] + rest["theta_deg"])
    a_rest = round(a_rest, 2)
    wc = make_wc(a_rest, spin)
    # ---- shot: strike time where the backward-extended observed shot line meets the observed slide
    sh = INP["shot"]
    q1, q2 = obs_p[sh["frames"][0]], obs_p[sh["frames"][1]]
    v_obs = (q2 - q1) * FPS
    sp_obs = float(np.linalg.norm(v_obs))

    def slide_at(t):
        tau = t - t_flick
        tau_stop = float(np.linalg.norm(v_flick_obs)) / a_fric
        tau = min(tau, tau_stop)
        return p_rest + u * (float(np.linalg.norm(v_flick_obs)) * tau - 0.5 * a_fric * tau ** 2)
    ts_grid = np.arange(fr(sh["frames"][0] - 1), fr(sh["frames"][0]), 0.0001)
    t_strike = float(min(ts_grid, key=lambda t: np.linalg.norm(slide_at(t) - (q1 - v_obs * (fr(sh["frames"][0]) - t)))))
    p_strike = slide_at(t_strike)
    # direction: centre of the window of straight paths that clear the static goalie (low geometry) and both posts
    eg_poly_ = world_polygon(eg, t_strike)
    post_disks = unary_union([Point(*po).buffer(POST_R) for po in POSTS])
    win = []
    for dd in np.arange(-15.0, 10.0001, 0.05):
        ud = np.array([math.cos(math.radians(dd)), math.sin(math.radians(dd))])
        end = p_strike + ud * ((BACK_X - p_strike[0]) / ud[0])
        line = LineString([tuple(p_strike), tuple(end)])
        yg = p_strike[1] + ud[1] * (GX - p_strike[0]) / ud[0]
        cg, cp = line.distance(eg_poly_) - R_PUCK, line.distance(post_disks) - R_PUCK
        if cg >= sh["min_clearance_mm"] and cp >= sh["min_clearance_mm"] and abs(yg - GY) < HALF:
            win.append((round(float(dd), 2), round(float(cg), 2), round(float(cp), 2)))
    assert win, "no clear straight shot from the strike point"
    d_shot = float(np.mean([w[0] for w in win])) if sh["direction"] == "window_centre" else float(sh["direction"])
    v_shot_set = sp_obs * np.array([math.cos(math.radians(d_shot)), math.sin(math.radians(d_shot))])
    # heading at the strike: the model blade's front face touches the puck (scan clockwise from the last sharp pose)
    a_s = wc.arc(t_strike)
    h_s = None
    for h in np.arange(spin["touch_scan_from_deg"], -90.0, -0.02):
        if clearance(Static("W-C", "skater", Slot("W-C").at(a_s), h), 0, p_strike) <= 0.0:
            h_s = round(float(h), 2)
            break
    assert h_s is not None, "no heading touches the puck at the strike"
    th128 = turn["keyframes"][str(spin["start_frame"])]
    th133 = poses[spin["end_frame"]]["heading_deg"] - 360.0
    spin_kf = [(fr(spin["start_frame"]), th128), (t_strike, h_s), (fr(spin["end_frame"]), th133)]
    sx = np.array([k[0] for k in spin_kf]); sy = np.array([k[1] for k in spin_kf]); sm = pchip_slopes(sx, sy)
    th_new = [k for k in wc.thetas if not ("spin profile" in k["source"])]
    for tq in np.arange(sx[0] + 0.001, sx[-1] - 1e-9, 0.001):
        th_new.append({"t": round(float(tq), 4), "theta_deg": round(pchip_eval(sx, sy, sm, tq), 3), "sigma_deg": None,
                       "source": "clockwise spin: monotone cubic through the frame-128 pose, the touching pose at the strike and the frame-133 pose (motion-blurred 129-132)"})
    th_new = sorted({round(k["t"], 4): k for k in th_new}.values(), key=lambda k: k["t"])
    wc = Figure("W-C", "W", "skater", wc.arcs, th_new)
    q_ = Point(*to_local(wc, t_strike, p_strike))
    nb_ = LOW["skater"].boundary.interpolate(LOW["skater"].boundary.project(q_))
    n_s = rot(wc.pose(t_strike)[1]) @ (np.array(q_.coords[0]) - np.array(nb_.coords[0]))
    shot_info = {"t_s": round(t_strike, 5), "frame": round(t_strike * FPS, 3), "strike_point_mm": [round(float(x), 2) for x in p_strike], "arc_mm": round(a_s, 2),
                 "heading_touch_deg": h_s, "observed_speed_mm_s": round(sp_obs, 1), "observed_direction_deg": round(math.degrees(math.atan2(v_obs[1], v_obs[0])), 2),
                 "clear_window_deg": [win[0][0], win[-1][0]], "direction_used_deg": round(d_shot, 2), "direction_rule": sh["direction"],
                 "model_contact_normal_deg": round(math.degrees(math.atan2(n_s[1], n_s[0])), 2), "contact_local_mm": [round(float(x), 2) for x in nb_.coords[0]],
                 "part": "stick/blade" if STICK["skater"].distance(q_) <= LOW["skater"].distance(q_) + 0.3 else "skate/body",
                 "spin_speed_at_strike_deg_s": round(float(np.interp(t_strike, sx, sm)), 1)}
    shot_info["impulse_minus_normal_deg"] = round(((d_shot - shot_info["model_contact_normal_deg"] + 180) % 360) - 180, 2)
    a_f = wc.arc(t_flick)
    h_touch = None
    for h in np.arange(200.0, 300.0, 0.05):
        if clearance(Static("W-C", "skater", Slot("W-C").at(a_f), h), 0, p_rest) <= 0.0:
            h_touch = round(float(h), 2)
            break
    assert h_touch is not None, "no heading touches the resting puck"
    kept = [k for k in wc.thetas if not (abs(k["t"] - t_flick) < 0.75 / FPS and k["t"] > fr(INP["turn"]["start_frame"]) and "toe mark" in k["source"] or k["source"].startswith("assumed (blurred"))]
    replaced = [k for k in wc.thetas if k not in kept]
    kept.append({"t": round(t_flick, 5), "theta_deg": h_touch, "sigma_deg": None,
                 "source": f"flick: the heading at which the model blade touches the resting puck at the flick time (replaces {[ (k['t'], k['theta_deg']) for k in replaced ]})"})
    wc = Figure("W-C", "W", "skater", wc.arcs, kept)
    flick_info = {"t_s": round(t_flick, 5), "arc_mm": round(a_f, 2), "heading_touch_deg": h_touch, "replaced_keyframes": replaced}
    # contact normal of the model at the flick vs the observed impulse direction
    q = Point(*to_local(wc, t_flick, p_rest))
    nb = LOW["skater"].boundary.interpolate(LOW["skater"].boundary.project(q))
    n_w = rot(wc.pose(t_flick)[1]) @ (np.array(q.coords[0]) - np.array(nb.coords[0]))
    flick_info["model_contact_normal_deg"] = round(math.degrees(math.atan2(n_w[1], n_w[0])), 2)
    flick_info["observed_impulse_direction_deg"] = round(math.degrees(math.atan2(u[1], u[0])), 2)
    flick_info["impulse_minus_normal_deg"] = round(((flick_info["observed_impulse_direction_deg"] - flick_info["model_contact_normal_deg"] + 180) % 360) - 180, 2)
    flick_info["contact_local_mm"] = [round(float(x), 2) for x in nb.coords[0]]
    flick_info["part"] = "stick/blade" if STICK["skater"].distance(q) <= LOW["skater"].distance(q) + 0.3 else "skate/body"
    others = {pid: Static(pid, "goalie" if f["position"] == "G" else "skater", f["pivot_mm"][:2], f["heading_deg"]) for pid, f in ASM.items() if pid not in ("W-C", "E-G")}
    movers = [wc, eg, *others.values()]

    # ---- puck: pushing contact + ice friction + goal net, every DT
    def run(wc_):
        figs = [wc_, eg, *others.values()]
        p, v = p_rest.copy(), np.zeros(2)
        out, touching, in_net = [], [], False
        touching_flick = []
        t = t0
        n = int(round((t1 - t0) / DT))
        for k in range(n + 1):
            t = t0 + k * DT
            if k:
                sp = float(np.linalg.norm(v))
                if sp > 0:
                    v = v * max(0.0, sp - a_fric * DT) / sp
                if t - DT < t_flick <= t:
                    v = v_flick_obs.copy()  # flick impulse from the touching blade (observed velocity)
                    touching_flick.append(t)
                if t - DT < t_strike <= t:
                    v = v_shot_set.copy()  # shot impulse from the touching blade (observed speed, corridor direction)
                    touching_flick.append(t)
                q = p + v * DT
                hits = ["W-C:stick/blade"] if touching_flick and abs(touching_flick[-1] - t) < 1e-12 else []
                for _ in range(3):  # resolve simultaneous contacts
                    moved = False
                    for f in figs:
                        q2, pushed = push_out(f, t, q)
                        if pushed:
                            hits.append(f.pid); q = q2; moved = True
                    q2, pushed = push_posts(q)
                    if pushed:
                        hits.append("goal_post"); q = q2; moved = True
                    if not moved:
                        break
                if q[0] > GX and abs(q[1] - GY) < HALF and q[0] >= BACK_X:
                    q = np.array([BACK_X, q[1]])
                    if not in_net:
                        hits.append("goal_net")  # the back of the cage stops the puck
                    in_net = True
                pushed_now = [h for h in hits if h != "W-C:stick/blade" or not (touching_flick and abs(touching_flick[-1] - t) < 1e-12)]
                v = (q - p) / DT if (pushed_now or in_net) else v
                if in_net:
                    v = np.zeros(2)
                p = q
                touching.append((t, tuple(sorted(set(hits)))))
            out.append((t, p.copy(), v.copy()))
        return out, touching

    traj, touching = run(wc)
    T = np.array([x[0] for x in traj]); Pp = np.array([x[1] for x in traj]); V = np.array([x[2] for x in traj])

    def puck_at(tq):
        return np.array([np.interp(tq, T, Pp[:, 0]), np.interp(tq, T, Pp[:, 1])])
    # contact intervals by obstacle
    intervals = []
    figs_by = {f.pid: f for f in movers}
    for t, hits in touching:
        for h in hits:
            part = None
            if h in figs_by:
                p_ = np.array([np.interp(t, T, Pp[:, 0]), np.interp(t, T, Pp[:, 1])])
                q = Point(*to_local(figs_by[h], t, p_))
                part = "stick/blade" if STICK[figs_by[h].kind].distance(q) <= LOW[figs_by[h].kind].distance(q) + 0.3 else "skate/body"
            h = f"{h}:{part}" if part else h
            if intervals and intervals[-1]["obstacle"] == h and t - intervals[-1]["t1"] <= 2 * DT + 1e-9:
                intervals[-1]["t1"] = t
            else:
                intervals.append({"obstacle": h, "t0": t, "t1": t})
    # events
    wcc = [iv for iv in intervals if iv["obstacle"].startswith("W-C")]
    def merged(after, before):
        sel = [iv for iv in wcc if after <= iv["t0"] < before]
        return {"obstacle": ",".join(sorted({iv["obstacle"] for iv in sel})), "t0": sel[0]["t0"], "t1": sel[-1]["t1"], "n_intervals": len(sel)} if sel else None
    flick = merged(fr(turn["start_frame"]), fr(spin["start_frame"]))
    shot = merged(fr(spin["start_frame"]), t1)
    i_goal = int(np.argmax(Pp[:, 0] >= GX)) if (Pp[:, 0] >= GX).any() else None
    t_goal = float(T[i_goal]) if i_goal else None
    y_goal = float(Pp[i_goal, 1]) if i_goal else None
    i_net = int(np.argmax(Pp[:, 0] >= BACK_X - 1e-6)) if (Pp[:, 0] >= BACK_X - 1e-6).any() else None
    t_net = float(T[i_net]) if i_net else None

    def vel_after(iv):
        i = int(np.searchsorted(T, iv["t1"] + 4 * DT))
        return V[i]
    v_flick = vel_after(flick) if flick else None
    v_shot = vel_after(shot) if shot else None
    # residuals vs observations
    resid = []
    for k, w in sorted(obs_p.items()):
        if fr(k) < t0 or fr(k) > t1:
            continue
        q = puck_at(fr(k))
        resid.append({"frame": k, "t": round(fr(k), 4), "observed_mm": [round(float(x), 1) for x in w], "trace_mm": [round(float(x), 1) for x in q],
                      "residual_mm": round(float(np.linalg.norm(q - w)), 1),
                      "reading_uncertainty_mm": next(r["reading_uncertainty_mm"] for r in OBS["puck_take1"] if r["frame"] == k)})
    # ---- nodes and phases
    nodes = []
    phase_of = []
    for i in range(0, len(traj), NODE_EVERY):
        t = traj[i][0]
        if flick and t < flick["t0"]:
            ph = "rest_at_heel"
        elif flick and t <= flick["t1"]:
            ph = "flick_backhand"
        elif shot and t < shot["t0"]:
            ph = "slide"
        elif shot and t <= shot["t1"]:
            ph = "shot_forehand"
        elif t_net is None or t < t_net:
            ph = "shot_free"
        else:
            ph = "in_goal"
        nodes.append({"t": round(t, 5), "x_mm": round(float(traj[i][1][0]), 4), "y_mm": round(float(traj[i][1][1]), 4), "phase": ph})
        phase_of.append(ph)
    ph_list = []
    for n_ in nodes:
        if not ph_list or ph_list[-1]["id"] != n_["phase"]:
            ph_list.append({"id": n_["phase"], "t": [n_["t"], None]})
            if len(ph_list) > 1:
                ph_list[-2]["t"][1] = n_["t"]
    # ---- checks on the saved trace (linear between nodes), every DT, all 12 figures, boards, posts
    nt = np.array([n_["t"] for n_ in nodes]); nx = np.array([n_["x_mm"] for n_ in nodes]); ny = np.array([n_["y_mm"] for n_ in nodes])

    def traced(tq):
        i = int(np.searchsorted(nt, tq, side="right") - 1)
        return np.array([np.interp(tq, nt, nx), np.interp(tq, nt, ny)]), nodes[min(max(i, 0), len(nodes) - 1)]["phase"]
    rows, viol, prev, max_step = {}, [], None, 0.0
    for tq in np.arange(t0, t1 + 1e-9, DT):
        p, ph = traced(tq)
        if prev is not None:
            max_step = max(max_step, float(np.linalg.norm(p - prev)))
        prev = p
        for f in movers:
            c = clearance(f, tq, p)
            r = rows.setdefault((f.pid, ph), {"min_clearance_mm": 1e9, "t_at_min": None})
            if c < r["min_clearance_mm"]:
                r.update(min_clearance_mm=round(float(c), 3), t_at_min=round(float(tq), 5))
            if c < -PEN_TOL:
                viol.append((f.pid, ph, round(float(tq), 5), round(float(c), 3)))
        bc = BOARD.exterior.distance(Point(*p)) - R_PUCK
        r = rows.setdefault(("boards", ph), {"min_clearance_mm": 1e9, "t_at_min": None})
        if bc < r["min_clearance_mm"]:
            r.update(min_clearance_mm=round(float(bc), 3), t_at_min=round(float(tq), 5))
        if bc < -PEN_TOL:
            viol.append(("boards", ph, round(float(tq), 5), round(float(bc), 3)))
        for k, po in enumerate(POSTS):
            pc = float(np.linalg.norm(p - po)) - R_PUCK - POST_R
            key = (f"goal_post_{'pos' if k == 0 else 'neg'}_y", ph)
            r = rows.setdefault(key, {"min_clearance_mm": 1e9, "t_at_min": None})
            if pc < r["min_clearance_mm"]:
                r.update(min_clearance_mm=round(pc, 3), t_at_min=round(float(tq), 5))
            if pc < -PEN_TOL:
                viol.append((key[0], ph, round(float(tq), 5), round(pc, 3)))
    vint = {}
    for pid, ph, tq, c in viol:
        a = vint.setdefault((pid, ph), {"t0": tq, "t1": tq, "worst_mm": c})
        a["t1"] = tq; a["worst_mm"] = min(a["worst_mm"], c)
    # unexplained motion: the puck's velocity may change only during a contact or by the fitted friction
    unexplained = []
    res_flick_t = t_flick
    for i in range(2, len(traj)):
        if touching[i - 1][1] or abs(T[i] - res_flick_t) < 2 * DT or abs(T[i] - t_strike) < 2 * DT:
            continue
        dv = V[i] - V[i - 1]
        sp = float(np.linalg.norm(V[i - 1]))
        allowed = a_fric * DT + 1e-6
        if float(np.linalg.norm(dv)) > allowed + 1e-6 and sp > 0:
            unexplained.append(round(float(T[i]), 5))
    events = [
        {"id": "turn.onset", "t_estimate": round(fr(turn["start_frame"]), 4), "status": "observed (first movement of the stick, frames 121-122)"},
        {"id": "contact.flick", "t_estimate": round(flick["t0"], 5) if flick else None, "t_end": round(flick["t1"], 5) if flick else None,
         "speed_mm_s": round(float(np.linalg.norm(v_flick)), 1) if flick else None, "direction_deg": round(math.degrees(math.atan2(v_flick[1], v_flick[0])), 2) if flick else None,
         "part": flick["obstacle"] if flick else None, "contact_point_local_mm": flick_info["contact_local_mm"], "n_contact_intervals": flick["n_intervals"] if flick else None, "status": "derived (pushing contact): back of the blade (backhand) during the counter-clockwise turn"},
        {"id": "spin.onset", "t_estimate": round(fr(spin["start_frame"]), 4), "status": "assumed at the last sharp frame of the turn (frame 128)"},
        {"id": "contact.shot", "t_estimate": round(shot["t0"], 5) if shot else None, "t_end": round(shot["t1"], 5) if shot else None,
         "speed_mm_s": round(float(np.linalg.norm(v_shot)), 1) if shot else None, "direction_deg": round(math.degrees(math.atan2(v_shot[1], v_shot[0])), 2) if shot else None,
         "part": shot["obstacle"] if shot else None, "contact_point_local_mm": shot_info["contact_local_mm"], "n_contact_intervals": shot["n_intervals"] if shot else None, "heading_at_contact_deg": round(wc.theta(shot["t0"]), 2) if shot else None, "arc_at_contact_mm": round(wc.arc(shot["t0"]), 2) if shot else None, "status": "derived (pushing contact): front of the blade (forehand) during the clockwise spin and lunge"},
        {"id": "goal_entry", "t_estimate": round(t_goal, 5) if t_goal else None, "goal_line_y_mm": round(y_goal, 2) if y_goal is not None else None,
         "status": "derived"},
        {"id": "goal_net", "t_estimate": round(t_net, 5) if t_net else None, "status": "rule: the puck stops against the back of the preview cage"},
    ]
    return dict(wc=wc, eg=eg, others=others, movers=movers, nodes=nodes, ph_list=ph_list, events=events, resid=resid, rows=rows, vint=vint, max_step=max_step,
                slide=slide, flick=flick_info, shot=shot_info, a_fric=a_fric, a_rest=a_rest, a_read=a_read, p_rest=p_rest, intervals=intervals, unexplained=unexplained, traced=traced,
                y_goal=y_goal, t0=t0, t1=t1)


def write(res):
    wc, eg = res["wc"], res["eg"]
    t0, t1 = res["t0"], res["t1"]
    trace = {
        "schema": "shot-trace/1",
        "trace_id": "trace.spjass.v1",
        "status": INP["status"],
        "shot": "spjass (centre move)",
        "geometry_version": G["geometry_version"],
        "asset_refs": {"figure_molds_sha256": sha(REPO / "data/figure-molds.json"), "skater_glb_sha256": sha(REPO / "assets/figures/skater_FIN.glb"),
                       "goalie_glb_sha256": sha(REPO / "assets/figures/goalie_SWE.glb"), "skater_scale_k": K_SK, "goalie_scale_k": K_GO,
                       "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()},
        "source": {"observations": "shots/spjass/observations.json", "inputs": "shots/spjass/inputs.json", "recording": OBS["source"]["path"], "recording_sha256": OBS["source"]["sha256"]},
        "time_base": {"t": "source time in seconds = frame / 30 in the TikTok (take 1, real time)", "window_s": [t0, t1]},
        "interpolation": {"arc_mm": "Fritsch-Carlson monotone cubic Hermite through arc_keyframes (held outside)", "theta_deg": "linear between theta_keyframes (held outside)",
                          "puck": "linear between puck.nodes (held outside)", "implementation": "src/model/trace.ts traceEvaluator (mirrors this script)"},
        "pose_convention": "docs/pose.md: pivot on the slot centreline at arc_mm; heading = team home (W 0, E 180 deg) + theta_deg; assume.fixture_axis_on_slot_centreline",
        "figures": {
            "W-C": {"player_id": "W-C", "team": "W", "fixture_path_id": wc.slot.id, "slot_length_mm": round(wc.slot.length, 2), "status": "moving: the spjass",
                    "arc_keyframes": wc.arcs, "theta_keyframes": wc.thetas},
            "E-G": {"player_id": "E-G", "team": "E", "fixture_path_id": Slot("E-G").id, "slot_length_mm": round(Slot("E-G").length, 2),
                    "status": "static (observed blade pose, frame 100, moved onto the slot)",
                    "arc_keyframes": [{"t": t0, "arc_mm": OBS["e_g_blade_pose"]["nearest_arc_mm"], "sigma_mm": 3.0, "source": "frame-100 blade pose, nearest slot point"}],
                    "theta_keyframes": [{"t": t0, "theta_deg": round(OBS["e_g_blade_pose"]["heading_deg"] - 180.0, 2), "sigma_deg": 5.0, "source": "frame-100 blade pose"}]},
            "others": "static assembly pose (validation/16-assembly-poses.json), as the renderer shows them; included in the checks"},
        "puck": {"radius_mm": R_PUCK, "radius_status": "catalog_nominal", "thickness_mm": PUCK_T, "thickness_status": "assumed (preview)",
                 "ice_friction_deceleration_mm_s2": round(float(res["a_fric"]), 1), "ice_friction_status": "fitted to the observed slide (frames " + "-".join(map(str, res["slide"]["frames"])) + ")",
                 "nodes": res["nodes"], "phases": res["ph_list"], "observations_vs_trace_mm": res["resid"]},
        "events": res["events"],
        "uncertainty": {"camera_rms_px": OBS["camera_take1"]["rms_px"], "camera_leave_one_out_rms_px": OBS["camera_take1"]["leave_one_out_rms_px"],
                        "px_per_mm_near_the_action": 2.6, "puck_mm": "2.5 mm sharp frames, 6 mm motion-blurred", "pose": "toe mark 4 px (about 1.5 mm); heading about 4-5 deg", "timing_s": round(1 / FPS, 4)},
        "limitations": INP["limitations"],
    }
    OUT_TRACE.parent.mkdir(parents=True, exist_ok=True)
    samp = []
    traced = res["traced"]
    for tq in np.round(np.arange(t0, t1 + 1e-9, 0.02), 4):
        e = {"t": float(tq)}
        for f in (wc,):
            e[f.pid] = {"arc_mm": round(f.arc(tq), 4), "theta_deg": round(f.theta(tq), 4)}
        p, _ = traced(tq)
        e["puck"] = [round(float(p[0]), 4), round(float(p[1]), 4)]
        samp.append(e)
    trace["evaluation_samples"] = samp
    OUT_TRACE.write_text(json.dumps(trace, indent=1) + "\n")
    checks = {"trace_id": trace["trace_id"], "sampling_s": DT, "max_puck_step_mm": round(res["max_step"], 3), "penetration_tolerance_mm": PEN_TOL,
              "contact_rule": "CLAUDE.md 'Contact physics': the puck may touch figures, boards and goal but never overlap them (every 0.25 ms, whole trace, all 12 figures, no phase exemptions)",
              "min_clearance_by_obstacle_and_phase": [{"obstacle": k[0], "phase": k[1], **v} for k, v in sorted(res["rows"].items()) if v["min_clearance_mm"] < 30],
              "unexpected_penetrations": [{"obstacle": k[0], "phase": k[1], **v} for k, v in res["vint"].items()],
              "approved_exceptions": [],
              "contacts": [{**iv, "t0": round(iv["t0"], 5), "t1": round(iv["t1"], 5)} for iv in res["intervals"]],
              "unexplained_velocity_changes": res["unexplained"][:20], "unexplained_count": len(res["unexplained"]),
              "slide_fit": res["slide"], "flick": res["flick"], "shot": res["shot"], "rest": {"arc_mm_reading": res["a_read"], "arc_mm_used": res["a_rest"], "puck_rest_mm": [round(float(x), 2) for x in res["p_rest"]]},
              "goal_line": {"x_mm": GX, "crossing_y_mm": round(res["y_goal"], 2) if res["y_goal"] is not None else None,
                            "inside_mouth_window_y_mm": [round(GY - HALF + POST_R + R_PUCK, 1), round(GY + HALF - POST_R - R_PUCK, 1)]},
              "observations_vs_trace_mm": res["resid"]}
    OUT_CHECKS.write_text(json.dumps(checks, indent=1) + "\n")
    return trace, checks


# ---------------------------------------------------------------- diagnostics
def sheet(res):
    wc, movers, traced = res["wc"], res["movers"], res["traced"]
    ev = {e["id"]: e for e in res["events"]}
    S, W_, H_ = 2.3, 560, 640

    def P(w):  # top view: +x (toward goal.E) up the panel, +y to the left; world x 115..345, y -120..120
        return (W_ / 2 - w[1] * S, H_ - 30 - (w[0] - 115) * S)
    times = [("rest", fr(118)), ("flick", ev["contact.flick"]["t_estimate"]), ("frame 127", fr(127)), ("spin", fr(130)),
             ("shot", ev["contact.shot"]["t_estimate"]), ("goal", ev["goal_entry"]["t_estimate"]), ("frame 134", fr(134)), ("net", ev["goal_net"]["t_estimate"])]
    tiles = []
    for name, tq in times:
        if tq is None:
            continue
        im = Image.new("RGB", (W_, H_), "white"); d = ImageDraw.Draw(im)
        for po in POSTS:
            c = P(po); d.ellipse([c[0] - POST_R * S, c[1] - POST_R * S, c[0] + POST_R * S, c[1] + POST_R * S], fill=(200, 0, 0))
        gl = [P((GX, GY - HALF)), P((GX, GY + HALF))]; d.line(gl, fill=(200, 0, 0), width=2)
        d.line([P((GX + DEPTH, GY - HALF)), P((GX + DEPTH, GY + HALF))], fill=(200, 120, 120), width=1)
        sl = Slot("W-C"); d.line([P(sl.at(a)) for a in np.arange(150, sl.length, 2)], fill=(60, 60, 60), width=6)
        for f in movers:
            poly = world_polygon(f, tq)
            for g in ([poly] if poly.geom_type == "Polygon" else list(poly.geoms)):
                pts_ = [P(c) for c in g.exterior.coords]
                if min(p_[1] for p_ in pts_) < H_ and max(p_[1] for p_ in pts_) > 0:
                    d.polygon(pts_, fill=(150, 190, 255) if f.pid == "W-C" else (255, 225, 120), outline=(30, 30, 30))
        trail = [P(traced(x)[0]) for x in np.arange(max(res["t0"], tq - 0.12), tq, 0.002)]
        if len(trail) > 1:
            d.line(trail, fill=(255, 150, 0), width=2)
        p, ph = traced(tq); c = P(p)
        d.ellipse([c[0] - R_PUCK * S, c[1] - R_PUCK * S, c[0] + R_PUCK * S, c[1] + R_PUCK * S], outline=(0, 0, 0), width=2)
        clr = min(clearance(f, tq, p) for f in movers)
        d.text((8, 6), f"{name}  t={tq:.4f} s  ({tq * FPS:.1f} fr)  phase {ph}", fill=(0, 0, 0), font=FB)
        d.text((8, 30), f"W-C arc {wc.arc(tq):.1f} mm  theta {wc.theta(tq):.1f} deg   min clearance {clr:+.2f} mm", fill=(0, 120, 0) if clr >= -PEN_TOL else (200, 0, 0), font=FS)
        tiles.append(im)
    cols = 4
    sheet_ = Image.new("RGB", (W_ * cols, H_ * ((len(tiles) + cols - 1) // cols) + 40), "white")
    for i, im in enumerate(tiles):
        sheet_.paste(im, ((i % cols) * W_, 40 + (i // cols) * H_))
    ImageDraw.Draw(sheet_).text((10, 8), "trace.spjass.v1 - top view (goal.E up, +y left): W-C blue, E-G and others yellow (low geometry, z < puck top), puck black, recent path orange", fill=(0, 0, 0), font=FB)
    sheet_.save(OUT_PNG)


if __name__ == "__main__":
    res = main()
    if os.environ.get("SPJASS_OVERRIDE"):
        ev = {e["id"]: e for e in res["events"]}
        print(json.dumps({"shot": ev["contact.shot"], "goal": ev["goal_entry"], "contacts_after_shot": [iv["obstacle"] for iv in res["intervals"] if ev["contact.shot"]["t_estimate"] and iv["t0"] > ev["contact.shot"]["t_end"]],
                          "unexpected": [k for k in res["vint"]]}))
        raise SystemExit
    trace, checks = write(res)
    sheet(res)
    print(json.dumps({"events": res["events"], "slide": res["slide"], "flick": res["flick"], "shot": res["shot"], "rest": checks["rest"], "goal_line": checks["goal_line"],
                      "unexpected": checks["unexpected_penetrations"], "unexplained_count": checks["unexplained_count"], "max_step": checks["max_puck_step_mm"],
                      "resid": [(r["frame"], r["residual_mm"]) for r in res["resid"]]}, indent=1))
