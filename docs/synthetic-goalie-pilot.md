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
- Validation: the renders with seed ending in 9, composited with fixed randomness. **Correction (found 2026-10-09):**
  a seed ending in 9 is odd, so in the first run (even seeds W, odd E) all 500 validation renders were E. The first
  run's synthetic numbers below are for the yellow goalie only. The white-goalie runs (section 5) validate both ends.

## 2. Results

Run on 2026-10-09: 5,000 renders (4,500 train, 500 validation), 12 epochs, 2.5 min per epoch on 4 CPU cores.
Numbers from `out/synth/train-report.json` and `out/synth/eval-real.json`.

**Synthetic validation (composited renders the model never saw; E only, see the correction in 1E):**

| Epoch | θ error median | θ error p90 | u error (mean) |
| --- | --- | --- | --- |
| 1 | 13.1° | 30.2° | 0.151 (about 13 mm) |
| 6 | 2.5° | 6.9° | 0.053 |
| 12 | **1.2°** | **3.1°** | **0.0097 (about 0.8 mm)** |

So on its own (yellow-goalie) renders the model reads the pose almost exactly, front and back included.

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

### White-goalie fix (2026-10-09, at the user's request)

**Cause.** Renders of the W goalie at the user's and the model's headings, next to the failing crops, show that the
reference kit does not look like the NM26 W goalie: on the NM26 table it has blue legs and pads below a white jersey, a
"1" on the back (reference print "FINLAND 31"), and a darker, more saturated blue. The user's labels match what the
crops show (at about 103° the back faces the camera squarely; at 120-130° the goalie is turned with the "1" in view).

**Changes:**
- `render-goalie-crops.py ... W nm26`: the "nm26" kit for the W goalie. Kit faces below a jersey hem of 22, 26 or 30 mm
  (picked at random) become blue; the reference kit is kept in 15%; the back print is the reference "1" alone
  (`out/synth/textures/print_goalie_FIN_1.png`, generated); the blue is darker and more saturated, set from the real
  crops (sRGB median (34, 57, 116) against the reference renders' (75, 96, 146)). The hem heights and colours are
  traced by eye from broadcast crops: **assumed**, not measured on a figure.
- 2,500 new W renders (`out/synth/train_w2`, seeds 10000-12499); the old W renders with the reference kit are left out
  (`--drop-ref-w`). Training set: 2,000 E (first batch) + 2,250 W; validation 500 E + 250 W.
- `train-goalie-pose.py --real-train`: the user's labelled crops of games 1, 2, 4 and 6 (112 crops) join training,
  each repeated 6 times per epoch with light degradations; games 3, 5 and 7 (88 crops: 44 W, 44 E) are the real test
  set. `--real-u-from`: slot-position targets for those crops from the renders-only model (without them the slot
  output drifted on real images, see run B).

**Results** (facing error against the user: median / 90th percentile / front-back wrong; "test" = games 3, 5, 7, whose
labels no model saw; "slot" = median slot difference from the silhouette search, 120 crops; "jumps" = rotation steps
over 90° in 10 s of game 5, 300 frames):

| Model | Trained on | Test W | Test E | Slot W / E | Jumps W / E |
| --- | --- | --- | --- | --- | --- |
| First pilot (`goalie-pose.pt`) | reference-kit renders | 27° / 80° / 9% | 15° / 31° / 0% | 5.6 / 5.2 mm | 8 / 0 |
| A (`goalie-pose-v2a.pt`) | renders, NM26 W kit | 14° / 40° / 0% | 13° / 35° / 0% | 4.2 / 6.1 mm | 4 / 0 |
| B (`goalie-pose-v2b.pt`) | A + real labels (rotation only) | 5° / 18° / 0% | 5° / 15° / 0% | 12.4 / 7.0 mm | 0 / 0 |
| **C (`goalie-pose-v2c.pt`)** | **A + real labels + slot targets from A** | **5° / 16° / 0%** | **5° / 16° / 0%** | **4.2 / 6.2 mm** | **0 / 0** |

- **The kit fix alone (A, still no real labels) removes the white end's front/back failures:** 0% flipped in the test
  games (1 of 100 over all W crops), the median halves to 14°, and the −11° W bias drops to −2.5°.
- **A hundred labelled crops then bring both ends to about 5°** (C): about the precision a single tap allows. In
  10 s of continuous video the W rotation no longer jumps (rotation step p95 9°, was 31°).
- **C is the model to use.** B reads the rotation as well but its slot position scatters on real W crops (12 mm from
  the search); C keeps A's slot accuracy.
- Before/after on the 12 largest first-pilot errors in the test games: `validation/goalie-facing-fixed.jpg` (user pink,
  model green); the worst went from 115° to 2°. Silhouette overlays of C: `validation/synth-goalie-pilot-real-goalie-pose-v2c.jpg`.
- Numbers: `out/synth/facing-eval-goalie-pose-v2c.json`, `out/synth/eval-real-goalie-pose-v2c.json` (and -v2a, -v2b),
  training logs `out/synth/goalie-pose-v2*-report.json`. Over all 200 crops C is at 2.6° (W) and 2.8° (E), but half of
  those were training labels; only the test numbers above are fair.

## 3. Limitations

- **Small real test set.** 44 crops per end from three games; the same table, figures and camera as the training
  labels. A new event or table needs new plates, a kit check and some labels.
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
2. **White end: done** (section "White-goalie fix"; model C, `out/synth/goalie-pose-v2c.pt`).
3. **Temporal model:** smooth the per-frame output (or predict from 3-5 frames) to remove the front/back jumps.
4. **Then skaters:** the same pipeline per slot, with occlusion by the neighbouring figures; that is the step that
   would feed figure poses into the pass map and into Remotion reconstructions of real NM26 plays.

## 5. Skaters (2026-10-09, at the user's request)

The same approach for the ten skaters.

**Kit check.** Renders of the reference skater kits against real crops: the layout matches (white or yellow jersey, blue
pants, light socks, blue skates); only the blue differs (real sRGB median (40, 60, 114) against (69, 96, 151)), the
same gap as on the W goalie. Kit "nm26" (`scripts/synth/skater_kits_nm26.py`) gives every blue material the goalie's
NM26 blue. Status: assumed from broadcast crops.

**Pipeline:**
- `scripts/synth/skater-frames.py`: 40 random live-play frames per game, registered to the reference frame.
- `scripts/synth/skater-plates.py`: rink plates (per-pixel median, all 280 frames and per game).
- `scripts/synth/render-skater-crops.py ... nm26`: 6,000 renders (600 per skater). All twelve figures on the ice at
  random positions and rotations (no pivot closer than 60 mm), so neighbours and occlusion are real; puck in 40%;
  200 x 200 crop around the target's pivot with up to 16 px offset (the localiser's error).
