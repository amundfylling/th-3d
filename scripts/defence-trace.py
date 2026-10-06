"""Defending against the left wing: one contact-checked trace that illustrates the three defences from the user's
TikTok (references/shots/defence-vs-left-wing-tiktok.mp4): passive (the box), active, and the mix.

    /root/venvs/blender/bin/python scripts/defence-trace.py

Inputs: shots/defence-left-wing/inputs.json, the geometry and figure meshes (helpers from scripts/spjass-trace.py).
Outputs: data/traces/defence-left-wing.trace.json, shots/defence-left-wing/checks.json, validation/defence-trace.png.

A concept illustration, not a recorded shot:
- the attacking left wing (W-LW) holds the puck still on the front of its blade at the +y boards near the goal line;
  the attacking centre (W-C) waits in the slot;
- the defending goalie (E-G) and right defender (E-RD) move between the set-ups (designed smootherstep moves; the
  defender turns to face the puck);
- the attacker's options are LANES: the straight shot into the short corner, the centrifuge pass to the centre and
  the centre's first-time shot into the far corner. Each lane is swept with the finite puck; where it would first
  touch a defending figure (goalie, defender) it is BLOCKED there, otherwise OPEN. The video draws these lanes as
  graphics; the puck itself never leaves the left wing's blade, so no blocked shot is simulated.
Checks (CLAUDE.md "Contact physics", "Slide or bounce"): the finite puck against every figure, the boards and the
posts every 0.25 ms (overlap tolerance 0.1 mm); the puck never moves, so no contact changes its motion.
"""
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Point

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("spjass_trace", REPO / "scripts/spjass-trace.py")
sp = importlib.util.module_from_spec(_spec)
sys.argv = sys.argv[:1]
_spec.loader.exec_module(sp)  # helpers only

INP = json.loads((REPO / "shots/defence-left-wing/inputs.json").read_text())
SPJ = json.loads((REPO / "data/traces/spjass.trace.json").read_text())
OUT_TRACE = REPO / "data/traces/defence-left-wing.trace.json"
OUT_CHECKS = REPO / "shots/defence-left-wing/checks.json"
OUT_PNG = REPO / "validation/defence-trace.png"
DT, EPS, PEN_TOL, R_PUCK = sp.DT, sp.EPS, sp.PEN_TOL, sp.R_PUCK
KEY_DT = 0.01


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def goalie_arc(y):
    s = sp.Slot("E-G")
    return float(min(np.arange(0, s.length, 0.05), key=lambda a: abs(s.at(a)[1] - y)))


