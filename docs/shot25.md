# Iteration 25 - the first reusable video: "#17 Shovel"

Status: exported on 2026-10-05 and AI-reviewed. The final video is `validation/25-shovel-17-final.mp4`. It is the
iteration-24 presentation of the accepted trace, rendered directly with Remotion/Three. No new shot, no simulator,
no change to the trace, geometry or presentation.

## Rerender (one command)

```sh
npm run video:shovel-17
```

What this runs:
- `npm run remotion:assets`: copies the scene GLB to `public/` and rewrites the asset manifest.
- `node scripts/shot25-export.ts`: bundles, renders the draft and then the final, checks every frame and writes
  `validation/25-export-report.json`.
- `scripts/shot25-review.py`: writes the review sheet `validation/25-final-review.png`.

Inputs it needs (all committed):
- **Trace:** `data/traces/shovel-17.trace.json`.
- **Presentation:** `data/presentations/shovel-17.presentation.json`.
- **Geometry:** `data/geometry.json`.
- **Scene:** `assets/scene/full_static_appearance.glb`.
- **Contact checks:** `shots/22-shovel/checks.json`.
- **Environment:** `npm ci` with the lockfile, and the chrome-headless-shell at
  `/opt/pw-browsers/chromium_headless_shell-1194` (the cloud container's browser; elsewhere, pass another
  `chrome-headless-shell` in `BROWSER` at the top of the script).

Partial runs:
- `node scripts/shot25-export.ts --draft`: draft only, written to `out/25/`, not committed.
- `node scripts/shot25-export.ts --final`: final only.

To change the shot, change the trace (iteration 22 tooling) or the presentation JSON and rerun. The tests then
flag the old export: the report records the trace and presentation SHA-256.

## Route and versions

| Item | Value |
| --- | --- |
| Renderer route | Remotion/Three, composition rendered directly. `docs/review.md`: the Cycles benchmark was specified but never run, so there is no switch and no offline handoff. |
| Composition | `shot25-shovel-17-final` (`remotion/ShotPresentation.tsx`, registered in `remotion/Root.tsx`) |
| Remotion, @remotion/three, @remotion/renderer | 4.0.531 |
| three / @react-three/fiber / react | 0.186.1 / 9.4.0 / 19.2.0 |
| Node | 22.22.2 |
| Browser / GL | chrome-headless-shell (Chromium 141.0.7390.37), `--gl=swangle` (SwiftShader, CPU) |
| Geometry | `0.6.0` |
| Trace | `trace.shovel-17.v2` (accepted 2026-10-04, revised 2026-10-05; one approved overlap exception) |
| Presentation | `presentation.shovel-17.v1` (iteration 24; camera `oblique`) |
| Exact hashes | `validation/25-export-report.json` (trace, presentation, scene GLB, figure assets, output files) |

## Output settings (presentation choice)

No settings had been agreed, so the iteration prompt's proposal was used: **1920 × 1080, 60 fps**, H.264, CRF 18,
yuv420p, 446 frames (7.43 s).

- This is a presentation choice, not extra geometry precision: the model is self-consistent to about 1-2 output
  pixels, and its absolute accuracy is limited by the unmeasured inputs (`docs/review.md`).
- **60 fps:** the approved 30 fps timeline is laid out at two output frames per presentation frame
  (`resolveTimeline(spec, trace, 60)`). Every source time of the 30 fps version appears bit for bit at the matching
  even frame (test). The odd frames add in-between source times of the same trace, not new mechanics.
- **Length:** the pause and the hold lengths stay the same in seconds.

## Checks run (`validation/25-export-report.json`)

| Step | Result |
| --- | --- |
| Draft: 480 × 270, 60 fps, all 446 frames, CRF 23 (`out/25/`, not committed) | every frame's logged state equals the pure evaluation; 2973 s with 3 parallel renders |
| Draft review (`out/25/draft-review.png`) | whole playback in order (opening hold, normal pass, hold, replay, 2 s pause with the explanation, replay into the net); every contact event visible in the normal pass and the replay |
| Final: 1920 × 1080, 60 fps, 446 frames, CRF 18 | every frame's logged state equals the pure evaluation; scene read-back within 3e-14; 2946 s with 2 parallel renders; 0.97 MB |
| Final review (`validation/25-final-review.png`) | the whole playback (every 12th frame) and the 8 contact-event frames (normal pass and replay) checked: title, speed labels, pause explanation and puck ring present and legible; the contact visible; nothing clipped |
| `npm run check` | typecheck, validate, all tests pass (including `tests/shot25.test.ts`: 30 fps ↔ 60 fps bit-identical source times, the registered settings, and the report matching the committed trace, presentation, scene and video) |

## Observed limitations

- **Look.** The CPU renderer gives no shadows, opaque white end screens and a flat ice look. This is not
  photorealistic yet; the renderer decision (Cycles benchmark) is still open.
- **Render time.** About 6.7 s per draft frame (3 parallel renders oversubscribe the 4 CPUs) and about 6.6 s per final frame on the 4-CPU container,
  because SwiftShader renders on the CPU. A GPU WebGL would be much faster.
- **Inherited from the trace v2:**
  - the far-corner shot direction is assumed, with the approved 2.65 mm skate-brush exception;
  - the drag-back between observations is reconstructed;
  - contact sizes are preview values;
  - the seven figures not in the trace stand in the static assembly pose.
- **Captions** are AI wording ("centre", "right wing"); they were not changed at review.
- **Review sheet fix.** The first version of the review sheet drew its frame labels over the top of each frame and
  hid the title and speed captions. Labels now sit above the frames; the captions are in the video.

## Git

The final MP4 (0.97 MB) and the review sheet are committed as the iteration's deliverable. Draft video, frame
sequences, Remotion bundles and caches stay out of git (`out/` and `.cache/` are ignored; Remotion bundles to a temp
directory).

## Next

This is the last numbered iteration in `Claude_Code_Stiga_Iteration_Prompts.md`. Open items for the user:
- the renderer decision (the bounded Cycles benchmark in `docs/review.md`), if photorealism is wanted;
- measurements of the real figures (skate and fixture), which would remove the approved exception and the preview
  values;
- the next shot.
