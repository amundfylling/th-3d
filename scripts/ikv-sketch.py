"""Invers Kryssar med Velodrom: interpretation sketch on the canonical rink (no trace, no animation yet).

    /root/venvs/blender/bin/python scripts/ikv-sketch.py            -> shots/invers-kryssar-velodrom/sketch-geometry.json
    (then node scripts/ikv-sketch-render.ts and /root/venvs/blender/bin/python scripts/ikv-sketch.py --overlay)

Computes from shots/invers-kryssar-velodrom/sketch.json:
- the figure poses (W-RW at the start and when receiving, W-LW when receiving) and the puck at the blade;
- pass 1 (cross pass, straight), the velodrome (the puck simulated along the boards with the pushing-contact rule and
  the spjass ice friction), the shot (straight), each with its clearance to every figure (all 12, the posed ones at
  their sketch pose, the rest in the assembly pose), the goal posts and the cage;
- with --overlay: draws the lines on the overhead render out/ikv/sketch-*.png -> validation/ikv-sketch.png.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("sp", REPO / "scripts/spjass-trace.py")
sp = importlib.util.module_from_spec(_spec)
_argv = sys.argv[:]
sys.argv = sys.argv[:1]
_spec.loader.exec_module(sp)
sys.argv = _argv
SK = json.loads((REPO / "shots/invers-kryssar-velodrom/sketch.json").read_text())
OUT = REPO / "shots/invers-kryssar-velodrom/sketch-geometry.json"
R = sp.R_PUCK
BLADE_MID = np.array([2.8, 33.1])  # skater blade middle, local mm (figures-report heel/toe mean)


def pose(pid, arc, theta):
    team = pid[0]
    return sp.Static(pid, "skater", sp.Slot(pid).at(arc), sp.HOME[team] + theta)


def puck_at_blade(f, face=+1):
    """Puck centre touching the blade's front (+1) or back (-1) face at its middle."""
    piv, h = f.pose(0)
    loc = BLADE_MID + np.array([face * (R + 1.6), 0.0])
    return piv + sp.rot(h) @ loc


def clear_line(pts, figs, skip=()):
    out = {}
    line = LineString([tuple(p) for p in pts])
    samples = [np.array(line.interpolate(d).coords[0]) for d in np.arange(0, line.length + 1e-9, 1.0)]
    for f in figs:
        if f.pid in skip:
            continue
        out[f.pid] = round(min(sp.clearance(f, 0, q) for q in samples), 1)
    out["goal_posts"] = round(min(min(float(np.linalg.norm(q - po)) for po in sp.POSTS) for q in samples) - R - sp.POST_R, 1)
    out["boards"] = round(min(sp.BOARD.exterior.distance(Point(*q)) for q in samples) - R, 1)
    return out


def velodrome(p, v, a, figs):
    inset = sp.BOARD.buffer(-R)
    p, v = np.array(p, float), np.array(v, float)
    pts, dt = [p.copy()], sp.DT
    for _ in range(int(2.0 / dt)):
        s = float(np.linalg.norm(v))
        if s < 1:
            break
        v = v * max(0.0, s - a * dt) / s
        q = p + v * dt
        if not inset.contains(Point(*q)):  # board: pushing contact, keeps the tangential velocity
            b = inset.exterior
            q = np.array(b.interpolate(b.project(Point(*q))).coords[0])
            v = (q - p) / dt
        p = q
        pts.append(p.copy())
        if p[0] < SK["poses"]["rw_receive"]["catch_x_mm"] if "catch_x_mm" in SK["poses"]["rw_receive"] else False:
            break
    return np.array(pts), v


