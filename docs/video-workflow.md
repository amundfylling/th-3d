# Video workflow: describe a combination, review it, export it

Status: PROPOSED (2026-10-12, branch `claude/combo-video-workflow-j0piia`, not merged). One command (`scripts/video.ts`)
previews and exports every analysis video on the shared renderer (`remotion/AnalysisVideo.tsx`): the five hand-made ones
(Shovel, spjass, IKV, Näcka, defence) and every shot-encyclopedia move. Presentation changes (text, pauses, slow-motion
rates, camera offsets, theme) are regenerated from a valid trace without rerunning the simulation, and a pilot scene cache
re-renders only the 3D scene states that changed.

Nothing here changes a trace, a check, the rink or the figures. The figure model belongs to the "Better figure models"
work; the scene cache keys on it, so a model change simply starts a new cache namespace.

## 1. Commands

```sh
npm run remotion:assets                                  # once per checkout (copies the scene GLB to public/)
npm run video:list                                       # every target and its composition

# review
npm run video:stills -- move:hjerpefinte                 # automatic review stills + contact sheet (scale 0.5)
npm run video:stills -- ikv --frames 35,223,401          # chosen frames
npm run video:draft  -- move:hjerpefinte --segment shot_in,shot_freeze   # low-res clip of named segments
npm run video:draft  -- move:hjerpefinte --frames 250-420 --scale 0.25

# export
npm run video:final  -- move:hjerpefinte --cache         # 1920x1080, every check, report next to the mp4
npm run video:final  -- ikv nacka                        # several targets: one bundle, one browser
node scripts/analysis-render.ts move:hjerpefinte         # old command, now a wrapper (direct renderer)

# presentation only (moves)
python3 scripts/build-move.py hjerpefinte --check        # is the saved motion still valid? (JSON, exit 1 if not)
python3 scripts/build-move.py hjerpefinte --presentation # story.json -> data/presentations/<id>.analysis.json
```

Targets: `shovel-17`, `spjass`, `ikv`, `defence-lw`, `nacka`, and `move:<id>` (or the composition name) for each move with
a generated video. Options (all commands):

| option | meaning |
|---|---|
| `--frames 100-160,200` | output frames, inclusive ranges |
| `--segment shot_in,shot_freeze` | named presentation segments (exactly the frames f with f0 <= f < f1; adjacent ones merge into one clip) |
| `--scale 0.5` | resolution factor (stills and draft default 0.5, final 1) |
| `--cache` | scene layer from the scene cache (section 4); default is the direct WebGL renderer |
| `--browser <path>`, `--gl <backend>` | section 3 |
| `--concurrency n` | browser tabs rendering in parallel. Default: 1 for WebGL on a software renderer (it already uses every core), 2 on a GPU, one per core (at most 8) for cached composites (section 8) |
| `--plain-render` | draw the scene with the plain single three.js call, the reference of the faster scene renderer (section 8); its cached images get their own namespace |
| `--out <dir>` | output directory for stills, draft and partial finals |
| `--report <file>`, `--cold` | timings as JSON; `--cold` deletes the bundler cache first (benchmarks) |

