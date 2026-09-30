# Iteration 05: provisional inner board boundary

**Status:** provisional trace, not calibrated; no millimetre accuracy is claimed. AI review under the user's delegation accepted it on 2026-09-30 (`docs/decisions.md` D1-D3). No personal user approval.

Evidence for the review decisions: `validation/05-evidence-check.json`, from `scripts/check-board-evidence.ts`.

| Item | Path |
| --- | --- |
| Overlay to review | `validation/05-board-overlay.svg` |
| Numbers | `validation/05-board-report.json` |
| Canonical data | `data/geometry.json` (geometry version 0.2.0) |
| Procedure | `scripts/trace-board.ts` (`npm run trace:board`) |
| Overlay renderer | `scripts/render-board-overlay.ts` (`npm run render:board`) |

## Source

- Photo: `stiga_se_fi_overhead` (`references/originals/stiga-sports-71-1145-01-overhead.jpg`), 5636 x 5636 px.
- The tracer checks the photo's SHA-256 before decoding it. The photo is only read.
- The overlay embeds the original JPEG bytes unchanged, at native size (1 SVG unit = 1 source pixel), so it is never stretched.
- This is the highest-resolution installed overhead available.
- The bare sheet (`stiga_ca_bare_ice_sheet`) was not used. Its perimeter may run under the boards.

## What was traced

- **Traced line:** the ice-contact edge of the installed boards. In this near-vertical view that is the innermost edge of the board band.
- **Board structure, from the ice outward:** white ice (often in shadow), then a near-black strip about 15 px wide (median), then the printed inner face of the boards, then the black top rail. At the ends, the translucent screens are outside that.
- **Assumption on the edge:** the trace follows the ice side of the near-black strip (`assume.board_edge_is_ice_contact`). The strip could be a base trim, a gap over the loose sheet, or a shadow.
- **Not traced:** the board top rail, the outer housing, and the loose-sheet perimeter (hidden under the boards).

## Method (all parameters are at the top of the script)

1. **Find the ice region.** Flood-fill it from a centre-ice seed pixel (2818, 1650). Pixels with max(R, G, B) < 90 act as barriers. The fill stays inside the boards: 10.96 Mpx, bounding box x 468–5176, y 1488–4107.
2. **Sample the edge.** Cast 1440 rays from the centre of the ice region. On each ray, locate the sub-pixel point where brightness crosses the midpoint between the ice level and the strip level.
3. **Quality check per sample.** The inside level must be at least 130 and at least 80 above the strip level. The rule is contrast, not "white", because the ice next to the boards is in shadow.
4. **Fit the outline.** Robust line fits for the 4 straight sides, then circle fits for the 4 corners.
5. **Reject outliers** using two tests:
   - the distance from the fitted model
   - a local test: a quadratic fitted to the 8 neighbouring rays on each side must match within 2 px
6. **Fill rejected rays.** Rejected rays are interpolated between the nearest accepted rays (`assume.board_occlusion_fill`). Every second ray is stored (720 points, 0.5 deg apart).
7. **Place landmarks** where the centre line, the blue lines and the goal lines meet the top and bottom boards. Each marking's centreline is extrapolated from 10 offsets, 15–60 px inside the boards. That gives 10 landmarks, `lm.board.*`.

**Result:** 1431 of 1440 rays detected and consistent. Two short stretches are interpolated:
- where the W blue line meets the top board
- two rays near the bottom-left corner joint

Running the script again reproduces byte-identical data, report and overlay.

## Evidence and checks (pixels)

| Check | Result | Reading |
| --- | --- | --- |
| Straight-side fit RMS | top 2.73, bottom 1.84, left 0.72, right 0.54 | The long sides are not straight (next row). |
| Side bow (quadratic sagitta) | top -10.1, bottom -6.6, left -2.3, right -1.7 (all bulge outward). Quadratic RMS at most 0.49. | Lens barrel distortion or physically bowed boards; the photo cannot separate them. The trace keeps the detected points, so the bow is preserved. |
| Corner radii | 610.5 / 624.2 / 613.0 / 624.6 (TL / TR / BR / BL). Circle RMS at most 0.70. | Corners are close to circular with near-equal radii. The arcs miss the lines by 1.6–6.3 px (tangency gap), so the corners are not exactly line-tangent circles. |
| Opposite sides parallel | top/bottom 0.22 deg, left/right 0.06 deg | Nearly perpendicular view. |
| Keystone | width 2603.8 / 2610.2 / 2616.6 at left / mid / right | About 0.5% scale change across the rink. |
| Centre line vs traced centre | -9.1 px along the long axis | Small offset. |
| Marking lean | on every marking line, the top end sits 14–17 px further toward -x than the bottom end (about 0.35 deg) | The same sign for W and E lines points to a slightly rotated printed sheet, not perspective. |
| Goal-line symmetry about the centre line | 15.9 px (top), 8.3 px (bottom) | Consistent with the keystone. |
| Aspect ratio | traced 1.8025 vs catalog 845/457 = 1.849 | The catalog "playing area" is not the traced rectangle at one scale (next section). |

**Error estimate:** trace uncertainty **21 px**, stored as `uncertainty_px`.
- Rule: ceil(median strip width + 2 x worst straight-side RMS).
- The strip width dominates, because the true contact line could lie anywhere across the strip.
- The uniform-scale mapping adds up to **16.5 px** of error, from the bow plus the keystone.

## Preview scale (ASSUMED)

- **Mapping:** `map.overhead.preview`, a similarity with one uniform scale.
- **Scale:** 0.179597 mm/px, taken from the catalog length of approx. 845 mm spread over the traced length of 4705.0 px (`assume.preview_scale_catalog_length`).
- **Placement:** origin at the traced boundary centre; +x along the fitted long axis toward the image right.
- **Implied width:** 468.8 mm, against the catalog's approx. 457 mm, a difference of 11.8 mm. This is reported, not forced away: x and y are never scaled separately.
- **Outline in mm:** `board.inner_boundary.world` is stored with status `assumed`. Corner radius and board length stay `unknown` in mm.
- **Plane correction:** no rectification (homography) was applied. Plane landmarks with known world positions do not exist yet, so mapping residuals cannot be computed.
- **Ice plane only:** the mapping must never be applied to board tops, screens, goals or figures.

## What replaces the assumptions

- A perpendicular overhead of the empty installed rink with scale markers in both directions. That enables a homography with landmark residuals and separates lens bow from board bow.
- A measured inner length and width.
- A close-up of the board base.
