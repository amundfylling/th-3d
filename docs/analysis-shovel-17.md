# Analysis video: "#17 The Shovel"

Status: rendered and AI-reviewed on 2026-10-05 (user request after iteration 25; not a numbered iteration).

The video is a VAR-style sports-analysis breakdown of the accepted trace `trace.shovel-17.v2`. It uses the same
scene, models, trace and contact sequence as iterations 23-25, and it changes none of them.

| Item | Value |
| --- | --- |
| Video | `validation/analysis-shovel-17.mp4` |
| Format | 1920 × 1080 (16:9), 30 fps, H.264 CRF 20, yuv420p, 748 frames (24.93 s) |
| Size | 12,144,395 bytes (12.14 MB), measured from the file; limit 25 MB, checked by the render script |
| Composition | `analysis-shovel-17` (`remotion/ShotAnalysis.tsx`, registered in `remotion/Root.tsx`) |
| Data | `data/presentations/shovel-17.analysis.json` (shot timeline, camera views and keys, chapters, graphics) |
| Model code | `src/model/analysis.ts` (spec resolution, badges, frame evaluation), `src/model/camera-track.ts` (camera), `src/model/presentation.ts` (timeline; `rewind` segments added) |
| Review sheet | `validation/analysis-shovel-17-review.png` |
| Report | `validation/analysis-shovel-17-report.json` (versions, hashes, ffprobe, per-frame checks) |

## Reproduce

```sh
npm run video:analysis-shovel-17
```

This copies the scene GLB to `public/`, renders and checks the video (`scripts/analysis-render.ts`, about 66 min on
the 4-CPU container with SwiftShader) and writes the review sheet (`scripts/analysis-review.py`). Single frames for
tuning: `node scripts/analysis-stills.ts 0.5 <frame> ...` → `out/analysis/`. The other compositions (`shot23-*`,
`shot24-shovel-17`, `shot25-shovel-17-final`, `static-*`) are unchanged and still registered.

## Structure

Three independent tracks, each a pure function of the frame number:

1. **Shot timeline** (`segments`): which source time of the trace each frame shows. Segment kinds are `play` (any
   rate), `hold` (freeze: the entire physical scene stays at one source time) and `rewind` (plays backwards).
2. **Camera track** (`views`, `camera`): named views and keys. Between two keys with the same view the camera stands
   still. Between different views it moves with smootherstep easing, in a cylindrical blend around the moving target,
   with an optional sine-shaped lift that keeps the camera high over the figures. All camera moves happen during
   freezes. The camera is stationary during every slow-motion segment, every explanation and the replay.
3. **Graphics** (`chapters`, `graphics`): chapter lower thirds and graphics anchored to objects. Anchored graphics are
   projected with the same camera parameters as the canvas: player highlight rings, the pass arrow, the contact
   marker, the slot arrow and the puck trail. They read the evaluated state and never feed back into it.

No `useFrame`, no clock, no state carried between frames (tested). Every frame's figure poses and puck position equal
the pure Node evaluation of the trace, and every frame's canvas camera equals the pure camera track (both checked by
the render script on the full render).

## Story (30 fps presentation frames)

| Time | Segments | Shot | Camera | Graphics |
| --- | --- | --- | --- | --- |
| 0.0-1.7 s | `intro` | freeze at 0.50 s | high wide view, eases down to the broadcast view | title card |
| 1.7-4.1 s | `full`, `goal_hold` | 0.50 → 2.17 s at full speed | broadcast (still) | FULL SPEED; GOAL |
| 4.1-5.2 s | `rewind`, `pass_set` | 2.17 → 1.55 s backwards, freeze | moves to the right winger | REWIND |
| 5.2-9.0 s | `pass_in`, `pass_freeze` | ×0.2 to the backhand release (1.772 s), freeze | still | chapter 1; winger highlight; pass arrow; puck trail |
| 9.0-10.2 s | `to_reception` | freeze at the release | arcs over to the centre's back | |
| 10.2-13.9 s | `reception_in`, `reception_freeze` | ×0.1 to the reception contact (1.8343 s), freeze | still | chapter 2; centre highlight; contact marker at the skates |
| 13.9-16.0 s | `to_shovel`, `shovel_read` | freeze at the contact | rises to a high view from the centre's back side | chapter 3; slot arrow |
| 16.0-19.4 s | `carry`, `release_freeze`, `shot_out`, `goal_freeze` | ×0.05 contact → separation (1.8548 s), freeze, ×0.12 into the net, freeze | still | puck trail; GOAL |
| 19.4-23.1 s | `to_replay`, `replay` | 1.00 → 2.05 s at ×0.5 | pulls back to a three-quarter view, then still | REPLAY ×0.5; puck trail; summary card from 22.8 s |
| 23.1-24.9 s | `outro` | freeze | still | summary card |

