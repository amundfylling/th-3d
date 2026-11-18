"""Goal clip -> editable th-combo/1 draft (hypothesis experiment, PROPOSED).

    python3 scripts/clip2combo.py g1 83.1 [--out file.json]          one clip: game and the clip's end (the goal, video s)
    python3 scripts/clip2combo.py --goal g1-goal1 [--auto-end]       a goal of data/games/nm26-semifinal/goal-labels.json
    python3 scripts/clip2combo.py --all [--auto-end] --outdir DIR    all 25 marked goals

What it does, from the committed NM26 tracks (no video, no torch; pure numpy):
  1. CALIBRATE  reuses <game>/calibration.json (tracks are already in world mm). Not re-run here.
  2. TRACKS     puck-track-synth-v2 (via the passes-synth-v1 flights) and figure-tracks-v3.
  3. SEGMENT    the last possession of the scoring team before the clip's end becomes touches, passes and a shot:
                - flights of the puck come from <game>/passes-synth-v1.json (who released, who received);
                - REPAIR: two 'battle' flights in a row (a->b, b->c) are one flight a->c (a pass that crosses an
                  opponent's reach area), a 'battle'/'turnover' flight that starts at the scoring team and ends in an
                  opponent's reach is attributed to the scoring skater nearest its end when one is within 90 mm;
                - the chain stops at the last flight released by the opponent; at most 4 passes.
                - the SCORER is the last receiver (or the last carrier when nobody passed); the shot itself is not in
                  the broadcast, so its arrow runs from the scorer's last puck point to the goal-mouth corner away from
                  the goalie (ASSUMED).
  4. EMIT       a th-combo/1 file in the attacking team's frame (scoring team = W, attacks +x, like the editor's library):
                figures at their first touch time (arc_mm = u * slot length, theta relative to the home heading, as in
                the tracks), puck at the first touch, one arrow per pass/shot, numbered touches.
  5. NAME       family from the touch roles (rule table below, no fitting) and the nearest library move.
Output keys beyond th-combo/1 are kept in `clip2combo` (the editor ignores unknown keys).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import table_common as T  # noqa: E402

D = REPO / "data/games/nm26-semifinal"
FPS = 30.0
BLADE_MID = (2.8, 33.1)  # blade middle in the figure frame, as the editor's BLADE_MID_MM
GOAL_E = {"x": 286.79, "y": 0.53, "mouth": 86.94}  # the goal W attacks (validation/12-hardware-report.json)
SCHEMA = "th-combo/1"
SKATERS = ["LW", "RW", "C", "LD", "RD"]
LIB_PATHS = [REPO / "site/public/library.json", REPO / "../th-site/site/public/library.json"]


# switches of the segmentation; the evaluation turns them on one by one (docs/clip2combo.md)
LIB_DISTANCE = "pass_path"  # or "pose_and_paths" (the first version; blade positions at the set-up + path chamfer)
OPTS = {"repair": True, "end_by_holder": True, "shot_aware": True, "restart_at_carrier": True, "unseen_pass": True}


def lib():
    for p in LIB_PATHS:
        if p.exists():
            return json.loads(p.read_text())
    return None


# ---------------------------------------------------------------- frames


def flip_pt(p):  # the rink is point symmetric: W-X <-> E-X under a 180 degree turn
    return [-p[0], -p[1]]


def flip_pid(pid):
    return ("E" if pid[0] == "W" else "W") + pid[1:]


def team_of(pid):
    return pid[0]


def blade_world(pid, arc_mm, theta_deg):
    u = arc_mm / T.SLOT_LEN[pid]
    p = T.slot_point(pid, u)
    h = math.radians(T.HOME[pid[0]] + theta_deg)
    return [p[0] + math.cos(h) * BLADE_MID[0] - math.sin(h) * BLADE_MID[1], p[1] + math.sin(h) * BLADE_MID[0] + math.cos(h) * BLADE_MID[1]]


# ---------------------------------------------------------------- data


class Game:
    def __init__(self, g):
        self.g = g
        pj = json.loads((D / g / "passes-synth-v1.json").read_text())
        self.events = pj["events"]
        fj = json.loads((D / g / "figure-tracks-v3.json").read_text())
        self.fcols = fj["columns"]
        self.frows = np.array([[np.nan if v is None else v for v in r] for r in fj["rows"]], float)
        self.fframes = self.frows[:, 0]
        tj = json.loads((D / g / "puck-track-synth-v2.json").read_text())
        c = tj["columns"]
        self.prows = np.array([[r[c.index("frame")], r[c.index("x_mm")], r[c.index("y_mm")]] for r in tj["rows"] if r[c.index("x_mm")] is not None], float)

    def pose_at(self, pid, t, search_s=1.0):
        """(arc_mm, theta_deg, found, dt) of figure pid near video time t; the nearest valid reading within search_s."""
        iu, ith = self.fcols.index(f"{pid}_u"), self.fcols.index(f"{pid}_theta_deg")
        fr = t * FPS
        order = np.argsort(np.abs(self.fframes - fr))[:40]
        for k in order:
            if abs(self.fframes[k] - fr) / FPS > search_s:
                break
            u, th = self.frows[k, iu], self.frows[k, ith]
            if not (np.isnan(u) or np.isnan(th)):
                return float(u) * T.SLOT_LEN[pid], float(th), True, float(self.fframes[k] / FPS - t)
        return None, None, False, None

    def puck_near_end(self, t_end, back_s=3.0):
        sel = self.prows[(self.prows[:, 0] / FPS <= t_end + 0.3) & (self.prows[:, 0] / FPS >= t_end - back_s)]
        return sel


# ---------------------------------------------------------------- segmentation


def infer_scoring_end(G, t_end):
    """The end whose team scores. end_by_holder: the team of the last pass, carry or shot (not a battle or a turnover: those
    are flights that end in an opponent's reach, often after the goal) released in the 2.5 s before the clip's end; if there
    is none, or the switch is off, the puck's last tracked positions: x > 0 means W attacks the E goal."""
    if OPTS["end_by_holder"]:
        ev = [e for e in G.events if t_end - 2.5 <= e["t_release_s"] <= t_end + 0.35 and e["kind"] in ("pass", "carry", "shot")]
        if ev:
            return ev[-1]["from"][0], len(ev)
    s = G.puck_near_end(t_end, 2.5)
    if len(s) == 0:
        s = G.puck_near_end(t_end, 6.0)
    if len(s) == 0:
        return None, 0
    last = s[-8:]
    return ("W" if last[:, 1].mean() > 0 else "E"), len(s)


def merge_battles(evs):
    """Two 'battle' flights in a row where the first one's receiver releases the second (a->b, b->c within 0.3 s) are one
    flight a->c: the puck crossed an area that two skaters can reach."""
    out = []
    for e in evs:
        if out and e["kind"] == "battle" and out[-1]["kind"] == "battle" and out[-1]["to"] == e["from"] and e["t_release_s"] - out[-1]["t_reception_s"] <= 0.3:
            p = out[-1]
            m = dict(p)
            m["to"] = e["to"]
            m["to_uncertain"] = e["to_uncertain"]
            m["t_reception_s"] = e["t_reception_s"]
            m["frame_reception"] = e["frame_reception"]
            m["line_mm"] = p["line_mm"] + e["line_mm"][1:] if p["line_mm"][-1] == e["line_mm"][0] else p["line_mm"] + e["line_mm"]
            m["kind"] = "merged_battle"
            out[-1] = m
        else:
            out.append(e)
    return out


def nearest_skater_blade(G, S, point, t, max_mm=90.0):
    best = (1e9, None)
    for r in SKATERS:
        pid = f"{S}-{r}"
        a, th, ok, _ = G.pose_at(pid, t, 0.5)
        if not ok:
            continue
        d = float(np.hypot(*(np.array(blade_world(pid, a, th)) - np.array(point))))
        if d < best[0]:
            best = (d, pid)
    return best[1] if best[0] <= max_mm else None


def length(line):
    return sum(math.dist(line[i], line[i + 1]) for i in range(len(line) - 1))


def in_goal_zone(line, S):
    """A flight that ends within 150 mm of the goal line the team S attacks (attacker frame x >= 140 after the turn)."""
    p = line[-1] if S == "W" else flip_pt(line[-1])
    return p[0] >= 140.0 and abs(p[1]) <= 110.0


def segment(G, t_end, S, window_s=12.0, max_passes=4):
    """Returns (events, flights, info). flights = passes of the scoring team S in order; info holds the scorer
    reading ('seen' or 'inferred') and the notes."""
    evs = [e for e in G.events if t_end - window_s <= e["t_release_s"] <= t_end + 0.35]
    if OPTS["repair"]:
        evs = merge_battles(evs)
    flights, notes, shot_ev = [], [], None
    boundary_t = -1e9
    for e in reversed(evs):
        f, to, k = e["from"], e["to"], e["kind"]
        if OPTS["repair"] and k in ("battle", "turnover", "merged_battle") and f[0] == S and to[0] != S and length(e["line_mm"]) >= 60:
            alt = nearest_skater_blade(G, S, e["line_mm"][-1], e["t_reception_s"])
            if alt and alt != f:
                e = dict(e); e["to"] = to = alt; e["kind"] = k = "pass(repaired)"
        if OPTS["shot_aware"] and f[0] == S and (k == "shot" or (to[0] != S and (to.endswith("-G") or in_goal_zone(e["line_mm"], S)))) and not flights and shot_ev is None and e["t_release_s"] >= t_end - 1.5:
            shot_ev = e  # the shot itself was seen: it is the end of the chain, not a loss of the puck
            continue
        is_pass = k in ("pass", "pass(repaired)", "merged_battle") and f[0] == S and to[0] == S and f != to
        if is_pass and length(e["line_mm"]) >= 60:
            if len(flights) < max_passes:
                flights.insert(0, e)
            continue
        if k == "shot" and f[0] == S:
            continue
        if f[0] != S:
            boundary_t = e["t_reception_s"]; break
        if k in ("turnover", "battle") and to[0] != S:
            boundary_t = e["t_reception_s"]; break
    flights = [e for e in flights if e["t_release_s"] >= boundary_t - 1e-6]
    info = {"shot_seen": shot_ev is not None, "shot_from": shot_ev["from"] if shot_ev else None, "scorer_source": "last receiver", "inferred": None}
    last_recv = flights[-1]["to"] if flights else None
    # the last carrier of S after the last pass: the puck moved on to it without a flight we saw
    after = [e for e in evs if e["from"][0] == S and e["kind"] == "carry" and (not flights or e["t_release_s"] >= flights[-1]["t_reception_s"] + 0.25)]
    carrier = after[-1]["from"] if after else None
    if OPTS["restart_at_carrier"] and carrier and last_recv and carrier != last_recv:
        notes.append(f"chain restarted at {carrier}: it carried the puck after the last seen pass to {last_recv}")
        flights = []; last_recv = None; info["scorer_source"] = "last carrier"
    if shot_ev is not None and not flights:
        info["shot_from_role"] = role(shot_ev["from"])
    info["carrier"] = carrier
    info["notes"] = notes
    return evs, flights, info


def rebound_hint(evs, S, t_end):
    """An earlier shot by the scoring team in the last 4 s (the rebound family)."""
    return any(e["kind"] == "shot" and e["from"][0] == S and t_end - 4.0 <= e["t_release_s"] < t_end - 0.4 for e in evs)


# ---------------------------------------------------------------- roles, family, library


def role(pid):
    return pid.split("-")[1]


def family_from_roles(seq, rebound):
    """Rule table, written from the playbook (no fitting). seq = roles of the touches, the last one shoots."""
    if not seq:
        return "unknown"
    scorer = seq[-1]
    assist = seq[-2] if len(seq) > 1 else None
    if rebound:
        return "rebound"
    if scorer == "C":
        if assist == "RW":
            return "shovel"
        if assist == "LW":
            return "centrifuge"
        return "centre"
    if scorer in ("LD", "RD", "G"):
        return "defence"
    if scorer in ("LW", "RW"):
        return "wing"
    return "unknown"


def library_roles(m):
    """Touch roles of a library move: the attacking figures nearest to the arrows' end points (blade, <= 80 mm)."""
    pts = []
    for a in m["arrows"]:
        pts += [a["points_mm"][0], a["points_mm"][-1]]
    seq = []
    for p in pts:
        best = (1e9, None)
        for pid, ps in m["figures"].items():
            if pid[0] != "W" or pid.endswith("-G") and False:
                continue
            d = math.dist(blade_world(pid, ps["arc_mm"], ps["theta_deg"]), p)
            if d < best[0]:
                best = (d, pid)
        if best[1] and best[0] <= 80:
            r = role(best[1])
            if not seq or seq[-1] != r:
                seq.append(r)
    return seq


def polyline_resample(pts, n=24):
    pts = np.array(pts, float)
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
    if seg[-1] < 1e-6:
        return np.repeat(pts[:1], n, 0)
    s = np.linspace(0, seg[-1], n)
    return np.c_[np.interp(s, seg, pts[:, 0]), np.interp(s, seg, pts[:, 1])]


def chamfer(a, b):
    A, B = polyline_resample(a), polyline_resample(b)
    d = np.hypot(*(A[:, None, :] - B[None, :, :]).transpose(2, 0, 1))
    return float((d.min(1).mean() + d.min(0).mean()) / 2)


def best_library(L, combo, roles, pass_lines, lib_cache={}):
    """Library moves ranked by distance to this draft. Candidates: moves whose last two touch roles equal the draft's (a
    one-touch draft: moves with the same last role). Distance (mm) = mean blade-to-blade distance of the touching figures
    at the set-up + 0.5 x mean chamfer distance between the pass paths (the shot arrow is left out: its aim is assumed)."""
    if L is None or not roles:
        return None
    if "roles" not in lib_cache:
        lib_cache["roles"] = {m["id"]: library_roles(m) for m in L["moves"]}
    mine = {r: blade_world(f"W-{r}", combo["figures"][f"W-{r}"]["arc_mm"], combo["figures"][f"W-{r}"]["theta_deg"]) for r in set(roles)}
    cands = []
    for m in L["moves"]:
        lr = lib_cache["roles"][m["id"]]
        k = min(2, len(roles))
        if len(lr) < k or lr[-k:] != roles[-k:]:
            continue
        bl = [math.dist(mine[r], blade_world(f"W-{r}", m["figures"][f"W-{r}"]["arc_mm"], m["figures"][f"W-{r}"]["theta_deg"])) for r in roles[-k:]]
        arrows = [a["points_mm"] for a in m["arrows"][:-1] if len(a["points_mm"]) >= 2]
        if LIB_DISTANCE == "pass_path":
            # the last pass only (passer to receiver) against the library's pass arrow that ends nearest the receiver's blade
            d = float(min(chamfer(pass_lines[-1], a) for a in arrows)) if arrows and pass_lines else 1e3
        else:
            ch = float(np.mean([min(chamfer(p, a) for a in arrows) for p in pass_lines])) if arrows and pass_lines else 0.0
            d = float(np.mean(bl) + 0.5 * ch)
        cands.append((d, m["id"], m["name"], lr))
    cands.sort()
    return cands[:5] if cands else None


# ---------------------------------------------------------------- build the combo


def aim_point(G, S, t, scorer_pt):
    """Goal-mouth corner away from the goalie, in the attacker frame (assumed; the shot is not visible)."""
    gk = f"{'E' if S == 'W' else 'W'}-G"
    a, th, ok, _ = G.pose_at(gk, t, 1.0)
    gy = None
    if ok:
        gy = T.slot_point(gk, a / T.SLOT_LEN[gk])[1]
        if S == "E":
            gy = -gy
    off = GOAL_E["mouth"] / 2 - 9.0
    y = GOAL_E["y"] + (off if (gy is None or gy < GOAL_E["y"]) else -off)
    return [GOAL_E["x"] - 4.0, y], gy


def to_attacker(S, p):
    return flip_pt(p) if S == "E" else list(p)


def r1(v):
    return round(float(v), 1)


def build_combo(G, game, t_end, S, flights, info, evs, name, defaults):
    notes = list(info.get("notes", []))
    flights = list(flights)
    if flights:
        touches = [flights[0]["from"]] + [e["to"] for e in flights]
        t_first = flights[0]["t_release_s"]
        start_pt = flights[0]["line_mm"][0]
        last_pt = flights[-1]["line_mm"][-1]
        t_last = flights[-1]["t_reception_s"]
    else:
        holder = info.get("shot_from") or info.get("carrier")
        cand = [e for e in evs if e["from"][0] == S and e["t_release_s"] <= t_end + 0.35 and (holder is None or e["from"] == holder)]
        if cand:
            c = cand[-1]
            touches = [c["from"]]; t_first = c["t_release_s"]; start_pt = c["line_mm"][0]
            t_last = c["t_reception_s"]; last_pt = c["line_mm"][-1]
        else:
            touches, t_first, start_pt, t_last, last_pt = [], t_end - 1.0, None, t_end - 1.0, None
    # the last visible holder is a winger and the puck then vanishes: the playbook's centre shoots (inferred pass)
    inferred = None
    if OPTS["unseen_pass"] and touches and role(touches[-1]) in ("LW", "RW") and not info.get("shot_seen") and last_pt is not None:
        cpid = f"{S}-C"
        a_, th_, ok_, _ = G.pose_at(cpid, min(t_last + 0.3, t_end), 0.5)
        if ok_:
            wc = blade_world(cpid, a_, th_)
            inferred = {"from": touches[-1], "to": cpid, "line_mm": [list(last_pt), wc], "kind": "pass(inferred)", "t_release_s": t_last, "t_reception_s": min(t_last + 0.3, t_end)}
            flights.append(inferred); touches.append(cpid); last_pt = wc; t_last = inferred["t_reception_s"]
            notes.append(f"{inferred['from']} > {cpid}: pass not visible in the track; inferred (a winger's last touch, then the centre shoots)")
    # figure poses at t_first
    figures, tracked, pose_dt = {}, 0, []
    for pid in T.SKATERS + T.GOALIES:
        a, th, ok, dt = G.pose_at(pid, t_first)
        wpid = flip_pid(pid) if S == "E" else pid
        if ok:
            if S == "E":
                # E's slots are the W slots turned 180 degrees, but with the arc running the other way: re-measure the
                # turned pivot on the W slot (theta, relative to the home heading, is unchanged by a half turn)
                piv = -T.slot_point(pid, a / T.SLOT_LEN[pid])
                _, uw = T.nearest_on_slot(T.SLOT[wpid], piv)
                a = uw * T.SLOT_LEN[wpid]
            a = min(max(a, 0.6), T.SLOT_LEN[wpid] - 0.6)  # the editor keeps a figure half a millimetre off the slot ends
            figures[wpid] = {"arc_mm": r1(a), "theta_deg": r1(((th + 180) % 360) - 180)}
            tracked += 1
            pose_dt.append(abs(dt))
        else:
            d = defaults.get(wpid, {"arc_mm": T.SLOT_LEN[pid] / 2, "theta_deg": 0.0})
            figures[wpid] = {"arc_mm": r1(d["arc_mm"]), "theta_deg": r1(d["theta_deg"])}
            notes.append(f"{wpid}: no tracked pose within 1 s of the first touch; default pose")
    arrows, markers = [], []
    n = 0
    puck0 = to_attacker(S, start_pt) if start_pt else [0.0, 0.0]

    def mk(pt, label):
        markers.append({"id": f"m{len(markers) + 1}", "label": label, "x_mm": r1(pt[0]), "y_mm": r1(pt[1]), "color": "#0e2a57"})

    if start_pt:
        mk(puck0, "1")
    for i, e in enumerate(flights):
        pts = [to_attacker(S, p) for p in e["line_mm"]]
        # keep it light: first, the corner points, last
        pts = [[r1(c) for c in p] for p in pts]
        arrows.append({"id": f"a{i + 1}", "points_mm": pts, "style": "dashed" if e.get("kind") == "pass(inferred)" else "solid", "curved": False, "color": "#16be34", "width_mm": 4.2, "head": True})
        mk(pts[-1], str(i + 2))
    shot_from = to_attacker(S, last_pt) if last_pt is not None else puck0
    aim, gy = aim_point(G, S, t_last, shot_from)
    if start_pt or flights:
        arrows.append({"id": f"a{len(flights) + 1}", "points_mm": [[r1(shot_from[0]), r1(shot_from[1])], [r1(aim[0]), r1(aim[1])]], "style": "solid", "curved": False, "color": "#16be34", "width_mm": 4.2, "head": True})
    roles = [role(t) for t in touches]
    fam = family_from_roles(roles, rebound_hint(evs, S, t_end) and bool(roles))
    combo = {
        "schema": SCHEMA, "name": name, "description": f"Draft from clip {game} ending {t_end:.1f} s: {' > '.join(roles) or 'no touches found'} (shot aim assumed).",
        "figures": figures, "puck": {"x_mm": r1(puck0[0]), "y_mm": r1(puck0[1])}, "arrows": arrows, "markers": markers,
    }
    meta = {"status": "PROPOSED", "source": "NM26 committed tracks (puck-track-synth-v2, figure-tracks-v3, passes-synth-v1); docs/clip2combo.md", "game": game, "clip_end_s": t_end, "scoring_end": S, "touches": [flip_pid(t) if S == "E" else t for t in touches], "roles": roles,
            "family": fam, "scorer_source": info.get("scorer_source"), "inferred_pass": bool(inferred), "shot_seen": info.get("shot_seen"), "t_first_touch_s": t_first, "figures_tracked": tracked, "pose_dt_max_s": max(pose_dt) if pose_dt else None,
            "pass_lines_attacker_frame": [[[r1(c) for c in p] for p in a["points_mm"]] for a in arrows[:-1]], "notes": notes, "goalie_y_attacker_frame": gy}
    return combo, meta


def clip_to_combo(game, t_end, S=None, name=None, G_cache={}):
    if game not in G_cache:
        G_cache[game] = Game(game)
    G = G_cache[game]
    L = lib()
    defaults = (L or {}).get("default_figures", {})
    inferred, npts = infer_scoring_end(G, t_end)
    end = S or inferred
    if end is None:
        raise ValueError("no puck track near the clip end")
    evs, flights, carrier = segment(G, t_end, end)
    combo, meta = build_combo(G, game, t_end, end, flights, carrier, evs, name or f"Draft {game} {t_end:.0f}s", defaults)
    meta["scoring_end_inferred"] = inferred
    seen = G.puck_near_end(t_end, 6.0)
    meta["puck_seen_fraction_last_6s"] = round(len(seen) / (6.3 * FPS), 3)
    meta["library_candidates"] = best_library(L, combo, meta["roles"], [[tuple(p) for p in pl] for pl in meta["pass_lines_attacker_frame"]]) if meta["roles"] else None
    combo["clip2combo"] = meta
    return combo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game", nargs="?")
    ap.add_argument("t_end", nargs="?", type=float)
    ap.add_argument("--goal")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--auto-end", action="store_true", help="use the pipeline's own goal-moment estimate instead of the user's mark")
    ap.add_argument("--off", default="", help="comma list of OPTS switches to turn off (the ablation)")
    ap.add_argument("--out")
    ap.add_argument("--outdir")
    a = ap.parse_args()
    for k in filter(None, a.off.split(",")):
        OPTS[k] = False
    labels = {r["id"]: r for r in json.loads((D / "goal-labels.json").read_text())["labels"]}
    est = {g["id"]: g["goal_moment_estimate_s"] for g in json.loads((D / "combo-labels.json").read_text())["goals"]}
    jobs = []
    if a.all:
        jobs = [(gid, r["game"], est[gid] if a.auto_end else r["goal_video_s"]) for gid, r in labels.items()]
    elif a.goal:
        r = labels[a.goal]
        jobs = [(a.goal, r["game"], est[a.goal] if a.auto_end else r["goal_video_s"])]
    else:
        jobs = [(f"{a.game}-{a.t_end:.1f}", a.game, a.t_end)]
    for gid, game, t in jobs:
        c = clip_to_combo(game, t, name=f"Draft {gid}")
        txt = json.dumps(c, indent=1)
        if a.outdir:
            Path(a.outdir).mkdir(parents=True, exist_ok=True)
            (Path(a.outdir) / f"{gid}.json").write_text(txt + "\n")
        elif a.out:
            Path(a.out).write_text(txt + "\n")
        m = c["clip2combo"]
        print(f"{gid}: end {m['scoring_end']} touches {' > '.join(m['roles']) or '-'} family {m['family']}", flush=True)


if __name__ == "__main__":
    main()
