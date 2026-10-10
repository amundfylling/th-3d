# Invers Kryssar med Velodrom (right wing): designed trace and analysis video

Status:
- **v1**: the sketch was approved and animated on 2026-10-06. The user asked: "Do this one without an illustration ...
  Give me a photo of how you interpret it to look with lines before implementing the animation", then said "The
  picture is correct. Implement animation".
- **v2** (2026-10-06): the left wing's pass was redesigned after the user's feedback on v1. The user said: *"the way
  that the left wing shoots the puck, it would actually bounce ... it has to ... not flick the puck, but ... move it
  standing forward, forward facing, and then pushing the puck towards the [curve] on the left side"*. They sent an
  example clip "for the physics" (a different combination).
- Not a numbered iteration. The trace `trace.invers-kryssar-velodrom.v2` is **proposed**.

| Item | Path |
| --- | --- |
| Source (preserved, indexed) | `references/combinations/puck-no-invers-kryssar-med-velodrom.html` (no illustration or video), `puck-no-invers-kryssar.html` (the base move) |
| Physics example (user upload, indexed) | `references/shots/lw-board-pass-example.mov`: a different combination, used only for how a board pass is played |
| Approved reading | `validation/ikv-sketch.png`; `shots/invers-kryssar-velodrom/sketch.json`, `sketch-geometry.json` (`scripts/ikv-sketch.py`, `scripts/ikv-sketch-render.ts`, composition `pose-preview`) |
| Design choices | `shots/invers-kryssar-velodrom/inputs.json` |
| Trace | `data/traces/invers-kryssar-velodrom.trace.json` (`scripts/ikv-trace.py`); checks `shots/invers-kryssar-velodrom/checks.json`; top view `validation/ikv-trace.png` |
| Analysis spec | `data/presentations/invers-kryssar-velodrom.analysis.json` |
| Composition | `analysis-ikv` (`remotion/IkvAnalysis.tsx` + the shared `remotion/AnalysisVideo.tsx`) |
| Video | `validation/analysis-ikv.mp4`; report `validation/analysis-ikv-report.json`; review sheet `validation/analysis-ikv-review.png`; puck visibility `validation/analysis-ikv-occlusion.json` |
| Tests | `tests/ikv.test.ts` |

Reproduce: `npm run trace:ikv`, then `npm run video:analysis-ikv` (about 75 min on the 4-CPU container).

## Source and reading

The NTHF description (right wing, difficulty 7/10): *"Pass from right wing to left wing, who passes along the boards
behind the goal to the right wing, who shoots directly into the goal."* The base move "Invers Kryssar" is *"Pass from
right wing to left wing, who shoots into the left corner"*.

Approved reading (sketch):
1. **Cross pass:** the right wing passes across the ice to the left wing at the far board.
2. **Velodrome:** the left wing sends the puck along the boards. It rides the curved boards round behind the goal and
   comes out along the right wing's board.
3. **Shot:** the right wing, who has moved and turned round meanwhile, shoots it first time into the goal.

## What changed in v2, and why: slide or bounce

In v1 the left wing waited turned with its blade in the pass lane and swept the back of the blade through the
arriving puck. That was an impulsive strike: about 2.9 m/s relative speed at impact, sending the puck into the corner
at 4.7 m/s. The user judged that a real puck would bounce there, not slide.

The example clip (`references/shots/lw-board-pass-example.mov`, frames 42-118, top-down) shows how a board pass is
played:
- The yellow left wing travels along its curved slot into the corner with the puck in front of its blade.
- The blade guides the puck along the curved board.
- The puck then runs down the end board behind the goal, round the far corner and along the side board to the right
  wing.
- Puck speeds were read with an uncalibrated scale (about 2.4 px/mm from the board-to-board width): about 1.0 m/s along
  the end board just after the corner, and 0.7 → 0.5 m/s along the far side board.
- The puck never jumps; every change of direction is a push or a glancing board contact.

This became a project rule (`CLAUDE.md`, "Slide or bounce"). It is checked in `checks.json` → `slide_check`:
- every figure contact must meet the puck at a relative normal speed of at most 500 mm/s;
- every board, post or cage contact at most 300 mm/s;
- both limits are assumed values, to be reviewed with the user.

v1 fails this check (2882 mm/s at the left wing). v2 passes with a wide margin.

## How the motion is made

The figure motions are designed. The puck follows from them through contacts, ice friction and the boards. Every
0.25 ms:
- **Ice friction:** a constant deceleration (the spjass slide fit, 926 mm/s²).
- **Figure contact:** where any figure would overlap the puck, the puck is moved out to touching along the contact
  normal. If it approaches the figure's surface there (the surface velocity comes from the figure's pose change), it
  takes a collision impulse with restitution 0.5. The impulse is frictionless.
  - A push is therefore a run of small touches. Each one is recorded with its impact speed.
- **Boards, posts and cage:** moved out to touching with the normal velocity removed, so the puck slides along them.
  Each normal speed removed is recorded.
- **Goal:** the cage is open only at the mouth, and the back net stops the puck.

Figure motions are smooth moves (quintic arc moves, smootherstep turns; `inputs.json`). From 0.68 s the left wing's
rod turn follows its slot through the curve. This is a designed rotation, not an automatic one (rule 6), so the blade
stays square to the curved board.

