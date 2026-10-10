"""The table as the move engine sees it: slots, figure poses, contact footprints, boards and the preview goal.

Pure data and geometry, no simulation. Values and conventions are the same as scripts/spjass-trace.py (the helpers the
earlier traces import), but the figure geometry comes from data/figures/contact-footprints.json instead of Blender
meshes, so a move builds in seconds in any container with numpy, shapely and pillow.
"""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union

REPO = Path(__file__).resolve().parents[2]
G = json.loads((REPO / "data/geometry.json").read_text())
HW = json.loads((REPO / "validation/12-hardware-report.json").read_text())
ASM = {f["player_id"]: f for f in json.loads((REPO / "validation/16-assembly-poses.json").read_text())["figures"]}
FOOT = json.loads((REPO / "data/figures/contact-footprints.json").read_text())

R_PUCK = G["puck"]["diameter"]["value"] / 2
PUCK_T = HW["puck"]["thickness_mm_preview"]
DT = 0.00025          # simulation and check step (CLAUDE.md: every 0.25 ms or finer)
NODE_EVERY = 2        # saved puck nodes every 0.5 ms
EPS = 0.05            # pushed-out puck rests this far outside the contact surface
PEN_TOL = 0.1         # overlap tolerance (CLAUDE.md)
HOME = {"W": 0.0, "E": 180.0}
ALL_FIGURES = sorted(ASM)


def _check_footprints():
    stale = [p for p, h in FOOT["inputs_sha256"].items() if hashlib.sha256((REPO / p).read_bytes()).hexdigest() != h]
    for p, h in FOOT.get("meshes_sha256", {}).items():  # generated meshes: checked when present
        if (REPO / p).exists() and hashlib.sha256((REPO / p).read_bytes()).hexdigest() != h:
            stale.append(p)
    if stale or FOOT["puck_thickness_mm"] != PUCK_T:
        raise SystemExit(f"data/figures/contact-footprints.json is stale ({stale or 'puck thickness'}); re-run scripts/shotlib/export_footprints.py")


_check_footprints()


def rot(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s], [s, c]])


def _poly(js):
    ps = [Polygon(g["exterior"], g["interiors"]) for g in js]
    return ps[0] if len(ps) == 1 else MultiPolygon(ps)


def _rings(poly):
    gs = [poly] if poly.geom_type == "Polygon" else list(poly.geoms)
    return [r for g in gs for r in [g.exterior, *g.interiors]]


_LOW0 = {k: _poly(v["low"]) for k, v in FOOT["figures"].items()}
_STICK0 = {k: _poly(v["stick"]) for k, v in FOOT["figures"].items()}
LOW, STICK, LOW_OUT, RINGS_OUT = {}, {}, {}, {}


def set_footprint_transform(scale=1.0, dx=0.0, dy=0.0):
    """Robustness runs only (scripts/shotlib/robustness.py): scale the footprints about the pivot and shift them in the
    figure frame. The default is the footprint file as exported."""
    for k in _LOW0:
        tf = lambda g: affinity.translate(affinity.scale(g, scale, scale, origin=(0, 0)), dx, dy) if (scale, dx, dy) != (1.0, 0.0, 0.0) else g
        LOW[k], STICK[k] = tf(_LOW0[k]), tf(_STICK0[k])
        LOW_OUT[k] = LOW[k].buffer(R_PUCK + EPS, 64)
        RINGS_OUT[k] = _rings(LOW_OUT[k])


set_footprint_transform()


class Slot:
    def __init__(self, pid):
        p = next(x for x in G["fixture_paths"] if x["player_id"] == pid)
        self.P = np.array(p["centreline"]["points_mm"], float)
        self.s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(self.P, axis=0), axis=1))]
        self.length = float(self.s[-1])
        self.id = p["id"]
        self._tan = None

    def at(self, a):
        a = min(max(a, 0.0), self.length)
        return np.array([np.interp(a, self.s, self.P[:, 0]), np.interp(a, self.s, self.P[:, 1])])

    def arc_of_y(self, y, step=0.05):
        """Arc whose point is nearest the given y (goalie placement)."""
        return float(min(np.arange(0, self.length, step), key=lambda a: abs(self.at(a)[1] - y)))

    def tangent_deg(self, a):
        """Direction of the centreline at arc a (deg), smoothed: central differences over +-10 mm, then a Gaussian
        (sigma 8 mm) along the arc - the traced centreline wiggles at the 3 mm vertex spacing (as ikv-trace.py)."""
        if self._tan is None:
            aa = np.arange(0.0, self.length + 1e-9, 0.5)
            d = np.array([self.at(x + 10.0) - self.at(x - 10.0) for x in aa])
            ang = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
            k = np.exp(-0.5 * (np.arange(-48, 49) * 0.5 / 8.0) ** 2); k /= k.sum()
            pad = np.r_[np.full(48, ang[0]), ang, np.full(48, ang[-1])]
            self._tan = (aa, np.degrees(np.convolve(pad, k, mode="valid")))
        aa, deg = self._tan
        return float(np.interp(a, aa, deg))


