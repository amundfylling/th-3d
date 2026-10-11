# Pipeline: from zero to all outputs

How to rebuild everything in this repository in a fresh cloud container, in order, and what can and cannot be rebuilt.
Written 2026-10-10 (tests-and-reproducibility workstream). Every "verified" below was run in a fresh container on that day.

## 0. Environment (fresh container, about 5 min)

| What | Command | Notes |
| --- | --- | --- |
| Node packages | `npm ci` | Node 22.18+ runs the `.ts` scripts directly (docs/tools.md). |
| Blender venv | `python3.11 -m venv /root/venvs/blender && /root/venvs/blender/bin/pip install "bpy==4.5.*" shapely mapbox_earcut "numpy<2" pillow "opencv-python-headless<4.11" av scipy` | docs/blender.md, plus PyAV and SciPy for the NM26 scripts. Gives bpy 4.5.14, OpenCV 4.10.0, NumPy 1.26.4, PyAV 18.1, SciPy 1.17.1. |
| PyTorch (models only) | `/root/venvs/blender/bin/pip install torch torchvision` | Only for stage `models` and the goalie evidence sheets. Not verified: the PyTorch CPU index (download.pytorch.org) did not install in this container. |
| Tests | `python3` with NumPy | `npm test` runs the Python tests in `tests/synth/` through `tests/synth/synth.test.ts` (set `PYTHON` to use another interpreter). |

Every NM26 and synth script runs with `/root/venvs/blender/bin/python`. Keep NumPy below 2 in that venv (bpy 4.5 is built
against NumPy 1; docs/materials.md). A different OpenCV or NumPy can change frame registration and puck candidates
slightly, so rebuild with the pinned venv when comparing against committed outputs.

## 1. Model, assets and videos (iterations 01-25)

These are the existing npm scripts, in dependency order. Each iteration's doc has the details and expected outputs.

| Order | What | Commands | Doc |
| --- | --- | --- | --- |
| 1 | Geometry checks | `npm run check` (typecheck, validate, test) | docs/geometry.md |
| 2 | Traces from the references | `npm run trace:board`, `trace:slots`, `trace:goals` and their `render:*` overlays | docs/board-trace.md, docs/tracks.md, docs/goals.md |
| 3 | Figures | `players:frames`, `players:preview`, `players:fit`, `players:overhead`, `players:define`, `blender:figures` | docs/players.md, docs/figures.md |
| 4 | Blender scene | `blender:rink`, `blender:hardware`, `assembly:poses`, `blender:assembly`, `blender:materials`, `blender:appearance` | docs/blender.md, docs/materials.md |
| 5 | Remotion | `remotion:assets`, `remotion:stills` | docs/remotion.md |
| 6 | Shots | `shot:21` ... `shot:24`, `video:shovel-17` | docs/shot21.md ... docs/shot25.md |
| 7 | Analysis videos | `trace:spjass` / `video:analysis-spjass`, `trace:nacka` / `video:analysis-nacka`, `trace:ikv` / `video:analysis-ikv`, `trace:defence-lw` / `video:analysis-defence-lw`, `video:analysis-shovel-17` | docs/spjass.md, docs/nacka.md, docs/invers-kryssar-velodrom.md, docs/defence-left-wing.md |
| 8 | Own recorded match | `npm run game:track` (about 10 min) | docs/game-tracking.md |
| 9 | Own match, per-frame camera and figure tracks | `own-video-camera.py`, `own-video-figures.py`, `own-video-figure-paths.py`, `own-video-review.py` (about 20 min; commands in the doc) | docs/own-video-tracking.md |
| 10 | Shot encyclopedia moves | `scripts/build-move.py <id> --robustness --video-spec`, `python3 scripts/encyclopedia-index.py`, `node scripts/analysis-render.ts move:<id>` | docs/shot-encyclopedia.md |

Remotion renders need the headless shell `/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell` with
`--gl=swangle` (docs/remotion.md). Not re-verified in this workstream: steps 2-8 (they predate it and have their own
checks in `npm test`).

## 2. NM26 semi-final: one runner

`scripts/pipeline/nm26_rebuild.py` runs every NM26 step in stages. Each step lists its inputs, Python modules and
outputs; a step whose input or module is missing is skipped with the reason, never faked.

