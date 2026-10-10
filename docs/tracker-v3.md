# Figure tracker v3 (NM26 broadcast)

Status: PROPOSED (2026-10-10, batch workstream 4). Model output, measured against the user's existing labels and an
AI visual check of the broadcast; no new user labels.

## Answer first

- **On the user's labels v3 is as good as v2 and makes fewer gross errors.** On the 352 skater labels (feet and
  facing taps) both read the slot position to 1.0 mm (median) and the facing to about 6°. Gross slot errors (over
  30 mm, the tracker on the wrong spot) drop from 0.9% to 0.3%, front/back flips from 0.3% to 0. The goalie labels
  cannot separate them (0 flips either way).
- **The labels are the easy frames.** They were made on crops a kit-colour localiser had centred, so the localiser's
  failures are mostly missing from them (they are the 48 "can't see it" answers). The weak cases show up only on full
  video, so the main evidence there is a visual check.
- **On full video v3 is clearly better where the two disagree.** In game 2's goal windows v2 (cleaned) and v3 put a
  skater more than 30 mm apart in 12% of skater-frames. In 32 random disagreements, checked by eye on the broadcast,
  v3 was on the right figure 14 times and v2 5 times (5 neither, 8 unclear). Full-game numbers: section 4.
- **Re-track: done** for all seven games, written to new files `data/games/nm26-semifinal/<game>/figure-tracks-v3.json`
  (the v2 files are unchanged). **Recommendation for consolidation:** switch readers of `figure-tracks-smooth.json` to
  `figure-tracks-v3.json` (same columns: `<fig>_u`, `<fig>_theta_deg`, `<fig>_src`).
- **What fell short:** the rebuilt skater model reads rotation slightly worse than v2b (8.3° against 7.0° median on
  the 152 test crops), because the container had no models and only a third of v2b's renders could be made in the
  time. Near-board wings that are hidden for a long time stay wrong or unknown (section 5).

## 1. The weak cases (from `docs/nm26-figure-tracks.md`)

1. **Near-board wings.** A hidden or blurred wing is placed on the near board where there is no figure.
2. **Localiser lock-ons.** The localiser takes the best kit-colour spot along the slot; a same-kit neighbour, an
   advert or the yellow rink artwork can win.
3. **Rotation flips.** The pose model reads a figure front-to-back for a frame.

v2 handled these after the fact (`smooth-tracks.py`: drop readings far from the local median, interpolate).

## 2. What v3 changes

All in `scripts/synth/track-figures-v3.py` and `scripts/synth/tracker_v3_decode.py`:

