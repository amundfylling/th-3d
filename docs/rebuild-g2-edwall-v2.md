# Edwall hat-trick rebuild v2 (NM26 semi-final game 2, goals 2-4)

Status: PROPOSED (2026-10-10). Three traces, one per goal, and three analysis videos. Follows
`docs/rebuild-g2-edwall.md` (v1: evidence sheets only). Nothing here is measured on the table; every value is read from one
broadcast camera or designed.

**Update 2026-10-10 (docs/nm26-new-tracks.md section 5):** goal 3's trace is now v2 (detector readings, rest at the
readings, the passer's and shooter's tracker readings); its row below and its video are from v1. Goals 2 and 4 stay v1:
no v2 fit scored.

**Results**

| goal | trace | contact check | slide check | carry force check | goal frame (trace / user label) | video |
|---|---|---|---|---|---|---|
| g2-goal2 | `data/traces/edwall-g2-goal2.trace.json` | pass | pass (shovel catch 449 mm/s) | FAILS | 27722.0 / 27723 | `validation/analysis-edwall-g2-goal2.mp4` |
| g2-goal3 | `data/traces/edwall-g2-goal3.trace.json` | pass | pass (shovel catch 280 mm/s) | FAILS | 28351.0 / 28347 | `validation/analysis-edwall-g2-goal3.mp4` |
| g2-goal4 | `data/traces/edwall-g2-goal4.trace.json` | pass | pass (shovel catch 384 mm/s) | FAILS | 28709.8 / 28707 | `validation/analysis-edwall-g2-goal4.mp4` |

Checks per goal: `shots/edwall/<goal>.checks.json` (contact: whole trace, every 0.25 ms, all 12 figures, boards, posts,
cage, 0.1 mm tolerance, no exceptions; `slide_check`; `unexplained_velocity_changes`; `carry_force_check`;
`observation_fit`). Top-view sheets: `validation/edwall-<goal>-trace.png`.

## What failed or is missing (read this first)

1. **The carries are kinematic, not explained by contact forces.** Both plays are modelled as a heel-groove carry (the
   puck stays at the touching point of the stick from catch to release). The CLAUDE.md checks pass (the puck touches and
   never overlaps), but my own `carry_force_check` asks whether the force the puck needs lies inside the contact normals
   that the figure's low outline offers there (widened by an ASSUMED 17 degree friction angle). It does not: in goal 2 the
   right wing would have to pull the puck in all 47 checked steps of the drag, in goal 3 in 38 of 60, in goal 4 in 56 of 89;
   the centre's short carries need a pull in every checked step. The preview low
   outline has no real groove at the carry point (normal fan 4.5-7 degrees, i.e. a flat face), so the puck is, in effect,
   glued to the blade while the figure turns. A plain push (no carry) could not reach the observed pass direction (the
   search got stuck near 40 degrees against about 66 degrees observed). What would fix it: the real heel-groove shape of
   the stick (a concave pocket at puck height) in the figure geometry, then a push model in that pocket.
2. **The shot is hidden in the broadcast and DESIGNED.** The puck disappears behind the E goalie and the near goal frame
   1-3 frames before the user's goal frame, before the centre touches it. The centre's lunge, turn and the shot line are fitted to "score into the
   open far (+y) corner near the goal frame", not to observations. Goal 2's shovel is a 4 ms touch that turns the puck
   from 54 to -1 degrees at 1.36 m/s; with a 449 mm/s relative normal speed it is just inside the slide limit, but it is
   really a redirect, which the slide rule warns bounces. Goals 3 and 4 shovel the puck with the centre's skate/body
   (280 and 384 mm/s), not the blade; in goal 4 the centre has turned so far (heading 234 degrees at the contact) that it
   plays the puck with the back of the figure. That is what the fit found, not what an Edwall shovel looks like.
3. **The puck's rest position is probably wrong by about 44 mm.** I snapped the resting puck to the near board
   (y = -222), assuming the board's top edge hid the ice next to it and biased the readings. The puck detector that
   arrived later (see "Check against the puck detector") reads the same rest position as my hand readings (y about -178,
   3-4 mm apart), and the camera geometry does not support the bias: with the camera about 27 degrees above the ice, a
   puck against the board would be almost completely hidden behind a board of the assumed 25 mm height, not seen 44 mm further out. So the
   puck most likely rests about 44 mm off the board, at the right wing's stick, and every trace starts its drag from
   the wrong place. A refit with the rest at the readings is the first next step.
4. **Pass fit residuals.** Flight readings are matched within 4-10 mm in goals 3 and 4 but 26-35 mm in goal 2 (the trace's pass
   leaves at 54 degrees, the readings at about 66). The first streak frame of goal 4 is off by 73 mm. Rest readings sit about 41-54 mm off because the rest is snapped to the
   board (item 3).
