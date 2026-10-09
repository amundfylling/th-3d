"""Build the NM26 goal review page: a clip of every goal; the user marks the moment, scorer, assist and shot type.

    python3 scripts/nm26-goal-page.py

Clips from scripts/nm26-goal-clips.py (out/nm26/goal-clips/<id>.mp4, published next to the page as clips/<id>.mp4).
The page stores answers in its db (collection "goals"): goal_clip_s (seconds into the clip when the puck crosses the
line; video time = clip_start_s + goal_clip_s), scorer and assist (figure role of the scoring team, "own", "none",
"unknown"), family (attacking family), combination (free text, NTHF names offered), rebuild (worth a 3D video), notes.
Writes validation/nm26-goals-review.html.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
clips = json.loads((REPO / "out/nm26/goal-clips/clips.json").read_text())
cat = json.loads((REPO / "data/combinations/nthf-catalogue.json").read_text())["combinations"]
names = sorted({c["name"] for c in cat})
PLAYER = {"nygard": "Nygård", "fjermestad": "Fjermestad"}
log = REPO / "out/nm26/goal-clips/log.txt"
done = {l.split()[0] for l in log.read_text().splitlines() if l.endswith(" MB")} if log.exists() else set()
data = []
for c in clips:
    if c["id"] not in done: continue  # only clips the encoder has finished (its log line)
    gt = c.get("game_time_s"); mm = f"{int(gt // 60)}:{int(gt % 60):02d}" if gt is not None else "?"
    data.append({"id": c["id"], "game": c["game"][1:], "n": c["n"], "scorer": PLAYER[c["scorer"]], "end": c["end"],
                 "ot": not c.get("in_regulation", True), "box": round(c["box_s"] - c["clip_start_s"], 1), "clock": mm,
                 "src": f"clips/{c['id']}.mp4"})
page = (REPO / "scripts/nm26-goal.template.html").read_text()
page = page.replace("/*DATA*/[]", json.dumps(data, ensure_ascii=False, separators=(",", ":"))).replace("/*NAMES*/[]", json.dumps(names, ensure_ascii=False))
(REPO / "validation/nm26-goals-review.html").write_text(page)
print(len(data), "goals")
