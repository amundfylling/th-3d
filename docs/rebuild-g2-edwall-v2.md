# Edwall hat-trick rebuild v2 (NM26 semi-final game 2, goals 2-4)

Status: PROPOSED (2026-10-10). Three traces, one per goal, and three analysis videos. Follows
`docs/rebuild-g2-edwall.md` (v1: evidence sheets only). Nothing here is measured on the table; every value is read from one
broadcast camera or designed.

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
3. **No newer puck track.** There was no `claude/puck-detector-*` branch on the remote when this was built (checked with
   `git fetch` twice), so the traces use my hand readings (`shots/edwall/puck-readings.json`).
4. **Pass fit residuals.** Flight readings are matched within 4-10 mm in goals 3 and 4 but 26-35 mm in goal 2 (the trace's pass
   leaves at 54 degrees, the readings at about 66). The first streak frame of goal 4 is off by 73 mm. Rest readings sit about 41-54 mm off because the rest is snapped to the
   board (see "Puck readings").
5. **Goal frames.** Goal 2 crosses the line 1 frame before the user's goal frame, goal 3 4 frames after (28351 vs 28347;
   the broadcast shows the puck still in flight at 28346, so that label looks 2-3 frames early), goal 4 3 frames after.
6. **Other ten figures** follow the cleaned model tracks unverified frame by frame (`g2/figure-tracks-smooth.json`).
   In goal 2 the shot grazes the E goalie (179 mm/s) on its way into the corner.

## Method

**Frames.** `scripts/edwall-frames.py <goal>` decodes the broadcast around each label, registers every frame to the game's
reference frame and writes the E half at 2x (`out/edwall/<goal>/`, not committed).

**Puck readings** (`shots/edwall/puck-readings.json`, by hand, crop pixels of the registered E half): rest (puck still
against the near board), streak (motion-blurred, centre of the streak), flight (sharp), hidden. Back-projected to the plane
z = 6 mm (half the assumed puck thickness) with the calibrated camera (`camera-ref.json`). The near board's top edge
(about 25 mm high) hides the ice right at the board, so a puck resting against the board reads about 40 mm too far from
it (y about -180 instead of -222). The rest position is therefore snapped to just inside the canonical board line, and
the rest readings are reported but not fitted. Free flight reads about 1.1-1.2 m/s at about 66 degrees; the streak frames
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
RENDER_NOTES

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

- Model the stick's heel groove at puck height and replace the kinematic carry by a push in that pocket.
- A puck detector track (or a second camera) for the last 5 frames, where the shot is hidden.
- The user's review of the goal-3 label and of the passer's lunge in goal 2.
