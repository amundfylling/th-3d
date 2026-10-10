# Iteration 22 - constrained reconstruction of "#17 Shovel" (ACCEPTED)

Status: **accepted by the user on 2026-10-04**, with one assumed value: the shot direction (see "User review"). The
AI reconstructed the trace from the iteration-21 observations, and the user confirmed the contacts and the
far-corner goal. No movie, no presentation overlays, no general physics simulation.

## Outputs

| Path | What |
| --- | --- |
| `data/traces/shovel-17.trace.json` | The trace (`shot-trace/1`, `trace.shovel-17.v1`, status `accepted`, user review recorded in `review`). Contents: geometry 0.6.0 and asset SHA-256 references; source time in seconds; figure arc/rotation keyframes with sources and sigma; puck nodes and phases; contact events with observed intervals; uncertainty; limitations; evaluation samples. |
| `shots/22-shovel/inputs.json` | New hand-read marks (traced, AI): blade marks, orientation notes, static-figure feet, W-C run rows for frames 111/114, replay constraints (superseded) and the user's review (`user_review`). |
| `shots/22-shovel/checks.json` | Clearances per obstacle and phase, unexpected overlaps, goal-line crossing, blade-pivot checks, run-timing scan, rotation and shot-direction diagnostics. |
| `validation/22-diagnostics.png` | **Main artifact.** Nine stills: before, at and after pass release, reception contact and goal entry. Each still is the nearest source frame with the trace projected by the segment-1 camera, plus a top view. |
| `validation/22-trace-overview.png` | Whole puck path, top view, coloured by phase, with the iteration-21 observations. |
| `src/model/trace.ts` | Pure evaluator `traceEvaluator(trace)(t)`: Fritsch-Carlson arc, linear rotation, linear puck. |
| `scripts/shot22-trace.py` | Reconstruction (`npm run shot:22`, about 2 min). |

Times below are source time `t` (seconds in the recording); shot time = t - 0.45.

## Method (rules, not a simulator)

- **Camera**: segment-1 homography from iteration 21 (RMS 6.1 px). Every image mark is mapped to the ice plane.
  The diagnostics project the trace back into the source frames. The replay (segment 2) is uncalibrated and, after the
  user review, not used as evidence (it may be a different take).
- **Figures**: rigid pieces. Position is the slot arc (mm along the canonical slot centreline). Rotation theta is
  relative to the team home heading (docs/pose.md).
  - Arc: Fritsch-Carlson monotone cubic through the observed keyframes.
  - Theta: linear between measured or rule-inferred keyframes.
  - Both are held outside the keyframes.
- **Rotation from blades**: the blade edge is read in the frame and mapped to the ice. The asset's blade heel/toe
  give the heading and pivot. Blade-derived pivots lie 0.1-2.8 mm from the slot centreline, which supports the
  calibration, the skater scale and the fixture-axis assumption.
- **W-C (shooter)**:
  - Faces back toward its own end while receiving (heading about -197 deg at 1.73-1.78 s). The shovel is played
    with the back of the figure.
  - Rest pose at 2.78 s: -163 deg.
  - Rotation during the run is not observed (blur). It is interpolated linearly, which turns it less than 1 deg
    over the 21 ms carry.
- **W-RW (passer)**: rotates counter-clockwise from -171.5 deg (blade, 1.70 s) through a backhand release.
  - The release rotation is inferred from a rule: the blade face normal points along the pass direction. Sigma 15 deg.
  - Back toward the camera at 1.78 s (visual, sigma 30 deg); rest 8.6 deg (blade).
- **Static figures**: E-G, E-RD and E-LD are kept in their frame-167 poses.
  - Their feet are read and snapped to the slot.
  - E-G rotation (33 deg) comes from the paddle direction.
  - Defender rotations are assumed 0, with sigma null.
- **Puck**:
  1. Observed blob centres before the pass.
  2. Linear from the last at-blade sample to the release.
  3. Constant velocity (1785 mm/s, 75.4 deg) through the two flight observations.
  4. First contact of the finite disk with W-C's low geometry (mesh below the 12 mm preview puck top). Read every 0.25 ms.
  5. Rigid carry at that contact offset.
  6. Separation at W-C's peak slot speed.
  7. Constant velocity to the back of the preview cage.
  8. At rest there (assumed).
- **W-C run timing**: frames 109, 111 and 114 are blurred. They are used as exposure constraints, not keyframes
  (exposure at most one content frame, 40 ms).
  - The run starts within frame 109's exposure.
  - During 111 and 114, the skates reach the image rows re-read in `inputs.json` (`run_marks`).
  - The onset and top-arrival times are scanned on a 3 ms grid (298 valid timings).
  - A timing is feasible if the puck crosses the goal line inside the mouth on the +y side (the far corner), and
    clears the goalie and W-C after separation. None is (see below), so the least violating timing is kept.
- **Finite-size checks**: catalog 25.4 mm puck against every figure's low geometry, the board boundary, both posts
  and the goal line, every 0.25 ms. The puck moves at most 1.1 mm per step, so fast motion between samples is covered.

