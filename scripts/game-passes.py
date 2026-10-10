"""Passes and turnovers of the match recording, with the puck's own path from release to reception.

    /root/venvs/blender/bin/python scripts/game-passes.py

Inputs: data/games/fylling-vs-moe-2022/{possession.json, puck-track.json}, data/geometry.json (inner boards).
Output: data/games/fylling-vs-moe-2022/passes.json.

Which hand-overs are passes (Claude's reading of the user's possession rule; ASSUMED, to be confirmed):
- A pass is the puck going from one skater to a TEAMMATE: possession episode A is followed by episode B of another
  skater of the same team, with at most MAX_TRANSIT_S of "nobody" between them.
- A turnover is the same with B on the OTHER team (an intercepted pass, a lost puck or a blocked shot; the video
  does not tell them apart).
- A puck that comes back to the same skater is no pass. Touches shorter than the minimum episode (0.5 s) are not
  possessions, so one-touch passes through a skater do not appear.
- A hand-over whose puck path is shorter than MIN_LENGTH_MM (80 mm) is a battle at the border of two skaters' areas.

Where the puck left and where it ended up (the pass line), from the detected puck positions only:
- A passed puck slides in a straight line at near-constant speed until a board turns it. Around each hand-over (from
  WINDOW_S before A's possession ends to WINDOW_S after B's starts) the detections are fitted with straight-line,
  constant-velocity segments (RANSAC over pairs of detections): a detection fits when it is within TOL_MM of the
  segment's predicted position at its time. A segment needs at least MIN_INLIERS detections, a speed of at least
  MOVING_MM_S, and must cover the hand-over.
- A board bounce: when a segment ends within NEAR_BOARD_MM of the boards, a following segment starting at that point
  is fitted to the later detections (up to MAX_BOUNCES).
- The line must START inside the passer's reach and END inside the receiver's reach (slot plus figure plus puck, with
  AREA_SLACK_MM for the position error). A segment may start at a slow detection in the passer's reach (the puck
  resting on the blade at release) and then needs only MIN_INLIERS - 1 moving detections.
- Among valid lines, the one with the most fitted detections wins (then the longest).
- RELEASE: the first point of the line. RECEPTION: its last fitted detection, moved forward to where the puck slowed at
  the receiver if a later detection lies on the line within EXTEND_S.
- A hand-over without such a fit has no measured line ("measured": false). It is still counted, but not drawn as a
  line.
- Positions are the centre of the puck's dark blob on the ice plane: about +-10 mm (calibration and the blob including
  the puck's side; the side biases the point toward the camera).
"""
import numpy as np
from shapely.geometry import LineString, Point, Polygon

from game_common import GAME, MATCH_START_S, geometry, load, save

MAX_TRANSIT_S = 2.0
MIN_LENGTH_MM = 80.0
WINDOW_S = 1.0
TOL_MM = 15.0
MIN_INLIERS = 3
MOVING_MM_S = 300.0
NEAR_BOARD_MM = 35.0
MAX_BOUNCES = 2
EXTEND_S = 0.6
AREA_SLACK_MM = 20.0
FPS = 25.0

P = load(GAME / "possession.json")
T = load(GAME / "puck-track.json")
BOARD = Polygon(geometry()["board"]["inner_boundary"]["world"]["points_mm"])
R = [(r[0] / FPS - MATCH_START_S, r[2], r[3]) for r in T["rows"]]
R = [r for r in R if 0 <= r[0] < P["match_s"]]
TS = np.array([r[0] for r in R])
XY = np.array([[r[1], r[2]] for r in R])


REACH = P["parameters"]["skater_reach_mm"] + P["parameters"]["puck_radius_mm"]
AREA = {f["player_id"]: LineString(f["centreline"]["points_mm"]).buffer(REACH + AREA_SLACK_MM)
        for f in geometry()["fixture_paths"] if not f["player_id"].endswith("-G")}


