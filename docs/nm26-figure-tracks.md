# NM26: figure tracks for all seven games (overnight run, 2026-10-10)

Status: PROPOSED. Model output from the synthetic-data pose models (`docs/synthetic-goalie-pilot.md`): no smoothing,
no user check of the full tracks. Numbers below from `data/games/nm26-semifinal/figure-analysis.json`
(`scripts/nm26-figure-analysis.py`).

## What was made

- `scripts/synth/track-figures.py`: every NM26 game at 5 frames per second, and every frame (30 fps) from 8 s before
  to 1 s after each goal. Per frame, all twelve figures: slot position u and rotation. Skaters: the kit-colour
  localiser finds each skater along its slot, skater model v2b reads its pivot and rotation; goalies: goalie model C.
  23,756 frames in all; about 0.3 s per frame on 4 CPU cores. Checkpoints every 300 frames (container restarts).
- Tracks: `data/games/nm26-semifinal/<game>/figure-tracks.json` (columns per figure: u, theta_deg relative to the
  team's home heading, slot_dist_mm for skaters).
- Checking pictures: `validation/figure-tracks-g1.jpg` … `-g7.jpg` (four frames each; every figure's tracked pivot as
  a dot and its facing as an arrow; red = pivot more than 15 mm off its slot).
- For the rebuild: `data/games/nm26-semifinal/rebuild/g2-goal2-figures.json` (and goal3, goal4): every frame of the
  9 s goal windows, all figures.

## Quality

| Game | Frames | Pivot from slot (median / p90) | Over 15 mm | Jumps at 30 fps: slot / rotation |
| --- | --- | --- | --- | --- |
| 1 | 4,347 | 3.6 / 9.7 mm | 1.9% | 6.0% / 4.5% |
| 2 | 2,633 | 2.9 / 9.0 mm | 1.8% | 5.8% / 2.9% |
| 3 | 3,487 | 3.9 / 9.6 mm | 2.7% | 5.9% / 3.7% |
| 4 | 3,018 | 3.6 / 9.9 mm | 3.9% | 7.6% / 4.8% |
| 5 | 4,171 | 3.0 / 8.6 mm | 1.8% | 5.9% / 3.9% |
| 6 | 3,390 | 3.8 / 11.8 mm | 4.9% | 7.5% / 4.9% |
| 7 | 2,710 | 3.6 / 10.2 mm | 2.3% | 6.2% / 4.4% |

- A jump is a frame-to-frame step over 30 mm along the slot or over 60° of rotation within 1/30 s: faster than a figure
  moves, so tracking noise. About 6% of steps (slot) and 4% (rotation): the tracks need smoothing before use.
- The checking pictures show most figures placed on their feet with a sensible facing. The main failure: a near-board
  wing that is hidden or blurred is sometimes placed on the near board where there is no figure (the colour localiser
  then follows noise). Tracks after the end tone (players resetting the table) are meaningless.

## Findings

**1. Where the centre stands when it scores** (0.5 s before each of the 22 centre goals the user labelled; distance
from the goal-side end of the centre's 250 mm slot):

| Attack (user's label) | Centre position |
| --- | --- |
| Shovel "Spade" (3) | 243, 244, 245 mm: the very back of the slot |
| Shovel "Edwallskyffel lang" (5) | 225, 241, 243, 243 mm (Nygård, 4); 17 mm (Fjermestad, 1) |
| Centrifuge, "Short centrifuge" (3) | 182, 188, 199 mm |
| Centrifuge, unnamed (7) | 9-61 mm: the front, close to the goal |
| Spjass (2) | 56, 58 mm |

This matches the NTHF catalogue's text for Spade ("right wing and centre stand at the very back of the slot") with no
input from it, and separates the short centrifuge from the ordinary one. So the tracks carry real information about
how goals are set up. Sample sizes are small (one set of labels, 22 goals).

**2. The Edwall hat-trick has one repeatable setup** (game 2, goals 2-4, 0.5 s before each goal): the white/blue right
wing at u 0.11-0.15 facing 208-224° (relative to its home heading), the centre at the back of its slot facing
302-329°, the yellow goalie at u 0.61-0.65 facing 52-71°. Game 1's first goal (also an Edwall long shovel) has the
same setup (right wing 211°, centre 316°).

**3. Puck touches** (a skater's blade contact point within 25 mm of a detected puck, 5 fps frames only):
- Only 10-17% of the frames with a detected puck have a blade that close: the puck is often moving between figures,
  and the 25 mm rule, the blade point and the puck positions all carry errors. Treat the split below as indicative.
- Nygård: left wing 37%, centre 33%, left defence 17%, right wing 10%, right defence 4%.
- Fjermestad: right defence 26%, right wing 22%, left wing 19%, left defence 17%, centre 17%.
- This agrees with the puck-track finding (Nygård plays through his left wing; Fjermestad spreads it) and adds that
  Nygård's centre is on the puck about twice as often as Fjermestad's, while Fjermestad's right defence is more
  involved.

## Next

1. Smooth the tracks (remove jumps; a figure cannot move 30 mm in 1/30 s) and drop near-board wing positions the
   localiser cannot support.
2. The puck during passes and shots: frame-by-frame puck positions in the last 0.6 s of the hat-trick goals (user taps,
   or a puck detector trained on synthetic renders like the figures).
3. The hat-trick trace (contact and slide checks) and its video.
