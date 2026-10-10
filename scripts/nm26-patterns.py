"""Cross-game patterns for the NM 2026 semi-final: data/games/nm26-semifinal/patterns.json and two control maps.

    /root/venvs/blender/bin/python scripts/nm26-patterns.py

Inputs: data/games/nm26-semifinal/{config.json, timeline.json, g*/<puck track>, g*/passes.json} (puck track: scripts/nm26_tracks.py), data/geometry.json,
validation/12-hardware-report.json (goal cages, for the maps).
Outputs: data/games/nm26-semifinal/patterns.json, validation/nm26-control-nygard.png, validation/nm26-control-fjermestad.png.

Method (docs/nm26-game-patterns.md):
- Live play per game: LIVE windows below (start signal to the end of play), minus the 10 s before every score-overlay
  change (the overlay changes at the restart drop, so this removes the goal, the retrieval and the drop).
- A puck position is ON a figure when it lies in that figure's reach area and in no other (docs/game-mechanics.md, A10);
  otherwise contested (two or more) or free (none). Reach: passes.json parameters (skater 56.3 mm, goalie 48.7 mm).
- Player view: positions are point-reflected (x, y) -> (-x, -y) when the player is at the right end, so every player
  attacks to the right and his left side is +y. Roles: own/opp + LD, RD, C, LW, RW, G.
- Holds: runs of the puck on one figure of at least 0.3 s (gaps under 1 s joined; repeated runs within 3 s merged).
- All values are PROPOSED: from automatic tracks that are not user-confirmed (error sources: docs/nm26-passes.md).
"""
import collections
import json

import cv2
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

from nm26_common import CFG, DATA, REPO, load, proj, save
from nm26_tracks import PUCK_TRACK, load_puck

GAMES = [g for g in CFG["games"]]
TL = load(DATA / "timeline.json")["games"]
LIVE = {g: TL[g]["live_play_s"] for g in GAMES}
G = load(REPO / "data/geometry.json")
P0 = load(DATA / "g1/passes.json")["parameters"]
REACH, RG = P0["reach_mm"]["skater"], P0["reach_mm"]["goalie"]
BOARD = Polygon(G["board"]["inner_boundary"]["world"]["points_mm"])
AREA = {f["player_id"]: LineString(f["centreline"]["points_mm"]).buffer(RG if f["player_id"].endswith("-G") else REACH).intersection(BOARD)
        for f in G["fixture_paths"]}
EXCL = {k: prep(a.difference(unary_union([b for j, b in AREA.items() if j != k]))) for k, a in AREA.items()}
UNION = prep(unary_union(list(AREA.values())))
BLUE_W, BLUE_E = -100.0, 93.5  # blue lines, world x (geometry landmarks)
PLAYERS = ("nygard", "fjermestad")


def live(g, t):
    if not any(a <= t < b for a, b in LIVE[g]):
        return False
    return not any(x["overlay_change_s"] and x["overlay_change_s"] - 10 <= t < x["overlay_change_s"] for x in TL[g]["goals"])


def owner(x, y):
    p = Point(x, y)
    k = next((k for k, v in EXCL.items() if v.contains(p)), None)
    return k or ("contested" if UNION.contains(p) else "free")


def share(c, n):
    return {k: round(v / n, 3) for k, v in c.most_common()}


rows, events, team = {}, {}, {}
PUCK = {g: load_puck(g) for g in GAMES}
for g in GAMES:
    team[g] = {"W": CFG["games"][g]["team_W"], "E": CFG["games"][g]["team_E"]}
    rows[g] = [r + [owner(r[2], r[3])] for r in PUCK[g]["rows"] if live(g, r[1])]
    events[g] = [e for e in load(DATA / g / "passes.json")["events"] if live(g, e["t_release_s"])]

per_game = {}
for g in GAMES:
    R, E = rows[g], events[g]
    n = len(R)
    nyg = "W" if team[g]["W"] == "nygard" else "E"
    flights = [e for e in E if e["kind"] != "carry" and e["length_mm"] >= 100]
    mins = sum(b - a for a, b in LIVE[g]) / 60
    on = collections.Counter(r[8][0] if r[8] not in ("contested", "free") else r[8] for r in R)
    per_game[g] = {
        "left_end_player": team[g]["W"],
        "live_min": round(mins, 2),
        "seen_fraction": round(n / (mins * 60 * 30), 3),
        "puck_in_attacking_end": {"nygard": round(sum(1 for r in R if (r[2] > BLUE_E if nyg == "W" else r[2] < BLUE_W)) / n, 3),
                                  "fjermestad": round(sum(1 for r in R if (r[2] < BLUE_W if nyg == "W" else r[2] > BLUE_E)) / n, 3)},
        "puck_on_own_figures": {"nygard": round(on[nyg] / n, 3), "fjermestad": round(on["E" if nyg == "W" else "W"] / n, 3),
                                "contested": round(on["contested"] / n, 3), "free": round(on["free"] / n, 3)},
        "flights_ge_100mm_per_min": round(len(flights) / mins, 1),
        "possession_changes_per_min": round(sum(1 for e in E if e["kind"] in ("turnover", "battle")) / mins, 1),
        "flight_median_speed_mm_s": int(np.median([e["speed_mm_s"][1] for e in flights])),
        "flight_board_bounce_share": round(float(np.mean([e["bounces"] > 0 for e in flights])), 3),
    }