Outputs: stills in `out/review/<target>/` (`fNNNN.png`, `index.json` with every still's reasons, `contact-sheet.jpg`);
drafts in `out/video/<target>-draft[-<from>-<to>].mp4`; a full final at scale 1 replaces the committed export
(`validation/...mp4`) and its report; a partial final goes to `out/video/` and replaces nothing.

What each mode keeps:
- **Draft**: the same frame indices, fps, camera track and timing as the final; only the resolution (and the overlay
  pixels, which scale with it) differ. The renderer's per-frame state and camera checks still run.
- **Final**: everything the committed exports had: trace gate, per-frame state = pure evaluation, camera = camera track,
  ffprobe frame accounting, size, report fingerprints.
- Every render command first runs the gates: the trace's asset compatibility and checks, and for moves
  `build-move.py --check` (section 2). A failing gate stops the command; nothing renders stale or failed motion.

Review stills are picked from the trace events and the presentation (`scripts/video/plan.ts`): the title card, the
set-up freeze, every contact just before / at / just after it in the slowest play segment that shows it, every labelled
explanation freeze once its camera has arrived, the middle of every camera move, the goal at full speed and the end card.
Frames closer than 3 apart merge, keeping all reasons.

## 2. A new combination without new TSX

1. `moves/<id>/move.json`: the motion (figures, puck start, contacts, expectations). See docs/shot-encyclopedia.md.
2. `moves/<id>/story.json` (`move-story/1`): what the video says and shows. Copy `moves/hjerpefinte/story.json`.

   ```jsonc
   {"schema": "move-story/1", "move": "<id>", "theme": "classic",        // or "nbhf" (docs/theme.md)
    "title": "...", "subtitle": "...", "bug": "...", "end_steps": ["...", "..."],
    "setup": {"title": "THE SET-UP", "text": "...", "highlight": {"W-C": "CENTRE"}, "puck_label": "..."},
    "beats": [{"contact": "shot", "title": "THE SHOT", "text": "...", "label": "SHOT · BLADE PUSH",
               "freeze_frames": 96,                                       // optional, per beat
               "camera": {"offset_mm": [-150, -170, 230], "fov_deg": 30}}],  // optional, per beat
    "timing": {"beat_freeze_frames": 120, "replay_rate": 0.3},            // optional overrides
    "camera": {"replay": {"offset_mm": [-180, -330, 330], "fov_deg": 32}}} // optional, per view
   ```
   Timing keys (frames at 30 fps; rates in source seconds per presentation second): `intro_frames`,
   `goal_hold_frames`, `rewind_rate`, `setup_set_frames`, `setup_freeze_frames`, `to_beat_frames`, `approach_s`,
   `beat_freeze_frames`, `shot_out_min_rate`, `goal_freeze_frames`, `to_replay_frames`, `replay_rate`, `outro_frames`.
   Camera views: `intro_high`, `broadcast`, `setup`, `beat`, `replay`. Unknown keys are refused.
3. `python3 scripts/build-move.py <id> --robustness --video-spec` (motion + checks + presentation + registry entry).
4. `npm run video:stills -- move:<id>`, then `npm run video:draft -- move:<id> --segment ...`.
5. Text, pauses, rates, camera or theme to change: edit `story.json`, then `python3 scripts/build-move.py <id>
   --presentation` (about a second, no simulation), and back to 4. With `--cache`, only scene states whose camera or
   timing changed render again.
6. `npm run video:final -- move:<id> --cache`, then `npm test`.

Generated files stay generated: `data/presentations/<id>.analysis.json` (with `generated_from`: the story and trace
SHA-256 and the generator) and `remotion/encyclopedia-registry.ts` are written by `build-move.py`; edit `story.json`.

**The presentation gate** (`scripts/shotlib/identity.py`, run by `--presentation`, `--check` and every render of a move)
refuses when: the trace's motion fingerprint differs from `move.json` without its story (`motion_sha256`); the engine
code (`scripts/shotlib`, except presentation/robustness/identity) or its data inputs (geometry, hardware report, assembly
poses, contact footprints) changed since the build; the model files in the asset manifest changed; the checks did not
pass (overlaps, slide check, unexplained motion changes, expectations); or (for rendering) the story changed since the
presentation was generated. The story is not part of the motion fingerprint, so a caption edit never invalidates the
motion. The test `tests/video-workflow.test.ts` exercises each refusal on a copy of the repository.

## 3. Browser and GL

`scripts/video/render-env.ts` gives every render (the CLI, the old wrappers, `npm run remotion:stills` and the
shot23/24/25, IKV sketch, defence goalie and Edwall scripts) the same browser and `chromiumOptions.gl`:

- Browser, first match: `--browser <path>` or `REMOTION_BROWSER_EXECUTABLE`; Remotion's own chrome-headless-shell
  (`ensureBrowser`, downloaded once into `node_modules/.remotion`); a Playwright chrome-headless-shell found by search
  under `$PLAYWRIGHT_BROWSERS_PATH` or `~/.cache/ms-playwright`. No fixed path. In the cloud container the download is
  blocked (DNS / proxy 403), so the search finds `/opt/pw-browsers/chromium_headless_shell-1194` (Chromium 141.0.7390.37).
- GL: `--gl <backend>` or `REMOTION_GL`, default `swangle`. On a desktop with a GPU try `--gl angle` (macOS, Windows)
  or `--gl angle-egl` / `egl` / `vulkan` (Linux).
- What drew the frames is measured, not assumed: every run probes the page's WebGL renderer string (composition
  `gl-probe`) and every scene render logs `[gl-renderer]`; reports carry `render.gl_flag`, `render.probe_renderer` and
  `render.webgl_renderers`. A cache namespace includes the reported renderer.