def candidates(idx, anchors):
    """Constant-velocity segments over detections idx. Free segments need MIN_INLIERS fitted detections; segments
    anchored at a slow detection (the puck on the blade) need MIN_INLIERS - 1 after the anchor.
    Yields (inliers sorted, p0, v, t0, anchor)."""
    out = []
    starts = [((TS[i], XY[i]), i, False) for i in idx] + [((TS[i], XY[i]), i, True) for i in anchors]
    for (ta, pa), ia, anchored in starts:
        for jb in idx:
            if TS[jb] <= ta + 1e-6:
                continue
            v = (XY[jb] - pa) / (TS[jb] - ta)
            if float(np.hypot(*v)) < MOVING_MM_S:
                continue
            later = [k for k in idx if TS[k] >= ta - 1e-6]
            pred = pa + np.outer(TS[later] - ta, v)
            inl = [k for k, d in zip(later, np.hypot(*(XY[later] - pred).T)) if d <= TOL_MM]
            if anchored:
                inl = [k for k in inl if k != ia]
                if len(inl) < MIN_INLIERS - 1:
                    continue
                tt = TS[inl] - ta
                v2 = np.linalg.lstsq(tt[:, None], XY[inl] - pa, rcond=None)[0][0]
                p0, inl = pa, [ia] + inl
            else:
                if len(inl) < MIN_INLIERS:
                    continue
                tt = TS[inl] - ta
                sol = np.linalg.lstsq(np.c_[np.ones(len(tt)), tt], XY[inl], rcond=None)[0]
                p0, v2 = sol[0], sol[1]
            if float(np.hypot(*v2)) < MOVING_MM_S:
                continue
            out.append((sorted(set(inl), key=lambda k: TS[k]), p0, v2, ta, anchored))
    return out


def seg_pos(sg, t):
    return sg[1] + (t - sg[3]) * sg[2]


def flight(a, b):
    t0, t1 = a[2] - WINDOW_S, b[1] + WINDOW_S
    idx = np.arange(np.searchsorted(TS, max(a[1], t0)), np.searchsorted(TS, min(b[2], t1)))
    if len(idx) < MIN_INLIERS - 1:
        return None
    A, B = AREA[a[0]], AREA[b[0]]
    # anchors: slow detections in A's last second (puck resting or carried on the passer's blade)
    anchors = [k for k in idx if TS[k] <= a[2] + 0.1 and (k == 0 or TS[k] - TS[k - 1] > 0.2 or
               np.hypot(*(XY[k] - XY[k - 1])) / (TS[k] - TS[k - 1]) < MOVING_MM_S) and A.contains(Point(*XY[k]))]
    best = None
    for sg in candidates(idx, anchors):
        inl = sg[0]
        if not (TS[inl[0]] <= b[1] + 0.3 and TS[inl[-1]] >= a[2] - 0.3):
            continue
        if not A.contains(Point(*XY[inl[0]])):
            continue
        segs = [sg]
        while len(segs) <= MAX_BOUNCES and not B.contains(Point(*XY[segs[-1][0][-1]])):
            last = segs[-1][0][-1]
            if BOARD.exterior.distance(Point(*XY[last])) > NEAR_BOARD_MM:
                break
            rest = np.array([k for k in idx if TS[k] > TS[last] + 1e-6])
            # a bounce segment starts at the last point
            cs = []
            for jb in rest:
                v = (XY[jb] - XY[last]) / (TS[jb] - TS[last])
                pred = XY[last] + np.outer(TS[rest] - TS[last], v)
                inl2 = [k for k, d in zip(rest, np.hypot(*(XY[rest] - pred).T)) if d <= TOL_MM]
                if len(inl2) >= MIN_INLIERS - 1 and float(np.hypot(*v)) >= MOVING_MM_S:
                    cs.append((len(inl2), -abs(TS[inl2[-1]] - TS[last]), ([last] + sorted(inl2, key=lambda k: TS[k]), XY[last], v, TS[last], True)))
            if not cs:
                break
            segs.append(max(cs, key=lambda c: (c[0], c[1]))[2])
        end = segs[-1][0][-1]
        if not B.contains(Point(*XY[end])):
            continue
        pts = sorted(set(k for sg2 in segs for k in sg2[0]), key=lambda k: TS[k])
        span = float(sum(np.hypot(*(XY[sg2[0][-1]] - XY[sg2[0][0]])) for sg2 in segs))
        score = (len(pts), span)
        if best is None or score > best[0]:
            best = (score, segs, pts)
    if best is None:
        return None
    _, segs, pts = best
    first, lastk = pts[0], pts[-1]
    # reception: extend forward to where the puck slowed at the receiver, on the line
    v1 = segs[-1][2]
    u = v1 / np.hypot(*v1)
    post = [k for k in idx if TS[lastk] < TS[k] <= TS[lastk] + EXTEND_S and
            abs(float((XY[k] - XY[lastk])[0] * u[1] - (XY[k] - XY[lastk])[1] * u[0])) <= TOL_MM and float((XY[k] - XY[lastk]) @ u) > 0]
    rec = post[-1] if post else lastk
    res = float(np.mean([min(np.hypot(*(XY[k] - seg_pos(sg2, TS[k]))) for sg2 in segs) for k in pts]))
    return {"fitted": pts, "release": first, "reception": rec, "release_extended": bool(segs[0][4]),
            "reception_extended": bool(rec != lastk), "corners": [sg2[0][-1] for sg2 in segs[:-1]],
            "speeds": [round(float(np.hypot(*sg2[2])), 0) for sg2 in segs], "residual_mm": round(res, 1)}


