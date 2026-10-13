"""Move pictures: the puck.no move pictures recreated on our rink (docs/move-pictures.md).

    python3 scripts/move-pictures/build.py [ids...]           -> out/move-pictures/jobs.json + <id>-geometry.json
    node scripts/move-pictures/render.ts [ids...]              -> out/move-pictures/<id>-base.png (overhead still)
    python3 scripts/move-pictures/build.py --draw [ids...]     -> validation/move-pictures/<id>.png

Reads data/move-pictures/<id>.json (contacts and arrows read off the puck.no picture, or a saved trace) and
data/move-pictures/formation.json (where the other figures stand). A contact made by a figure is snapped to that
figure's blade: the figure is turned to face where the puck goes next (the front of the blade pushes it) and moved
along its slot until the blade is as close as it gets to the picture's point. The arrows are illustrations like the
puck.no ones, not a checked trace (no contact or slide check).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
G = json.loads((REPO / "data/geometry.json").read_text())
HW = json.loads((REPO / "validation/12-hardware-report.json").read_text())
ASM = {f["player_id"]: f for f in json.loads((REPO / "validation/16-assembly-poses.json").read_text())["figures"]}
FORM = json.loads((REPO / "data/move-pictures/formation.json").read_text())
OUT = REPO / "out/move-pictures"
VAL = REPO / "validation/move-pictures"
R = G["puck"]["diameter"]["value"] / 2
BLADE_MID = np.array([2.8, 33.1])  # skater blade middle, local mm (scripts/ikv-sketch.py)
HOME = {"W": 0.0, "E": 180.0}
GX, GY = HW["goal"]["placement_mm"]["E"]
BOARD = np.array(G["board"]["inner_boundary"]["world"]["points_mm"], float)
PX_PER_MM = 3.0
VIEWS = {"half": {"x": (68.0, 436.0), "y": (-252.0, 252.0)}, "full": {"x": (-436.0, 436.0), "y": (-252.0, 252.0)}}
MARGIN_L = 70  # px, left strip for the level scale (as on puck.no)
TURN_COST = 0.15  # mm per degree the blade is turned away from the push
BACKHAND_COST = 2.0  # mm



# Picture style: puck.no arrows (green, numbered circles), NBHF (puck.no) colours from docs/theme.md.
NAVY, RED, ICE = (14, 42, 87), (200, 16, 46), (244, 247, 251)
GREEN = (22, 190, 52)
FONT = str(REPO / "public/fonts/BarlowCondensed-ExtraBold.ttf")


def rot(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s], [s, c]])


class Slot:
    def __init__(self, pid):
        p = next(x for x in G["fixture_paths"] if x["player_id"] == pid)
        self.P = np.array(p["centreline"]["points_mm"], float)
        self.s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(self.P, axis=0), axis=1))]
        self.length = float(self.s[-1])

    def at(self, a):
        a = min(max(a, 0.5), self.length - 0.5)  # the pose code rejects u outside [0, 1]
        return np.array([np.interp(a, self.s, self.P[:, 0]), np.interp(a, self.s, self.P[:, 1])])

    def nearest(self, q):
        arcs = np.linspace(0.5, self.length - 0.5, int(self.length * 2) + 1)
        d = [np.linalg.norm(self.at(a) - q) for a in arcs]
        i = int(np.argmin(d))
        return float(arcs[i]), float(d[i])


def pic_to_world(u, v):
    m = FORM["picture_to_world"]
    return np.array([m["goal_line_x_mm"] - (v - m["goal_line_v_px"]) / m["s_px_per_mm"], (m["centre_u_px"] - u) / m["s_px_per_mm"]])


def solve_contact(pid, target, toward):
    """Pose of pid with the puck against the blade middle (front face pushing toward `toward`, or the back face,
    backhand), as close to target as the slot allows. Turning away from the push direction costs 0.08 mm per degree,
    the backhand 4 mm, so the figure faces the pass unless that leaves the blade far from the picture's point."""
    team = pid[0]
    slot = Slot(pid)
    want = math.degrees(math.atan2(*(toward - target)[::-1]))
    best = None
    for face, extra in ((1, 0.0), (-1, BACKHAND_COST)):
        loc = BLADE_MID + np.array([face * (R + 1.6), 0.0])
        for dh in range(-180, 181, 2):
            h = want + dh + (0 if face > 0 else 180)
            arc, d = slot.nearest(target - rot(h) @ loc)
            cost = d + TURN_COST * abs(dh) + extra
            if best is None or cost < best[0]:
                best = (cost, arc, h, d, face, loc)
    _, arc, h, d, face, loc = best
    theta = (h - HOME[team] + 180) % 360 - 180
    puck = slot.at(arc) + rot(h) @ loc
    return {"pid": pid, "arc_mm": round(arc, 1), "theta_deg": round(theta, 1), "heading_deg": round(h, 1),
            "face": "front" if face > 0 else "back", "turned_from_push_deg": round((h - want - (0 if face > 0 else 180) + 180) % 360 - 180, 1),
            "puck_mm": [round(float(c), 1) for c in puck], "miss_mm": round(d, 1)}