Observed here (2026-10-12): `--gl swangle` → "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) ...), SwiftShader
driver)", i.e. CPU. `--gl angle` in this container also reports SwiftShader (no GPU). **Desktop GPU rendering is
supported by the options but has not been verified on a machine with a GPU.**

## 4. Scene cache (pilot)

Most output frames of an analysis video repeat a scene: a freeze holds the trace while text fades in. The Hjerpefinte
video has 631 frames but only 325 distinct (trace time, camera) pairs and 244 distinct scene states (a freeze with a
still camera is one state; a freeze with a moving camera is a new state per frame; identical poses at different times
are one state). The historical "631 / 325" counted (time, camera) pairs; 244 is the number of images the cache needs.

How it works (`scripts/video/scene-cache.ts`, `remotion/SceneLayer.tsx`):
1. For each selected output frame, the pure evaluators give the frame's scene state: every figure's pose matrix, the
   puck and the full camera (double precision). `stateKey` = SHA-256 of the namespace and that state.
2. Missing states are rendered once by the scene-only composition (`frameMap` → the representative frame, overlays off,
   lossless PNG). Each render's logged state and camera are compared with the pure evaluation; only a verified render
   becomes a cache entry (`out/scene-cache/<namespace>/<key>.png` + `.json` with its verification record).
3. The output is composed by the normal composition: the cached PNG as the scene layer (served from 127.0.0.1) and the
   live overlays drawn on top. Overlays are never cached.
4. The export report's `checks.scene_cache` lists, per frame, the key and whether it was rendered or reused, plus the
   verification record of the render it reuses. Reused frames do not get a WebGL readback of their own and none is
   claimed: `frames_logged` counts live scene renders, `scene_cache.checked` the frames checked against an entry.

The namespace (anything that changes pixels without changing the state) is: `SceneLayer.tsx`, `ShotScene.tsx`,
`scene-render.ts`, `cameras.ts`, `coordinates.ts`, `asset-manifest.json`, the served scene GLB, `geometry.json`, the three / r3f /
remotion / react versions, the browser version, the `--gl` flag and the reported WebGL renderer, width, height, scale,
PNG, the theme background and the scene draw mode (`reuse` or `plain`, section 8). Overlay text, graphics and chapter timing are not in it.

Kept as the reference and fallback: without `--cache` every frame renders the scene live, exactly as before.

## 5. Scene isolation fix (ShotScene)

`useLoader` caches one GLTF per URL for the whole page, and `ShotScene` moved the figure nodes of that shared scene in
place. A composition rendered after another in the same tab started from the previous one's poses for any figure its
own trace did not move (the static figures). Fixed: each mount clones the scene graph once (`gltf.scene.clone(true)`:
own transforms, shared geometry and materials), records the rest transform of the 12 figures and the puck, and resets
them before applying every frame's state. No per-frame clone.

Verified with `node scripts/video.ts probe-scenes shovel-17 ikv nacka move:hjerpefinte`: each composition's scene alone,
then all in one tab in two orders. Before the fix (`validation/video-workflow/scene-probe-before-fix.json`) Hjerpefinte,
IKV and Näcka differed from their alone render in at least one order; after it
(`validation/video-workflow/scene-probe-fixed.json`) all are byte-identical, and the alone renders are byte-identical to
the old code's.

## 6. Benchmarks (measured 2026-10-12)

Cloud container, 4 cores, no GPU; Chromium 141.0.7390.37 headless shell; `--gl=swangle`, WebGL renderer reported
SwiftShader (CPU); concurrency 2. Every row is one measured run (`validation/video-workflow/benchmarks.json`); nothing is
extrapolated. Pilot: Hjerpefinte (631 frames, 244 distinct scene states). Regression case: IKV (892 frames, four
contacts).

