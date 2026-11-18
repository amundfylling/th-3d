# Interactive 3D move viewer (PROPOSED, prototype)

A static web page that plays the saved traces live in the browser: scrub, slow motion (0.02x-1x), free orbit/touch camera,
presets (oblique, overhead, side, behind W, follow puck), puck trail and full-path ribbon, figure highlight ring, events
(tap to jump), phases on the timeline, story text, mobile layout. No server logic; host `viewer/dist/` on any static host.

- Build: `npm run viewer:build` (exports the four moves with `scripts/viewer-export.ts` every 2 ms, bundles `viewer/src/main.ts`
  with esbuild). Serve locally with brotli: `npm run viewer:serve` (http://localhost:8123/#nacka).
- Rule 7 holds: the page only interpolates samples written by the same pure evaluator as the videos (`shotTimeEvaluator`); no physics.
- Scene: `viewer/public/scene.glb` is `assets/scene/full_static_appearance.glb` after `scripts/viewer-optimize-scene.sh`
  (17.1 MB -> 0.87 MB; meshopt, WebP, meshes simplified to 15 %). The skater drops from 79.5k to 12.4k triangles; compared in
  `validation/viewer/skater-simplified-vs-original.png`. The clear end screens use plain translucency instead of KHR transmission
  (`?transmission=1` restores it). It is a viewing copy: contact checks always run on the original geometry.
- Moves without `moves/<id>/story.json` or `shots/<id>/checks.json` simply show less text (the exporter tolerates both).
- Measurements and verdict: `/mnt/project-files/hypotheses/live-3d-viewer/report.md` (the copy in `validation/viewer/report.md`).
