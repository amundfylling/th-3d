# STIGA Play Off 21 shot videos

Goal: photorealistic 3D Remotion videos that explain shots played on the user's
STIGA Play Off 21 table hockey game (family 71-1145-XX). The model must be built
around the actual hardware, not a generic hockey table.

Work proceeds in numbered iterations from `Claude_Code_Stiga_Iteration_Prompts.md`.
There were no animated shots before iteration 23.

## Active batch

The autonomous batch 06-20 (`docs/autonomous-run.md`) is COMPLETE. Rule 1 ("stop after each
iteration") applies again. Iterations 21-25 are done (docs/shot21.md - docs/shot25.md). The iteration-22 trace is
ACCEPTED by the user (2026-10-04) with an assumed far-corner shot direction; iteration 23 plays it in Remotion
(fixed overhead camera). Revised 2026-10-05 (trace v2): W-RW drags the puck with its foot, and the contact-physics
rule below applies. Iteration 24 is done (docs/shot24.md): normal pass, 1/4-speed replay with a pause at the
key contact, oblique benchmark camera. Iteration 25 is done (docs/shot25.md): the first video is exported
(validation/25-shovel-17-final.mp4, 1920x1080 60 fps; rerender with `npm run video:shovel-17`). No further
numbered iteration is defined. A sports-analysis video of the same trace (composition `analysis-shovel-17`,
validation/analysis-shovel-17.mp4, `npm run video:analysis-shovel-17`) is documented in docs/analysis-shovel-17.md.
The spjass centre move (user's TikTok, references/shots/spjass-tiktok.mp4) is reconstructed as a PROPOSED trace
(data/traces/spjass.trace.json) and animated (composition `analysis-spjass`, validation/analysis-spjass.mp4); see docs/spjass.md.
Näcka (NTHF page and illustration, references/combinations/; no recording) is a PROPOSED, DESIGNED trace
(data/traces/nacka.trace.json) with video validation/analysis-nacka.mp4; see docs/nacka.md.
Invers Kryssar med Velodrom (NTHF text only; the user approved the sketch validation/ikv-sketch.png) is a PROPOSED,
DESIGNED trace (data/traces/invers-kryssar-velodrom.trace.json, v2: the left wing catches softly and pushes the puck
into the corner, after the user rejected v1's flick) with video validation/analysis-ikv.mp4; see
docs/invers-kryssar-velodrom.md.
A concept video of the three ways to defend when the opponent's left wing has the puck (passive/box, active, mix; user's
TikTok references/shots/defence-vs-left-wing-tiktok.mp4) uses the PROPOSED, DESIGNED trace data/traces/defence-left-wing.trace.json
(video validation/analysis-defence-lw.mp4); its shots and passes are lanes drawn as graphics; see docs/defence-left-wing.md.
All analysis videos share remotion/AnalysisVideo.tsx.
Game mechanics: the ITHF rules (references/rules/ithf-game-rules.pdf) and one full recorded match (Fylling vs Moe,
references/games/; handheld phone) are digested in docs/game-mechanics.md, with open questions for the user. No tracking
model is built yet; answer those questions first.

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

## Contact physics (user rule, 2026-10-05)

- The puck is a rigid disk. It may TOUCH figures (skates, stick, body), boards and goal, but NEVER overlap or pass
  through them: not at any time in a trace, in any phase, including preparation moves (drags, stick handling),
  occluded intervals and the time between samples. Every saved trace is checked with the finite puck against every
  figure's geometry, the boards and the goal posts every 0.25 ms or finer, with an overlap tolerance of at most
  0.1 mm and no phase exemptions. A trace that fails is not saved as proposed or accepted, and Remotion does not
  play it.
- Every change in the puck's motion has a named physical cause: a contact with a specific part (foot/skate, blade,
  back of the figure, boards, goal). No unexplained course changes, no jumps, no puck moving through geometry.
- Follow the real technique: the drag-back is done with the foot (skate) and a slight turn of the figure, not with
  the stick through the puck. When the evidence is unclear, choose a contact that is physically possible (touching,
  pushing in the direction of motion), never an overlap. Rigid figures also obey rule 5: rotate the figure, don't
  bend it.
- Exceptions only with the user's explicit approval, recorded as data (`shots/*/inputs.json`
  `approved_overlap_exceptions`: what, why, maximum depth, approver, removal condition) and reported in the checks.
  Never add one silently, and never widen one without asking.

## Slide or bounce (user rule, 2026-10-06)

The puck is a light, thin disk. It stays flat and SLIDES only when every contact changes its velocity gently. A hard
hit makes it tip, jump or rebound, and traces do not model that. So a trace must not rely on a contact that would
make the puck bounce.
- **Slides:**
  - **A push.** The blade or skate meets the puck at a low relative speed and then moves WITH it, building the speed
    up over a sustained contact. The figure faces the push direction and travels along its slot and/or turns slowly.
    This is how a pass along the boards is played: the wing skates forward with the puck on the front of the blade,
    into the curve of the corner, and the puck runs on along the boards (example:
    `references/shots/lw-board-pass-example.mov`, a different combination; the puck leaves the corner at about
    1 m/s).
  - **A soft reception.** The blade gives way (turns or moves with the incoming puck), so the puck is slowed, not
    stopped dead or sent back.
  - **Along the boards.** The puck meets the board at a glancing angle (it enters a curve nearly tangentially) and
    then follows it.
  - **A first-time play of a moving puck.** The blade first moves with the puck (it gives way: the figure slides
    along its slot or turns away), then accelerates it in the new direction.
- **Bounces (not allowed in a trace):**
  - A flick or strike: a fast-sweeping blade hits the puck at a large relative speed, worst of all a puck that is
    coming toward the blade (a first-time reversal or a sharp redirect).
  - A puck driven steeply into the boards, a post or a figure at speed. It rebounds; it does not stick and slide.
- **Checks** (every new or changed trace, reported in its checks file as `slide_check`):
  - every figure contact: relative normal impact speed at most 500 mm/s;
  - every board, post or cage contact: normal impact speed at most 300 mm/s;
  - the goal net catching the puck is exempt.
  - These limits are ASSUMED. They come from the user's judgement that the left-wing flick in the first IKV trace (v1),
    with a 2.9 m/s impact, bounces, and from the example clip. Change them only with the user.
  - Traces made before this rule (Shovel, spjass, Näcka) have not been rechecked against it.
  - In the frictionless restitution-0.5 contact model, a push shows up as a run of many small touches. That is
    expected; each touch must be within the limit.

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
