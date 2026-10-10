# NM26: combination recognition for every goal (2026-10-10)

Status: PROPOSED. Model output from the committed figure and puck tracks; checked leave-one-out against the user's 25
goal labels. The 15 unreviewed goals carry PROPOSED labels, not user labels.

**Since 2026-10-10 (docs/nm26-new-tracks.md):** the NM26 analysis reads `puck-track-synth.json` and `figure-tracks-v3.json`; the numbers below are from the old tracks, the new ones and the
label changes are in docs/nm26-new-tracks.md by default (`scripts/nm26_tracks.py`).

**Run:** `python3 scripts/nm26-combo-recognition.py [--puck <file>]` (about 3 s, numpy and Pillow only, no video).
`--puck` picks another puck-track file in each game folder (default now `puck-track-synth.json`, was `puck-track.json`), so the whole analysis can be
re-run on a better puck track (workstream 1) with one command.

**Outputs:**
- `data/games/nm26-semifinal/combo-labels.json`: every goal's moment, set-up features, the predictions, the final
  label, and the leave-one-out report (accuracy, per-family recall and precision, confusion matrices).
- `validation/nm26-combo-spots.png`: where the puck was set up before each goal, in the scoring team's frame.

## Headline

| Method (family of 6) | Leave-one-out, user's goal moment | Leave-one-out, estimated moment |
| --- | --- | --- |
| Majority class (centrifuge) | 10/25 (40%) | |
| Decision tree, depth 3 (declared primary before the run) | 20/25 (80%) | 17/25 |
| Nearest labelled goal (1-NN) | 21/25 (84%) | 20/25 |
| Playbook rules (in-sample, see below) | 23/25 | 20/25 |
| **Vote of the three (used for the PROPOSED labels)** | **23/25 (92%)** | **20/25 (80%)** |

- The two goals every method misses are the only goal of their family: the left wing's own goal (`wing`, g1-goal2)
  and the rebound (g3-goal7). Leave-one-out cannot learn a family from zero examples. Both look like centrifuges in
  the set-up (the left wing holds the puck behind the goal), which is what they are until the last touch.
- On the four families that have at least two examples (shovel, centrifuge, centre trick, defence), the vote gets
  23/23 and the tree 20/23.
- The rules were revised once after the first run (v1 called a goal "rebound" when an opponent's blade was nearest;
  near-board wings are often mislocated, so it fired on centrifuges). Their score, and so the vote's, is in-sample.
  The tree and 1-NN scores are true leave-one-out.
- "Estimated moment" re-runs the leave-one-out with each labelled goal's moment taken from the estimator below instead
  of the user's mark. That is the condition the 15 unreviewed goals are in.