| workload | before (main) | now | notes |
|---|---|---|---|
| preparation: bundle | every script bundles per target | 12.6 s cold (`--cold`), 2.1-2.6 s warm | one bundle and one browser per invocation, any number of targets |
| review stills, Hjerpefinte | frames picked by hand | 16 automatic stills: 98.4 s cold / 86.3 s warm (scale 0.5, direct); 89.5 s at 1080p direct; **9.8 s** at 1080p from a warm cache | contact sheet and reasons in `index.json` |
| draft clip, Hjerpefinte `shot_in,shot_freeze` (156 frames, scale 0.5) | no draft mode | direct 572 s; cached **49.1 s** cold (4 scene renders), **22.1 s** warm | same frames, fps and camera timing as the final |
| full 1080p export, Hjerpefinte | 2552 s direct (historical run, context only; not rerun here) | cached cold **1253 s** (244 scene renders 1156 s + composite 89 s); cached warm **99 s** | both cached runs give the same mp4 bytes |
| caption-only change, full 1080p | full rerender | `--presentation` 0.24 s + render **96 s**: 244/244 hits, 0 scene renders | title and beat text edited, then reverted |
| IKV regression | - | 33 automatic stills cached cold 164.5 s (32 scene renders); draft of 8 segments (348 frames, 0.5) cached 473.5 s: 112 states, 15 reused from the stills run | stills and drafts at one scale share a namespace |
| `--gl angle` here | - | reports SwiftShader as well | no GPU in the container |

Cache sizes: 244 PNGs at 1920x1080 = 238 MB; 133 PNGs at scale 0.5 = 54 MB (`out/scene-cache/`, not committed).

Direct vs cached output (`validation/video-workflow/hjerpefinte-direct-vs-cached.jpg`): the scene layer alone
(`--no-graphics`) is byte-identical at frames 23, 247, 399 and 489. With overlays, pixels differ by at most 3/255, only
where overlays are drawn (translucent panels, text and line edges): the browser blends the overlays over a WebGL canvas
in one case and over an image in the other. The committed Hjerpefinte export is now the cached render; its report
records 631 frames checked against 244 verified entries (worst entry readback 2.8e-14, camera 0.005 mm).

Not measured: a direct full export on this branch, and anything on a GPU.

## 7. Limitations

- The cache pays off where states repeat (freezes with a still camera, the static start). A freeze under a moving camera
  is a new state per frame, so a cold cached export still renders 244 of 631 frames for Hjerpefinte.
- Cached and direct exports are not byte-identical (overlay blending, above); each is verified against the pure
  evaluation in its own way. The direct renderer stays the reference.
- The cache lives in `out/` (not committed, about 1 MB per 1080p state); nothing prunes old namespaces.
- `--presentation` covers shot-encyclopedia moves. The five hand-made videos keep their hand-written
  `data/presentations/*.analysis.json`, which is already presentation-only data.
- The Edwall analysis reports (`validation/analysis-edwall-g2-goal*-report.json`) fingerprint `AnalysisVideo.tsx` and are
  now stale; no test reads them and their videos were not re-rendered.

## 8. Render speed (2026-11-10)

Status: PROPOSED (branch `claude/project-thread-k1lpin`). Measured in the cloud container: 4 cores, no GPU, SwiftShader,
Chromium 141, 1920x1080. Raw numbers: `validation/video-workflow/render-speed.json`.

**Where a frame's time went** (Hjerpefinte, frames 300-305, one tab, after the scene has loaded): 4.2 s per frame, of which
4.0 s is the WebGL draw itself. The screenshot, the overlays and React are about 0.2 s. Inside the draw:

| part | cost per frame | how it was measured |
|---|---|---|
| second full-scene draw for the two clear end screens (three.js transmission pass) | 2.3 s | the screens made opaque: 1.9 s per frame |
| 4x multisampling (smooth edges) | about 1.0 s | `antialias: false`: 3.1 s; with the screens opaque as well: 0.93 s |
| the twelve figures (1.12 of the scene's 1.2 million triangles) | about 0.9 s of the 1.9 s | figures hidden: 1.0 s with the screens opaque |
| rink (49 k triangles, but most of the pixels) | about 1.0 s of the 1.9 s | same run |

Two more findings: a second tab does not help on a software renderer (12 frames: 32 s with one tab, 36 s with two, 44 s
with four; SwiftShader already runs on all four cores), and `--scale 0.5` did not make the 3D draw smaller (R3F clamps the
device pixel ratio to at least 1, so a half-size draft was drawn at 1080p and shrunk by the screenshot).

**What changed**

1. `remotion/scene-render.ts` draws the opaque scene once and gives three's transmission pass the canvas itself (colour
   converted back from ACES + sRGB to linear light, and the canvas depth) instead of a second draw of the whole scene.
   three's own transmission shader still draws the screens. `--plain-render` keeps the old single call as the reference.
   If the canvas depth cannot be copied, the tone mapping is not ACES filmic + sRGB, or no screen is in view, the plain
   call is used. Every frame logs how it was drawn (`[<tag>-draw]`; reports: `scene_draws`).
