# The spjass (centre move): reconstruction and analysis video

Status: reconstructed and rendered on 2026-10-06 from the user's TikTok (user request "Create an animation for it";
not a numbered iteration). The trace `trace.spjass.v1` is **proposed**: it has not been reviewed by the user. The
video is rendered from it because the user asked for the animation directly. Accepting or correcting the trace is the
next step.

| Item | Path |
| --- | --- |
| Source video (preserved) | `references/shots/spjass-tiktok.mp4` (SHA-256 `bf0da0e1...ebcc`, listed in `references/index.json`) |
| Hand-read marks | `shots/spjass/marks.json` |
| Observations | `shots/spjass/observations.json` (`scripts/spjass-observe.py`), overlay `validation/spjass-observations.png` |
| Reconstruction choices | `shots/spjass/inputs.json` |
| Trace | `data/traces/spjass.trace.json` (`scripts/spjass-trace.py`), checks `shots/spjass/checks.json`, top-view sheet `validation/spjass-trace.png` |
| Analysis spec | `data/presentations/spjass.analysis.json` |
| Composition | `analysis-spjass` (`remotion/SpjassAnalysis.tsx` + the shared `remotion/AnalysisVideo.tsx`) |
| Video | `validation/analysis-spjass.mp4`; report `validation/analysis-spjass-report.json`; review sheet `validation/analysis-spjass-review.png`; puck visibility `validation/analysis-spjass-occlusion.json` |
| Tests | `tests/spjass.test.ts` |

Reproduce:
```sh
npm run trace:spjass            # observations + trace + checks (deterministic)
npm run video:analysis-spjass   # render (about 70 min on the 4-CPU container), occlusion report, review sheet
```

## What the TikTok shows

The clip is a portrait TikTok by @tablehockeyglobal. It was recorded on another STIGA edition (Byggmax/gyproc
artwork) with a white Finland centre (no. 26) against a yellow Sweden goalie. Sections:
- **Intro (frames 0-62):** low close-up from behind the centre.
- **Take 1 (66-145):** full speed from a fixed top-down camera. This is the evidence for the trace.
- **Presenter and hand explanation (146-580).**
- **Slow manual demonstration (700-880).**
- **Wider full-speed repetition (894-948).**

The spoken explanation was not transcribed: speech recognition is not available here (the model downloads are
blocked). Everything below is read from the pictures.

The take-1 picture is not mirrored: the ice text is rotated 180°, and the board ads in the intro read normally. So
handedness and sides are real. Image up is +x (toward goal.E) and image left is +y. White attacks goal.E, so the
mover is **W-C** and the goalie is **E-G**, as in the Shovel.

The move, frame by frame in take 1, with heading as in docs/pose.md (W home 0° = facing goal.E):
1. **Set-up (66-121).** W-C faces away from the goal (heading about 180°). The puck rests behind its heel on the slot
   line, near the slot end.
2. **Turn and flick (122-124).** W-C turns counter-clockwise (seen from above). The back of the blade (backhand) hits
   the puck at frame 124.0 and sends it toward +y, at 66° and about 0.3 m/s.
3. **Slide (125-131).** The puck slides in a straight line and slows evenly. Fitted: 65.6°, deceleration
   926 mm/s², RMS 0.16 mm.
4. **Spin and shot (129-132, motion-blurred).** W-C spins **clockwise** almost a full turn while sliding about 25 mm
   up its slot. The front of the blade (forehand) arrives behind the puck and drives it forward at about 1.6 m/s.
   - The clockwise direction is seen in the slow demonstration (frames 790-880: stick up, right, down, down-left,
     ending behind the puck) and in the follow-through (133-140).
5. **Goal (133).** The puck passes between the goalie and the +y post into the net.

## Calibration and observations

- **Camera.** Homography from 8 marks: slot ends, and slots crossing the blue and goal lines. Fit RMS 4.0 px,
  leave-one-out 8.3 px; about 1.5-3 mm at 2.6 px/mm. The overlay (`validation/spjass-observations.png`) shows the
  projected slots on the real ones.
- **Puck.** Automatic dark-blob track, frames 96-133. Parallax of the visible top is under 1 mm (pinhole estimate,
  weakly conditioned).
- **W-C poses.** Read from the blade toe, which lies on the ice: the pivot sits on the slot at the toe's local radius.
  - Frames 124-128: slot position 207.1-207.9 mm, heading 246 → 293°.
  - Frames 133-140: slot position about 233 mm (the lunge), heading 300 → 265°.
- **E-G pose.** From its blade at frame 100: heading 166.8°, measured blade length 25.5 mm against the model's 26.0.
  Moved 5.5 mm onto its slot.

## Reconstruction rules (no simulator)

- **Pushing contact.**
  - The puck moves with its velocity, slowed by the fitted ice friction.
  - Wherever any figure (all 12), a goal post or the boards would overlap it, it is moved out to touching along the
    contact normal and takes the resulting velocity. This is the iteration-22 rule.
  - It stops against the back of the cage.
