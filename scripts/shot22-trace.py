"""Iteration 22: one constrained motion trace for the '#17 Shovel' shot (proposed, not accepted).

    /root/venvs/blender/bin/python scripts/shot22-trace.py

Inputs: shots/21-shovel/observations.json (iteration-21 observations and segment-1 camera), shots/22-shovel/inputs.json
(blade, orientation and static-figure marks), data/geometry.json (slots, boards, puck), validation/12-hardware-report.json
(preview goal), out/figures/{skater,goalie}.npz (figure meshes, mold units) and validation/players/figures-report.json.
Outputs: data/traces/shovel-17.trace.json, shots/22-shovel/checks.json, validation/22-diagnostics.png,
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
            tm = round((t_on + t_top) / 2, 4)
            base = lin_eval(np.array([k["t"] for k in wc_th]), np.array([k["theta_deg"] for k in wc_th]), tm)
            th = th + [{"t": tm, "theta_deg": round(base + dtheta, 2), "sigma_deg": None,
                        "source": "solved: mid-run rotation (unobserved, blurred); smallest change that reproduces the replay goal side"}]
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
    # whether an unobserved mid-run turn could explain the replay's goal side.
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
                + (f"the smallest offset that reproduces the replay is {rot_ok[0]['dtheta_deg']:+.0f} deg ({rot_ok[0]['feasible']} timings, best goalie clearance "
                   f"{rot_ok[0]['best_goalie_clearance_mm']} mm). No frame shows such a turn." if rot_ok else "none reproduces the replay."))
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
    t_rel_line = t_rel
    t_rel = t_rel_contact_end
    p_rel = p_line0 + v * (t_rel - t_line0)

    def puck(tq):
        if tq <= t102:
            ks = sorted(P.values(), key=lambda a: a[0])
            ks = [k for k in ks if k[0] <= t102 + 1e-9]
            return np.array([np.interp(tq, [k[0] for k in ks], [k[1][i] for k in ks]) for i in (0, 1)]), "prep_observed"
        if tq <= t_rel:
            f = (tq - t102) / (t_rel - t102)
            return p102 + f * (p_rel - p102), "pre_release_interpolated"
        if tq <= t_contact:
            return p_rel + v * (tq - t_rel), "pass_free"
        if tq <= t_sep:
            return wc.to_w(tq, loc_c), "carried_by_W-C"
        if t_back is None or tq <= t_back:
            return p_sep + v_sep * (tq - t_sep), "shot_free"
        return p_sep + v_sep * (t_back - t_sep), "in_goal_rest"

    t_start, t_end = src_t(0.05), src_t(1.73)
    # puck nodes: observed samples in prep, 2 ms elsewhere, exact phase boundaries
    nodes_t = sorted(set([k[0] for k in P.values() if k[0] <= t102] + list(np.round(np.arange(t102, t_end, 0.002), 4)) +
                         [round(x, 5) for x in (t_rel, t_contact, t_sep, t_back or t_end, t_end)]))
    nodes = []
    for tq in nodes_t:
        p, ph = puck(tq)
        nodes.append({"t": round(float(tq), 5), "x_mm": round(float(p[0]), 2), "y_mm": round(float(p[1]), 2), "phase": ph})

    # ---- clearance checks
    board = Polygon(G["board"]["inner_boundary"]["world"]["points_mm"])
    posts = [np.array([gx, HW["goal"]["placement_mm"]["E"][1] + s * HW["goal"]["mouth_width_per_goal_mm"]["E"] / 2]) for s in (1, -1)]
    # diagnostic: which straight shot directions from the separation point would clear the static goalie and both posts
    # and cross the goal line inside the mouth on the replay's +y side (same separation point and time as the trace)
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
    dir_diag = {"separation_point_mm": [round(float(x), 1) for x in p_sep], "trace_direction_deg": round(math.degrees(math.atan2(v_sep[1], v_sep[0])), 1),
                "clear_plus_y_directions_deg": [min(ok_dirs), max(ok_dirs)] if ok_dirs else None,
                "goalie_low_geometry_y_mm": [round(float(eg_poly.bounds[1]), 1), round(float(eg_poly.bounds[3]), 1)],
                "note": "straight puck paths from the trace's separation point that clear the static goalie (low geometry) and the posts and enter on the +y side; "
                        "how far the rule-based shot direction is from the replay"}
    post_r = HW["goal"]["post_radius_mm"]
    all_figs = {**figs, **static}
    expected = {"W-C": ("carried_by_W-C",), "W-RW": ("prep_observed", "pre_release_interpolated")}
    rows = {}
    viol = []
    prev = None
    max_step = 0.0
    for tq in np.arange(t_rel - 0.06, t_end, DT):
        p, ph = puck(tq)
        if prev is not None:
            max_step = max(max_step, float(np.linalg.norm(p - prev)))
        prev = p
        for pid, f in all_figs.items():
            c = f.clearance(tq, p)
            key = (pid, ph)
            r = rows.setdefault(key, {"min_clearance_mm": 1e9, "t_at_min": None})
            if c < r["min_clearance_mm"]:
                r.update(min_clearance_mm=round(float(c), 2), t_at_min=round(float(tq), 4))
            if c < -0.5 and ph not in expected.get(pid, ()):
                viol.append((pid, ph, round(float(tq), 4), round(float(c), 2)))
        bc = board.exterior.distance(Point(*p)) - R_PUCK
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
    y_cross = float((p_sep + v_sep * (t_goal - t_sep))[1]) if t_goal else None
    half = HW["goal"]["mouth_width_per_goal_mm"]["E"] / 2 - post_r - R_PUCK
    yc = HW["goal"]["placement_mm"]["E"][1]
    # group violations into intervals
    vint = {}
    for pid, ph, tq, c in viol:
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
                            "feasible_count": 0 if conflict else len(feas), "scanned": len(scan0), "conflict_with_replay": conflict,
                            "scan_extrema": {"goal_line_y_mm": [min(x["goal_line_y_mm"] for x in scan0), max(x["goal_line_y_mm"] for x in scan0)],
                                             "goalie_clearance_mm": [min(x["goalie_clearance_mm"] for x in scan0), max(x["goalie_clearance_mm"] for x in scan0)]},
                            "rotation_diagnostic": rot_text,
                            "rule": "W-C holds its frame-109 arc until the onset and reaches the frame-116 top arc at t_top (Fritsch-Carlson run). Blurred frames 109, 111 and 114 are exposure constraints, not keyframes: the run starts within frame 109's exposure, and during the exposures of 111 and 114 the skates reach the re-read row intervals (inputs.json run_marks; exposure at most 40 ms). Feasible = goal-line crossing inside the mouth on the +y side (replay), puck clearing the goalie and W-C after separation; chosen = nearest the centroid of the feasible region, or, if none is feasible, the least violating timing (crossing inside the mouth, then largest goalie clearance) with conflict_with_replay = true."},
         "status": "derived" if not conflict else "derived; CONFLICT: no scanned run timing reproduces the replay goal side"},
        {"id": "shot.separation", "t_estimate": round(t_sep, 4), "speed_mm_s": round(float(np.linalg.norm(v_sep)), 0),
         "direction_deg": round(math.degrees(math.atan2(v_sep[1], v_sep[0])), 1),
         "derivation": "W-C peak slot speed after contact (the figure decelerates afterwards; the puck keeps its velocity)", "status": "rule-based (not observed)"},
        {"id": "goal_entry", "t_estimate": round(t_goal, 4) if t_goal else None, "observed_interval": obs_win["goal_entry"],
         "inside_observed_interval": bool(t_goal and obs_win["goal_entry"][0] <= t_goal <= obs_win["goal_entry"][1]),
         "goal_line_y_mm": round(y_cross, 1) if y_cross is not None else None, "mouth_centre_window_y_mm": [round(yc - half, 1), round(yc + half, 1)],
         "replay_side": "+y (goalie's right)",
         "status": "derived" if (y_cross is not None and abs(y_cross - yc) <= half and y_cross > yc) else "derived; CONFLICT with the replay (wrong side or outside the mouth; see limitations)"},
    ]
    def fig_out(f, status):
        return {"player_id": f.pid, "team": f.team, "fixture_path_id": f.slot.id, "slot_length_mm": round(f.slot.length, 2), "status": status,
                "arc_keyframes": f.arcs, "theta_keyframes": f.thetas}
    trace = {
        "schema": "shot-trace/1",
        "trace_id": "trace.shovel-17.v1",
        "status": "proposed",
        "review": "not reviewed: contacts and the carry rule await the user's review (iteration 22); not accepted",
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
                     {"id": "prep_observed", "t": [t_start, t102], "status": "observed blob centres; W-RW contact mechanics not reconstructed"},
                     {"id": "pre_release_interpolated", "t": [t102, round(t_rel, 4)], "status": "linear from the last at-blade sample to the release point (occluded by W-RW)"},
                     {"id": "pass_free", "t": [round(t_rel, 4), round(t_contact, 4)], "status": "constant velocity from two flight observations"},
                     {"id": "carried_by_W-C", "t": [round(t_contact, 4), round(t_sep, 4)], "status": "rule: rigid at the contact offset (occluded in segment 1; replay shows the puck just ahead of W-C's feet)"},
                     {"id": "shot_free", "t": [round(t_sep, 4), round(t_back, 4) if t_back else None], "status": "rule: constant velocity after separation (not observed in segment 1)"},
                     {"id": "in_goal_rest", "t": [round(t_back, 4) if t_back else None, t_end], "status": "assumed: at the back of the preview cage (position in the net not observed)"}],
                 "observations_vs_trace_mm": [{"frame": r["recording_frame"], "t": src_t(r["shot_time_s"]), "observed": r["world_mm_blob_centre"],
                                               "trace": [round(float(x), 1) for x in puck(src_t(r["shot_time_s"]))[0]],
                                               "residual_mm": round(float(np.linalg.norm(puck(src_t(r["shot_time_s"]))[0] - np.array(r["world_mm_blob_centre"]))), 1),
                                               "reading_uncertainty_mm": r["reading_uncertainty_mm"]} for r in puck_obs]},
        "events": events,
        "uncertainty": {"figure_arc_mm": "per keyframe sigma_mm (iteration-21 reading, 4-55 mm)", "theta_deg": "per keyframe sigma_deg; null = not measured",
                        "puck_mm": "blob-centre reading 3-13 mm plus parallax bias (up to half the unknown puck thickness); rule-based phases have no measured uncertainty",
                        "timing_s": 0.017},
        "limitations": [
            *([("CONFLICT: with W-C's observed rotation, rigid carry and separation at peak slot speed, no run timing inside the frame-109/111/114 "
                "exposure constraints makes the puck enter on the replay's +y side clear of the goalie; the saved timing is the least violating one "
                "and the shot phase passes through the static goalie mesh. "
                + (f"The rule-based shot leaves at {dir_diag['trace_direction_deg']} deg; straight paths from the same point that clear the goalie and "
                   f"enter on +y need {dir_diag['clear_plus_y_directions_deg'][0]}-{dir_diag['clear_plus_y_directions_deg'][1]} deg. "
                   if dir_diag["clear_plus_y_directions_deg"] else "")
                + "Candidate causes: the contact rule (rigid carry, separation direction), an unobserved W-C rotation during the carry ("
                + (f"only a {rot_ok[0]['dtheta_deg']:+.0f} deg offset, which no frame shows, reproduces the replay" if rot_ok else "no tested offset fixes it")
                + "), the goalie's position, assumed rotation or AI-mold size, or a different slot layout on the recorded edition.")] if conflict else []),
            "Recorded on another STIGA edition; positions assume the canonical Play Off 21 slot layout (blade-derived pivots lie 0.4-3 mm from the slots, supporting it).",
            "Slot position readings disagree: the blade-derived pivots (inputs.json blade marks) lie 2-25 mm along the slot from the iteration-21 "
            "skate-row arcs (checks blade_pivot_checks; W-C 18-25 mm further up the slot by blade, W-RW 2-6 mm). The trace keeps the skate-row arcs; "
            "a sensitivity run with every W-C reading shifted +18 mm keeps the replay conflict (docs/shot22.md).",
            "W-C rotation between 1.78 and 2.78 s source time (the carry) is not observed; linear between the receiving pose and the rest pose.",
            "W-RW rotation during the pass is reconstructed from a contact rule (backhand normal along the pass direction), not observed.",
            "The carry is a rule (rigid push at the first-contact offset), the separation a rule (peak slot speed); both occluded in segment 1.",
            "Blade, skate and stick geometry are the AI-modelled mold at the assumed preview scale: real contact dimensions unknown; puck thickness and goal size are preview values.",
            "Fixture axis assumed on the slot centreline; rod-to-figure transfer, stops and backlash unknown."]}
    checks = {"sampling_s": DT, "max_puck_step_mm": round(max_step, 3),
              "min_clearance_by_obstacle_and_phase": [{"obstacle": k[0], "phase": k[1], **v} for k, v in sorted(rows.items())],
              "unexpected_penetrations": [{"obstacle": k[0], "phase": k[1], **v} for k, v in vint.items()],
              "goal_line": {"x_mm": gx, "crossing_y_mm": round(y_cross, 2) if y_cross is not None else None,
                            "clear_window_y_mm": [round(yc - half, 1), round(yc + half, 1)],
                            "inside_window": bool(y_cross is not None and abs(y_cross - yc) <= half)},
              "blade_pivot_checks": [{"player_id": pid, "frame": m["frame"], "heading_deg": round(m["heading_deg"], 1), "pivot_mm": [round(float(x), 1) for x in m["pivot"]],
                                      "distance_to_slot_mm": round(m["slot_dist_mm"], 1), "arc_from_blade_mm": round(m["arc_mm"], 1),
                                      "arc_in_trace_mm": round(all_figs[pid].arc(m["t"]), 1) if pid in all_figs else None}
                                     for pid, ms in (("W-C", meta["wc_meas"]), ("W-RW", meta["wr_meas"])) for m in ms],
              "expected_contacts": {"W-C": "carried_by_W-C", "W-RW": "prep / pre-release"},
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
    render(all_figs, puck, events, t_rel, t_contact, t_goal, posts, board, nodes)


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
    d.text((10, 8), "22 - PROPOSED trace 'shovel-17' (not accepted). Left: source frame with the trace projected by the segment-1 camera (red = puck disk, "
                    "cyan = W figures' low geometry, orange = E). Right: top view, 1 px = 0.5 mm.", fill=(0, 0, 0), font=FB)
    d.text((10, 44), "Release, contact and separation times are derived (see data/traces/shovel-17.trace.json events), not observed exactly. "
                     "Goal entry is hidden in segment 1. AI diagnostics, not user-reviewed.", fill=(0, 0, 0), font=FS)
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
    cols = {"prep_observed": (120, 120, 120), "pre_release_interpolated": (200, 150, 0), "pass_free": (0, 140, 0), "carried_by_W-C": (0, 90, 220),
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
    d.text((8, 4), "22 - PROPOSED puck trace (not accepted), top view, 2 px/mm. Grey = slots; circles = iteration-21", fill=(0, 0, 0), font=FS)
    d.text((8, 22), "observations (radius = 2 x reading uncertainty). Grey prep (observed), amber pre-release, green pass,", fill=(0, 0, 0), font=FS)
    d.text((8, 40), "blue carried by W-C (rule), red shot (rule" + ("; passes through the goalie: CONFLICT" if any(e.get("w_c_run_timing", {}).get("conflict_with_replay") for e in events) else "") + "), purple in the net (assumed).", fill=(0, 0, 0), font=FS)
    im.save(OUT_OVER)


if __name__ == "__main__":
    main()
