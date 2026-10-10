# Iteration 24 - one slow replay and minimal teaching overlays

Status: done on 2026-10-05 and AI-reviewed. This is presentation only, around the accepted trace
`trace.shovel-17.v2`. The trace and the geometry are unchanged: no puck velocity, contact or event was added or
edited.

## What was built

| Path | What |
| --- | --- |
| `data/presentations/shovel-17.presentation.json` | The presentation as data: segments (an explicit presentation-time → source-time mapping), captions and one marker. It refers to trace events by id, never by copied numbers. |
| `src/model/presentation.ts` | Pure mapping. `resolveTimeline(spec, trace)` resolves the segments; `sourceAtFrame(timeline, frame)` gives the source time and segment for a frame. It rejects any source time outside the trace window, any backwards play, and a spec made for a different trace. |
| `src/model/shot-pose.ts` | `shotTimeEvaluator`: the physical state at a source time. The iteration-23 frame evaluator now calls it, so the same function serves both shots. |
| `remotion/ShotScene.tsx` | The shared scene: applies a state to the GLB nodes, reads it back and logs it. Moved out of `ShotPlayback.tsx`; iteration 23 is unchanged in behaviour (its tests and renders still pass). |
| `remotion/ShotPresentation.tsx` | Composition `shot24-shovel-17`: 223 frames at 30 fps (7.4 s), 1920 × 1080, oblique benchmark camera, plain background. Prop `overlays` (false = mechanics only, for pixel comparisons). |
| `scripts/shot24-render.ts`, `scripts/shot24-sheet.py` | Renders and checks (`npm run shot:24`, about 20 min on the CPU). |
| `tests/shot24.test.ts` | Six tests: the mapping, the window bounds, the pause at the contact, normal = replay at the same source time, caption and marker rules, and no clock, blur or depth of field. |

## Timeline (presentation frames at 30 fps → source time)

| Segment | Frames | Source time | Rate | Shown |
| --- | --- | --- | --- | --- |
| intro | 0-30 | 0.500 (held) | pause | title "#17 Shovel", "Normal speed" |
| normal | 30-80 | 0.500 → 2.167 | 1× | the whole shot once at real speed |
| normal_end | 80-95 | 2.167 (held) | pause | - |
| replay_in | 95-123.1 | 1.600 → 1.8343 | 1/4× | "Replay - 1/4 speed", ring on the puck |
| contact_pause | 123.1-183.1 | **1.8343** (held: `contact.W-C_reception`) | pause, 2 s | "Paused at the key contact" plus the explanation, ring |
| replay_out | 183.1-203 | 1.8343 → 2.000 | 1/4× | ring until the puck reaches the net |
| replay_end | 203-223 | 2.000 (held) | pause | - |

How the mapping works:
- **Play:** source time = window start + (u0 + (frame − f0) × rate) / 30, with u0 the start in source frames.
- **Replay frames match normal frames.** The replay starts on source frame 33, so replay frame 95 + 4m shows
  exactly (bit for bit) the source time of normal frame 63 + m.
- **Pause:** the pause holds the trace's own reception time. No new event is invented.

## Presentation choices (not mechanics)

- **Camera.** The oblique benchmark camera from iterations 16-20 (`remotion/cameras.ts`, the view named for the
  renderer benchmark). It shows the whole rink, so no figure leaves the frame (the tight overhead camera of
  iteration 23 lost W-RW at the far board end). The reception contact is not hidden by any figure from this angle.
- **Overlays** are a separate layer that only reads the state; they never change it:
  - a short title, "#17 Shovel";
  - a speed label;
  - the key-contact explanation, shown only during the pause: "Key contact: the pass from the right wing lands on
    the back of the centre. He carries it up his slot and it slides off into the far corner.";
  - one restrained marker: a thin yellow ring around the puck, projected with the scene camera, during the replay
    around the contact.
- **No blur or depth of field.** The pipeline uses neither, and a test forbids them in the composition.
- **Frame rate.** 30 fps and the 1/4 replay speed are presentation choices.

## Checks run (`validation/24-render-checks.json`)

| Check | Result |
| --- | --- |
| Normal vs replay at the same source time: 4 pairs (normal frames 64, 66, 68, 70 vs replay frames 99, 107, 115, 123; t = 1.633-1.833 s), rendered with the overlays off | identical logged state, **identical PNG bytes**, equal to the pure Node evaluation |
| Contact pause: frames 124, 153, 183 | all at t = 1.8343 s (the trace event), identical state and PNG bytes |
| Draft clip: all 223 frames, `renderMedia`, concurrency 2 | all 223 frames logged; every frame equals the pure evaluation; scene read-back within 3e-14; 1530 s on the CPU |
| `npm run check` | typecheck, validate, all tests pass |

**Main artifact:** `validation/24-comparison.png`. It shows a normal frame and the replay frame at the same source
time, the contact pause with its explanation, and a replay frame after the contact. The draft video is
`validation/24-draft.mp4` (960 × 540).

## Limitations

- **Renderer.** The CPU renderer (SwiftShader) gives no shadows, opaque end screens and a flat look; the
  photorealism decision (`docs/review.md`) is still open.
- **Inherited from the trace v2.** The shot direction is assumed (far corner), with the approved 2.65 mm skate brush.
  The puck between the observations in the drag-back is reconstructed. Contact sizes are preview values.
- **Seven figures** not in the trace stand in the static assembly pose.
- **Caption wording** is the AI's. The user may want other names (W-C/W-RW are shown as "centre" and "right wing").

## Next

Iteration 25 (export and document the first reusable video) after the user reviews this presentation: the camera
choice, the replay speed, the pause length and the wording.
- Iteration-23 check after the scene refactor: `shot23-shovel-17` frame 40 re-rendered and viewed (same pose and framing as before).
