# Goal clip -> editable combo draft (experiment, PROPOSED)

Status: built 2026-11-18 as one of the parallel hypothesis experiments. Everything here is PROPOSED model output; the only
labels used are the user's own (`data/games/nm26-semifinal/goal-labels.json`, 25 goals).

Hypothesis: the pieces already exist to go from a short clip of a goal to an editable `th-combo/1` draft in the combo editor
(PR #23, `site/`), as one command. Verdict (numbers below): **partly confirmed**. From the committed tracks to a draft that the
editor opens, yes, in 0.6 s for all 25 goals. From pixels, no: the one command starts at the tracks, because the video and the
models cannot be fetched or run in a fresh container (section 4).

## 1. The command

    python3 scripts/clip2combo.py --goal g1-goal1 --out draft.json      # one marked goal
    python3 scripts/clip2combo.py g1 83.1 --out draft.json              # any clip: game and the clip's end (video s)
    python3 scripts/clip2combo.py --all --outdir DIR [--auto-end]       # all 25 (--auto-end: the pipeline's own goal-moment estimate)
    npm run clip2combo:eval         # the 25 + 15 unlabelled goals, editor reader, scores -> data/clip2combo/eval.json
    npm run clip2combo:ablation     # one switch on at a time -> data/clip2combo/ablation.json

Pure numpy, no video, no torch. `tests/clip2combo/` (via `npm test`) checks the output shape, the end-frame mapping and four
golden touch sequences. The editor check (`scripts/clip2combo-load.ts`) imports the editor's own `normalizeCombo` from `site/`
(set `SITE_DIR`; needs PR #23 and `node site/scripts/build-assets.mjs`).

## 2. What each stage does

| Stage | Done by | Status here |
| --- | --- | --- |
| Table detection and calibration | `<game>/calibration.json` (slot-line fit), reused | not re-run; one per game, not per clip |
| Puck and figure tracks | `puck-track-synth-v2.json`, `figure-tracks-v3.json`, flights in `passes-synth-v1.json` | committed outputs, not re-run |
| Segmentation into touches, passes, shot | `scripts/clip2combo.py` (new) | built, scored below |
| Combo file | `scripts/clip2combo.py` (new), attacker frame (scoring team = W, attacks +x) | built, opened by the editor |
| Name | family rule table + nearest library move | family good, name weak |

Segmentation, on the flights of `passes-synth-v1.json` in the last 12 s of the clip (each step is a switch; section 3):
1. **repair**: two `battle` flights in a row (a->b, b->c within 0.3 s) are one flight a->c; a flight by the scoring team that
   ends in an opponent's reach is given to the scoring skater whose blade is within 90 mm of its end.
2. **end_by_holder**: the scoring end is the team of the last pass, carry or shot in the last 2.5 s (a battle or turnover
   flight after the goal would give the wrong end).
3. **shot_aware**: a seen flight from the scoring team into the goalie or the goal zone is the shot, not a lost puck.
4. **restart_at_carrier**: a scoring skater who carries the puck after the last seen pass restarts the chain.
5. **unseen_pass**: the last visible holder is a winger and the puck then vanishes: the centre is the scorer (the playbook's
   centrifuge/shovel; **this is a prior**: 22 of the 25 labelled scorers are the centre) and the pass arrow is dashed.

The chain stops at the last flight released by the opponent, at most 4 passes. The shot is not in the broadcast (docs/synthetic-puck.md),
so its arrow runs from the last puck point to the goal-mouth corner away from the goalie (**assumed**; the draft says so in
its description). Figures are posed at the first touch: `arc_mm = u x slot length`, theta relative to the home heading, as in
the tracks. For the E end the turn to the attacker frame is a 180 degree rotation **and** the arc runs the other way (E slots
are the W slots turned, with u reversed): a first version that kept the arc put every E figure in the wrong place, found by
checking the pass line against the receiver's blade (`tests/clip2combo`).

## 3. Results (the 25 marked goals, clip ends at the user's goal mark)

| Measure | Result |
| --- | --- |
| Opened by the editor's reader, with no repair note and unchanged by a second read | **25/25** (and 15/15 for the other 15 goals) |
| Also loaded and drawn in the built editor in a real browser | 4 of 4 tried (`/mnt/project-files/hypotheses/clip2combo-pipeline/screens/`) |
| Scoring end from the clip alone | 24/25 |
| Scorer (last touch) | 21/25; "always centre" gets 22/25 |
| Assist (second last touch) | 22/25; "always the most common" gets 10/25 |
| Scorer and assist both | 20/25 |
| Family | 20/25 (majority class 10/25; the existing recognition tree: 18/25 leave-one-out, docs/nm26-combinations.md) |
| Named combination, top 1 / top 3 (11 goals whose user name is a library move) | 0/11, 3/11 |
| Puck seen in the last 6 s | 75% of frames on average; the last pass was inferred (not seen) for 10 of 25 goals; the shot was seen for 2 |

Ablation (family correct / scorer and assist correct, user mark; `data/clip2combo/ablation.json`): no switch 7 / 9, +repair 10 / 12,
+end_by_holder 11 / 11, +shot_aware 12 / 12, +restart_at_carrier 13 / 13, +unseen_pass **20 / 20**. With the pipeline's own goal-moment
estimate as the clip end (median error 0.17 s, p90 4.0 s) the final row is 17 / 17.
Caveats: the switches were designed while looking at these same 25 goals, so the numbers are in-sample; the 15 unlabelled goals have
no label, only agreement with the recognition script (12/15 same family). The unseen-pass prior is right for 8 of the 10 goals it fired on.

What fails: g1-goal2 (a solo wing goal; the prior adds a centre), g1-goal7 (a rebound hint fires on a shovel), g3-goal5 and g3-goal7 (centre
trick and rebound; no seen touch before the shot), g4-goal4 (the defender's shot is read as a pass to the left wing), g5-goal2 (the defender
shoots; the goalie's save flight is read as the scorer).

The names fail for a reason: shovel goals with a right wing -> centre pass differ in NTHF only by things the broadcast does not show
(heel or stick groove, which corner). The nearest library move for a Spade is Hagerup (same pass, other corner) in 3 of 3, and for
an Edwallskyffel it is the Hælskyffel (carry backward) or Lindahlskyffel.

## 4. Why the command starts at the tracks

- The video: the URL in `data/games/nm26-semifinal/config.json` is a release page without an asset name; `curl` returns HTTP 400,
  so `rebuild:nm26:fetch` cannot run here. The video is 656 MB.
- The detector and figure models need torch (`docs/models.md`), not installed here; the cache step is about 12 min per game.
- A phone video of the user's own table has no tracks at all: `docs/own-video-tracking.md` finds 5 of 10 skaters and no rotation
  at that resolution, so the same chain would not hold there.

So "one command from a clip" needs (a) the pixel stage packaged as a command per clip (cache, calibrate, puck, figures for a time
window rather than a whole game) and (b) the same scoring on a clip that has no committed tracks. Neither exists yet.

## 5. Files

`scripts/clip2combo.py`, `clip2combo-eval.py`, `clip2combo-ablation.py`, `clip2combo-load.ts`, `tests/clip2combo*`, `data/clip2combo/`
(40 drafts, `eval.json`, `ablation.json`). The drafts carry a `clip2combo` object (touches, roles, family, library candidates, notes); the
editor ignores unknown keys. Nothing under `data/games/nm26-semifinal/` was changed.