def build():
    t0, t1 = INP["window_s"]
    a, c = INP["attacker"]["W-LW"], INP["attacker"]["W-C"]
    key = lambda arc, why: [{"t": t0, "arc_mm": arc, "sigma_mm": None, "source": why}]
    th = lambda v, why: [{"t": t0, "theta_deg": v, "sigma_deg": None, "source": why}]
    lw = sp.Figure("W-LW", "W", "skater", key(a["arc_mm"], "designed: holds the puck"), th(a["theta_deg"], "designed"))
    wc = sp.Figure("W-C", "W", "skater", key(c["arc_mm"], "designed: waits in the slot"), th(c["theta_deg"], "designed"))
    # puck resting against the front of the left wing's blade (moved out to just touching)
    p = sp.to_world(lw, t0, np.array(a["puck_local_mm"]) - np.array([2.0, 0.0]))
    p, _ = sp.push_out(lw, t0, p)
    # defender and goalie: smootherstep moves between the set-ups of the schedule, keys every 10 ms
    S = INP["setups"]
    sched = INP["schedule"]
    rd_slot = sp.Slot("E-RD")

    def rd_theta(arc):
        piv = rd_slot.at(arc)
        h = math.degrees(math.atan2(p[1] - piv[1], p[0] - piv[0]))
        return ((h - 180.0 + 180.0) % 360.0) - 180.0 if INP["defender_faces_puck"] else 0.0

    eg_slot = sp.Slot("E-G")

    def g_theta(setup):
        """Goalie rotation: square to the play (0) or, when the set-up says so, turned with its BACK to the puck so its
        whole width lies across the straight-shot line (the user: 'the back outwards ... cover the corner')."""
        if not S[setup].get("E-G_back_to_puck"):
            return 0.0
        piv = eg_slot.at(goalie_arc(S[setup]["E-G_y_mm"]))
        away = math.degrees(math.atan2(piv[1] - p[1], piv[0] - p[0]))  # facing away from the puck
        return away - 180.0 + 360.0 if away - 180.0 < -180.0 else away - 180.0

    rd_arcs, rd_th, g_arcs, g_th = [], [], [], []
    for (ta, sa), (tb, sb) in zip(sched[:-1], sched[1:]):
        n = max(1, int(round((tb - ta) / KEY_DT)))
        for k in range(0 if not rd_arcs else 1, n + 1):
            t = ta + (tb - ta) * k / n
            u = smooth(k / n) if sa != sb else 0.0
            arc = S[sa]["E-RD_arc_mm"] + (S[sb]["E-RD_arc_mm"] - S[sa]["E-RD_arc_mm"]) * u
            ga = goalie_arc(S[sa]["E-G_y_mm"]) + (goalie_arc(S[sb]["E-G_y_mm"]) - goalie_arc(S[sa]["E-G_y_mm"])) * u
            why = f"designed: {sa}" if sa == sb else f"designed: {sa} -> {sb}"
            rd_arcs.append({"t": round(t, 5), "arc_mm": round(arc, 4), "sigma_mm": None, "source": why})
            rd_th.append({"t": round(t, 5), "theta_deg": round(rd_theta(arc), 4), "sigma_deg": None, "source": why + " (faces the puck)"})
            g_arcs.append({"t": round(t, 5), "arc_mm": round(ga, 4), "sigma_mm": None, "source": why})
            gt = g_theta(sa) + (g_theta(sb) - g_theta(sa)) * u
            g_th.append({"t": round(t, 5), "theta_deg": round(gt, 4), "sigma_deg": None, "source": why + (" (back to the puck)" if S[sb].get("E-G_back_to_puck") or S[sa].get("E-G_back_to_puck") else "")})
    rd = sp.Figure("E-RD", "E", "skater", rd_arcs, rd_th)
    eg = sp.Figure("E-G", "E", "goalie", g_arcs, g_th)
    others = {pid: sp.Static(pid, "goalie" if f["position"] == "G" else "skater", f["pivot_mm"][:2], f["heading_deg"]) for pid, f in sp.ASM.items() if pid not in ("W-LW", "W-C", "E-RD", "E-G")}
    return t0, t1, p, lw, wc, rd, eg, others


def blade_point(f, t):
    """Puck centre just touching the front of the figure's blade at mid blade (where a pass is received)."""
    q = sp.to_world(f, t, np.array([12.0, 33.0]))
    q, _ = sp.push_out(f, t, q)
    return q


