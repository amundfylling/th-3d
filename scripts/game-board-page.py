"""Interactive board view of the match possession count: validation/game-possession-board.html.

    /root/venvs/blender/bin/python scripts/game-board-page.py

Inputs: data/games/fylling-vs-moe-2022/{possession.json, puck-track.json, passes.json}, data/geometry.json (inner board boundary,
board landmarks of the lines, slot centrelines), validation/12-hardware-report.json (preview goal placement and size),
out/figures/{skater,goalie}.npz + validation/players/figures-report.json (top-view figure outlines).
Template: scripts/game-board.template.html (the page; this script only injects the data as JSON).

Figure poses on the board are ILLUSTRATIVE: the figures are not tracked. Each skater stands on its slot at the point
nearest the average seen puck position while the puck was on it, turned so its blade points at that position
(the stick toe is at local +y of the mold). Goalies stand at the middle of their slots, square to play.
"""
import json
import math

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from game_common import GAME, MATCH_START_S, REPO, geometry, load, proj

G = geometry()
P = load(GAME / "possession.json")
T = load(GAME / "puck-track.json")
HW = load(REPO / "validation/12-hardware-report.json")["goal"]
FIG = load(REPO / "validation/players/figures-report.json")
M = np.array(G["image_to_world"][0]["matrix"]).reshape(3, 3)
LM = {l["id"]: proj(M, [l["px"]])[0] for l in G["landmarks"] if l["source_image_id"] == "stiga_se_fi_overhead"}
R1 = lambda v: round(float(v), 1)


def pts(geom, tol=0.6):
    return [[R1(x), R1(y)] for x, y in geom.simplify(tol).coords]


def outline(kind, k, labels=None):
    d = np.load(REPO / f"out/figures/{kind}.npz")
    V, Tr, L = d["verts"] * k, d["tris"], d["labels"]
    keys = [str(x) for x in d["keys"]]
    sel = Tr
    if labels is not None:
        ids = [keys.index(x) for x in labels if x in keys]
        sel = Tr[np.isin(L, ids)]
    poly = unary_union([p.buffer(0.05) for p in (Polygon(V[t][:, :2]) for t in sel) if p.area > 1e-4]).buffer(0)
    gs = [poly] if poly.geom_type == "Polygon" else list(poly.geoms)
    return [pts(g.exterior, 0.3) for g in gs if g.area > 0.5]


K_SK, K_GO = FIG["scale_k_mm_per_mold_unit"], FIG["scales"]["goalie"]
silhouettes = {
    "skater": {"body": outline("skater", K_SK, ["kit", "blue", "skin"]), "stick": outline("skater", K_SK, ["stick_metal", "stick_tan"])},
    "goalie": {"body": outline("goalie", K_GO, ["kit", "blue", "skin"]), "stick": outline("goalie", K_GO, ["stick_metal", "stick_tan"])},
}

board = Polygon(G["board"]["inner_boundary"]["world"]["points_mm"])
lines = []
for name, kind in [("goal_line.W", "red"), ("blue_line.W", "blue"), ("centre_line", "red"), ("blue_line.E", "blue"), ("goal_line.E", "red")]:
    a, b = LM[f"lm.board.{name}.top"], LM[f"lm.board.{name}.bottom"]
    lines.append({"id": name, "kind": kind, "a": [R1(a[0]), R1(a[1])], "b": [R1(b[0]), R1(b[1])]})

slots = {f["player_id"]: pts(LineString(f["centreline"]["points_mm"]), 0.8) for f in G["fixture_paths"]}
areas = {k: [[[R1(x), R1(y)] for x, y in q] for q in v] for k, v in P["exclusive_areas_mm"].items()}
R_AREA = P["parameters"]["skater_reach_mm"] + P["parameters"]["puck_radius_mm"]
inner = board.buffer(-P["parameters"]["puck_radius_mm"])
reach = {f["player_id"]: LineString(f["centreline"]["points_mm"]).buffer(R_AREA).intersection(inner)
         for f in G["fixture_paths"] if not f["player_id"].endswith("-G")}
union = unary_union(list(reach.values()))
excl = unary_union([Polygon(q).buffer(0) for v in areas.values() for q in v]).buffer(0.5)
contested = union.difference(excl).buffer(0)
contested_polys = [pts(g.exterior, 0.8) for g in ([contested] if contested.geom_type == "Polygon" else contested.geoms) if g.area > 20]

# puck rows in match time; owner per seen row
mf0 = int(round(MATCH_START_S * 25))
puck = [[round(r[0] / 25 - MATCH_START_S, 2), R1(r[2]), R1(r[3])] for r in T["rows"] if mf0 <= r[0] < mf0 + 7500]
eps = P["episodes"]


