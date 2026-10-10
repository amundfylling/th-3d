"""Before/after numbers for the NM26 track switch (docs/nm26-new-tracks.md).

    python3 scripts/nm26-track-switch-compare.py [--base <git rev>]

Before = the outputs at --base (default ee0681d, the consolidation branch head built on puck-track.json and the v2
figure tracks); after = the outputs in the working tree (puck-track-synth.json, figure-tracks-v3.json). Compares
passes, patterns, figure analysis, combination labels and the replays' coverage. Writes validation/nm26-track-switch.json.
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
D = "data/games/nm26-semifinal"
BASE = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "ee0681d"
GAMES = [f"g{k}" for k in range(1, 8)]


def before(path):
    r = subprocess.run(["git", "show", f"{BASE}:{path}"], cwd=REPO, capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else None


def after(path):
    p = REPO / path
    return json.loads(p.read_text()) if p.exists() else None


def match_passes(a, b, tol=6):
    """Share of a's passes (kind pass) that b has too: same from/to figures, release within tol frames."""
    pa = [e for e in a if e["kind"] == "pass"]; pb = [e for e in b if e["kind"] == "pass"]
    hit = sum(1 for e in pa if any(f["from"] == e["from"] and f["to"] == e["to"] and abs(f["frame_release"] - e["frame_release"]) <= tol for f in pb))
    return hit, len(pa)


out = {"base": BASE, "passes": {}, "patterns": {}, "figure_analysis": {}, "combinations": {}, "replays": {}}
tot = {"before": Counter(), "after": Counter()}
for g in GAMES:
    a, b = before(f"{D}/{g}/passes.json"), after(f"{D}/{g}/passes.json")
    tot["before"].update(a["summary"]); tot["after"].update(b["summary"])
    h1, n1 = match_passes(a["events"], b["events"]); h2, n2 = match_passes(b["events"], a["events"])
    out["passes"][g] = {"before": a["summary"], "after": b["summary"], "uncertain_ends": [a["uncertain_ends"], b["uncertain_ends"]],
                        "before_passes_found_after": f"{h1}/{n1}", "after_passes_found_before": f"{h2}/{n2}"}
out["passes"]["all"] = {"before": dict(tot["before"]), "after": dict(tot["after"])}
LABS = [x for x in json.loads((REPO / D / "goal-labels.json").read_text())["labels"] if x.get("goal_video_s")]
def shot_hits(get):
    ev = {g: get(f"{D}/{g}/passes.json")["events"] for g in GAMES}
    return sum(1 for x in LABS if any(e["kind"] == "shot" and x["goal_video_s"] - 2.0 <= e["t_release_s"] <= x["goal_video_s"] + 0.2 for e in ev[x["game"]]))
out["passes"]["user_goals_with_a_shot_in_the_last_2s"] = [f"{shot_hits(before)}/{len(LABS)}", f"{shot_hits(after)}/{len(LABS)}"]
pa, pb = before(f"{D}/patterns.json"), after(f"{D}/patterns.json")
for g in GAMES:
    x, y = pa["per_game"][g], pb["per_game"][g]
    out["patterns"][g] = {k: [x[k], y[k]] for k in ("seen_fraction", "puck_on_own_figures", "flights_ge_100mm_per_min", "possession_changes_per_min",
                                                   "flight_median_speed_mm_s", "flight_board_bounce_share")}
for p in pa["per_player"]:
    x, y = pa["per_player"][p], pb["per_player"][p]
    out["patterns"][p] = {k: [x[k], y[k]] for k in ("puck_zone", "flights_from_own_figures") if k in x}
fa, fb = before(f"{D}/figure-analysis.json"), after(f"{D}/figure-analysis.json")
out["figure_analysis"] = {"touch_share": {g: [fa["games"][g]["touch_share"], fb["games"][g]["touch_share"]] for g in GAMES},
                          "puck_frames": {g: [fa["games"][g]["puck_frames"], fb["games"][g]["puck_frames"]] for g in GAMES},
                          "selected_tracks_after": {g: fb["games"][g].get("selected_tracks") for g in GAMES},
                          "touches_by_player_role": [fa["touches_by_player_role"], fb["touches_by_player_role"]]}
ca, cb = before(f"{D}/combo-labels.json"), after(f"{D}/combo-labels.json")
loo = lambda c, k: {m: f"{v['correct']}/{v['n']}" for m, v in c["leave_one_out"][k].items() if isinstance(v, dict) and "correct" in v}
ga, gb = {x["id"]: x for x in ca["goals"]}, {x["id"]: x for x in cb["goals"]}
out["combinations"] = {
    "leave_one_out_user_moment": [loo(ca, "at_user_moment"), loo(cb, "at_user_moment")],
    "leave_one_out_estimated_moment": [loo(ca, "at_estimated_moment"), loo(cb, "at_estimated_moment")],
    "goal_moment_loo_abs_error_s": [ca["goal_moment"]["loo_abs_error_s"], cb["goal_moment"]["loo_abs_error_s"]],
    "goal_moment_by_method": [ca["goal_moment"]["by_method"], cb["goal_moment"]["by_method"]],
    "proposed_label_changes": [{"id": i, "before": [ga[i]["family"], ga[i].get("combination"), ga[i].get("confidence")],
                                "after": [gb[i]["family"], gb[i].get("combination"), gb[i].get("confidence")]}
                               for i in ga if ga[i]["status"] != "user_label" and (ga[i]["family"], ga[i].get("combination"), ga[i].get("confidence"))
                               != (gb[i]["family"], gb[i].get("combination"), gb[i].get("confidence"))],
}
ra, rb = before("validation/replays/replays.json"), after("validation/replays/replays.json")
if ra and rb:
    A, B = {x["id"]: x for x in ra["goals"] if "coverage" in x}, {x["id"]: x for x in rb["goals"] if "coverage" in x}
    mean = lambda X, k: round(sum(x["coverage"][k] for x in X.values()) / len(X), 3)
    out["replays"] = {k: [mean(A, k), mean(B, k)] for k in ("puck_seen", "puck_disk", "figures_shown_mean", "figure_rows_every_frame")}
    out["replays"]["note"] = "means over the replay windows; puck_disk = slow (after) or disk (before)"
(REPO / "validation/nm26-track-switch.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
print(json.dumps({k: out[k] for k in ("combinations", "replays")}, indent=1, ensure_ascii=False)[:3000])
print(json.dumps(out["passes"]["all"]))
for g in GAMES: print(g, out["passes"][g]["before_passes_found_after"], out["passes"][g]["after_passes_found_before"], out["figure_analysis"]["touch_share"][g])
