# NM26 goal replays

Status: PROPOSED. Drawn from model output (cleaned figure tracks and the automatic puck track); no replay has been
checked against the video frame by frame.

Open `index.html` (in a browser, from this folder) or the published page. Pick a goal; the broadcast clip and the
top-down replay play together (1×, ½×, ¼×, frame steps, "Goal −1 s").

## Rebuild

    python3 scripts/nm26-replays.py                 # all goals: replays, broadcast clips, replays.json, index.html
    python3 scripts/nm26-replays.py g2-goal2        # one goal (the page and replays.json are rewritten for all)
    python3 scripts/nm26-replays.py --no-clips      # replays only (no video needed)
    python3 scripts/nm26-replays.py --page-only     # only replays.json and index.html

Needs Python with opencv-python-headless, numpy and PyAV (libdav1d for the AV1 source). Broadcast clips need the
video at `out/dl/nm26.webm` (`data/games/nm26-semifinal/config.json` → `video.url`, sha256 there). It reads only
committed tracks selected by `scripts/nm26_tracks.py` (since 2026-10-10 `<game>/puck-track-synth.json` and
`<game>/figure-tracks-v3.json`), so rerun it after a new track lands. A full run takes about 7 minutes on 4 cores.

## What is here

| File | What |
| --- | --- |
| `<goal>.mp4`, `<goal>.jpg` | Replay from above, 1044 x 624, 30 fps; poster at the goal moment |
| `clips/<goal>.mp4`, `.jpg` | Broadcast video of the same window, registered to game 1's reference frame, cropped to the rink, 1044 x 384 |
| `replays.json` | Goal list: window, goal moment source, label, data coverage, clip registration |
| `index.html` | The review page (built from `scripts/nm26-replays.template.html`) |

## Goals and windows

- 41 goals in `timeline.json`; 40 have a score-box time and a replay. Game 4's overtime winner (g4-goal5) has none:
  the box never shows it, so there is no time for it.
- 25 goals have the user's goal mark (`goal-labels.json`): window 8 s before to 1 s after it.
- 15 goals (g5-goal3 to g7-goal4) have only the box time. The user's marks put the box 3.0-13.6 s after the goal
  (median 7.9 s), too spread to estimate the moment, so the window is the 17 s from 18 s to 1 s before the box change
  and the page counts time to the box. Marking these 15 goals would let them use the 8 s + 1 s window.

## Limits

- Figures: dot at the pivot, arrow for the facing, a stick to the mold-frame blade point (12, 33) mm. Not the mold
  footprint. Hollow = interpolated (rejected reading, or between 5-per-second readings outside the 30 fps goal
  windows of `track-figures.py`). Unknown figures are left out.
- Puck: seen in 18-100% of the window's frames depending on the goal (`replays.json` → `coverage`); during fast shots
  it is often missing, so the shot itself is the weakest part of each replay. Since 2026-10-10 the puck comes from
  the synthetic puck detector: a black disk when slow (under 0.3 m/s), a ring when faster (docs/nm26-new-tracks.md).
- Blue and centre lines nominal (x = ±120, 0 mm); goals are the preview cage (validation/12-hardware-report.json).
