# Figures (iterations 13-15)

All figure geometry is **provisional**. AI review only; no personal user approval.

## Representative skater W-RD (Finland no. 4)

| Part | Asset | Evidence |
| --- | --- | --- |
| Blade, shaft, skates | `assets/figures/skater_W-RD_lower.*` (iteration 13) | Provisional debug contacts, docs/contacts.md |
| Whole rigid figure | `assets/figures/skater_W-RD.*` (iteration 14) | Body proxy plus the unchanged lower asset (vertex-identical, checked) |

### Iteration 14 body proxy

```sh
/root/venvs/blender/bin/python assets/blender/build_skater_body.py   # about 1 min
```

- **Construction.** Metaballs (ellipsoids and capsules) are merged into one smooth, moulded-looking mesh, joined with the lower asset into one rigid object `Skater.W-RD`. There is no armature. The origin is the fixture axis.
  - Calibration: at threshold 0.6 the surface lies at 0.575 × radius × size.
  - Blender clamps metaball resolution to ≥ 0.005 units, so the body is built in mm units at 0.25 mm and scaled by 0.001.
- **Layout.** Pivot-local mm, in `BALLS` / `CAPSULES` in the script. It is an operator interpretation of the only identified W-RD view, the official overhead (`trace.figure.W-RD.overhead.top_silhouette`, traced by hand because the white jersey and the ice are not separable by colour), plus generic STIGA skater proportions from the side and oblique photos, whose mold identity is **unverified**.
- **Checks** (`validation/14-skater-body-report.json`; thresholds set before building):
  - top-silhouette IoU **0.816** (≥ 0.75), at the overhead's 0.1796 mm/px (`validation/14-silhouette-top.png`: grey overlap, blue model only, red reference only);
  - height **56.8 mm** (catalog approx. 57 ± 10%, datum unknown);
  - body entirely above the ice; lower asset preserved.
- **First attempt** (repair cycle 1): the metaball sizes were wrong and the resolution was clamped. The result was disjoint blobs, IoU 0.40 and height 46 mm. It was fixed by the calibration above; the thresholds were not changed.
- **View sheet** `validation/14-view-sheet.png` (front, back, left, right, overhead). **Only the overhead has W-RD evidence.** The other four views are provisional.

Remaining defects (AI review):
1. The proxy is about 2–3 px larger than the traced top silhouette all round.
2. **Conflict:** the top silhouette shows the right leg reaching y ≈ −24 mm. The iteration-10 debug skate placeholders sit at ±5 mm, so the right placeholder is disconnected under the pelvis. The contacts were left unchanged (iteration 14 must preserve them); needs a measurement or a targeted correction.
3. No moulded detail (helmet shape, face, jersey/pants edges, number). It is a mass-and-pose proxy, **not the physical piece**.

### Mold sharing

- **Other skaters.** The side and oblique photos show Finland skaters with clearly different molded poses (deep crouch with the stick across, low stickhandling, skating stride). Jersey numbers are not consistent between photos.
- **Consequence.** W-RD's mold is **not** shown to be shared; each other outfield position needs its own variant. Until evidenced, iteration 16 must use distinct proxies marked as missing variants.