2. The canvas uses the page's device pixel ratio while rendering, so a draft or still at scale 0.5 draws a quarter of the
   pixels. Scale 1 is unchanged.
3. Tabs: 1 for WebGL on a software renderer, 2 on a GPU, one per core (at most 8) for composites over cached scene images.

**Picture**: outside the end screens the new renderer gives the plain render's bytes. Through a screen, three frames
compared at 1080p without overlays (`validation/video-workflow/scene-render-before-after.jpg`):

| frame (Hjerpefinte) | pixels that differ (of 2 073 600) | by more than 2/255 | by more than 8/255 | largest |
|---|---|---|---|---|
| 40 (wide view, both screens) | 6270 | 1064 | 21 | 17/255 |
| 300 (goal view) | 1201 | 145 | 7 | 11/255 |
| 480 (replay view) | 1254 | 159 | 8 | 10/255 |

The differences sit where a screen meets an opaque edge (one depth per pixel instead of one per sample) and, below
2/255, in what is seen through the plastic (it has passed through the canvas' 8 bits).

**Time**

| workload | before | now |
|---|---|---|
| one frame, 1080p, scene loaded | 4.2 s | 2.5 s |
| 24 frames 300-323, 1080p, direct (`final --frames 300-323`) | 121.4 s (2 tabs) | 68.6 s |
| the same 24 frames as a half-size draft | about 121 s (it was drawn at 1080p and shrunk); 77.9 s with only the pixel-ratio fix | 41.6 s |
| full 1080p Hjerpefinte export, empty cache (807 frames, 313 scene states) | 2470 s recorded on 2026-10-13 (2330 s scene renders + 140 s composite, two tabs, Chromium 141); not rerun today | **941 s (15.7 min)**: 313 scene renders 853 s (2.7 s each), composite 81 s |
| composite of 807 frames over cached scenes | 2 tabs (99 s for 631 frames on 2026-10-12) | 81 s, 4 tabs |

All six committed videos were re-exported with the new renderer (`final --cache`, empty cache, scale 1). "Previous" is
the render time recorded in the report each export replaces (2026-10-06 to 2026-10-13: the five hand-made videos direct
with two tabs, Hjerpefinte cached from an empty cache; Chromium 141, today 149), so that column is another day and browser
build and includes the move from direct to cached exports:

| video | frames | scene states | previous export | now |
|---|---|---|---|---|
| move:hjerpefinte | 807 | 313 | 2470 s | **938 s** (852.8 s scenes + 81.3 s composite) |
| shovel-17 | 748 | 405 | 3965 s | **1255 s** (1167.9 s scenes + 83.6 s composite) |
| spjass | 742 | 335 | 3571 s | **958 s** (879.6 s scenes + 74.7 s composite) |
| ikv | 900 | 509 | 4261 s | **1309 s** (1215.2 s scenes + 90.6 s composite) |
| defence-lw | 1061 | 154 | 4342 s | **427 s** (328.7 s scenes + 95.3 s composite) |
| nacka | 744 | 316 | 4482 s | **826 s** (753.8 s scenes + 68.8 s composite) |
| all six | | | 23091 s (6.4 h) | **5712 s (1.6 h)** |

Every scene state was drawn by the new path (`scene_draws: reuse`), every frame was checked against a verified cache
entry, and frame accounting passed for all six. Frames 450 (IKV) and 60 (Hjerpefinte) of the new files were looked at.
The review sheets and occlusion reports next to the hand-made videos (`validation/analysis-*-review.png`,
`-occlusion.json`) were not regenerated: they do not depend on the renderer's pixels beyond what is described above.

**What is left, and what would be the next step**: a frame is now about 1.9 s of opaque scene (half of it the 4x
multisampling) plus 0.6 s for the screens. At half size the figures' triangles dominate (1.7 s per frame), which is why a
draft is 1.6x and not 4x faster than a final. Not done, each needs a decision:
- a lower-detail copy of the figures for rendering (80 k triangles per skater, 160 k per goalie, drawn at 100-300 pixels
  height): an estimated further 0.5-0.7 s per frame; changes the drawn model slightly;
- a GPU: `--gl angle` (or `angle-egl`, `vulkan`) on a machine with one draws a frame in a small fraction of this; still
  unverified because the container has none;
- reusing the unchanged background while the camera stands still (131 of Hjerpefinte's 313 states): about a quarter of
  the scene time, a larger change to the renderer.
