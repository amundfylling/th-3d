# Synthetic puck detector for the NM26 broadcast

Status: PROPOSED (2026-10-10, batch workstream 1, at the user's request). Model output; no puck position here is
user-checked. Same approach as the goalie and skater models (`docs/synthetic-goalie-pilot.md`): Blender renders in the
NM26 reference camera, composited on real NM26 pictures.

**Since 2026-10-10 (docs/nm26-new-tracks.md):** the NM26 analysis reads this detector's track (`puck-track-synth.json`); the before/after effect on passes,
patterns, combinations, replays and the Edwall refit is in docs/nm26-new-tracks.md by default (`scripts/nm26_tracks.py`).

**Question.** The current puck track (`<game>/puck-track.json`, `scripts/nm26-track.py`) finds the puck as a dark
disk at rest or as a grey smudge in a straight fast run. It loses the puck in passes and shots, exactly where the
rebuilds, the combination recognition and the replays need it (`docs/rebuild-g2-edwall.md`: "the automatic puck track
jumps between unrelated places in these windows and misses the pass and the shot"). Can a detector trained on renders
of a moving, blurred, partly hidden puck do better?

## 1. Pipeline

| Step | Script | Output (under `out/` = generated, not committed) |
| --- | --- | --- |
| A. Register and sample real frames | `scripts/synth/puck-frames.py <game>` | `out/nm26/<game>/H.npz`, `out/synth/puck/real/` |
| B. Render pucks | `scripts/synth/render-puck-crops.py <dir> <seed> <count>` | `out/synth/puck/renders/` |
| C. Blob-to-top offset | `scripts/synth/puck-blob-offset.py` | `out/synth/puck/blob-offset.json` |
| D. Train | `scripts/synth/train-puck-detector.py` | `out/synth/puck-det-v1.pt` |
| E. Evaluate (held-out games) | `scripts/synth/eval-puck-detector.py` | `out/synth/puck-det-v1-eval.json` |
| F. Track a game | `scripts/synth/track-puck.py <game>` | `data/games/nm26-semifinal/<game>/puck-track-synth.json` |
| G. Compare with the current track | `scripts/synth/puck-compare.py` | `data/games/nm26-semifinal/puck-synth-compare.json` |
| H. Review sheets | `scripts/synth/puck-review-sheet.py` | `validation/synthetic-puck-*.jpg` |

Inputs: the NM26 video (`out/dl/nm26.webm`, release URL in `config.json`), each game's `background.png` (empty rink,
stab px), `camera-ref.json`, `geometry.json`, the current `puck-track.json` (only to pick real training frames) and
`assets/scene/full_static.blend`. Environment: the Blender venv (`/root/venvs/blender`, Python 3.11, bpy 4.5, PyAV,
OpenCV) plus PyTorch (CPU).

## 2. Method

**A. Real frames (`puck-frames.py`).** One pass over each game window, four processes.
- Registration: every 6th frame and every sampled frame is registered to the reference frame (game 1 at 180 s) with the
  `nm26_common.Registrar` of the current pipeline. Registration is the slow step (about 10 frames/s per process), and the
  camera drifts slowly, so the tracker interpolates between the registered frames.
- Check of the interpolation against per-frame registration (2 s each in games 2, 5 and 6): the worst corner of the ice
  polygon moves a median 1.3-1.5 px, 95th percentile 3-4 px. Part of that is the per-frame registration's own jitter. A
  puck is about 35 px wide.
- Registration fallbacks: none, except 1 in game 5 and 60 in game 6.
- Training backgrounds: 2,324 frame triplets (t-1, t, t+1), 249-360 per game. They are taken only where the current track
  is sure of the puck:
  - 70%: a disk with score >= 2 and disk neighbours within 6 px;
  - 30%: a smudge inside a kept flight run, which gives real motion blur.
- Frames where the current track is unsure are never used, because their real puck would be an unlabelled positive.

**B. Renders (`render-puck-crops.py`, 1,500 samples, 4,500 Cycles frames).**
- Only the puck is rendered, three consecutive frames at 30 fps. Its position is uniform on the ice, with extra weight at
  the boards (20%) and around the goals (15%).
- Velocity: 30% slow (0-300 mm/s), 70% fast (300-6,000 mm/s), constant over the three frames.
- Shutter: open for 20-100% of the frame interval (the broadcast exposure is unknown), centred, with Cycles motion blur.
- Material: matte near-black (base 0.008-0.05, roughness 0.45-0.9). The sun is within 25° of overhead.
- Scene: the ice is a shadow catcher. Goals, boards and screens are holdouts, so the real cage and boards hide the puck
  where the model's do.
- Each frame is its own crop around the swept puck, 24 samples, no denoising. Throughput was about 1 s per frame while
  the frame pass ran alongside.
- The figures are left out on purpose: the detector learns them from the real frames.

**C. Label point.**
- The detector's label is the projection of the puck's top-face centre, 12 mm above the ice (the Blender puck; the real
  thickness is unknown).
- The current track gives the dark blob's centre instead. In the reference camera that centre lies 8.8 px (std 0.3)
  below the top-face centre (`puck-blob-offset.py`, geometry of the projected puck).
- So real labels from the current track are moved up 8.8 px.
- The new track maps its points through the camera onto the 12 mm plane, which gives the puck centre. The current track
  maps the blob centre onto the ice plane, which puts the puck about 13 mm further +y (away from the camera).

**D. Training sample (`train-puck-detector.py`).**
- One sample is a 384 × 256 stab-px crop of a real triplet plus that game's background (empty rink).
- The real puck is either erased or labelled:
  - erased (replaced by the background in all three frames) when it is a resting disk with nothing else near it (50%);
  - otherwise labelled.
- 0-2 synthetic pucks are pasted at their rendered place, frame by frame:
  - occlusion: a real foreground blob covering the puck whose lowest pixel (the figure's feet) is nearer the camera than
    the puck's near edge is drawn over the puck;
  - render pixels that are light and not opaque (the shadow catcher's light-catcher artefact) are dropped;
  - the sprite gets camera blur, gain and offset, and the crop is re-encoded as JPEG (quality 70-95);
  - a puck hidden for more than 75% is not a target, and its region is ignored in the loss.
- Input: the three frames and the background at half resolution, 12 channels.
- Network: a small encoder-decoder (strides 2/4/8, dilated convolutions, skip connections, about 6 GFLOP per full frame).
- Output: a heatmap at 1/4 resolution with CenterNet focal loss, plus a sub-cell offset (L1).
- Training: AdamW with a one-cycle schedule, batch 16, CPU. A 500-step pilot (v0) came first, then 7 × 1,000 steps (v1),
  14 minutes per epoch.
- Validation: games 3 and 7 and renders with seed % 10 == 9. Neither is used for training.

**E. Tracking (`track-puck.py`).**
- Every frame is warped, and the detector sees frames t-1, t and t+1. Up to 6 peaks with score >= 0.05 are kept. A game
  of 300 s takes about 8 minutes on 4 CPUs.
- Then a Viterbi over {absent, peaks}:
  - emission = logit(score), clipped to [-4, 5], **+ 1.0**;
  - motion cost (d / 60 mm)² / 2 per frame, impossible above 350 mm per frame;
  - 3.0 to enter or leave "absent".
- The +1.0 emission bias was chosen with the frame review below. Without it, the track keeps only confident peaks: 60-65%
  of frames in games 1-2, against 80% with it.
- No interpolation: frames without a chosen peak are "not seen", as in the current track.

## 3. Results

### Detector on held-out games (`out/synth/puck-det-v1-eval.json`, games 3 and 7)

| Test set | n | Recall (peak >= 0.3 within 12 px) | Location error (median) |
| --- | --- | --- | --- |
| Real puck, resting disk (current track sure) | 280 | 86% | 1.0 px |
| Real puck, smudge in a flight (current track) | 147 | **44%** | 4.2 px |
| Synthetic, 0-300 mm/s | 179 | 82% | 0.8 px |
| Synthetic, 300-1,500 mm/s | 97 | 89% | 1.0 px |
| Synthetic, 1,500-3,000 mm/s | 75 | 89% | 1.2 px |
| Synthetic, 3,000-6,000 mm/s | 129 | 90% | 1.8 px |
| Synthetic, 50-90% visible (hidden by real figures) | 49 | 86% | 2.2 px |

There are 0.23 extra peaks per real crop (384 × 256 px).

- **The gap:** on renders, fast pucks are found as well as slow ones (90%), but only 44% of the real smudges are.
- Part of that 44% is the reference itself: the frame review below finds the current track's lone positions mostly on
  figure blur.
- Part is a real domain gap: real streaks of a shot are fainter than the renders.

### Whole games against the current track (`data/games/nm26-semifinal/puck-synth-compare.json`, live play only)

| Game | Coverage old → new | Both: within 15 mm | Old only | New only | Old: steps > 7 m/s |
| --- | --- | --- | --- | --- | --- |
| 1 | 75.4% → 77.2% | 81% | 8.5% | 10.3% | 0.5% |
| 2 | 78.1% → 79.2% | 82% | 8.6% | 9.6% | 0.3% |
| 3 | 72.8% → 83.7% | 71% | 6.9% | 17.8% | 0.3% |
| 4 | 68.8% → 82.1% | 78% | 7.7% | 21.0% | 0.2% |
| 5 | 73.2% → 83.7% | 81% | 4.9% | 15.5% | 0.3% |
| 6 | 51.2% → 54.2% | 81% | 6.5% | 9.5% | 0.2% |
| 7 | 70.7% → 70.4% | 82% | 8.9% | 8.6% | 0.4% |
| **All** | **70.3% → 76.4%** | **80%** | | | **0.3% → 0.0%** |

- The new track never makes a physically impossible step (over 7 m/s between frames). The old one does in 0.3% of
  steps.
- Where both tracks have a position, they agree to a median of 4-5 mm (one convention, see 2C).
- Game 6 is low for both tracks. A possible cause is its 60 registration fallbacks; not investigated.

**Goal windows** (the 25 goals the user marked; the moment the puck crosses the line):

| | Old | New |
| --- | --- | --- |
| Coverage, last 2 s before the goal | 78.0% | **84.3%** |
| Coverage, last 0.5 s | 74.0% | **82.2%** |
| Puck seen in the last 0.2 s | 6 of 25 | **16 of 25** |
| Distance from the goal at the last sighting (median) | 195 mm | 178 mm |
| Puck seen at the goal mouth (-1.0 to +0.5 s) | 1 of 25 | 1 of 25 |

- Goals not marked by the user (box time - 12 s), games 5-7: coverage 52%/34%/36% (old) → 72%/37%/39% (new).
- The shot flight itself is still missed by both. The new track follows the puck to the release (16 of 25 goals within
  0.2 s of the goal), then loses it for the last 2-5 frames. At 3-6 m/s the puck crosses 180-200 mm in that time, as a
  faint streak.

**Passes and shots of the current pipeline** (`passes.json`). These are flights found by the old track, so the
comparison favours it:

| | Old | New |
| --- | --- | --- |
| Pass frames covered | 82.7% | 80.1% |
| Shot frames covered | 80.1% | 81.4% |

The new track's own fast intervals (over 500 mm/s) are covered by the old one only 77% of the time.

### Which track is right where they differ (Claude's frame review)

The first look: the Edwall goals in game 2.
- `validation/synthetic-puck-g2-goal{2,3,4}.jpg`: red = old (blob centre), green = new (top-face centre).
- In goal 3, the old track sits on a dark spot at the near board at the other end, then on figures. The new one follows
  W-RW's carry at the near board and the blurred pass to the centre, and loses the puck at the shot.

Then a sample. 56 frames from games 1 and 2 (`data/games/nm26-semifinal/puck-synth-review-claude.json`,
`validation/synthetic-puck-frame-review.jpg`), drawn from four cases of the bias-1.0 track (one reviewer, one pass, PROPOSED):

| Case (frames in games 1-2) | Sampled | Old on the puck | New on the puck |
| --- | --- | --- | --- |
| A. Both, within 10 px (11,024) | 8 | 8 | 8 |
| B. Both, more than 30 px apart (1,685) | 16 | 0 (14 wrong, 2 unclear) | 9 (2 wrong, 5 unclear) |
| C. Old only (1,850) | 16 | 3 (13 wrong) | — |
| D. New only (2,183) | 16 | — | 9 (5 wrong, 2 unclear) |

Weighted by the case sizes (assuming every frame of A is right, as all 8 sampled were):

| | Old | New |
| --- | --- | --- |
| Positions (live play, games 1-2) | 14,559 | 14,892 |
| On the puck | about 78% | about **89%** |
| Not on the puck | about **20%** | about 6% |
| Unclear | about 1% | about 5% |

- The old track's wrong positions are mostly on figures (blurred kits, blue skates and trousers, sticks), plus "release"
  points beside the real puck.
- The new track's wrong positions are mostly figure blur near the boards and the corner glass.
- The sample is small (16 per case); treat these as rough rates.

## 4. Verdict and use

- **The new track (`<game>/puck-track-synth.json`) should replace `puck-track.json`** as the input for passes, rebuilds,
  combination recognition and replays. It covers more frames (76% vs 70% of live play; 84% vs 78% of the 2 s before
  goals). It has about a third of the wrong positions and no impossible jumps. It follows carries and passes in the goal
  windows that the old track loses.
- **Not yet replaced.** As agreed for this batch, `puck-track.json` is untouched so that the other threads have a stable
  input. Same columns. Two differences matter:
  - x_mm, y_mm are the puck centre (about 13 mm nearer the camera, -y, than the old blob convention);
  - kind is "det" and score is the detector's peak (0-1).
- `scripts/nm26-passes.py` has not been re-run on it. Its thresholds (speed, the 15 mm simplification) were tuned on the
  old track.
- **For the Edwall rebuild (g2-goal2..4):** the new track has W-RW's carry at the near board and the pass to the centre.
  The shot is not in either track; it has to be read by hand or fitted between the release and the goal moment.

## 5. Limitations

- **Shots:** the last 2-5 frames of a shot (faint streak) are missed. Real smudge recall is 44%.
- **No user-checked positions.** All accuracy figures are model checks, renders, or Claude's single-pass review of
  56 frames.
- **Assumed:** the puck thickness (12 mm, sets the label point and the plane), the exposure (shutter 20-100%), the puck
  material and lighting, the interpolated registration (1-4 px), and the occlusion rule (feet nearer than the puck's
  front edge). Hands are not in the renders.
- **The real training labels come from the current track's sure frames.** Its errors there (about 14% of "sure disks" are
  not found by the detector either) leak into training.
- **Only 1,500 renders** and 7,000 training steps on CPU; neither was tuned.
- **The tracker** is first-order (no velocity state) and has no stoppage or hand detection.

## 6. Next steps

1. **Shots:** renders at 6-10 m/s with longer, fainter streaks; a fine-tune weighted to real flight frames; a
   constant-velocity gap filler from the release toward the goal moment.
2. **Switch the pipeline:** re-run `nm26-passes.py` and `nm26-patterns.py` on the new track and compare the pass maps.
3. **A small user truth set:** about 100 taps on hard frames (passes, shots, near boards) on a label page like the goalie
   one. That would measure both tracks properly.

## 7. Reproduce

```sh
/root/venvs/blender/bin/pip install torch torchvision "numpy<2"   # in the Blender venv (docs/blender.md)
for g in g1 g2 g3 g4 g5 g6 g7; do /root/venvs/blender/bin/python scripts/synth/puck-frames.py $g; done      # ~45 min
for c in 0 1 2; do /root/venvs/blender/bin/python scripts/synth/render-puck-crops.py out/synth/puck/renders $((c*500)) 500; done
/root/venvs/blender/bin/python scripts/synth/puck-blob-offset.py
/root/venvs/blender/bin/python scripts/synth/train-puck-detector.py --epochs 2 --steps 250 --name puck-det-v0
/root/venvs/blender/bin/python scripts/synth/train-puck-detector.py --epochs 7 --steps 1000 --name puck-det-v1 --init puck-det-v0
/root/venvs/blender/bin/python scripts/synth/eval-puck-detector.py --n 500
for g in g1 g2 g3 g4 g5 g6 g7; do /root/venvs/blender/bin/python scripts/synth/track-puck.py $g; done        # ~70 min
/root/venvs/blender/bin/python scripts/synth/puck-compare.py
```

The model (`out/synth/puck-det-v1.pt`, 1.1 MB) is not committed, like the other models. The candidates
(`out/nm26/<game>/puck-cands-puck-det-v1.json`) let `track-puck.py <game> --track-only` re-run the tracker in seconds.