5. **Goal frames.** Goal 2 crosses the line 1 frame before the user's goal frame, goal 3 4 frames after (28351 vs 28347;
   the broadcast shows the puck still in flight at 28346, so that label looks 2-3 frames early), goal 4 3 frames after.
6. **Other ten figures** follow the cleaned model tracks unverified frame by frame (`g2/figure-tracks-smooth.json`).
   In goal 2 the shot grazes the E goalie (179 mm/s) on its way into the corner.

## Method

**Frames.** `scripts/edwall-frames.py <goal>` decodes the broadcast around each label, registers every frame to the game's
reference frame and writes the E half at 2x (`out/edwall/<goal>/`, not committed).

**Puck readings** (`shots/edwall/puck-readings.json`, by hand, crop pixels of the registered E half): rest (puck still
against the near board), streak (motion-blurred, centre of the streak), flight (sharp), hidden. Back-projected to the plane
z = 6 mm (half the assumed puck thickness) with the calibrated camera (`camera-ref.json`). I assumed the near board's top edge hides the ice right at the board, so that a puck resting
against the board would read about 40 mm too far from it (y about -180 instead of -222), and snapped the rest position to
just inside the canonical board line; the rest readings are reported but not fitted. This assumption is probably wrong
(item 3 above). Free flight reads about 1.1-1.2 m/s at about 66 degrees; the streak frames
read faster and are weighted 0.15.

**Figures.** All twelve figures are in each trace. W-RW (passer) and W-C (shooter) are designed: smootherstep moves along
the slot and around the fixture axis (rule 5: rigid, no bending). Their rest poses come from the cleaned track
(`data/games/nm26-semifinal/g2/figure-tracks-smooth.json`), the passer's rest arc is solved so that it touches the puck,
and after the play both return to the track. The tracks are interpolated through these fast moves, so they cannot fix the
lunges. The other ten figures follow the cleaned tracks.

**Puck model** (`scripts/edwall-trace.py`, reusing `scripts/spjass-trace.py`): 0.25 ms steps, ice friction 926.1 mm/s^2
(spjass slide fit), frictionless figure contacts with restitution 0.5, inelastic boards and posts, the net stops the puck.
New: the heel-groove carry (NTHF: "carries the puck with the heel groove"; precedent: the rigid carry of the accepted
shovel-17 trace). From the catch to the release the puck stays at the touching point of the figure and leaves with that
point's velocity. The catch is logged as a touch with its relative normal speed, so the slide rule applies to it.

**Fit** (two stages, differential evolution inside `fit.bounds` then Nelder-Mead; values in each inputs file under
`fitted`): pass = passer's rest rotation, lunge, turn and release against the puck readings; shot = shooter's lunge,
turns and release against the goal window (`goal_window_frames`), a goal-line target y = 26 mm (the open far corner), the
shooter arriving at the front of its slot by `wc_front_frame`, no overlap with other figures or posts during the carry,
and the slide limits. Goal 4's first shot search missed the goal; the second started from goal 2's shot shifted by
+0.03 s with a larger search (population 10, 25 generations).

| goal | passer rest rotation (fit / track) | lunge | turn | pass speed, direction | flight residuals |
|---|---|---|---|---|---|
| g2-goal2 | 236 / 212 deg | 43 mm in 82 ms | 142 deg | 1.79 m/s, 54 deg | 35, 26 mm |
| g2-goal3 | 219 / 220 deg | 142 mm in 219 ms | 67 deg | 1.60 m/s, 48 deg | 10, 8 mm |
| g2-goal4 | 228 / 223 deg | 116 mm in 123 ms | 82 deg | 1.26 m/s, 72 deg | 4, 7, 10 mm |

Goal 2's passer fit disagrees with the video: its rest rotation is 24 degrees off the track and its lunge is 43 mm where
the video shows roughly 95 mm.

## Videos

`remotion/EdwallAnalysis.tsx` builds three compositions (`analysis-edwall-g2-goal2..4`) on the shared
`remotion/AnalysisVideo.tsx`, registered by their own entry (`remotion/edwall-index.ts`) so the shared Root and render
script stay untouched. Specs: `data/presentations/edwall-<goal>.analysis.json` (`scripts/edwall-presentation.py <goal>`):
full speed, rewind, the drag and pass in slow motion with a freeze, the shovel with a freeze, a half-speed replay.
Render and check: `node scripts/edwall-render.ts <goal>` (per-frame state equals the pure trace evaluation; camera equals
the camera track; file below 25 MB; report `validation/analysis-edwall-<goal>-report.json`).
Rendered (2026-10-10): goal 2 528 frames (17.6 s, 8.7 MB), goal 3 559 frames (18.6 s, 8.6 MB), goal 4 568 frames
(18.9 s, 9.0 MB), 1920 x 1080, 30 fps; every frame's logged state equals the pure evaluation, camera within 0.005 of the
track, each about 75 min on this CPU. Review sheets: `validation/analysis-edwall-<goal>-review.jpg`
(`scripts/edwall-video-sheet.py`). Seen in review: the passer's TURN arrow is partly under the chapter card, and in goal
4 the centre shoots with its back to the goal (item 2 above).

