"""Possession count per skater for the match recording, from the puck track and the skaters' reach areas.

    /root/venvs/blender/bin/python scripts/game-possession.py

Inputs: data/games/fylling-vs-moe-2022/{puck-track.json, calibration.json, background.png}, data/geometry.json (slot
centrelines, inner board boundary, puck), out/figures/skater.npz and validation/players/figures-report.json (skater
mesh, for its reach), validation/12-hardware-report.json (preview puck thickness).
Outputs: data/games/fylling-vs-moe-2022/possession.json, validation/game-figure-areas.png,
validation/game-possession.png.

Definition (user answers A10-A15, docs/game-mechanics.md section 6):
- A skater's reach area: every puck-centre position its stick or body can touch, over its whole slot and every
  rotation. The puck is ON a skater while it lies in that skater's area and in no other skater's area. Goalies are
  not counted (A14) and do not block (simplest reading of "don't count the goalie").
- Per skater: the time the puck is on it, and the number of times it gets the puck (entries into its exclusive
  area).
- Frames where the puck is not seen: a gap of up to MAX_GAP_S keeps the owner when the puck is on the same skater
  before and after; otherwise the first half goes to the owner before and the second half to the owner after. A gap
  longer than MAX_GAP_S is on nobody (A15; whether the whole gap or only the part after 10 s is open, Q16).
- An episode shorter than MIN_EPISODE_S on a skater is counted as nobody (detection jitter at area edges).
"""
import json

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

from game_common import FPS, GAME, MATCH_START_S, REPO, geometry, load, match_frames, proj, save, world_to_crop

MAX_GAP_S, MIN_EPISODE_S = 10.0, 0.2
G = geometry()
R_PUCK = G["puck"]["diameter"]["value"] / 2
TEAM = {"W": "Fylling (left)", "E": "Moe (right)"}


def skater_reach_mm():
    """Largest distance from the fixture axis of the skater's geometry at puck height (stick blade toe)."""
    fig = load(REPO / "validation/players/figures-report.json")
    pt = load(REPO / "validation/12-hardware-report.json")["puck"]["thickness_mm_preview"]
    d = np.load(REPO / "out/figures/skater.npz")
    V, T = d["verts"] * fig["scale_k_mm_per_mold_unit"], d["tris"]
    low = V[T[V[T][:, :, 2].min(1) < pt]].reshape(-1, 3)
    low = low[low[:, 2] < pt]
    return float(np.linalg.norm(low[:, :2], axis=1).max())


REACH = skater_reach_mm()
BOARD = Polygon(G["board"]["inner_boundary"]["world"]["points_mm"]).buffer(-R_PUCK)
SKATERS = [f["player_id"] for f in G["fixture_paths"] if not f["player_id"].endswith("-G")]
AREA = {f["player_id"]: LineString(f["centreline"]["points_mm"]).buffer(REACH + R_PUCK).intersection(BOARD)
        for f in G["fixture_paths"] if f["player_id"] in SKATERS}
EXCL = {k: a.difference(unary_union([b for j, b in AREA.items() if j != k])) for k, a in AREA.items()}
UNION = unary_union(list(AREA.values()))
PE = {k: prep(v) for k, v in EXCL.items()}
PU = prep(UNION)


def classify(x, y):
    p = Point(x, y)
    for k, v in PE.items():
        if v.contains(p):
            return k, "exclusive"
    return "nobody", ("contested" if PU.contains(p) else "unreachable")


def episodes(seq):
    out, s = [], 0
    for k in range(1, len(seq) + 1):
        if k == len(seq) or seq[k] != seq[s]:
            out.append([seq[s], s, k])
            s = k
    return out


tr = load(GAME / "puck-track.json")
POS = {r[0]: (r[2], r[3]) for r in tr["rows"]}
MF = list(match_frames())
n = len(MF)


def assign(pos, max_gap_s=MAX_GAP_S, min_episode_s=MIN_EPISODE_S, gap_rule="whole", classify=classify):
    """Owner and reason per match frame. gap_rule 'whole': a long gap is nobody throughout; 'after': the owner is held
    for the first max_gap_s, nobody after that."""
    own, why = [None] * n, [None] * n
    for k, i in enumerate(MF):
        if i in pos:
            own[k], why[k] = classify(*pos[i])
    k = 0
    while k < n:
        if own[k] is not None:
            k += 1
            continue
        j = k
        while j < n and own[j] is None:
            j += 1
        a = own[k - 1] if k > 0 else "nobody"
        b = own[j] if j < n else "nobody"
        if (j - k) / FPS > max_gap_s:
            m = k + int(max_gap_s * FPS) if gap_rule == "after" else k
            own[k:m], why[k:m] = [a] * (m - k), ["gap_held" if a != "nobody" else "gap_nobody"] * (m - k)
            own[m:j], why[m:j] = ["nobody"] * (j - m), ["long_gap"] * (j - m)
        elif a == b:
            own[k:j], why[k:j] = [a] * (j - k), ["gap_held" if a != "nobody" else "gap_nobody"] * (j - k)
        else:
            m = (k + j) // 2
            own[k:m], why[k:m] = [a] * (m - k), ["gap_split" if a != "nobody" else "gap_nobody"] * (m - k)
            own[m:j], why[m:j] = [b] * (j - m), ["gap_split" if b != "nobody" else "gap_nobody"] * (j - m)
        k = j
    for o, a, b in episodes(own):
        if o != "nobody" and (b - a) / FPS < min_episode_s:
            own[a:b], why[a:b] = ["nobody"] * (b - a), ["short_episode"] * (b - a)
    return own, why


