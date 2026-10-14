# Move pictures: the puck.no pictures recreated on our rink

Status: PROPOSED (2026-10-13). All 51 puck.no pictures recreated in the tilted view the user chose (angle 2):
`validation/move-pictures/<id>.png`, side by side with puck.no in `validation/move-pictures/comparison/page1-8.jpg`.

The user asked to recreate the puck.no move pictures (green arrows, numbered contacts) before animating every move,
without the explanatory text the analysis videos carry. Pilot: five visibly different centre moves (below). After the
angle study the user chose the tilted view and asked for all combinations: the other 46 specs were written from the
puck.no pictures (contacts, figures, arrow paths) and every picture was redrawn tilted. The 70 NTHF moves that have no
puck.no picture (66 right-wing and 4 centre moves) are not drawn.

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
3. `render.ts`: the rink with the pose-preview composition (same pose code as every video; the composition takes
   `widthPx`, `heightPx`, `background` and a perspective camera). Camera: overhead tilted 20 deg toward the attackers'
   end, goal up (no mirroring: the attackers' left is on the left, as on puck.no). Three framings by how much of the
   rink the move uses: `half` (x 68-446 mm), `mid` (x -95-446) and `full` (whole rink). The puck is drawn at contact 1.
4. `build.py --draw`: the arrows and circles projected with the same camera (matches three.js), green arrows, large navy numbered circles at the contacts (a circle steps aside when the arrow is too short to show, as in Näcka), the 0-9 level scale with the level boxed in NBHF
   red (docs/theme.md colours). No other text.

Spec features added for the full set: unnumbered contacts (`{"id", "kind": "board"|"point"}`, e.g. a board touch or
puck.no's plain dots), `via` points and `"boards"` in a path segment, goal segments with their own end point, `toward_px`
for the facing, `snap: false`, per-move figure overrides, and `index_id` for moves whose file id is ASCII (Lillhæl ->
lillhael, Lillstøvel, Søren). Spjass is read from its saved trace (`data/traces/spjass.trace.json`) like Näcka.

Like puck.no, a figure is drawn once (at its first touch); a later touch by the same figure (Agdur 3, Veggdyr 2)
is a numbered point without a figure.

## What is assumed or differs from puck.no

- The arrows are illustrations, not checked traces (no contact or slide check). Veggdyr's rebound off the boards
  would be a bounce under the slide rule; the picture shows it anyway because puck.no does.
- Contacts the blade cannot reach exactly (snapped more than 9 mm from the picture's point): Agdur 3 (12.7 mm),
  Horvath 2 (11.7), Lillstøvel 2 (12.0), Omvendt spjass 2 (9.8), Senter-backnäcka 3 (10.7).
- Poses are chosen by the snapping rule, not by the real technique (except Näcka, from its trace). Senter-Velodrom's
  right wing and Senterkniv's centre play backhand to reach the picture's points.
- Bystanders moved out of a lane: Veggdyr's right wing (puck.no's arrow runs through it), Senterkniv's opposing centre.
- Text and picture disagree (ours follows the picture; to ask the user):
  - Veggdyr: the NTHF text says the LEFT boards; the picture uses the RIGHT boards.
  - Fakie-Veggdyr: the text says the right boards; the picture uses the left.
  - Fakie-invers-halv-Agduro: the text passes to the right wing; the picture to the left wing (unnumbered dots).
- Our slots are the user's table (geometry.json), so the figures stand on slightly different lines than puck.no's
  drawing.

Sources: `references/combinations/puck-no-pictures/` (all 51 pictures, fetched 2026-10-13, index entry
`puck_no_move_pictures`).

## Camera-angle study (2026-10-13)

The user asked whether another angle would be better and wanted one Näcka picture per suggested angle (images, not
video): `validation/move-pictures/angles/nacka-{overhead,tilted,oblique,goalie}.png`, side by side in
`nacka-angles.jpg`. Composition `angle-study` (`remotion/AngleStudy.tsx`, the saved Näcka trace through the usual
gate), rendered by `node scripts/move-pictures/angles.ts` (last frame, 1920x1080; `--video` renders the slow-motion
clip instead). The arrows are projected from the puck path on the ice, so they are drawn over figures in the 3D views.

## Moves without a puck.no picture (2026-10-13)

The user asked for pictures of the 70 NTHF moves that have no puck.no picture (66 right-wing moves and 4 centre
fakie tricks). Their specs (`data/move-pictures/<id>.json`, `"source": "designed from the NTHF text"`) were written
from the NTHF description alone, with the same contacts, arrows and figure snapping as the redrawn pictures:
- Contacts are placed on the figures' real slots (W-RW in its slot, passes to the centre's usual shooting spot, the
  defenders and goalie in their slots). "Left corner" and "right corner" are seen from the attackers.
- A carry (the same figure touching the puck twice in a row) is drawn as a short arrow; the figure stands where it
  releases the puck, and the puck where the carry starts.
- An innspill ends at the receiving centre (no goal arrow); `build.py` now allows a path without a goal.
- "Behind their own goal" runs along the bottom boards (via the point behind the own goal); "Jorda rundt" goes all the
  way round with board waypoints.
- The fakie centre tricks (Fakie-Lillstøvel, -Näcka, -Omvendspjass, -Spjass) start from the other groove; the quick
  groove shift is too small to draw and is not shown.
- Assumed where the text is silent: Snok plays off the far right corner, Fakie-Tomahawk off the left boards near the
  goal line, Tomahawk off the right boards.
- Contacts more than 9 mm off the drawn point (blade cannot reach): Fakie-Lillstøvel 2 (12.0 mm), Fakie-Omvendspjass 2
  (9.8 mm), as in their base moves.

## Review page

`python3 scripts/move-pictures/review-page.py` (`npm run pictures:review`) writes `out/move-pictures/review/`: one
page with every move picture (121), its NTHF text, the puck.no original where there is one, and per move a
"Looks good" / "Needs change" choice and a comment. The page keeps the verdicts in its artifact database
(collection `reviews`, document id = move id from `data/encyclopedia/index.json`), which Claude reads back with the
artifact data tool. Published as an artifact for the user (link in the thread and in docs/state.md).

### First review round (2026-10-14)

Six pictures redrawn after the user's comments on the review page:
- Edwall-innspill and Lindahl-innspill: the wing is drawn at the START of the carry, further back in its slot, facing
  forward, with a set grip (`puck_local_mm` in the contact): the puck between the blade heel and the skate (heel
  groove, Edwall) or between the stick and the skate (stick groove, Lindahl). Grip positions are ASSUMED from the
  skater keypoints (`data/figure-keypoints.json`). The contact's circle steps aside so the grip stays visible. New view
  `deep` (x 0-446 mm) shows the back of the slots.
- Fakie Lillstøvel, Näcka, Omvendspjass and Spjass: played from the middle of the centre's slot (the user: impossible
  from further forward).
On the page the redone moves go back to "not reviewed" with the user's comment kept and a "Redrawn" note.
