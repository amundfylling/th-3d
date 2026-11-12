# Checking saved traces from the file alone

Status: in use by `npm test` since 2026-11-11 (pipeline audit, refactor 1). Changes no trace, check file or video.

## Why

CLAUDE.md "Contact physics" says every saved trace is checked with the finite puck against every figure, the boards and
the goal every 0.25 ms, and that Remotion does not play a trace that fails. Before this, that check existed seven times:
once inside each script that writes a trace (`shot22-trace.py`, `spjass-trace.py`, `nacka-trace.py`, `ikv-trace.py`,
`defence-trace.py`, `edwall-trace.py`, and `scripts/shotlib/build.py`). Each ran on its own simulation objects and wrote
the answer into a checks file (`shots/*/checks.json`). The tests and the render gate (`remotion/AnalysisVideo.tsx`) only
read that file: `unexpected_penetrations` empty and the same `trace_id`.

Two gaps follow. A checks file is not tied to the trace bytes (the id is a version label), so a trace that is edited,
or regenerated while the old checks file stays, keeps its "no overlap". And a mistake in one script's loop is invisible,
because nothing else measures its trace.

## What there is now

`scripts/shotlib/verify.py` is one check that needs no generator:

- It reads a `shot-trace/1` file and places the figures as the renderer does (`src/model/trace.ts`: monotone cubic arc,
  linear theta, linear puck). Figures the trace does not list stand in the assembly pose
  (`validation/16-assembly-poses.json`), as the renderer shows them.
- It measures the puck against all twelve figures' contact footprints (`data/figures/contact-footprints.json`, the
  footprints of the move engine), the boards, both goals' posts and cages, every 0.25 ms over the whole window, in every
  phase. Tolerance 0.1 mm. A puck outside the boards is an overlap however far out it is. The cage of the goal the puck
  enters is not an obstacle while the puck centre is inside it (the net catches the puck); a puck that goes on through
  the back or a side of the net is an overlap. The posts are always obstacles.
- Exceptions are only the user's recorded ones (`approved_overlap_exceptions` in the inputs file beside the trace's
  checks file). Each covers its own obstacle, phase and depth, and needs "user" in `approved_by`. Rows are named by the phase of the
  puck node before the sample, as the generators name them; where the recorded intervals (`puck.phases`, what the
  renderer reads) say another phase, an exception does not apply (the Shovel has 7 such samples, none in an overlap).
- It also reports the largest puck step between two samples (a jump is 2 mm or more) and the smallest clearance per
  obstacle and phase.

```sh
python3 scripts/verify-trace.py                                 # every trace in data/traces/ (about 2 s on 4 cores)
python3 scripts/verify-trace.py data/traces/spjass.trace.json   # chosen traces
python3 scripts/verify-trace.py --json                          # full reports
```

Needs numpy and shapely, no Blender. Exit code 1 on an overlap, a jump or a trace without a checks file.

## Result on the nine saved traces (2026-11-11)

All nine pass. The only overlap is the Shovel's approved skate brush: 2.051 mm measured here, 2.05 mm recorded, limit
2.7 mm.

The generators recorded 132 clearance rows (obstacle, phase, smallest clearance). 131 have a counterpart here: 127
agree within 0.006 mm, two near-contact rows differ by 0.012 and 0.022 mm, and two far rows of the Edwall goal 2 trace
differ by 0.29 and 0.36 mm (a post at 13.6 mm and the boards at 29 mm). The test allows 0.05 mm below 5 mm of clearance
and 0.5 mm above. The one row without a counterpart is `W-C / shovel_carry` in the Edwall goal 3 checks: the saved
trace has no puck node in that phase, so there is nothing to measure under that name (the same samples are measured
under the neighbouring phases).

## Tests

`tests/trace-verify.test.ts` runs `tests/traces/test_verify.py` (22 tests, about 10 s). It is skipped, and says so, when
the Python has no shapely.

| Test group | Covers |
| --- | --- |
| SavedTraces | every saved trace passes from its file; every phase and all twelve figures are measured; only the recorded exception is used; agreement with the recorded clearances |
| Catches | a puck moved into a listed figure, into a figure the trace does not list, 1 mm into a blade for one node (0.5 ms), outside the boards, onto a post, through the side net; a jump; malformed traces (schema, node times, puck radius, empty keyframes, coarser sampling) |
| Exceptions | the Shovel fails without its exception; the exception does not cover a deeper overlap, another phase, another figure, or an approver that is not the user |
| Evaluation | vector poses and clearances equal `world.Figure.pose` and `world.clearance`; the hull shortcut keeps every minimum and every overlap exact |

## Limits and next steps

- **Slide rule not covered.** Impact speeds come from a simulation's contact events, which a saved trace does not hold.
  `slide_check` is still each generator's own report.
- **The generators keep their own loops.** `verify.py` is listed in `identity.NOT_ENGINE`, so adding it did not
  invalidate the Hjerpefinte trace. Replacing the loop inside `build.py` changes the engine hash, which forces a rebuild
  and a re-render of every engine-built video; do it together with the next engine change.
- **The render gate still reads the checks file.** `scripts/video.ts` could call `verify-trace.py` before a render. Not
  done here because the render-speed work is changing that file.
- **Footprints, not meshes.** The older scripts measured against Blender meshes (`out/figures/*.npz`); this check uses
  the exported footprints. The row agreement above shows they are the same shapes.