- **Blade impulses.**
  - **Flick:** observation-driven. At the moment the fitted slide reaches the rest point (frame 124.04), the figure is
    posed so the model blade touches the puck, and the puck takes the observed velocity.
  - **Shot:** the strike is where the backward-extended shot line (frames 132-133) meets the slide (frame 131.06).
    The puck takes the observed speed, in the direction described under the assumptions. The figure is posed so the
    blade's front face touches it.
  - Both pushes stay within a plausible blade-puck friction cone of the model contact normal: flick 16°, shot 4.4°.
- **W-C motion.**
  - Rest arc: the read pose would overlap the model puck by about 2 mm, so it is backed off 1.75 mm until the puck
    just touches the heel. The figure moves up to the turn reading by frame 124.
  - Turn: from the onset straight to the touching pose at the flick (about 29°/frame), then through the frame 125-128
    blade poses.
  - Spin: a monotone cubic through the frame-128 pose, the touching pose at the strike and the frame-133 pose.
  - Lunge: nearly complete at the strike (assumed timing).
- **Checks** (`shots/spjass/checks.json`). The finite puck is checked against every figure's low geometry (all 12
  figures; those not in the trace stand in the assembly pose), the boards and the posts, every 0.25 ms:
  - no overlap and no approved exception;
  - no unexplained velocity change;
  - contacts are exactly blade (flick), blade (shot) and goal net;
  - closest approaches: goalie 0.86 mm, +y post 1.18 mm. The tight corner shot of the video.
- **Agreement with take 1.** Puck residuals are 0.1-0.3 mm on every sharp frame from 122 to 131. They are 5.1 and
  8.2 mm on the blurred frames 132-133, from the assumed shot direction below.

## Assumptions to review (most important first)

1. **Shot direction.** The observed blurred line (−1.4°) crosses the goal line 7.7 mm from our +y post's centre. With
   the preview goal (whose mouth width is a preview value) it would overlap the post. The trace shoots at −4.6°: the
   centre of the window of straight paths that clear the measured goalie pose and both posts (−5.2° to −4.0°).
2. **The spin's timing within the blur** (frames 129-132) and the **lunge timing**: only the direction and the end
   poses are observed.
3. **Flick contact pose.** The model blade touches the resting puck only at heading 254.4°, 8.5° past the frame-124
   reading (the TikTok figure's stick differs from our AI-modelled mold). The two assumed intermediate turn keyframes
   in `inputs.json` (122.5, 123.3) are superseded by this touching pose (reported in `checks.flick.replaced_keyframes`).
4. **Ice friction** is a fitted rule (926 mm/s²), not a measured coefficient.
5. **Another table edition.** The canonical slot layout and the preview goal are assumed; figure, stick and puck
   sizes are preview values.

## Analysis video

The video uses the same structure and look as the Shovel analysis (`docs/analysis-shovel-17.md`), from the shared
`remotion/AnalysisVideo.tsx`. That module was refactored out of the Shovel composition; six Shovel frames rendered
before and after the refactor are byte-identical, recorded in `validation/analysis-shovel-17-report.json`.

| Time | Segments | Shot | Camera | Graphics |
| --- | --- | --- | --- | --- |
| 0.0-1.5 s | `intro` | freeze at rest | high +y view eases down | title card |
| 1.5-2.8 s | `full`, `goal_hold` | the whole move at full speed (it takes about 0.4 s) | broadcast, +y side | FULL SPEED; GOAL |
| 2.8-3.4 s | `rewind` | back to the set-up | moves to the set-up view | REWIND |
| 3.4-7.6 s | `setup_set`, `setup_freeze` | freeze | still | chapter 1; centre highlight; "PUCK BEHIND THE HEEL" |
| 7.6-12.6 s | `to_flick`, `turn_in`, `flick_freeze` | ×0.15 turn to the flick, freeze | closer, then still | chapter 2; TURN arrow (counter-clockwise); "FLICK · BACK OF THE BLADE"; flick direction |
| 12.6-18.3 s | `to_shot`, `spin_in`, `strike_freeze` | ×0.15 slide and spin to the strike, freeze | behind the shooter, still | chapter 3; SPIN arrow (clockwise); step-up arrow; "SHOT · FRONT OF THE BLADE"; puck trail |
| 18.3-20.1 s | `shot_out`, `goal_freeze` | ×0.12 into the net, freeze | still | GOAL |
| 20.1-23.1 s | `to_replay`, `replay` | ×0.4 replay | three-quarter, still | REPLAY ×0.4; puck trail |
| 23.1-24.7 s | `outro` | freeze | still | summary card |

Checks:
- **Captions:** each chapter is shown at least 3.5 s with a still camera, at no more than 4 words per second.
- **Camera:** steps under 60 mm per frame, never below 100 mm (`tests/spjass.test.ts`).
- **Puck visibility** (`validation/analysis-spjass-occlusion.json`): sight lines to the puck are ray-cast against the
  real posed figure meshes on every frame. The puck is fully visible in every explanation, slow-motion and replay
  segment. It is partly hidden only during the rewind and two camera moves.
- **Render:** every rendered frame's state equals the pure evaluation and every camera equals the camera track
  (`validation/analysis-spjass-report.json`).

The video's wording ("centre", "flick", "spin", "front/back of the blade") is AI wording for non-players. The name
"spjass" is the user's.
