# Slot tracks (iterations 06-08)

**Status:** provisional pixel traces, reviewed by AI only (no personal user approval). They show the
**visible slot centrelines**. The fixture-axis paths (`fixture_axis_path`) and the usable travel
stops (`usable_stops`) stay **unknown** until the rods are recorded.

| Item | Path |
| --- | --- |
| Seeds and identity evidence (operator input) | `data/slot-seeds.json` |
| Tracer | `scripts/trace-slots.ts` (`npm run trace:slots`, about 20 s), `src/model/slot-trace.ts`, `src/model/homography.ts` |
| Numbers | `validation/slots-report.json` |
| Overlays | `validation/06-straight-tracks.svg` (later: 07, 08) via `scripts/render-tracks-overlay.ts` |
| Canonical data | `data/geometry.json`: `image_traces` `trace.slot.<player>.<overhead|bare>`, landmarks `lm.slot.*`, `fixture_paths.*` |

## Teams and IDs

- **Team A = `W`:** defends `goal.W` at -x (image left) and attacks +x. It is Finland (white/blue) in the reference photos.
- **Team B = `E`:** defends `goal.E` at +x. It is Sweden (yellow/blue) in the reference photos.
- **Left and right** are seen by a player facing the goal they attack (docs/decisions.md D4). For W, left is +y (the image top); for E, left is -y (the image bottom).
- **Path IDs:** `path.<team>-<role>`, where the role is LD, RD, C, LW, RW or G.

## Slot identity (evidence, not mirroring)

Every slot in the official overhead has exactly one figure standing on it. The jersey colour of that
figure gives the team, and the slot's side gives left or right. Each path is traced separately from
its own seed in both photographs. The tests check that no path is a mirrored copy of the other
team's path.

| Path | Slot | Figure on it (overhead) |
| --- | --- | --- |
| W-LD | Upper long slot in the W half, curving down at its end near the centre line | Finland, at the curved end |
| W-RD | Lower straight slot in the W half | Finland, standing over the slot near its right end |
| W-C | Lower diagonal centre slot, through the grey centre disc into the E half | Finland, at the right end |
| E-LD | Lower long slot in the E half, curving at its start near the centre line | Sweden, at the curved start |
| E-RD | Upper straight slot in the E half | Sweden, at the left end |
| E-C | Upper diagonal centre slot, from the W half into the centre disc | Sweden, at the left end |

## Method

1. **Seed.** A few rough points per slot and image in `data/slot-seeds.json`, read from gridded views. The seed fixes identity and direction only.
2. **Cross-sections.** Taken every 8 px in the overhead and every 4 px in the bare sheet. Each one uses a slot signal: 255 - max(R,G,B) in the overhead (dark slots) and min(R,G,B) in the bare sheet (white cut-outs). The two edges are found at sub-pixel level (mid-level crossings) and give the centre and width.
3. **Three guide passes.** The later passes accept only sections close to the refined guide and within ±25% of the median width. Extensions restart from the seed ends, so the trace cannot run off onto printed white features.
4. **Gaps and ends.** Gaps (figures, puck, touching print) are interpolated and recorded as inferred segments. Ends are found at sub-pixel level along the end tangent.
5. **Homography.** A bare-to-overhead homography is fitted to all curves, starting from the ends visible in both images and refined by closest-point iterations. Points beyond an occluded end are ignored. It predicts the slot ends hidden under figures in the overhead (`assume.bare_sheet_same_slot_layout`).
6. **Curve representation.** A polyline through the smoothed centres at the section spacing. The fit error is the RMS and max distance of the raw section centres from it (`stats.fit_rms_px`, `fit_max_px`).

## Results, iteration 06

- **Slot width:** 39.4–40.3 px in the overhead and 15.6–17.0 px in the bare sheet.
- **Fit error:** RMS 0.05–0.62 px (overhead).
- **Bare-to-overhead homography:** curve RMS **2.43 px** overall, per slot 0.9–3.6 px.
- **Visible ends:** the two photographs agree within 8.5 px along the slot and 5 px across it.
- **Ends hidden under figures:** the bare sheet places the true end +11 to +89 px further on. The world centreline is extended to that prediction and the end is marked `assumed`.
- **Occlusions:**
  - the puck on W-C;
  - the black printed logo box that touches W-C and E-C inside the centre disc;
  - the white printed bands in the bare sheet that hide the W-C start and E-C end.
- **Limits:** each `visible_slot_limits` value is an arc length in overhead **pixels**. A mm centreline (`centreline`) exists only through the ASSUMED preview scale.
