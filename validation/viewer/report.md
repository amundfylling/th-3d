# Hypothesis: a live browser viewer replaces rendered video for the catalogue

**Verdict: page weight and load time CONFIRMED; 60 fps on desktop NOT MEASURABLE here (inconclusive, with a bounded estimate); cost and learning-value claims supported but the learning claim is a judgement, not measured.**

Prototype: `viewer/` + `scripts/viewer-{build,serve,optimize-scene}`, docs in `docs/viewer.md`. Loads Hjerpefinte, Näcka, Spjass and Invers Kryssar med Velodrom from the existing traces through the existing evaluator (`scripts/viewer-export.ts`, which already existed and was made tolerant of moves without story/checks files).

## What was built
Scrub, 0.02x to 1x speed, ±5 ms stepping, loop, orbit/pinch camera with 5 presets (oblique, overhead, side, behind W, follow puck), puck trail plus faint full path, event markers on the ice, per-figure highlight ring, event list (tap to jump), phase timeline, story text for moves that have it, responsive phone layout (stage on top, controls and text below), space/arrow keys. Redraws only when something changed (idle = 0 GPU work).

## Measurements (headless Chromium 1243, localhost, brotli, cold load)
| item | size on the wire |
|---|---|
| viewer.js (three.js + app) | 153 KB br (173 KB gz) |
| scene.glb (rink, 12 figures, goals, puck) | 0.85 MB (was 17.1 MB raw GLB) |
| move data | Hjerpefinte 3.5 KB, Näcka 4.2 KB, Spjass 5.2 KB, IKV 18 KB (gzip; 2 ms samples) |
| **first visit total** | **~1.0 MB** (measured 1011-1025 KB per move) |
| **each further move** | **4-18 KB**, scene and code are cached |

Target was under 5 MB per move: met with 5x margin, even counting the full scene for every move. Load: scene fetch+decode 180-250 ms, ready 0.3-0.5 s, first frame ~0.9-1.1 s on localhost (no network latency included; on 4G add roughly 1 MB / 1.5 Mbit/s ≈ 5 s).

Size work needed to get there (the raw scene GLB is 17 MB, which on its own would fail the target): meshopt + WebP (17.1 → 1.65 MB), then mesh simplification (→ 0.87 MB). Skater 79.5k → 12.4k triangles, goalie 160.8k → 25k, per-frame triangles 2.39M → ~290k, 100 draw calls. Close-up comparison with the original: no visible difference (`skater-simplified-vs-original.png`, left simplified, right original).

## Frame rate: what could and could not be measured
This sandbox has no GPU; WebGL runs on SwiftShader (CPU rasteriser). It takes 0.8-2 s per frame regardless of resolution (320x180 still 1 s), so it says nothing about GPU fps. **I did not observe 60 fps and do not claim it.** What was measured:
- JS cost per frame (pose interpolation + three.js command submission): **3.4 ms mean (5 ms max) at 1x, 13.6 ms mean (21 ms max) at 4x CPU throttle**. A phone-class CPU at 4x fits a 60 fps frame only just; at 2x it fits comfortably.
- GPU load per frame: ~290k triangles, 100 draw calls, one 2048-px ice texture, MSAA on. This is a light budget for any laptop/desktop GPU (millions of triangles at 60 fps is routine) and plausible for phones, but unverified. Removing KHR transmission on the clear end screens (they make three.js draw the scene twice) was needed for that budget and halved the software-GL time (2.0 s → ~0.9 s).
- Needs a real-GPU run (any laptop, `npm run viewer:build && npm run viewer:serve`, open `/?bench=1&play=1#nacka`, read `__viewer.perf`) to settle it.

## Cost
Video: ~41 CPU-hours of rendering for the catalogue (coordinator's figure; not re-measured). Viewer: moves export in about a second each at 2 ms sampling, no rendering. Hosting is a static folder. Adding a move = export one JSON (4-18 KB). The viewer cannot replace what video does well: narration, captions, cuts, sharing on TikTok.

## Caveats
- The viewer shows the PROPOSED traces; Näcka, Spjass and IKV have no `checks`/story files so the sidebar shows less ("n/a").
- The simplified scene is a viewing copy; contact rules (docs/trace-verification.md) still run on the original geometry.
- Trail is a flat ribbon on the ice (puck height ignored); goalie/skater print decals are carried along unchanged.
- Highlight uses a ring on the ice because cloning shared figure materials broke three's uniform refresh (found and removed).
- The learning-experience claim is an opinion: free camera, slow motion and scrubbing are things a video cannot offer; I did not test with users.

## Screenshots
desktop-nacka-oblique.png, desktop-hjerpefinte-overhead.png (highlight ring on the goalie, trail), desktop-spjass-follow.png (follow-puck camera), mobile-ikv.png (390x844), skater-simplified-vs-original.png. All rendered in software GL.