def main():
    P = SK["poses"]
    rw0 = pose("W-RW", P["rw_start"]["arc_mm"], P["rw_start"]["theta_deg"])
    lw = pose("W-LW", P["lw_receive"]["arc_mm"], P["lw_receive"]["theta_deg"])
    rw1 = pose("W-RW", P["rw_receive"]["arc_mm"], P["rw_receive"]["theta_deg"])
    wc = pose("W-C", P["wc_static"]["arc_mm"], P["wc_static"]["theta_deg"])
    others = [wc] + [sp.Static(pid, "goalie" if f["position"] == "G" else "skater", f["pivot_mm"][:2], f["heading_deg"]) for pid, f in sp.ASM.items() if pid not in ("W-RW", "W-LW", "W-C")]
    p0 = puck_at_blade(rw0, +1)
    p_lw = puck_at_blade(lw, +1)
    p_rw = puck_at_blade(rw1, -1)
    # velodrome: launch from the LW contact, ride the boards until the puck reaches the RW's catch point (x)
    launch_p, launch_v = p_lw.copy(), np.array(SK["velodrome_launch"]["velocity_mm_s"])  # leaves the left wing's blade
    inset = sp.BOARD.buffer(-R)
    p, v, pts = launch_p.copy(), launch_v.copy(), [launch_p.copy()]
    t = 0.0
    while t < 2.0:
        s = float(np.linalg.norm(v))
        v = v * max(0.0, s - SK["ice_friction_mm_s2"] * sp.DT) / s
        q = p + v * sp.DT
        if not inset.contains(Point(*q)):
            b = inset.exterior
            q = np.array(b.interpolate(b.project(Point(*q))).coords[0])
            v = (q - p) / sp.DT
        p = q; pts.append(p.copy()); t += sp.DT
        if p[1] < 0 and sp.clearance(rw1, 0, p) <= 0.05:  # first touch of the right wing (the catch)
            break
    p_rw = p.copy()
    velo = np.array(pts)
    target = np.array(SK["shot_target_mm"])
    shot = [p_rw, target]  # clearance up to the goal line (inside the cage the side net, not the post, would stop it)
    figs_start = [rw0, lw, *others]
    figs_end = [rw1, lw, *others]
    res = {
        "poses": {k: {"pid": f.pid, "pivot_mm": [round(float(x), 1) for x in f.pose(0)[0]], "heading_deg": round(f.pose(0)[1], 1), **P[k]}
                  for k, f in (("rw_start", rw0), ("lw_receive", lw), ("rw_receive", rw1), ("wc_static", wc))},
        "rw_catch_part": "stick/blade" if sp.STICK["skater"].distance(Point(*sp.to_local(rw1, 0, p_rw))) <= sp.LOW["skater"].distance(Point(*sp.to_local(rw1, 0, p_rw))) + 0.3 else "skate/body",
        "puck": {"start": [round(float(x), 1) for x in p0], "lw_contact": [round(float(x), 1) for x in p_lw], "rw_contact": [round(float(x), 1) for x in p_rw]},
        "pass1": {"from": [round(float(x), 1) for x in p0], "to": [round(float(x), 1) for x in p_lw], "length_mm": round(float(np.linalg.norm(p_lw - p0)), 1),
                  "direction_deg": round(math.degrees(math.atan2(*(p_lw - p0)[::-1])), 1),
                  "clearance_mm": clear_line([p0, p_lw], figs_start, skip=("W-RW", "W-LW"))},
        "velodrome": {"points_mm": [[round(float(a), 1), round(float(b), 1)] for a, b in velo[::40]] + [[round(float(velo[-1][0]), 1), round(float(velo[-1][1]), 1)]],
                      "length_mm": round(float(np.sum(np.linalg.norm(np.diff(velo, axis=0), axis=1))), 1), "duration_s": round(t, 3),
                      "launch_speed_mm_s": round(float(np.linalg.norm(launch_v)), 0), "arrival_speed_mm_s": round(float(np.linalg.norm(v)), 0),
                      "clearance_mm": {k: v_ for k, v_ in clear_line(velo[::8], figs_end, skip=("W-LW", "W-RW")).items() if k != "boards"},
                      "behind_goal_min_x_mm": round(float(velo[np.abs(velo[:, 1]) < 60][:, 0].min()), 1), "cage_back_x_mm": round(sp.GX + sp.DEPTH, 1)},
        "shot": {"from": [round(float(x), 1) for x in p_rw], "target": SK["shot_target_mm"], "direction_deg": round(math.degrees(math.atan2(*(target - p_rw)[::-1])), 1),
                 "clearance_mm": clear_line(shot, figs_end, skip=("W-RW",))},
    }
    OUT.write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: res[k] for k in ("poses", "puck")}, indent=0))
    for k in ("pass1", "velodrome", "shot"):
        print(k, {kk: vv for kk, vv in res[k].items() if kk != "points_mm"})