def board_path():
    """The puck centre riding the inner boards (offset by the puck radius + 0.5 mm), closed polyline."""
    P = BOARD
    n = len(P)
    out = []
    for i in range(n):
        t = P[(i + 1) % n] - P[i - 1]
        nrm = np.array([-t[1], t[0]]) / np.linalg.norm(t)
        if np.dot(nrm, -P[i]) < 0:  # inward = towards the rink centre
            nrm = -nrm
        out.append(P[i] + nrm * (R + 0.5))
    return np.array(out)


def board_run(a, b):
    """Board-riding path from near a to near b, the way round that passes the attacking end (largest x)."""
    BP = board_path()
    n = len(BP)
    ia = int(np.argmin(np.linalg.norm(BP - a, axis=1)))
    ib = int(np.argmin(np.linalg.norm(BP - b, axis=1)))
    fwd = [BP[(ia + k) % n] for k in range((ib - ia) % n + 1)]
    bwd = [BP[(ia - k) % n] for k in range((ia - ib) % n + 1)]
    run = fwd if max(p[0] for p in fwd) >= max(p[0] for p in bwd) else bwd
    return [np.asarray(p) for p in run]


def nearest_board(q):
    BP = board_path()
    return BP[int(np.argmin(np.linalg.norm(BP - q, axis=1)))]


