"""Score NM26 puck tracks on the measures of the shot workstream (docs/synthetic-puck.md section 8). Python 3 + NumPy.

    python3 scripts/synth/puck-track-eval.py [<track file> <passes file>] ... [--json out.json]

Default: the v1 track (puck-track-synth.json + passes.json) and the v2 track (puck-track-synth-v2.json +
passes-synth-v2.json). Per track:
- shots: user-marked goals (goal-labels.json, 25 with a goal moment) with a shot event released in the last 2 s before
  the goal moment (or up to 0.2 s after), the rule of scripts/nm26-track-switch-compare.py; and shot events in all;
- taps (validation/tap-review: Amund's answers, 2026-10-10), puck items only, scored as scripts/nm26-tap-review.py eval
  does (tap moved up 8.8 px, right within 15 mm on the 12 mm plane; "none" makes any reported puck wrong): right of 63,
  false alarms on the "not in this picture" answers, misses of a puck the user tapped, median error where both exist;
- coverage: share of live-play frames with a position, and of the last 2 s before the 25 goals.
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
D = REPO / "data/games/nm26-semifinal"
TL = json.loads((D / "timeline.json").read_text())["games"]
LABS = [x for x in json.loads((D / "goal-labels.json").read_text())["labels"] if x.get("goal_video_s")]
CAM = json.loads((D / "camera-ref.json").read_text())
CFG = json.loads((D / "config.json").read_text())
K, R, T = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
X0, Y0 = CFG["roi_px"][:2]
GAMES = [f"g{k}" for k in range(1, 8)]
TAP = REPO / "validation/tap-review"
PUCK_Z, PUCK_OK_MM, TAP_TO_TOP_PX = 12.0, 15.0, 8.8


def from_stab(q, z):
    H = K @ np.c_[R[:, 0], R[:, 1], R[:, 2] * z + T]
    q = np.atleast_2d(np.asarray(q, float)) + [X0, Y0]
    w = np.c_[q, np.ones(len(q))] @ np.linalg.inv(H).T
    return w[:, :2] / w[:, 2:]


def live(g, t):
    return any(a <= t < b for a, b in TL[g]["live_play_s"])


def score(track, passes):
    rows = {g: {r[0]: r for r in json.loads((D / g / track).read_text())["rows"]} for g in GAMES}
    ev = {g: json.loads((D / g / passes).read_text())["events"] for g in GAMES}
    shots = [x["id"] for x in LABS if any(e["kind"] == "shot" and x["goal_video_s"] - 2.0 <= e["t_release_s"] <= x["goal_video_s"] + 0.2
                                          for e in ev[x["game"]])]
    n_shots = {g: sum(1 for e in ev[g] if e["kind"] == "shot") for g in GAMES}
    items = {it["id"]: it for it in json.loads((TAP / "items.json").read_text())["items"]}
    taps = json.loads((TAP / "taps.json").read_text())
    taps = taps.get("taps", taps) if isinstance(taps, dict) else taps
    right = n = fa = n_none = miss = 0; err = []
    per = []
    for tp in taps:
        it = items.get(tp["item"])
        if not it or it["kind"] != "puck" or tp.get("answer") == "unsure":
            continue
        n += 1
        r = rows[it["game"]].get(it["frame"])
        if tp["answer"] == "tap":
            w = from_stab([tp["x_stab"], tp["y_stab"] - TAP_TO_TOP_PX], PUCK_Z)[0]
            if r is None:
                miss += 1; per.append([it["id"], "missing"]); continue
            d = float(np.linalg.norm(from_stab([r[4], r[5]], PUCK_Z)[0] - w)); err.append(d)
            ok = d <= PUCK_OK_MM; right += ok; per.append([it["id"], "right" if ok else "wrong", round(d, 1)])
        else:
            n_none += 1
            if r is None:
                right += 1; per.append([it["id"], "missing_ok"])
            else:
                fa += 1; per.append([it["id"], "false_alarm"])
    live_n = live_seen = 0
    for g in GAMES:
        f0, f1 = (int(round(v * 30)) for v in CFG["games"][g]["video_window_s"])
        for f in range(f0, f1):
            if live(g, f / 30):
                live_n += 1; live_seen += f in rows[g]
    gw_n = gw_seen = 0
    for x in LABS:
        fg = int(round(x["goal_video_s"] * 30))
        for f in range(fg - 60, fg + 1):
            gw_n += 1; gw_seen += f in rows[x["game"]]
    return {
        "track": track, "passes": passes,
        "user_goals_with_a_shot_in_the_last_2s": f"{len(shots)}/{len(LABS)}", "goals_with_a_shot": shots,
        "shot_events": sum(n_shots.values()), "shot_events_by_game": n_shots,
        "taps": {"puck_items": n, "right": right, "false_alarms_on_none": f"{fa}/{n_none}", "missed_a_tapped_puck": miss,
                 "median_error_mm": round(float(np.median(err)), 1) if err else None, "within_25_mm": f"{sum(e <= 25 for e in err)}/{len(err)}",
                 "items": per},
        "coverage_live_play": round(live_seen / live_n, 3), "coverage_last_2s_before_goals": round(gw_seen / gw_n, 3),
    }


if __name__ == "__main__":
    a = sys.argv[1:]
    out = None
    if "--json" in a:
        k = a.index("--json"); out = a[k + 1]; a = a[:k] + a[k + 2:]
    pairs = list(zip(a[::2], a[1::2])) or [("puck-track-synth.json", "passes.json"), ("puck-track-synth-v2.json", "passes-synth-v2.json")]
    res = [score(t, p) for t, p in pairs if all((D / g / t).exists() and (D / g / p).exists() for g in GAMES)]
    for r in res:
        print(r["track"], r["user_goals_with_a_shot_in_the_last_2s"], "shots", r["shot_events"],
              {k: v for k, v in r["taps"].items() if k != "items"}, "coverage", r["coverage_live_play"], r["coverage_last_2s_before_goals"])
    if out:
        Path(out).write_text(json.dumps({"description": __doc__.split("\n\n")[0], "results": res}, indent=1) + "\n")