| npm script | Stages | What it does |
| --- | --- | --- |
| `npm run rebuild:nm26:list` | all | Lists every step and whether it can run here. |
| `npm run rebuild:nm26:fetch` | fetch | Downloads the video (656 MB) from the GitHub release to `out/dl/nm26.webm` and checks its sha256. |
| `npm run rebuild:nm26:cache` | fetch, cache | `nm26-detect.py` per game: `out/nm26/<game>/frames.json`, **the cache** (per frame: registration homography and puck candidates). About 12 min per game on 4 CPUs. |
| `npm run rebuild:nm26` | calibrate, meshes, puck, figures, analysis, sheets, pages | **Every NM26 output from the cache.** |
| `npm run rebuild:nm26:check` | same | The same, then compares every committed output with the rebuilt one (`git status`, row diffs for JSON) and writes `out/pipeline/rebuild-report.json`. |
| `npm run rebuild:nm26:puck` | meshes, puck | Puck tracks, passes and patterns only, with the check. |
| `npm run rebuild:nm26:figures` | figures | Cleaned figure tracks, figure analysis and tactics boards from the committed tracks (seconds; no video). |
| `npm run rebuild:nm26:analysis` | analysis | Combination recognition and the old/synthetic puck-track comparison from the committed tracks (seconds; no video). |
| `npm run rebuild:nm26:edwall` | meshes, edwall | The three Edwall hat-trick traces, checks and video specs from their fitted inputs (not in the default run). |
| `npm run rebuild:nm26:from-zero` | fetch ... pages | Everything except the models and the Edwall stage, in one go (about 1.5 h, measured before the replays step was added). |

Run one game with `--games g2`; `--keep-going` continues past a failed step, and any later step that reads a failed
step's output is skipped (an old copy on disk is not used). The step interpreter is `$NM26_PY`, else the
Blender venv, else the runner's own Python.

### Stages and steps

| Stage | Step (script) | Reads | Writes |
| --- | --- | --- | --- |
| fetch | download | `config.json` url + sha256 | `out/dl/nm26.webm` |
| cache | `nm26-detect.py <g>` | video, `<g>/background.png` | `out/nm26/<g>/frames.json` |
| calibrate | `nm26-calibrate.py g1` | `g1/background.png`, `g1/calibration-inputs.json` | `g1/calibration.json`, `validation/nm26-g1-calibration.jpg` |
| meshes | `assets/blender/preview_molds.py skater goalie` | figure molds (bpy) | `out/figures/{skater,goalie}.npz` (reach of a figure for the passes) |
| puck | `nm26-track.py <g>` | cache, g1 calibration | `<g>/puck-track.json` |
| puck | `nm26-passes.py <g>` | selected puck track (`puck-track-synth.json`), meshes | `<g>/passes.json` |
| puck | `nm26-patterns.py` | all passes, timeline | `patterns.json`, `validation/nm26-control-*.png` |
| figures | `synth/smooth-tracks.py` | `<g>/figure-tracks.json` | `<g>/figure-tracks-smooth.json` |
| figures | `nm26-figure-analysis.py` | raw v2 figure tracks (quality, rebuild files), selected figure and puck tracks (touches), goal labels | `figure-analysis.json`, `rebuild/g2-goal{2,3,4}-figures.json` |
| figures | `synth/figure-tracks-board.py g2-goal2 [--smooth]` | the above | `validation/board-g2-goal2[-smooth].png` |
| analysis | `nm26-combo-recognition.py` | selected figure and puck tracks, goal labels, timeline | `combo-labels.json`, `validation/nm26-combo-spots.png` |
| analysis | `synth/puck-compare.py` | both puck tracks, passes, goal labels, timeline | `puck-synth-compare.json` |
| sheets | `synth/figure-tracks-sheet.py <g> 4` | video, cache, figure tracks | `validation/figure-tracks-<g>.jpg` |
| sheets | `nm26-rebuild-evidence.py g2-goal{2,3,4}` | video, cache, goalie model C | `rebuild/<goal>-evidence.json`, `validation/rebuild-<goal>-sheet.jpg` |
| pages | `nm26-review-page.py g1` | video, cache, passes | `validation/nm26-g1-review.html` |
| pages | `nm26-goal-clips.py`, `nm26-goal-page.py` | video, cache, timeline | `out/nm26/goal-clips/`, `validation/nm26-goals-review.html` |
| pages | `nm26-replays.py` | video, selected figure and puck tracks, goal labels, timeline | `validation/replays/` (40 replays, clips, `replays.json`, `index.html`) |
| edwall | `edwall-trace.py g2-goal{2,3,4}`, `edwall-presentation.py g2-goal{2,3,4}` | `shots/edwall/*.inputs.json` (fitted), puck readings, g2 detector puck track, g2 selected figure tracks, meshes | `data/traces/edwall-*.trace.json`, `shots/edwall/*.checks.json`, `validation/edwall-*-trace.png`, `data/presentations/edwall-*.analysis.json` |
| models | renders, training, `synth/track-figures.py` | see section 3 | `out/synth/*.pt`, `<g>/figure-tracks.json` |
| models | `synth/puck-frames.py`, `render-puck-crops.py`, `puck-blob-offset.py`, `train-puck-detector.py`, `eval-puck-detector.py`, `track-puck.py <g>` | video, Blender, PyTorch | `out/synth/puck-det-v1.pt`, `<g>/puck-track-synth.json` |
| models | `synth/render-skater-hard.py`, `track-figures-v3.py plates`, `train-skater-v3.py` (3 runs), `track-figures-v3.py obs/decode <g>` | video, Blender, PyTorch | `out/synth/skater-pose-v3.pt`, `<g>/figure-tracks-v3.json` |

