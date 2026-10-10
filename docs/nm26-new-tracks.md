# NM26 on the new tracks (2026-10-10)

Status: PROPOSED. Step 1 of the consolidation summary: the NM26 analysis now reads the synthetic puck detector's track
(`<game>/puck-track-synth.json`, docs/synthetic-puck.md) and tracker v3's figure tracks (`<game>/figure-tracks-v3.json`,
docs/tracker-v3.md) instead of `puck-track.json` and `figure-tracks-smooth.json`. Passes, patterns, the figure analysis,
combinations, the 40 replays and the Edwall rebuild were re-run. Every number below is model output; none is checked by the
user yet. The check is the tap page (section 6).

All before/after numbers: `validation/nm26-track-switch.json` (`python3 scripts/nm26-track-switch-compare.py`; before =
the committed outputs at ee0681d, after = this branch).

## 1. What changed in the code

- `scripts/nm26_tracks.py` picks the tracks. `NM26_PUCK_TRACK` and `NM26_FIGURE_TRACKS` override them, which is how the
  before numbers were reproduced (with the old files every output rebuilt identical to the committed one, apart from the
  new `puck_track`/`figure_tracks` keys).
- **Slow instead of disk.** The old track told a sharp, resting puck (`disk`) from a blur (`smudge`); several steps used
  `disk` to mean "the puck is still or slow here" (centre-spot restarts in patterns, puck-at-rest frames in the figure
  analysis and combinations, the filled puck in the replays). The detector has no such kind, so a detection is `slow`
  when its speed to every neighbour detection within 3 frames is under 300 mm/s (at least one neighbour). ASSUMED
  threshold. On the old track `slow` is `disk`, so the old outputs reproduce.
- **13 mm convention shift.** The detector's x/y is the puck's centre; the old blob centre lay about 13 mm nearer the
  camera (8.8 px below the top face). `camera-ref.json` maps both to the same stabilised pixels (0.05 px median for g1,
  g3, g6, the synthetic track at z = 12 mm, the old at z = 0), so nothing else in the chain needed a correction.
- **Thresholds were not retuned.** The pass, reach and combination thresholds were tuned on the old track. They are
  unchanged; the tap results (section 6) should decide whether they need to move.
- The figure analysis keeps its quality metrics on the raw v2 tracks (`figure-tracks.json`, unchanged) and adds a
  `selected_tracks` block per game for v3. `rebuild/g2-goal{2,3,4}-figures.json` still come from the raw v2 tracks.
- `scripts/nm26-replays.py` draws text with Barlow (`public/fonts`): OpenCV's own font has no "å" and printed
  "Nyg??rd". The committed replays had been made with a renderer the committed script did not contain.
- Edwall: `scripts/edwall-trace.py` can use detector readings, rest at the readings, tracker readings of the passer and
  shooter, a carry-force term and a bounded polish (section 5).

## 2. Passes (`<g>/passes.json`)

| | pass | shot | turnover | battle | carry | uncertain ends (g1) |
|---|---|---|---|---|---|---|
| before (all games) | 379 | 61 | 354 | 482 | 3104 | 193 |
| after | 370 | 49 | 274 | 338 | 2507 | 96 |

- Fewer battles, turnovers and carries: the detector holds the puck through fast flights, so fewer of them break into
  pieces. Uncertain ends fall in every game (g1 193 to 96, g4 208 to 125, g7 143 to 78).
- **The two tracks agree on only about a third of the passes** (same from/to figures, release within 6 frames): g1 21 of
  67 old passes are found on the new track, g2 13 of 42, g4 25 of 61. Without taps nobody can say which is right.
- **Goals:** a shot event in the last 2 s before the user's goal moment exists for 3 of 25 user-marked goals before and
  1 of 25 after. The detector loses the last frames of most shots (the puck is in the goal or behind the goalie), so the
  pass chain does not end in a shot. This is the weakest point of the new track for analysis.
- Claude's 136-candidate review of game 1 (`g1/review-claude.json`) was made on the old candidates; it now records that
  (`puck_track`), and the test checks it one to one only while the candidates come from that track. The game-1 review
  page (`validation/nm26-g1-review.html`) was not rebuilt (it needs the frame cache).
- `puck-synth-compare.json` re-ran with the new passes. Its pass and shot windows now come from the new track, so its
  coverage numbers now favour the new track; the version at ee0681d is the fair comparison.

## 3. Patterns (`patterns.json`, control maps)

