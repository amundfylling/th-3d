# Iteration 21 - observations from one real shot ("#17 Shovel")

Status: observed by the AI on 2026-10-04. Not reviewed by the user. No motion fitted, no puck simulated, no
animation.

## Inputs

- **Recording**: `references/shots/shovel-17-screen-recording.mov` (SHA-256 `65eca3cd...7886`, 20.1 MB),
  uploaded by the user, who stated that it shows one combination, first at full speed and then as a replay of the
  same shot. It is an iOS screen recording (ReplayKit) of a third-party video titled "#17 SHOVEL, difficulty
  4/10" with a "Brent Plast Bordhockey" watermark.
  - Frames: 2556 x 1180 after the display rotation, HEVC, 424 frames, 7.04 s.
  - Recording cadence: ~60 fps container (recording intervals 15-16.7 ms).
- **Model-review feedback**: the user asked to proceed with iteration 21 after the round-13 figure work. The
  model's review status is unchanged: AI review only, no user approval of the model recorded.

## Timing (measured)

| Part | Recording frames | Recording time | Content |
| --- | --- | --- | --- |
| Title card | 0-26 | 0.00-0.43 s | static title over the first shot frame |
| Segment 1 | 27-185 | 0.45-3.08 s | full-speed shot, camera behind the W attack looking at goal.E (calibrated) |
| Segment 2 | 186-423 | 3.10-7.04 s | slow-motion replay from behind goal.E (not calibrated) |

- **Content rate**: the screen recording repeats frames, and content changes every 2 or 3 recording frames, so
  segment-1 content runs at **24.9 fps (40 ms per frame)**. The container rate is not the source camera rate; the
  source camera's own capture rate and exposure are unknown.
- **Real time**: segment 1 is treated as real time on the user's statement ("full speed"). Shot time is measured
  from the first frame of segment 1, +/- 17 ms (one recording interval).
- **Replay**: segment 2 is slower by an undetermined factor (roughly 3-10x) and is not mapped to segment 1.
  **Update (user, 2026-10-04):** the replay may not be the same take as segment 1 (only one camera was used), so its
  marks are not evidence for the segment-1 shot. The goal side (far corner, +y) is confirmed by the user.

## Camera (segment 1)

- **Method**: planar homography from the ice plane (world mm, `data/geometry.json`) to the recording frame. It is
  fitted to nine points:
  - the E goal, E blue and centre lines where they meet the -y board;
  - three red faceoff dots, measured as centroids in the reference overhead and mapped by `map.overhead.preview`;
  - three slot ends (E-RD and E-LD far ends, W-C near end).
- **Fit**: RMS 6.1 px, leave-one-out RMS 13.5 px (max 24 px). Local scale is 2.4-5.9 px/mm, so the error is about
  2-5 mm on the ice.
- **Scale checks** (consistent, not measurements): the sharp puck maps to a 26-27 mm horizontal chord against the
  ~25.4 mm catalog diameter; the E.neg_y circle maps to ~105 mm against ~97-100 mm in the reference overhead.
- **Corrections during the iteration**: a first fit had an RMS of 25 px because I mistyped one slot-end mark by
  100 px. The calibration overlay exposed it, and the mark was corrected. A second point (an assumed W-LW slot
  start) was in fact the W-LD slot end and was rejected; see `marks.json`.
- **Caveat**: the recorded table is a different STIGA edition (other sponsor artwork) and not the user's own
  table. Using the canonical slot layout for it is an assumption, supported by the residuals and by the projected
  slots overlaying the visible ones (`validation/21-camera-calibration.png`).

## ID mapping

Mapped by slot topology on the calibration overlay:
- **W-C** (white, centre slot): the receiver and shooter.
- **W-RW** (white no. 64, curved -y winger slot): the passer.
- **Static**: E-G (yellow goalie), E-LD and E-RD (yellow no. 2).
- White attacks goal.E (+x).
- The reference pack prints 64 on W-C; here 64 is on W-RW, so the recorded pack differs.

## Observations (`shots/21-shovel/observations.json`)

Shot times are segment-1 seconds. Slot positions are arc lengths along the canonical visible slot centreline.

| Event | Time (s) | Evidence |
| --- | --- | --- |
| Preparation 1: W-RW drags the puck from the -y corner (arc ~328 mm) to centre ice and back; W-C feints along its slot | 0.05-0.68 | puck sharp at the W-RW blade at 0.05 and 0.68 s |
| Preparation 2: second drag toward centre ice; W-C goes to the near end of its slot (arc 0) | 0.68-1.25 | |
| Pass release from W-RW (rotating), toward W-C | 1.25-1.33 | puck hidden at 1.28 s, a 236-px streak in flight at 1.33 s |
| Reception at the W-C blade (interval, exact contact not observed) | 1.33-1.40 | smear at the blade at 1.37 s; replay 256-263 |
| Carry: W-C travels up its slot with the puck at the blade (arc 0 -> 248 mm in ~0.15 s) | 1.37-1.48 | W-C marks; replay 265-280 |
| Goal entry into goal.E, goalie's right (+y) side (corrected in iteration 22; iteration 21 said left); hidden in segment 1 | 1.40-1.53 | replay 280-289 (smear into the net, then puck inside) |
| W-C returns down its slot | 1.48-1.73 | |

- **Smallest useful segment**: 1.25-1.73 s (pass, reception, carry, goal). Full combination: 0.05-1.73 s.
- **Puck positions** are blob centres (parallax bias up to half a puck thickness); occluded samples are recorded as
  not visible.
- **Not measured**: figure rotation (blur, unknown blade offset).

## Limitations

- Different table edition and figure pack from the user's; world positions assume the canonical layout.
- No exact contact time or point: release, reception and goal entry are intervals of one or more 40 ms content
  frames, and the source camera blurs the motion heavily.
- Goal entry is seen only in the uncalibrated slow-motion replay.
- Fixture points snap the skate row to the slot centreline; the true fixture axis offset is unknown.

## Reproduce

`npm run shot:21` (= `/root/venvs/blender/bin/python scripts/shot21-observe.py`) regenerates
`shots/21-shovel/observations.json`, `validation/21-contact-sheet.png` and `validation/21-camera-calibration.png`
from the pinned recording and `shots/21-shovel/marks.json`.