sk = [e for e in P["episodes"] if e[0] != "nobody"]
events = []
for a, b in zip(sk, sk[1:]):
    transit = b[1] - a[2]
    if a[0] == b[0] or transit > MAX_TRANSIT_S:
        continue
    kind = "pass" if a[0][0] == b[0][0] else "turnover"
    f = flight(a, b)
    ev = {"kind": kind, "team": a[0][0], "from": a[0], "to": b[0], "t_poss_end": round(a[2], 2), "t_poss_start": round(b[1], 2),
          "transit_s": round(transit, 2), "measured": f is not None}
    if f:
        r, c = f["release"], f["reception"]
        line = [r] + f["corners"] + [c]
        pt = lambda k: [round(float(XY[k][0]), 1), round(float(XY[k][1]), 1)]
        length = float(sum(np.hypot(*(XY[line[i]] - XY[line[i - 1]])) for i in range(1, len(line))))
        ev.update({
            "t_release": round(float(TS[r]), 2), "t_reception": round(float(TS[c]), 2),
            "start_mm": pt(r), "end_mm": pt(c), "line_mm": [pt(k) for k in line],
            "bounces": len(f["corners"]), "length_mm": round(length, 1), "speed_mm_s": f["speeds"],
            "detections_on_line": len(f["fitted"]), "fit_residual_mm": f["residual_mm"],
            "release_at_rest": bool(f["release_extended"]), "reception_at_rest": bool(f["reception_extended"]),
            "fitted_detections": [[round(float(TS[k]), 2)] + pt(k) for k in f["fitted"]],
        })
        if float(np.hypot(*(XY[c] - XY[r]))) < MIN_LENGTH_MM and not f["corners"]:
            ev["kind"] = "battle"
    else:
        ev.update({"t_release": round(a[2], 2), "t_reception": round(b[1], 2)})
    events.append(ev)

pairs = {}
for ev in events:
    if ev["kind"] != "battle":
        k = f"{ev['from']}>{ev['to']}"
        pairs[k] = pairs.get(k, 0) + 1
summary = {t: {"passes": sum(1 for e in events if e["kind"] == "pass" and e["team"] == t),
               "turnovers_lost": sum(1 for e in events if e["kind"] == "turnover" and e["team"] == t),
               "battles_lost": sum(1 for e in events if e["kind"] == "battle" and e["team"] == t)} for t in "WE"}
ms = [e for e in events if e["kind"] != "battle"]
quality = {"hand_overs": len(events), "measured_lines": sum(1 for e in ms if e["measured"]), "not_measured": sum(1 for e in ms if not e["measured"]),
           "release_at_rest": sum(1 for e in ms if e.get("release_at_rest")), "reception_at_rest": sum(1 for e in ms if e.get("reception_at_rest")),
           "with_bounces": sum(1 for e in ms if e.get("bounces"))}
save(GAME / "passes.json", {
    "description": "Passes and turnovers with the puck's path from release to reception (scripts/game-passes.py). Match seconds. PROPOSED; definitions assumed (see the script).",
    "definition": __doc__.split("Which hand-overs")[1].split("\n\"\"\"")[0].strip(),
    "parameters": {"max_transit_s": MAX_TRANSIT_S, "min_length_mm": MIN_LENGTH_MM, "window_s": WINDOW_S, "tol_mm": TOL_MM,
                   "min_inliers": MIN_INLIERS, "moving_mm_s": MOVING_MM_S, "near_board_mm": NEAR_BOARD_MM,
                   "max_bounces": MAX_BOUNCES, "extend_s": EXTEND_S, "min_episode_s": P["parameters"]["min_episode_s"]},
    "summary": summary, "quality": quality, "pairs": pairs, "events": events,
}, indent=1)
print(summary, quality)
