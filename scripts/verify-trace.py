"""Check saved traces against the contact rule, from the trace files alone (scripts/shotlib/verify.py).

    python3 scripts/verify-trace.py                                  every trace in data/traces/
    python3 scripts/verify-trace.py data/traces/spjass.trace.json    chosen traces
    python3 scripts/verify-trace.py --json                           the full reports (clearance per obstacle and phase)

Needs numpy and shapely (no Blender). Exit code 1 if a trace overlaps geometry beyond the user's recorded exceptions,
jumps between samples, or has no saved checks file.
"""
import argparse
import json
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shotlib import verify  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("traces", nargs="*")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    paths = [Path(p) for p in a.traces] or verify.saved_traces()
    with Pool(max(1, min(a.jobs, len(paths)))) as pool:
        reports = pool.map(verify.verify_file, paths)
    if a.json:
        print(json.dumps(reports, indent=1, ensure_ascii=False))
    else:
        for r in reports:
            near = min(r["min_clearance_by_obstacle_and_phase"], key=lambda x: x["min_clearance_mm"])
            print(f"{'ok  ' if r['passed'] else 'FAIL'} {r['trace_id']} ({r['status']}): {r['samples']} samples, {r['figures_checked']} figures, "
                  f"nearest {near['obstacle']} {near['min_clearance_mm']} mm in {near['phase']}, max step {r['max_puck_step_mm']} mm")
            for e, x in r["approved_exceptions"].items():
                print(f"       approved exception {e}: {x['obstacle']} in {x['phase']} {x['worst_mm']} mm (limit -{x['max_overlap_mm']} mm, {x['approved_by']})")
            for o in r["unexpected_penetrations"]:
                print(f"       OVERLAP {o['obstacle']} in {o['phase']}: {o['worst_mm']} mm, t {o['t0']}-{o['t1']} s")
            for p in r["problems"]:
                print(f"       PROBLEM {p}")
    return 0 if all(r["passed"] for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
