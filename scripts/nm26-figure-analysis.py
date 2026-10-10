"""First analysis of the NM26 figure tracks (all seven games): tracking quality, puck touches, goal setups.

    python3 scripts/nm26-figure-analysis.py

Inputs: data/games/nm26-semifinal/<g>/figure-tracks.json (raw v2 model readings, scripts/synth/track-figures.py, PROPOSED)
for the quality figures and the hat-trick windows; the selected figure tracks (scripts/nm26_tracks.py: figure-tracks-v3.json,
or $NM26_FIGURE_TRACKS) for the touches and goal setups; the selected puck tracks (puck-track-synth.json, or
$NM26_PUCK_TRACK; PROPOSED), the user's goal labels (goal-labels.json) and config.json (team_W per game).
- Quality (raw v2 readings): slot_dist_mm (how far the model's pivot lies from the slot), and in the 30 fps goal windows
  the share of frame-to-frame steps over 30 mm (slot) or over 60 degrees (rotation): jumps, not motion.
- Touches: a skater touches the puck when the puck centre (a slow detection in the same frame; scripts/nm26_tracks.py) lies within 25 mm of
  its blade contact point, the mold-frame point (12, 33) mm (mid blade, where a pass is received; as in
  scripts/defence-trace.py; +x = facing, +y = the figure's left) rotated by the tracked heading. Goalies are left out.
  Only the evenly sampled (5 fps) frames with a disk detection count. Status: PROPOSED; thresholds assumed.
  Figures unknown in that frame (null u) are left out.
- Goal setups: each labelled goal's scoring team's pose 0.5 s before the goal moment (nearest tracked frame; null when
  the figure is unknown there).
Writes data/games/nm26-semifinal/figure-analysis.json and data/games/nm26-semifinal/rebuild/<goal>-figures.json for
the Edwall hat-trick (g2-goal2..4: every tracked frame of the 9 s goal window, all figures, raw v2 readings).
"""
import json, math, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[1]; D = REPO / "data/games/nm26-semifinal"
sys.path.insert(0, str(REPO / "scripts"))
from nm26_tracks import FIGURE_TRACKS, PUCK_TRACK, load_figures, load_puck  # noqa: E402
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
CFG = json.loads((D / "config.json").read_text())
HOME = {"W": 0.0, "E": 180.0}; SKATERS = ["W-LW", "E-LW", "W-RW", "E-RW", "W-C", "E-C", "W-LD", "E-LD", "W-RD", "E-RD"]
BLADE = np.array([12.0, 33.0]); TOUCH_MM = 25.0
ACC = {p: np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))] for p, P in SLOT.items()}
labels = {r["id"]: r for r in json.loads((D / "goal-labels.json").read_text())["labels"]}


def pivots(pid, u):
    P, acc = SLOT[pid], ACC[pid]; s = np.asarray(u) * acc[-1]
    return np.c_[np.interp(s, acc, P[:, 0]), np.interp(s, acc, P[:, 1])]


def blade(pid, u, th):
    a = np.radians(HOME[pid[0]] + np.asarray(th)); c, s = np.cos(a), np.sin(a)
    return pivots(pid, u) + np.c_[c * BLADE[0] - s * BLADE[1], s * BLADE[0] + c * BLADE[1]]


def player_of(game, pid):
    w = CFG["games"][game].get("team_W") or CFG["games"][game].get("left_end_player")
    other = {"nygard": "fjermestad", "fjermestad": "nygard"}
    return w if pid[0] == "W" else other.get(w, "?")