**Per family (vote, user's moment):**

| Family (user) | Goals | Correct | Precision |
| --- | --- | --- | --- |
| shovel | 9 | 9 | 1.00 |
| centrifuge | 10 | 10 | 0.83 (the wing goal and the rebound land here) |
| centre (Spjass) | 2 | 2 | 1.00 |
| defence | 2 | 2 | 1.00 |
| wing | 1 | 0 | — |
| rebound | 1 | 0 | — |

**Confusion matrix (vote, rows = user, columns = predicted):** all off-diagonal cells are zero except
wing → centrifuge (1) and rebound → centrifuge (1).

**Where the single methods fail (leave-one-out, user's moment):**
- Tree: g1-goal3 and g1-goal5 (centrifuge → centre: the set-up spot is in front of the far post, between the lanes),
  g4-goal4 (defence → centrifuge: with that goal left out, only one defence goal remains and the tree's split misses
  it), plus the two singletons.
- 1-NN: g4-goal2 (centrifuge → wing), g4-goal3 (centrifuge → centre), plus the two singletons.

**Sub-families** (1-NN within the user's family, leave-one-out):
- Shovel: Spade vs Edwall long shovel 7/8 (g3-goal1, a Spade, is called Edwall).
- Centrifuge: short vs ordinary 10/10. In the short centrifuge the centre stands far back in its slot: 50-68 mm from
  its own end, against 180-241 mm (near the goal) in the ordinary one. The figure-track doc found the same.

## Method

### 1. Team frame

Every goal is turned into the scoring team's frame: the left end's world frame, and for the right end the world turned
by 180° (the rink is point-symmetric). Every team then attacks +x (goal line at about x = +250 mm), its left wing plays
on +y and its right wing on −y. Slot depth is measured from the figure's own-goal end. Rotations stay relative to the
team's home heading, as in the tracks.

### 2. The goal moment

The 25 labelled goals use the user's "goal is now" mark. For the other 15 the moment is estimated from the puck track.

- **Holds:** a hold is a run of at least 4 disk detections, with gaps of at most 3 frames and steps under 15 mm.
  Three kinds of hold are ignored:
  - holds at the centre spot (face-offs);
  - static false spots: a place where the game has a 1 s hold moving less than 1.5 mm, at least twice;
  - one false spot found by inspection: a candidate at the near board of the left corner (world about (−240, −178) mm).
    The track sits there for 7-21 s in each of games 2-5 while the real puck is elsewhere (in g2-goal3 for 4 s while
    the right wing carries the real puck).
- **Replays (new finding, inferred from the puck track):** the broadcast replays many goals. The same puck path
  reappears 4.7-5.9 s after the goal. The script finds the delay at which the moving puck's detections repeat within
  8 mm, after the previous goal's restart. The goal is the end of the matched live segment + 0.27 s.
  - Every labelled goal with a correct replay match has a score-box lag of 7.8-13.6 s. Goals with a lag of 3-5 s show
    no replay. So the replay is probably why the box lag is bimodal (`docs/nm26-game-patterns.md`).
- **Fallback:** the hold followed by the longest time without another hold (the puck went into the goal and play
  stopped), + 0.30 s. Only holds after the previous goal's restart, in [box − 14 s, box − 1 s], count.
- **Error, leave-one-out on the 25 labelled goals (constants refitted without each goal):**
  - median 0.32 s; 14 within 0.5 s, 16 within 1 s; 90th percentile 4.6 s; worst 8.5 s;
  - replay: 9 goals, median 0.17 s;
  - longest gap: 15 goals, median 0.35 s.
- **Large misses:**
  - g2-goal2: a false replay match;
  - g5-goal1 and g1-goal2: the live hold is not the one followed by the longest gap;
  - g1-goal3, g3-goal4, g3-goal7: the puck is not tracked in the last second.

### 3. Features at the goal moment

- **Set-up spot:** where the last hold in the 2 s before the goal ended. Without a hold, the mean puck position in the
  last 1.5 s.
- **Holder:** the scoring team's skater whose blade point is nearest the spot at that time. The blade point is the
  mold point (12, 33) mm, as in `scripts/nm26-figure-analysis.py`.
- **Figure set-up, from the smoothed figure tracks, 0.5 s before the goal:** for the centre, right wing and left wing,
  slot depth and facing; for both defenders, slot depth; and the centre's total turning in the last 1.5 s.

### 4. Classifiers

- **Decision tree:** depth 3, Gini. On all 25 goals it learns:
  - `spot_y <= −121` → shovel (the right-wing lane);
  - otherwise, `spot_x <= 3` → defence;
  - otherwise, `spot_x <= 215` → centre;
  - otherwise, the centre's depth decides between centrifuge and wing (fitted to the single wing goal).
- **1-NN:** the nearest labelled goal on standardised features (mean squared difference over the features both goals
  have).
- **Playbook rules** (`docs/table-hockey-playbook.md` 3.3, written in the team frame):
  - set up in the own half (x < −60 mm) → defence;
  - in the right-wing lane (y < −110) → shovel;
  - in the left-wing lane or behind the goal (y > 110 or x > 300) → centrifuge;
  - between the lanes → the holder decides (right wing → shovel, left wing → centrifuge), otherwise centre trick.
- **Final label (PROPOSED goals):** the majority of the three, or the tree on a three-way split.
  - The tree was declared the primary method before any results. The vote was chosen after seeing that the tree
    overfits the single wing goal. Both are reported.
  - **Combination name:** the user's name of the nearest labelled goal in the same family. Null means the nearest is
    an unnamed one ("ordinary" centrifuge, unnamed shovel).
- **Confidence:**
  - high: all three methods agree and the vote does not change when the goal moment is shifted by −0.5, −0.25, +0.25
    or +0.5 s;
  - medium: two of three agree;
  - low: none.

## PROPOSED labels for the 15 unreviewed goals

The scorer is the player (by end, `config.json`). Spot: set-up spot (x, y) in mm, team frame.

| Goal | Scorer | Moment (video s, method) | Family | Combination (nearest labelled goal) | Confidence | Tree / 1-NN / rules | Spot, holder |
| --- | --- | --- | --- | --- | --- | --- | --- |
| g5-goal3 | Fjermestad | 2521.0 (replay) | defence | — | medium | shovel / defence / defence | (−237, −136), RD |
| g5-goal4 | Nygård | 2551.3 (replay) | centre | — | high | all centre | (166, 3), C |
| g5-goal5 | Nygård | 2566.4 (replay) | centre | — | high | all centre | (164, 7), C |
| g5-goal6 | Nygård | 2600.1 (replay) | centrifuge | Short centrifuge (g4-goal2) | medium | centrifuge / wing / centrifuge | (253, 209), LW |
| g5-goal7 | Fjermestad | 2671.2 (replay) | centrifuge | ordinary (g1-goal6) | high | all centrifuge | (215, 170), LW |
| g6-goal1 | Nygård | 2809.1 (longest gap) | defence | — | high | all defence | (−111, −67), RD |
| g6-goal2 | Nygård | 2896.0 (replay) | shovel | Edwallskyffel lang (g2-goal4) | high | all shovel | (6, −196), RW |
| g6-goal3 | Fjermestad | 2907.0 (longest gap) | centrifuge | Short centrifuge (g3-goal6) | high | all centrifuge | (342, 200), LW |
| g6-goal4 | Nygård | 2951.6 (longest gap) | defence | — | medium | shovel / defence / defence | (−177, −222), RD |
| g6-goal5 | Nygård | 2978.6 (longest gap) | centre | — | high | all centre | (103, −40), C |
| g6-goal6 | Nygård | 3003.1 (longest gap) | centrifuge | ordinary (g5-goal1) | medium | centrifuge / centrifuge / centre | (257, 78), LW |
| g7-goal1 | Nygård | 3372.2 (replay) | shovel | Edwallskyffel lang (g2-goal2) | high | all shovel | (0, −170), RW |
| g7-goal2 | Fjermestad | 3397.0 (longest gap) | shovel | Edwallskyffel lang (g3-goal4) | high | all shovel | (50, −198), RW |
| g7-goal3 | Fjermestad | 3472.5 (replay) | centrifuge | ordinary (g1-goal3) | high | all centrifuge | (274, 159), LW |
| g7-goal4 | Fjermestad | 3505.5 (longest gap) | centrifuge | ordinary (g3-goal2) | high | all centrifuge | (305, 164), LW |

**Summary:** 11 high, 4 medium, 0 low.
- **Least sure:** the three defence goals g5-goal3, g6-goal1 and g6-goal4. Their set-up spot is deep in the scoring
  team's own right corner (g6-goal4 at the board, y −222). A goal from there is unusual. It may be a long shot by the
  right defence, or the moment estimate may have landed on an earlier hold. Worth a look in the clips first.
- g4-goal5 (game 4 overtime) has no score-box time and no clip, so it is not in the list. 40 of the 41 goals are
  covered.

## What the labels say (all 40 goals, user labels plus PROPOSED)

| Player | Shovel | Centrifuge | Centre trick | Defence | Wing | Rebound |
| --- | --- | --- | --- | --- | --- | --- |
| Nygård (20) | 7 | 3 | 5 | 3 | 1 | 1 |
| Fjermestad (20) | 5 | 13 | 0 | 2 | 0 | 0 |

- Fjermestad scores mostly from the left-wing side: 13 of his 20 goals are centrifuges (left wing → centre).
- Nygård spreads his goals:
  - the right-wing shovel, including the Edwall hat-trick;
  - centre tricks: the two Spjass goals plus three PROPOSED centre goals in games 5-6, all with the puck at the centre
    in front of the goal;
  - defence shots.
- This is the opposite of possession. Nygård keeps the puck on his left wing (`docs/nm26-game-patterns.md` section 6),
  yet scores from the right wing and the centre. The 15 PROPOSED labels are part of these counts.

## What fell short

- **Singleton families.** Wing goal and rebound: one example each, both called centrifuge. More labelled goals (or
  the user's labels for the 15) are the only fix.
- **Goal moments without a replay.**
  - The moment comes from the puck track, which misses the shot itself (`docs/rebuild-g2-edwall.md`).
  - About a third of the labelled goals would be more than 1 s off.
  - Classification at the estimated moment drops from 23 to 20 of 25.
  - A puck detector that sees the shot (workstream 1) should help most here. Re-run with `--puck`.
- **The false spot** at the left corner's near board is excluded by a fixed box found by inspection, not by a
  detector. A real puck there is ignored too.
- **Holder:** the blade point of a near-board wing is often wrong (the wing is mislocated; `docs/nm26-figure-tracks.md`).
  For some centrifuges the left wing's blade is 120-230 mm from the puck. The classifiers therefore lean on the set-up
  spot, not on the holder.
- **Families only, not moves.** The features describe the set-up (where the puck is, who stands where), not the last
  pass or the shot. Spade vs Edwall long shovel is 7/8. The centre tricks (Spjass vs Näcka vs Lillstøvel) are not
  separated: two labelled examples, both Spjass.

## Next

1. The user labels the 15 PROPOSED goals on the existing goal review page, starting with the three defence goals and
   the medium ones. Then re-run: the leave-one-out grows to 40 goals.
2. Re-run with the synthetic puck track (`--puck`) once workstream 1 has one, and compare the goal-moment error and
   the estimated-moment accuracy.
3. Add the last pass (passer, direction) from a puck track that sees fast flights. That gives move-level names
   (Spade vs Edwall, Spjass vs Näcka) instead of families.
