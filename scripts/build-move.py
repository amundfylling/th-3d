"""Build moves of the shot encyclopedia from their move files (moves/<id>/move.json); docs/shot-encyclopedia.md.

    /root/venvs/blender/bin/python scripts/build-move.py <move-id> [<move-id> ...]       build, save if every check passes
    /root/venvs/blender/bin/python scripts/build-move.py <move-id> --set theta.x=1 ...    parameter scan (scratch only)
    /root/venvs/blender/bin/python scripts/build-move.py <move-id> --scratch             build to out/moves/<id>/ only

Any Python with numpy, shapely and pillow works (no Blender needed). Exit code 1 if a move fails its checks.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shotlib import build  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("moves", nargs="+")
ap.add_argument("--set", action="append", default=[], help="override a move-file value: dotted.path=<json>")
ap.add_argument("--scratch", action="store_true")
ap.add_argument("--robustness", action="store_true", help="also rerun the move with its uncertain inputs changed (scripts/shotlib/robustness.py)")
ap.add_argument("--margins", action="store_true", help="also find how far each uncertain input can change before the move misses (robustness.margins)")
ap.add_argument("--video-spec", action="store_true", help="also write the analysis video spec and the Remotion registry (scripts/shotlib/presentation.py)")
ap.add_argument("--quick", action="store_true", help="print the contact groups and the goal only (for scans)")
a = ap.parse_args()
ok = True
for m in a.moves:
    if a.quick:
        print(json.dumps(build.quick_summary(build.load_move(m, a.set)[1])))
        continue
    r = build.build(m, a.set, a.scratch)
    ok &= r["passed"]
    if a.video_spec and r["passed"]:
        from shotlib import presentation
        r["video_spec"] = presentation.write(build.load_move(m)[1])
    if a.robustness:
        from shotlib import robustness
        rb = robustness.robustness(m, build.load_move(m, a.set)[1], canonical=not (a.scratch or a.set))
        r["robustness"] = {k: rb[k] for k in ("variants_passed", "robust", "goal_y_spread_mm")}
        r["robustness"]["failed"] = [x["variant"] for x in rb["rows"] if not (x["outcome_ok"] and x["slide_ok"])]
    if a.margins:
        from shotlib import robustness
        mg = robustness.margins(m, build.load_move(m, a.set)[1], canonical=not (a.scratch or a.set))
        r["margins"] = {x["input"]: {"holds_up_to": [x["down"]["holds_up_to"], x["up"]["holds_up_to"]], "steps_holding": x["steps_holding"],
                                     "steps_scoring": x["steps_scoring"]} for x in mg["margins"]}
    print(json.dumps(r, indent=1, ensure_ascii=False))
sys.exit(0 if ok else 1)
