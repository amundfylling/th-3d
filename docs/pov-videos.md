# POV videos (Karlis Balodis, DJI Osmo Nano): camera and model baseline

Status: PROPOSED (2026-10-15). Steps 1-5 of the user's nine-step plan for using the head-mounted POV videos to
improve the NM26 models, run on one game (Swedish Masters 2026-02-07, `DJI_20260207100451_0002_D.LRF`). Survey of the
footage: `/mnt/project-files/pov-videos/README.md`. Results, numbers and sheets for the game:
`/mnt/project-files/pov-videos/game-0002/README.md` (the videos are not in the repo).

## Result

- The camera is solvable per frame: 95% of 8,717 frames, 0.57 px median residual against the slots and the board.
- The broadcast-trained models do not transfer: skater-v3 and goalie-c fail in almost every crop (the figures are seen
  from above); puck-v1's confident peaks are mostly on the puck, but its weak peaks sit in the far goal's net.
- The DJI data track carries a per-frame orientation quaternion and an accelerometer; the quaternion agrees with the
  solved camera to about 4 degrees but does not predict frame-to-frame motion, so it is not used for tracking.

## Pipeline (`scripts/pov/`, Python 3 with opencv, numpy, scipy, torch, torchvision)

| Step | Script | Output (under the game folder) |
| --- | --- | --- |
| metadata | `dji_meta.py <video> --dump N` | decoder for the `djmd` track (dvtm_ow001.proto) |
| 2. signals | `index_game.py <video> <dir>` | frames.npz: quaternion, accelerometer, sharpness |
| 4. camera | `track_camera.py <video> <intrinsics.npy> <plate.png> <out.npz>` | per-frame pose (flow + rink ICP, SIFT relocalisation on the plate) |
| plate | `rink_plate.py <video> <track.npz> <plate.png>` | empty rink, top-down 1 px/mm |
| 3. lens | `calibrate_lens.py <video> <track.npz> <lens.json> <check.jpg>` | f, k1, k2 from 24 frames |
| 2. gate | `segment_game.py <video> <dir> <out> --track <track.npz>` | segments.json, contact sheets |
| 4. export | `camera_outputs.py <video> <track.npz> <lens.json> <out>` | camera-track.json, overlay sheet |
| 5. models | `baseline_models.py`, `baseline_puck.py`, `baseline_summary.py`, `baseline_sheet.py`, `baseline_puck_sheet.py` | baseline/ |

Shared: `pov_common.py` (geometry, projection, line masks), `camera_fit.py` (the rink ICP). The first camera needs a
seed: one frame solved from ten hand-picked line-board points (`lm.board.*`) and refined with `camera_fit.fit`.

## Assumptions (all visible in the outputs)

- World scale is the repo's preview scale (geometry.json image_to_world, assumed).
- Principal point at the image centre; distortion k1, k2 only.
- The rink is point-symmetric: W is placed at the camera's end; the kits then follow the rule (white/blue W, yellow
  E), which is consistent but not an independent check.
- Gate and tracker thresholds (angles, speeds, residuals) are assumed.

## Steps 6-8 (2026-10-15, PROPOSED)

Results and outputs: `/mnt/project-files/pov-videos/game-0002/README.md` (steps 6-8 section).

| Step | Script | Output |
| --- | --- | --- |
| 4 fix | `fix_track_markings.py <video> <track.npz> <out.npz>` | the track without its along-table slide (centre/blue lines) |
| 6. poses | `pov_synth_poses.py <track.npz> <poses.json> [n] --exclude-eval figures.json` | real cameras for the renders |
| 6. renders | `/root/venvs/blender/bin/python render_pov_frames.py <poses.json> <out> <seed0> <count>` | RGBA canvases + labels.jsonl |
| 6. composite | `compose_pov.py <video> <plate.png> <render_dir> --track <fixed track>` | <seed>.jpg |
| 6. train | `train_pov_figures.py <render_dir> <out.pt> [epochs]` | POV figure model (`pov_figures.py`) |
| 6. eval | `eval_pov_figures.py <video> <track> <plate> <model> <out> --frames figures.json --run start n` | summary.json, sheet |
| 7 | `facing_review_page.py ...` (template `facing-review.template.html`) | facing tap page, db `pov_facing` |
| 8 | `puck_review_page.py ...` (template `puck-review.template.html`) | puck tap page, db `pov_puck` |

Added assumptions: centre line at x = 0 (symmetry), blue lines at x = +-94 mm (traced, +-4 mm); synthetic pivots on
the slot centreline; goalie rotations within +-100 deg of home in the renders.

## Next

Turn the user's taps into the first real rotation and puck test sets, score the POV model and puck-v1 on them,
then fine-tune puck-v1 for the POV view (far goal net as a negative). Step 9 (more games) waits on that.
