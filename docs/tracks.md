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

## Results, iteration 06 (first run, superseded by the table below)

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

## Winger identity (iteration 07)

| Path | Slot | Figure on it (overhead) |
| --- | --- | --- |
| W-LW | Upper slot from the centre region along the top, around the top-right corner and down behind the E goal | Finland no. 26, on its lower end behind the E goal |
| W-RW | Lower slot from the centre region along the bottom, curving up into the bottom-right corner | Finland, at the curved right end |
| E-LW | Lower slot running down behind the W goal, around the bottom-left corner and along the bottom | Sweden no. 92 beside its top end; the stick crosses the slot |
| E-RW | Upper slot from the W corner (curve at the top-left) along the top | Sweden, at the curved left end |

The two left-wing rods (W-LW, E-LW) carry link 7A in the manual (7111-9073-01). What it does to the
figure's motion is unknown.

## Current results: all 10 outfield slots (after iteration 07)

Tracer changes in iteration 07. They apply to all slots, and 06 was re-traced and re-reviewed:
- **Edge scan:** outward from the core, bridging short light reflection streaks inside a dark slot (W-RW, E-RW).
- **Lateral-consistency filter from the second pass:** a quadratic fit of the neighbours' offsets, which rejects sections that jump onto a figure standing over a slot.
- **Gap filling:** interpolates the sideways offset along the guide, so curves are kept across gaps.
- **Bare-sheet seeds:** the curve seeds for W-LW, E-LW and W-RW were replaced by measured white-run centres; the ones I first read off the grid were 20–50 px out.

Curve representation: a polyline at an 8 px spacing in the overhead and 4 px in the bare sheet. That
is about 45 points per quarter circle on the corner curves (radius about 300–450 px). The fit error
is the distance of the raw section centres from the stored polyline.

| Path | Overhead length px | Width px | Fit RMS / max px | Detected | Bare->overhead residual RMS / max px |
| --- | --- | --- | --- | --- | --- |
| W-LD | 2319.6 | 39.39 | 0.09 / 0.57 | 100% | 3.47 / 6.18 |
| W-RD | 1320.2 | 40.27 | 0.05 / 0.23 | 90% | 0.86 / 1.83 |
| W-C | 1374.8 | 39.83 | 0.1 / 0.76 | 84% | 2.15 / 6.72 |
| E-LD | 2388.3 | 40 | 0.26 / 2.6 | 97% | 2.4 / 23.35 |
| E-RD | 1330.4 | 39.39 | 0.06 / 0.33 | 93% | 2.22 / 3.61 |
| E-C | 1293.9 | 39.38 | 0.12 / 0.66 | 99% | 2.18 / 4.37 |
| E-RW | 2430.3 | 38.94 | 0.25 / 1.73 | 93% | 4.11 / 11.41 |
| W-LW | 2664.6 | 38.19 | 0.32 / 2.62 | 99% | 2.69 / 5.59 |
| E-LW | 2743.2 | 38.27 | 0.31 / 2.41 | 96% | 1.34 / 4.41 |
| W-RW | 2401.2 | 39.18 | 0.2 / 1.89 | 95% | 2.73 / 6.27 |

Bare-to-overhead homography over all 10 curves: RMS **2.689 px**.

| End | Overhead | Bare-predicted along (px) | Across (px) |
| --- | --- | --- | --- |
| W-LD start | visible | -2.9 | 6.1 |
| W-LD end | hidden: Finland figure | 94.2 | 9.6 |
| W-RD start | visible | 14 | 1.6 |
| W-RD end | visible | -2.2 | -0.2 |
| W-C end | hidden: Finland figure | 18.5 | -6.6 |
| E-LD start | hidden: Sweden figure | 23.9 | -42.9 |
| E-LD end | visible | 1.6 | 1.3 |
| E-RD start | hidden: Sweden figure | -1.1 | -1.4 |
| E-RD end | visible | 17.4 | -3.7 |
| E-C start | hidden: Sweden figure | 96.8 | 0 |
| E-RW start | hidden: Sweden figure | 70.4 | -2.9 |
| E-RW end | visible | -7.5 | 3.7 |
| W-LW start | visible | -0.1 | -1.5 |
| W-LW end | hidden: Finland figure no. 26 | 90.7 | 0.4 |
| E-LW start | visible | -0.6 | 6.6 |
| E-LW end | visible | 0.3 | 0.8 |
| W-RW start | visible | -6.1 | 0.1 |
| W-RW end | hidden: Finland figure | 120.2 | -19.8 |

Reading the table:
- For **visible ends**, the along/across values measure the disagreement between the two photographs. They stay within 17 px.
- For **hidden ends**, the along value is how much further the slot runs under the figure.
- **Explicit difference:** at the curved E-LD start under the Sweden figure, the two photographs disagree by up to 23 px, and the predicted hidden end sits 43 px across the slot. That end position is therefore uncertain by that much.

## Where usable travel still needs a hardware recording

None of the ten `usable_stops` can come from photographs. Each needs a push/pull recording of its rod
to the physical stops. The most important:
1. **Ends hidden under figures** in the reference photo: W-LD end, W-C end, E-LD start, E-RD start, E-C start, E-RW start, W-LW end (behind the E goal), W-RW end. The slot end is only predicted, and a stop may sit short of the slot end.
2. **Behind-goal and corner sections** of W-LW and E-LW, and the corner curves of E-RW and W-RW. The relation between rod displacement and position along a curve is not linear arc length, and the left-wing link 7A may change it.
3. **Figure rotation along every path:** twist-to-rotation transfer, rotation limits and backlash. Rotation is not assumed to follow the slot tangent.
4. **Where the figures stand relative to the slot:** in the overhead, several figures stand beside their slot (for example Sweden no. 92 about 80 px to the left of E-LW). The fixture axis may therefore be offset from the slot centreline (`fixture_axis_path` stays unknown).

## Track fix: sticks lying on the E-RW and W-RW slots (2026-10-01)

User review of the Remotion overhead marked two irregularities: a bump in E-RW over the top of the W-zone
face-off circle and a dip in W-RW over the bottom of the E-zone face-off circle. In the official overhead a
skater's metal stick lies along the slot at both places (dark wire with a bright highlight, crossing the slot
at a shallow angle); the tracer had followed it. The bare sheet (no figures) shows both stretches straight
within its own resolution (deviation <= 0.46 mm after mapping), so the layout itself is straight there.

Fix (at the source, not in the output):
- `data/slot-seeds.json`: `occluded_boxes_overhead` per path - operator-marked overhead pixel boxes where an
  object lies on the slot (E-RW px 1545-1830, W-RW px 3640-4045, with reasons).
- `src/model/slot-trace.ts`: sections whose guide point falls inside a box are never measured; they are
  bridged by the existing Hermite gap interpolation from the accepted sections on both sides, and do not count
  toward the 400 px gap limit (a long stick would otherwise end the visible trace early). They are listed as
  `inferred_segments` with the reason.

Result (`validation/track-fix-report.json`, `validation/track-fix-compare.png`): deviation from a straight line
over x -300..-100 mm (E-RW) / 100..300 mm (W-RW): E-RW max 2.03 -> 0.14 mm, W-RW max 0.60 -> 0.12 mm. Slot
width and curved sections unchanged; all other paths moved <= 0.03 mm (bare->overhead homography refit,
curve RMS 2.49 -> 2.41 px). W-RW's last visible cross-section under the end figure moved 14 px, changing
one point at the join to the predicted hidden end by 0.64 mm (the curve is otherwise unchanged within 0.08 mm).
