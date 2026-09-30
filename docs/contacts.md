# Contact geometry: representative skater (iteration 10)

**CRITICAL CHECKPOINT.** The fixture axis position and the blade offset are **unmeasured**. A
correct-looking figure with a wrong pivot or blade offset produces wrong shots. Everything below the
inventory is **provisional debug geometry**, and nothing here is a measurement. AI review only.

| Item | Path |
| --- | --- |
| Script | `scripts/define-contacts.ts` (`npm run contacts:define`) |
| Numbers | `validation/10-contacts-report.json` |
| Review sheet | `validation/10-skater-contacts.svg` (`npm run render:contacts10`) |
| Data | `data/geometry.json` -> `figure_assets[fig.W-RD]`: `inventory`, `contact_shapes`, `note`; assumption `assume.debug_contacts.W-RD`; `players[W-RD].stick_handedness = left` |
| Tests | `tests/contacts.test.ts` |

## Representative figure

**W-RD, Finland no. 4.** Its slot is visible on *both* sides of the figure in the official overhead
(the end cap shows just behind the helmet). That confines the hidden fixture axis to a covered stretch
of about 134 px, **±12.1 mm** along the slot at the preview scale. No other skater gives a tighter
constraint. No loose-figure or scaled figure views exist.

## Inventory (in data)

| Item | Status | Evidence |
| --- | --- | --- |
| Fixture axis position | unknown | Only confined to the covered slot stretch; the lateral offset from the slot centreline is unknown. |
| Blade outline | unknown | The top view shows only the stick's projection. |
| Blade offset from pivot | unknown | Debug estimate: tip about 42.7 mm from the assumed pivot, on the left. |
| Stick side | traced | The figure faces +x and the stick extends to +y: the blade is on the figure's **left**. |
| Feet / skates | unknown | Hidden under the body from above; unscaled in the side views. |
| Contact heights, ice clearance | unknown | No scaled side view. |
| Figure height | catalog_nominal | Approx. 57 mm, datum unspecified. |
| Shared mold with other skaters | unknown | Not established. |

## Provisional debug contacts (`status: assumed`, `provisional: true`)

The inputs are operator-read overhead pixels (hands 2400,3250; stick tip 2393,3050; body axis
2330→2440 at y 3330), mapped through the ASSUMED preview scale into the pivot-local frame:
- **Pivot and heading:** the pivot is the midpoint of the covered stretch; the heading, 0.19°, comes from the body axis.
- **Blade:** a vertical strip along the last 30% of the stick's top-view projection, from the ice to 4 mm (assumed). It runs from local (3.4, 31.8) to (3.1, 42.6) mm, with uncertainty ±13 mm.
- **Shaft:** the top-view projection, rising linearly to 20 mm at the hands (assumed).
- **Skates:** placeholders 5 mm either side of the axis at ice level.

The tests show the contacts behave as a rigid part of the figure:
- pairwise distances are invariant under any pose;
- each point's radius from the axis and its height are preserved under rotation;
- the blade stays on the figure's left for both teams (det +1).

**Puck:** diameter approx. 25.4 mm (catalog nominal). The thickness is **not** established by any
photograph. The review sheet places the puck beside the blade purely for scale. There is no outgoing
velocity and no collision solver.

## What replaces this

Scaled photographs or measurements of a loose and an installed W-RD-type figure:
- fixture axis position relative to the slot, blade outline, lie, offset and height;
- skate contacts and ice clearance;
- whether the other skater positions share this mold.