def sweep(a, b, t, blockers, step=0.25):
    """Move the finite puck from a to b; the first position where it would overlap a blocker (defending figure or
    post) is the block: returns (end point just touching, blocker id or None)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = float(np.linalg.norm(b - a))
    n = max(1, int(L / step))
    last = a
    for k in range(1, n + 1):
        q = a + (b - a) * k / n
        for f in blockers:
            if sp.clearance(f, t, q) < 0:
                return last, f.pid
        for i, po in enumerate(sp.POSTS):
            if np.linalg.norm(q - po) < R_PUCK + sp.POST_R:
                return last, "goal_post"
        last = q
    return b, None


def lanes_at(t, p, wc, rd, eg):
    L = INP["lanes"]
    R = blade_point(wc, t)
    out = {}
    for name, a, b in (("straight_shot", p, np.array(L["straight_shot"]["to"])), ("centrifuge_pass", p, R), ("centre_shot", R, np.array(L["centre_shot"]["to"]))):
        end, who = sweep(a, b, t, [rd, eg])
        out[name] = {"from_mm": [round(float(a[0]), 2), round(float(a[1]), 2)], "to_mm": [round(float(b[0]), 2), round(float(b[1]), 2)],
                     "end_mm": [round(float(end[0]), 2), round(float(end[1]), 2)], "blocked_by": who, "open": who is None, "note": L[name]["note"]}
    return out


def main():
    t0, t1, p, lw, wc, rd, eg, others = build()
    figs = [lw, wc, rd, eg, *others.values()]
    # contact check: the finite puck (static) against every figure, the boards and the posts every DT
    rows, viol = {}, []
    for tq in np.arange(t0, t1 + 1e-9, DT):
        cs = [(f.pid, sp.clearance(f, tq, p)) for f in figs] + [("boards", sp.BOARD.exterior.distance(Point(*p)) - R_PUCK)]
        cs += [(f"goal_post_{'pos' if k == 0 else 'neg'}_y", float(np.linalg.norm(p - po)) - R_PUCK - sp.POST_R) for k, po in enumerate(sp.POSTS)]
        for ob, c in cs:
            r = rows.setdefault(ob, {"min_clearance_mm": 1e9, "t_at_min": None})
            if c < r["min_clearance_mm"]:
                r.update(min_clearance_mm=round(float(c), 3), t_at_min=round(float(tq), 5))
            if c < -PEN_TOL:
                viol.append((ob, round(float(tq), 5), round(float(c), 3)))
    # set-ups and lanes
    sched = INP["schedule"]
    marks = [("setup.neutral", 0.3, "neutral"), ("passive.set", 1.0, "passive"), ("active.set", 2.4, "active"),
             ("mix.passive_1", 3.7, "passive"), ("mix.active", 4.5, "active"), ("mix.passive_2", 5.3, "passive")]
    events = []
    for eid, tq, setup in marks:
        lanes = lanes_at(tq, p, wc, rd, eg)
        events.append({"id": eid, "t_estimate": tq, "setup": setup, "E-RD_pivot_mm": [round(float(x), 2) for x in rd.pose(tq)[0]], "E-RD_heading_deg": round(rd.pose(tq)[1], 2),
                       "E-G_pivot_mm": [round(float(x), 2) for x in eg.pose(tq)[0]], "E-G_heading_deg": round(eg.pose(tq)[1], 2), "lanes": lanes,
                       "status": "designed set-up; lanes swept with the finite puck"})
    moves = [{"id": f"move.{sa}_to_{sb}", "t_estimate": ta, "t_end": tb, "status": "designed"} for (ta, sa), (tb, sb) in zip(sched[:-1], sched[1:]) if sa != sb]
    events = sorted(events + moves, key=lambda e: e["t_estimate"])
    nodes = [{"t": round(float(t), 5), "x_mm": round(float(p[0]), 4), "y_mm": round(float(p[1]), 4), "phase": "held_by_left_wing"} for t in (t0, t1)]
    fig_out = lambda f, status: {"player_id": f.pid, "team": f.team, "fixture_path_id": f.slot.id, "slot_length_mm": round(f.slot.length, 2), "status": status,
                                 "arc_keyframes": f.arcs, "theta_keyframes": f.thetas}
    trace = {
        "schema": "shot-trace/1", "trace_id": "trace.defence-left-wing.v1", "status": INP["status"],
        "shot": "Defending against the left wing: passive (the box), active, mix (concept illustration)",
        "geometry_version": sp.G["geometry_version"],
        "asset_refs": {**SPJ["asset_refs"], "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()},
        "source": {**INP["source"], "inputs": "shots/defence-left-wing/inputs.json"},
        "time_base": {"t": "designed time (s); a concept illustration, no recording", "window_s": [t0, t1]},
        "interpolation": SPJ["interpolation"], "pose_convention": SPJ["pose_convention"],
        "figures": {"W-LW": fig_out(lw, "static: holds the puck (designed)"), "W-C": fig_out(wc, "static: waits in the slot (designed)"),
                    "E-RD": fig_out(rd, "moving: the defender on the left wing's side (designed set-ups)"), "E-G": fig_out(eg, "moving: goalie (designed set-ups)"),
                    "others": "static assembly pose (validation/16-assembly-poses.json), as the renderer shows them; included in the checks"},
        "puck": {"radius_mm": R_PUCK, "radius_status": "catalog_nominal", "thickness_mm": sp.PUCK_T, "thickness_status": "assumed (preview)",
                 "nodes": nodes, "phases": [{"id": "held_by_left_wing", "t": [t0, None]}]},
        "events": events,
        "limitations": INP["limitations"],
    }
    samp = []
    for tq in np.round(np.arange(t0, t1 + 1e-9, 0.1), 4):
        samp.append({"t": float(tq), **{f.pid: {"arc_mm": round(f.arc(tq), 4), "theta_deg": round(f.theta(tq), 4)} for f in (rd, eg)}, "puck": [round(float(p[0]), 4), round(float(p[1]), 4)]})
    trace["evaluation_samples"] = samp
    OUT_TRACE.write_text(json.dumps(trace, indent=1, ensure_ascii=False) + "\n")
    checks = {"trace_id": trace["trace_id"], "sampling_s": DT, "penetration_tolerance_mm": PEN_TOL,
              "contact_rule": "CLAUDE.md 'Contact physics': the finite puck against every figure (all 12), the boards and the posts every 0.25 ms, no exemptions",
              "min_clearance_by_obstacle": [{"obstacle": k, **v} for k, v in sorted(rows.items()) if v["min_clearance_mm"] < 60],
              "unexpected_penetrations": [{"obstacle": o, "t": t, "clearance_mm": c} for o, t, c in viol[:20]], "approved_exceptions": [],
              "contact_sequence": ["W-LW:stick/blade"], "unexplained_count": 0,
              "slide_check": {"rule": "CLAUDE.md 'Slide or bounce'", "figure_impact_max_mm_s": 500.0, "wall_impact_max_mm_s": 300.0, "per_contact": [],
                              "note": "the puck rests on the left wing's blade the whole time: no impacts. Shots and passes are drawn as lanes, not simulated.", "passed": True},
              "lanes": {e["id"]: {k: {"blocked_by": v["blocked_by"], "end_mm": v["end_mm"]} for k, v in e["lanes"].items()} for e in events if "lanes" in e}}
    OUT_CHECKS.write_text(json.dumps(checks, indent=1, ensure_ascii=False) + "\n")
    sheet(figs, p, events)
    print(json.dumps({"puck": [round(float(x), 2) for x in p], "violations": viol[:5], "lanes": checks["lanes"],
                      "close": [r for r in checks["min_clearance_by_obstacle"] if r["min_clearance_mm"] < 5]}, indent=1))


def sheet(figs, p, events):
    S, W_, H_ = 1.6, 560, 560
    P_ = lambda w: (W_ / 2 - (w[1] - 90) * S, H_ - 20 - (w[0] - 40) * S)
    tiles = []
    for e in [x for x in events if "lanes" in x][:3]:
        tq = e["t_estimate"]
        im = Image.new("RGB", (W_, H_), "white"); d = ImageDraw.Draw(im)
        d.line([P_(c) for c in sp.BOARD.exterior.coords], fill=(60, 60, 60), width=2)
        for po in sp.POSTS:
            c = P_(po); d.ellipse([c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3], fill=(200, 0, 0))
        for f in figs:
            poly = sp.world_polygon(f, tq)
            for g in ([poly] if poly.geom_type == "Polygon" else list(poly.geoms)):
                d.polygon([P_(c) for c in g.exterior.coords], fill=(150, 190, 255) if f.pid.startswith("W") else (255, 225, 120), outline=(30, 30, 30))
        for name, ln in e["lanes"].items():
            col = (0, 160, 0) if ln["open"] else (210, 0, 0)
            d.line([P_(ln["from_mm"]), P_(ln["end_mm"])], fill=col, width=3)
            if not ln["open"]:
                c = P_(ln["end_mm"]); d.line([c[0] - 8, c[1] - 8, c[0] + 8, c[1] + 8], fill=col, width=3); d.line([c[0] - 8, c[1] + 8, c[0] + 8, c[1] - 8], fill=col, width=3)
        c = P_(p); d.ellipse([c[0] - R_PUCK * S, c[1] - R_PUCK * S, c[0] + R_PUCK * S, c[1] + R_PUCK * S], fill=(0, 0, 0))
        d.text((8, 6), f"{e['setup'].upper()}  t={tq:.2f} s", fill=(0, 0, 0), font=sp.FB)
        d.text((8, 30), "  ".join(f"{k}: {'OPEN' if v['open'] else 'blocked by ' + v['blocked_by']}" for k, v in e["lanes"].items()), fill=(0, 0, 0), font=sp.FS)
        tiles.append(im)
    out = Image.new("RGB", (W_ * len(tiles), H_ + 34), "white")
    for i, im in enumerate(tiles):
        out.paste(im, (i * W_, 34))
    ImageDraw.Draw(out).text((10, 6), "trace.defence-left-wing.v1 - top view of goal.E (goal line at the top, +y left); lanes: green open, red blocked (finite puck sweep)", fill=(0, 0, 0), font=sp.FB)
    out.save(OUT_PNG)


if __name__ == "__main__":
    main()