def build(spec):
    poses, points, arrows, notes = {}, {}, [], []
    # everyone not in the move stands where the puck.no pictures put them
    for pid, uv in FORM["figures"].items():
        arc, d = Slot(pid).nearest(pic_to_world(*uv))
        poses[pid] = {"arc_mm": round(arc, 1), "theta_deg": 0.0, "source": f"formation (slot {d:.1f} mm from the picture)"}
    for pid, o in spec.get("figures", {}).items():  # a move may move a bystander (e.g. out of a passing lane)
        arc, d = Slot(pid).nearest(pic_to_world(*o["picture_px"]))
        poses[pid] = {"arc_mm": round(arc, 1), "theta_deg": o.get("theta_deg", 0.0), "source": o.get("why", "move spec")}
    if "from_trace" in spec:
        ft = spec["from_trace"]
        tr = json.loads((REPO / ft["trace"]).read_text())
        nodes = tr["puck"]["nodes"]
        T = np.array([q["t"] for q in nodes])
        XY = np.array([[q["x_mm"], q["y_mm"]] for q in nodes])
        at = lambda t: np.array([np.interp(t, T, XY[:, 0]), np.interp(t, T, XY[:, 1])])
        for pid, f in tr["figures"].items():
            if isinstance(f, dict) and pid.startswith(("W-", "E-")):
                ak, tk = f.get("arc_keyframes"), f.get("theta_keyframes")
                if ak and tk:
                    ta = ft["pose_t"]
                    arc = float(np.interp(ta, [k["t"] for k in ak], [k["arc_mm"] for k in ak]))
                    th = float(np.interp(ta, [k["t"] for k in tk], [k["theta_deg"] for k in tk]))
                    if pid != "E-G":
                        poses[pid] = {"arc_mm": round(arc, 2), "theta_deg": round(th, 2), "source": f"{ft['trace']} at t={ta}"}
        stops = [(c["n"], c["t"]) for c in ft["contacts"]] + [("goal", ft["end"]["t"])]
        for n, t in stops:
            points[n] = at(t)
        for (n0, t0), (n1, t1) in zip(stops, stops[1:]):
            sel = (T > t0) & (T < t1)
            arrows.append([at(t0), *XY[sel][:: max(1, int(sel.sum() // 60))], at(t1)])
        puck = points[stops[0][0]]
    else:
        cs = spec["contacts"]
        key = lambda c: "board" if c.get("board") else c["n"]
        raw = {key(c): pic_to_world(*c["picture_px"]) for c in cs}
        for seg in spec["path"]:
            if seg["to"] == "goal":
                raw["goal"] = pic_to_world(*seg["picture_px"])
        nxt = {seg["from"]: seg["to"] for seg in spec["path"]}
        for c in cs:
            k = key(c)
            if c.get("board"):
                points[k] = nearest_board(raw[k])
                continue
            toward = pic_to_world(*c["toward_px"]) if "toward_px" in c else raw[nxt[k]]
            sol = solve_contact(c["pid"], raw[k], toward)
            points[k] = np.array(sol["puck_mm"])
            notes.append({"contact": k, **sol, "picture_mm": [round(float(v), 1) for v in raw[k]], "drawn": c["pose"]})
            if c["pose"]:
                poses[c["pid"]] = {"arc_mm": sol["arc_mm"], "theta_deg": sol["theta_deg"], "source": f"contact {k} (blade snapped)"}
        points["goal"] = raw["goal"]
        for seg in spec["path"]:
            a, b = points[seg["from"]], points[seg["to"]]
            if seg.get("via") == "boards":
                arrows.append([a, *board_run(a, b), b])
            else:
                arrows.append([a, b])
        first = cs[0]
        puck = points[key(first)]
    v = VIEWS[spec["view"]]
    cx, cy = sum(v["x"]) / 2, sum(v["y"]) / 2
    wmm, hmm = v["x"][1] - v["x"][0], v["y"][1] - v["y"][0]
    job = {"id": spec["id"], "poses": {k: {"arc_mm": p["arc_mm"], "theta_deg": p["theta_deg"]} for k, p in poses.items()},
           "puckMm": [round(float(puck[0]), 2), round(float(puck[1]), 2)],
           "camera": {"cx": cx, "cy": cy, "widthMm": wmm}, "widthPx": int(round(wmm * PX_PER_MM)), "heightPx": int(round(hmm * PX_PER_MM)),
           "background": "#%02x%02x%02x" % NAVY}
    geo = {"id": spec["id"], "status": "illustration (PROPOSED): arrows read off the puck.no picture, contacts snapped to the blades; not a checked trace",
           "view": v, "px_per_mm": PX_PER_MM, "poses": poses, "contacts": notes,
           "points_mm": {str(k): [round(float(c), 1) for c in p] for k, p in points.items()},
           "arrows_mm": [[[round(float(c), 1) for c in p] for p in a] for a in arrows]}
    return job, geo


def to_px(geo, p):
    v = geo["view"]
    s = geo["px_per_mm"]
    # rotated 90 deg CCW: +x (attacking goal) up, +y (the attackers' left) left
    return (MARGIN_L + (v["y"][1] - p[1]) * s, (v["x"][1] - p[0]) * s)


def arrow(d, pts, width, color, head, cut_start, cut_end):
    pts = [np.array(p, float) for p in pts]
    pts = [p for i, p in enumerate(pts) if i == 0 or np.linalg.norm(p - pts[i - 1]) > 0.5]

    def trim(ps, cut):
        while cut > 0 and len(ps) > 1:
            seg = np.linalg.norm(ps[1] - ps[0])
            if seg > cut:
                ps[0] = ps[0] + (ps[1] - ps[0]) * cut / seg
                return ps
            cut -= seg
            ps.pop(0)
        return ps
    pts = trim(pts, cut_start)
    pts = trim(pts[::-1], cut_end)[::-1]
    length = sum(np.linalg.norm(b - a) for a, b in zip(pts, pts[1:]))
    head = min(head, 0.55 * length)  # a short pass (Näcka's heel pass) still shows a line behind the head
    tip = pts[-1]
    # direction at the tip from the last ~head length of the line
    acc, i = 0.0, len(pts) - 1
    while i > 0 and acc < head:
        acc += np.linalg.norm(pts[i] - pts[i - 1])
        i -= 1
    u = tip - pts[i]
    u = u / np.linalg.norm(u)
    nrm = np.array([-u[1], u[0]])
    base = tip - u * head
    line = pts[: i + 1] + [tip - u * head * 0.6]
    d.line([tuple(p) for p in line], fill=color, width=width, joint="curve")
    for p in (line[0], line[-1]):
        d.ellipse([p[0] - width / 2, p[1] - width / 2, p[0] + width / 2, p[1] + width / 2], fill=color)
    d.polygon([tuple(tip), tuple(base + nrm * head * 0.55), tuple(base - nrm * head * 0.55)], fill=color)


def badge(d, p, n, r):
    d.ellipse([p[0] - r - 3, p[1] - r - 3, p[0] + r + 3, p[1] + r + 3], fill=(255, 255, 255))
    d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=NAVY)
    f = ImageFont.truetype(FONT, int(r * 1.45))
    d.text((p[0], p[1] + 1), str(n), font=f, fill=(255, 255, 255), anchor="mm")


def level_scale(d, h, level):
    """The puck.no difficulty scale 0-9 on the left edge, the move's level boxed in red."""
    cell = 34
    x0 = (MARGIN_L - cell) // 2
    y0 = int(h * 0.30)
    f = ImageFont.truetype(FONT, 24)
    for k in range(10):
        y = y0 + k * cell
        d.rectangle([x0, y, x0 + cell, y + cell], fill=ICE, outline=NAVY, width=1)
        d.text((x0 + cell / 2, y + cell / 2 + 1), str(k), font=f, fill=NAVY, anchor="mm")
    y = y0 + level * cell
    d.rectangle([x0 - 3, y - 3, x0 + cell + 3, y + cell + 3], outline=RED, width=5)


def draw(spec, geo):
    base = Image.open(OUT / f"{spec['id']}-base.png").convert("RGB").rotate(90, expand=True)
    W, H = base.width + MARGIN_L, base.height
    im = Image.new("RGB", (W, H), NAVY)
    im.paste(base, (MARGIN_L, 0))
    d = ImageDraw.Draw(im)
    r = 21
    pts = {k: to_px(geo, p) for k, p in geo["points_mm"].items()}
    for a in geo["arrows_mm"]:
        P = [to_px(geo, p) for p in a]
        start_is_badge = any(np.allclose(P[0], q) for k, q in pts.items() if k not in ("goal", "board"))
        end_is_badge = any(np.allclose(P[-1], q) for k, q in pts.items() if k not in ("goal", "board"))
        arrow(d, P, 13, GREEN, 46, r + 6 if start_is_badge else 0, r + 7 if end_is_badge else 0)
    for k, p in pts.items():
        if k not in ("goal", "board"):
            badge(d, p, k, r)
    level_scale(d, H, spec["level"])
    VAL.mkdir(parents=True, exist_ok=True)
    out = VAL / f"{spec['id']}.png"
    im.save(out, optimize=True)
    print("wrote", out.relative_to(REPO), im.size)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ids = args or sorted(p.stem for p in (REPO / "data/move-pictures").glob("*.json") if p.stem != "formation")
    OUT.mkdir(parents=True, exist_ok=True)
    if "--draw" in sys.argv:
        for i in ids:
            spec = json.loads((REPO / f"data/move-pictures/{i}.json").read_text())
            draw(spec, json.loads((OUT / f"{i}-geometry.json").read_text()))
        return
    jobs = []
    for i in ids:
        spec = json.loads((REPO / f"data/move-pictures/{i}.json").read_text())
        job, geo = build(spec)
        jobs.append(job)
        (OUT / f"{i}-geometry.json").write_text(json.dumps(geo, indent=1, ensure_ascii=False) + "\n")
        for c in geo["contacts"]:
            print(i, "contact", c["contact"], c["pid"], "arc", c["arc_mm"], "theta", c["theta_deg"], c["face"], "turned", c["turned_from_push_deg"], "miss", c["miss_mm"], "mm")
    (OUT / "jobs.json").write_text(json.dumps(jobs, indent=1) + "\n")
    print("wrote", (OUT / "jobs.json").relative_to(REPO), len(jobs), "jobs")


if __name__ == "__main__":
    main()
