"""Iteration 22: one constrained motion trace for the '#17 Shovel' shot (status from the user review in inputs.json).

    /root/venvs/blender/bin/python scripts/shot22-trace.py

Inputs: shots/21-shovel/observations.json (iteration-21 observations and segment-1 camera), shots/22-shovel/inputs.json
(blade, orientation and static-figure marks), data/geometry.json (slots, boards, puck), validation/12-hardware-report.json
(preview goal), out/figures/{skater,goalie}.npz (figure meshes, mold units) and validation/players/figures-report.json.
Outputs: data/traces/shovel-17.trace.json, shots/22-shovel/checks.json, validation/22-diagnostics.png, validation/22-prep-foot-drag.png,
validation/22-trace-overview.png.

Reconstruction rules (no general simulator):
- Figures: slot arc length (mm along the canonical visible slot centreline) keyframes at observed source times,
  interpolated by a Fritsch-Carlson monotone cubic (held outside the keyframes). Rotation theta (deg, unwrapped,
  relative to the team home heading) keyframes only where measured (blade marks) or inferred from a stated contact
  rule, interpolated linearly (held outside). Static figures keep their observed pose.
- Puck: before the pass, the observed blob centres (contact mechanics with W-RW not reconstructed). Pass: constant
  velocity from the two flight observations; release time where that line meets the last at-blade sample. Reception:
  first time the moving puck disk touches W-C's low geometry (everything below the puck top). Carry: the puck stays at
  its contact offset in W-C's frame (rigid push by the figure's back). Separation: at W-C's peak slot speed, after
  which the figure decelerates; the puck then keeps its velocity (no friction) until it reaches the back of the goal.
- Checks: finite puck (catalog 25.4 mm, preview thickness 12 mm) against every figure's low geometry, boards, goal
  posts and goal line, sampled every 0.25 ms (puck moves < 1 mm per step).
"""
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

REPO = Path(__file__).resolve().parents[1]
OBS = json.loads((REPO / "shots/21-shovel/observations.json").read_text())
INP = json.loads((REPO / "shots/22-shovel/inputs.json").read_text())
G = json.loads((REPO / "data/geometry.json").read_text())
HW = json.loads((REPO / "validation/12-hardware-report.json").read_text())
FIG = json.loads((REPO / "validation/players/figures-report.json").read_text())
H = np.array(OBS["camera_seg1"]["H_world_mm_to_frame_px"])
HI = np.linalg.inv(H)
SRC = REPO / OBS["source"]["path"]
T0 = OBS["timing"]["segments"][1]["t_start_s"]  # source time of shot time 0 (first frame of segment 1)
R_PUCK = G["puck"]["diameter"]["value"] / 2
PUCK_T = HW["puck"]["thickness_mm_preview"]
DT = 0.00025
# Sensitivity runs (not the saved trace): SHOT22_WC_ARC_OFFSET=<mm> shifts every W-C slot reading by that amount (clamped to
# the slot) and writes all outputs to SHOT22_OUT_DIR instead of the repository paths.
WC_ARC_OFFSET = float(os.environ.get("SHOT22_WC_ARC_OFFSET", "0"))
OUT_DIR = Path(os.environ["SHOT22_OUT_DIR"]) if WC_ARC_OFFSET else None
OUT_TRACE = (OUT_DIR / "trace.json") if OUT_DIR else REPO / "data/traces/shovel-17.trace.json"
OUT_CHECKS = (OUT_DIR / "checks.json") if OUT_DIR else REPO / "shots/22-shovel/checks.json"
OUT_DIAG = (OUT_DIR / "diagnostics.png") if OUT_DIR else REPO / "validation/22-diagnostics.png"
OUT_OVER = (OUT_DIR / "overview.png") if OUT_DIR else REPO / "validation/22-trace-overview.png"
FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
FS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
HOME = {"W": 0.0, "E": 180.0}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def to_world(px):
    return cv2.perspectiveTransform(np.array([[px]], float), HI)[0][0]


def to_px(w):
    return cv2.perspectiveTransform(np.array([w], float).reshape(1, -1, 2), H)[0]


# ---------------------------------------------------------------- slots and figure geometry
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

    def nearest(self, q):
        best = (1e9, 0.0)
        for i in range(len(self.P) - 1):
            a, b = self.P[i], self.P[i + 1]
            d = b - a
            t = float(np.clip(np.dot(q - a, d) / np.dot(d, d), 0, 1))
            e = float(np.linalg.norm(q - (a + t * d)))
            if e < best[0]:
                best = (e, self.s[i] + t * np.linalg.norm(d))
        return best  # (distance mm, arc mm)

    def arc_at_row(self, v):
        Q = to_px(self.P)
        for i in range(len(Q) - 1):
            y0, y1 = Q[i, 1], Q[i + 1, 1]
            if (y0 - v) * (y1 - v) <= 0 and y0 != y1:
                f = (v - y0) / (y1 - y0)
                return float(self.s[i] + f * (self.s[i + 1] - self.s[i]))
        return float(self.s[int(np.argmin(np.abs(Q[:, 1] - v)))])


def low_polygon(kind, k):
    """Union of the figure mesh below the puck top (z < puck thickness), local mm, pivot at the origin."""
    d = np.load(REPO / f"out/figures/{kind}.npz")
    V, T = d["verts"] * k, d["tris"]
    sel = T[V[T][:, :, 2].min(1) < PUCK_T]
    polys = [Polygon(V[t][:, :2]) for t in sel]
    polys = [p.buffer(0.01) for p in polys if p.area > 1e-6]
    return unary_union(polys).buffer(0)


K_SK = FIG["scale_k_mm_per_mold_unit"]
K_GO = FIG["scales"]["goalie"]
SK_LOW = low_polygon("skater", K_SK)
GO_LOW = low_polygon("goalie", K_GO)


def part_polygon(kind, k, stick):
    """Low geometry of the stick only (stick=True) or of everything else - skates/feet - (stick=False)."""
    d = np.load(REPO / f"out/figures/{kind}.npz")
    keys = [str(x) for x in d["keys"]]
    V, T, L = d["verts"] * k, d["tris"], d["labels"]
    is_stick = np.isin(L, [keys.index(x) for x in ("stick_metal", "stick_tan") if x in keys])
    sel = T[(V[T][:, :, 2].min(1) < PUCK_T) & (is_stick if stick else ~is_stick)]
    polys = [Polygon(V[t][:, :2]).buffer(0.01) for t in sel]
    return unary_union([q for q in polys if q.area > 1e-6]).buffer(0)


# No-interpenetration rule (CLAUDE.md "Contact physics"): the puck disk may touch figure geometry but never overlap it.
EPS = 0.05  # mm: projected puck centres are placed this far outside the contact distance
PEN_TOL = 0.1  # mm: any overlap deeper than this (between 0.5 ms nodes, checked every 0.25 ms) is a violation
SK_FOOT = part_polygon("skater", K_SK, stick=False)
# puck-centre positions (skater-local) where the puck touches a skate/foot and is clear of everything else (stick included)
SK_FOOT_CONTACT = SK_FOOT.buffer(R_PUCK + EPS, 64).boundary.difference(SK_LOW.buffer(R_PUCK, 64))
LOW_OUT = {"skater": SK_LOW.buffer(R_PUCK + EPS, 64), "goalie": GO_LOW.buffer(R_PUCK + EPS, 64)}
_out = LOW_OUT["skater"]
SK_RING = max(([_out] if _out.geom_type == "Polygon" else list(_out.geoms)), key=lambda g: g.area).exterior  # touching outline


BOARD = Polygon(G["board"]["inner_boundary"]["world"]["points_mm"])


def ring_local(qa, qb, f, way):
    """Skater-local puck centre a fraction f of the way from qa to qb, sliding along the touching outline of the figure
    (way +1 = the shorter way round, -1 = the longer way); the end offsets of qa, qb from the outline are blended in linearly."""
    L_ = SK_RING.length
    sa, sb = SK_RING.project(Point(*qa)), SK_RING.project(Point(*qb))
    d_ = (sb - sa) % L_
    short = d_ if d_ <= L_ / 2 else d_ - L_  # robust when qa and qb (nearly) coincide
    dl = short if way > 0 else short - np.sign(short or 1.0) * L_
    ra, rb = np.array(SK_RING.interpolate(sa).coords[0]), np.array(SK_RING.interpolate(sb).coords[0])
    r = np.array(SK_RING.interpolate((sa + f * dl) % L_).coords[0])
    return r + (1 - f) * (np.asarray(qa) - ra) + f * (np.asarray(qb) - rb)


def push_out(f, t, p):
    """Pushing contact: if the puck centre p is closer than the puck radius to figure f's geometry at time t, move it to the
    nearest position where it just touches (kinematic projection: no masses, friction or restitution). Returns (p, push)."""
    q = Point(*f.to_local(t, p))
    out = LOW_OUT[f.kind]
    if not out.contains(q):
        return np.asarray(p, float), 0.0
    rings = [out.exterior] + list(out.interiors) if out.geom_type == "Polygon" else [g.exterior for g in out.geoms] + [i for g in out.geoms for i in g.interiors]
    best = min((r.interpolate(r.project(q)) for r in rings), key=lambda z: z.distance(q))
    w = f.to_w(t, np.array(best.coords[0]))
    return w, float(np.linalg.norm(w - p))


