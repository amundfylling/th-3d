# Goals and goalie routes (iteration 08)

**Status:** provisional pixel data, reviewed by AI only (no personal user approval).
Overlay: `validation/08-goals-and-goalies.svg`. Numbers: `validation/goals-report.json` and
`validation/slots-report.json`. Scripts: `scripts/trace-goals.ts` (`npm run trace:goals`, run after
`npm run trace:slots`) and `scripts/render-goals-overlay.ts`.

## Goalie routes

- **W-G** (Finland) and **E-G** (Sweden) each run in their own short slot in the crease, in front of their goal. They use the goalie rod 7111-9083-02, not a skater path.
- Both slots run about 3° off the image vertical, in the same direction, in both photographs. That fits the rink's 180° rotational symmetry.
- **Hidden ends:** the W-G lower end and the E-G upper end are under the goalies. The tracer does not search past hidden ends. The observed end is the last clear cross-section, and the bare sheet predicts the rest: +22 px for W-G, +128 px for E-G.
- **Partial cover:** below y ≈ 2785 the W-G slot is half covered by the goalie's pad. The trace there follows the measured slot line and is interpolated.
- **Difference between the references:** after the homography, the mapped bare goalie slots sit about 7 px toward the rink centre in *both* goals (RMS 12.0 / 10.4 px). Neighbouring slots agree within 1–4 px. The cause is unresolved: an older sheet version, or the slot wall being visible. The goalie slots are excluded from the homography fit, with the reason recorded in `data/slot-seeds.json`.

## Goal regions (per goal: `goals[].image_trace_ids`, `landmark_ids`)

| Feature | Trace | Plane | Result |
| --- | --- | --- | --- |
| Ice-sheet cut-out behind the goal line | `trace.goal.<T>.cutout.bare` (traced), `...cutout.overhead` (mapped, `assumed`) | ice | 42–45-vertex polygons. The mapped front edge sits on the goal line: W −8.2 px, E +5.6 px. That is an independent check of the homography near the goals. |
| Red cage outline | `trace.goal.<T>.cage.overhead` | **elevated** | Convex hull of the red cage pixels. It is not a footprint. |
| Post tops | `lm.goal.<T>.post_top.pos_y/neg_y` | **elevated** | Mouth between the post tops: W 504.6 px, E 484.1 px. The post tops sit outward of the goal lines by 15–24 px (W) and 52–66 px (E), which fits the perspective displacement of elevated points. The W/E asymmetry is unexplained. |
| Space behind the goal | report | ice | Board to the back of the cut-out: W 497.7 px, E 503.2 px. Board to the cage back (elevated): 461–471 px. |

In the reference photos no white insert is visible. The dark area inside each cage is the ice
cut-out seen through the cage.

## Goal configuration

`goal_setup.configuration = ithf_no_insert_no_cup`. This is the user's statement (docs/decisions.md D5):
without the white insert/deflector (7111-0526-11) and without goal cups, with the plexiglass screens
kept. The retail alternative stays in `candidates`.

## Unresolved (unknown in mm)

- Goal opening width and height, post and crossbar size, cage depth, and where the goal stands relative to the goal line at ice level.
- Cut-out size.
- Goalie pivot position and offset, goalie travel stops and rotation limits.

## Inventory

- **Routes:** 10 outfield and 2 goalie routes are now traced in pixels in both photographs. That does **not** establish their measured usable travel.
- **Unknown for all 12:** `usable_stops`, `fixture_axis_path` and the rotation limits (docs/tracks.md, "Where usable travel still needs a hardware recording").
