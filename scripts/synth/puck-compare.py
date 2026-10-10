"""Compare the synthetic-detector puck track with the current one (docs/synthetic-puck.md).

    /root/venvs/blender/bin/python scripts/synth/puck-compare.py [--model-file puck-track-synth.json]

Per game, live play only (timeline.json live_play_s): coverage (frames with a position), agreement where both tracks
have one, physically impossible steps, and the windows that matter for passes and shots:
- goal windows: the last 2 s and the last 0.5 s before each goal the user marked (goal-labels.json, 25 goals: the
  moment the puck crosses the line), and the 12 s before the score-box change for the others (timeline.json);
- shot reach: does the track put the puck at the mouth of the conceding goal (from 30 mm in front of the goal line to
  the back of the cage, within the posts plus the puck radius; goal placement validation/12-hardware-report.json)
  between 1.0 s before and 0.5 s after the user's goal moment;
- flights: the passes and shots of the current pipeline (passes.json; they come from the current track, so this
  favours it) and fast intervals of the new track.
Positions are compared in one convention: the current track's blob centre (stab px) moved to the top-face centre
(out/synth/puck/blob-offset.json) and mapped through the reference camera onto the plane 12 mm above the ice, as
track-puck.py does.
Writes data/games/nm26-semifinal/puck-synth-compare.json.
"""
import json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
D = REPO / "data/games/nm26-semifinal"
A = sys.argv[1:]
def arg(n, d): return A[A.index(n) + 1] if n in A else d
NEW = arg("--model-file", "puck-track-synth.json")
CFG = json.loads((D / "config.json").read_text()); TL = json.loads((D / "timeline.json").read_text())["games"]
LAB = json.loads((D / "goal-labels.json").read_text())["labels"]
HW = json.loads((REPO / "validation/12-hardware-report.json").read_text())["goal"]
X0, Y0 = CFG["roi_px"][:2]
CAM = json.loads((D / "camera-ref.json").read_text())
Kc, Rc, tc = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
H_TOP = np.array([[1, 0, -X0], [0, 1, -Y0], [0, 0, 1.0]]) @ Kc @ np.c_[Rc[:, 0], Rc[:, 1], Rc[:, 2] * 12.0 + tc]
HI = np.linalg.inv(H_TOP)
OFF = np.array(json.loads((REPO / "out/synth/puck/blob-offset.json").read_text())["mean_px"]) if (REPO / "out/synth/puck/blob-offset.json").exists() else np.array([0.15, -8.81])
FPS = 30


def to_world(uv):
    q = np.c_[uv, np.ones(len(uv))] @ HI.T; return q[:, :2] / q[:, 2:]


def load_track(g, name, old):
    p = D / g / name
    if not p.exists(): return None
    rows = json.loads(p.read_text())["rows"]
    uv = np.array([[r[4], r[5]] for r in rows], float)
    if old: uv = uv + OFF
    W = to_world(uv) if len(uv) else np.zeros((0, 2))
    return {r[0]: (W[k], r[6]) for k, r in enumerate(rows)}


def mouth(end, p):
    gx, gy = HW["placement_mm"][end]; half = HW["mouth_width_per_goal_mm"][end] / 2 + 12.7; depth = HW["depth_per_goal_mm"][end]
    s = -1 if end == "W" else 1  # behind the goal line = further toward the end
    along = (p[0] - gx) * s
    return -30 <= along <= depth and abs(p[1] - gy) <= half


def cov(tr, fr):
    return round(float(np.mean([f in tr for f in fr])), 3) if len(fr) else None


def steps(tr, fr):
    """Steps between consecutive frames faster than 7 m/s (impossible for a sliding puck)."""
    n = bad = 0
    for f in fr:
        if f in tr and f + 1 in tr:
            n += 1; bad += np.hypot(*(tr[f + 1][0] - tr[f][0])) * FPS > 7000
    return round(bad / max(n, 1), 4)