## Events

| Event | Trace t (s) | Observed interval (s) | Basis |
| --- | --- | --- | --- |
| pass.release (W-RW backhand) | 1.772 | 1.698-1.782 | derived: flight line + last instant W-RW still touches the puck |
| contact.W-C_reception | 1.834 | 1.782-1.848 | derived: first disk overlap with W-C (back of the figure, near the skates) |
| shot.separation | 1.855 | not observed | time and speed: rule (W-C peak slot speed, 4.4 m/s). Direction: **assumed 11.2 deg** (rule 7.0 deg), see "User review" |
| goal_entry | 1.901 | 1.848-1.980 | derived: goal-line crossing at y = +14.2 mm, far corner (mouth window -28.7..29.8) |

All three observed events fall inside their intervals. Contact and release are estimates inside the observed
intervals, not measured instants. The user confirmed both contacts.

## Rule direction vs the far corner (resolved by the user review)

The puck went in the far corner: between the goalie and the +y post, on the goalie's right (user, 2026-10-04; first
seen in the replay, which the user now says may be a different take). With W-C's observed rotation, the rigid carry
and separation at peak slot speed, **no run timing does that**. The figures below are for the rule direction,
before the adjustment:

- Goal-line crossings over all 298 timings: -45.3 to -1.1 mm. All are at or left of the mouth centre.
- Every timing puts the puck through the static goalie, by -11.4 to -18.8 mm.
- The least violating timing crosses inside the mouth (a goal), but at the rule direction the shot overlaps the
  goalie by 11.6 mm. The trace keeps this timing and changes only the direction (below).
- **Shot direction**: the rule-based shot leaves at 7.0 deg, the slot tangent at separation. Straight paths from the
  same separation point that clear the goalie and enter on +y need **11.2-15.2 deg**, about 4-8 deg more toward +y.
  A rigid carry can only launch the puck along the figure's motion. A puck sliding along or deflecting off W-C's
  angled back would gain that sideways component, but a contact model is outside this iteration.
- **Rotation diagnostic** (not in the trace): one unobserved mid-run W-C turn was added and scanned. Offsets of
  -30, +30, -60 and +60 deg fail. Only +90 deg reaches the far corner (5 timings, goalie clearance 1.0 mm). No
  frame shows such a turn: W-C faces back at 1.78 s and again at the top end.
- **Sensitivity to the W-C position**: the blade-derived pivots put W-C 18-25 mm further up the slot than the
  iteration-21 skate-row readings, while W-RW differs by 2-6 mm. Accounting for the skate-to-pivot offset with the
  mesh explains only about 6 mm. A run with every W-C reading shifted +18 mm keeps the mismatch and worsens it: the
  goal is crossed at -26 mm, and 19.4-21.0 deg would be needed against 7.0 deg.

Candidate causes of the missing sideways angle, most likely first:
1. The carry and separation rule: the puck leaves along the slot tangent.
2. The goalie's position or rotation (one feet mark; rotation from a partly hidden paddle) or the AI goalie mold
   size (low geometry spans y -47.3 to -6.7 mm).
3. An unobserved W-C rotation during the carry.
4. A different slot layout on the recorded table edition.

## User review (2026-10-04) and the adjustment

The user's answers (recorded in `shots/22-shovel/inputs.json` `user_review` and in the trace's `review`):