per_player, maps = {}, {}
for p in PLAYERS:
    zone, side, area, n = collections.Counter(), collections.Counter(), collections.Counter(), 0
    holds, nxt, seq, passes = collections.defaultdict(list), collections.Counter(), collections.Counter(), collections.defaultdict(list)
    kinds, pts = collections.Counter(), []
    for g in GAMES:
        me = "W" if team[g]["W"] == p else "E"
        m = 1 if me == "W" else -1
        ep = []
        for r in rows[g]:
            x, y, o = m * r[2], m * r[3], r[8]
            n += 1
            zone["own end" if x < BLUE_W else "attacking end" if x > BLUE_E else "neutral"] += 1
            side["left" if y > 60 else "right" if y < -60 else "middle"] += 1
            if o in ("contested", "free"):
                area[o] += 1
                continue
            role = ("own " if o[0] == me else "opp ") + o[2:]
            area[role] += 1
            if o[0] == me:
                pts.append((x, y))
            if ep and ep[-1][0] == role and r[1] - ep[-1][2] < 1.0:
                ep[-1][2] = r[1]
            else:
                ep.append([role, r[1], r[1]])
        merged = []
        for e in (e for e in ep if e[2] - e[1] >= 0.3):
            if merged and merged[-1][0] == e[0] and e[1] - merged[-1][2] < 3:
                merged[-1][2] = e[2]
            else:
                merged.append(e)
        for e in merged:
            if e[0].startswith("own"):
                holds[e[0]].append(e[2] - e[1])
        for a, b in zip(merged, merged[1:]):
            if b[1] - a[2] < 3 and a[0].startswith("own"):
                nxt[(a[0], b[0])] += 1
        for a, b, c in zip(merged, merged[1:], merged[2:]):
            if a[0].startswith("own") and b[0].startswith("own") and b[1] - a[2] < 3 and c[1] - b[2] < 3:
                seq[(a[0], b[0], c[0])] += 1
        for e in events[g]:
            if e["from"] and e["from"][0] == me and e["length_mm"] >= 100 and e["kind"] in ("pass", "turnover", "shot"):
                kinds[e["kind"]] += 1
                if e["kind"] == "pass":
                    passes[(e["from"][2:], e["to"][2:])].append(e)
    per_player[p] = {
        "seen_frames": n,
        "puck_zone": share(zone, n),
        "puck_side_of_player": share(side, n),
        "puck_on": share(area, n),
        "holds_by_own_role": {k: {"n": len(v), "total_s": round(sum(v)), "median_s": round(float(np.median(v)), 1), "p90_s": round(float(np.percentile(v, 90)), 1)}
                              for k, v in sorted(holds.items(), key=lambda x: -sum(x[1]))},
        "next_after_own_hold": [[a, b, k] for (a, b), k in nxt.most_common(15)],
        "three_step_chains": [[a, b, c, k] for (a, b, c), k in seq.most_common(8)],
        "flights_from_own_figures": dict(kinds),
        "passes_by_roles": [{"from": a, "to": b, "n": len(v), "median_len_mm": int(np.median([e["length_mm"] for e in v])),
                             "board_bounce_share": round(float(np.mean([e["bounces"] > 0 for e in v])), 2),
                             "median_speed_mm_s": int(np.median([e["speed_mm_s"][1] for e in v]))}
                            for (a, b), v in sorted(passes.items(), key=lambda x: -len(x[1]))[:10]],
    }
    pts = np.array(pts)
    H, _, _ = np.histogram2d(pts[:, 0], pts[:, 1], bins=[43, 24], range=[[-430, 430], [-240, 240]])
    maps[p] = cv2.resize(cv2.GaussianBlur(H.astype(np.float32), (3, 3), 0.8), (47, 85), interpolation=cv2.INTER_LINEAR)

