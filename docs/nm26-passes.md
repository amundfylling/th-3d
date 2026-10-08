# NM 2026 semi-final: pass mapping, game 1 (first version)

Status: built on 2026-10-07 after the investigation (`docs/nm26-game1-investigation.md`); the user said "Go".
**Proposed.** The candidates are automatic; the user confirms them on the review page, and the confirmed set is the
result.

| Step | Script | Output |
| --- | --- | --- |
| Settings | — | `data/games/nm26-semifinal/config.json` (video, game windows, teams per game, ice polygon) |
| 1. Register and detect | `scripts/nm26-detect.py g1` | `data/games/nm26-semifinal/g1/background.png`, `out/nm26/g1/frames.json` (cache, not committed) |
| 2. Calibrate | `scripts/nm26-calibrate.py g1` | `g1/calibration.json`, `validation/nm26-g1-calibration.jpg` (starting points `g1/calibration-inputs.json`) |
| 3. Track | `scripts/nm26-track.py g1` | `g1/puck-track.json` |
| 4. Flights and passes | `scripts/nm26-passes.py g1` | `g1/passes.json` |
| 5. Review page | `scripts/nm26-review-page.py g1` | `validation/nm26-g1-review.html`, published with a `db` for the verdicts |

**Run:** `npm run nm26:g1` (games 2-7 and the cross-game patterns: `npm run nm26:all`, see `docs/nm26-game-patterns.md`). It needs the video at `out/dl/nm26.webm` (download from the release URL in
`config.json`) and PyAV in the Blender venv. About 14 minutes on 4 CPUs, mostly step 1.

## Results for game 1 (video 20-545 s)

- **Registration:** all 15,750 frames registered to the reference frame (180 s), with no fallbacks.
- **Calibration:** the repo's slot centrelines fit the image slots with a median of 0.86 px; 71% of slot samples
  are within 2 px.
  - The misses are slot parts hidden by figures in the background image.
  - Scale: about 0.6 mm/px along the rink and 1.4-1.7 mm/px across it.
- **Puck track:** a position in 73% of frames:
  - 7,404 as a disk (at rest or slow);
  - 2,977 as a smudge in a fast straight run;
  - 1,161 added by flight filling.
  - 3,322 smudges were dropped because they did not form a straight fast run (figure blur).
- **Candidates:** 67 passes, 64 turnovers, 13 shots, 77 battles, 592 carries.
  - The review page shows the 136 that are passes, turnovers, shots or loose pucks at least 100 mm long.
  - 193 events have an uncertain end, where two figures could reach the point.

## How each step works

**1. Detection:**
- **Registration:** ORB at half resolution on the rink and housing, RANSAC homography to the reference frame.
- **Background:** the median of registered frames every 3 s.
- **Disk:** dark, neutral, puck-sized, and darker than the background by 60 or more.
- **Smudge:** grey, darker than the ice by 22 or more, changed since the previous frame, inside the ice polygon.

**2. Calibration:**
- Start from ten line-board points, then ICP of every skater slot centreline onto the dark slot pixels (radius 40 →
  5 px, RANSAC 3 px each round).
- The line points fix which end is goal.W (the video's left in game 1).

**3. Tracking:**
- Viterbi over the candidates, with a score per candidate (size against the projected puck, darkness, neutral
  colour, a penalty at static dark spots).
- A disk partly over the dark centre logo is judged by darkness and width only.
- Smudges are kept only in straight fast runs of 3 or more (18 mm tolerance, at least 250 mm/s).
- Flight filling: between two kept positions far apart, candidates that fit a constant-velocity path (straight or
  with one board bounce) are added.

**4. Flights:**
- Fast runs (at least 300 mm/s over two steps) are cut into straight segments (15 mm).
- Runs separated by one or two slow steps are joined when the direction continues.
- A corner at the boards is a bounce. A corner of more than 30° away from the boards is a figure touch and splits
  the flight.
- Release and reception are the slow detections just before and after the flight, when they lie on its line.
- The passer and receiver are the figures whose slot is nearest to the end point, within reach.

**5. Classification:**
- shot: attacking team, at least 150 mm, heading into the opponent's goal mouth, ending within 150 mm of the goal line;
- pass: same team;
- battle: other team and shorter than 150 mm;
- turnover: other team, longer;
- carry: same figure or shorter than 60 mm.

## Known limits (first version)

- **Coverage of long moves:** 30 of the 52 fast moves of more than 250 px found in the investigation come out as one
  event. Others are split, at real or noise corners, into two events. The review page shows each piece.
- **Shots:** only 13 shots in a game with 7 goals. Shots that end hidden in the goal or behind the goalie stop before
  the goal line and are often classified as turnovers or loose pucks. The user fixes them on the page.
- **Who:** the passer and receiver come from reach areas, not tracked figures. Contested ends are flagged.
- **Dead time:** stoppages are not removed yet. The first candidate (21.5 s) is before the opening signal.
- **Position bias:** the puck top is about 12 mm above the ice. Its blob centre projects a few mm away from the camera
  (+y); not corrected.

## Review page

`validation/nm26-g1-review.html`, published as a private artifact with a `db` capability.
- Each candidate shows three registered frames (release with the line, middle, reception), a mini board, and the
  buttons Correct, Not a pass and Fix (kind, from, to).
- A form adds missed passes: the video time, the players, and two clicks on the board. Claude snaps them to the track.
- Verdicts are stored in `reviews` and missed passes in `missed`. Claude reads both back with `ArtifactData` to
  produce the confirmed pass map.

## Claude's review (2026-10-08)

The user asked Claude to review all 136 candidates with a confidence from 0 to 100, including the 10 they had marked
("I did not do it properly"). The result is `data/games/nm26-semifinal/g1/review-claude.json` (**proposed**). The
review page shows it on every card and opens on the cards below 50, least sure first.

**Method.** For each candidate, one image row:
- puck-centred crops 0.3 s before the release, at the release and at the reception, with the claimed figure's slot drawn;
- a crop 0.4 s after the reception;
- a darkest-pixel composite of the whole flight with the measured line.

Claude judged:
- whether the puck really moves along the line;
- which kit is at each end (white/blue = Nygård, yellow = Fjermestad);
- hands in the rink, split moves and tracking jumps.

Reach lists (every slot within 75 mm of an end) name the figure when the kit at the puck disagrees with the nearest slot.

**Result:**

| Verdict | Count |
| --- | --- |
| ok | 74 |
| fix | 15 |
| wrong | 24 |
| unsure | 23 |

Confidence: 33 below 40, 86 from 40 to 59, 17 at 60 or above.

**What goes wrong (to fix in the pipeline):**
- **Stoppages:** a hand in the rink at #76, #94, #112, #113, #126, #127, #134 and #135. The last two come after the
  overtime winner.
- **Tracking jumps:** out-and-back moves with few detections and impossible speeds: #9, #37/#38, #43/#44, #51, #68/#69
  and #80.
- **Split moves:** a "release" at a board bounce or mid-flight, e.g. #15, #23/#24 and #65/#66.
- **Who:**
  - A figure standing nearer the camera covers the puck without touching it, so kit-at-the-puck judgements are
    limited.
  - The nearest slot is sometimes the wrong team: #17, #66, #70 and #97 end at white '14' (W-RW) while E-LW's slot is
    nearer.
- **Shot or pass:** cross-ice plays past the far post into the corner (#18, #35, #90, #119) are toss-ups. The four
  centre shots by yellow '2' (#58, #84, #103, #124) end beside the W net, not in it.