| game | seen | possession changes/min | median flight speed mm/s | flights >= 100 mm/min |
|---|---|---|---|---|
| g1 | 0.661 to 0.686 | 14.9 to 12.1 | 848 to 1032 | 19.2 to 16.2 |
| g2 | 0.695 to 0.720 | 20.2 to 16.0 | 921 to 1101 | 23.8 to 21.8 |
| g3 | 0.588 to 0.646 | 19.6 to 16.2 | 901 to 1200 | 25.2 to 21.6 |
| g4 | 0.650 to 0.763 | 19.6 to 12.2 | 797 to 1384 | 19.1 to 18.8 |
| g5 | 0.637 to 0.710 | 16.9 to 11.4 | 887 to 1228 | 20.0 to 16.8 |
| g6 | 0.446 to 0.472 | 12.8 to 9.0 | 816 to 1220 | 15.0 to 11.4 |
| g7 | 0.670 to 0.664 | 17.0 to 13.2 | 896 to 1030 | 20.7 to 18.2 |

The puck is seen more, changes hands less often and flies faster: fast flights that the old track lost or split are now
whole. Possession by player barely moves overall (Nygård's puck zone 42/34/24 % attacking/own/neutral before and 43/34/23
after), but single games can: in g4 the puck on Nygård's figures goes from 33 % to 46 %.

## 4. Figure analysis and combinations

- **Touches** (puck within reach of a figure, share of puck frames): up in six games (g2 0.168 to 0.231), down in g4
  (0.112 to 0.092). By role, Nygård's centre becomes his most-used figure (35 %, was LW 37 %).
- **v3 track quality** (selected tracks, dense steps): slot jumps 0.7-1.1 %, rotation jumps at most 0.08 %, interpolated
  5-7 %, unknown 0.3-2.2 % (g6 highest).
- **Combinations**, leave-one-out against the user's 25 goal labels:

| | tree | 1-nn | rules | vote |
|---|---|---|---|---|
| at the user's goal moment, before | 20 | 21 | 23 | 23 |
| after | 18 | 23 | 23 | 23 |
| at the estimated goal moment, before | 17 | 20 | 20 | 20 |
| after | 15 | 18 | 18 | 18 |

- **Goal moment** (leave-one-out, absolute error): median 0.32 s to 0.78 s, within 0.5 s for 14 to 9 of the goals. The
  hold method got better (median 0.35 to 0.08 s) but the replay method got much worse (0.17 to 1.7 s): the replay rule
  (when the puck reappears at the centre spot after the goal) was tuned on the old track's `disk`, and the detector finds
  the slow puck 2-3 s later in g3-goal3, g4-goal1 and g4-goal4. I did not retune it: with no ground truth beyond the
  same 25 goals it would only fit them.
- **PROPOSED label changes** (the 15 goals without a user label): g5-goal3 defence medium to high; g5-goal5 centre to
  shovel (Edwallskyffel lang, medium); g5-goal7 adds Short centrifuge; g6-goal1 defence to centrifuge (Short); g6-goal2
  Edwallskyffel lang to Spade; g6-goal3 Short centrifuge to centrifuge with no combination; g6-goal4 defence to
  centrifuge (high); g7-goal3 high to medium. None of the user's 25 labels change.

## 5. Edwall refit (game 2, goals 2-4)

The refit was meant to fix the three problems of v1 (docs/rebuild-g2-edwall-v2.md): the puck rested about 44 mm off the
board but was snapped to it, the goal-4 shot pose was wrong (the centre played the puck with the back of the figure), and
the carry-force check failed in all three goals.

