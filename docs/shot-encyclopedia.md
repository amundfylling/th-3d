# Shot encyclopedia: groundwork for cheap, fast and accurate move videos

Status: PROPOSED (2026-10-10). The user chose the shot encyclopedia as the priority (`docs/vision.md` item 2): "do the
groundwork now so that it will be cheap, fast and super accurate animations in the future". Nothing here is
user-reviewed; the one new move (Hjerpefinte) is Claude's reading of a one-line NTHF text.

## 1. What was built

| Part | Where | What it gives |
| --- | --- | --- |
| Move engine | `scripts/shotlib/` (`world`, `motion`, `puck`, `build`, `robustness`, `presentation`) | One code path for every designed move: figure motion → puck by the contact rules → every CLAUDE.md check → `shot-trace/1`. Replaces copying a 300-500 line script per move. |
| Move files | `moves/<id>/move.json` | A move is data: figure keyframes and moves, the puck's start, named contacts, expectations, the video story. |
| Build command | `scripts/build-move.py` | Builds in about 7 s on any Python with numpy, shapely and pillow; saves only if every check passes. |
| Contact footprints | `data/figures/contact-footprints.json` (`scripts/shotlib/export_footprints.py`) | The figure geometry the puck can touch, exported once from the molds. No Blender or mesh files needed to build a move; one place to update when the figures are measured. Records the hashes of the mold data, the mesh-building code, the scale and puck files and the generated meshes; the engine and tests refuse a stale file. |
| Robustness check | `scripts/shotlib/robustness.py`, `--robustness` | Reruns the move with each uncertain input changed and reports whether the goal and contact sequence hold. |
| Generated video | `scripts/shotlib/presentation.py`, `--video-spec`; `remotion/EncyclopediaAnalysis.tsx`, `remotion/encyclopedia-registry.ts` | The analysis video (same template as the five hand-made ones) from a short `story` block: timeline, slow-motion rates, camera views, chapters and graphics are derived from the trace. Composition `move-<id>`. |
| Index | `data/encyclopedia/index.json` (`scripts/encyclopedia-index.py`) | All 121 NTHF combinations with their stage (not started, move file, trace, video), a family (keyword heuristic), NM26 goal count and a suggested build order. |
| Tests | `tests/encyclopedia.test.ts` | Every built move is tested automatically: checks, robustness, TypeScript playback equals the engine, video spec, registry. |

Changed shared files (small): `remotion/Root.tsx` (registers the `move-*` compositions), `scripts/analysis-render.ts`
(`move:<id>` renders an encyclopedia video).

## 2. Workflow for a new move

1. **Reading.** Read the NTHF text (`data/combinations/nthf-catalogue.json`, `docs/table-hockey-playbook.md`). For
   anything not obvious, show the user a sketch and get the reading approved before tuning (as IKV:
   `approved_reading`). A move is `accepted` only with an approved reading (enforced by the tests).
2. **Move file.** Copy the closest existing move (`moves/hjerpefinte/move.json` for a single figure). Set the figures'
   start poses, turns and slot moves, the puck's start (`against` a figure part, or `at_mm`), the named contacts and
   `expect` (goal, goal-line window, contact sequence).
3. **Tune.** `scripts/build-move.py <id> --quick --set figures.W-C.theta.turns.0.3=205 ...` prints the goal and the
   contact groups in seconds without writing anything. Hjerpefinte took about 15 such runs.
4. **Build and check.** `scripts/build-move.py <id> --robustness --video-spec`. It saves `data/traces/<id>.trace.json`,
   `shots/<id>/checks.json`, `validation/moves/<id>-sheet.png` (review sheet), the robustness report and the video spec
   only when the contact, slide and expectation checks pass.
5. **Render.** `node scripts/analysis-render.ts move:<id>` (needs `npm run remotion:assets` once) →
   `validation/moves/<id>.mp4` and its report; `COMP=move-<id> node scripts/analysis-stills.ts 0.5 <frames>` for quick
   stills first.
