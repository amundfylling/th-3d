# Project state

## Current position

- Last completed iteration: **05 - Trace only the installed board boundary** (2026-09-30), plus the post-05
  decisions of the same day (docs/decisions.md D1-D5). The user delegated the board-trace review to the AI.
  AI review accepted the trace from recorded evidence. No personal user approval is claimed.
- Batch run 06-20 complete. Last completed: **20 - Review the model and incorporate calibration** (2026-09-30). Next: **21** (blocked on user review feedback + a real shot recording).
- **Player figures (user request, done before 21, 2026-09-30):** the skater and goalie proxies and the ten
  placeholders are replaced by two rigid STIGA molds (skater shared by all ten skaters, goalie by both goalies)
  in Sweden/Finland kits, fitted to the user's photos/videos (`references/players_images`) and the official
  overhead: mount socket (fixture axis) under the left skate (skater) / right skate (goalie), stick, blade,
  skates, uniform and back prints. geometry_version **0.6.0**. Details, results and open questions:
  `docs/players.md`. AI review only; no user approval recorded.
- **Figure refinement round 2 (user request, 2026-10-01):** visible-fidelity pass on the skater (arms/torso,
  helmet, face, collar, gloves) and goalie (mask with painted skin gaps, pads, blocker, catcher), block-number
  lettering traced from the photos, calibrated plastic colours; matched-camera close-up sheets including
  held-out views (`validation/players/closeups-{skater,goalie}.png`). Still before iteration 21.
- **Goalie measured (user, 2026-10-01):** height 54 mm, blade 26 x 5.5 mm recorded as `user_measurement`;
  goalie scale and blade set from them (k 1.142); skater scale unchanged (overhead-fitted) until measured.
- **Track fix (user, 2026-10-01):** E-RW and W-RW followed a stick lying on the slot in the official
  overhead; operator occlusion boxes in the tracer straighten them (docs/tracks.md); rink, scene, renders and
  Remotion stills regenerated.
- **Figure refinement round 3 (user request, 2026-10-01):** moulded contours - skater gloves (fists), lathe
  gauntlet cuffs, helmet, face, collar; goalie mask (eye hollows, ridge), skin crescents, pads, catcher (pocket,
  thumb ridge); blue albedo desaturated. Cameras frozen; before/after sheet
  `validation/players/closeups-before-after.png` (held-out views in red). Goalie 54 mm / 26 x 5.5 mm kept.
  Remaining mismatches and next inputs: `docs/players.md`. AI review only. Still before iteration 21.
- Geometry version: `0.5.0` (`data/geometry.json`). Board boundary, all 12 slots and both goal regions traced in pixels;
  goal setup = without inserts (user). No meshes or movement.
- Code, 3D assets, animations: none. No animated shots exist or are planned before iteration 23.

## Batch run result (docs/autonomous-run.md)

**Batch 06-20 finished 2026-09-30: all iterations completed with recorded verification. Stopped after 20 as instructed.**
No motion reconstruction or animated shots were started. **Next: iteration 21 requires the user's review feedback and a real shot recording.**

Iteration 20 closed without repair cycles:
- [x] Intake recorded: nothing supplied; checks re-run (84/84 tests, validate).
- [x] Reprojection check: slots mean offset <= 1.7 px, ice edge median 0.75 px (pipeline consistency only).
- [x] Review sheet validation/20-review-sheet.png (matched overhead; side/oblique qualitative; blade/puck provisional), AI-reviewed; geometry and appearance reported separately.
- [x] Output 1920x1080 proposed; the one-output-pixel claim is explicitly NOT supported.
- [x] Remotion/Three judged below photorealism; a bounded Cycles benchmark task specified, not started, no pipeline switch.
- [x] Four separate statuses and the required inputs in docs/review.md; user approval NOT recorded.

## Verification status