What v2 adds (`shots/edwall/<goal>.inputs.json`, `trace_version: v2`): the detector's readings (score at least 0.2) in
place of the hand readings on the same frames; the rest spot at the mean rest reading; the passer's and shooter's own v3
readings (src 0) as a soft constraint (sigma 15 mm and 20 degrees, weight 100, capped; ASSUMED); the carry-force share as a
penalty; the shovel must be played with the blade; and a Nelder-Mead polish that stays inside the bounds (in v1 it could
leave them: the first v2 round put goal 3's passer at 245 degrees, outside its 170-240 bounds).

| goal | v2 result | trace |
|---|---|---|
| g2-goal3 | **rebuilt.** Scores at frame 28350.2 (user 28347, v1 28351). Rest within 0.2-1.3 mm of the readings (v1 41 mm). Flight readings 12-30 mm off (v1 8-27). The shovel is played with the blade at 217 mm/s (v1: skate/body). Contact and slide checks pass. Carry-force check still FAILS: the right wing drags the puck with its skate (part `skate/body`, which matches the foot drag-back of CLAUDE.md) but would have to pull it in 39 of 50 steps, at most 6.9 degrees outside the contact fan (v1: 38 of 60, up to 47.7 degrees). The right wing touches the puck once more after release (463 mm/s, inside the limit). | `data/traces/edwall-g2-goal3.trace.json` (v2) |
| g2-goal2 | **not rebuilt.** No fitted shot scores: with the rest at the readings the pass fits (pass objective 3703 with the bounded polish, against 7680 without it), but every shot the search found (four rounds, the last with 45 generations and the shooter held to its track only until it reaches the front of its slot) either hits the E goalie at 1.3 m/s, hits the post or misses. | v1 kept |
| g2-goal4 | **not rebuilt.** Same (pass objective 2658): the pass fits, the centre reaches the puck (396 mm/s), but no shot scores; in one round the passer's skate sent the puck into the goalie at 1.8 m/s. The v3 track shows the centre at 263-302 degrees during the shot, where v1 had 234 (back of the figure). | v1 kept |

The v2 attempts for goals 2 and 4 are kept as `shots/edwall/g2-goal{2,4}.v2-attempt.inputs.json` (their last fitted
values); the live inputs and traces are v1, and they still rebuild identically (v1 inputs read the old figure tracks,
`figure-tracks-smooth.json`). What would help: the user's view of where the shots go (goals 2 and 4 are hidden behind
the goalie in the broadcast), and a goalie that is the real E goalie pose (the trace uses the goalie track as is).

The goal-3 video (`validation/analysis-edwall-g2-goal3.mp4`) and its presentation were made from the v1 trace. The
presentation (`data/presentations/edwall-g2-goal3.analysis.json`) is rebuilt; the video is NOT re-rendered (about 75 min).
Top view: `validation/edwall-g2-goal3-trace.png`.

## 6. The check: taps on the frames where the tracks disagree

Page: https://claude.ai/artifact/21hTqYXsKVvuYDcZHGuWXp (private; 96 frames; source
`validation/tap-review/index.html`, made by `scripts/nm26-tap-review.py page`). Each frame is the registered broadcast
crop; the user taps where the puck (or the named figure) really is, or answers "not in this picture" / "can't tell".
Neither track is drawn.

| items | count | how chosen |
|---|---|---|
| puck, both tracks see it but more than 15 mm apart | 22 | random, at least 3 s apart |
| puck, only the old track | 14 | |
| puck, only the new track | 14 | |
| puck, last 2 s before a user goal | 11 | |
| puck, tracks agree (control) | 5 | |
| figure, v2 and v3 more than 30 mm apart | 30 | half in the 30 fps goal windows, half at 5 per second |

Scoring (`python3 scripts/nm26-tap-review.py eval <taps.json>`, writes `validation/tap-review/results.json`): a puck
track is right within 15 mm of the tap (measured on the 12 mm plane), a figure track within 25 mm (ice plane); "not in
this picture" makes a track that reports the puck wrong. Claude exports the page's answers (collection `taps`) when the
user says they are done.

**What could not be verified without taps:** which track is right where they disagree (two thirds of the passes); whether
the faster flights are real; the replay-rule regression for the goal moment; the label changes; the Edwall goal-3 rest
spot (the detector and the hand readings agree, but both come from the same broadcast pixels).

## 7. Replays (`validation/replays/`)

Re-run without new broadcast clips (`--no-clips`; the clips do not depend on the tracks). Mean over the 40 windows: puck
seen 0.642 to 0.682, slow (filled disk) 0.390 to 0.426, figures shown 11.92 to 11.98 of 12. The puck is a filled disk
when slow, a ring when faster.

## 8. Not re-run or still on the old tracks

- `validation/nm26-g1-review.html` (pass review page; needs the frame cache) and Claude's review of it (section 2).
- `rebuild/<goal>-evidence.json` and its sheets (need the goalie model C), `validation/figure-tracks-<g>.jpg` (raw v2).
- The Edwall videos (all three; goal 3's trace changed, section 5).
- `docs/nm26-game-patterns.md`, `docs/nm26-passes.md` and `docs/nm26-combinations.md` keep their old-track numbers; this
  document has the new ones.