Paths without a folder are under `data/games/nm26-semifinal/`.

**Selected tracks (2026-10-10, docs/nm26-new-tracks.md).** `scripts/nm26_tracks.py` picks the tracks the analysis reads:
`puck-track-synth.json` (puck detector) and `figure-tracks-v3.json` (tracker v3). `NM26_PUCK_TRACK=puck-track.json` and
`NM26_FIGURE_TRACKS=figure-tracks-smooth.json` bring back the old inputs (that is how the before numbers were made).
The old track's `disk` kind (a sharp, slow puck) is replaced by a `slow` flag: under 300 mm/s to a neighbour detection
within 3 frames; on the old track `slow` is `disk`, so old outputs rebuild unchanged.
`track-switch-compare` writes the before/after numbers, `tap-review-page` the user's tap page (`validation/tap-review/`).

**Sources (not rebuilt; listed in `SOURCES` in the runner).** `config.json`, `timeline.json` and
`g1/calibration-inputs.json` are hand-made; `camera-ref.json` was decomposed from the g1 calibration by hand (no script);
the user's labels (`goal-labels.json`, `skater-labels.json`, `goalie-facing-labels.json`) are made by
`nm26-goal-labels.py`, `synth/skater-labels.py` and `synth/goalie-facing-eval.py` from exports of the label pages'
databases; `g1/review-claude.json` is Claude's pass review, and `puck-synth-review-claude.json` Claude's 56-frame puck-track review. `<g>/background.png` is reused by the detector unless `--bg`
is given. `g2/calibration.json` ... `g7/calibration.json` are unused (all games are registered to game 1 and use its
calibration, `calibration_from` in `config.json`).

### What was verified (2026-10-10)

Fresh container, pinned Blender venv (section 0), `npm run rebuild:nm26:from-zero` in pieces, then `--check`:

- **Cache:** video downloaded (sha256 matches `config.json`), `nm26-detect.py` for all seven games: 66 min on 4 CPUs
  (g1 770 s ... g7 430 s). Registration fallbacks 0 except g5 (9) and g6 (237), as before.
- **Byte-identical to the committed files (40 outputs):** `g1/calibration.json` and its jpg; all seven `puck-track.json`
  and `passes.json`; `patterns.json` and both control maps; all seven `figure-tracks-smooth.json`; `figure-analysis.json`
  and the three hat-trick `rebuild/*-figures.json`; `board-g2-goal2-smooth.png`; all seven `figure-tracks-<g>.jpg`;
  `nm26-g1-review.html`; `nm26-goals-review.html`. The figure meshes give the committed reach (skater 56.3 mm, goalie
  48.7 mm).
