"""Flights, passes, shots and turnovers for one NM 2026 game, from the puck track.

    /root/venvs/blender/bin/python scripts/nm26-passes.py g1

Inputs: data/games/nm26-semifinal/<game>/<puck track> (scripts/nm26_tracks.py: puck-track-synth.json, or $NM26_PUCK_TRACK), config.json (which player is team W), data/geometry.json,
validation/players/figures-report.json + out/figures/skater.npz (skater reach).
Output: data/games/nm26-semifinal/<game>/passes.json.

1. FLIGHT: a run of consecutive detections (gaps of at most MAX_GAP frames) where the puck moves at MIN_SPEED or
   faster (measured over two steps against jitter; a detection implying more than MAX_SPEED into and out of it is a
   wrong candidate and dropped). Its path is cut into straight segments, each grown while all its points stay within
   SIMPLIFY_MM of one line. Runs separated by at most MERGE_ROWS slow steps are joined when the direction continues
   (within MERGE_DEG) or the break is at the boards.
   - A corner within NEAR_BOARD_MM of the boards is a board bounce and stays inside the flight.
   - A corner away from the boards that turns the path by more than MIN_TURN_DEG is a touch by a figure: the flight is
     split there, so a deflection or a one-touch
     pass becomes two flights.
2. RELEASE: the last slow detection just before the flight (the puck on the passer's blade), if within MAX_GAP frames
   and on the line behind the flight (within LINE_TOL_MM); else the flight's first point. RECEPTION: the first slow
   detection just after the flight on the line ahead, else the flight's last point.
3. WHO: the skater whose reach (slot + figure + puck) contains the point.
   - If several reach it, the one whose slot is nearest. A contested point (another skater's slot within
     CONTEST_MM of the nearest) is flagged "uncertain".
   - Goalies count here (they pass and stop shots), unlike in the possession count.
4. KIND:
   - shot: by the attacking team, at least BATTLE_MM long, with a segment moving toward the opponent's goal, ending within SHOT_REACH_MM of its goal line (or beyond), whose extension
     crosses the line between the posts (blocked or not);
   - pass: release and reception by two different skaters of the same team;
   - battle: the receiver is an opponent and the flight is shorter than BATTLE_MM (a fight for the puck at the border of
     two areas);
   - turnover: the receiver is an opponent and the flight is longer;
   - carry: same skater, or a short flight;
   - loose: no skater can reach the reception point.
"""
import os
import sys

import numpy as np
from shapely.geometry import LineString, Point, Polygon

from nm26_common import CFG, FPS, REPO, game_dir, load, save
import nm26_tracks
from nm26_tracks import puck_path

GAME = sys.argv[1] if len(sys.argv) > 1 else "g1"
# `--track <file> --out <file>` (or $NM26_PUCK_TRACK, $NM26_PASSES_OUT): another puck track in, another file out, for a
# track that is not (yet) the analysis input, e.g. `g1 --track puck-track-synth-v2.json --out passes-synth-v2.json`
# (docs/synthetic-puck.md section 8). Kept out of the docstring: it is copied into every passes.json as "definition".
_A = sys.argv[2:]
if "--track" in _A: nm26_tracks.PUCK_TRACK = _A[_A.index("--track") + 1]
PUCK_TRACK = nm26_tracks.PUCK_TRACK
PASSES_OUT = _A[_A.index("--out") + 1] if "--out" in _A else os.environ.get("NM26_PASSES_OUT", "passes.json")
MAX_GAP, MIN_SPEED, SIMPLIFY_MM, NEAR_BOARD_MM = 3, 300.0, 15.0, 40.0
LINE_TOL_MM, CONTEST_MM, MIN_FLIGHT_MM = 20.0, 15.0, 60.0
MIN_TURN_DEG, BATTLE_MM, SHOT_REACH_MM = 30.0, 150.0, 150.0
G = load(REPO / "data/geometry.json")
TR = load(puck_path(GAME))
CG = CFG["games"][GAME]
BOARD = Polygon(G["board"]["inner_boundary"]["world"]["points_mm"])
R_PUCK = G["puck"]["diameter"]["value"] / 2
HW = load(REPO / "validation/12-hardware-report.json")["goal"]


def reach_mm(kind):
    fig = load(REPO / "validation/players/figures-report.json")
    k = fig["scale_k_mm_per_mold_unit"] if kind == "skater" else fig["scales"]["goalie"]
    d = np.load(REPO / f"out/figures/{kind}.npz")
    V, T = d["verts"] * k, d["tris"]
    low = V[T[V[T][:, :, 2].min(1) < 12.0]].reshape(-1, 3)
    return float(np.linalg.norm(low[low[:, 2] < 12.0][:, :2], axis=1).max())


REACH = {"skater": reach_mm("skater") + R_PUCK, "goalie": reach_mm("goalie") + R_PUCK}
SLOTS = {f["player_id"]: LineString(f["centreline"]["points_mm"]) for f in G["fixture_paths"]}
TEAM = {"W": CG["team_W"], "E": CG["team_E"]}


