# Hypothesis: fuse cheap signals to estimate the goal moment within 0.2 s for >=23/25 goals and lift recognition to >=22/25

**Verdict: REFUTED on the recognition target (21/25 at best, 19/25 with the pre-declared setup, baseline 20/25); the moment target (>=23/25 within 0.2 s) is met only with a post-hoc false-spot mask (21/25 with the documented mask). The moment estimator itself is a real improvement (within 0.5 s: 16 -> 21/25, 23/25 post-hoc).**

All numbers are leave-one-goal-out over the 25 user-labelled goals (`scripts/nm26-goal-moment-fusion.py`, about 20 s, PROPOSED).

## Signals used
- Puck: last detection before a >= 0.8 s gap with no detection (puck went into the goal), after dropping ice-mark false spots so they do not break the gap.
- Replay: the last 1.2 s puck path reappears 3.3-7.2 s later (this is the original) or appeared 3.3-7.2 s earlier (this is the replay copy).
- Broadcast audio: log rise of the 100 ms RMS in [t+0.3, t+1.5] over [t-1.5, t]. Crowd reaction peaks about +0.8 s after the goal mark in most goals (raw peak is noisy: outliers at -5 s and +3 s from replays and commentary).
- Scoreboard change = the existing `box_s` (already an overlay-change detector, used as a lag window of B-16..B-1 s and a lag feature).
- Ridge logistic regression over candidates; estimate = candidate + median training offset (0.10 s).
- NOT tested: goalie/figure "reset" signal, separate replay-transition (wipe) detection from pixels, commentator-excitement ASR. The replay is captured through the puck-path repeat instead.

## Goal-moment accuracy (25 labelled goals, LOO)
| Setup | within 0.2 s | within 0.5 s | within 1 s |
| --- | --- | --- | --- |
| Existing estimator (docs/nm26-combinations.md, constants refitted LOO) | 15 (in-sample, no LOO figure) | 16 | 19 |
| Fusion, documented false-spot mask (pre-declared) | **21** | 21 | 22 |
| Fusion, wider false-spot mask (x -275..-186, y -205..-170) | **23** | 23 | 23 |

The wider mask came from a transcription slip in my first prototype; it removes about 250 more detections in game 3. It helps, but I found it after seeing results, so treat 23/25 as an upper estimate, not a clean held-out number. With 25 goals the choice flips 2 goals either way.

Ablation (documented mask / wide mask, within 0.2 s): puck only 14/14; + replay 18/21; + replay + lag 17/19; + audio rise 21/23; audio without replay 17/20. So audio adds +2 to +4 goals, replay +4 to +7.

Ceiling: a correct candidate (last sighting before a gap, within 0.3 s of the user's mark) exists for 22/25 goals (documented mask), 23/25 (wide). The misses are candidate-generation failures, not ranking: g1-goal5 and g4-goal2 (the true last puck sightings are mislocated near-board detections, a different false spot), g3-goal3 (a false detection cuts the gap), g3-goal4 (+0.67 s).

## Recognition (vote of tree, 1-NN, rules; LOO; user's moment = 23/25)
| Moments used | Vote | 1-NN / rules | Tree |
| --- | --- | --- | --- |
| Existing estimate | 20/25 | 20 / 20 | 16 |
| Fused, documented mask | 19/25 | 19 / 19 | 16 |
| Fused, wide mask | 21/25 | 21 / 21 | 17 |
| User's mark (ceiling) | 23/25 | 23 / 23 | 18 |

Target was >=22/25: missed. Even a perfect moment tops out at 23/25 because the wing and rebound goals are singleton families, so >=22 needs at most one bad moment among the other 23. One bad moment (g1-goal5, which picks the previous goal's candidate) is enough to lose a point.

Proposed labels of the 15 unreviewed goals under the fused moments (documented mask): 14 of 15 unchanged, 1 flips (g6-goal3 centrifuge -> defence, with the estimated moment moving 2907.0 -> 2912.9, i.e. a different candidate; not checked against the video; a 5.9 s move suggests one of the two is the wrong shot). Several moments differ by more than 3 s between estimators (g5-goal7, g6-goal3, g6-goal4, g6-goal6, g7-goal3), so those 15 goals really do need review whichever estimator is used.

## False positives on non-goal stretches (all seven game windows, 39.3 min)
Unconditional detector (no box time, so no lag feature; puck gap + replay + audio rise, threshold at the 10th percentile of LOO true-goal scores): detects 33/40 known goals within 0.5 s and fires **71 times on non-goal time = 1.8 per minute** (66 if replay copies of goals are excluded). Per game: g1 15, g2 5, g3 12, g4 12, g5 9, g6 8, g7 10. Without the scoreboard-lag gate the fused signals are not a goal detector; I did not inspect the false positives by eye; most are probably puck pauses (held, lost or hidden) coinciding with an audio rise. The overlay-box gate (B-16..B-1 s) is what makes the estimator usable.

## Interpretation
- Hypothesis 1 (weak link is the moment): partly right. Perfect moments give 23/25; the current estimate gives 20; the fusion estimator gets 19-21.
- Why a better moment gave a worse score with the documented mask: recognition features (set-up spot, holder, figure poses) are sensitive to *which* hold is picked, and the fusion's 4 misses pick wrong holds that happen to be ordinary-looking set-ups, while the old estimator's near-misses (0.1-0.5 s off) stay on the right shot. Moment accuracy within 0.2 s is not the bottleneck; the wrong-shot picks are.
- Next steps that could still reach >=22: (1) a second false-spot mask (the one near the board the old estimator also trips on); (2) one-to-one assignment of candidates to goals within a game (g1-goal5 reuses g1-goal4's moment); (3) a tracker re-run for the 3 candidate-less goals. I did not apply them: with 25 goals they would be tuning on the test set.

## Reproduce
`python3 scripts/nm26-goal-moment-fusion.py [--false-positives] [--no-write]` (needs the broadcast video at out/dl/nm26.webm, 660 MB; `NM26_WIDE_MASK=1` for the sensitivity run); `python3 scripts/nm26-combo-recognition.py --moments validation/nm26-goal-moments-fused.json --out /tmp/x.json`.