out = {"description": __doc__.split("\n\n")[0], "new_file": NEW, "games": {}, "goals": []}
tot = {}
for g in CFG["games"]:
    old, new = load_track(g, "puck-track.json", True), load_track(g, NEW, False)
    if new is None: print(g, "no new track"); continue
    live = [f for a, b in TL[g]["live_play_s"] for f in range(int(round(a * FPS)), int(round(b * FPS)))]
    both = [f for f in live if f in old and f in new]
    d = np.array([np.hypot(*(old[f][0] - new[f][0])) for f in both]) if both else np.zeros(0)
    st = {"live_frames": len(live), "coverage_old": cov(old, live), "coverage_new": cov(new, live),
          "both": len(both), "agree_median_mm": round(float(np.median(d)), 1) if len(d) else None,
          "agree_within_15mm": round(float((d <= 15).mean()), 3) if len(d) else None,
          "disagree_over_50mm": round(float((d > 50).mean()), 3) if len(d) else None,
          "only_old": round(float(np.mean([(f in old) and (f not in new) for f in live])), 3),
          "only_new": round(float(np.mean([(f in new) and (f not in old) for f in live])), 3),
          "impossible_steps_old": steps(old, live), "impossible_steps_new": steps(new, live)}
    # flights of the current pipeline
    ev = json.loads((D / g / "passes.json").read_text())["events"]
    for kind in ("pass", "shot"):
        fr = [f for e in ev if e["kind"] == kind for f in range(e["frame_release"], e["frame_reception"] + 1)]
        st[f"{kind}_frames"] = len(fr); st[f"{kind}_coverage_old"] = cov(old, fr); st[f"{kind}_coverage_new"] = cov(new, fr)
    # fast intervals of the new track (speed over 500 mm/s between consecutive detections)
    fast = [f for f in live if f in new and f + 1 in new and np.hypot(*(new[f + 1][0] - new[f][0])) * FPS > 500]
    st["new_fast_frames"] = len(fast); st["new_fast_coverage_old"] = cov(old, fast)
    # goal windows
    gl = [l for l in LAB if l["game"] == g]
    marked = [l["goal_video_s"] for l in gl]
    win2, win05 = [], []
    for l in gl:
        t = l["goal_video_s"]; f = int(round(t * FPS))
        w2 = list(range(f - 60, f + 1)); w05 = list(range(f - 15, f + 1)); win2 += w2; win05 += w05
        conc = "E" if l["scoring_end"] == "W" else "W"
        reach = {}
        for nm, tr in (("old", old), ("new", new)):
            hit = [k for k in range(f - 30, f + 16) if k in tr and mouth(conc, tr[k][0])]
            gx, gy = HW["placement_mm"][conc]
            dist = [np.hypot(tr[k][0][0] - gx, tr[k][0][1] - gy) for k in range(f - 30, f + 16) if k in tr]
            seen = [k for k in range(f - 30, f + 1) if k in tr]
            reach[nm] = {"last_seen_before_goal_s": round((seen[-1] - f) / FPS, 3) if seen else None,
                         "goal_dist_at_last_seen_mm": round(float(np.hypot(tr[seen[-1]][0][0] - gx, tr[seen[-1]][0][1] - gy)), 1) if seen else None,
                         "at_mouth": bool(hit), "first_at_mouth_s": round((hit[0] - f) / FPS, 3) if hit else None,
                         "closest_to_goal_mm": round(float(min(dist)), 1) if dist else None,
                         "coverage_last_2s": cov(tr, w2), "coverage_last_0_5s": cov(tr, w05)}
        out["goals"].append({"id": l["id"], "combination": l["combination"], "family": l["family"], "conceding_end": conc, **reach})
    st["user_goals"] = len(gl)
    st["goal_last2s_coverage_old"], st["goal_last2s_coverage_new"] = cov(old, win2), cov(new, win2)
    st["goal_last0.5s_coverage_old"], st["goal_last0.5s_coverage_new"] = cov(old, win05), cov(new, win05)
    box = [f for gg in TL[g]["goals"] if not any(abs(gg["overlay_change_s"] - m) < 15 for m in marked)
           for f in range(int((gg["overlay_change_s"] - 12) * FPS), int(gg["overlay_change_s"] * FPS))]
    st["other_goal_windows_frames"] = len(box); st["other_goal_windows_coverage_old"] = cov(old, box); st["other_goal_windows_coverage_new"] = cov(new, box)
    out["games"][g] = st
    print(g, st)
G = out["goals"]
out["summary"] = {
    "user_goals": len(G),
    "at_mouth_old": sum(x["old"]["at_mouth"] for x in G), "at_mouth_new": sum(x["new"]["at_mouth"] for x in G),
    "seen_in_last_0.2s_old": sum((x["old"]["last_seen_before_goal_s"] or -9) >= -0.2 for x in G),
    "seen_in_last_0.2s_new": sum((x["new"]["last_seen_before_goal_s"] or -9) >= -0.2 for x in G),
    "median_goal_dist_at_last_seen_old_mm": float(np.median([x["old"]["goal_dist_at_last_seen_mm"] for x in G if x["old"]["goal_dist_at_last_seen_mm"] is not None])) if G else None,
    "median_goal_dist_at_last_seen_new_mm": float(np.median([x["new"]["goal_dist_at_last_seen_mm"] for x in G if x["new"]["goal_dist_at_last_seen_mm"] is not None])) if G else None,
    "goal_last2s_coverage_old": round(float(np.mean([x["old"]["coverage_last_2s"] for x in G])), 3) if G else None,
    "goal_last2s_coverage_new": round(float(np.mean([x["new"]["coverage_last_2s"] for x in G])), 3) if G else None,
    "goal_last0.5s_coverage_old": round(float(np.mean([x["old"]["coverage_last_0_5s"] for x in G])), 3) if G else None,
    "goal_last0.5s_coverage_new": round(float(np.mean([x["new"]["coverage_last_0_5s"] for x in G])), 3) if G else None,
}
for k in ("coverage_old", "coverage_new", "pass_coverage_old", "pass_coverage_new", "shot_coverage_old", "shot_coverage_new",
          "impossible_steps_old", "impossible_steps_new", "agree_within_15mm", "new_fast_coverage_old"):
    v = [(s[k], s["live_frames"]) for s in out["games"].values() if s.get(k) is not None]
    if v: out["summary"][k] = round(sum(a * b for a, b in v) / sum(b for _, b in v), 3)
print(out["summary"])
(D / "puck-synth-compare.json").write_text(json.dumps(out, indent=1) + "\n")