def who(p):
    q = Point(*p)
    d = sorted((SLOTS[k].distance(q), k) for k in SLOTS if SLOTS[k].distance(q) <= REACH["goalie" if k.endswith("-G") else "skater"])
    if not d:
        return None, False
    return d[0][1], len(d) > 1 and d[1][0] - d[0][0] < CONTEST_MM


rows = TR["rows"]
# outliers: a detection that implies more than MAX_SPEED both into and out of it (a wrong candidate) is dropped
MAX_SPEED = 6000.0
fr0 = np.array([r[0] for r in rows])
XY0 = np.array([[r[2], r[3]] for r in rows])
v_in = np.r_[0, np.hypot(*np.diff(XY0, axis=0).T) / (np.diff(fr0) / FPS)]
v_out = np.r_[v_in[1:], 0]
rows = [r for r, a, b in zip(rows, v_in, v_out) if not (a > MAX_SPEED and b > MAX_SPEED)]
fr = np.array([r[0] for r in rows])
XY = np.array([[r[2], r[3]] for r in rows])
t = fr / FPS
# speed over a two-step baseline (less jitter): link i is "fast" if i-2 -> i (or i-1 -> i) moves at MIN_SPEED or more
spd = np.zeros(len(rows))
for i in range(1, len(rows)):
    k = i - 2 if i >= 2 and fr[i] - fr[i - 2] <= 2 * MAX_GAP else i - 1
    g = fr[i] - fr[k]
    spd[i] = np.hypot(*(XY[i] - XY[k])) / (g / FPS) if g <= 2 * MAX_GAP else 0.0
fast = spd >= MIN_SPEED


def line_fit(idx):
    """Max distance of points idx from their least-squares line."""
    P = XY[idx]
    if len(P) < 3:
        return 0.0
    c = P.mean(0)
    u = np.linalg.svd(P - c)[2][0]
    return float(np.abs((P - c) @ np.array([-u[1], u[0]])).max())


def segments(idx):
    """Greedy straight segments over detections idx: grow each segment while all its points lie within SIMPLIFY_MM of
    one line. Returns the corner indices (shared ends)."""
    corners, a = [idx[0]], 0
    while a < len(idx) - 1:
        b = a + 1
        while b + 1 < len(idx) and line_fit(idx[a:b + 2]) <= SIMPLIFY_MM:
            b += 1
        corners.append(idx[b])
        a = b
    return corners


def near_board(i):
    return BOARD.exterior.distance(Point(*XY[i])) < NEAR_BOARD_MM


def simplify(idx):
    return segments(idx)


# runs of fast links
runs, i = [], 1
while i < len(rows):
    if fast[i]:
        j = i
        while j + 1 < len(rows) and fast[j + 1]:
            j += 1
        runs.append(list(range(i - 1, j + 1)))
        i = j + 1
    else:
        i += 1
# merge runs separated by at most MERGE_ROWS slow steps when the puck keeps its direction (a jittery or wrong
# position inside one flight)
MERGE_ROWS, MERGE_DEG = 2, 35.0


def heading(a, b):
    d = XY[b] - XY[a]
    return np.degrees(np.arctan2(d[1], d[0]))


merged = []
for r in runs:
    if merged:
        p = merged[-1]
        if r[0] - p[-1] <= MERGE_ROWS and fr[r[0]] - fr[p[-1]] <= 2 * MAX_GAP and len(p) >= 2 and len(r) >= 2:
            dh = abs((heading(p[-2], p[-1]) - heading(r[0], r[1]) + 180) % 360 - 180)
            near = near_board(p[-1]) or near_board(r[0])
            if dh <= MERGE_DEG or near:
                merged[-1] = p + list(range(p[-1] + 1, r[0])) + r
                continue
    merged.append(r)
runs = merged
# split runs at corners away from the boards
flights = []
for idx in runs:
    ks = simplify(idx)
    cut = []
    for m in range(1, len(ks) - 1):
        k = ks[m]
        u1, u2 = XY[k] - XY[ks[m - 1]], XY[ks[m + 1]] - XY[k]
        ang = np.degrees(np.arccos(np.clip(u1 @ u2 / (np.hypot(*u1) * np.hypot(*u2) + 1e-9), -1, 1)))
        if not near_board(k) and ang > MIN_TURN_DEG:
            cut.append(k)
    start = idx[0]
    for c in cut + [idx[-1]]:
        seg = [k for k in idx if start <= k <= c]
        if len(seg) >= 2:
            flights.append(seg)
        start = c


def on_line(k, a, b, ahead):
    u = (XY[b] - XY[a]) / (np.hypot(*(XY[b] - XY[a])) or 1e-9)
    d = XY[k] - (XY[b] if ahead else XY[a])
    along = float(d @ u)
    perp = abs(float(d[0] * u[1] - d[1] * u[0]))
    return perp <= LINE_TOL_MM and (along >= -LINE_TOL_MM if ahead else along <= LINE_TOL_MM)


