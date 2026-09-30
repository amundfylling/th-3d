# Model review and calibration checkpoint (iteration 20)

**Status: illustrative prototype with provisional geometry.** This is an AI review. **Your personal
visual approval has not been received** and is not recorded anywhere. Unknown dimensions are not marked
as verified.

Main artifact: `validation/20-review-sheet.png`. Reprojection numbers: `validation/20-reprojection.json`.

## Calibration intake (2026-09-30)

No measurements, scaled photographs or mechanism recordings have been supplied, so no canonical parameter
changed. The existing checks were re-run on the current state (`npm run check`: validation plus all tests,
including the pose, contact and assembly tests).

## Four separate statuses

| Area | Status | Evidence |
| --- | --- | --- |
| **Implementation completeness** | Iterations 01–20 implemented. | Canonical data, pose maths, rink, goals, puck, one skater (W-RD) and one goalie (W-G) proxy, full static assembly, materials, Remotion static integration. 10 of 12 figures are **placeholders** (missing mold variants). Boards artwork is a placeholder. There are no rods or handles. |
| **Geometric evidence** | **Traced / assumed, not measured.** | Slots, boards, goal regions and markings are traced from one PDF photo (fit RMS ≤ 0.7 px, trace uncertainty 21 px ≈ 3.8 mm). The scale is the **assumed** catalog length of approx. 845 mm; the implied width is 468.8 mm against the catalog's approx. 457 mm, which is unresolved. The housing-length conflict (960 vs 940 mm) is unresolved. The pipeline reprojection is consistent to ≤ 1.7 output px (mean, slots) and 0.75 px (median, ice edge). |
| **Physical-mechanism evidence** | **None.** | Fixture-axis positions, blade and skate contacts, puck thickness, goal opening, travel stops, rotation limits, the rod-to-figure transfer and link 7A are all unknown or debug placeholders. No recording exists. |
| **Visual review** | AI review only. | Iteration sheets 05–19 and this sheet. User approval: **not received**. |

## Geometry vs appearance (reported separately)

**Geometry**
- **Matched overhead** (same world window, orthographic): the Blender and Remotion renders place markings, slots, goals and logos where the reference shows them.
- **Reprojection:** canonical data → Blender → GLB → Remotion.
  - Slots: centreline mean offset ≤ 1.7 px at 0.485 mm/px. The maximum offsets of 7–11 px occur only where a figure or the puck covers the slot.
  - Ice edge: median offset 0.75 px, 90th percentile 11 px (where boards or figures shade the edge).
  - This tests the pipeline, **not** physical accuracy.
- **Side and oblique:** the reference camera poses are unknown, so the projection is **not matched** and the comparison is qualitative. The layout, goal positions and team sides agree. The model's housing below the ice (53 mm, preview) looks shallower than the photo's printed housing, and the rods, handles and legs are absent.

**Appearance**
- **Cycles:** soft shadows, clear screens and printed ice read well at 1920 × 1080.
- **Remotion/Three:** the same layout and colours, but no shadows, opaque white end screens and flatter ice.
- **Both:** smooth proxy figures, placeholder boards, no decals, and photo lighting baked into the ice texture.

## Output resolution and the one-pixel question

- **Proposed output:** 1920 × 1080. Full-rink overhead: 1 px ≈ 0.485 mm. Oblique: ≈ 0.6–1.2 mm per px across the rink.
- **One output pixel is NOT supported** for physical geometry. The absolute error is dominated by:
  - the assumed scale (the width already disagrees with the catalog by 11.8 mm);
  - a trace uncertainty of about 3.8 mm;
  - lens bow of up to about 3 mm;
  - unmeasured pivots and blades, which could be off by 10–20 mm (the covered-slot stretch: ±12 mm for W-RD, ±20 mm for W-G).
- **Supported claim:** the model is self-consistent to about 1–2 output pixels between data and render.

## Renderer decision (not switched)

Remotion/Three in the current setup does **not** reach the photorealism of the reference photos: no
shadows, no transmission, SwiftShader on the CPU. Cycles already looks better on the same geometry.
Before choosing the final route, run this **bounded Cycles benchmark task** (it follows the "Optional
Blender Cycles quality benchmark" prompt; not started):

1. **Scene:** `assets/scene/full_static_appearance.blend`, unchanged.
2. **Renders:** two stills at 1920 × 1080, with documented samples, seed and light:
   - the Remotion oblique camera (`remotion/cameras.ts`);
   - one blade/puck close-up.
3. **Remotion counterparts:** the same two views with shadow maps enabled and a physical transmission material for the screens.
4. **Compare** four named defects only: ice shading, screen transparency, contact shadows, figure detail. Report render time per frame for each route.
5. **Recommend** the final renderer from those stills. Do not build animation.

## The few inputs still required for an exact model

1. **Empty installed rink, perpendicular overhead, with scale markers in both directions.** This yields the real scale (replacing the 845 mm assumption), the lens and keystone correction, slot ends and the board line.
2. **Loose and installed figures with a scale** (at least W-RD-type and goalie; ideally one of each distinct mold):
   - fixture-axis position relative to the slot;
   - blade outline, lie, offset and height;
   - skate contacts and ice clearance;
   - which positions share a mold.
3. **Rod travel recordings for each control type:** push/pull and twist to the stops, including the left-wing link 7A. This gives the usable stops, rotation limits and transfer.
4. **Caliper measurements:** puck thickness and rim; goal opening width and height and post diameter; board height; slot width at the surface.
5. **Your actual teams and artwork.** The goal setup is known: without inserts.

Iteration 21 (the first shot) additionally needs your review feedback and a real high-frame-rate shot recording.
