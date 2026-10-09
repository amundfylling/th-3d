# Synthetic training data pilot: goalie pose from the NM26 broadcast

Status: pilot started on 2026-10-09 at the user's request ("Start the pilot"), after the chat answer on how to use the 3D
model for synthetic training data. Everything here is PROPOSED: no real pose is user-labelled.

**Question.** Can renders of our own 3D model, in the NM26 broadcast camera, teach a network to read a goalie's pose
(slot position and rotation) from real broadcast frames, with no hand labels?

The goalie was chosen because it has one slot, is close to the camera's centre, is rarely hidden, and its pose matters for
shot analysis (what the shooter sees).

## 1. Pipeline

| Step | What | Where |
| --- | --- | --- |
| A. Camera | 3D camera of the broadcast, from the ice-plane calibration | `data/games/nm26-semifinal/camera-ref.json` |
| B. Plates | Clean background of each goal box, without the goalie | `out/synth/plates/` (generated) |
| C. Renders | Goalie (and distractors, puck) at random poses, RGBA, with labels | `scripts/synth/render-goalie-crops.py` |
| D. Compositing | Render over a real plate, with camera-like degradations | `scripts/synth/compose.py` |
| E. Training | ResNet-18, u and (sin θ, cos θ) | `scripts/synth/train-goalie-pose.py` |
| F. Real check | Silhouette agreement, search agreement, temporal smoothness | `scripts/synth/eval-goalie-real.py`, `scripts/synth/fit_goalie.py` |

Everything under `out/` is generated and not committed (5,000 renders, 188 MB, about 1.5 h of CPU rendering).

### A. The broadcast camera (status: assumed)

- Decomposed from game 1's ice-plane calibration (`g1/calibration.json`, the slot ICP) as an OpenCV pinhole with square
  pixels: f = 3925 px, principal point (1083, 540), camera centre about (45, −2137, 1086) mm in world mm, so about 2.1 m
  in front of the near board and 1.1 m above the ice, looking down about 25°.
- The plane alone leaves one degree of freedom (focal length against principal-point row). I fixed the row at the image
  centre. A 54 mm goalie projects to 80-81 px across that whole family, so the choice barely matters for this task.
- Every game's frames register to game 1's reference frame. Games 3-7 differ from it only by zoom (×1.13, camera centre
  within about 2 cm), so after registration the one camera serves all seven games.
- Checks: plane reprojection 0.00 px; the rendered goalie slots lie on the real slots; rendered goalies are 86-90 px tall,
  the same as the real ones in the registered crops.
- Not checked: the goal cage height (the model's 50 mm cage does not line up well, so either the cage or the camera height
  is off by a few mm).
- Blender: sensor fit horizontal, 36 mm sensor, lens = f·36/W, shift from the principal point; the Blender projection
  matches the OpenCV one exactly.

### B. Clean plates

- Real registered goal crops, 200 × 200 px per end, every 15th frame of all seven games (5,338 frames).
- Per pixel, the most common colour (Lab, quantised) over all games for each end. The goalie moves, so the ice, the slot
  and the goal behind it win. Small goalie remnants stay on the slot; inpainting them smeared the blue line and logo, so
  the raw plates are used.
- Per-game plates exist too; the compositor picks at random.

### C. Renders

- `assets/scene/full_static.blend`, Cycles CPU, 8 samples with denoising, Standard view transform (the default AgX made
  the yellow kit pale).
- The ice is a shadow catcher, so the render carries the figure and its shadow; goals, boards and screens are holdouts,
  because they are in the plate.
- Per sample (seeded): the end (even seed W, odd E); the goalie at a uniform slot position u ∈ [0, 1] and rotation
  θ ∈ [0, 360°) relative to the home heading (W 0°, E 180°); pivot on the slot centreline (assumed); back print hidden in
  30%; 0-3 distractor skaters from slots that cross the crop; a puck in 50%; kit colour jitter; random sun and ambient.