## Check against the puck detector (added after the renders; traces and videos unchanged)

The synthetic puck detector's track (`data/games/nm26-semifinal/g2/puck-track-synth.json` on branch
`claude/puck-detector-st067s`, PROPOSED; x/y = puck centre) arrived after the traces were built. Compared with
`python3 scripts/edwall-puck-compare.py <track file>`:

- **Hand readings and detector agree closely**: median 4.2, 4.2 and 3.3 mm (goals 2, 3, 4) over the 7-9 frames both have,
  including the blurred streak frames (worst 14.5 mm, goal 2 frame 27715, where the detector score is 0.43).
- **Rest position**: the detector also puts the resting puck at y about -178 for the whole second before the play, not
  at the board (-222). The traces are 44-48 mm off there. See "What failed", item 3.
- **The pass**: the traces are 2-10 mm from the detector in the sharp flight frames of goals 3 and 4, and 25-30 mm in
  goal 2; the streak frames differ by up to 75 mm (goal 4 frame 28701, where the trace's pass leaves earlier).
- **The shot**: the detector loses the puck where my readings do (goal 2 after 27719, goal 4 after 28705; its later
  goal-4 detections at x about -221 are elsewhere on the rink). In goal 3 it has one more detection, at frame 28347
  (225.8, -20.5, score 0.74), 30 mm ahead of the trace along the pass line at the moment the trace's centre makes contact.
  That suggests the goal-3 pass is faster at the end than the trace.

## Check against tracker v3 (added after the renders; traces and videos unchanged)

Tracker v3 (`data/games/nm26-semifinal/g2/figure-tracks-v3.json` on branch `claude/tracker-v3-j1by4n`, PROPOSED) was
compared with `EDWALL_TRACKS=<v3 file> scripts/edwall-track-compare.py <goal>`: the ten tracked figures rebuilt from v3,
the saved puck path checked against them every 0.25 ms, and the pose differences over each goal window.

- **No overlaps.** With v3's figures the saved puck path still never overlaps any tracked figure in any goal. Closest:
  goal 2 E goalie 0.05 mm (the same graze as in the trace) and E-LD 19 mm; goal 3 E goalie 14 mm, E-LD 35 mm; goal 4 E
  goalie 28 mm.
- **E-LD moves.** v3 puts E-LD about 190-220 mm (median) away from the cleaned track in all three windows, and E-LW about
  210 mm away in goal 2. Neither comes into the play in either version.
- **v3 reads inside the lunges, where the cleaned tracks only interpolate.** That tests the designed moves:
  - Passer's lunge length agrees: goal 3 trace 121/155 mm vs v3 135/142 mm (frames 28344/28345); goal 4 trace
    152 mm vs v3 141/149 mm (28702/28703).
  - Passer's turn is too small in the traces: v3 reads 333-360 degrees at the release frames, the traces 287-310 (goal 3
    by 45-65 degrees, goal 4 by 25-50). A bigger turn would also steer the pass closer to the observed 66 degrees.
  - Goal 4 shooter disagrees: v3 has the centre at 226-231 mm facing 263-278 degrees at frames 28706-28707; the trace
    has it at the front (250 mm) and turned round to 202 then 132 degrees (the back-of-figure shot). This supports
    treating goal 4's shot as wrong.
  - Goal 2 shooter: v3's next real reading after the play has the centre at 145 mm (frame 27724), where the trace holds
    it at the front (246 mm). Either the centre pulls back fast after the shot or it never reached the front.
- Next step from this: refit the passer's turn and both shots with v3's in-lunge readings as constraints.

## Reproduce

```
/root/venvs/blender/bin/python scripts/edwall-frames.py <goal> 3.0 0.5      # frames (optional, for reading)
/root/venvs/blender/bin/python scripts/edwall-trace.py <goal> --fit pass     # slow; writes inputs.fitted
/root/venvs/blender/bin/python scripts/edwall-trace.py <goal> --fit shot
/root/venvs/blender/bin/python scripts/edwall-trace.py <goal>                # trace, checks, sheet
python3 scripts/edwall-presentation.py <goal>
npm run remotion:assets && node scripts/edwall-render.ts <goal>
```

## Next

- Refit all three with the puck resting where both readings put it (y about -178), the detector track as the puck
  observations, and v3's in-lunge figure readings as constraints; then rerender.
- Model the stick's heel groove at puck height and replace the kinematic carry by a push in that pocket.
- A puck detector track (or a second camera) for the last 5 frames, where the shot is hidden.
- The user's review of the goal-3 label and of the passer's lunge in goal 2.