def kind_of(pid):
    return "goalie" if pid.endswith("-G") else "skater"


# ---------------------------------------------------------------- interpolation (mirrored in src/model/trace.ts)
def _end_slope(h0, h1, d0, d1):
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
    m[0] = _end_slope(h[0], h[1], dl[0], dl[1])
    m[-1] = _end_slope(h[-1], h[-2], dl[-1], dl[-2])
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
    """A figure on its slot: arc (monotone cubic through arc keyframes) and rotation (linear between theta keyframes),
    exactly as src/model/trace.ts evaluates a saved trace."""

    def __init__(self, pid, arcs, thetas, status=""):
        self.pid, self.team, self.kind, self.status = pid, pid[0], kind_of(pid), status
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
    """A figure in a fixed pose (pivot mm, heading deg), e.g. the static assembly pose."""

    def __init__(self, pid, pivot, heading, status=""):
        self.pid, self.team, self.kind, self.status = pid, pid[0], kind_of(pid), status
        self.piv, self.h = np.asarray(pivot, float), float(heading)

    def pose(self, t):
        return self.piv, self.h


def assembly_figure(pid):
    f = ASM[pid]
    return Static(pid, f["pivot_mm"][:2], f["heading_deg"], "static assembly pose (validation/16-assembly-poses.json)")


def to_local(f, t, w):
    piv, h = f.pose(t)
    return rot(h).T @ (np.asarray(w) - piv)


def to_world(f, t, loc):
    piv, h = f.pose(t)
    return piv + rot(h) @ np.asarray(loc)


def clearance(f, t, w):
    """Signed distance puck edge -> the figure's footprint (negative = overlap)."""
    q = Point(*to_local(f, t, w))
    low = LOW[f.kind]
    d = low.boundary.distance(q)
    return (-d if low.contains(q) else d) - R_PUCK


def part_of(f, t, p):
    q = Point(*to_local(f, t, p))
    return "stick/blade" if STICK[f.kind].distance(q) <= LOW[f.kind].distance(q) + 0.3 else "skate/body"


def world_polygon(f, t):
    piv, h = f.pose(t)
    return affinity.translate(affinity.rotate(LOW[f.kind], h, origin=(0, 0)), piv[0], piv[1])


def local_contact(f, t, p):
    """Nearest footprint point (local mm) and the contact normal (world deg) for a puck at p."""
    q = Point(*to_local(f, t, p))
    nb = LOW[f.kind].boundary.interpolate(LOW[f.kind].boundary.project(q))
    n = rot(f.pose(t)[1]) @ (np.array(q.coords[0]) - np.array(nb.coords[0]))
    return [round(float(x), 2) for x in nb.coords[0]], round(math.degrees(math.atan2(n[1], n[0])), 2)


# ---------------------------------------------------------------- goals (preview cage) and boards
class Goal:
    def __init__(self, end):
        self.end = end
        self.sign = 1.0 if end == "E" else -1.0  # +x for the E goal
        self.x, self.y = HW["goal"]["placement_mm"][end]
        self.half = HW["goal"]["mouth_width_per_goal_mm"][end] / 2
        self.depth = HW["goal"]["depth_per_goal_mm"][end]
        self.post_r = HW["goal"]["post_radius_mm"]
        self.posts = [np.array([self.x, self.y + self.half]), np.array([self.x, self.y - self.half])]
        self.back_x = self.x + self.sign * (self.depth - R_PUCK)  # puck centre against the back of the cage
        # the cage seen from outside: two side nets and the back net (the mouth stays open; the posts are their own obstacles)
        bx = self.x + self.sign * self.depth
        self.walls = LineString([(self.x, self.y - self.half), (bx, self.y - self.half), (bx, self.y + self.half), (self.x, self.y + self.half)])
        self.cage_out = unary_union([self.walls.buffer(R_PUCK, 32)])

    def beyond_line(self, x):
        return self.sign * (x - self.x) >= 0

    def crossed(self, p_prev, q):
        return (not self.beyond_line(p_prev[0])) and self.beyond_line(q[0]) and abs(q[1] - self.y) < self.half

    def mouth_window(self):
        return [round(self.y - self.half + self.post_r + R_PUCK, 1), round(self.y + self.half - self.post_r - R_PUCK, 1)]


GOALS = {"E": Goal("E"), "W": Goal("W")}
BOARD = Polygon(G["board"]["inner_boundary"]["world"]["points_mm"])
INSET = BOARD.buffer(-R_PUCK)
