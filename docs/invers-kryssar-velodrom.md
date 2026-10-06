# Invers Kryssar med Velodrom (right wing): designed trace and analysis video

Status: sketch approved by the user and animated on 2026-10-06 (user: "Do this one without an illustration ... Give
me a photo of how you interpret it to look with lines before implementing the animation", then "The picture is
correct. Implement animation"). Not a numbered iteration. The trace `trace.invers-kryssar-velodrom.v1` is
**proposed**.

| Item | Path |
| --- | --- |
| Source (preserved, indexed) | `references/combinations/puck-no-invers-kryssar-med-velodrom.html` (no illustration or video), `puck-no-invers-kryssar.html` (the base move) |
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

## How the motion is made

The figure motions are designed. The puck follows from them through contacts, ice friction and the boards. Every
0.25 ms:
- **Ice friction:** a constant deceleration (the spjass slide fit, 926 mm/s²).
- **Figure contact:** where any figure would overlap the puck, the puck is moved out to touching along the contact
  normal. If it approaches the figure's surface there (the surface velocity comes from the figure's pose change), it
  takes a collision impulse with restitution 0.5. The impulse is frictionless.
- **Boards, posts and cage:** moved out to touching with the normal velocity removed, so the puck slides along them.
  This is what carries it round the velodrome.
- **Goal:** the cage is open only at the mouth, and the back net stops the puck.

The trace:

| Time | Event | Part | Puck after |
| --- | --- | --- | --- |
| 0.237 s | cross pass | front of the right wing's blade (clockwise sweep 100° → 30°) | 1.69 m/s at 53° |
| 0.470 s | velodrome pass | back of the left wing's blade (counter-clockwise sweep 110° → 195°) | 4.69 m/s at −15° |
| 0.50–0.90 s | velodrome | boards: the +y corner, behind the goal (x ≥ 409.5 mm, cage back at 338 mm), the −y corner | slides on along the −y board, slowing |
| 0.50–1.05 s | — | the right wing moves 105 mm down his slot (to slot position 35 mm) and turns round to 204° | — |
| 1.555 s | first-time shot | back of the right wing's blade (counter-clockwise sweep 204° → 262°) | 1.61 m/s at 35.7° |
| 1.802 s | goal | crosses the goal line at y = −8 mm (mouth window ±29 mm) | — |
| 1.836 s | net | stops against the back of the cage | 0 |

**Checks** (`shots/invers-kryssar-velodrom/checks.json`). The finite puck is checked against all 12 figures, the
boards, the posts and the cage every 0.25 ms:
- no overlap and no exception;
- no unexplained velocity change;
- contact sequence: right wing's blade → left wing's blade → boards → right wing's blade → net;
- closest approaches on the shot: goalie 6.8 mm, near post 14.0 mm.

## Deviation from the sketch: the catch point

In the sketch, the right wing receives about 18 cm from the goal line (slot position 215 mm). The trace showed this
cannot work with our figures:
- The velodrome brings the puck pressed against the −y board, 37 mm from the right wing's slot.
- Only the board-side face of his blade can reach it there, and that face can send the puck off the board at no more
  than about 30–35°.
- From 18 cm the goal needs about 65°. A hit with the end of the blade just sends the puck back along the board, and
  every tried variant failed.

From further back the angle fits. The right wing therefore receives near the centre line, at slot position 35 mm,
moving down his slot instead of up. The shot becomes a long first-time diagonal into the near half of the goal. The
rest of the reading is unchanged.

## Assumptions to review (most important first)

1. **The catch point** (above): near the centre line instead of near the goal.
2. **The goalie stands toward the left post** (y = +20 mm, as if drawn there by the cross pass). In the assembly pose
   the shot still goes in, but only after touching his stick and the post.
3. **The left wing's pass is very hard** (4.7 m/s). The puck must survive the whole circuit against the measured ice
   friction and still reach the right wing.
4. **All timing and figure motions are designed**, since no recording exists.
5. **The collision rule** (restitution 0.5, frictionless; inelastic boards), the figure, stick and puck sizes, and the
   preview goal are assumptions.

## Analysis video

Same structure as the other analysis videos (27.3 s):
1. **Intro (0–4.8 s):** title, the whole move at full speed (it takes 1.8 s), GOAL, rewind.
2. **Chapter 1, "THE CROSS PASS" (4.8–9.1 s):** the right-wing highlight and the pass arrow.
3. **Chapter 2, "THE VELODROME" (9.1–15.7 s):** the left-wing highlight, "PASS · BACK OF THE BLADE" and its
   direction. Then the velodrome at ×0.5 from a high view, with a puck trail.
4. **Chapter 3, "THE FIRST-TIME SHOT" (15.7–21.9 s):** the right wing's SWEEP and "SHOT · BACK OF THE BLADE", the
   shot at ×0.3, then GOAL.
5. **Replay ×0.7 and summary card (21.9–27.3 s).**

The puck is visible in every frame (ray-cast against the real figure meshes, `validation/analysis-ikv-occlusion.json`).
Captions get at least 3.5 s with a still camera, and camera steps stay under 60 mm per frame (`tests/ikv.test.ts`).
