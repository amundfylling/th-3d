# Figure tracker v3 (NM26 broadcast)

Status: PROPOSED (2026-10-10, batch workstream 4). Model output and an AI visual review; no new user labels.

DRAFT: results below are filled in as the runs finish.

## Why

`docs/nm26-figure-tracks.md` lists three weak cases of the v2 tracker (`scripts/synth/track-figures.py`):
1. **Near-board wings.** A wing that is hidden (plexiglass, a hand, a neighbour) or blurred is sometimes placed on the
   near board where there is no figure: the kit-colour localiser then follows noise.
2. **Localiser lock-ons.** The localiser takes the best kit-colour spot along the slot; when a same-kit neighbour
   stands on or near the slot it can take the neighbour.
3. **Rotation flips.** The pose model sometimes reads a figure front-to-back for a frame.

v2 dealt with these after the fact (`smooth-tracks.py`: drop readings far from the local median, interpolate).

## What v3 changes

All in `scripts/synth/track-figures-v3.py` (with `tracker_v3_decode.py`):

| Part | v2 | v3 |
| --- | --- | --- |
| Localiser | best kit-colour spot along the slot | the two best separate spots (at least 40 mm apart; the second only at 30% of the first's score or more); below the ice (near board and its adverts) the background difference uses the plate's local 5 x 5 range, so a registration error at the adverts' white letters is not a figure |
| Pose model | v2b: pivot pixel, rotation | v3: the same plus **presence** (is this skater in the crop at all?); read at each candidate |
| Training data | 6,000 renders + the user's labels (games 1, 2, 4, 6) | base renders (same recipe) + **hard-example renders** + re-targeted negatives + the same user labels |
| Temporal prior | none in the tracker; separate clean-up | inside the tracker: per figure the cheapest path through the candidates that a figure can move along (speed limits; a frame can be dropped at a cost), then front/back flips undone along that path |
| Gaps | interpolated up to 1 s | the same |

**Hard-example renders** (`scripts/synth/render-skater-hard.py ... hard`): wings in half of the samples (the two
near-board wings, W-RW and E-LW, in a quarter), at a slot end in half, one or two figures 60-90 mm away in half;
negatives: the crop centred on the skater's own slot 45-200 mm away from it (a lock-on), or the skater not rendered at
all (hidden). **Re-targeted negatives** cost no rendering: a base crop with the one-hot of another skater whose slot
runs through the crop; it is "absent" unless that skater's pivot happens to be in the crop.
Sheet: `validation/tracker-v3-training-samples.jpg`.

**Decoder limits (assumed, not fitted):** motion along the slot costs one unit per 600 mm/s above 12 mm of reading
noise, with a hard limit of 2,500 mm/s + 35 mm; dropping a frame costs 1.6; a 180° flip costs 2.5 against one unit per
900°/s of rotation above 15°. Reading cost: the predicted pivot's distance from the slot (over 6 mm; over 25 mm the
reading is not used), a kit-colour score under 6, -1.5 log(presence), and 0.3 for the second candidate.

## Reproducing

```sh
/root/venvs/blender/bin/python scripts/synth/render-skater-hard.py out/synth/skaters/train 0 1500 base --threads 2
/root/venvs/blender/bin/python scripts/synth/render-skater-hard.py out/synth/skaters/hard 100000 1000 hard --threads 2
/root/venvs/blender/bin/python scripts/synth/track-figures-v3.py plates
/root/venvs/blender/bin/python scripts/synth/train-skater-v3.py 8
/root/venvs/blender/bin/python scripts/synth/track-figures-v3.py loc-eval
for g in g1 g2 g3 g4 g5 g6 g7; do
  /root/venvs/blender/bin/python scripts/synth/track-figures-v3.py obs $g --labels
  /root/venvs/blender/bin/python scripts/synth/track-figures-v3.py decode $g --labels
done
python3 scripts/synth/tracker-v3-eval.py --lite ...
```

Environment notes (2026-10-10): the container had no models (they are under `out/`, not committed), so the skater
model was rebuilt. `download.pytorch.org` and `huggingface.co` are blocked, so the ImageNet start weights are timm's
ResNet-18 (RSB A1) from timm's GitHub release (see `train-skater-v3.py`). `bpy` 4.5 needs Python 3.11
(`python3.11 -m venv /root/venvs/blender`).
