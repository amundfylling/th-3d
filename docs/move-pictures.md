# Move pictures: the puck.no pictures recreated on our rink

Status: PILOT, PROPOSED (2026-10-13), waiting for the user's review of `validation/move-pictures/pilot-comparison.jpg`.

The user asked to recreate the puck.no move pictures (green arrows, numbered contacts) before animating every move,
without the explanatory text the analysis videos carry. Pilot: five visibly different centre moves.

| move | level | what it shows | source of the arrows |
|---|---|---|---|
| Näcka | 4 | centre trick (heel pass, shot) | the saved trace `data/traces/nacka.trace.json` (PROPOSED) |
| Agdur | 6 | give-and-go with the left wing | puck.no picture |
| Veggdyr | 6 | off the boards and back | puck.no picture |
| Senter-Velodrom | 7 | velodrome round the goal to the right wing | puck.no picture (board run computed) |
| Senterkniv | 7 | pass back to the left defender, long shot (full rink) | puck.no picture |

## How a picture is made

`npm run pictures:moves` (or the three steps in `scripts/move-pictures/build.py`'s docstring).

1. `data/move-pictures/<id>.json`: the contacts read off the puck.no picture (picture px), which figure touches the
   puck at each, which of them is drawn, the arrow path (straight, or `via: boards`), the end point in the goal.
   `formation.json`: where every other figure stands (read off the puck.no pictures, which all use one layout) and the
   picture-to-world mapping (goal line, blue line and face-off circles; 1.054 px/mm).
2. `build.py`: a contact by a figure is snapped to its blade. The figure is turned to face where the puck goes next
   (front of the blade pushing) and moved along its slot until the blade middle is as close to the picture's point as
   the slot allows; turning away from the push costs 0.15 mm per degree, the backhand 2 mm. The miss and the turn are
   printed and saved in `out/move-pictures/<id>-geometry.json`. Board runs follow the inner boards offset by the puck
   radius. A move may move a bystander out of a lane (`figures`, with the reason).
3. `render.ts`: the rink straight from above with the pose-preview composition (same pose code as every video; the
   composition now takes `widthPx`, `heightPx`, `background`). The puck is drawn at contact 1.
4. `build.py --draw`: rotated so the attacking goal is up (no mirroring: the attackers' left is on the left, as on
   puck.no), green arrows, navy numbered circles at the contacts, the 0-9 level scale with the level boxed in NBHF
   red (docs/theme.md colours). No other text.

Like puck.no, a figure is drawn once (at its first touch); a later touch by the same figure (Agdur 3, Veggdyr 2)
is a numbered point without a figure.

## What is assumed or differs from puck.no

- The arrows are illustrations, not checked traces (no contact or slide check). Veggdyr's rebound off the boards
  would be a bounce under the slide rule; the picture shows it anyway because puck.no does.
- Agdur contact 3: the centre's blade cannot reach the picture's point; it is snapped 12.7 mm away.
- Poses are chosen by the snapping rule, not by the real technique (except Näcka, from its trace). Senter-Velodrom's
  right wing and Senterkniv's centre play backhand to reach the picture's points.
- Bystanders moved out of a lane: Veggdyr's right wing (puck.no's arrow runs through it), Senterkniv's opposing centre.
- Veggdyr: the NTHF text says the LEFT boards; the puck.no picture plays it off the RIGHT boards. Ours follows the
  picture. To ask the user.
- Our slots are the user's table (geometry.json), so the figures stand on slightly different lines than puck.no's
  drawing.

Sources: `references/combinations/puck-no-pictures/` (all 51 pictures, fetched 2026-10-13, index entry
`puck_no_move_pictures`).