6. **Index and tests.** `python3 scripts/encyclopedia-index.py`, `npm test`.

## 3. Move file format (`move-spec/1`)

```jsonc
{
 "schema": "move-spec/1", "id": "hjerpefinte", "name": "...", "nthf": {"name": "Hjerpefinte", "player": "Centre", "level": 2},
 "trace_id": "trace.hjerpefinte.v1", "status": "proposed", "kind": "designed",
 "source_text": "...", "approved_reading": null, "window_s": [0.0, 0.7],
 "physics": {"restitution_figure": 0.5},                    // optional; defaults in scripts/shotlib/build.py
 "puck": {"start": {"against": "W-C", "local_mm": [-10.0, 26.8]}, "start_phase": "on_the_blade"},
 "figures": {                                               // figures not named stand in the static assembly pose
  "W-C": {"arc":   {"keys": [[t, arc_mm, why]], "moves": [[t0, t1, a0, v0, a1, v1, why]]},   // quintic slot moves
          "theta": {"start": 181.0, "turns": [[t_start, duration, from, to, why]]},          // smootherstep turns
          "follow_tangent_from_s": null},                   // optional: the player turns the figure with the slot
  "E-G": {"static": {"y_mm": 28.0, "theta_deg": 0.0, "why": "..."}}
 },
 "contacts": [{"id": "shot", "figure": "W-C", "group": -1, "min_touches": 5}],   // which touch group is which
 "expect": {"goal": "E", "goal_y_mm": [-28.7, -8.0], "contact_sequence": ["W-C:stick/blade", "goal_net"]},
 "events": [{"id": "turn.onset", "t": 0.1}],
 "story": {...},                                            // video text (scripts/shotlib/presentation.py)
 "limitations": ["..."]
}
```

Angles are degrees relative to the team's home heading, arcs mm along the slot, times s. Every keyframe carries its
`why`, which the trace keeps as the keyframe source. `triggers` (start a figure's motion when the puck comes near a
point, crosses a line or a contact starts or ends) are implemented but experimental; see section 5.

## 4. Results

**The engine reproduces the hand-built IKV trace exactly** (`moves/invers-kryssar-velodrom/move.json` is the port of
`shots/invers-kryssar-velodrom/inputs.json`): 4,701 puck nodes, every figure keyframe, difference 0.0 mm
(`validation/moves/invers-kryssar-velodrom-equivalence.json`). The saved IKV trace stays the one its own script writes;
the port is only compared with it.

**New move: Hjerpefinte** (centre, level 2; `moves/hjerpefinte/`). The centre stands at the front of its slot with its
back to the goal, the puck resting on the blade to the right of the slot. A 70 ms counter-clockwise turn (181 → 205°)
with a 14 mm step pushes the puck from rest into the right corner (goal line at y = −18.7 mm, 575 mm/s).
- Checks: no overlap; one contact, a push of 65 small touches with a peak impact of 33 mm/s; no unexplained motion change.
- Robust in 11 of 11 variants; the goal-line crossing moves by 0.4 mm at most.
- Sheet `validation/moves/hjerpefinte-sheet.png`. Video `validation/moves/hjerpefinte.mp4` (631 frames, 21.0 s,
  1920x1080 30 fps, 7.96 MB; rendered in about 35 min on CPU; rerender with `node scripts/analysis-render.ts
  move:hjerpefinte`). Its report `validation/moves/hjerpefinte-video-report.json` finds every frame equal to the pure
  evaluation of the trace. Frames of the mp4 were checked: rewind, slow-motion approach, contact freeze with the push
  arrow, replay.
- The goalie leans to the left post (assumed: "only works against a goalie expecting a Hjerpe"). The reading is Claude's
  and needs the user's approval.

