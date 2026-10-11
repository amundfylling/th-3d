# Trained models: where they live and how to fetch them

Every NM26 figure and puck track in this repository comes from one of four trained networks. The weights are not
committed (`out/` is ignored); they are published as assets of the GitHub release
[`nm26-models-v1`](https://github.com/amundfylling/th-3d/releases/tag/nm26-models-v1) and listed, with their sha256,
in `data/models/manifest.json`. Written 2026-10-11. All model outputs are PROPOSED.

## Fetch (the one way)

```
npm run models:fetch                       # all four, into out/synth/
python3 scripts/fetch-models.py goalie-c   # one model by id
python3 scripts/fetch-models.py --list     # local state of each: missing / ok / differs
```

- Standard library and `curl` only. Each download is written to a `.part` file, checked against the manifest's sha256
  and only then moved into place, so a broken download never leaves a model behind.
- A local file that already matches is kept. A local file with a different sha256 (a model retrained here) is **not**
  overwritten: the script says so and exits 1. `--force` replaces it with the published file.
- The NM26 rebuild runner calls it as step `fetch-models` in stage `fetch` (`npm run rebuild:nm26:fetch`, and the first
  stage of `rebuild:nm26:from-zero`). Every rebuild step outside stage `models` that reads a `.pt` file gets it from
  there; `tests/synth/test_models_manifest.py` checks that.
- The repository is private, so the download needs GitHub credentials (the cloud container's proxy supplies them, as for
  the broadcast video).

## The four models

| id | file | made by | behind | status |
| --- | --- | --- | --- | --- |
| `goalie-c` | `goalie-pose-v2c.pt` (44.8 MB) | `synth/train-goalie-pose.py` (docs/synthetic-goalie-pilot.md) | goalie columns of `<g>/figure-tracks.json` (and so of the smoothed and v3 tracks); the hat-trick evidence sheets | exact |
| `skater-v2b` | `skater-pose-v2b.pt` (44.9 MB) | `synth/train-skater-pose.py` (docs/synthetic-goalie-pilot.md) | skater columns of `<g>/figure-tracks.json` and `figure-tracks-smooth.json` | exact |
| `skater-v3` | `skater-pose-v3.pt` (44.9 MB) | `synth/train-skater-v3.py`, three runs (docs/tracker-v3.md) | `<g>/figure-tracks-v3.json` | exact |
| `puck-v1` | `puck-det-v1.pt` (1.1 MB) | `synth/train-puck-detector.py` (docs/synthetic-puck.md) | `<g>/puck-track-synth.json` | exact |

`status` in the manifest: **exact** means the file is the one that produced the committed tracks (confirmed by the
thread that trained it, from file times against the tracking runs); **retrained** would mean it was rebuilt from the
repo's scripts, and tracks rebuilt from it may differ slightly (random augmentation, thread scheduling).

Skater v3 was trained from timm's ImageNet ResNet-18 (RSB A1). Those start weights are public and are not republished;
the manifest names their URL and sha256 (`start_weights`), and `train-skater-v3.py` expects them at
`/root/.cache/torch/hub/checkpoints/alt/resnet18_a1.pth`. Only training needs them.

Intermediate checkpoints (goalie A and B, skater v1a, skater v3 ep4/ep16, puck v0, the first goalie pilot) are not
published: no committed output reads them. Retraining goalie C needs goalie A (`--real-u-from`), so goalie C is the
starting point to publish, not A.

## Adding or replacing a model

1. Upload the `.pt` file to a release. Use a **new tag** (`nm26-models-v2`, ...) for changed weights; never replace an
   asset under an existing tag, because the committed sha256 would stop matching.
2. Add or update its entry in `data/models/manifest.json`: `file`, `local_path`, `sha256`, `size_bytes`, `status`,
   `provenance`, `produced`, `doc`, `trained_by`, `loaded_by`. For a new tag, move the manifest's `release` to it and
   upload the unchanged models there too (one tag holds the whole set).
3. Run `npm test` (the manifest test) and `python3 scripts/fetch-models.py --list`.

Sessions in this project cannot create releases (GitHub refuses "creating releases ... for this session type"), so the
upload in step 1 is done by the user in the GitHub web interface.