1. Contacts: correct (reception on W-C's back; W-RW backhand while rotating counter-clockwise).
2. Goal side: correct, **far corner**. The replay may not be the same take as the full-speed segment (one camera),
   so it is no longer used as evidence. The goal side now rests on the user's statement.
3. Shot angle: the user chose to aim the shot at the far corner.
4. The trace looks good: accepted.

**Adjustment**: separation time, point and speed stay as the rule gives them. Only the direction changes, from 7.0
deg to **11.2 deg**, the smallest angle that clears the goalie and the far post. Inside the clear window (11.2-15.2
deg) the puck brushes the rear of W-C's right skate as it slides off the figure's back. That overlap grows with the
angle (2.7 mm at 11.2 deg, 8.4 mm at 15.2 deg), so the smallest angle has the shallowest overlap. Results:

- goal-line crossing y = +14.2 mm (far corner), 15.1 mm clear of the far post;
- goalie clearance 0.04 mm, a near miss along the goalie's right pad;
- W-C overlap -2.65 mm (1.859-1.879 s), within the unknown skate contact size of the AI mold;
- goal entry 1.901 s, inside the observed interval.

The extra 4.2 deg is an assumption ("assumed" in the trace), not a measurement. The likely mechanism is the puck
sliding along W-C's angled back, which no contact model here describes.

## Revision 2026-10-05: W-RW foot drag-back and the contact-physics rule (trace v2)

**User feedback on the iteration-23 playback.** "The stick goes through the puck when it does the drag back of the
puck on the RW. The common way is to use the foot to drag it back and to turn the player slightly." The user also
asked for a permanent rule; it is now in `CLAUDE.md` under "Contact physics".

**Cause.** The prep phase (frames 30-102) was never reconstructed physically:
- W-RW's rotation was held at its frame-102 value (facing the camera) the whole time. The recording shows it facing
  up the ice at the board end (frames 30 and 68).
- The puck followed the observed blob centres in straight lines, independent of the figure.
- The clearance check started only 60 ms before the release and exempted W-RW.

**Fix** (`scripts/shot22-trace.py`):
- **Pose at each puck observation.** At each of the 10 prep observations, W-RW's slot position and heading are
  solved so that the puck touches a skate (the foot) and nothing overlaps it. The solve stays close to the visual
  heading read on the recording (`inputs.json` `prep_heading_marks`) and to the skate-row slot readings.
  - The puck moves at most 7.1 mm from its read position, always within the reading uncertainty.
  - At the board end, W-RW faces up the ice turned slightly (+18.8 deg at frame 30, -24 deg at frame 68), with the
    puck at its right foot.
  - It drags the puck back with the foot and turns to face the camera on the way, as the recording shows.
- **Between observations.** The puck stays on the figure. It slides along the figure's touching outline, in the
  figure's own frame, so it moves with the foot. The way round the figure and the turn direction are chosen so
  the puck moves without jumps and never enters the boards.
- **Whole-trace check.** Every saved node (every 0.5 ms) is pushed out of any figure it would overlap (a pushing
  contact). The check then covers the whole trace every 0.25 ms, with a 0.1 mm tolerance and no phase exemptions.
  Result: no overlap anywhere except the one approved exception below. The largest puck step is 1.1 mm per
  0.25 ms (the shot speed), so the puck never jumps.
- **Shot: one approved exception.** The far-corner shot brushes the back of W-C's right skate by 2.65 mm.
  - Under strict contact, that skate pushes the puck back into the goalie.
  - Only a W-C turn of about 75 deg during the carry avoids it, and that contradicts frame 116, where W-C faces
    back (`checks.json` `shot_direction_diagnostic.w_c_turn_scan`).
  - The user approved keeping the accepted shot with this single exception (2026-10-05). It is recorded in
    `inputs.json` `approved_overlap_exceptions` (at most 2.7 mm deep) and is removed once the skate is measured.
- **Gates.** The Remotion shot plays only a trace whose `checks.json` matches its `trace_id` and lists no
  unexpected overlaps.
- **New artifact.** `validation/22-prep-foot-drag.png`: W-RW's foot, stick and the puck every 25 ms, with the
  foot and stick clearances. The foot clearance stays at 0.0-0.1 mm through the drag, and the stick clearance
  never goes negative.

Trace id `trace.shovel-17.v2`. Status stays `accepted`: the corrections follow the user's instruction and
decision, which are recorded in `review.revisions`.

## Corrections made in this iteration

- **Goal side**: iteration 21 wrote "goalie's left (camera-right in the replay)". Camera-right in the replay is +y,
  the E goalie's right. Corrected in `docs/shot21.md`, `shots/21-shovel/observations.json`, `marks.json` and
  `scripts/shot21-observe.py`; the replay frames 274-292 were re-checked.
- **Frame-111 smear**: the iteration-21 note "smear spans v 383-800" is the whole blurred figure, not the skate
  travel. An earlier draft of this reconstruction read it as skate travel, which forced a 15 m/s shot. The skate rows
  were re-read: frame 111 rows 600-700, frame 114 rows 415-475.

## Limitations (also in the trace)

- The contact dimensions are unknown: blade, skate and stick come from the AI mold at the preview scale; the puck
  thickness (12 mm) and goal size are preview values.
- The recording shows another STIGA edition. The canonical Play Off 21 slot layout is assumed.
- The rod-to-figure transfer, travel stops and backlash are unknown. The fixture axis is assumed on the slot centreline.
- Occluded intervals stay labelled:
  - pre-release, behind W-RW;
  - carry and shot, behind W-C and the goalie, not visible in segment 1;
  - the in-net position, assumed at the back of the cage.
- The shot direction is assumed (above). The goalie pose comes from one feet mark and a partly hidden paddle.
- The replay is not used as evidence (possibly a different take).
- Overlaps (since the 2026-10-05 revision): none, except the approved 2.65 mm brush past W-C's right skate in the
  shot. Every contact elsewhere is touching (0-0.1 mm).

## Reproduce

```
npm run shot:22                       # writes the trace, checks and both images (about 2 min)
node --test tests/shot22.test.ts      # status, references, events, step size, TS evaluator vs samples, order independence
SHOT22_WC_ARC_OFFSET=18 SHOT22_OUT_DIR=<dir> /root/venvs/blender/bin/python scripts/shot22-trace.py   # sensitivity run
```

`asset_refs.git_commit` records the commit the trace was generated from (the parent of the iteration-22 commit).

## Next

Iteration 23 can use the accepted trace. The assumed shot direction and the brush past W-C's skate stay visible in
the trace's `limitations` and in `shots/22-shovel/checks.json`.
