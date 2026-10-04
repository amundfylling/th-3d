# Iteration 22 - constrained reconstruction of "#17 Shovel" (PROPOSED)

Status: **proposed, not accepted.** Reconstructed by the AI on 2026-10-04 from the iteration-21 observations. The
contacts await the user's review. The trace contains an **explicit conflict with the replay** (below). No movie, no
presentation overlays, no general physics simulation.

## Outputs

| Path | What |
| --- | --- |
| `data/traces/shovel-17.trace.json` | The trace (`shot-trace/1`, `trace.shovel-17.v1`, status `proposed`). Contents: geometry 0.6.0 and asset SHA-256 references; source time in seconds; figure arc/rotation keyframes with sources and sigma; puck nodes and phases; contact events with observed intervals; uncertainty; limitations; evaluation samples. |
| `shots/22-shovel/inputs.json` | New hand-read marks (traced, AI): blade marks, orientation notes, static-figure feet, W-C run rows for frames 111/114, replay constraints. |
| `shots/22-shovel/checks.json` | Clearances per obstacle and phase, unexpected overlaps, goal-line crossing, blade-pivot checks, run-timing scan, rotation and shot-direction diagnostics. |
| `validation/22-diagnostics.png` | **Main artifact.** Nine stills: before, at and after pass release, reception contact and goal entry. Each still is the nearest source frame with the trace projected by the segment-1 camera, plus a top view. |
| `validation/22-trace-overview.png` | Whole puck path, top view, coloured by phase, with the iteration-21 observations. |
| `src/model/trace.ts` | Pure evaluator `traceEvaluator(trace)(t)`: Fritsch-Carlson arc, linear rotation, linear puck. |
| `scripts/shot22-trace.py` | Reconstruction (`npm run shot:22`, about 2 min). |

Times below are source time `t` (seconds in the recording); shot time = t - 0.45.

## Method (rules, not a simulator)

- **Camera**: segment-1 homography from iteration 21 (RMS 6.1 px). Every image mark is mapped to the ice plane.
  The diagnostics project the trace back into the source frames. The replay (segment 2) is uncalibrated and is used
  only for event order and the goal side.
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
  - A timing is feasible if the puck crosses the goal line inside the mouth on the replay's +y side, and clears the
    goalie and W-C after separation.
- **Finite-size checks**: catalog 25.4 mm puck against every figure's low geometry, the board boundary, both posts
  and the goal line, every 0.25 ms. The puck moves at most 1.1 mm per step, so fast motion between samples is covered.

## Events

| Event | Trace t (s) | Observed interval (s) | Basis |
| --- | --- | --- | --- |
| pass.release (W-RW backhand) | 1.772 | 1.698-1.782 | derived: flight line + last instant W-RW still touches the puck |
| contact.W-C_reception | 1.834 | 1.782-1.848 | derived: first disk overlap with W-C (back of the figure, near the skates) |
| shot.separation | 1.855 | not observed | rule: W-C peak slot speed. Puck 4.4 m/s at 7.0 deg |
| goal_entry | 1.901 | 1.848-1.980 | derived: goal-line crossing at y = -1.1 mm (mouth window -28.7..29.8) |

All three observed events fall inside their intervals. Contact and release are estimates inside the observed
intervals, not measured instants.

## Conflict with the replay (main review item)

The replay shows the puck entering between the goalie and the +y post, on the goalie's right. With W-C's observed
rotation, the rigid carry and separation at peak slot speed, **no run timing does that**:

- Goal-line crossings over all 298 timings: -45.3 to -1.1 mm. All are at or left of the mouth centre.
- Every timing puts the puck through the static goalie, by -11.4 to -18.8 mm.
- The saved trace is the least violating timing. It crosses inside the mouth (a goal), but the shot phase overlaps
  the goalie by 11.6 mm (1.888-1.896 s).
- **Shot direction**: the rule-based shot leaves at 7.0 deg, the slot tangent at separation. Straight paths from the
  same separation point that clear the goalie and enter on +y need **11.2-15.2 deg**, about 4-8 deg more toward +y.
  A rigid carry can only launch the puck along the figure's motion. A puck sliding along or deflecting off W-C's
  angled back would gain that sideways component, but a contact model is outside this iteration.
- **Rotation diagnostic** (not in the trace): one unobserved mid-run W-C turn was added and scanned. Offsets of
  -30, +30, -60 and +60 deg fail. Only +90 deg reproduces the replay (5 timings, goalie clearance 1.0 mm). No
  frame shows such a turn: W-C faces back at 1.78 s and again at the top end.
- **Sensitivity to the W-C position**: the blade-derived pivots put W-C 18-25 mm further up the slot than the
  iteration-21 skate-row readings, while W-RW differs by 2-6 mm. Accounting for the skate-to-pivot offset with the
  mesh explains only about 6 mm. A run with every W-C reading shifted +18 mm keeps the conflict and worsens it: the
  goal is crossed at -26 mm, and 19.4-21.0 deg would be needed against 7.0 deg.

Candidate causes, most likely first:
1. The carry and separation rule: the puck leaves along the slot tangent.
2. The goalie's position or rotation (one feet mark; rotation from a partly hidden paddle) or the AI goalie mold
   size (low geometry spans y -47.3 to -6.7 mm).
3. An unobserved W-C rotation during the carry.
4. A different slot layout on the recorded table edition.

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
- Small expected overlaps:
  - W-RW at release: -0.64 mm;
  - W-RW before release: -3.7 mm, where contact is expected;
  - W-C during the carry: 0 mm, touching.

## Reproduce

```
npm run shot:22                       # writes the trace, checks and both images (about 2 min)
node --test tests/shot22.test.ts      # status, references, events, step size, TS evaluator vs samples, order independence
SHOT22_WC_ARC_OFFSET=18 SHOT22_OUT_DIR=<dir> /root/venvs/blender/bin/python scripts/shot22-trace.py   # sensitivity run
```

`asset_refs.git_commit` records the commit the trace was generated from (the parent of the iteration-22 commit).

## Needed from the user (review)

1. **Contacts**:
   - Is the reception on W-C's back or skates correct?
   - Is the pass a backhand release while W-RW rotates counter-clockwise?
2. **Goal side**: confirm the puck enters between the goalie and the post on the goalie's right (replay frames 280-289).
3. **Which explanation to pursue**:
   - the puck slides along W-C's back, so the contact rule must change;
   - W-C turns during the carry;
   - the goalie stood further toward -y or faced differently.
   A sharper frame, or the original full-resolution video, would decide it.
4. **Accept or correct** the trace before iteration 23 uses it.