def overlay():
    from PIL import Image, ImageDraw, ImageFont
    geo = json.loads(OUT.read_text())
    cam = json.loads((REPO / "out/ikv/camera.json").read_text())
    W_, H_ = cam["width_px"], cam["height_px"]
    s = W_ / cam["width_mm"]
    X = lambda w: (W_ / 2 + (w[0] - cam["cx"]) * s, H_ / 2 - (w[1] - cam["cy"]) * s)
    base = Image.open(REPO / "out/ikv/sketch-end.png").convert("RGBA")
    start = Image.open(REPO / "out/ikv/sketch-start.png").convert("RGBA")
    # ghost of the start pose (RW start + its puck): blend the start render in a circle around them
    mask = Image.new("L", base.size, 0)
    md = ImageDraw.Draw(mask)
    for w, r in ((geo["poses"]["rw_start"]["pivot_mm"], 62), (geo["puck"]["start"], 26)):
        c = X(w); md.ellipse([c[0] - r * s, c[1] - r * s, c[0] + r * s, c[1] + r * s], fill=150)
    img = Image.composite(start, base, mask)
    ov = Image.new("RGBA", base.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    F = lambda n, b=True: ImageFont.truetype(str(REPO / ("public/fonts/BarlowCondensed-ExtraBold.ttf" if b else "public/fonts/Barlow-SemiBold.ttf")), n)

    def arrow(pts, col, w=9, head=30):
        q = [X(p) for p in pts]
        for a, b in zip(q, q[1:]):
            d.line([a, b], fill=(0, 0, 0, 150), width=w + 6)
        d.line(q, fill=col, width=w, joint="curve")
        (x1, y1), (x0, y0) = q[-1], q[-2]
        L = math.hypot(x1 - x0, y1 - y0) or 1; ux, uy = (x1 - x0) / L, (y1 - y0) / L
        d.polygon([(x1 + ux * 6, y1 + uy * 6), (x1 - ux * head - uy * head * 0.55, y1 - uy * head + ux * head * 0.55), (x1 - ux * head + uy * head * 0.55, y1 - uy * head - ux * head * 0.55)], fill=col, outline=(0, 0, 0, 200))

    def badge(w, n, col, dx=0, dy=0):
        c = X(w); c = (c[0] + dx, c[1] + dy)
        d.ellipse([c[0] - 26, c[1] - 26, c[0] + 26, c[1] + 26], fill=col, outline=(0, 0, 0, 255), width=3)
        d.text(c, str(n), fill=(10, 15, 24, 255), font=F(40), anchor="mm")

    AMB, CYA, GRN, WHT = (255, 178, 30, 255), (47, 214, 255, 255), (60, 224, 122, 255), (244, 246, 250, 255)
    p1 = geo["pass1"]; arrow([p1["from"], p1["to"]], AMB)
    vel = geo["velodrome"]["points_mm"]; arrow(vel, CYA)
    sh = geo["shot"]; tgt = np.array(sh["target"]); fr_ = np.array(sh["from"]); u = (tgt - fr_) / np.linalg.norm(tgt - fr_)
    arrow([fr_, tgt + u * 30], GRN)
    # RW movement: along its slot from the start to the receiving arc (dashed, white with a dark edge)
    slot = sp.Slot("W-RW"); a0, a1 = geo["poses"]["rw_start"]["arc_mm"], geo["poses"]["rw_receive"]["arc_mm"]
    mv = [slot.at(a) + np.array([0, 42.0]) for a in np.linspace(a0 + 5, a1 + 5, 14)]
    q = [X(p) for p in mv]
    for k in range(0, len(q) - 2, 2):
        d.line([q[k], q[k + 1]], fill=(0, 0, 0, 170), width=13)
        d.line([q[k], q[k + 1]], fill=WHT, width=7)
    (x1, y1) = q[-1]
    d.polygon([(x1 + 22, y1), (x1 - 4, y1 - 16), (x1 - 4, y1 + 16)], fill=WHT, outline=(0, 0, 0, 220))
    badge(np.array(p1["from"]) + (np.array(p1["to"]) - np.array(p1["from"])) * 0.45, 1, AMB, dx=-38)
    badge(vel[len(vel) // 2], 2, CYA, dx=-40)
    badge(fr_ + (tgt - fr_) * 0.55, 3, GRN, dx=-36)
    # labels on figures
    def tag(w, text, dx, dy, col):
        c = X(w); x, y = c[0] + dx, c[1] + dy
        tw = d.textlength(text, font=F(30, False))
        d.rectangle([x - 6, y - 4, x + tw + 10, y + 38], fill=(9, 14, 24, 215)); d.rectangle([x - 12, y - 4, x - 6, y + 38], fill=col)
        d.text((x + 2, y + 2), text, fill=WHT, font=F(30, False))
    tag(geo["poses"]["rw_start"]["pivot_mm"], "RIGHT WING · START", -120, 52, AMB)
    tag(geo["poses"]["rw_receive"]["pivot_mm"], "RIGHT WING · SHOOTS", 70, -160, GRN)
    tag(geo["poses"]["lw_receive"]["pivot_mm"], "LEFT WING", -170, 40, CYA)
    img = Image.alpha_composite(img, ov)
    # legend panel
    leg_h = 300
    out = Image.new("RGBA", (W_, H_ + leg_h), (14, 19, 28, 255)); out.paste(img, (0, 0))
    d2 = ImageDraw.Draw(out)
    d2.text((40, H_ + 22), "INVERS KRYSSAR MED VELODROM  ·  HOW I READ IT (sketch for approval, not yet animated)", fill=WHT, font=F(40))
    rows = [(AMB, "1", f"Cross pass: the right wing passes across the ice to the left wing ({p1['length_mm'] / 10:.0f} cm)."),
            (CYA, "2", f"Velodrome: the left wing sends it along the boards - it rides the curved boards behind the goal ({geo['velodrome']['length_mm'] / 10:.0f} cm, {geo['velodrome']['duration_s']:.2f} s)."),
            (GRN, "3", "First-time shot: the right wing, now further up and turned, shoots it straight into the goal."),
            (WHT, "", "Dashed: the right wing moves up his slot and turns round while the puck travels (ghost = his start position).")]
    for i, (col, n, txt) in enumerate(rows):
        y = H_ + 90 + i * 50
        if n:
            d2.ellipse([40, y, 80, y + 40], fill=col); d2.text((60, y + 20), n, fill=(10, 15, 24, 255), font=F(30), anchor="mm")
        else:
            for xx in (40, 58):
                d2.line([(xx, y + 20), (xx + 10, y + 20)], fill=col, width=6)
            d2.polygon([(88, y + 20), (74, y + 10), (74, y + 30)], fill=col)
        d2.text((100, y + 2), txt, fill=WHT, font=F(30, False))
    out.convert("RGB").save(REPO / "validation/ikv-sketch.png")
    print("wrote validation/ikv-sketch.png")


if __name__ == "__main__":
    overlay() if "--overlay" in sys.argv else main()