def owner_at(t):
    lo, hi = 0, len(eps) - 1
    while lo < hi:
        m = (lo + hi) // 2
        if eps[m][2] <= t:
            lo = m + 1
        else:
            hi = m
    return eps[lo][0]


# illustrative figure poses
poses = {}
for f in G["fixture_paths"]:
    pid = f["player_id"]
    line = LineString(f["centreline"]["points_mm"])
    home = 0.0 if pid[0] == "W" else 180.0
    if pid.endswith("-G"):
        c = line.interpolate(0.5, normalized=True)
        poses[pid] = {"x": R1(c.x), "y": R1(c.y), "heading": home, "kind": "goalie"}
        continue
    seen = [(x, y) for t, x, y in puck if owner_at(t) == pid]
    if seen:
        mx, my = np.mean(seen, axis=0)
        c = line.interpolate(line.project(Point(mx, my)))
        to = math.degrees(math.atan2(my - c.y, mx - c.x))
        heading = to - math.degrees(math.atan2(43.5, 2.9))  # turn the stick toe (local +y) toward the puck
        poses[pid] = {"x": R1(c.x), "y": R1(c.y), "heading": R1(heading), "kind": "skater", "puck_mean": [R1(mx), R1(my)]}
    else:
        c = line.interpolate(0.5, normalized=True)
        poses[pid] = {"x": R1(c.x), "y": R1(c.y), "heading": home, "kind": "skater"}

def label_point(pid):
    """A point well inside the skater's area and clear of its drawn figure (and of every other figure)."""
    area = unary_union([Polygon(q).buffer(0) for q in areas[pid]])
    core = area.buffer(-14)
    core = core if not core.is_empty else area
    figs = [Point(v["x"], v["y"]) for v in poses.values()]
    xs = np.arange(core.bounds[0], core.bounds[2], 4.0)
    ys = np.arange(core.bounds[1], core.bounds[3], 4.0)
    best, score = core.representative_point(), -1e9
    for x in xs:
        for y in ys:
            q = Point(x, y)
            if not core.contains(q):
                continue
            clear = min(f.distance(q) for f in figs)
            sc = min(clear, 55) + 0.35 * min(area.exterior.distance(q) if area.geom_type == "Polygon" else 20, 25)
            if sc > score:
                best, score = q, sc
    return [R1(best.x), R1(best.y)]


label_at = {k: label_point(k) for k in areas}
goals = {t: {"x": HW["placement_mm"][t][0], "y": HW["placement_mm"][t][1], "width": HW["mouth_width_per_goal_mm"][t],
             "depth": HW["depth_per_goal_mm"][t], "back": -1 if t == "W" else 1} for t in "WE"}

PS = load(GAME / "passes.json")
DATA_PASSES = {"events": PS["events"], "summary": PS["summary"], "pairs": PS["pairs"], "parameters": PS["parameters"], "quality": PS["quality"]}
DATA = {
    "match": {"title": "Fylling vs Moe", "event": "Trondheim Open 2022 · final", "result": "1–1 after 5:00 · Fylling won 2–1 in overtime",
              "length_s": P["match_s"], "seen_fraction": P["frames_seen_fraction"]},
    "players": {"W": {"name": "Fylling", "end": "left", "goal": "left goal"}, "E": {"name": "Moe", "end": "right", "goal": "right goal"}},
    "settings": {"min_episode_s": P["parameters"]["min_episode_s"], "max_gap_s": P["parameters"]["max_gap_s"], "reach_mm": round(R_AREA, 1)},
    "per_skater": P["per_skater"], "per_team": P["per_team"], "nobody": P["nobody_s"],
    "board": pts(board.exterior, 0.6), "lines": lines, "goals": goals, "slots": slots, "areas": areas,
    "contested": contested_polys, "labels": label_at, "poses": poses, "silhouettes": silhouettes,
    "episodes": eps, "puck": puck, "passes": DATA_PASSES,
    "areas_share": {"exclusive": round(sum(P["areas_mm2"]["exclusive"].values()) / P["areas_mm2"]["rink_puck_centre"], 3),
                    "reachable": round(P["areas_mm2"]["reachable"] / P["areas_mm2"]["rink_puck_centre"], 3)},
}
tpl = (REPO / "scripts/game-board.template.html").read_text()
out = tpl.replace("/*__DATA__*/null", json.dumps(DATA, separators=(",", ":")))
(REPO / "validation/game-possession-board.html").write_text(out)
print("bytes", len(out), "puck rows", len(puck), "episodes", len(eps))