**Finding: the IKV v2 trace only works with its exact inputs.** The robustness run
(`validation/moves/invers-kryssar-velodrom-robustness.json`) scores in 1 of 11 variants: the nominal one.
- A change of 0.001 mm in the figure geometry, 0.2 mm in the puck's start, 2% in the figure scale, 25% in the ice
  friction or a restitution of 0.3 or 0.7 each make it miss the goal or break the slide limits.
- Cause: the move is a long open-loop chain (pass, catch, push round the corner, velodrome, first-time shot). Each figure
  moves on a fixed clock, and the frictionless restitution-0.5 push makes many micro-bounces whose pattern changes with
  tiny inputs. Errors grow along the chain until the right wing's shot meets the puck at the wrong time.
- It was found when the first footprint export, rounded to 0.000001 mm, already changed IKV's outcome.
- Reactive timing (the receivers start when the puck arrives, `triggers`) was tried on IKV and did not make it robust
  (0 of 11): the push chaos changes where the puck is, not only when.
- Single-contact moves from rest (Hjerpefinte) are robust. The shovels and Edwall moves sit in between: a carry and a
  pass to a waiting centre.

## 5. What makes future moves cheap, fast and accurate

**Cheap and fast (done):** a move is a data file; building, checking and the review sheet take seconds; the video spec
is generated; tests come for free. What still costs time: the reading (the user's approval) and tuning a chain of
contacts by hand, and the render (about 4 s per 1080p frame on this CPU; an analysis video is 15-35 s long).

**Accurate: three steps, in order of value.**
1. **Robustness as a gate (done as a report; make it a requirement).** A move whose outcome depends on 0.001 mm is not
   an explanation of how the move works. Proposal: a move is saved only if it is robust, unless the user accepts it.
2. **Solved receptions instead of clocked ones (next).** For any contact with a moving puck (catch, first-time shot,
   push after a board run), solve the receiving figure's slot position and heading so its blade meets the puck where
   the move file says (a point on the blade, a give-way speed), as iteration 22 did for the Shovel's foot drag. The
   chain then cannot drift: each contact starts from where the puck really is. This replaces hand-tuned timings, which
   is also the main remaining cost.
3. **Contact model and measurements.** The push model (frictionless, restitution 0.5) is assumed. A sustained push
   should keep the puck against the blade (a low-speed inelastic contact was tried and changes IKV; it needs the user's
   view and a test against the board-pass example clip). The robustness report shows which inputs a move is sensitive
   to; measuring those first is the cheapest accuracy gain:
   - the blade's position and width relative to the pivot (the footprints are AI-modelled at the preview scale);
   - the puck's diameter and thickness;
   - the ice friction (a slow-motion clip of a sliding puck on the user's table, as the spjass fit);
   - the goal mouth and post positions.
   Re-export `data/figures/contact-footprints.json` after any mold change; the engine refuses a stale file.

## 6. The index and what to build next

`data/encyclopedia/index.json`: 121 moves; 3 with a video from the earlier scripts (Spjass, Näcka, IKV), 1 with an
engine video (Hjerpefinte), 117 not started. Suggested order (NM26 goals first, then easy before hard):
Edwallskyffel lang (5 NM26 goals), Spade (3), Spjass (2, done), then the level-2 moves (Edwall-innspill,
Lindahl-innspill, Sørenfinte) and the level-3 ones (Direkteskudd, Lillstøvel, Maltzev).
- "Short centrifuge" and "Ceuleman" are user goal labels that are not catalogue names; they are listed separately.
- The family is a keyword heuristic; a few are wrong (Fakie Forulemping is a right-wing shot that starts behind the
  goal) and should be corrected with the user's labels.

## 7. Open

1. Approve or correct the Hjerpefinte reading (the review sheet and the video).
2. Should robustness be a hard gate for saving a move?
3. Should IKV v2 be redesigned with solved receptions, or kept as it is with its fragility noted?
4. The "Slide or bounce" limits and the push contact model are still assumptions (CLAUDE.md).
5. The rotation-arrow graphic in the generated video uses default angles; per-move tuning may be needed for some moves.