def goal_entry(a, b):
    """Goal id if the segment XY[a] -> XY[b] heads into a goal mouth: it moves toward that goal, ends within
    SHOT_REACH_MM in front of the goal line (or beyond it), and its extension crosses the line between the posts."""
    for g in ("W", "E"):
        gx, gy = HW["placement_mm"][g]
        half = HW["mouth_width_per_goal_mm"][g] / 2
        p, q = XY[a], XY[b]
        sgn = -1 if g == "W" else 1
        if (q[0] - p[0]) * sgn <= 1e-6 or (gx - q[0]) * sgn > SHOT_REACH_MM:
            continue
        y = p[1] + (q[1] - p[1]) * ((gx - p[0]) / (q[0] - p[0]))
        if abs(y - gy) <= half + R_PUCK:
            return g
    return None


events = []
for fl in flights:
    a, b = fl[0], fl[-1]
    rel = a - 1 if a > 0 and fr[a] - fr[a - 1] <= MAX_GAP and not fast[a] and on_line(a - 1, a, b, False) else a
    rec = b + 1 if b + 1 < len(rows) and fr[b + 1] - fr[b] <= MAX_GAP and not fast[b + 1] and on_line(b + 1, a, b, True) else b
    ks = simplify(fl)
    line = [rel] + [k for k in ks[1:-1]] + [rec]
    length = float(sum(np.hypot(*(XY[line[m]] - XY[line[m - 1]])) for m in range(1, len(line))))
    p_from, unc_from = who(XY[rel])
    p_to, unc_to = who(XY[rec])
    goal = None
    for m in range(1, len(line)):
        goal = goal_entry(line[m - 1], line[m]) or goal
    if goal and (length < BATTLE_MM or (p_from and p_from[0] == goal)):
        goal = None  # too short, or a team moving the puck toward its own goal
    if goal:
        kind = "shot"
    elif length < MIN_FLIGHT_MM or (p_from and p_from == p_to):
        kind = "carry"
    elif p_to is None:
        kind = "loose"
    elif p_from is None:
        kind = "loose_received"
    elif p_from[0] == p_to[0]:
        kind = "pass"
    elif length < BATTLE_MM:
        kind = "battle"
    else:
        kind = "turnover"
    v = [float(spd[k]) for k in fl[1:]]
    events.append({
        "kind": kind, "from": p_from, "to": p_to, "from_uncertain": bool(unc_from), "to_uncertain": bool(unc_to),
        "player_from": TEAM[p_from[0]] if p_from else None, "player_to": TEAM[p_to[0]] if p_to else None,
        "goal_of": goal, "t_release_s": round(float(t[rel]), 3), "t_reception_s": round(float(t[rec]), 3),
        "frame_release": int(fr[rel]), "frame_reception": int(fr[rec]),
        "line_mm": [[round(float(XY[k][0]), 1), round(float(XY[k][1]), 1)] for k in line],
        "bounces": len(line) - 2, "length_mm": round(length, 1),
        "detections": len(fl) + (rel != a) + (rec != b), "speed_mm_s": [round(min(v)), round(float(np.median(v))), round(max(v))],
        "release_at_rest": bool(rel != a), "reception_at_rest": bool(rec != b),
    })

kinds = sorted({e["kind"] for e in events})
summary = {k: sum(1 for e in events if e["kind"] == k) for k in kinds}
by_player = {pl: {"passes": sum(1 for e in events if e["kind"] == "pass" and e["player_from"] == pl),
                  "shots": sum(1 for e in events if e["kind"] == "shot" and e["player_from"] == pl),
                  "turnovers_lost": sum(1 for e in events if e["kind"] == "turnover" and e["player_from"] == pl)} for pl in TEAM.values()}
save(game_dir(GAME) / PASSES_OUT, {
    "description": "Flights of the puck classified as passes, shots, turnovers, carries and loose pucks (scripts/nm26-passes.py). Video seconds. PROPOSED: definitions assumed, to be confirmed by the user.",
    "puck_track": PUCK_TRACK,
    "definition": __doc__.split("\n\n", 1)[1].strip(),
    "parameters": {"min_turn_deg": MIN_TURN_DEG, "battle_mm": BATTLE_MM, "shot_reach_mm": SHOT_REACH_MM, "max_gap_frames": MAX_GAP, "min_speed_mm_s": MIN_SPEED, "simplify_mm": SIMPLIFY_MM, "near_board_mm": NEAR_BOARD_MM,
                   "line_tol_mm": LINE_TOL_MM, "contest_mm": CONTEST_MM, "min_flight_mm": MIN_FLIGHT_MM,
                   "reach_mm": {k: round(v, 1) for k, v in REACH.items()}},
    "teams": TEAM, "summary": summary, "by_player": by_player,
    "uncertain_ends": sum(1 for e in events if e["from_uncertain"] or e["to_uncertain"]),
    "events": events,
}, indent=1)
print(summary, by_player, "uncertain", sum(1 for e in events if e["from_uncertain"] or e["to_uncertain"]))