- Non-overlap: seeds 0-98 rejected distractors by mesh overlap (BVH), which was too slow (5 s per sample); seeds 99-4999
  use a pivot distance of 75 mm (puck 50 mm). Both keep the figures apart.
- Speed: about 1 s per crop on 4 CPU cores.

### D. Compositing (on the fly in training)

Alpha composite over a random plate of the same end, then: foreground gain and contrast, shift ±6 px, rotation ±1.5°,
scale 0.96-1.04, Gaussian blur σ 0.4-1.3, HSV jitter, noise, JPEG quality 35-85 (the broadcast is AV1 at 1080p).

### E. Model

- ResNet-18 with ImageNet weights; 4 input channels: the 160 × 160 crop and a constant plane for the end (one model for
  both ends).
- Outputs u, sin θ and cos θ. Loss: L1 on u plus squared error on (sin, cos). AdamW, one-cycle learning rate,
  batch 32, CPU.
- Validation: the renders with seed ending in 9 (500), composited with fixed randomness.

## 2. Results

Run on 2026-10-09: 5,000 renders (4,500 train, 500 validation), 12 epochs, 2.5 min per epoch on 4 CPU cores.
Numbers from `out/synth/train-report.json` and `out/synth/eval-real.json`.

**Synthetic validation (composited renders the model never saw):**

| Epoch | θ error median | θ error p90 | u error (mean) |
| --- | --- | --- | --- |
| 1 | 13.1° | 30.2° | 0.151 (about 13 mm) |
| 6 | 2.5° | 6.9° | 0.053 |
| 12 | **1.2°** | **3.1°** | **0.0097 (about 0.8 mm)** |

So on its own data the model reads the pose almost exactly, front and back included.

**Real NM26 crops (120 crops, all seven games, 60 per end, every 15th frame).** There are no real labels, so these
checks are indirect (`eval-goalie-real.py`):

| Check | W (white/blue) | E (yellow) | All |
| --- | --- | --- | --- |
| Soft F1 of the predicted silhouette against the real foreground (median) | 0.38 | 0.49 | 0.44 |
| The same for the best pose of the exhaustive silhouette search (median) | 0.46 | 0.52 | 0.50 |
| Predicted F1 at least 90% of the search's | | | 53% |
| Slot position difference from the search (median) | 5.6 mm | 5.3 mm | 5.3 mm |
| Slot position within 10 mm of the search | 80% | 80% | 80% |
| Rotation axis difference from the search, folded to 0-90° (median) | 31° | 12° | 20° |
| Axis within 20° of the search | 30% | 72% | 51% |

**Temporal smoothness (game 5, 2400-2410 s, 300 consecutive frames per end, no smoothing):**

| | Slot step median / p95 | Rotation step median / p95 | Jumps over 90° |
| --- | --- | --- | --- |
| W | 0.4 / 3.0 mm | 1.7° / 30.8° | 8 |
| E | 0.5 / 1.9 mm | 0.7° / 2.8° | 0 |

**Overlay** (`validation/synth-goalie-pilot-real.jpg`, 24 real crops, the predicted pose's silhouette in green): the
outline sits on the goalie in nearly every tile: the right slot position, the right lean and the right height. The
misses are in the outline's width (which way the blocker and catcher point), mostly at the W end.

**Reading:**
- **Slot position transfers.** It agrees with the search to about 5 mm (the slot is 83 mm long) and is smooth
  frame to frame.
- **Rotation transfers at the yellow end, not yet at the white end.** At E the axis agrees to 12° and the sequence is
  smooth with no jumps. At W it agrees to 31° and the sequence jumps by more than 90° eight times in 10 s: the model
  hesitates between front and back. The white kit on white ice is the hard case: the plate and render contrast are
  low, and the real white figure is bluer and glossier than the render.
- **Front and back:** see the user labels below.
- **The domain gap is real but not large.** Synthetic validation gives 1.2°; real agreement with the search is 12-31°.
  Part of that is the search's own error (its median F1 is only 0.50).

### Real accuracy against the user's labels (2026-10-09)

The user marked all 200 crops on the label page (`validation/goalie-facing-review.html`): a tap on the ice in the
direction the goalie faces (chest and mask), none marked "can't tell". `scripts/synth/goalie-facing-eval.py` maps the
tap and the pivot to the ice through the reference camera (taps lie a median 54 mm from the pivot) and compares the
model's facing (the mold's +x axis at heading home + θ). Labels with world headings:
`data/games/nm26-semifinal/goalie-facing-labels.json`.