- **Differs:** `validation/board-g2-goal2.png` (stale, see section 6).
- **Not rebuilt:** `rebuild/g2-goal{2,3,4}-evidence.json` and their sheets need goalie model C (not committed);
  `<g>/figure-tracks.json` need both models (section 3).
- The whole cache-to-outputs run (`npm run rebuild:nm26`) takes about 15 min, mostly the goal clips and the review page.
- An OpenCV 5.0 / NumPy 2 environment was not compared; use the pinned venv.

## 3. Synthetic-data models (stage `models`, not rebuilt)

The figure tracks (`<g>/figure-tracks.json`) come from two networks trained on Blender renders: goalie model C
(`out/synth/goalie-pose-v2c.pt`) and skater model v2b (`out/synth/skater-pose-v2b.pt`). `out/` is not committed, so the
models, renders and plates are not in the repository. Rebuilding them takes hours of CPU (about 1 s per render, 6,000+
renders per model, plus training) and needs PyTorch. The order (docs/synthetic-goalie-pilot.md):

1. Plates: goal-box plates (`out/synth/plates/`), `synth/skater-frames.py <g>` and `synth/skater-plates.py`.
2. Renders: `synth/render-goalie-crops.py <dir> <first_seed> <count> [W|E|both] [ref|nm26]` and
   `synth/render-skater-crops.py <dir> <first_seed> <count> nm26`.
3. Training: `synth/train-goalie-pose.py ... --drop-ref-w --real-train g1,g2,g4,g6 --real-u-from out/synth/goalie-pose-v2a.pt --out goalie-pose-v2c`
   and `synth/train-skater-pose.py 10 --renders <dirs> --real-train g1,g2,g4,g6 --out skater-pose-v2b`.
4. Tracking: `synth/track-figures.py <g> --fps 5` (about 25 min per game).

**Gaps:** the goal-box plates (`out/synth/plates/plate_{W,E}_raw.png`) have no committed script, so the goalie
training steps stay skipped until one is written; and the exact command lines of the committed models (render directories, seed ranges, epochs of model C and A)
were not recorded; the lines above are reconstructed from the doc and are not verified. Retrained models will not
reproduce the committed tracks bit for bit (random augmentation, thread scheduling). To make the tracks reproducible,
publish the two `.pt` files as a release asset next to the video, with their sha256 in `config.json`.

## 4. Tests

- `npm test`: all tests, including `tests/synth/` (Python, NumPy only, about 10 s).
- `npm run test:synth`: the Python tests alone, verbose.
- `tests/synth/_load.py` loads helper functions from the scripts as they are (by parsing the script, without running it),
  so the tests need neither torch nor the video.

| Test file | Covers |
| --- | --- |
| `test_pivot_to_u.py` | `pivot_to_u` (synth/train-skater-pose.py, used by track-figures): camera round trip for all ten slots, offset from the slot in mm, clamping past the ends, crop split, network coordinates |
| `test_smoothing.py` | `smooth-tracks.py`: rejection by slot distance and by the ±0.3 s median, interpolation (shorter arc for rotation), the 1 s gap limit, the 3-frame average on 30 fps windows, stats; and that every committed `figure-tracks-smooth.json` rebuilds exactly |
| `test_blade_contact.py` | `blade` / `pivots` (nm26-figure-analysis.py): the (12, 33) mm mid-blade contact point, home headings, rotation sense, the 25 mm touch radius, same point as `defence-trace.py` |
| `test_rebuild_steps.py` | The runner: scripts exist, inputs come before use, and every committed file under `data/games/nm26-semifinal/` is a step output or a listed source |

**Finding from the tests (current behaviour, not changed here).** `smooth-tracks.py` needs at least 3 valid readings
within ±0.3 s to call a reading an outlier. The full-game tracks are sampled at 5 fps, which gives only 2 neighbours in
that window, so outside the 30 fps goal windows the jump test never fires (in the committed tracks it can fire for
1-20% of the 5 fps rows per game, those next to denser sampling); there only the 15 mm slot-distance rule rejects readings.
`test_at_5_fps_the_outlier_test_cannot_fire` pins this. A wider window (±0.5 s) or "at least 2 neighbours" at 5 fps
would fix it; that belongs to the tracker work (docs/tracker-v3.md).

