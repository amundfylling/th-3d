"""Build moves of the shot encyclopedia from their move files (moves/<id>/move.json); docs/shot-encyclopedia.md.

    /root/venvs/blender/bin/python scripts/build-move.py <move-id> [<move-id> ...]       build, save if every check passes
    /root/venvs/blender/bin/python scripts/build-move.py <move-id> --set theta.x=1 ...    parameter scan (scratch only)
    /root/venvs/blender/bin/python scripts/build-move.py <move-id> --scratch             build to out/moves/<id>/ only
    python3 scripts/build-move.py <move-id> --presentation                                 regenerate the video spec from
        moves/<id>/story.json and the SAVED trace (no simulation); refused when the trace no longer matches the move file,
        the engine or the model, or failed its checks (scripts/shotlib/identity.py)

Any Python with numpy, shapely and pillow works (no Blender needed). Exit code 1 if a move fails its checks.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ap = argparse.ArgumentParser()
ap.add_argument("moves", nargs="+")
ap.add_argument("--set", action="append", default=[], help="override a move-file value: dotted.path=<json>")
ap.add_argument("--scratch", action="store_true")
ap.add_argument("--robustness", action="store_true", help="also rerun the move with its uncertain inputs changed (scripts/shotlib/robustness.py)")
ap.add_argument("--video-spec", action="store_true", help="also write the analysis video spec and the Remotion registry (scripts/shotlib/presentation.py)")
ap.add_argument("--quick", action="store_true", help="print the contact groups and the goal only (for scans)")
ap.add_argument("--presentation", action="store_true", help="presentation only: regenerate the video spec from story.json and the saved, checked trace")
ap.add_argument("--check", action="store_true", help="only report whether the saved trace and presentation are current and passed their checks (JSON; exit 1 if not)")
a = ap.parse_args()
ok = True
if a.check:  # light: no simulation imports (used by scripts/video.ts before it renders a move)
    from shotlib import identity
    rows = [{"move": m, "problems": identity.presentation_gate(m)} for m in a.moves]
    print(json.dumps(rows))
    sys.exit(0 if all(not r["problems"] for r in rows) else 1)
from shotlib import build  # noqa: E402
if a.presentation:
    from shotlib import identity, presentation
    for m in a.moves:
        problems = identity.motion_gate(m)
        if problems:
            print(f"{m}: REFUSED, the saved trace is not current (rebuild: python3 scripts/build-move.py {m} --video-spec)\n  - " + "\n  - ".join(problems))
            ok = False
            continue
        print(json.dumps({"move": m, "motion_gate": "passed", "video_spec": presentation.write(build.load_move(m)[1])}))
    sys.exit(0 if ok else 1)
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
    print(json.dumps(r, indent=1, ensure_ascii=False))
sys.exit(0 if ok else 1)