def solve_foot_contact(slot, p_obs, sigma_p, arc_prior, theta_prior):
    """W-RW pose (arc mm, heading deg) at one puck observation such that the puck touches a skate (the foot) and nothing
    overlaps it. Minimises (push/sigma_p)^2 + ((arc - arc_obs)/sigma)^2 + ((heading - visual)/sigma)^2 over a grid, then refines.
    Returns arc, heading, push (mm) and the adjusted puck centre (world)."""
    p_obs = np.asarray(p_obs, float)

    def cost(s, th):
        q = Point(*(rot(th).T @ (p_obs - slot.at(s))))
        dl = SK_FOOT_CONTACT.distance(q)
        c = (dl / sigma_p) ** 2
        if arc_prior:
            c += ((s - arc_prior[0]) / arc_prior[1]) ** 2
        if theta_prior:
            c += ((((th - theta_prior[0] + 180) % 360) - 180) / theta_prior[1]) ** 2
        return c, dl
    s0 = slot.nearest(p_obs)[1]
    best = (1e18, 0.0, 0.0, 0.0)
    for s in np.arange(max(0.0, s0 - 70), min(slot.length, s0 + 70) + 1e-9, 1.0):
        if np.linalg.norm(p_obs - slot.at(s)) > 75:
            continue
        for th in range(0, 360, 2):
            c, dl = cost(s, th)
            if c < best[0]:
                best = (c, s, float(th), dl)
    for step_s, step_t in ((0.25, 0.25), (0.05, 0.05)):
        _, s1, t1, _ = best
        for s in np.arange(max(0.0, s1 - 4 * step_s), min(slot.length, s1 + 4 * step_s) + 1e-9, step_s):
            for th in np.arange(t1 - 8 * step_t, t1 + 8 * step_t + 1e-9, step_t):
                c, dl = cost(s, th)
                if c < best[0]:
                    best = (c, float(s), float(th), dl)
    c, s, th, dl = best
    piv = slot.at(s)
    q = Point(*(rot(th).T @ (p_obs - piv)))
    geoms = SK_FOOT_CONTACT.geoms if SK_FOOT_CONTACT.geom_type == "MultiLineString" else [SK_FOOT_CONTACT]
    near = min((g.interpolate(g.project(q)) for g in geoms), key=lambda z: z.distance(q))
    return {"arc_mm": s, "heading_deg": th, "push_mm": dl, "cost": c, "puck_adj": piv + rot(th) @ np.array(near.coords[0])}
BLADE = {"skater": (np.array(FIG["assets"]["skater_FIN"]["blade_heel_mm"]), np.array(FIG["assets"]["skater_FIN"]["blade_toe_mm"])),
         "goalie": (np.array(FIG["assets"]["goalie_SWE"]["blade_heel_mm"]), np.array(FIG["assets"]["goalie_SWE"]["blade_toe_mm"]))}


def rot(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s], [s, c]])


def blade_pose(kind, heel_w, toe_w):
    lh, lt = BLADE[kind]
    h = math.degrees(math.atan2(*(toe_w - heel_w)[::-1])) - math.degrees(math.atan2(*(lt - lh)[::-1]))
    R = rot(h)
    piv = heel_w - R @ lh
    return h, piv


# ---------------------------------------------------------------- interpolation (mirrored in src/model/trace.ts)
def pchip_slopes(x, y):
    n = len(x)
    h = np.diff(x)
    dl = np.diff(y) / h
    m = np.zeros(n)
    if n == 2:
        m[:] = dl[0]
        return m
    for i in range(1, n - 1):
        if dl[i - 1] * dl[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / dl[i - 1] + w2 / dl[i])
    m[0] = end_slope(h[0], h[1], dl[0], dl[1])
    m[-1] = end_slope(h[-1], h[-2], dl[-1], dl[-2])
    return m


def end_slope(h0, h1, d0, d1):
    m = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
    if m * d0 <= 0:
        return 0.0
    if d0 * d1 <= 0 and abs(m) > abs(3 * d0):
        return 3 * d0
    return m


def pchip_eval(x, y, m, t):
    if t <= x[0]:
        return float(y[0])
    if t >= x[-1]:
        return float(y[-1])
    i = int(np.searchsorted(x, t) - 1)
    h = x[i + 1] - x[i]
    s = (t - x[i]) / h
    h00, h10, h01, h11 = 2 * s**3 - 3 * s**2 + 1, s**3 - 2 * s**2 + s, -2 * s**3 + 3 * s**2, s**3 - s**2
    return float(h00 * y[i] + h10 * h * m[i] + h01 * y[i + 1] + h11 * h * m[i + 1])


def lin_eval(x, y, t):
    return float(np.interp(t, x, y))


class Figure:
    def __init__(self, pid, team, kind, arcs, thetas):
        self.pid, self.team, self.kind = pid, team, kind
        self.slot = Slot(pid)
        self.arcs = sorted(arcs, key=lambda k: k["t"])
        self.thetas = sorted(thetas, key=lambda k: k["t"])
        self.ax = np.array([k["t"] for k in self.arcs])
        self.ay = np.array([k["arc_mm"] for k in self.arcs])
        self.am = pchip_slopes(self.ax, self.ay) if len(self.ax) > 1 else np.zeros(1)
        self.tx = np.array([k["t"] for k in self.thetas])
        self.ty = np.array([k["theta_deg"] for k in self.thetas])
        self.low = SK_LOW if kind == "skater" else GO_LOW

    def arc(self, t):
        return pchip_eval(self.ax, self.ay, self.am, t) if len(self.ax) > 1 else float(self.ay[0])

    def theta(self, t):
        return lin_eval(self.tx, self.ty, t) if len(self.tx) > 1 else float(self.ty[0])

    def pose(self, t):
        return self.slot.at(self.arc(t)), HOME[self.team] + self.theta(t)

    def to_local(self, t, w):
        piv, h = self.pose(t)
        return rot(h).T @ (np.asarray(w) - piv)

    def to_w(self, t, loc):
        piv, h = self.pose(t)
        return piv + rot(h) @ np.asarray(loc)

    def clearance(self, t, w):
        """Signed distance puck edge -> low geometry (negative = penetration)."""
        q = Point(*self.to_local(t, w))
        d = self.low.exterior.distance(q) if self.low.geom_type == "Polygon" else self.low.boundary.distance(q)
        return (-d if self.low.contains(q) else d) - R_PUCK

    def world_polygon(self, t):
        piv, h = self.pose(t)
        R = rot(h)
        geoms = self.low.geoms if self.low.geom_type == "MultiPolygon" else [self.low]
        return [np.array([piv + R @ np.array(c) for c in g.exterior.coords]) for g in geoms]


# ---------------------------------------------------------------- build keyframes
def src_t(shot_t):
    return round(shot_t + T0, 4)


def build_figures():
    o = OBS["figures"]
    figs, notes = {}, {}
    # arc keyframes from iteration 21 (source time)
    arcs = {pid: [{"t": src_t(r["shot_time_s"]), "arc_mm": r["arc_mm"], "sigma_mm": r["arc_uncertainty_mm"],
                   "source": f"obs21 frame {r['recording_frame']} ({r['state']})"} for r in o[pid]["observations"]] for pid in ("W-C", "W-RW")}
    if WC_ARC_OFFSET:
        L_wc = Slot("W-C").length
        for k in arcs["W-C"]:
            k["arc_mm"] = round(min(max(k["arc_mm"] + WC_ARC_OFFSET, 0.0), L_wc), 1)
    # blade-measured headings
    meas = {}
    for m in INP["blade_marks"]["marks"]:
        kind = "goalie" if m["player_id"].endswith("-G") else "skater"
        h, piv = blade_pose(kind, to_world(m["heel_px"]), to_world(m["toe_px"]))
        slot = Slot(m["player_id"])
        e, a = slot.nearest(piv)
        t = frame_shot_time(m["frame"])
        meas.setdefault(m["player_id"], []).append({"frame": m["frame"], "t": t, "heading_deg": h, "pivot": piv, "slot_dist_mm": e, "arc_mm": a})
    unwrap = lambda ref, a: a + 360 * round((ref - a) / 360)  # noqa: E731
    # W-C: measured at 104, 107 (receiving, facing back) and 167 (rest); unobserved in between (blur)
    wc = meas["W-C"]
    th0 = wc[0]["heading_deg"]
    wc_th = [{"t": m["t"], "theta_deg": round(unwrap(th0, m["heading_deg"]) - HOME["W"], 2), "sigma_deg": 4.0,
              "source": f"blade frame {m['frame']}"} for m in wc]
    # W-RW: blade at 102 (-171.5, facing the camera, puck behind it), pass direction -> backhand contact at release,
    # visual back-to-camera at 107, blade at 167. Counter-clockwise rotation (theta increasing), required by the pass.
    wr = {m["frame"]: m for m in meas["W-RW"]}
    th102 = wr[102]["heading_deg"]
    figs_meta = {"wc_meas": wc, "wr_meas": list(wr.values())}
    return arcs, wc_th, th102, wr, figs_meta


FRAME_T = {}


def frame_shot_time(fr):
    for pid in OBS["figures"]:
        for r in OBS["figures"][pid]["observations"]:
            FRAME_T[r["recording_frame"]] = r["shot_time_s"]
    for r in OBS["puck"]["observations"]:
        FRAME_T[r["recording_frame"]] = r["shot_time_s"]
    if fr in FRAME_T:
        return src_t(FRAME_T[fr])
    return round(segment_time(fr), 4)  # frames without an iteration-21 row: recording presentation time


_TS = None


def recording_times():
    global _TS
    if _TS is None:
        cap = cv2.VideoCapture(str(SRC))
        ts = []
        while cap.grab():
            ts.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
        _TS = np.array(ts)
    return _TS


def segment_time(fr):
    return float(recording_times()[fr])