## 5. Steps from the parallel workstreams (2026-10-10)

The puck detector (docs/synthetic-puck.md), tracker v3 (docs/tracker-v3.md), combination recognition
(docs/nm26-combinations.md), the all-goals replays (validation/replays/), the Edwall rebuild (docs/rebuild-g2-edwall-v2.md)
and the own-video pipeline (docs/own-video-tracking.md) added scripts in parallel. To add a step:

1. Add a `Step(...)` in `steps()` of `scripts/pipeline/nm26_rebuild.py` (the marked section at the end): stage, command,
   inputs, Python modules, outputs. A new stage name goes into `STAGES` (and `DEFAULT` if it should run from the cache).
2. If the step writes under `data/games/nm26-semifinal/`, `test_rebuild_steps.py` fails until it is a step output.
3. Add a row to the stage table above and, if useful, an npm script `rebuild:nm26:<stage>`.

Registered at consolidation (2026-10-10, branch `claude/consolidation-batch-2026-10-10`). Command lines come from each
workstream's doc. Steps execute in list order and this section comes last, so a run of `models analysis` tracks first and
compares after.

| Workstream | Stage | Steps | Status |
| --- | --- | --- | --- |
| Puck detector | models | `puck-frames-<g>`, `puck-renders-0..2`, `puck-blob-offset`, `train-puck-v0`, `train-puck-v1`, `eval-puck-v1`, `track-puck-synth-<g>` | registered; not run here (no video, Blender or PyTorch). Not bit-reproducible (training). |
| Puck detector | analysis | `puck-synth-compare` | **verified 2026-10-10: byte-identical** (python3 3.13, NumPy 2.5, without `out/synth/puck/blob-offset.json`) |
| Tracker v3 | models | `skater-renders-v3-base-0`, `-1500`, `skater-renders-v3-hard`, `figure-plates-v3`, `train-skater-v3-a/b/c`, `figure-obs-v3-<g>`, `figure-tracks-v3-<g>` | registered; not run here. `--out` names added to the training runs so they chain (the doc calls the checkpoints `-ep4` and `-ep16`). Needs timm's ResNet-18 weights (docs/tracker-v3.md). |
| Combination recognition | analysis | `combo-recognition` | **verified 2026-10-10: byte-identical** (`combo-labels.json`, `validation/nm26-combo-spots.png`) |
| All-goals replays | pages | `goal-replays` (`npm run nm26:replays` runs the script alone) | registered; not run here (needs the video) |
| Edwall rebuild | edwall (not default) | `edwall-trace-<goal>`, `edwall-presentation-<goal>` | presentation steps **verified: byte-identical**; trace steps not run (need the figure meshes, bpy). Videos: `node scripts/edwall-render.ts <goal>`, outside the runner. |
| Puck at the shot (2026-10-11) | models, puck, analysis | `track-puck-synth-v2-<g>` (tracker 2 on the v1 candidates, seconds), `passes-synth-v2-<g>`, `puck-track-eval`; detector v2 (not adopted): `puck-renders-shots`, `train-puck-v2`, `eval-puck-v2`, `detect-puck-v2-<g>` | run 2026-10-11 (docs/synthetic-puck.md section 8). v1 working files: `/mnt/project-files/puck-det-v1-workdir/`, v2: `puck-det-v2-workdir/` |
| Own-video pipeline | — | not an NM26 step | section 1, row 9 |

Review sheets without recorded command lines (not registered): `validation/synthetic-puck-*.jpg`
(`synth/puck-review-sheet.py`), the tracker v3 review sheets and evaluations (`synth/tracker-v3-review.py`,
`tracker-v3-eval.py`, see docs/tracker-v3.md "Reproducing").

## 6. Housekeeping found on the way

- `assets/blender/__pycache__/stiga_blender.cpython-311.pyc` was committed although `.gitignore` excludes `__pycache__/`;
  every Blender run rewrote it and left the tree dirty. Removed from the index at consolidation (`git rm --cached`).
- `validation/board-g2-goal2.png` was drawn by an earlier version of `figure-tracks-board.py`; the current script differs
  in 0.07% of the pixels (small drawing differences). Rebuilding replaces it.