- `scripts/synth/train-skater-pose.py`: ResNet-18 with a one-hot plane per skater (which figure in the crop is meant).
- Real labels: the user's label page (https://claude.ai/artifact/64gKazbqzoPrksuutxE7Nm, 400 crops, 40 per skater,
  centred by a kit-colour localiser along the slot): two taps per crop, feet and facing. 352 poses, 48 "can't see it"
  (`data/games/nm26-semifinal/skater-labels.json`, `scripts/synth/skater-labels.py`). The feet taps lie a median
  3.9 mm from the slot centreline: consistent with the geometry.
- Evaluation: `scripts/synth/eval-skater-real.py` (games 3, 5, 7 held out, 152 labelled crops).

**Results** (rotation error against the user: median / 90th percentile / front-back wrong; slot = position along the
slot against the user's feet tap):

| Model | Trained on | Test rotation | Test slot |
| --- | --- | --- | --- |
| v1a (`skater-pose-v1a.pt`, 8 epochs) | renders only; predicts u directly | 14° / 35° / 1.3% | 18 mm median, 54 mm p90 |
| **v2b (`skater-pose-v2b.pt`, 10 epochs)** | **renders + user labels of games 1, 2, 4, 6; predicts the pivot pixel** | **7.0° / 17.5° / 0%** | **1.3 mm median, 3.6 mm p90** |

Per skater (v2b, test games): rotation 5-11° median (worst W-RD 10.9°, E-LD 9.5°), slot 0.8-2.3 mm, no front/back error.
Sheet: `validation/skater-pose-v2b-real.jpg` (the six largest test errors first, then ten at random; user pink, model
green, model pivot as a green dot). The largest errors are crowded scenes (two figures overlapping), one skater behind
the corner plexiglass, and one crop where the model put the pivot on a neighbouring figure (39 mm).

**What changed between v1 and v2.** v1 predicted the slot position u directly; from a 200 px crop of a slot up to
495 mm long it read it worse than the crop centre (17 mm against the user, while the crop centre was 4 mm from the user).
v2 predicts where the pivot is in the crop; u follows from the crop origin and the camera. The compositor now returns
its affine so the pixel label follows the augmentation.

**Caveats.**
- v2 was only trained with the real labels: a renders-only v2 (to separate the head change from the labels) was not
  run. The container restarted twice; v1a stopped at 8 of 12 epochs, the first v1b was stopped in favour of v2.
- The real crops are centred by the localiser (4 mm from the user); on full video the localiser must find each skater
  first. The slot accuracy holds only when it does.
- The test labels come from the same table and camera, one labeller, one pass.