| Facing error against the user | W (white/blue) | E (yellow) | All |
| --- | --- | --- | --- |
| **Model:** median | 23° | 14° | 19° |
| Model: 90th percentile | 84° | 35° | 51° |
| Model: within 20° / within 45° | 42% / 78% | 65% / 95% | 54% / 87% |
| **Model: front and back wrong (error over 90°)** | **9%** | **0%** | **4.5%** |
| Model: mean signed error (crops within 90°) | −11° | +1° | |
| Silhouette search (120 crops): median / front-back wrong | 48° / 37% | 25° / 20% | 40° / 28% |

- **The model reads front and back.** It agrees with the user on front/back in 191 of 200 crops, which the silhouette
  search cannot (it gets 28% backwards). So the model learned more from the renders than the outline alone: the
  mask, the back print and the shading.
- **E (yellow) works:** median 14°, no flips, no bias. That is close to what a tap label can resolve.
- **W (white) has one failure pattern** (`validation/goalie-facing-worst.jpg`, the 16 largest errors, all at W; user
  pink, model green): the goalie turned with its back to the camera and towards its own goal's far post, the number on
  its back in view. The user marks it facing up and to the left (away from the camera, towards the cage); the model says
  it faces the rink (+x). The same pose recurs across games 3-7, so it is a systematic error, not noise. The W crops also
  carry a −11° bias (the model turns the goalie clockwise of the user's direction).
- **Label precision is not measured.** A tap 5 mm off at 54 mm from the pivot is about 5°; no crop was marked twice.

**Verdict (PROPOSED, now with real labels):** trained only on renders, the model gives the goalie's facing to a median
19° and gets front and back right in 95.5% of real crops: the yellow goalie to 14° with no flips, the white goalie to 23°
with a 9% flip rate concentrated in one pose. Slot position agrees with the silhouette search to 5 mm (not
user-checked).

## 3. Limitations

- **One labeller, one pass.** The 200 facing labels are the user's single taps; their precision is not measured, and
  the slot position has no user labels.
- **The silhouette search is not ground truth.** It uses the same model mesh and the same camera, so a shared error
  (camera height, mesh) passes both. Its own median best F1 is only 0.50 on real crops (hands, sticks, plate remnants, blur).
- **Assumptions:** the camera (one degree of freedom fixed), the pivot on the slot centreline, the 54 mm goalie mesh
  and its kit colours, the plates with goalie remnants.
- **Occlusion:** hands, sticks and skaters in front of the goalie are only partly represented (distractors, no hands).
- **One table, one camera.** Nothing here transfers to another broadcast without a new calibration and plates.

## 4. Next steps

1. **Real labels: done** (2026-10-09; label page https://claude.ai/artifact/PZYZ99CUBmmQkp8pjKnbr6, built by
   `scripts/synth/goalie-facing-page.py`, crop list `data/games/nm26-semifinal/goalie-facing-crops.json`).
2. **White end:** check the W goalie's back print and kit in the renders against the failure pose
   (`validation/goalie-facing-worst.jpg`), render more of that pose, and fine-tune on part of the 200 labelled crops
   (keeping the rest for testing).
3. **Temporal model:** smooth the per-frame output (or predict from 3-5 frames) to remove the front/back jumps.
4. **Then skaters:** the same pipeline per slot, with occlusion by the neighbouring figures; that is the step that
   would feed figure poses into the pass map and into Remotion reconstructions of real NM26 plays.
