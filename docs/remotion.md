# Remotion static integration (iteration 19)

## Versions (exact pins; npm lockfile)

| Package | Version |
| --- | --- |
| `remotion`, `@remotion/cli`, `@remotion/three` | 4.0.531 (all `@remotion/*` in the lockfile are 4.0.531, checked by a test) |
| `react`, `react-dom` | 19.2.0 |
| `three` | 0.186.1 (`@types/three` 0.186.0) |
| `@react-three/fiber` | 9.4.0 |

The online docs (remotion.dev) were blocked by the network policy. The API was taken from the packages
themselves:
- `@remotion/three` `ThreeCanvas` requires `width` and `height`, and wraps its children in a Suspense loader that calls `delayRender`.
- The `@remotion/renderer` `gl` option accepts `swangle`, `angle`, `egl`, `swiftshader`, `vulkan` and `angle-egl`.

## Commands

```sh
npm run remotion:stills   # copies the GLB to public/ and renders out/19-{oblique,overhead,side,checks}.png
npm run remotion:studio   # interactive studio (not used in the cloud container)
```

- **Browser.** The full Chromium 141 in `/opt/pw-browsers` refuses Remotion's headless mode ("Old Headless mode has been removed"). The environment's **chrome-headless-shell** (`/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell`) works.
- **WebGL.** `--gl=swangle` gives WebGL through SwiftShader (CPU), about 25 s per 1920 × 1080 still.

## Structure

- `remotion/index.ts`, `Root.tsx`: compositions `static-overhead`, `static-side` and `static-oblique` (1920 × 1080, 30 frames), plus `static-checks` (oblique with a check overlay).
- `remotion/StaticInspection.tsx`:
  - loads `public/full_static_appearance.glb` (the iteration-18 Blender export) with `useLoader(GLTFLoader, staticFile(...))`, so `ThreeCanvas` waits for it;
  - the scene then holds a `delayRender` handle until the post-import checks have run;
  - it never reads the frame number, so every frame is the same fixed pose: frame 0 and frame 29 are pixel-identical (checked).
- `remotion/cameras.ts`: cameras defined in world mm and converted once with `worldMmToGltfM` (`src/model/coordinates.ts`). They match the Blender benchmark cameras.
- `remotion/checks.ts`: after import,
  1. **basis point:** the W-RD fixture axis from the pose data (mm, z up) through the adapter equals the imported node's world position (0.0004 mm);
  2. **blade orientation:** the stored W-RD blade, placed by the pose matrix, has the same direction (0.00000°) and tip (0.0000 mm) as when placed by the imported node's matrix, and it stays on the figure's left;
  3. **units and axes:** the imported ice extent equals the canonical boundary in metres, with the ice top at Y = 0.

  All three **PASS** in the rendered `validation/19/19-checks.png`.

## Review (AI)

`validation/19/19-overhead.png`, `19-side.png`, `19-oblique.png` and `19-checks.png` match the Blender
stills of iterations 17–18 in layout, units and orientation.

Differences from Cycles:
- **End screens are opaque white.** Blender transmission becomes a glTF transmission material that the three.js default pipeline does not render as clear.
- No shadows (no shadow maps configured) and simpler lighting.
- The ice looks flatter.
- WebGL runs on the CPU (SwiftShader), with no GPU.

There is no animated shot, no physics loop and no camera animation.

## Shot playback (iteration 23)

- `remotion/ShotPlayback.tsx`, compositions `shot23-shovel-17` (the accepted trace at real speed, 30 fps,
  1920 × 1080) and `shot23-at-time` (one frame at any source time, `--props='{"startS": t}'`, for diagnostics).
- Time: `t = startS + useCurrentFrame() / fps` (`sourceTimeForFrame`, `src/model/shot-pose.ts`). Each frame sets
  every trace-driven node (W-C, W-RW, E-G, E-RD, E-LD, puck) to an absolute pose from the pure evaluator. There is
  no `useFrame()`, no clock and no state carried between frames. The other seven figures keep the static assembly pose.
- Rotation: the pose matrix comes from the continuous heading (`rigid(heading)`), never from a quaternion blend
  between frames, so a turn through 0/360 deg cannot take the short way back.
- Version gate: `remotion/asset-manifest.json` (written by `scripts/shot23-manifest.ts` in `npm run remotion:assets`)
  holds the geometry version and the SHA-256 of the files named by the trace's `asset_refs`, and of the scene GLB.
  The composition throws if the trace differs from it or is not `accepted`. The browser also hashes the GLB it
  actually loads, and cancels the render on a mismatch.
- Each frame logs `[shot23-state]` (pure state plus a read-back of the drawn nodes). `scripts/shot23-render.ts` uses
  the Node API (`renderStill`/`renderMedia` with `onBrowserLog`), because the CLI does not print page `console.log`.
- Caveat (studio only): `useLoader` caches the GLB per page, so in an interactive studio session the shot's posed
  nodes would also show in a static composition opened afterwards in the same tab. Renders load each composition
  separately and are not affected (the static-checks still was re-rendered after iteration 23: all PASS).