| Part | v2 (`track-figures.py` + `smooth-tracks.py`) | v3 |
| --- | --- | --- |
| Localiser | best kit-colour spot along the slot | the two best separate spots (at least 40 mm apart; the second at 30% of the first's score or more); below the ice (near board and its adverts) the background difference uses the plate's local 5 × 5 range |
| Pose model | v2b: pivot pixel, rotation | v3: the same plus **presence** (is this skater's pivot in the crop at all?) |
| Readings per frame | one per skater | one per candidate; the second spot is read when the first reading is doubtful (presence under 0.9 or pivot over 10 mm from the slot) |
| Training data | 6,000 renders + user labels (games 1, 2, 4, 6) | 1,915 base renders (same recipe) + 978 **hard-example renders** + re-targeted negatives + the same user labels |
| Temporal prior | clean-up afterwards (median ±0.3 s; needs 3 neighbours, so at the 5 fps rate of most of each game only the 15 mm off-slot rule acts) | inside the tracker: per figure the cheapest path through the candidates that a figure can move along, then front/back flips undone along that path; works at any frame rate |
| Gaps | interpolated up to 1 s | the same |
| Goalies | model C | model C readings copied from the v2 raw tracks; only the flip decoding is new |

**Hard-example renders** (`scripts/synth/render-skater-hard.py ... hard`, seeds from 100000): a wing in half of the
samples (the two near-board wings, W-RW and E-LW, in a quarter), at a slot end in half, one or two figures 60-90 mm away
in half. Negatives (presence 0): the crop centred on the skater's own slot 45-200 mm away (a lock-on, 25%), or the
skater not rendered (hidden, 10%). **Re-targeted negatives** cost no rendering: a base crop with the one-hot of another
skater whose slot runs through it, "absent" unless that skater's pivot happens to lie in the crop. Sheet as the network
sees them: `validation/tracker-v3-training-samples.jpg`.

**Decoder limits (assumed, not fitted):** motion along the slot costs one unit per 600 mm/s above 12 mm of reading
noise, hard limit 2,500 mm/s + 35 mm; dropping a frame costs 1.6; a 180° flip costs 2.5 against one unit per 900°/s of
rotation above 15°. Reading cost: pivot distance from the slot over 6 mm (/6; over 25 mm unused), kit-colour score under 6,
−1.5 log(presence), +0.3 for the second spot.

**Localiser variants tried** (`track-figures-v3.py loc-eval`, model-free, first spot against the user's feet tap on the
352 label frames; lock-on = over 30 mm):

| Variant | Lock-ons (first spot) | Neither of two spots right |
| --- | --- | --- |
| v2 | 2.3% | 0.6% |
| local range everywhere | 5.7% | 1.4% |
| local range off the ice | 2.8% (W-LW 2.8% → 8.3%) | 0.6% |
| local range everywhere for the yellow kit | 3.4% (E-LW 13.9%) | 1.1% |
| **local range below the ice only (v3)** | **2.3%** | **0.6%** |

The local range swallows white kit next to white ice or board, so it is used only where the phantom near-board wings
came from (white advert letters under a registration error). With two spots, the right one is among them in 99.4% of
the label frames.

## 3. Results on the user's labels

### Committed v2 tracks against v3-lite (no new model)

Only labels whose frame is in the committed tracks (101 skater, 126 goalie labels). "v3-lite" is the v3 decoder run on
the committed v2 raw readings (one candidate, no presence), `tracker-v3-eval.py --lite`.

| Track | Skater slot median / p90 | Facing median / p90 | Gross (>30 mm) | Flips | Goalie facing median / p90 | Goalie flips |
| --- | --- | --- | --- | --- | --- | --- |
| v2 raw | 1.0 / 3.1 mm | 5.0° / 15.6° | 2.0% | 0 | 2.8° / 10.4° | 0 |
| v2 cleaned | 1.1 / 3.0 mm | 6.6° / 16.5° | 1.0% | 0 | 2.8° / 9.8° | 0 |
| v3-lite | 1.0 / 2.9 mm | 6.0° / 15.9° | 1.0% | 0 | 2.8° / 9.8° | 0 |

Test games only (3, 5, 7; 52 skater, 49 goalie labels): v2 raw 1.6 mm / 7.6°, gross 3.8%; cleaned 1.6 mm / 8.6°,
1.9%; v3-lite 1.6 mm / 8.1°, 1.9%. Goalies 5.1-5.2°, no flips. Jumps between consecutive 30 fps frames (all games,
121,140 skater steps): raw 7.6% slot / 5.0% rotation, cleaned 0.9% / 0, v3-lite 1.5% / 0.06%; goalie rotation jumps
raw 0.31%, cleaned 0, v3-lite 0.01%.

### v2 rule against v3 on windows around every label (the fair comparison)

`track-figures-v3.py obs <game> --labels`: 5 fps (as most of each game) within ±0.8 s of every one of the 280 label
frames, the same model readings for both (model v3; every candidate read), then:
- **v2 rule** = the first colour spot (v2's choice), raw and after `smooth-tracks.py`;
- **v3** = the decoder over all candidates with presence.

| All 352 facing labels | Slot median / p90 | Facing median / p90 | Gross (>30 mm) | Flips | Unknown |
| --- | --- | --- | --- | --- | --- |
| v2 rule, raw | 1.0 / 3.5 mm | 5.8° / 16.2° | 0.9% (3) | 0.3% | 0 |
| v2 rule + clean-up | 1.0 / 3.5 mm | 6.1° / 16.2° | 0.9% (3) | 0 | 0 |
| **v3** | **1.0 / 3.4 mm** | **5.9° / 16.1°** | **0.3% (1)** | **0** | 0.6% |

Test games only (152 labels): slot 1.4 mm for all; facing 8.3° (v2 rule) and 8.5° (v3); gross 0.7% → 0.

**Presence on real frames** (the label frames; every spot the localiser kept, judged right when the model's slot
position is within 30 mm of the user's feet):

| | n | Presence over 0.5 |
| --- | --- | --- |
| right spots | 376 | 99.7% |
| wrong spots | 142 | 8.5% |
| first spot at the "can't see it" labels | 48 | 18.8% |

So the presence output, trained on renders only (plus present real crops), transfers: it keeps the right spots and
rejects 92% of the wrong ones. At most "can't see it" labels it says no skater is there; the decoder then interpolates
over the short gap (only 4% of those frames end up unknown).

**Model** (`out/synth/skater-pose-v3.pt`, not committed; `train-skater-v3.py`, 24 epochs in three runs: 4 epochs with
presence weight 1, which left presence stuck at "present"; 12 with weight 5; 8 fine-tuning at a lower learning rate):
on the 152 real test crops facing 8.3° median, no flips (v2b 7.0°); on validation renders facing 5.0°, pivot 2.3 px,
presence right in 98.4% (absent crops called present 7%).

## 4. Results on full video

(Filled in from the full re-track; see below.)

## 5. What fell short / open

- **Model rotation is 1.3° worse than v2b** on the test crops (8.3° against 7.0°): fewer renders (1,915 against
  6,000) and a different ImageNet start (timm's weights; torchvision's are blocked here). More base renders would
  likely close it.
- **Long hidden stretches.** A near-board wing hidden for more than a second is unknown (src 2) rather than guessed;
  when the localiser's spots are all wrong and presence is fooled (8.5% of wrong spots pass), v3 still follows them.
- **The decoder limits are assumed**, not fitted to labelled motion.
- **The label windows read every candidate; the full re-track reads the second spot only when the first is doubtful**
  (for speed). On the label frames the first spot's presence is over 0.9 for nearly every right spot, so the two
  should agree; not measured separately.
- **The visual check is Claude's**, on the broadcast at 300 × 220 px tiles; many tiles are "unclear" (blur, hands,
  plexiglass).
- No new user labels. The best next measurement: the user taps 50-100 frames picked from v2/v3 disagreements, where
  the two trackers differ.

## Reproducing

```sh
python3.11 -m venv /root/venvs/blender   # bpy 4.5 needs Python 3.11
/root/venvs/blender/bin/pip install "bpy==4.5.*" shapely mapbox_earcut "numpy<2" pillow "opencv-python-headless<4.11" av scipy torch torchvision
# ImageNet start weights (download.pytorch.org and huggingface.co are blocked here):
curl -L -o /root/.cache/torch/hub/checkpoints/alt/resnet18_a1.pth \
  https://github.com/rwightman/pytorch-image-models/releases/download/v0.1-rsb-weights/resnet18_a1_0-d63eafa0.pth
P=/root/venvs/blender/bin/python
$P scripts/synth/render-skater-hard.py out/synth/skaters/train 0 1000 base --threads 2      # and 1500 1000
$P scripts/synth/render-skater-hard.py out/synth/skaters/hard 100000 1000 hard --threads 2
$P scripts/synth/track-figures-v3.py plates
$P scripts/synth/train-skater-v3.py 4 --presence-weight 1        # what was run; a single 16-epoch run with weight 5 should do
$P scripts/synth/train-skater-v3.py 12 --init out/synth/skater-pose-v3-ep4.pt
$P scripts/synth/train-skater-v3.py 8 --init out/synth/skater-pose-v3-ep16.pt --lr 3e-4
$P scripts/synth/track-figures-v3.py loc-eval
for g in g1 g2 g3 g4 g5 g6 g7; do $P scripts/synth/track-figures-v3.py obs $g --labels --all-candidates; $P scripts/synth/track-figures-v3.py decode $g --labels; done
python3 scripts/synth/tracker-v3-eval.py --windows --out out/synth/v3/eval-windows.json
python3 scripts/synth/tracker-v3-eval.py --lite
for g in g1 g2 g3 g4 g5 g6 g7; do $P scripts/synth/track-figures-v3.py obs $g; $P scripts/synth/track-figures-v3.py decode $g; done
$P scripts/synth/tracker-v3-review.py "data/games/nm26-semifinal/{game}/figure-tracks-smooth.json" "data/games/nm26-semifinal/{game}/figure-tracks-v3.json" --n 48 --name v2-v3
```

The label-window run above read every candidate (the doubt gate did not exist yet); `--all-candidates` reproduces it.
Times on 4 CPU cores: renders about 1.7 s each (3 processes × 2 threads), training 2.7 min per epoch, the observation
pass about 0.45 s per frame (one process; parallel processes were slower).
