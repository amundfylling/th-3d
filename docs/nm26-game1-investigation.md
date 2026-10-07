# NM 2026 semi-final, game 1: how to map every pass with exact coordinates

Status: investigation only (2026-10-07). The user asked for "a deep investigation into game 1 to find out the best way
forward to map out every single pass with exact coordinates". Nothing in the analysis pipeline was changed. The
scratch scripts used here are not committed.

**Source:** `references/index.json` → `user_game_video_nygard_vs_fjermestad_nm26_semifinal`.
- Seven games, about 59 minutes, from a GitHub release.
- The video is not in git; it is downloaded to `out/dl/nm26.webm`.

## The facts this rests on

| Topic | Finding | How |
| --- | --- | --- |
| Decoding | AV1 1080p30. OpenCV here can't decode AV1; PyAV with libdav1d decodes about 290 frames per second | probe |
| Game 1 window | Starts with the timer tone at 21.6-25.0 s of the video. 3-3 after regulation (the overlay shows 3-3 from about 200 s to 530 s). Fjermestad's overtime goal at about 535 s; the series shows 0-1 from 539 s. Matches the user's result 3:4 OT | overlay crops every 1 s, audio spectrum |
| Teams | Nygård white/blue, Fjermestad yellow (overlay panel colours). In game 1, Nygård's goalie is at the left end | user, overlay, frames |
| Goals | The overlay's game score changes at each goal (first change at about 92 s). The digits change by a few pixels, so a digit reader is needed, not a pixel-change threshold. Overlay updates may lag | overlay crops |
| Camera | Fixed, but the table moves in the image by up to about 20 px (mostly sideways) over the game. All 15,750 frames registered to one reference frame (ORB + RANSAC on the rink and housing): **0 failures** | `stab_det.py` |
| Scale | The rink is about 1500 px wide: about **0.6 mm/px** along the rink and **1.4-1.7 mm/px** across it (rough homography from the lines) | line landmarks |
| Calibration | A slot-chamfer fit like the Fylling video's did not converge from rough hand points (median 8-9 px). It needs a careful one-time anchored fit per camera position, as before. The rink markings are symmetric, so the end orientation must come from the slot layout. **Not done yet** | `calib*.py` |
| The puck at rest or slow | A clear black disk, about 40 × 22 px (far side) to 44 × 27 px (near side). A simple shape and colour rule finds exactly one in **32%** of game-1 frames; 67% none (hidden by figures, merged with a figure's dark trousers, or moving) | `det_g1.json` |
| The puck in flight | Visible in every frame as a grey motion-blurred smudge (about 50-80 px per frame on passes and shots), checked frame by frame on one shot | frame strip, frames 1410-1425 |
| Smudges along passes | In 52 jumps of the disk detector (passes or shots), **98%** of the frames in between contain a moving grey smudge near the straight line between the ends. This is an upper bound: moving figures near the line count too | `gapcheck.py` |
| Simple gap tracker | With a rink mask, a greedy nearest-smudge tracker follows plausible pass paths, including board bounces. It also picks up figure blur where figures move next to the puck, so a real tracker is needed | `gaptrack.py`, 6 tracks viewed |
| Precision | A puck centroid is good to 1-2 px: about 1 mm along the rink and 2-3 mm across. A careful calibration adds about 2-3 mm. The puck's height (top face about 12 mm above the ice) biases the centroid toward the camera by a known amount that can be corrected | scale above |

Compared with the handheld Fylling video:
- the puck is 4-5 times larger;
- the camera is fixed;
- the puck is visible in flight.

Precise frame-by-frame pass lines are realistic here; with the Fylling video they were not.

## Recommended way forward (cheapest in tokens that still gives exact lines)

The principle: let scripts do all the per-frame work, look at a picture only for the one-time calibration and for spot
checks, and let the user confirm the few uncertain passes in a click page.

1. **Per game, scripted (about 15 min of compute, no images):**
   - **Stabilise:** as in this investigation.
   - **Detect two kinds of puck:**
     - the black disk (slow or resting);
     - the grey moving smudge, found by background and frame difference, neutral colour, inside the rink mask.
   - **Track:** a tracker with constant velocity, friction and reflections off the calibrated board outline, choosing
     between the candidates of both kinds. The existing Viterbi tracker extended with a motion model, or a small
     multi-hypothesis tracker.
2. **Calibrate once per camera position:** hand anchors on slot ends and line intersections, one overlay image to
   check it, then the slot-chamfer refinement. The camera did not move in game 1. The table shifts, but the per-frame
   registration absorbs that.
3. **Segment the track into flights.** A flight is a straight run at speed between two contacts; a board bounce is a
   corner. This is the pass-line fit already in `scripts/game-passes.py`, but on every frame's position instead of
   sparse detections, so each line rests on 5-30 points.
4. **Who passed to whom:** the skaters' reach areas (`scripts/game-possession.py`), with the passer at the flight's
   start and the receiver at its end. Figures don't need tracking for the lines. Contested areas are left to step 5.
5. **Confirm page (the user, about 5-10 min per game):** a page that steps through the passes with the video crop and
   the measured line. The user presses OK, drags an end, or fixes the passer or receiver. My token cost per game then
   stays near zero.
6. **Goals and stoppages:** read the overlay's game score per second with a small digit template (the digits are a
   fixed font), so the pass map can exclude dead puck time.

**Expected result:** every pass from release to reception, as a polyline with board bounces, in table millimetres to
within a few millimetres, for all seven games.

**Effort:**
- building steps 1-4 and 6 once, plus the click page;
- then running the scripts for each game and a short confirmation by the user.

## Open points

- **Calibration:** must be done carefully once; this view is new.
- **Which end is which per game:** the 2-2-1-1-1 end changes (user) must be checked against the goalie colours in each
  game.
- **One-touch passes:** at 30 fps a fast one-touch pass shows as a bend in a flight. The tracker will see it as two
  flights with a contact, and only the click page can say whether it was a pass.
- **Hidden ends:** a puck behind a figure is the main remaining gap. The puck is usually visible again within a few
  frames, and the flight's line extends to it.