| Item | Status |
| --- | --- |
| PDF text and hyperlinks | Extracted (iteration 01). PDF unchanged, SHA-256 `1c7355ef...9a4cc`. |
| Embedded images | All 10 extracted to `references/originals/` (7 JPEG byte-identical to the PDF's DCT streams, 3 lossless PNG). Native sizes verified against captions. SHA-256 in `references/index.json`. |
| View identities | Confirmed by viewing each image (downscaled previews) plus two native-resolution crops. |
| Remote originals | **Not obtained.** Network policy blocks `stigasports.centracdn.net`, `www.stigasports.com`, `www.stigacanada.ca`, `d.otto.de`, `www.ithf.info` (curl CONNECT 403; WebFetch EGRESS_BLOCKED). Byte identity with remote files unverified. |
| Tooling (iteration 03) | `npm ci`, `npm run typecheck`, `npm run smoke` all run and pass (clean reinstall from lockfile). Typecheck confirmed to fail on a deliberate type error. Smoke SVG rendered in headless Chromium and viewed. |
| Geometry contract (iteration 04) | `npm run check` passes: typecheck (incl. tsc cross-check that runtime schema matches the interfaces; a removed field was confirmed to fail), `npm run validate` (schema + policy + reference hashes), 15 policy tests (canonical file valid; 12 invalid mutations rejected; similarity-uniformity helper). |
| Board trace (iteration 05) | 1431/1440 rays detected and consistent; 2 short interpolated stretches. Fit RMS <= 2.73 px (long sides bow outward up to 10.1 px; quadratic RMS <= 0.49 px); corner radii 610-625 px. Trace uncertainty 21 px (dominated by the ~15 px dark strip at the board base); uniform-mapping bound 16.5 px. Rerun reproduces byte-identical outputs. Overlay rendered in headless Chromium and inspected by me (corners, landmark, gap insets). |
| Post-05 review evidence | `node scripts/check-board-evidence.ts` -> `validation/05-evidence-check.json`. Strip width 7.3-8.1 px per 1000 px radius (vertical board face). Marking lines bow 19% / 47% of the lens-model prediction (lens explains only part of the board bow). `npm run check` passes (18 tests). |
| Slot traces (iterations 06-08) | 12 paths x 2 photos. Overhead fit RMS <= 0.74 px, width 38-40 px; bare->overhead homography over 10 outfield slots RMS 2.54 px (goalie slots excluded: symmetric ~7 px offset); every hidden end extends forward (+22 to +167 px). Goal cut-outs mapped onto goal lines within 8 px. Overlays 06/07/08 AI-reviewed. 23/23 tests. |
| Pose maths (iteration 09) | 10 pose tests pass (continuity on all 12 paths, boundaries, 360 deg, known point, handedness det +1, goalie adapter, glTF adapter). Debug SVG AI-reviewed. |
| Contacts (iteration 10) | Provisional debug contacts for W-RD only; rigidity, rotation and handedness tests pass; review sheet AI-reviewed. Real pivot, blade and skate values UNKNOWN. |
| Blender (iteration 11) | bpy 4.5.14 LTS (PyPI) in /root/venvs/blender; Cycles CPU. Rink built headless; GLB bounds and ID-render scale checks pass (tests 40/40). See docs/blender.md. |
| Figure molds (2026-09-30) | `npm run check` passes (73 tests: typecheck, validate, figures/assembly/appearance/Remotion tests). Silhouette IoU skater 0.808 (7 views) / goalie 0.816 (8 views); overhead k = 1.071 mm/mold unit (4 Sweden skaters, IoU 0.69-0.79); stick check within 1.5 mm; assembly without intersections; Remotion import checks pass; reprojection worst slot mean 0.80 px (check made colour-aware: figure plastic over the E-G slot, recorded in scripts/review-reprojection.ts). Renders inspected (AI review). |
| Dimensional accuracy | Goalie height and stick blade measured by the user (2026-10-01). Everything else not measured. All sizes are `catalog_nominal`, `assumed` (preview scale) or `unknown`. |

## Key decisions

- Figures (2026-09-30): one skater mold and one goalie mold (user statement: every skater identical; teams
  differ only in kit colour and country name). Team W = Finland kit, E = Sweden kit (D4). Figure scale from the
  official overhead at the assumed preview scale, shared by both molds (`assume.figure_mold_scale`); the
  iteration 13-15 proxies, debug contacts and their scripts were removed (git history keeps them).

- Sponsors dropped (user, D6, 2026-09-30): the ice carries hockey markings only; the reference print is kept as `assets/rink/textures/ice_basecolor_reference.png`.

- Target family 71-1145-XX; Sweden/Finland 71-1145-01 public gallery is the reference variant until
  the user supplies their own parts/teams/artwork.
- Conflicting overall lengths (960 vs 940 mm) are kept separate, not averaged. The approx. 845 x 457 mm
  playing area is not stretched to a housing size.
- Bare-sheet photo (older artwork, may extend beneath the boards) is for slot topology only, never
  for scale or installed-rink artwork.
- The PDF-embedded gallery images (5154-5636 px) are the working originals; remote downloads are only
  needed for byte-identity verification, not for tracing.
- Figures are rigid; motion data stays separate from camera and presentation (see CLAUDE.md).
- Tooling: npm + TypeScript 7.0.2 typecheck only; Node 22.18+ runs `.ts` directly (erasable syntax,
  `.ts` import extensions). No tsx/ts-node, Remotion, bundler or test framework yet. See `docs/tools.md`.
- Geometry: world mm, origin at the centre of the inner board boundary on the ice top (z = 0), +x toward
  `goal.E` (image-right of the official overhead), +y toward its image-top side, +z up. Teams named by
  side (`W`, `E`); reference variant Finland = W, Sweden = E. Details: `docs/geometry.md`.
- The runtime schema is hand-written typed combinators (no JSON Schema dependency); tsc enforces that it
  matches the TypeScript interfaces.
- Catalog values imported as `catalog_nominal`: housing claims 960 x 500 and approx. 940 x 502 x 83 (unresolved
  conflict), playing area approx. 845 x 457, skater figure height approx. 57 (datum unknown; not applied to
  goalies), end screen approx. 70 x 622 (length datum unknown), puck diameter approx. 25.4. Everything else null.
- No preview scale chosen in iteration 04. Iteration 05 added `map.overhead.preview`: ASSUMED uniform 0.179597 mm/px
  (catalog approx. 845 mm = traced length 4705 px). Implied width 468.8 mm vs catalog approx. 457 mm - reported, not
  forced. The mm outline (`board.inner_boundary.world`) is `assumed`; corner radius and board length in mm stay unknown.
- Board trace = ice side of the near-black strip at the board base (`assume.board_edge_is_ice_contact`); not the
  top rail, housing or loose-sheet perimeter. Method and checks: `docs/board-trace.md`.
- Observations to carry forward: long sides bow outward (lens or real boards, unresolved); every marking line
  leans ~0.35 deg relative to the board axis (sheet possibly rotated in the boards); ~0.5% keystone left-right.
- Image decoding in TypeScript uses jpeg-js (devDependency).
- Goal setup: without inserts or goal cups, screens kept (user, D5). Team/position convention unchanged (user: keep it consistent, D4).
- Planned structure: `references/`, `data/`, `src/model/`, `assets/`, `validation/`, `docs/`.

## Before iteration 06

- Board-trace review: done by AI review under delegation (D1-D3). The user may still override it.
- Iteration 06 traces tracks in the same overhead. Per D3, tracks follow the printed sheet (possibly rotated ~0.3 deg
  in the boards) and are not straightened to the board axis.

## Missing inputs (most important first)

1. Empty installed rink, perpendicular overhead, with scale markers in both directions
   (inner board boundary, track centrelines, slot ends).
2. **(critical, blocks shot accuracy)** Loose and installed figures with scale: fixture pivot, blade offset/profile, stick handedness,
   skate contacts, ice clearance, figure-height datum. No loose-figure views exist at all
   (full list under `missing_views` in `references/index.json`).
3. Travel stops and rod push/pull + twist recordings per control type (goalie, wing with link 7A,
   defence, centre).
4. Puck thickness, diameter, rim profile, mass; goal size, posts, clearance.
5. The user's actual teams/artwork. (Goal configuration now known: without inserts, D5.)
6. Blocked downloads: full manual A06 (`d.otto.de`), ITHF rules (`www.ithf.info`), the 1001 x 603
   older-artwork overhead (`www.stigacanada.ca`; not in the PDF). Allow these hosts in the cloud
   environment's network settings, or upload the files to `references/originals/`.

## Review artifacts

- **`validation/20-review-sheet.png`** - iteration 20 main artifact. Review: `docs/review.md`.
- **`validation/19/19-checks.png`**, `19-overhead.png`, `19-side.png`, `19-oblique.png` - iteration 19 Remotion stills. Docs: `docs/remotion.md`.
- **`validation/18-oblique-1080p.png`** and `18-*` close-ups - iteration 18 (assets/scene/full_static_appearance).
- **`validation/17-overhead-vs-reference.png`**, `17-oblique.png` - iteration 17 (assets/scene/full_static_materials, ice texture). Docs: `docs/materials.md`.
- **`validation/16-overhead-labelled.png`**, `16-oblique.png` - iteration 16 (assets/scene/full_static).
- **`validation/15-goalie-oblique.png`**, `15-goalie-side.png`, `15-goalie-top.png` - iteration 15 (assets/figures/goalie_W-G).
- **`validation/14-view-sheet.png`**, `14-silhouette-top.png` - iteration 14 (assets/figures/skater_W-RD). Docs: `docs/figures.md`.
- **`validation/13-contacts-top.png`**, `13-contacts-side.png` - iteration 13 (assets/figures/skater_W-RD_lower).
- **`validation/12-goal-oblique.png`**, `12-puck-side.png`, `12-overview.png` - iteration 12 (assets/goal, screen, puck, scene/static_hardware).
- **`validation/11-rink-overhead.png`**, `11-rink-side.png` - iteration 11 clay rink (assets/rink/rink.blend, rink.glb). Docs: `docs/blender.md`.
- **`validation/10-skater-contacts.svg`** - iteration 10 (critical checkpoint; provisional contacts). Docs: `docs/contacts.md`.
- **`validation/09-pose-debug.svg`** - iteration 09 (static sample poses). Docs: `docs/pose.md`.
- **`validation/08-goals-and-goalies.svg`** - iteration 08 (12-route inventory, goal regions, unresolved dimensions). Docs: `docs/goals.md`.
- **`validation/07-winger-tracks.svg`** - iteration 07 (4 wingers, sample points, end insets).
- **`validation/06-straight-tracks.svg`** - iteration 06 (both photos, 6 colour-coded paths, 12 end insets, evidence table). Method: `docs/tracks.md`.
- **`validation/05-board-overlay.svg`** - main artifact of iteration 05 (unchanged photo at native size, trace,
  landmark IDs with pixel coordinates, 9 zoom insets, notes). Numbers: `validation/05-board-report.json`.
- `docs/board-trace.md` - trace method, checks, error estimate, assumptions.
- `docs/decisions.md` - decision log (D1-D5); `validation/05-evidence-check.json` - evidence for D2/D3.
- `data/geometry.json` - canonical geometry (iteration 04; all physical unknowns null).
- `docs/geometry.md` - coordinate system, IDs, evidence policy, Blender/glTF/Three adapter.
- `validation/03-smoke.svg` - toolchain smoke diagnostic (iteration 03; not hockey geometry).
- `docs/tools.md` - environment findings; `README.md` - working commands.
- `references/index.json` - source catalogue (main artifact of iteration 02).
- `references/originals/` - the ten recovered images.
- `docs/reference.md` - reference brief, now with recovered assets and manual page numbers.
- `CLAUDE.md` - project instructions.

## Iteration history

| Iteration | Date | Result | Checks run |
| --- | --- | --- | --- |
| 01 | 2026-09-30 | CLAUDE.md, docs/reference.md, docs/state.md | PDF text/link/image-object extraction; page renders viewed; PDF SHA-256 recorded, file unchanged |
| 02 | 2026-09-30 | 10 PDF-embedded images in references/originals/, references/index.json, manual pages 2/18 in docs/reference.md | Byte comparison of extracted JPEGs vs decoded PDF streams (7/7 identical); decoded sizes vs captions (10/10 match); SHA-256 computed; JSON parse check; previews and 2 native crops viewed; download attempts for 5 hosts (all blocked); PDF SHA-256 unchanged |
| 03 | 2026-09-30 | package.json, package-lock.json, tsconfig.json, .gitignore, scripts/smoke.ts, data/fixtures/smoke.json, validation/03-smoke.svg, README.md, docs/tools.md | Environment inspected; `npm ci` clean reinstall; `npm run typecheck` pass (and fails on a probe error); `npm run smoke` pass; SVG screenshot in headless Chromium viewed |
| 04 | 2026-09-30 | src/model/{geometry,geometry-schema,check,validate}.ts, data/geometry.json, scripts/validate-geometry.ts, tests/geometry.test.ts, docs/geometry.md | `npm run check` (typecheck, validate, 15 tests) pass; schema-drift probe fails as intended |
| 05 | 2026-09-30 | scripts/trace-board.ts, scripts/render-board-overlay.ts, src/model/{fit,raster}.ts, data/geometry.json 0.2.0 (trace, 10 landmarks, 4 assumptions, preview mapping), validation/05-board-{overlay.svg,report.json}, docs/board-trace.md; jpeg-js added | `npm run check` (typecheck, validate, 17 tests) pass; tracer rerun byte-identical; source photo hash unchanged; overlay screenshot inspected (main view + insets); user visual approval not received |
| 05+ | 2026-09-30 | User answers recorded: goal setup without inserts, convention kept, review delegated. scripts/check-board-evidence.ts, validation/05-evidence-check.json, docs/decisions.md; `user_statement` source kind; geometry 0.3.0 | Evidence script run; trace rerun (points unchanged); overlay re-rendered; `npm run check` 18/18 pass |
| 06 | 2026-09-30 | slot tracer (src/model/slot-trace.ts, homography.ts, scripts/trace-slots.ts, render-tracks-overlay.ts), data/slot-seeds.json, 12 slot traces + 24 end landmarks, geometry 0.4.0 (fixture_axis_path, identity_evidence, team label, trace stats), validation/06-straight-tracks.svg, slots-report.json, docs/tracks.md | `npm run check` 20/20; overlay AI-reviewed; 2 repair cycles |
| 07 | 2026-09-30 | 4 winger traces (both photos), tracer robustness fixes (06 re-traced), measured bare curve seeds, validation/07-winger-tracks.svg, recording-needs list in docs/tracks.md | `npm run check` 21/21; overlays 06 and 07 AI-reviewed; 2 repair cycles |
| 08 | 2026-09-30 | goalie slot traces, hidden-end handling (all traces refreshed), goal regions (scripts/trace-goals.ts, render-goals-overlay.ts), Goal schema traces/landmarks, validation/08-goals-and-goalies.svg, goals-report.json, docs/goals.md | `npm run check` 23/23; overlays 06-08 re-rendered, 08 AI-reviewed; 2 repair cycles |
| 09 | 2026-09-30 | src/model/pose.ts, paths.ts, coordinates.ts; tests/pose.test.ts; assumption assume.fixture_axis_on_slot_centreline; validation/09-pose-debug.svg; docs/pose.md | `npm run check` 33/33; debug SVG AI-reviewed; 1 presentation repair |
| 10 | 2026-09-30 | scripts/define-contacts.ts, render-contacts.ts; schema (provisional contact shapes, inventory); fig.W-RD inventory + provisional contacts; W-RD stick left; validation/10-skater-contacts.svg; docs/contacts.md; tests/contacts.test.ts | `npm run check` 37/37; sheet AI-reviewed; 1 presentation repair |
| 11 | 2026-09-30 | assets/blender/stiga_blender.py, build_rink.py, verify_rink.py; assets/rink/rink.blend + rink.glb; preview_parameters (schema + data); slot tracer fixes (Hermite gaps, curve-following hidden ends, goalie seeds); validation/11-*; docs/blender.md; tests/rink-asset.test.ts | `npm run check` 40/40; stills AI-reviewed; 2 repair cycles |
| 12 | 2026-09-30 | assets/blender/build_hardware.py; assets/goal, screen, puck, scene/static_hardware (.blend/.glb); hardware preview_parameters; 'ratio' unit; side A and puck sources; geometry 0.5.0; validation/12-*; tests/hardware-assets.test.ts | `npm run check` 46/46; 3 stills AI-reviewed; 2 repair cycles |
| 13 | 2026-09-30 | assets/blender/build_skater_lower.py; assets/figures/skater_W-RD_lower.blend/.glb; contact build sizes; validation/13-*; tests/skater-lower.test.ts | `npm run check` 52/52; close-ups AI-reviewed; 2 repair cycles |
| 14 | 2026-09-30 | assets/blender/build_skater_body.py; assets/figures/skater_W-RD.blend/.glb; traced top silhouette (trace.figure.W-RD...); W-RD inventory (body proxy, mold sharing, skate conflict); validation/14-*; docs/figures.md; tests/skater-body.test.ts | `npm run check` pass; silhouette IoU 0.816; view sheet AI-reviewed; 1 repair cycle |
| 15 | 2026-09-30 | scripts/define-goalie.ts; assets/blender/build_goalie.py; shared metaball/silhouette helpers; assets/figures/goalie_W-G.*; W-G traces/contacts/inventory; goalie_height preview; validation/15-*; tests/goalie.test.ts | `npm run check` pass; IoU 0.794; renders AI-reviewed; 1 repair cycle |
| 16 | 2026-09-30 | scripts/assembly-poses.ts; assets/blender/build_assembly.py; assets/scene/full_static.*; validation/16-*; tests/assembly.test.ts | `npm run check` pass; renders AI-reviewed; 1 repair cycle |
| 17 | 2026-09-30 | assets/blender/make_ice_texture.py, build_materials.py; assets/rink/textures/ice_basecolor.png; assets/scene/full_static_materials.*; validation/17-*; docs/materials.md; tests/materials.test.ts; venv pinned numpy<2 + opencv 4.10 | `npm run check` pass; renders AI-reviewed; 3 repair cycles + 1 failed run (all fixed) |
| 18 | 2026-09-30 | assets/blender/build_appearance.py, render_appearance.py; materials on skater_W-RD, goalie_W-G, puck; assets/scene/full_static_appearance.*; validation/18-*; tests/appearance.test.ts | `npm run check` pass; renders AI-reviewed; 1 repair cycle |
| 19 | 2026-09-30 | remotion/ (index, Root, StaticInspection, cameras, checks); pinned remotion 4.0.531, react 19.2.0, three 0.186.1, R3F 9.4.0; tsconfig JSX/DOM; validation/19/*; docs/remotion.md; tests/remotion-setup.test.ts | typecheck + 83 tests pass; 4 Remotion stills rendered and AI-reviewed; import checks PASS; 2 repair cycles |
| 20 | 2026-09-30 | scripts/review-reprojection.ts, png-read.ts, review-sheet.py; validation/20-review-sheet.png, 20-reprojection.json; docs/review.md; reprojection test | `npm run check` 84/84; review sheet AI-reviewed; 0 repair cycles |
| D6 | 2026-09-30 | Sponsors dropped from the ice (assets/blender/drop_sponsors.py); the 17-20 renders, Remotion stills and review sheet regenerated; .blend1 backups untracked | `npm run check` 85/85; renders AI-reviewed; Remotion import checks PASS |