The trace:

| Time | Event | Part | Impact | Puck after |
| --- | --- | --- | --- | --- |
| 0.150-0.190 s | cross pass | front of the right wing's blade: the puck rests against it and a clockwise turn 72° → 20° pushes it | 42 mm/s | 0.96 m/s at 65° |
| 0.48-0.68 s | the left wing faces the pass (theta −90°) and turns counter-clockwise to face forward | — | — | — |
| 0.654 s | soft catch | front of the left wing's stick, low on the shaft above the heel, as the turn gives way | 166 mm/s | 0.55 m/s at 39° |
| 0.813 s | to the board | the +y board, glancing | 255 mm/s | slides along it |
| 0.73-0.92 s | the left wing skates up its slot after the puck and meets it just faster than it slides | — | — | — |
| 0.922-1.158 s | forward push | front of the left wing's blade, 277 touches, up the slot and through the curve (1.107 s: figure heading −44°, puck 1.12 m/s) | 61 mm/s first, 93 peak | 1.31 m/s at −90° (along the end board) |
| 1.16-1.76 s | velodrome | behind the goal (x = 409 mm, cage back at 338 mm), the −y corner, the −y board; 607 mm of board | ≤ 142 mm/s | slowing to 0.66 m/s |
| 1.50-1.83 s | the right wing (turned round to 204° from 1.0 s) slides down his slot ahead of the puck, at 450 mm/s when it arrives | — | — | — |
| 1.829-1.848 s | first-time shot | back of the right wing's blade, giving way, then a counter-clockwise turn 204° → 275° | 227 mm/s | 1.18 m/s at 43° |
| 2.145 s | goal | crosses the goal line at y = 0.0 mm (mouth window ±29 mm) | — | — |
| 2.197 s | net | stops against the back of the cage | — | 0 |

**Checks** (`shots/invers-kryssar-velodrom/checks.json`). The finite puck is checked against all 12 figures, the
boards, the posts and the cage every 0.25 ms:
- no overlap and no exception;
- no unexplained velocity change;
- slide check passed: figure contacts peak at 227 mm/s (limit 500), boards at 255 mm/s (limit 300), posts and cage are
  never touched;
- contact episodes: right wing's blade → left wing's stick → board → left wing's blade (with the board) → boards →
  right wing's blade → net;
- closest approaches on the shot: goalie 5.4 mm, nearest post 17.2 mm.

## Deviations from the sketch

- **The left wing receives further out and carries the puck into the corner.** In the sketch it stands in the corner
  and plays the puck on. In v2 it receives at slot position about 106 mm (near the blue line) and pushes the puck up
  the slot and through the curve. This is the forward-facing push the user asked for.
- **The catch point of the right wing.**
  - In the sketch he receives about 18 cm from the goal line.
  - Along the −y board the puck is 37 mm from his slot, so only the board-side face of his blade can reach it, and the
    puck can leave the board at only about 35-45°.
  - In v2 he receives at slot position 97 mm, about 26 cm from the goal line (v1: near the centre line).
  - The shot is a diagonal into the middle of the goal.

## Assumptions to review (most important first)

1. **The slide-or-bounce limits** (500 / 300 mm/s) are Claude's numbers for the user's rule.
2. **The left wing's catch:** it turns from facing the pass to facing forward as the puck arrives, and the puck meets
   the low part of the stick above the heel. The catch and the push timing are designed.
3. **Release speed 1.3 m/s.** That is faster than the example's (uncalibrated) 1.0 m/s, because our ice friction (from
   the spjass fit) is higher than the example suggests. The puck has to reach the right wing.
4. **The goalie stands toward the left post** (y = +20 mm, as if drawn there by the cross pass).
5. **All timing and figure motions are designed**, since no recording exists.
6. **The collision rule** (restitution 0.5, frictionless; inelastic boards), the figure, stick and puck sizes, and the
   preview goal are assumptions.

## Analysis video

Same structure as the other analysis videos (29.7 s, 892 frames):
1. **Intro (0-5.0 s):** title, the whole move at full speed (2.15 s, from a high broadcast view), GOAL, rewind.
2. **Chapter 1, "THE CROSS PASS" (5.0-9.6 s):** the right-wing highlight and the pass arrow.
3. **Chapter 2, "THE VELODROME" (10.2-19.6 s), seen from above the end board:**
   - the soft catch (TURNS TO FACE FORWARD, SOFT CATCH);
   - the push at ×0.25, with the slot arrow;
   - a freeze in the middle of the curve (PUSH · FRONT OF THE BLADE);
   - the velodrome at ×0.6 from a high view, with a puck trail.
4. **Chapter 3, "THE FIRST-TIME SHOT" (20.1-25.1 s):** TURN and "SHOT · BACK OF THE BLADE", the shot at ×0.4, then
   GOAL.
5. **Replay ×0.9 and summary card (25.1-29.7 s).**

The puck is visible in every frame: sight lines are ray-cast against the real figure meshes
(`validation/analysis-ikv-occlusion.json`). The first v2 camera for the push looked past the left wing, whose body hid
the puck. The view now looks from above the end board, in front of the figure. Captions get at least 3.5 s with a
still camera, and camera steps stay under 60 mm per frame (`tests/ikv.test.ts`).