def main():
    arcs, wc_th, th102, wr, meta = build_figures()
    puck_obs = [r for r in OBS["puck"]["observations"] if r.get("world_mm_blob_centre")]
    P = {r["recording_frame"]: (src_t(r["shot_time_s"]), np.array(r["world_mm_blob_centre"])) for r in puck_obs}

    # ---- pass flight: constant velocity from the two flight observations (107, 109)
    (t1, p1), (t2, p2) = P[107], P[109]
    v = (p2 - p1) / (t2 - t1)
    t102, p102 = P[102]
    # release: point of the flight line nearest the last at-blade sample (102)
    tau = float(np.dot(p102 - p1, v) / np.dot(v, v))
    t_rel = t1 + tau
    p_rel = p1 + v * tau
    rel_resid = float(np.linalg.norm(p_rel - p102))
    pass_dir = math.degrees(math.atan2(v[1], v[0]))
    # W-RW heading at release: backhand (local -x face) pushes the puck along the pass direction
    h_rel = pass_dir - 180.0
    th_rel = h_rel + 360 * round((th102 - h_rel) / 360)
    if th_rel < th102:
        th_rel += 360  # counter-clockwise from 102
    th_end = wr[167]["heading_deg"] + 360 * math.ceil((th_rel - wr[167]["heading_deg"]) / 360)
    wr_th = [{"t": wr[102]["t"], "theta_deg": round(th102, 2), "sigma_deg": 5.0, "source": "blade frame 102 (facing the camera, puck behind the figure)"},
             {"t": round(t_rel, 4), "theta_deg": round(th_rel, 2), "sigma_deg": 15.0, "source": "inferred: backhand face normal along the pass direction at release (contact rule, not observed)"},
             {"t": src_t(FRAME_T.get(107, 1.3317)), "theta_deg": round(th_end, 2), "sigma_deg": 30.0, "source": "visual: back to the camera in frame 107 (motion blur)"},
             {"t": wr[167]["t"], "theta_deg": round(th_end, 2), "sigma_deg": 3.0, "source": "blade frame 167 (and 131: identical)"}]
    # ---- prep (frames 30-102): W-RW drags the puck with its foot, turning slightly (user, 2026-10-05). At every puck
    # observation the arc and heading are solved so the puck touches a skate and nothing overlaps it (solve_foot_contact).
    slot_wr = Slot("W-RW")
    arc_obs = {}
    for k in arcs["W-RW"]:
        fr = int(k["source"].split()[2])
        arc_obs[fr] = (k["arc_mm"], k["sigma_mm"] or 10.0)
    head_prior = {m["frame"]: (m["heading_deg"], m["sigma_deg"]) for m in INP["prep_heading_marks"]["marks"]}
    head_prior[102] = (HOME["W"] + th102, 5.0)
    unc = {r["recording_frame"]: r["reading_uncertainty_mm"] for r in puck_obs}
    prep_frames = sorted(fr for fr, (tk, _) in P.items() if tk <= t102 + 1e-9)
    prep = {}
    for fr in prep_frames:
        tk, pk = P[fr]
        prep[fr] = solve_foot_contact(slot_wr, pk, unc[fr] + 3.0, arc_obs.get(fr), head_prior.get(fr))
        prep[fr]["t"] = tk
    # Heading at blurred frames without a visual reading, and the turn direction between observations: chosen so the foot
    # carries the puck without sudden jumps - the largest puck step between 1 ms nodes (puck carried in the figure's frame,
    # after pushing contact) is minimised.
    # Linear theta between keyframes would otherwise sweep the stick through the puck on the shorter way round.
    later_arcs = [k for k in arcs["W-RW"] if k["t"] > t102 + 1e-6]

    def sim_interval(k0, k1, fr0, fr1):
        """Largest puck step (mm per 1 ms) over one observation interval for keyframes k0, k1 = (arc, theta)."""
        t0_, t1_ = prep[fr0]["t"], prep[fr1]["t"]
        f_ = Figure("W-RW", "W", "skater", [{"t": t0_, "arc_mm": k0[0]}, {"t": t1_, "arc_mm": k1[0]}],
                    [{"t": t0_, "theta_deg": k0[1]}, {"t": t1_, "theta_deg": k1[1]}])
        qa, qb = f_.to_local(t0_, prep[fr0]["puck_adj"]), f_.to_local(t1_, prep[fr1]["puck_adj"])
        res = []
        for way in (1, -1):
            prev_, worst = None, 0.0
            for tq in np.linspace(t0_, t1_, max(3, int((t1_ - t0_) / 0.001) + 1)):
                pq = f_.to_w(tq, ring_local(qa, qb, (tq - t0_) / (t1_ - t0_), way))
                pq, _ = push_out(f_, tq, pq)
                if prev_ is not None:
                    worst = max(worst, float(np.linalg.norm(pq - prev_)))
                prev_ = pq
                bc_ = BOARD.exterior.distance(Point(*pq)) - R_PUCK if BOARD.contains(Point(*pq)) else -1.0
                if bc_ < -PEN_TOL:
                    worst = max(worst, 1e6 - bc_)  # the puck cannot go through the boards
            res.append((worst, way))
        return min(res)  # (largest step, way round the outline)

    def ccw_cw(prev_th, h):
        d_ = (h - prev_th) % 360
        return [prev_th + d_, prev_th + d_ - 360]

    free = [fr for fr in prep_frames if fr not in head_prior]
    cand = {}
    for fr in free:  # candidate headings every 10 deg, each with its own foot-contact arc
        tk, pk = P[fr]
        cand[fr] = [solve_foot_contact(slot_wr, pk, unc[fr] + 3.0, arc_obs.get(fr), (h_, 3.0)) for h_ in range(0, 360, 10)]
    th_seq = {prep_frames[0]: prep[prep_frames[0]]["heading_deg"] - HOME["W"]}
    i = 1
    while i < len(prep_frames):
        f0, f1 = prep_frames[i - 1], prep_frames[i]
        k0 = (prep[f0]["arc_mm"], th_seq[f0])
        if f1 in free and i + 1 < len(prep_frames):
            f2 = prep_frames[i + 1]
            best_ = None
            for c in cand[f1]:
                for th1 in ccw_cw(k0[1], c["heading_deg"] - HOME["W"]):
                    w1 = sim_interval(k0, (c["arc_mm"], th1), f0, f1)[0]
                    for th2 in ccw_cw(th1, prep[f2]["heading_deg"] - HOME["W"]):
                        sc = max(w1, sim_interval((c["arc_mm"], th1), (prep[f2]["arc_mm"], th2), f1, f2)[0])
                        if best_ is None or sc < best_[0]:
                            best_ = (sc, c, th1, th2)
            _, c, th1, th2 = best_
            prep[f1].update({k: c[k] for k in ("arc_mm", "heading_deg", "push_mm", "puck_adj")})
            th_seq[f1], th_seq[f2] = th1, th2
            i += 2
        else:
            opts = ccw_cw(k0[1], prep[f1]["heading_deg"] - HOME["W"])
            th_seq[f1] = min(opts, key=lambda th1: sim_interval(k0, (prep[f1]["arc_mm"], th1), f0, f1)[0])
            i += 1
    shift = 360 * round((th102 - th_seq[102]) / 360)
    for fr in prep_frames:
        prep[fr]["theta_deg"] = th_seq[fr] + shift
    # way round the outline per interval, for the final keyframes
    for f0, f1 in zip(prep_frames[:-1], prep_frames[1:]):
        prep[f0]["way_to_next"] = sim_interval((prep[f0]["arc_mm"], th_seq[f0]), (prep[f1]["arc_mm"], th_seq[f1]), f0, f1)[1]
    if abs(prep[102]["theta_deg"] - th102) > 20:
        raise SystemExit(f"prep heading at frame 102 ({prep[102]['theta_deg']:.1f}) disagrees with the blade ({th102:.1f})")
    arcs["W-RW"] = later_arcs + [
        {"t": prep[fr]["t"], "arc_mm": round(prep[fr]["arc_mm"], 2), "sigma_mm": arc_obs[fr][1] if fr in arc_obs else None,
         "source": f"solved frame {fr}: puck touches the foot, no overlap" + (f"; skate-row reading {arc_obs[fr][0]} mm" if fr in arc_obs else "")}
        for fr in prep_frames]
    wr_th = [{"t": prep[fr]["t"], "theta_deg": round(prep[fr]["theta_deg"], 2), "sigma_deg": head_prior[fr][1] if fr in head_prior else None,
              "source": f"solved frame {fr}: puck touches the foot" + (f"; visual heading {head_prior[fr][0]} +/- {head_prior[fr][1]} deg" if fr in head_prior else "; no visual reading (blur)")}
             for fr in prep_frames if fr != 102] + wr_th
    P_adj = {fr: (prep[fr]["t"], prep[fr]["puck_adj"]) for fr in prep_frames}
    p102_adj = P_adj[102][1]
    figs = {"W-RW": Figure("W-RW", "W", "skater", arcs["W-RW"], wr_th)}
    # release = last instant the flight-line puck still touches W-RW (the blade pushes it along that line until then)
    wrf = figs["W-RW"]
    t_last = t_rel
    for tq in np.arange(t_rel, t2, DT):
        if wrf.clearance(tq, p_rel + v * (tq - t_rel)) < 0:
            t_last = tq
    t_line0, p_line0 = t_rel, p_rel  # flight line parameter origin
    t_rel_contact_end = float(t_last)

    # ---- static figures
    static = {}
    for m in INP["static_marks"]["marks"]:
        pid = m["player_id"]
        slot = Slot(pid)
        a = slot.arc_at_row(m["feet_px"][1])
        if pid == "E-G":
            g = next(b for b in INP["blade_marks"]["marks"] if b["player_id"] == "E-G")
            h, _ = blade_pose("goalie", to_world(g["heel_px"]), to_world(g["toe_px"]))
            th = ((h - HOME["E"] + 180) % 360) - 180
            th_src, th_sig = "paddle direction, frame 167 (position from the feet)", 15.0
        else:
            th, th_src, th_sig = 0.0, "not measured: team home heading (assumed)", None
        kind = "goalie" if pid.endswith("-G") else "skater"
        static[pid] = Figure(pid, "E", kind, [{"t": 0.0, "arc_mm": round(a, 1), "sigma_mm": None, "source": f"feet frame {m['frame']}"}],
                             [{"t": 0.0, "theta_deg": round(th, 2), "sigma_deg": th_sig, "source": th_src}])
    gx = HW["goal"]["placement_mm"]["E"][0]
    back_x = gx + HW["goal"]["depth_per_goal_mm"]["E"] - R_PUCK
    half = HW["goal"]["mouth_width_per_goal_mm"]["E"] / 2 - HW["goal"]["post_radius_mm"] - R_PUCK
    yc = HW["goal"]["placement_mm"]["E"][1]
    eg = static["E-G"]

    k109 = next(k for k in arcs["W-C"] if k["source"].startswith("obs21 frame 109"))
    k111 = next(k for k in arcs["W-C"] if k["source"].startswith("obs21 frame 111"))
    k116 = next(k for k in arcs["W-C"] if k["source"].startswith("obs21 frame 116"))
    EXPO = 1.0 / OBS["timing"]["segments"][1]["content_rate_fps"]  # upper bound of the exposure (one content frame)
    k114 = next(k for k in arcs["W-C"] if k["source"].startswith("obs21 frame 114"))
    # run marks (inputs.json): arc interval the skates must reach at some instant of the frame's exposure
    run_win = []
    for m in INP["run_marks"]["marks"]:
        kf = {111: k111, 114: k114}[m["frame"]]
        lo_row, hi_row = m["skate_row_px"]
        L_wc = Slot("W-C").length
        run_win.append((kf["t"], min(Slot("W-C").arc_at_row(hi_row) + WC_ARC_OFFSET, L_wc), min(Slot("W-C").arc_at_row(lo_row) + WC_ARC_OFFSET, L_wc), m["frame"]))

    def solve(t_on, t_top, dtheta=0.0):
        """Reception, carry and shot for a W-C run starting at t_on (at the frame-109 arc) and reaching the top end
        (the frame-116 arc) at t_top. Frames 109, 111 and 114 are blurred: used as exposure constraints, not keyframes."""
        ak = [k for k in arcs["W-C"] if k is not k109 and k is not k111 and k is not k114]
        if abs(t_top - k116["t"]) < 2e-4:
            ak = [k for k in ak if k is not k116]
        ak += [{"t": round(t_on, 4), "arc_mm": k109["arc_mm"], "sigma_mm": None, "source": "run onset (solved; frame 109 'starting to move')"},
               {"t": round(t_top, 4), "arc_mm": k116["arc_mm"], "sigma_mm": None, "source": "arrival at the slot top end (solved; frame-111 streak reaches it)"}]
        th = list(wc_th)
        if dtheta:
            # turn during the carry (blurred frames), back to the observed facing by frame 116 (sharp: still facing back)
            tm = round((t_on + t_top) / 2, 4)
            tx_, ty_ = np.array([k["t"] for k in wc_th]), np.array([k["theta_deg"] for k in wc_th])
            base = lin_eval(tx_, ty_, tm)
            th = th + [{"t": tm, "theta_deg": round(base + dtheta, 2), "sigma_deg": None,
                        "source": "solved: turn during the carry (unobserved, frames 109-114 blurred); smallest turn that reaches the far corner without overlap"},
                       {"t": k116["t"], "theta_deg": round(lin_eval(tx_, ty_, k116["t"]), 2), "sigma_deg": None,
                        "source": "visual frame 116: W-C faces back again (sharp); value interpolated between the blade keyframes"}]
        wc = Figure("W-C", "W", "skater", ak, th)
        # exposure constraints: the run starts within frame 109's exposure (blurred, 'starting to move'); during the
        # exposures of frames 111 and 114 the skates reach the re-read row intervals (inputs.json run_marks)
        if not (k109["t"] - EXPO <= t_on <= k109["t"]):
            return None
        for tf, a_lo, a_hi, _ in run_win:
            e0, e1 = wc.arc(tf - EXPO), wc.arc(tf)
            if e1 < a_lo or e0 > a_hi:
                return None
        t = t_rel_contact_end
        t_contact = None
        while t < 1.95:
            if wc.clearance(t, p_rel + v * (t - t_rel)) <= 0:
                t_contact = t
                break
            t += DT
        if t_contact is None:
            return None
        loc = wc.to_local(t_contact, p_rel + v * (t_contact - t_rel))
        q = Point(*loc)
        geoms = wc.low.geoms if wc.low.geom_type == "MultiPolygon" else [wc.low]
        nearest = np.array(min((gg.exterior.interpolate(gg.exterior.project(q)).coords[0] for gg in geoms), key=lambda c: Point(c).distance(q)))
        n = loc - nearest
        n = n / np.linalg.norm(n) if np.linalg.norm(n) > 1e-9 else np.array([-1.0, 0.0])
        if wc.low.contains(q):
            n = -n
        loc_c = nearest + n * R_PUCK
        ts = np.arange(t_contact, t_top, DT)
        if len(ts) < 3:
            return None
        sp = np.gradient([wc.arc(x) for x in ts], DT)
        i_pk = int(np.argmax(sp))
        t_sep = float(ts[i_pk])
        p_sep = wc.to_w(t_sep, loc_c)
        v_sep = (wc.to_w(t_sep + 1e-4, loc_c) - wc.to_w(t_sep - 1e-4, loc_c)) / 2e-4
        if v_sep[0] <= 0:
            return None
        t_goal = t_sep + (gx - p_sep[0]) / v_sep[0]
        t_back = t_sep + (back_x - p_sep[0]) / v_sep[0]
        y_cross = float((p_sep + v_sep * (t_goal - t_sep))[1])
        gmin = min(eg.clearance(tq, p_sep + v_sep * (tq - t_sep)) for tq in np.arange(t_sep, t_back, DT))
        wcmin = min(wc.clearance(tq, p_sep + v_sep * (tq - t_sep)) for tq in np.arange(t_sep + DT, t_back, DT))
        return dict(wc=wc, dtheta=dtheta, t_on=t_on, t_top=t_top, t_contact=t_contact, nearest=nearest, loc_c=loc_c, t_sep=t_sep, p_sep=p_sep, v_sep=v_sep,
                    t_goal=t_goal, t_back=t_back, y_cross=y_cross, goalie_clearance=gmin, wc_after=wcmin,
                    ok=bool(abs(y_cross - yc) <= half and gmin >= 0 and y_cross > yc and wcmin >= -0.5))
    scan = []
    k107_t = next(k["t"] for k in arcs["W-C"] if k["source"].startswith("obs21 frame 107"))
    grid = [(float(a_), float(b_)) for a_ in np.arange(max(k107_t + 0.001, k109["t"] - EXPO), k109["t"] + 1e-9, 0.003)
            for b_ in np.arange(a_ + 0.015, k116["t"] + 1e-9, 0.003) if abs(a_ - k109["t"]) > 2e-4]
    for dth in [0.0] + [s_ * d for d in range(30, 181, 30) for s_ in (1, -1)][:-1]:
        if dth and any(x["feasible"] for x in scan):
            break  # rotation diagnostic only needed when the observed rotation fails
        for t_on, t_top in grid:
            r = solve(t_on, t_top, dth)
            if r:
                scan.append({"t_on": round(t_on, 4), "t_top": round(t_top, 4), "dtheta_deg": dth, "t_contact": round(r["t_contact"], 4),
                             "goal_line_y_mm": round(r["y_cross"], 1), "goalie_clearance_mm": round(r["goalie_clearance"], 1),
                             "peak_puck_speed_mm_s": round(float(np.linalg.norm(r["v_sep"])), 0), "feasible": r["ok"]})
    # The trace keeps W-C's observed rotation (dtheta 0). The other rotation offsets are a diagnostic only: they test
    # whether an unobserved mid-run turn could explain the far-corner goal side.
    rot_scan = []
    for dth in sorted({x["dtheta_deg"] for x in scan}):
        xs = [x for x in scan if x["dtheta_deg"] == dth]
        rot_scan.append({"dtheta_deg": dth, "n": len(xs), "feasible": sum(x["feasible"] for x in xs),
                         "goal_line_y_mm": [min(x["goal_line_y_mm"] for x in xs), max(x["goal_line_y_mm"] for x in xs)],
                         "best_goalie_clearance_mm": max(x["goalie_clearance_mm"] for x in xs)})
    scan0 = [x for x in scan if x["dtheta_deg"] == 0]
    rot_ok = [r for r in rot_scan if r["feasible"] and r["dtheta_deg"] != 0]
    rot_tried = ", ".join(f"{r['dtheta_deg']:+.0f}" for r in sorted(rot_scan, key=lambda r: abs(r["dtheta_deg"])) if r["dtheta_deg"] != 0)
    rot_text = (f"diagnostic only (not in the trace): a single unobserved mid-run W-C rotation offset was tried ({rot_tried} deg, smallest first); "
                + (f"the smallest offset that reaches the far corner is {rot_ok[0]['dtheta_deg']:+.0f} deg ({rot_ok[0]['feasible']} timings, best goalie clearance "
                   f"{rot_ok[0]['best_goalie_clearance_mm']} mm). No frame shows such a turn." if rot_ok else "none reaches the far corner."))
    feas = [x for x in scan0 if x["feasible"]]
    conflict = not feas
    if feas:  # the feasible solution nearest the centroid of the feasible region
        c_on, c_top = np.mean([x["t_on"] for x in feas]), np.mean([x["t_top"] for x in feas])
        best = min(feas, key=lambda x: (x["t_on"] - c_on) ** 2 + (x["t_top"] - c_top) ** 2)
    else:  # least violating: a crossing inside the mouth (a goal), then the largest goalie clearance, then the lower speed
        best = max(scan0, key=lambda x: (abs(x["goal_line_y_mm"] - yc) <= half, x["goalie_clearance_mm"], -x["peak_puck_speed_mm_s"]))
        feas = [best]
    sol = solve(best["t_on"], best["t_top"], best["dtheta_deg"])
    t_on_sel = best["t_on"]
    wc = sol["wc"]
    figs["W-C"] = wc
    t_contact, nearest, loc_c, t_sep, p_sep, v_sep = sol["t_contact"], sol["nearest"], sol["loc_c"], sol["t_sep"], sol["p_sep"], sol["v_sep"]
    t_goal, t_back = sol["t_goal"], sol["t_back"]
    board = Polygon(G["board"]["inner_boundary"]["world"]["points_mm"])
    posts = [np.array([gx, HW["goal"]["placement_mm"]["E"][1] + s * HW["goal"]["mouth_width_per_goal_mm"]["E"] / 2]) for s in (1, -1)]
    # diagnostic: which straight shot directions from the separation point would clear the static goalie and both posts
    # and cross the goal line inside the mouth on the +y side, the far corner from the shooter (user, 2026-10-04)
    eg_poly = unary_union([Polygon(c) for c in eg.world_polygon(t_sep)])
    post_disks = unary_union([Point(*po).buffer(HW["goal"]["post_radius_mm"]) for po in posts])
    ok_dirs = []
    for dd in np.arange(-20.0, 40.0001, 0.1):
        u = np.array([math.cos(math.radians(dd)), math.sin(math.radians(dd))])
        end = p_sep + u * ((back_x - p_sep[0]) / u[0])
        yg = p_sep[1] + u[1] * (gx - p_sep[0]) / u[0]
        line = LineString([tuple(p_sep), tuple(end)])
        if yc < yg <= yc + half and line.distance(eg_poly) >= R_PUCK and line.distance(post_disks) >= R_PUCK:
            ok_dirs.append(round(float(dd), 1))
    dir_diag = {"separation_point_mm": [round(float(x), 1) for x in p_sep], "rule_direction_deg": round(math.degrees(math.atan2(v_sep[1], v_sep[0])), 1),
                "clear_plus_y_directions_deg": [min(ok_dirs), max(ok_dirs)] if ok_dirs else None,
                "goalie_low_geometry_y_mm": [round(float(eg_poly.bounds[1]), 1), round(float(eg_poly.bounds[3]), 1)],
                "note": "straight puck paths from the trace's separation point that clear the static goalie (low geometry) and the posts and enter on the +y side; "
                        "how far the rule-based shot direction is from the far corner the user confirmed"}
    # User review (inputs.json user_review): the puck went in the far corner (+y). The rule direction (slot tangent at
    # separation) misses it, so the shot direction is rotated into the clear far-corner window, at the largest margin to
    # the goalie, the posts and W-C. Speed, separation point and time stay as derived. Assumption, not a measurement.
    def shot_path(wc_, p0, t0, spd, dd):
        """Free puck from the separation point p0 (time t0) at direction dd and speed spd. Where W-C (still moving after
        separation) would overlap it, the puck is pushed out to touching (pushing contact) and keeps its speed along the
        pushed direction. Steps of DT until the back of the cage."""
        u = np.array([math.cos(math.radians(dd)), math.sin(math.radians(dd))])
        pp, vv, tt = np.array(p0, float), spd * u, t0
        pts, touch = [(tt, pp.copy())], []
        while pp[0] < back_x and tt < t0 + 0.3:
            tt += DT
            pn = pp + vv * DT
            pq, push = push_out(wc_, tt, pn)
            if push > 0:
                touch.append(tt)
                dv = pq - pp
                vv = spd * dv / np.linalg.norm(dv)
            pp = pq
            pts.append((tt, pp.copy()))
        return pts, touch

    def shot_eval(wc_, p0, t0, spd, dd):
        pts, touch = shot_path(wc_, p0, t0, spd, dd)
        xs = np.array([q[1][0] for q in pts])
        if not (xs >= gx).any() or xs[0] >= gx:
            return None
        i = int(np.argmax(xs >= gx))
        f_ = (gx - xs[i - 1]) / (xs[i] - xs[i - 1])
        yg = float(pts[i - 1][1][1] + f_ * (pts[i][1][1] - pts[i - 1][1][1]))
        tg = float(pts[i - 1][0] + f_ * (pts[i][0] - pts[i - 1][0]))
        g_clear = min(eg.clearance(tq, pq) for tq, pq in pts)
        p_clear = min(float(np.linalg.norm(pq - po)) - R_PUCK - HW["goal"]["post_radius_mm"] for _, pq in pts for po in posts)
        d_last = pts[-1][1] - pts[-5][1]
        return {"dir": dd, "pts": pts, "touch": touch, "y_goal": yg, "t_goal": tg, "goalie_clearance": g_clear, "post_clearance": p_clear,
                "final_dir": math.degrees(math.atan2(d_last[1], d_last[0])),
                "ok": bool(yc < yg <= yc + half and g_clear >= 0.1 and p_clear >= 0.1)}

    # The far corner (user) with no overlap anywhere: the puck leaves W-C along the carried point's velocity (rule) and
    # slides off W-C if it touches it. Under W-C's observed facing it cannot get there (its own right skate pushes it back
    # toward the goalie), so W-C turns during the carry - the smallest turn that works (cf. the user's technique note
    # "turn the player slightly"; frames 109-114 are blurred, the turn is not observed).
    rule_dir = math.degrees(math.atan2(v_sep[1], v_sep[0]))
    turn_scan, chosen = [], None
    for dth in [0.0] + [sg * d_ for d_ in range(5, 125, 5) for sg in (1, -1)]:
        r = sol if dth == 0 else solve(best["t_on"], best["t_top"], dth)
        if not r:
            continue
        dd = math.degrees(math.atan2(r["v_sep"][1], r["v_sep"][0]))
        ev = shot_eval(r["wc"], r["p_sep"], r["t_sep"], float(np.linalg.norm(r["v_sep"])), dd)
        if ev is None:
            continue
        turn_scan.append({"turn_deg": dth, "t_contact": round(r["t_contact"], 4), "separation_dir_deg": round(dd, 2), "final_dir_deg": round(ev["final_dir"], 2),
                          "goal_line_y_mm": round(ev["y_goal"], 2), "goalie_clearance_mm": round(ev["goalie_clearance"], 2), "ok": ev["ok"]})
        if ev["ok"]:
            chosen = (dth, r, ev)
            break
    shot_fallback = chosen is None
    if shot_fallback:
        # No turn consistent with frame 116 reaches the far corner without overlap. Only with a user-approved exception
        # (inputs.json approved_overlap_exceptions) the accepted shot is kept: straight line at the near edge of the window
        # that clears the goalie and the far post (the smallest overlap with W-C's skate).
        if not any(x["obstacle"] == "W-C" and x["phase"] == "shot_free" for x in INP.get("approved_overlap_exceptions", [])):
            raise SystemExit("the far corner needs an overlap with W-C and no exception is approved: " + json.dumps(turn_scan[:6]))
        lo_d = dir_diag["clear_plus_y_directions_deg"][0]
        u_ = np.array([math.cos(math.radians(lo_d)), math.sin(math.radians(lo_d))])
        spd_ = float(np.linalg.norm(v_sep))
        pts_, tt_ = [], t_sep
        while True:
            pq_ = p_sep + spd_ * u_ * (tt_ - t_sep)
            pts_.append((tt_, pq_))
            if pq_[0] >= back_x:
                break
            tt_ += DT
        i_ = next(j for j, q in enumerate(pts_) if q[1][0] >= gx)
        chosen = (0.0, sol, {"dir": lo_d, "pts": pts_, "touch": [], "y_goal": float(pts_[i_][1][1]), "t_goal": float(pts_[i_][0]),
                             "final_dir": lo_d, "ok": False})
    w_c_turn, sol, shot = chosen
    wc = sol["wc"]
    figs["W-C"] = wc
    t_contact, nearest, loc_c, t_sep, p_sep, v_sep = sol["t_contact"], sol["nearest"], sol["loc_c"], sol["t_sep"], sol["p_sep"], sol["v_sep"]
    dir_rule = rule_dir
    dir_used = shot["dir"]
    if shot_fallback:
        v_sep = float(np.linalg.norm(v_sep)) * np.array([math.cos(math.radians(dir_used)), math.sin(math.radians(dir_used))])
    dir_status = ("rule-based (not observed): W-C peak slot speed, direction of the carried point" +
                  (f"; W-C turns {w_c_turn:+.0f} deg during the carry (assumed: smallest turn that reaches the far corner without overlap)" if w_c_turn else ""))
    if shot_fallback:
        dir_status = ("assumed: rotated from the rule direction to the near edge of the window that clears the goalie and the far post "
                      "(user review 2026-10-04: far corner); brushes W-C's right skate - user-approved exception shot.W-C_right_skate_brush (2026-10-05)")
    dir_diag["w_c_turn_scan"] = turn_scan
    dir_diag["applied_w_c_turn_deg"] = w_c_turn
    dir_diag["final_direction_after_contact_deg"] = round(shot["final_dir"], 2)
    dir_diag["contact_with_W-C_after_separation_s"] = [round(shot["touch"][0], 4), round(shot["touch"][-1], 4)] if shot["touch"] else None
    shot_t = np.array([q[0] for q in shot["pts"]])
    shot_x = np.array([q[1][0] for q in shot["pts"]])
    shot_y = np.array([q[1][1] for q in shot["pts"]])
    t_goal = shot["t_goal"]
    t_back = float(shot_t[-1])
    t_rel_line = t_rel
    t_rel = t_rel_contact_end
    p_rel = p_line0 + v * (t_rel - t_line0)

    wrf_ = figs["W-RW"]
    prep_tl = np.array([prep[fr]["t"] for fr in prep_frames])
    prep_ql = [wrf_.to_local(prep[fr]["t"], prep[fr]["puck_adj"]) for fr in prep_frames]

    def puck(tq):
        if tq <= t102:
            # carried by the foot: between the foot contacts at the observations the puck slides along the figure's touching
            # outline (in the figure's own frame), so it moves with the figure and never passes through it
            if tq <= prep_tl[0]:
                return wrf_.to_w(prep_tl[0], prep_ql[0]), "prep_foot_drag"
            j = int(np.searchsorted(prep_tl, tq) - 1)
            f_ = (tq - prep_tl[j]) / (prep_tl[j + 1] - prep_tl[j])
            return wrf_.to_w(tq, ring_local(prep_ql[j], prep_ql[j + 1], f_, prep[prep_frames[j]]["way_to_next"])), "prep_foot_drag"
        if tq <= t_rel:
            f = (tq - t102) / (t_rel - t102)
            return p102_adj + f * (p_rel - p102_adj), "pre_release_interpolated"
        if tq <= t_contact:
            return p_rel + v * (tq - t_rel), "pass_free"
        if tq <= t_sep:
            return wc.to_w(tq, loc_c), "carried_by_W-C"
        if tq <= t_back:
            return np.array([np.interp(tq, shot_t, shot_x), np.interp(tq, shot_t, shot_y)]), "shot_free"
        return np.array([shot_x[-1], shot_y[-1]]), "in_goal_rest"

    t_start, t_end = src_t(0.05), src_t(1.73)
    all_figs = {**figs, **static}
    # puck nodes every 0.5 ms (the figures move up to a few mm per ms) plus the exact observation and phase times. In the
    # observation-anchored phases the nominal puck is pushed out of every figure (pushing contact); the carried phase is
    # rigid at a touching offset and the shot path already includes its contact.
    nodes_t = sorted(set(list(np.round(np.arange(t_start, t_end, 0.0005), 5)) + [round(k[0], 5) for k in P_adj.values()] +
                         [round(x, 5) for x in (t_rel, t_contact, t_sep, t_back, t_end)]))
    nodes, push_by_phase = [], {}
    for tq in nodes_t:
        p, ph = puck(tq)
        if ph in ("prep_foot_drag", "pre_release_interpolated", "pass_free"):
            for _ in range(3):
                moved = 0.0
                for f in all_figs.values():
                    p, d_ = push_out(f, tq, p)
                    moved += d_
                    push_by_phase[ph] = max(push_by_phase.get(ph, 0.0), d_)
                if moved == 0:
                    break
        nodes.append({"t": round(float(tq), 5), "x_mm": round(float(p[0]), 3), "y_mm": round(float(p[1]), 3), "phase": ph})
    node_t = np.array([n["t"] for n in nodes])
    node_x = np.array([n["x_mm"] for n in nodes])
    node_y = np.array([n["y_mm"] for n in nodes])

    def puck_traced(tq):
        """The puck exactly as saved (linear between nodes) - what the renderer evaluates."""
        i = int(np.searchsorted(node_t, tq, side="right") - 1)
        ph = nodes[min(max(i, 0), len(nodes) - 1)]["phase"]
        return np.array([np.interp(tq, node_t, node_x), np.interp(tq, node_t, node_y)]), ph

    # ---- clearance checks
    post_r = HW["goal"]["post_radius_mm"]
    rows = {}
    viol = []
    prev = None
    max_step = 0.0
    for tq in np.arange(t_start, t_end, DT):
        p, ph = puck_traced(tq)
        if prev is not None:
            max_step = max(max_step, float(np.linalg.norm(p - prev)))
        prev = p
        for pid, f in all_figs.items():
            c = f.clearance(tq, p)
            key = (pid, ph)
            r = rows.setdefault(key, {"min_clearance_mm": 1e9, "t_at_min": None})
            if c < r["min_clearance_mm"]:
                r.update(min_clearance_mm=round(float(c), 2), t_at_min=round(float(tq), 4))
            if c < -PEN_TOL:  # no exemptions: touching is allowed, overlap never
                viol.append((pid, ph, round(float(tq), 4), round(float(c), 2)))
        bc = board.exterior.distance(Point(*p)) - R_PUCK
        if bc < -PEN_TOL:
            viol.append(("boards", ph, round(float(tq), 4), round(float(bc), 2)))
        r = rows.setdefault(("boards", ph), {"min_clearance_mm": 1e9, "t_at_min": None})
        if bc < r["min_clearance_mm"]:
            r.update(min_clearance_mm=round(float(bc), 2), t_at_min=round(float(tq), 4))
        for k, po in enumerate(posts):
            pc = float(np.linalg.norm(p - po)) - R_PUCK - post_r
            r = rows.setdefault((f"goal_post_{'pos' if k == 0 else 'neg'}_y", ph), {"min_clearance_mm": 1e9, "t_at_min": None})
            if pc < r["min_clearance_mm"]:
                r.update(min_clearance_mm=round(pc, 2), t_at_min=round(float(tq), 4))
            if pc < 0:
                viol.append((f"goal_post_{k}", ph, round(float(tq), 4), round(pc, 2)))
    # goal-line crossing window
    y_cross = shot["y_goal"]
    half = HW["goal"]["mouth_width_per_goal_mm"]["E"] / 2 - post_r - R_PUCK
    yc = HW["goal"]["placement_mm"]["E"][1]
    # group violations into intervals
    vint, approved = {}, {}
    exc = {(x["obstacle"], x["phase"]): x for x in INP.get("approved_overlap_exceptions", [])}
    for pid, ph, tq, c in viol:
        if (pid, ph) in exc and c >= -exc[(pid, ph)]["max_overlap_mm"]:
            a = approved.setdefault(exc[(pid, ph)]["id"], {"obstacle": pid, "phase": ph, "t0": tq, "t1": tq, "worst_mm": c,
                                                             "max_overlap_mm": exc[(pid, ph)]["max_overlap_mm"], "approved_by": exc[(pid, ph)]["approved_by"]})
            a["t1"] = tq
            a["worst_mm"] = min(a["worst_mm"], c)
            continue
        k = (pid, ph)
        a = vint.setdefault(k, {"t0": tq, "t1": tq, "worst_mm": c})
        a["t1"] = tq
        a["worst_mm"] = min(a["worst_mm"], c)
    obs_win = {e["id"]: [src_t(e["interval_s"][0]), src_t(e["interval_s"][1])] for e in OBS["events"]}
    events = [
        {"id": "pass.release", "t_estimate": round(t_rel, 4), "observed_interval": obs_win["pass.release"],
         "inside_observed_interval": obs_win["pass.release"][0] <= t_rel <= obs_win["pass.release"][1], "by": "W-RW (backhand, rotating counter-clockwise)",
         "derivation": f"flight line through puck observations at frames 107 and 109 (constant velocity {np.linalg.norm(v):.0f} mm/s, direction {pass_dir:.1f} deg); "
                       f"the line passes the last at-blade sample (frame 102) at t = {t_rel_line:.4f} s (residual {rel_resid:.1f} mm); release = last instant W-RW's rotating geometry still touches the puck on that line",
         "status": "derived"},
        {"id": "contact.W-C_reception", "t_estimate": round(t_contact, 4), "observed_interval": obs_win["contact.W-C_reception"],
         "inside_observed_interval": obs_win["contact.W-C_reception"][0] <= t_contact <= obs_win["contact.W-C_reception"][1],
         "contact_point_local_mm": [round(float(x), 1) for x in nearest], "puck_centre_local_mm": [round(float(x), 1) for x in loc_c],
         "derivation": "first overlap of the flying puck disk with W-C's geometry below the puck top (0.25 ms steps)",
         "w_c_run_timing": {"t_onset": best["t_on"], "t_top": best["t_top"], "mid_run_rotation_change_deg": 0,
                            "feasible_t_onset": [min(x["t_on"] for x in feas), max(x["t_on"] for x in feas)],
                            "feasible_t_top": [min(x["t_top"] for x in feas), max(x["t_top"] for x in feas)],
                            "feasible_count": 0 if conflict else len(feas), "scanned": len(scan0), "rule_reaches_far_corner": not conflict,
                            "scan_extrema": {"goal_line_y_mm": [min(x["goal_line_y_mm"] for x in scan0), max(x["goal_line_y_mm"] for x in scan0)],
                                             "goalie_clearance_mm": [min(x["goalie_clearance_mm"] for x in scan0), max(x["goalie_clearance_mm"] for x in scan0)]},
                            "rotation_diagnostic": rot_text,
                            "rule": "W-C holds its frame-109 arc until the onset and reaches the frame-116 top arc at t_top (Fritsch-Carlson run). Blurred frames 109, 111 and 114 are exposure constraints, not keyframes: the run starts within frame 109's exposure, and during the exposures of 111 and 114 the skates reach the re-read row intervals (inputs.json run_marks; exposure at most 40 ms). Feasible = goal-line crossing inside the mouth on the +y side (far corner, user), puck clearing the goalie and W-C after separation; chosen = nearest the centroid of the feasible region, or, if none is feasible, the least violating timing (crossing inside the mouth, then largest goalie clearance) with rule_reaches_far_corner = false; the shot direction is then adjusted (see shot.separation)."},
         "status": "derived; confirmed by the user (2026-10-04)"},
        {"id": "shot.separation", "t_estimate": round(t_sep, 4), "speed_mm_s": round(float(np.linalg.norm(v_sep)), 0),
         "direction_deg": round(math.degrees(math.atan2(v_sep[1], v_sep[0])), 1),
         "w_c_turn_deg": w_c_turn, "final_direction_after_contact_deg": round(shot["final_dir"], 2),
         "derivation": "time and speed: W-C peak slot speed after contact (the figure decelerates afterwards; the puck keeps its velocity). "
                       "Direction: see status", "status": dir_status},
        {"id": "goal_entry", "t_estimate": round(t_goal, 4) if t_goal else None, "observed_interval": obs_win["goal_entry"],
         "inside_observed_interval": bool(t_goal and obs_win["goal_entry"][0] <= t_goal <= obs_win["goal_entry"][1]),
         "goal_line_y_mm": round(y_cross, 1) if y_cross is not None else None, "mouth_centre_window_y_mm": [round(yc - half, 1), round(yc + half, 1)],
         "goal_side": "+y far corner (goalie's right; user statement)",
         "status": "derived" if (y_cross is not None and yc < y_cross <= yc + half) else "derived; NOT in the far corner (see limitations)"},
    ]
    def fig_out(f, status):
        return {"player_id": f.pid, "team": f.team, "fixture_path_id": f.slot.id, "slot_length_mm": round(f.slot.length, 2), "status": status,
                "arc_keyframes": f.arcs, "theta_keyframes": f.thetas}
    trace = {
        "schema": "shot-trace/1",
        "trace_id": "trace.shovel-17.v2",
        "status": INP["user_review"]["status_after_review"],
        "review": {**{k: v for k, v in INP["user_review"].items() if k != "status_after_review"},
                   "revisions": [{"date": "2026-10-05", "trace_id": "trace.shovel-17.v2", "by": "user instruction",
                                  "instruction": INP["user_instruction_2026_10_05"]["text"], "applied": INP["user_instruction_2026_10_05"]["applied"],
                                  "approved_exceptions": [x["id"] for x in INP.get("approved_overlap_exceptions", [])]}]},
        "geometry_version": G["geometry_version"],
        "asset_refs": {"figure_molds_sha256": sha(REPO / "data/figure-molds.json"),
                       "skater_glb_sha256": sha(REPO / "assets/figures/skater_FIN.glb"), "goalie_glb_sha256": sha(REPO / "assets/figures/goalie_SWE.glb"),
                       "skater_scale_k": K_SK, "goalie_scale_k": K_GO,
                       "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()},
        "source": {"observations": "shots/21-shovel/observations.json", "inputs": "shots/22-shovel/inputs.json", "recording": OBS["source"]["path"],
                   "recording_sha256": OBS["source"]["sha256"]},
        "time_base": {"t": "source time in seconds = presentation time in the recording", "shot_time_offset_s": T0,
                      "note": "shot time = t - offset (iteration-21 tables); segment 1 treated as real time (user: full speed); content 24.9 fps, timestamps +/- 0.017 s",
                      "window_s": [t_start, t_end]},
        "interpolation": {"arc_mm": "Fritsch-Carlson monotone cubic Hermite through arc_keyframes (held outside)", "theta_deg": "linear between theta_keyframes (held outside)",
                          "puck": "linear between puck.nodes (held outside)", "implementation": "src/model/trace.ts evaluateTrace (mirrors this script)"},
        "pose_convention": "docs/pose.md: pivot on the slot centreline at arc_mm; heading = team home (W 0, E 180 deg) + theta_deg; assume.fixture_axis_on_slot_centreline",
        "figures": {"W-C": fig_out(figs["W-C"], "moving: shooter"), "W-RW": fig_out(figs["W-RW"], "moving: passer"),
                    **{pid: fig_out(f, "static (observed frame 167)") for pid, f in static.items()},
                    "others": "not observed in segment 1 (out of frame or not checked): use the static assembly pose, not part of this trace"},
        "puck": {"radius_mm": R_PUCK, "radius_status": "catalog_nominal", "thickness_mm": PUCK_T, "thickness_status": "assumed (preview)", "nodes": nodes,
                 "phases": [
                     {"id": "prep_foot_drag", "t": [t_start, t102], "status": "W-RW drags the puck with its foot (user 2026-10-05): at each observation the puck touches a skate (moved at most the reported push from the blob centre); between observations it is carried in the figure's frame (interpolated between the foot contacts) and pushed out of every figure, so it slides along the foot"},
                     {"id": "pre_release_interpolated", "t": [t102, round(t_rel, 4)], "status": "linear from the frame-102 foot contact to the release point (occluded by W-RW), pushed out of the rotating figure (the backhand pushes the puck)"},
                     {"id": "pass_free", "t": [round(t_rel, 4), round(t_contact, 4)], "status": "constant velocity from two flight observations"},
                     {"id": "carried_by_W-C", "t": [round(t_contact, 4), round(t_sep, 4)], "status": "rule: rigid at the contact offset (occluded in segment 1; contact confirmed by the user)"},
                     {"id": "shot_free", "t": [round(t_sep, 4), round(t_back, 4) if t_back else None], "status": "rule: constant velocity after separation (not observed in segment 1)"},
                     {"id": "in_goal_rest", "t": [round(t_back, 4) if t_back else None, t_end], "status": "assumed: at the back of the preview cage (position in the net not observed)"}],
                 "observations_vs_trace_mm": [{"frame": r["recording_frame"], "t": src_t(r["shot_time_s"]), "observed": r["world_mm_blob_centre"],
                                               "trace": [round(float(x), 1) for x in puck_traced(src_t(r["shot_time_s"]))[0]],
                                               "residual_mm": round(float(np.linalg.norm(puck_traced(src_t(r["shot_time_s"]))[0] - np.array(r["world_mm_blob_centre"]))), 1),
                                               "reading_uncertainty_mm": r["reading_uncertainty_mm"]} for r in puck_obs]},
        "events": events,
        "uncertainty": {"figure_arc_mm": "per keyframe sigma_mm (iteration-21 reading, 4-55 mm)", "theta_deg": "per keyframe sigma_deg; null = not measured",
                        "puck_mm": "blob-centre reading 3-13 mm plus parallax bias (up to half the unknown puck thickness); rule-based phases have no measured uncertainty",
                        "timing_s": 0.017},
        "limitations": [
            *([(f"ASSUMED W-C TURN: with W-C's observed facing, its own right skate pushes the shot back toward the goalie (pushing contact), so "
                f"the puck cannot reach the far corner the user confirmed. W-C turns {w_c_turn:+.0f} deg during the carry (theta keyframe at "
                f"{(best['t_on'] + best['t_top']) / 2:.4f} s; frames 109-114 are blurred, the turn is not observed): the smallest turn in 5-deg steps "
                f"that reaches the far corner with no overlap anywhere. The puck leaves along the carried point's velocity ({dir_used:.1f} deg) "
                f"and enters at y = {shot['y_goal']:.1f} mm.")] if w_c_turn else []),
            *([(f"ASSUMED SHOT DIRECTION with an APPROVED OVERLAP: the rule direction ({dir_rule:.1f} deg) runs into the goalie; the far corner "
                f"(user) is reached at {dir_used:.1f} deg, the near edge of the window that clears the goalie and the far post. On the way the puck "
                "brushes the rear of W-C's right skate (checks approved_exceptions): a pushing contact would send it back toward the goalie, and no "
                "W-C turn consistent with frame 116 avoids it (checks shot_direction_diagnostic.w_c_turn_scan). The user approved this single "
                "exception on 2026-10-05 (skate size unknown, not visible); it is removed when the skate is measured.")] if shot_fallback else []),
            "PREP FOOT DRAG (user, 2026-10-05): W-RW drags the puck with its foot and turns; at each puck observation its arc and heading are "
            "solved so the puck touches a skate with no overlap (checks prep_foot_contacts: puck moved at most the listed push from the read blob "
            "centre); between observations the puck is carried in the figure's frame and slides along the foot (pushing contact), not observed in detail. The turn direction between observations is the "
            "shorter one; the large turns between the board end and centre ice are seen in the recording, their exact timing is not.",
            "Segment 2 (replay) may be a different take (user): it is not used as evidence for this trace.",
            "Recorded on another STIGA edition; positions assume the canonical Play Off 21 slot layout (blade-derived pivots lie 0.4-3 mm from the slots, supporting it).",
            "Slot position readings disagree: the blade-derived pivots (inputs.json blade marks) lie 2-25 mm along the slot from the iteration-21 "
            "skate-row arcs (checks blade_pivot_checks; W-C 18-25 mm further up the slot by blade, W-RW 2-6 mm). The trace keeps the skate-row arcs; "
            "a sensitivity run with every W-C reading shifted +18 mm moves the rule direction further from the far corner (docs/shot22.md).",
            "W-C rotation between 1.78 and 2.78 s source time (the carry) is not observed; linear between the receiving pose and the rest pose.",
            "W-RW rotation during the pass is reconstructed from a contact rule (backhand normal along the pass direction), not observed.",
            "The carry is a rule (rigid push at the first-contact offset), the separation a rule (peak slot speed); both occluded in segment 1.",
            "Blade, skate and stick geometry are the AI-modelled mold at the assumed preview scale: real contact dimensions unknown; puck thickness and goal size are preview values.",
            "Fixture axis assumed on the slot centreline; rod-to-figure transfer, stops and backlash unknown."]}
    checks = {"trace_id": trace["trace_id"], "sampling_s": DT, "max_puck_step_mm": round(max_step, 3),
              "min_clearance_by_obstacle_and_phase": [{"obstacle": k[0], "phase": k[1], **v} for k, v in sorted(rows.items())],
              "unexpected_penetrations": [{"obstacle": k[0], "phase": k[1], **v} for k, v in vint.items()],
              "approved_exceptions": approved,
              "goal_line": {"x_mm": gx, "crossing_y_mm": round(y_cross, 2) if y_cross is not None else None,
                            "clear_window_y_mm": [round(yc - half, 1), round(yc + half, 1)],
                            "inside_window": bool(y_cross is not None and abs(y_cross - yc) <= half)},
              "blade_pivot_checks": [{"player_id": pid, "frame": m["frame"], "heading_deg": round(m["heading_deg"], 1), "pivot_mm": [round(float(x), 1) for x in m["pivot"]],
                                      "distance_to_slot_mm": round(m["slot_dist_mm"], 1), "arc_from_blade_mm": round(m["arc_mm"], 1),
                                      "arc_in_trace_mm": round(all_figs[pid].arc(m["t"]), 1) if pid in all_figs else None}
                                     for pid, ms in (("W-C", meta["wc_meas"]), ("W-RW", meta["wr_meas"])) for m in ms],
              "contact_rule": "CLAUDE.md 'Contact physics': the puck may touch figures, boards and goal but never overlap them (tolerance PEN_TOL, every 0.25 ms, whole trace, no phase exemptions); only user-approved exceptions (inputs.json approved_overlap_exceptions) are allowed",
              "prep_foot_contacts": [{"frame": fr, "t": prep[fr]["t"], "arc_mm": round(prep[fr]["arc_mm"], 2), "skate_row_arc_mm": arc_obs.get(fr, (None,))[0],
                                      "heading_deg": round(prep[fr]["heading_deg"], 2), "visual_heading_deg": head_prior.get(fr, (None,))[0],
                                      "push_from_observed_mm": round(prep[fr]["push_mm"], 2), "observed_sigma_mm": unc[fr] + 3.0} for fr in prep_frames],
              "max_push_out_by_phase_mm": {k: round(v, 2) for k, v in push_by_phase.items()},
              "penetration_tolerance_mm": PEN_TOL,
              "shot_direction_diagnostic": dir_diag, "w_c_onset_scan": scan0, "w_c_rotation_diagnostic": rot_scan}
    # evaluation samples for the TypeScript evaluator cross-check
    samp = []
    for tq in np.round(np.arange(t_start, t_end + 1e-9, 0.04), 4):
        e = {"t": float(tq)}
        for pid, f in all_figs.items():
            e[pid] = {"arc_mm": round(f.arc(tq), 4), "theta_deg": round(f.theta(tq), 4)}
        p = np.array([np.interp(tq, [n["t"] for n in nodes], [n["x_mm"] for n in nodes]), np.interp(tq, [n["t"] for n in nodes], [n["y_mm"] for n in nodes])])
        e["puck"] = [round(float(p[0]), 4), round(float(p[1]), 4)]
        samp.append(e)
    trace["evaluation_samples"] = samp
    OUT_TRACE.parent.mkdir(parents=True, exist_ok=True)
    OUT_TRACE.write_text(json.dumps(trace, indent=1) + "\n")
    OUT_CHECKS.write_text(json.dumps(checks, indent=1) + "\n")
    print(json.dumps({"events": events, "goal_line": checks["goal_line"], "unexpected": checks["unexpected_penetrations"], "max_step": max_step}, indent=1))
    prep_sheet(figs["W-RW"], puck_traced, t_start, t_rel + 0.03, prep)
    render(all_figs, puck_traced, events, t_rel, t_contact, t_goal, posts, board, nodes)


# ---------------------------------------------------------------- diagnostics
def recording_frame_at(t_source):
    ts = recording_times()
    seg = OBS["timing"]["segments"][1]
    idx = np.arange(seg["first_frame"], seg["last_frame"] + 1)
    return int(idx[np.argmin(np.abs(ts[idx] - t_source))])


def read_frames(wanted):
    cap = cv2.VideoCapture(str(SRC))
    out, i = {}, 0
    while True:
        ok, fr = cap.read()
        if not ok or i > max(wanted):
            break
        if i in wanted:
            out[i] = fr
        i += 1
    return out


def prep_sheet(wr, puck, t0, t1, prep):
    """validation/22-prep-foot-drag.png: W-RW (foot blue, stick grey) and the puck every 25 ms, top view centred on the
    fixture axis, with the puck's clearance to the foot and to the stick (touching = 0, never negative)."""
    stick = part_polygon("skater", K_SK, True)
    S, Wt = 3.0, 220
    obs_t = {round(v["t"], 4): fr for fr, v in prep.items()}
    tiles = []
    for tq in np.round(np.arange(t0, t1 + 1e-9, 0.025), 4):
        p, ph = puck(tq)
        piv, h = wr.pose(tq)
        R = rot(h)
        im = Image.new("RGB", (Wt, Wt + 34), "white")
        d = ImageDraw.Draw(im)

        def P(w):
            return (Wt / 2 + (w[0] - piv[0]) * S, 34 + Wt / 2 - (w[1] - piv[1]) * S)
        for poly, col in ((SK_FOOT, (40, 80, 220)), (stick, (140, 140, 140))):
            for g in (poly.geoms if poly.geom_type == "MultiPolygon" else [poly]):
                d.polygon([P(piv + R @ np.array(c)) for c in g.exterior.coords], fill=col)
        q = Point(*(R.T @ (p - piv)))
        c_foot = SK_FOOT.distance(q) - R_PUCK
        c_stick = stick.distance(q) - R_PUCK
        r = R_PUCK * S
        pc = P(p)
        d.ellipse((pc[0] - r, pc[1] - r, pc[0] + r, pc[1] + r), outline=(0, 0, 0), width=3)
        d.ellipse((Wt / 2 - 3, 34 + Wt / 2 - 3, Wt / 2 + 3, 34 + Wt / 2 + 3), fill=(220, 0, 0))
        d.line([P(piv), P(piv + R @ np.array([14.0, 0.0]))], fill=(220, 0, 0), width=2)
        fr = next((f for tt, f in obs_t.items() if abs(tt - tq) < 0.0125), None)
        d.text((4, 2), f"t {tq:.3f} s  {'frame ' + str(fr) if fr else ''}", fill=(0, 0, 0), font=FS)
        d.text((4, 18), f"foot {c_foot:+.1f}  stick {c_stick:+.1f} mm", fill=(0, 120, 0) if min(c_foot, c_stick) >= -PEN_TOL else (200, 0, 0), font=FS)
        tiles.append(im)
    cols = 10
    head = 64
    sheet = Image.new("RGB", (cols * Wt, head + ((len(tiles) + cols - 1) // cols) * (Wt + 34)), "white")
    d = ImageDraw.Draw(sheet)
    d.text((8, 6), "22 (rev. 2026-10-05) - W-RW prep: the foot drags the puck (user rule). Top view centred on the fixture axis (red dot, red tick = facing), "
                   "1 px = 0.33 mm.", fill=(0, 0, 0), font=FB)
    d.text((8, 36), "Blue = skates/feet, grey = stick, black ring = puck. Clearances: puck edge to foot / stick (0 = touching; negative would be an "
                    "overlap). 'frame N' = puck observation (puck touches the foot there).", fill=(0, 0, 0), font=FS)
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % cols) * Wt, head + (i // cols) * (Wt + 34)))
    sheet.save(REPO / "validation/22-prep-foot-drag.png" if not OUT_DIR else OUT_DIR / "prep-foot-drag.png")


def render(figs, puck, events, t_rel, t_contact, t_goal, posts, board, nodes):
    stills = []
    for name, tc in (("pass release", t_rel), ("reception contact", t_contact), ("goal entry", t_goal)):
        for lab, dt in (("before", -0.04), ("at", 0.0), ("after", 0.04)):
            stills.append((f"{lab} {name}", tc + dt))
    frames = read_frames({recording_frame_at(t) for _, t in stills})
    tiles = []
    for label, t in stills:
        fr = frames[recording_frame_at(t)].copy()
        fidx = recording_frame_at(t)
        p, ph = puck(t)
        for pid, f in figs.items():
            for poly in f.world_polygon(t):
                q = np.round(to_px(poly)).astype(np.int32)
                cv2.polylines(fr, [q], True, (255, 255, 0) if pid.startswith("W") else (0, 165, 255), 2, cv2.LINE_AA)
        circ = np.array([p + R_PUCK * np.array([math.cos(a), math.sin(a)]) for a in np.linspace(0, 2 * math.pi, 48)])
        cv2.polylines(fr, [np.round(to_px(circ)).astype(np.int32)], True, (0, 0, 255), 3, cv2.LINE_AA)
        c = to_px(p[None])[0]
        x0, y0 = int(np.clip(c[0] - 380, 0, fr.shape[1] - 760)), int(np.clip(c[1] - 300, 0, fr.shape[0] - 600))
        left = Image.fromarray(cv2.cvtColor(fr[y0:y0 + 600, x0:x0 + 760], cv2.COLOR_BGR2RGB)).resize((456, 360), Image.LANCZOS)
        right = topdown(figs, p, t, posts, board, nodes)
        tile = Image.new("RGB", (456 + 360, 360 + 52), "white")
        tile.paste(left, (0, 52))
        tile.paste(right, (456, 52))
        d = ImageDraw.Draw(tile)
        d.text((6, 4), f"{label}: t = {t:.4f} s (shot {t - T0:.3f} s)", fill=(160, 0, 0), font=FB)
        d.text((6, 30), f"recording frame {fidx} ({recording_times()[fidx]:.3f} s, nearest); puck phase: {ph}", fill=(0, 0, 0), font=FS)
        tiles.append(tile)
    W, Hh = tiles[0].size
    sheet = Image.new("RGB", (3 * W, 3 * Hh + 80), "white")
    d = ImageDraw.Draw(sheet)
    d.text((10, 8), "22 - trace 'shovel-17', ACCEPTED by the user 2026-10-04 (contacts confirmed; far-corner shot direction assumed)",
           fill=(0, 0, 0), font=FB)
    d.text((10, 44), "Left: nearest source frame with the trace projected by the segment-1 camera (red = puck disk, cyan = W figures' low geometry, "
                     "orange = E). Right: top view, 1 px = 0.5 mm. Event times are derived, not observed exactly; goal entry is hidden in segment 1.",
           fill=(0, 0, 0), font=FS)
    for i, tl in enumerate(tiles):
        sheet.paste(tl, ((i % 3) * W, 80 + (i // 3) * Hh))
    sheet.save(OUT_DIAG)
    overview(figs, nodes, posts, board, events)


def topdown(figs, p, t, posts, board, nodes, scale=2.0, size=360):
    im = Image.new("RGB", (size, size), (235, 238, 242))
    d = ImageDraw.Draw(im)
    c = p.copy()

    def S(w):
        return (size / 2 + (w[0] - c[0]) * scale, size / 2 - (w[1] - c[1]) * scale)
    bx = np.array(board.exterior.coords)
    d.line([S(q) for q in bx], fill=(40, 40, 40), width=2)
    for f in figs.values():
        for poly in f.world_polygon(t):
            d.polygon([S(q) for q in poly], outline=(0, 120, 200) if f.team == "W" else (230, 120, 0))
        piv, h = f.pose(t)
        a, b = S(piv), S(piv + 12 * np.array([math.cos(math.radians(h)), math.sin(math.radians(h))]))
        d.line([a, b], fill=(200, 0, 0), width=2)
    for po in posts:
        a = S(po)
        d.ellipse((a[0] - 3, a[1] - 3, a[0] + 3, a[1] + 3), fill=(220, 0, 0))
    gl = HW["goal"]["placement_mm"]["E"][0]
    d.line([S((gl, -60)), S((gl, 60))], fill=(220, 0, 0), width=1)
    path = [S((n["x_mm"], n["y_mm"])) for n in nodes if abs(n["t"] - t) < 0.12]
    if len(path) > 1:
        d.line(path, fill=(120, 120, 120), width=1)
    a = S(p)
    r = R_PUCK * scale
    d.ellipse((a[0] - r, a[1] - r, a[0] + r, a[1] + r), outline=(0, 0, 0), width=2)
    d.text((4, size - 20), "+x right, +y up", fill=(0, 0, 0), font=FS)
    return im


def overview(figs, nodes, posts, board, events):
    scale = 1.0
    xs, ys = [n["x_mm"] for n in nodes], [n["y_mm"] for n in nodes]
    x0, x1, y0, y1 = -120, 360, -240, 120
    W, Hh = int((x1 - x0) * scale * 2), int((y1 - y0) * scale * 2)
    im = Image.new("RGB", (W, Hh + 60), "white")
    d = ImageDraw.Draw(im)

    def S(w):
        return ((w[0] - x0) * 2 * scale, 60 + (y1 - w[1]) * 2 * scale)
    d.line([S(q) for q in np.array(board.exterior.coords)], fill=(40, 40, 40), width=2)
    for pid, f in figs.items():
        P = f.slot.P
        d.line([S(q) for q in P], fill=(170, 170, 170), width=6)
    cols = {"prep_foot_drag": (120, 120, 120), "pre_release_interpolated": (200, 150, 0), "pass_free": (0, 140, 0), "carried_by_W-C": (0, 90, 220),
            "shot_free": (220, 0, 0), "in_goal_rest": (120, 0, 120)}
    for a, b in zip(nodes[:-1], nodes[1:]):
        d.line([S((a["x_mm"], a["y_mm"])), S((b["x_mm"], b["y_mm"]))], fill=cols[b["phase"]], width=3)
    for r in OBS["puck"]["observations"]:
        if r.get("world_mm_blob_centre"):
            a = S(r["world_mm_blob_centre"])
            e = r["reading_uncertainty_mm"] * 2
            d.ellipse((a[0] - e, a[1] - e, a[0] + e, a[1] + e), outline=(0, 0, 0))
    for po in posts:
        a = S(po)
        d.ellipse((a[0] - 4, a[1] - 4, a[0] + 4, a[1] + 4), fill=(220, 0, 0))
    for e in events:
        if e.get("t_estimate"):
            t = e["t_estimate"]
            n = min(nodes, key=lambda n: abs(n["t"] - t))
            a = S((n["x_mm"], n["y_mm"]))
            d.ellipse((a[0] - 6, a[1] - 6, a[0] + 6, a[1] + 6), outline=(0, 0, 0), width=2)
            d.text((a[0] + 8, a[1] - 8), e["id"], fill=(0, 0, 0), font=FS)
    d.text((8, 4), "22 - puck trace, ACCEPTED by the user (2026-10-04), top view, 2 px/mm. Grey = slots; circles = iteration-21", fill=(0, 0, 0), font=FS)
    d.text((8, 22), "observations (radius = 2 x reading uncertainty). Grey prep (observed), amber pre-release, green pass,", fill=(0, 0, 0), font=FS)
    d.text((8, 40), "blue carried by W-C (rule), red shot (" + next((("direction assumed: far corner, user" if e.get("direction_adjustment_deg") else "rule")) for e in events if e["id"] == "shot.separation") + "), purple in the net (assumed).", fill=(0, 0, 0), font=FS)
    im.save(OUT_OVER)


if __name__ == "__main__":
    main()
