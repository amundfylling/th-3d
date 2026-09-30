# Project state

## Current position

- Last completed iteration: **05 - Trace only the installed board boundary** (2026-09-30), plus the post-05
  decisions of the same day (docs/decisions.md D1-D5). The user delegated the board-trace review to the AI.
  AI review accepted the trace from recorded evidence. No personal user approval is claimed.
- Batch run (docs/autonomous-run.md) in progress. Last completed: **06 - Trace the defenders and centres**. Next: **07**.
- Geometry version: `0.4.0` (`data/geometry.json`). Board boundary and 6 defender/centre slots traced in pixels;
  goal setup = without inserts (user). No meshes or movement.
- Code, 3D assets, animations: none. No animated shots exist or are planned before iteration 23.

## Active iteration (batch run, docs/autonomous-run.md)

**07 - Trace the four winger paths.** Repair count: 0/3. (Checklist written when started.)

Iteration 06 closed with 2 repair cycles (tracer ran into white print in the bare sheet; one
wrong occlusion hint). All acceptance items passed:
- [x] 6 paths traced independently in both photographs; test proves no mirrored copies.
- [x] Team A = W (Finland in the reference), team B = E; IDs `path.<team>-<role>`.
- [x] Centreline points, polyline representation, fit error, end landmarks with visibility, inferred segments, provenance in data/geometry.json.
- [x] `fixture_axis_path` null (new field; validator only accepts a measured one), `usable_stops` unknown; visible limits in image px.
- [x] `npm run check` 20/20.
- [x] AI review of validation/06-straight-tracks.svg: every trace on its slot, diagonal centre routes kept, visible ends on slot caps, hidden ends marked with bare-sheet predictions.
- [x] Identity from the figure on each slot; homography RMS 2.43 px; visible-end agreement <= 8.5 px.

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
| Slot traces (iteration 06) | 6 paths x 2 photos. Overhead fit RMS 0.05-0.62 px, width 39-40 px; bare->overhead homography curve RMS 2.43 px; visible ends agree <= 8.5 px. Overlay rendered and AI-reviewed (all ends inset). 20/20 tests incl. identity and no-mirror checks. |
| Blender | bpy 4.5.14 LTS installed from PyPI in /root/venvs/blender (python 3.11); not yet used. |
| Dimensional accuracy | Nothing measured. All sizes are `catalog_nominal`, `assumed` (preview scale) or `unknown`. |

## Key decisions

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
2. Loose and installed figures with scale: fixture pivot, blade offset/profile, stick handedness,
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
