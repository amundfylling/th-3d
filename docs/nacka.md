# Näcka (centre move): designed trace and analysis video

Status: designed and rendered on 2026-10-06 (user request "Now make this one:
https://www.puck.no/en/combinations/nacka/"; not a numbered iteration). The trace `trace.nacka.v1` is **proposed**: it
has not been reviewed by the user.

Unlike the Shovel and the spjass, **no recording of Näcka exists**. The motion is designed from:
- the description and movement illustration of the Norwegian Table Hockey Association (NTHF);
- the set-up and physical rates measured in the spjass TikTok. NTHF gives both moves the same start.

| Item | Path |
| --- | --- |
| Sources (preserved, indexed) | `references/combinations/puck-no-nacka.html`, `trick-nacka.png` (and the NTHF Spjass page and illustration, used as a cross-check) |
| Design choices | `shots/nacka/inputs.json` |
| Trace | `data/traces/nacka.trace.json` (`scripts/nacka-trace.py`), checks `shots/nacka/checks.json`, top view `validation/nacka-trace.png` |
| Analysis spec | `data/presentations/nacka.analysis.json` |
| Composition | `analysis-nacka` (`remotion/NackaAnalysis.tsx` + the shared `remotion/AnalysisVideo.tsx`) |
| Video | `validation/analysis-nacka.mp4`; report `validation/analysis-nacka-report.json`; review sheet `validation/analysis-nacka-review.png`; puck visibility `validation/analysis-nacka-occlusion.json` |
| Tests | `tests/nacka.test.ts` |

Reproduce: `npm run trace:nacka`, then `npm run video:analysis-nacka` (about 70 min on the 4-CPU container).

## Sources

The NTHF description (centre, difficulty 4/10): *"Center starts with the puck in the heel groove, passes with the heel
a few centimeters out to the right, and shoots with the blade into the right corner."*

From the illustration (top view, goal at the top), scaled by the goal mouth (104 px = 86.94 mm, 0.836 mm/px):
- puck position 1 is at the centre's heel;
- position 2 is about 44 mm to the right and slightly forward (−69°);
- the shot runs about +5° into the right corner.

The drawing is schematic: taken literally, its arrow ends on our post and its goalie covers the whole mouth.

**Cross-check of the spjass.** NTHF's Spjass reads *"passes with the blade a few centimeters out to the left, spins
all the way around and shoots with the blade into the left corner"*. This matches the reconstruction from the TikTok
(`docs/spjass.md`) in every step. Left and right are seen from behind the centre, toward the goal: left is +y, right
is −y.

## The motion (designed)

1. **Set-up.** The rest pose of `trace.spjass.v1`: W-C has its back to the goal, with the puck touching its heel.
2. **Heel pass (clockwise turn, 4.05-4.125 s).** The back of W-C's right skate (local (−15.4, −13.1) mm) pushes the
   puck out to the right: 238 mm/s at −43°.
   - The puck slides 37.5 mm, with the ice friction fitted to the spjass slide.
   - The direction follows from the model skate's shape: every turn profile tried gives −44°. The drawing shows
     about −69°, so the puck ends further forward than drawn.
3. **Shot (counter-clockwise turn back with a 43 mm step up the slot, 4.24-4.35 s).** The blade's face (local
   (2.6, 26.8) mm, contact normal 0.3°) meets the puck square from behind at heading 177.9°, at slot position
   248.9 mm. The puck leaves at 0.9 m/s and +3.1° (drawing: +5.5°).
4. **Goal.** The puck crosses the goal line at y = −26.2 mm, inside the right post (its limit is −28.7), and stops
   against the back of the net.

**Checks** (`shots/nacka/checks.json`). The same rule as every saved trace: the finite puck against all 12 figures,
the boards and the posts every 0.25 ms. Results:
- no overlap, no exception, no unexplained velocity change;
- the contacts are exactly the skate heel (pass), the blade (shot) and the goal net;
- closest approaches: goalie 1.3 mm, right post 2.5 mm.

## Assumptions to review (most important first)

1. **Everything about the timing:** the turn speeds, the pause between pass and shot, and the step up the slot.
   These are design choices, at the rates of the measured spjass.
2. **The goalie stands 9.5 mm toward the left post** (E-G slot position 12.95 mm). With the assembly pose its stick
   closes the right corner for any straight shot. Näcka is shown as the counter to a goalie expecting the spjass.
3. **The pass direction** (−43°, from the model skate) differs from the drawing (−69°). As a result, W-C needs a long
   step up the slot (43 mm, near the slot end) to strike the puck square.
4. **"Heel" is read as the heel of the skate.** This follows "the puck in the heel groove", and the rule that
   drag-backs are done with the foot. If NTHF means the heel of the blade, the pass needs a different turn.
5. The model figure, stick and puck sizes and the preview goal are assumptions, as in the other traces.

## Analysis video

Same structure and look as the spjass video:
1. **Intro and full speed (0.0-2.9 s):** title, full speed, GOAL.
2. **Rewind (2.9-3.4 s).**
3. **Chapter 1, "THE SET-UP" (3.4-7.7 s):** "PUCK BEHIND THE HEEL".
4. **Chapter 2, "THE HEEL PASS" (7.7-12.5 s):** ×0.1 to the heel contact, then a freeze with the clockwise TURN
   arrow, "PASS · HEEL" and the pass direction.
5. **Chapter 3, "THE SHOT" (12.5-20.1 s):** ×0.2 slide and turn back, a freeze at the blade contact ("SHOT · BLADE",
   TURN BACK arrow), ×0.15 into the right corner, then GOAL.
6. **Replay and summary card (20.1-24.8 s):** replay ×0.4.

The views are on the −y side, where the move happens. The puck is visible in every explanation, slow-motion and replay
segment (`validation/analysis-nacka-occlusion.json`, ray-cast against the real figure meshes). Captions are shown for
at least 3.5 s with a still camera, at no more than 4 words per second; camera steps stay under 60 mm per frame
(`tests/nacka.test.ts`).
