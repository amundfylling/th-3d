# STIGA Play Off 21 shot videos

Goal: photorealistic 3D Remotion videos that explain shots played on the user's
STIGA Play Off 21 table hockey game (family 71-1145-XX). The model must be built
around the actual hardware, not a generic hockey table.

Work proceeds in numbered iterations from `Claude_Code_Stiga_Iteration_Prompts.md`.
There are no animated shots before iteration 23.

## Active batch

The autonomous batch 06-20 (`docs/autonomous-run.md`) is COMPLETE. Rule 1 ("stop after each
iteration") applies again. Iteration 21 needs the user's review feedback and a real shot recording.

## Key files

- `docs/state.md` - handoff: last/next iteration, verification status, decisions, missing inputs.
- `docs/reference.md` - reference brief: PDF identity, page pointers, published dimensions, conflicts, gaps.
- `Stiga_Play_Off_21_References.pdf` - eight-page research guide. Preserve unchanged.

## Working rules

1. Read `docs/state.md` before each task. Complete only the requested iteration and stop.
2. Preserve the references (never edit, recompress or overwrite them). Use one canonical
   geometry specification and stable player/asset IDs.
3. Every geometric value has a unit, a source and a status: `measured`, `catalog_nominal`,
   `traced`, `assumed` or `unknown`. Unspecified uncertainty is `null`, never zero.
   Preview assumptions stay visible in the data and in review notes.
4. The target is Play Off 21 family 71-1145-XX. The public Sweden/Finland pictures
   (71-1145-01) are a reference variant; the user's actual parts, teams and artwork take
   precedence when supplied.
5. Skaters are rigid molded pieces with a path position and a rotation around the actual
   fixture axis. No articulated skating, arm movement or independent stick swing.
   Preserve physical handedness for both teams. Treat the goalie separately.
6. Travel along a curved track does not imply automatic tangent-facing rotation.
   Rod-to-figure transfer functions, travel stops and backlash need evidence.
7. Keep motion data separate from camera, replay speed and overlays. Remotion frames
   evaluate a saved trace at time t; they must not depend on a live physics loop or on
   frame order.
8. Start with recorded-shot reconstruction. Do not build a general physics simulator
   in these iterations.
9. Run checks relevant to the change. Review visual artifacts when possible. Never claim
   an unexecuted build or an unseen render passed.
10. Finish each iteration with: changed paths, checks actually run, one main artifact to
    inspect, unresolved assumptions and the next step. Update `docs/state.md`. Commit that
    iteration's changes on the current working branch when git permits; do not merge or
    force-push.

## Evidence discipline

- Nominal is not measured. Never average conflicting published lengths (960 vs 940 mm)
  and never stretch the ice/playing area (approx. 845 x 457 mm) to a housing size.
- Housing, board boundary, ice sheet and playing area are different things; name which
  one a value refers to.
- The bare ice-sheet photo shows older artwork and may extend beneath the boards; keep it
  separate from the current installed-rink artwork.
- Photographs are perspective views, not dimensioned plans. Match the camera projection
  before tracing or comparing overlays.
- Model the goal configuration actually used in the demonstration (retail insert vs
  ITHF tournament setup) once the user states it.

## File structure (create folders only when an iteration needs them)

- `references/` - recovered source assets and `references/index.json`.
- `data/` - canonical geometry specification, measurements, motion traces.
- `src/model/` - pure TypeScript geometry and fixture-pose code.
- `assets/` - Blender sources and exported 3D assets.
- `validation/` - overlays, review renders and check outputs.
- `docs/` - reference brief, state handoff and review notes.