## What the video claims (and does not)

The captions describe only the sequence in the accepted trace:
- the right winger turns and releases a backhand pass;
- the centre receives at his skates with his back to the pass;
- he moves up his slot with the puck on his back, and it slides into the far corner.

The video adds no forces, spin or hidden movements. Inherited assumptions (from `docs/shot22.md` and
`docs/shot25.md`), unchanged here:
- the far-corner shot direction is assumed;
- the approved 2.65 mm skate-brush exception;
- the reconstructed drag-back between observations;
- preview contact sizes;
- seven figures standing in their static assembly pose.

The highlight rings, arrows and the trail are presentation graphics, not measured quantities. The pass arrow points
along the puck velocity just after the release (from the trace). The contact marker is the reception contact point
recorded on the trace event. The slot arrow follows the W-C fixture centreline.

## Review

- **Stills.** Rendered at half size during tuning (frames across every segment) and reviewed. Fixed after review:
  - the reception view was hidden by E-LD (#5);
  - the contact label overlapped the puck;
  - the GOAL banner covered the goal;
  - the action sat at the frame edge in the broadcast, shovel and replay views;
  - the title was unreadable on the ice;
  - the white puck trail was invisible on the ice (now amber with a dark edge);
  - the winger tag sat over the puck;
  - two captions were too long for their stationary reading time.
- **Occlusion during the carry (found in the first complete render).** From the first shovel view (low, from the
  −y side), E-LD (#5) stood between the camera and the centre during the carry and hid the centre and part of the
  puck. The shovel view is now chosen by a line-of-sight search. Every figure is a 25 mm × 56 mm cylinder (goalie
  32 mm), with the traced figures at their trace poses and the others at their scene positions. The search covers
  the reception contact to 20 ms after the separation. The new high view from the centre's back side clears every
  figure by about 50 mm. A test checks the sight lines to the puck and the centre on every frame of `shovel_read`,
  `carry` and `release_freeze`; it fails on the old view (E-LD hides the puck).
- **Timing after the review.** The longer swing to the replay view needed more time (camera step < 60 mm/frame).
  The summary card was too short to read (0.9 s); it now fades in 0.3 s before the replay ends and stays for
  about 2.1 s. The intro, the pass freeze, the goal hold and the replay rate (×0.45 → ×0.5) give back the time; the
  total stays under 25 s.
- **Captions.** Each chapter caption is fully shown for at least 3.5 s with a still camera, at no more than
  4 words per second (tested).
- **Camera.** The camera never goes below 130 mm above the ice; the tallest object in the scene is the 70 mm end
  screen. Its largest frame-to-frame step is under 60 mm (tested), so it never cuts or clips.
- **Render memory.** The first full render died at frame 94: the container's 14 GB memory limit killed ffmpeg.
  The composition passed a new `THREE.PerspectiveCamera` to `ThreeCanvas` on every frame, and memory grew by about
  140 MB per 1080p frame. With one canvas camera per tab, memory stayed flat at about 2.1 GB over a 50-frame probe.
  A test guards it.
- **Final video.** Reviewed from the review sheet (every 15th frame plus the middle frame of every segment):
  - title, chapters, badges and the summary card are legible;
  - the puck and the contacts are visible in the pass, reception, carry, release and goal freezes;
  - no label overlaps the puck or another label;
  - no clipping.
- **Render checks** (`validation/analysis-shovel-17-report.json`):
  - 748/748 frames logged, and every frame's state equals the pure evaluation;
  - the camera is within 0.005 mm of the camera track;
  - ffprobe reports h264, 1920 × 1080, 30/1, 748 frames, 24.93 s;
  - render time 3962 s with 2 parallel tabs.
- `npm run check`: typecheck, validate and 124/124 tests pass.

## Limitations

- The look is the CPU WebGL renderer's: no shadows and flat ice. This is not photorealistic; the renderer decision
  (Cycles benchmark in `docs/review.md`) is still open.
- The wording ("centre", "right winger", "slot") is AI wording, for non-players.
