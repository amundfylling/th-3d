# Match tracking: puck possession per skater (first version)

Status: built on 2026-10-07 at the user's request ("Start the tracking without those answers"). Not a numbered
iteration. **Proposed**, not accepted. The counts are a first measurement from the hardest camera angle, with known
errors listed below. The rules and the user's answers that define the count are in `docs/game-mechanics.md`.

| Item | Path |
| --- | --- |
| Source (indexed) | `references/games/fylling-vs-moe-trondheim-open-2022-final.mov` |
| Shared helpers | `scripts/game_common.py` |
| 1. Stabilisation | `scripts/game-stabilise.py` → `data/games/fylling-vs-moe-2022/{stabilisation.json, background.png}` |
| 2. Calibration | `scripts/game-calibrate.py`, inputs `calibration-inputs.json` → `calibration.json`, `validation/game-calibration.png` |
| 3. Puck track | `scripts/game-puck.py`, labels `puck-labels.json` → `puck-track.json` (cache `out/game/candidates.json`, not committed) |
| 4. Possession | `scripts/game-possession.py` → `possession.json`, `validation/game-figure-areas.png`, **`validation/game-possession.png`** |
| 5. Review | `scripts/game-review.py` → `validation/game-puck-spotcheck.jpg`, `validation/game-possession-review.jpg`; judgements in `review.json` |
| 6. Board page | `scripts/game-board-page.py` + `scripts/game-board.template.html` → **`validation/game-possession-board.html`** (interactive: areas shaded on the top-view table, illustrative figures, every seen puck position, a 5:00 timeline that scrubs the puck; `npm run game:board`) |
| Tests | `tests/game-tracking.test.ts` |

Reproduce: `npm run game:track` (about 10 min on the 4-CPU container).

## Result (5:00 regulation)

Settings chosen by the user (2026-10-07):
- **minimum episode 0.5 s:** a stay on one skater shorter than 0.5 s counts as nobody;
- **maximum gap 7 s:** the puck is held through a hidden stretch of up to 7 s, otherwise it is on nobody.

| Skater | Time on the puck | Times | Of which the puck was seen |
| --- | --- | --- | --- |
| W-LD | 32.5 s | 15 | 6.8 s |
| W-RD | 22.2 s | 9 | 13.1 s |
| W-C | 13.9 s | 6 | 7.7 s |
| W-LW | 39.9 s | 12 | 21.1 s |
| W-RW | 13.4 s | 9 | 3.0 s |
| **Fylling (W, left)** | **121.9 s** | **51** | |
| E-LD | 17.9 s | 9 | 11.2 s |
| E-RD | 5.0 s | 2 | 0.8 s |
| E-C | 14.3 s | 6 | 9.9 s |
| E-LW | 23.1 s | 12 | 6.6 s |
| E-RW | 21.5 s | 10 | 14.4 s |
| **Moe (E, right)** | **81.8 s** | **39** | |
| Nobody | 96.3 s | | contested 19.0 s, gaps between different skaters or after "nobody" 37.6 s, three gaps over 7 s 26.9 s, stays under 0.5 s 12.8 s |

Team W is the left player (Fylling, A1). Which goal is goal.W is assumed (see Calibration). "Seen" is the time the
puck was actually detected while on that skater; the rest was carried through gaps where the puck was hidden.

