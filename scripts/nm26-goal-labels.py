"""Collect the user's goal review answers (validation/nm26-goals-review.html, db collection "goals").

    python3 scripts/nm26-goal-labels.py <labels_dir>

<labels_dir>: the page's documents (ArtifactData list with out_dir). Adds the goal's video and game-clock time
(clip_start_s + goal_clip_s) and the score-box lag. Writes data/games/nm26-semifinal/goal-labels.json.
"""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
clips = {c["id"]: c for c in json.loads((REPO / "out/nm26/goal-clips/clips.json").read_text())}
T = json.loads((REPO / "data/games/nm26-semifinal/timeline.json").read_text())["games"]
rows = []
for f in sorted(Path(sys.argv[1]).glob("*.json")):
    d = json.loads(f.read_text()); c = clips[d["id"]]
    r = {k: d.get(k) for k in ("id", "scorer", "assist", "family", "combination", "rebuild", "notes")}
    r.update({"game": c["game"], "scoring_player": c["scorer"], "scoring_end": c["end"], "box_s": c["box_s"]})
    if d.get("goal_clip_s") is not None:
        t = c["clip_start_s"] + d["goal_clip_s"]
        r.update({"goal_video_s": round(t, 1), "goal_game_clock_s": round(t - T[c["game"]]["start_signal_s"], 1), "box_lag_s": round(c["box_s"] - t, 1)})
    rows.append(r)
rows.sort(key=lambda r: (int(r["game"][1:]), int(r["id"].split("goal")[1])))
out = {"description": "The user's goal review (2026-10-09; clips of every NM26 goal). scorer/assist: figure role of the scoring "
       "team; family: kind of attack; combination: the user's name (NTHF catalogue names where given). Times from the user's "
       "'goal is now' mark (puck crosses the line). Status: user labels.", "labels": rows}
(REPO / "data/games/nm26-semifinal/goal-labels.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
print(len(rows), "goals")