def summary(own):
    per = {s: [0.0, 0] for s in SKATERS}
    for o, a, b in episodes(own):
        if o != "nobody":
            per[o][0] += (b - a) / FPS
            per[o][1] += 1
    return {s: [round(v[0], 1), v[1]] for s, v in per.items()}


own, why = assign(POS)
EP = episodes(own)
pos = POS

per = {s: {"team": s[0], "time_s": 0.0, "times": 0, "time_seen_s": 0.0} for s in SKATERS}
for o, a, b in EP:
    if o != "nobody":
        per[o]["time_s"] += (b - a) / FPS
        per[o]["times"] += 1
for k2, i in enumerate(MF):
    if own[k2] != "nobody" and i in pos:
        per[own[k2]]["time_seen_s"] += 1 / FPS
for s in per.values():
    s["time_s"], s["time_seen_s"] = round(s["time_s"], 2), round(s["time_seen_s"], 2)
nobody = {r: round(sum(1 for w, o in zip(why, own) if o == "nobody" and w == r) / FPS, 2)
          for r in ("contested", "unreachable", "long_gap", "gap_nobody", "short_episode")}
teams = {t: {"player": TEAM[t], "time_s": round(sum(v["time_s"] for v in per.values() if v["team"] == t), 2),
             "times": sum(v["times"] for v in per.values() if v["team"] == t)} for t in "WE"}


# sensitivity of the counts to the open choices (each varied alone)
GOALIE_AREA = {f["player_id"]: LineString(f["centreline"]["points_mm"]).buffer(36.0 + R_PUCK) for f in G["fixture_paths"] if f["player_id"].endswith("-G")}
PG = prep(unary_union(list(GOALIE_AREA.values())))


def classify_goalie_blocks(x, y):
    o, r = classify(x, y)
    return ("nobody", "goalie") if o != "nobody" and PG.contains(Point(x, y)) else (o, r)


SENS = {
    "baseline": summary(own),
    "long gap: nobody only after 10 s (Q16)": summary(assign(POS, gap_rule="after")[0]),
    "goalies block (puck in a goalie's reach is on nobody)": summary(assign(POS, classify=classify_goalie_blocks)[0]),
    "minimum episode 0.4 s": summary(assign(POS, min_episode_s=0.4)[0]),
    "no minimum episode": summary(assign(POS, min_episode_s=0.0)[0]),
    "max gap 3 s": summary(assign(POS, max_gap_s=3.0)[0]),
}


def poly_list(g):
    gs = [g] if g.geom_type == "Polygon" else list(getattr(g, "geoms", []))
    return [[[round(x, 1), round(y, 1)] for x, y in q.simplify(0.5).exterior.coords] for q in gs if q.area > 1]


save(GAME / "possession.json", {
    "description": "Possession count per skater (scripts/game-possession.py). Match clock = video time - %.1f s." % MATCH_START_S,
    "definition": __doc__.split("Definition")[1].strip(),
    "parameters": {"max_gap_s": MAX_GAP_S, "min_episode_s": MIN_EPISODE_S, "skater_reach_mm": round(REACH, 2),
                   "puck_radius_mm": R_PUCK, "rotation": "full 360 deg (assumed)", "goalies": "not counted, do not block"},
    "status": "proposed",
    "teams": {"W": "left player, Fylling (A1); defends goal.W", "E": "right player, Moe; defends goal.E"},
    "per_skater": per,
    "per_team": teams,
    "nobody_s": nobody,
    "match_s": round(n / FPS, 2),
    "frames_seen_fraction": tr["match_frames_seen_fraction"],
    "areas_mm2": {"rink_puck_centre": round(BOARD.area), "reachable": round(UNION.area),
                  "exclusive": {k: round(v.area) for k, v in EXCL.items()}},
    "episodes": [[o, round(a / FPS, 2), round(b / FPS, 2)] for o, a, b in EP],
    "episodes_note": "[owner, start, end] in match seconds",
    "exclusive_areas_mm": {k: poly_list(v) for k, v in EXCL.items()},
    "sensitivity": {"note": "[time_s, times] per skater with one choice changed; goalie reach for the blocking variant: 36.0 mm (goalie mesh) + puck radius", **SENS},
}, indent=None)
print(json.dumps(per), teams, nobody)

# ---------------------------------------------------------------- review images
SURF, INK, INK2 = "#fcfcfb", "#0b0b0b", "#52514e"
COL = {"W": "#2a78d6", "E": "#eb6834"}
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)


