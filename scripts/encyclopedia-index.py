"""The shot encyclopedia's index: every NTHF combination (data/combinations/nthf-catalogue.json) with what exists for it
in this repo (move file, trace, checks, video, earlier hand-built trace) and how often it scored in NM26 (user labels).

    python3 scripts/encyclopedia-index.py      ->  data/encyclopedia/index.json

The suggested build order puts moves with real NM26 goals first, then easy before hard; the family is a keyword
heuristic on the NTHF text (docs/table-hockey-playbook.md section 4), status `heuristic`.
"""
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CAT = json.loads((REPO / "data/combinations/nthf-catalogue.json").read_text())
LABELS = json.loads((REPO / "data/games/nm26-semifinal/goal-labels.json").read_text())["labels"]
# traces built before the move engine (their own scripts), by catalogue name
LEGACY = {"Näcka": ("data/traces/nacka.trace.json", "validation/analysis-nacka.mp4", "scripts/nacka-trace.py"),
          "Spjass": ("data/traces/spjass.trace.json", "validation/analysis-spjass.mp4", "scripts/spjass-trace.py"),
          "Invers Kryssar med Velodrom": ("data/traces/invers-kryssar-velodrom.trace.json", "validation/analysis-ikv.mp4", "scripts/ikv-trace.py")}


def slug(name):
    s = unicodedata.normalize("NFKD", name.split("/")[0].strip()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def family(c):
    d, n = c["description"].lower(), c["name"].lower()
    if "goalie" in d and ("goalie passes" in d or "goalie shoots" in d or "goalie plays" in d):
        return "goalie involved"
    if "behind" in d and "own goal" in d:
        return "behind your own goal"
    if "behind" in d and "goal" in d:
        return "behind the goal"
    if "defen" in d:
        return "defender one-timer"
    if "left wing" in d:
        return "via the left wing"
    if c["player"] == "Right wing" and ("to the center" in d or "in to the center" in d or "passes in" in d or "sends it in" in d):
        return "shovel / innspill (RW -> C)"
    if c["player"] == "Right wing":
        return "right-wing shot"
    if "board" in d or "off the goalie" in d:
        return "off the boards / goalie"
    return "centre trick"


def main():
    nm = Counter(l["combination"] for l in LABELS if l.get("combination"))
    rows = []
    for c in CAT["combinations"]:
        mid = slug(c["name"])
        mf = REPO / "moves" / mid / "move.json"
        spec = json.loads(mf.read_text()) if mf.exists() else None
        have = lambda p: p if (REPO / p).exists() else None
        r = {"id": mid, "name": c["name"], "player": c["player"], "level": c["level"], "description": c["description"],
             "family": family(c), "family_status": "heuristic", "nm26_goals": nm.get(c["name"], 0),
             "move_file": str(mf.relative_to(REPO)) if spec else None, "move_status": spec["status"] if spec else None,
             "reading_approved": bool(spec and spec.get("approved_reading")),
             "trace": have(f"data/traces/{mid}.trace.json") if spec and not spec.get("legacy") else None,
             "checks": have(f"shots/{mid}/checks.json") if spec and not spec.get("legacy") else None,
             "robustness": have(f"validation/moves/{mid}-robustness.json"),
             "video": have(f"validation/moves/{mid}.mp4"), "legacy": None}
        if c["name"] in LEGACY:
            t, v, s = LEGACY[c["name"]]
            r["legacy"] = {"trace": have(t), "video": have(v), "script": s}
        r["stage"] = ("video" if r["video"] or (r["legacy"] and r["legacy"]["video"]) else "trace" if r["trace"] or (r["legacy"] and r["legacy"]["trace"])
                      else "move file" if spec else "not started")
        rows.append(r)
    order = sorted(rows, key=lambda r: (-r["nm26_goals"], r["level"], r["name"]))
    for i, r in enumerate(order):
        r["suggested_order"] = i + 1
    out = {"schema": "encyclopedia-index/1", "description": "Every NTHF combination and what exists for it (scripts/encyclopedia-index.py; docs/shot-encyclopedia.md).",
           "counts": {"moves": len(rows), "by_stage": Counter(r["stage"] for r in rows), "by_family": Counter(r["family"] for r in rows),
                      "with_nm26_goals": sum(1 for r in rows if r["nm26_goals"])},
           "nm26_labels_not_in_catalogue": sorted(k for k in nm if k not in {c["name"] for c in CAT["combinations"]}),
           "moves": order}
    (REPO / "data/encyclopedia").mkdir(parents=True, exist_ok=True)
    (REPO / "data/encyclopedia/index.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(out["counts"], ensure_ascii=False), out["nm26_labels_not_in_catalogue"])
    for r in order[:12]:
        print(r["suggested_order"], r["name"], r["level"], r["family"], r["nm26_goals"], r["stage"])


if __name__ == "__main__":
    main()