out = {"description": __doc__.split("\n\n")[1].strip(), "figure_tracks": FIGURE_TRACKS, "puck_track": PUCK_TRACK, "games": {}, "touches_by_player_role": {}, "goal_setups": []}
by_player = defaultdict(Counter)
for g in [f"g{k}" for k in range(1, 8)]:
    T = json.loads((D / g / "figure-tracks.json").read_text()); C = T["columns"]; R = np.array(T["rows"], float); ci = {c: i for i, c in enumerate(C)}
    frame = R[:, 0].astype(int); dense = R[:, 1] > 0
    sd = R[:, [ci[f"{p}_slot_dist_mm"] for p in SKATERS]]
    q = {"frames": int(len(R)), "slot_dist_mm_median": round(float(np.median(sd)), 1), "slot_dist_mm_p90": round(float(np.percentile(sd, 90)), 1),
         "doubtful_share_over_15mm": round(float(np.mean(sd > 15)), 4)}
    # jumps in the dense (30 fps) windows: consecutive frames only
    dj, dt, n = 0, 0, 0
    idx = np.where(dense[1:] & dense[:-1] & (np.diff(frame) == 1))[0]
    for p in SKATERS + ["W-G", "E-G"]:
        u = R[:, ci[f"{p}_u"]] * ACC[p][-1]; th = R[:, ci[f"{p}_theta_deg"]]
        du = np.abs(np.diff(u))[idx]; dth = np.abs((np.diff(th) + 180) % 360 - 180)[idx]
        dj += int((du > 30).sum()); dt += int((dth > 60).sum()); n += len(idx)
    q["dense_steps"] = n; q["slot_jump_share"] = round(dj / max(n, 1), 4); q["rotation_jump_share"] = round(dt / max(n, 1), 4)
    # touches (selected tracks; R, frame, dense, ci are rebound to them)
    raw_T, raw_C = T, C
    T = load_figures(g); C = T["columns"]; ci = {c: i for i, c in enumerate(C)}
    R = np.array([[np.nan if v is None else v for v in r] for r in T["rows"]], float); frame = R[:, 0].astype(int); dense = R[:, 1] > 0
    idx = np.where(dense[1:] & dense[:-1] & (np.diff(frame) == 1))[0]; dj = dt = n = 0
    for p in SKATERS + ["W-G", "E-G"]:
        u = R[:, ci[f"{p}_u"]] * ACC[p][-1]; th = R[:, ci[f"{p}_theta_deg"]]; ok = ~np.isnan(u[1:]) & ~np.isnan(u[:-1])
        du = np.abs(np.diff(u))[idx][ok[idx]]; dth = np.abs((np.diff(th) + 180) % 360 - 180)[idx][ok[idx]]
        dj += int((du > 30).sum()); dt += int((dth > 60).sum()); n += len(du)
    src = R[:, [ci[f"{p}_src"] for p in SKATERS]]
    q["selected_tracks"] = {"file": FIGURE_TRACKS, "dense_steps": n, "slot_jump_share": round(dj / max(n, 1), 4), "rotation_jump_share": round(dt / max(n, 1), 4),
                            "interpolated_share": round(float(np.mean(src == 1)), 4), "unknown_share": round(float(np.mean(src == 2)), 4)}
    P = load_puck(g); pc = P["columns"]
    puck = {int(r[pc.index("frame")]): (r[pc.index("x_mm")], r[pc.index("y_mm")]) for r, slow in zip(P["rows"], P["slow"]) if slow and r[pc.index("x_mm")] is not None}
    rows = [k for k, f in enumerate(frame) if f in puck and not dense[k]]  # even 5 fps sampling (goal windows would weigh more)
    pk = np.array([puck[frame[k]] for k in rows]) if rows else np.zeros((0, 2))
    dist = np.stack([np.linalg.norm(blade(p, R[rows, ci[f"{p}_u"]], R[rows, ci[f"{p}_theta_deg"]]) - pk, axis=1) for p in SKATERS], 1) if rows else np.zeros((0, 10))
    dist = np.where(np.isnan(dist), np.inf, dist)
    best = dist.argmin(1) if rows else np.array([], int); touched = dist.min(1) < TOUCH_MM if rows else np.array([], bool)
    cnt = Counter(SKATERS[b] for b, t in zip(best, touched) if t)
    q["puck_frames"] = len(rows); q["touch_share"] = round(float(touched.mean()), 3) if rows else None
    q["touches_by_figure"] = dict(sorted(cnt.items()))
    for p, c in cnt.items(): by_player[player_of(g, p)][p.split("-")[1]] += c
    out["games"][g] = q
    # goal setups
    for k in range(1, 12):
        lab = labels.get(f"{g}-goal{k}")
        if not lab or lab.get("goal_video_s") is None: continue
        f0 = int(round((lab["goal_video_s"] - 0.5) * 30)); j = int(np.argmin(np.abs(frame - f0))); end = lab["scoring_end"]
        rnd = lambda v, n: None if np.isnan(v) else round(float(v), n)
        pose = {p: {"u": rnd(R[j, ci[f"{p}_u"]], 3), "theta_deg": rnd(R[j, ci[f"{p}_theta_deg"]], 1)} for p in SKATERS if p[0] == end}
        opp = "E" if end == "W" else "W"
        out["goal_setups"].append({"id": lab["id"], "family": lab.get("family"), "combination": lab.get("combination"), "scorer": lab.get("scorer"),
                                   "assist": lab.get("assist"), "frame": int(frame[j]), "frame_offset": int(frame[j] - f0), "scoring_team": pose,
                                   "defending_goalie": {"u": rnd(R[j, ci[f"{opp}-G_u"]], 3), "theta_deg": rnd(R[j, ci[f"{opp}-G_theta_deg"]], 1)}})
    if g == "g2":
        raw_frame = [r[0] for r in raw_T["rows"]]
        for gid in ("g2-goal2", "g2-goal3", "g2-goal4"):
            lab = labels[gid]; t0 = lab["goal_video_s"] - 8; t1 = lab["goal_video_s"] + 1
            sel = [k for k, f in enumerate(raw_frame) if t0 <= f / 30 <= t1]
            (D / "rebuild" / f"{gid}-figures.json").write_text(json.dumps({"description": f"Figure tracks (model output, PROPOSED) for {gid}, "
                f"every tracked frame from 8 s before to 1 s after the user's goal moment ({lab['goal_video_s']} s). Columns as "
                "figure-tracks.json.", "columns": raw_C, "rows": [raw_T["rows"][k] for k in sel]}, separators=(",", ":")) + "\n")
# where the scoring centre stands 0.5 s before its goals: distance from the goal-side (front) end of its slot
cs = []
for x in out["goal_setups"]:
    if x["scorer"] != "C": continue
    lab = labels[x["id"]]; end = lab["scoring_end"]; c = x["scoring_team"][f"{end}-C"]
    front = (1 - c["u"]) if end == "W" else c["u"]  # W attacks +x (u = 1 at the front), E attacks -x (u = 0 at the front)
    if c["u"] is None: front = None
    cs.append({"id": x["id"], "player": lab["scoring_player"], "family": lab.get("family"), "combination": lab.get("combination"),
               "centre_from_front_mm": None if front is None else round(front * ACC[f"{end}-C"][-1]), "centre_theta_deg": c["theta_deg"]})
out["centre_shot_position"] = cs
tot = {pl: sum(c.values()) for pl, c in by_player.items()}
out["touches_by_player_role"] = {pl: {r: {"touches": n, "share": round(n / tot[pl], 3)} for r, n in sorted(c.items(), key=lambda x: -x[1])} for pl, c in by_player.items()}
(D / "figure-analysis.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
for g, q in out["games"].items(): print(g, {k: v for k, v in q.items() if k != "touches_by_figure"})
print(json.dumps(out["touches_by_player_role"], indent=0))