restarts = {}
for g in GAMES:
    runs, cur = [], None
    for r, slow in zip(PUCK[g]["rows"], PUCK[g]["slow"]):
        if abs(r[2]) < 30 and abs(r[3]) < 30 and slow:
            if cur and r[1] - cur[1] < 0.4:
                cur[1] = r[1]
            else:
                if cur:
                    runs.append(cur)
                cur = [r[1], r[1]]
    if cur:
        runs.append(cur)
    restarts[g] = [[round(a, 1), round(b - a, 1)] for a, b in runs if b - a >= 0.3]

save(DATA / "patterns.json", {
    "description": "Cross-game patterns from the automatic puck tracks of all seven games (scripts/nm26-patterns.py; docs/nm26-game-patterns.md).",
    "status": "proposed",
    "puck_track": PUCK_TRACK,
    "method": __doc__.split("Method (docs/nm26-game-patterns.md):")[1].strip(),
    "per_game": per_game, "per_player": per_player,
    "puck_resting_on_centre_spot_s": restarts,
}, indent=1)

# control maps: where each player's own figures have the puck alone (player view)
HW = load(REPO / "validation/12-hardware-report.json")["goal"]
M = np.array(G["image_to_world"][0]["matrix"]).reshape(3, 3)
LM = {l["id"]: proj(M, [l["px"]])[0] for l in G["landmarks"] if l["source_image_id"] == "stiga_se_fi_overhead"}
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]  # sequential blue (dataviz default)
RGB = [tuple(int(h[i:i + 2], 16) for i in (5, 3, 1)) for h in RAMP]
S = 1.4
W, HH = int(850 * S) + 40, int(470 * S) + 70


def P(x, y):
    return int(20 + (x + 425) * S), int(50 + (235 - y) * S)


for p, Hm in maps.items():
    img = np.full((HH, W, 3), 255, np.uint8)
    v = Hm / Hm.sum()
    q = np.quantile(v[v > 0], [.3, .5, .65, .78, .88, .95])
    nx, ny = v.shape
    for i in range(nx):
        for j in range(ny):
            if v[i, j] > q[0]:
                x0, y0 = -425 + i * 850 / nx, -235 + j * 470 / ny
                cv2.rectangle(img, P(x0, y0 + 470 / ny), P(x0 + 850 / nx, y0), RGB[min(int(np.searchsorted(q, v[i, j])), 6)], -1)
    board = np.array([P(x, y) for x, y in G["board"]["inner_boundary"]["world"]["points_mm"]], np.int32)
    mask = np.zeros(img.shape[:2], np.uint8)
    cv2.fillPoly(mask, [board], 1)
    img[mask == 0] = 255
    for nme, c in [("goal_line.W", (60, 60, 200)), ("blue_line.W", (180, 90, 40)), ("centre_line", (60, 60, 200)), ("blue_line.E", (180, 90, 40)), ("goal_line.E", (60, 60, 200))]:
        cv2.line(img, P(*LM[f"lm.board.{nme}.top"]), P(*LM[f"lm.board.{nme}.bottom"]), c, 1, cv2.LINE_AA)
    for f in G["fixture_paths"]:
        cv2.polylines(img, [np.array([P(x, y) for x, y in f["centreline"]["points_mm"]], np.int32)], False, (150, 150, 150), 1, cv2.LINE_AA)
    cv2.polylines(img, [board], True, (40, 40, 40), 2, cv2.LINE_AA)
    for gg, sg in (("W", -1), ("E", 1)):
        gx, gy = HW["placement_mm"][gg]
        w, d = HW["mouth_width_per_goal_mm"][gg], HW["depth_per_goal_mm"][gg]
        cv2.rectangle(img, P(gx, gy + w / 2), P(gx + sg * d, gy - w / 2), (40, 40, 200), 2)
    name = {"nygard": "Nygard", "fjermestad": "Fjermestad"}[p]
    cv2.putText(img, f"Where {name}'s figures have the puck alone, 7 games (his end on the left; his left side at the top)", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 1, cv2.LINE_AA)
    cv2.arrowedLine(img, (160, HH - 9), (260, HH - 9), (60, 60, 60), 2, tipLength=0.2)
    cv2.putText(img, "attacking direction", (20, HH - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60, 60, 60), 1, cv2.LINE_AA)
    for k, c in enumerate(RGB):
        cv2.rectangle(img, (W - 300 + k * 30, HH - 14), (W - 272 + k * 30, HH - 4), c, -1)
    cv2.putText(img, "less", (W - 345, HH - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60, 60, 60), 1, cv2.LINE_AA)
    cv2.putText(img, "more time", (W - 85, HH - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60, 60, 60), 1, cv2.LINE_AA)
    cv2.imwrite(str(REPO / f"validation/nm26-control-{p}.png"), img)
for p, v in per_player.items():
    print(p, v["puck_zone"], v["puck_on"].get("own LW"), v["flights_from_own_figures"])
