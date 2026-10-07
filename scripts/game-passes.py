"""Passes and turnovers of the match recording, from the possession episodes and the puck track.

    /root/venvs/blender/bin/python scripts/game-passes.py

Inputs: data/games/fylling-vs-moe-2022/{possession.json, puck-track.json}.
Output: data/games/fylling-vs-moe-2022/passes.json.

Definition (Claude's reading of the user's possession rule; ASSUMED, to be confirmed):
- A pass is the puck going from one skater to a TEAMMATE: possession episode A is followed by episode B of another
  skater of the same team, with at most MAX_TRANSIT_S of "nobody" between them (the puck travelling through
  contested ice or hidden).
- A turnover is the same with B on the OTHER team. It may be an intercepted pass, a lost puck or a blocked shot; the
  video does not tell them apart.
- A puck that comes back to the same skater after a nobody stretch is no pass. Touches shorter than the minimum episode
  (0.5 s) are not possessions, so one-touch passes through a skater do not appear.
- A hand-over shorter than MIN_LENGTH_MM (80 mm) is a battle at the border of two skaters' areas, not a pass or a
  turnover; it is listed as kind "battle".
- Start point: the last seen puck position in A's episode (or, if none, the first seen in the transit); end point: the
  first seen position in B's episode. "seen" flags record whether each end was actually detected near the hand-over;
  a missing end falls back to the middle of the skater's exclusive area (drawn dashed).
"""
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from game_common import GAME, MATCH_START_S, load, save

MAX_TRANSIT_S = 2.0
MIN_LENGTH_MM = 80.0  # shorter hand-overs happen at the border of two areas: a battle for the puck, not a pass
NEAR_S = 1.0  # a seen position counts as the hand-over point when it is this close in time to the hand-over
P = load(GAME / "possession.json")
T = load(GAME / "puck-track.json")
rows = [(r[0] / 25 - MATCH_START_S, r[2], r[3]) for r in T["rows"]]
rows = [r for r in rows if 0 <= r[0] < P["match_s"]]
ts = np.array([r[0] for r in rows])
centre = {k: unary_union([Polygon(q).buffer(0) for q in v]).representative_point() for k, v in P["exclusive_areas_mm"].items()}


def seen_in(t0, t1):
    i, j = np.searchsorted(ts, t0), np.searchsorted(ts, t1)
    return rows[i:j]


sk = [e for e in P["episodes"] if e[0] != "nobody"]
events = []
for a, b in zip(sk, sk[1:]):
    transit = b[1] - a[2]
    if a[0] == b[0] or transit > MAX_TRANSIT_S:
        continue
    kind = "pass" if a[0][0] == b[0][0] else "turnover"
    before = seen_in(max(a[1], a[2] - NEAR_S), a[2])
    during = seen_in(a[2], b[1])
    after = seen_in(b[1], min(b[2], b[1] + NEAR_S))
    if before:
        s, s_seen = before[-1], True
    elif during:
        s, s_seen = during[0], True
    else:
        c = centre[a[0]]
        s, s_seen = (a[2], c.x, c.y), False
    if after:
        e, e_seen = after[0], True
    elif during:
        e, e_seen = during[-1], True
    else:
        c = centre[b[0]]
        e, e_seen = (b[1], c.x, c.y), False
    length = float(np.hypot(e[1] - s[1], e[2] - s[2]))
    if length < MIN_LENGTH_MM:
        kind = "battle"
    events.append({
        "kind": kind, "team": a[0][0], "from": a[0], "to": b[0],
        "t_release": round(a[2], 2), "t_receive": round(b[1], 2), "transit_s": round(transit, 2),
        "start_mm": [round(s[1], 1), round(s[2], 1)], "end_mm": [round(e[1], 1), round(e[2], 1)],
        "start_seen": s_seen, "end_seen": e_seen,
        "length_mm": round(length, 1),
    })

pairs = {}
for ev in events:
    if ev["kind"] == "battle":
        continue
    k = f"{ev['from']}>{ev['to']}"
    pairs[k] = pairs.get(k, 0) + 1
summary = {t: {"passes": sum(1 for e in events if e["kind"] == "pass" and e["team"] == t),
               "turnovers_lost": sum(1 for e in events if e["kind"] == "turnover" and e["team"] == t),
               "battles_lost": sum(1 for e in events if e["kind"] == "battle" and e["team"] == t)} for t in "WE"}
save(GAME / "passes.json", {
    "description": "Passes and turnovers (scripts/game-passes.py). Match seconds. PROPOSED; the definition is assumed (see the script).",
    "definition": __doc__.split("Definition")[1].split("\n\"\"\"")[0].strip(),
    "parameters": {"max_transit_s": MAX_TRANSIT_S, "min_length_mm": MIN_LENGTH_MM, "near_s": NEAR_S, "min_episode_s": P["parameters"]["min_episode_s"]},
    "summary": summary, "pairs": pairs, "events": events,
}, indent=1)
print(summary, len(events), "both ends seen:", sum(e["start_seen"] and e["end_seen"] for e in events))