**How much the numbers move** (`possession.json` → `sensitivity`, each choice changed alone from the user's settings):

| Variant | Fylling | Moe |
| --- | --- | --- |
| Baseline | 121.9 s, 51 | 81.8 s, 39 |
| Long gap: nobody only after the limit (Q16) | 121.9 s, 51 | 81.8 s, 39 |
| Goalies block (puck in a goalie's reach is on nobody) | 109.8 s, 47 | 68.0 s, 35 |
| Previous defaults (max gap 10 s, minimum episode 0.2 s) | 133.0 s, 63 | 88.0 s, 55 |
| Minimum episode 0.3 s | 124.0 s, 56 | 87.1 s, 52 |
| Minimum episode 1.0 s | 113.4 s, 39 | 72.1 s, 26 |
| Max gap 10 s | 129.3 s, 52 | 81.8 s, 39 |
| Max gap 3 s | 97.2 s, 45 | 73.5 s, 38 |

The long-gap rule (Q16) makes no difference in this match: each gap over 7 s follows a "nobody" stretch.

## How it works

### 1. Stabilisation

Each frame is mapped to the reference frame 3000 with ORB features and a RANSAC homography. All 7756 frames got a fit.
The whole table is treated as one plane. The housing stands above the ice, so the fit is approximate while the camera
moves most (0-5 s). A median of every 10th stabilised frame gives an empty-table background.

### 2. Calibration (world mm → image)

A homography from the repo's rink coordinates to the stabilised image, fitted to:
- 6 hand-picked slot ends;
- the two blue lines (fit 0.22 px RMS);
- every skater slot centreline lying on the dark slot pixels of the background (median 0.8 px).

The overlay (`validation/game-calibration.png`) shows the slots matching across the rink. The anchor RMS is 6.3 px,
because the chosen slot-end points are hard to place exactly.
- **Assumed, from symmetry:** the rink markings and slots are point-symmetric, so the video can't tell goal.W from
  goal.E. goal.W is put at the video's left. That makes team W the left player's team.
- **Inherited:** the repo's geometry has the preview scale (assumed). The user confirmed the table has the same layout
  (A9); no dimension of this table was measured.
- **Near board:** the near board and housing hide a strip of ice along the near long side.
- **Scale:** about 0.4-0.9 image px per mm (`calibration.json` → `local_scale`). One image pixel is 1-2.5 mm along the
  rink and 2-3 mm across it.

### 3. Puck track

- **Candidates:** dark grey blobs, clearly darker than the background, of the size a 25.4 mm puck would project to at
  that place. About 16 per frame.
- **Classifier:** logistic regression on 15 features: size, shape, darkness, colour, the colours around the blob
  (yellow or blue that isn't in the background means a figure's jersey or trousers), and how often candidates appear at
  that spot over the whole match (catches static false spots).
  - Trained on `puck-labels.json`: 1967 hand-labelled candidate positions in 89 groups of linked detections, labelled
    by eye from zoomed sheets.
  - Cross-validated in 10 time blocks: in 555 of 622 labelled frames the puck is the best-scoring candidate. At
    p > 0.5, precision 0.78 and recall 0.72.
- **Track:** Viterbi over {absent, candidate 1..n} per frame. It penalises jumps (σ 30 mm per frame, impossible above
  160 mm) and switching between seen and not seen. No position is interpolated.
- **Seen in 40% of match frames.** The puck is hidden under and behind figures and the goal cages, blurs in fast play,
  and blends into the dark slots.

### 4. Possession (the user's definition, A10-A15)

- **Reach area:** every puck-centre position the skater's stick or body can touch, over its whole slot and every
  rotation:
  - slot centreline buffered by 43.6 mm (the skater mesh's reach at puck height) plus the puck radius;
  - clipped to the inner boards.
- **On a skater:** the puck is inside that skater's area and nobody else's (`validation/game-figure-areas.png`).
  - 65% of the rink is exclusive to one skater, 31% is contested, 4% no skater reaches.
  - Goalies are not counted (A14) and, in the baseline, do not block.
- **Gaps** (puck not seen):
  - up to 7 s with the same skater before and after: held;
  - up to 7 s with different owners: split in the middle;
  - over 7 s: nobody (user, 2026-10-07; A15 had said 10 s for a stoppage).
- **Minimum episode:** a stay on one skater shorter than 0.5 s counts as nobody (user, 2026-10-07).
- **Counts:** time on the puck, and the number of entries into the skater's area.

## Accuracy: what the review found (`review.json`)

- **Puck, 40 random match frames:**
  - 16 tracked: 10 clearly correct, 6 plausible but not verifiable at the sheet's resolution, none clearly wrong;
  - 24 not seen: in at least one (212.1 s), probably two, the puck was visible.
- **Possession, 24 random episodes** (with the user's settings):
  - the puck is seen at the middle of 22;
  - 8 are clearly consistent and 7 plausible; 5 can't be checked at the sheet's resolution;
  - 2 are probably wrong: the circle sits on the dark edge of the near board, where the housing hides the ice
    (E-LW at match 31.7 s and 180.3 s).
- **Fixed false spots:** the dark rim of the green ice logo next to the left goal (88 → 34 tracked frames), and the
  left goalie's navy trousers.

## Known weaknesses (most important first)

1. **Gap bridging carries much of the time.** Only 40% of frames see the puck, so 60% of the time is inferred. W-LD
   has 32.5 s, of which 6.8 s seen. Its area runs along the far side behind the left goal, where figures and the cage
   hide the puck.
2. **False detections on the near board edge.** The detection area reaches into the strip of ice hidden by the
   housing. Limiting it to the visible ice would remove them (not done yet).
3. **Remaining false detections** (about 34 frames at the logo rim, possibly others) and **missed visible pucks**.
   More labels, or a small learned detector on the stabilised crops, would help.
4. **Stoppages are not detected.** Goals and face-offs (A2: two regulation goals, times unknown, Q11) are counted like
   play. A dead puck held by hand over the ice is not recognised.
5. **Reach areas are geometric maxima** (full rotation, the whole slot), not the figures' actual positions. The figures
   themselves are not tracked.
6. **The blob centre is not the puck centre:** the visible side of the puck pulls it a few mm toward the camera.
7. **The goal.W/goal.E orientation is an assumption from symmetry** (it decides which team's slots are which). A
   180° error would swap every W/E label.

## Next steps (not done)

- The user's goal times (Q11), to mark the two stoppages and check them.
- Limit puck candidates to the visible ice (the near board edge).
- Check the counts against a minute the user counts by hand.
- Label more frames in the weak areas (far side by the left goal), or train a small CNN on the labelled crops.
- Then a fixed-camera recording, which should raise the seen fraction a lot.