def tint(hexc, a):
    c = np.array([int(hexc[i:i + 2], 16) for i in (1, 3, 5)])
    return tuple(int(v) for v in (c * a + 255 * (1 - a)))


# 1) top view of the areas + the same areas on the video background
S = 1.4
W_, H_ = int(900 * S), int(520 * S)
top = Image.new("RGB", (W_, H_ + 40), SURF)
d = ImageDraw.Draw(top)
T = lambda p: (W_ / 2 + p[0] * S, 20 + H_ / 2 - p[1] * S)
d.polygon([T(p) for p in BOARD.exterior.coords], fill="#ffffff", outline=INK2)
for g in [UNION.difference(unary_union(list(EXCL.values())))]:
    for q in poly_list(g):
        d.polygon([T(p) for p in q], fill="#d9d8d4")
for k, v in EXCL.items():
    for q in poly_list(v):
        d.polygon([T(p) for p in q], fill=tint(COL[k[0]], 0.35), outline=COL[k[0]])
for f in G["fixture_paths"]:
    d.line([T(p) for p in f["centreline"]["points_mm"]], fill=INK2, width=2)
for k, v in EXCL.items():
    c = v.representative_point()
    d.text(T((c.x, c.y)), k, fill=INK, font=FB, anchor="mm")
d.text((10, H_ + 14), "Exclusive reach areas (puck on that skater). Grey: reachable by two or more skaters (nobody). White: no skater reaches. "
       "Blue = Fylling (W, left), orange = Moe (E, right). Lines: slot centrelines.", fill=INK2, font=F)
bg = cv2.imread(str(GAME / "background.png"))
Hc = world_to_crop()
ov = bg.copy()
for k, v in EXCL.items():
    for q in poly_list(v):
        c = tuple(int(COL[k[0]][i:i + 2], 16) for i in (5, 3, 1))
        cv2.fillPoly(ov, [proj(Hc, q).astype(np.int32)], c)
vid = cv2.addWeighted(ov, 0.35, bg, 0.65, 0)
for k, v in EXCL.items():
    c = v.representative_point()
    u, w = proj(Hc, [[c.x, c.y]])[0]
    cv2.putText(vid, k, (int(u) - 14, int(w) + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1, cv2.LINE_AA)
vid = Image.fromarray(cv2.cvtColor(cv2.resize(vid, None, fx=W_ / vid.shape[1], fy=W_ / vid.shape[1]), cv2.COLOR_BGR2RGB))
sheet = Image.new("RGB", (W_, top.height + vid.height), SURF)
sheet.paste(top, (0, 0))
sheet.paste(vid, (0, top.height))
sheet.save(REPO / "validation/game-figure-areas.png")

# 2) per-skater bars: time on the puck, and number of times (two separate charts, one axis each)
order = ["W-LD", "W-RD", "W-C", "W-LW", "W-RW", "E-LD", "E-RD", "E-C", "E-LW", "E-RW"]
img = Image.new("RGB", (1300, 560), SURF)
d = ImageDraw.Draw(img)
d.text((24, 16), "Fylling vs Moe, Trondheim Open 2022 final: puck on each skater (5:00 regulation, tracked)", fill=INK, font=FB)
d.text((24, 44), "Puck on a skater = only that skater can reach it. Proposed; see docs/game-tracking.md for accuracy and assumptions.", fill=INK2, font=F)
for col, (key, title, unit, vmax) in enumerate([("time_s", "Time on the puck", "s", max(v["time_s"] for v in per.values())),
                                                ("times", "Number of times", "", max(v["times"] for v in per.values()))]):
    x0, y0, bw = 120 + col * 640, 100, 440
    d.text((x0 - 96, y0 - 8), title, fill=INK, font=FB)
    for r, s in enumerate(order):
        y = y0 + 30 + r * 38
        v = per[s][key]
        L = bw * v / vmax if vmax else 0
        d.text((x0 - 12, y + 12), s, fill=INK2, font=F, anchor="rm")
        if L > 0:
            d.rounded_rectangle([x0, y + 2, x0 + L, y + 24], radius=4, fill=COL[s[0]])
        d.text((x0 + L + 8, y + 13), f"{v:.1f} {unit}" if key == "time_s" else f"{v}", fill=INK, font=F, anchor="lm")
    d.line([x0, y0 + 26, x0, y0 + 30 + 10 * 38], fill=INK2, width=1)
for j, t in enumerate("WE"):
    d.rounded_rectangle([24 + j * 300, 520, 40 + j * 300, 536], radius=3, fill=COL[t])
    d.text((48 + j * 300, 528), f"{TEAM[t]}: {teams[t]['time_s']:.1f} s, {teams[t]['times']} times", fill=INK, font=F, anchor="lm")
d.text((640, 528), f"Nobody: {sum(nobody.values()):.1f} s (contested {nobody['contested']:.1f}, unreachable {nobody['unreachable']:.1f}, "
       f"long gaps {nobody['long_gap']:.1f}, other {nobody['gap_nobody'] + nobody['short_episode']:.1f})", fill=INK2, font=F, anchor="lm")
img.save(REPO / "validation/game-possession.png")
