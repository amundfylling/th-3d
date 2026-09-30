# Geometry contract

Canonical data: `data/geometry.json`. Schema: `src/model/geometry.ts` (types) and
`src/model/geometry-schema.ts` (runtime schema). `tsc` checks that the two describe the same
structure. Evidence policy: `src/model/validate.ts`. Run `npm run validate`, or `npm run check`
for typecheck, validation and policy tests together.

`geometry_version` follows semver. Bump the minor version when geometry values change or the
structure is extended compatibly (0.3.0 added the `user_statement` source kind). Bump the major
version for breaking structural changes. Later motion traces must record the version they were
fitted against.

## Coordinate system

| Frame | Definition |
| --- | --- |
| World | Right-handed, millimetres. Origin at the centre of the inner board boundary, on the top surface of the ice (z = 0). +x along the long axis toward `goal.E` (image-right in `stiga_se_fi_overhead`). +y toward the image-top long side of that photo. +z up. |
| Angles | Degrees in data. Positive is counter-clockwise about +z, seen from above. 0 deg faces +x. |
| Image pixels | Per source image: u right, v down, origin at the top-left corner. Pixel (i, j) covers [i, i+1) x [j, j+1). Every pixel trace names its `source_image_id`, and that image's SHA-256 is pinned in `source_images`. |
| Pivot-local | Per figure asset. Origin where the fixture rotation axis meets the ice plane. +z along the fixture axis. +x toward the blade at rotation 0. Contact shapes live here. The axis itself is still unknown. |

The origin is defined through the inner board boundary. Until that boundary is measured, the
origin is only as good as its trace. Whether the centre red line passes through it is a check,
not an assumption.

## Teams, players and IDs

- Teams are named by side, not by nation. `W` defends `goal.W` at -x and attacks +x. `E` defends
  `goal.E` at +x. In the public reference variant, Finland is W and Sweden is E. The user's
  teams replace this.
- Positions are G, LD, RD, C, LW and RW. Left and right are seen by a player facing the goal they
  attack, so for W, left is +y and for E, left is -y. This convention still has to be checked
  against the rod labelling on the user's table. The user asked only that it be applied consistently
  (docs/decisions.md D4).
- IDs are stable: player `W-LD`, fixture path `path.W-LD`, figure asset `fig.W-LD`, goals
  `goal.W`/`goal.E`, screens `screen.W`/`screen.E`, markings such as `blue_line.E` and
  `faceoff_circle.W.pos_y`.
- Assets are per player. `mold_group` stays null until shared molds are evidenced.

## Evidence policy (enforced by `npm run validate`)

1. Every quantity has a `unit`, a `status` (`measured`, `catalog_nominal`, `traced`, `assumed` or
   `unknown`) and `source_ids`. A setup choice stated by the user (for example the goal setup) cites a
   `user_statement` source. That is not a measurement.
2. `status: "unknown"` if and only if `value` is null. Absent dimensions stay null.
3. `uncertainty` is null when not stated. Zero or negative is rejected.
4. `measured` requires a `user_measurement` source. `catalog_nominal` requires a catalog or
   document source. `assumed` requires an `assumption_id` that exists in `assumptions`, with its
   reason and what should replace it.
5. Conflicting claims (for example 960 vs approx. 940 mm overall length) are stored as separate
   `dimension_claims` plus a `conflicts` entry. A conflict can only be resolved by citing a
   `user_measurement`. Averaging or picking one is invalid.
6. Pixel traces never count as millimetres. World coordinates from a photo come only through an
   `image_to_world` mapping on the ice plane (`ice_top_z0`). A world polyline cannot claim a
   stronger status than the mapping that produced it.
7. A preview scale is an `assumed` `similarity` mapping with one uniform scale; the validator
   rejects separate x/y scaling. It is replaceable by swapping the mapping and its assumption.
   It must never be applied to elevated objects such as figures, board tops or screens.
8. References are pinned. Each `source_images` entry must match `references/index.json` and the
   file's actual SHA-256.

## Current image-to-world mappings

- `map.overhead.preview` (iteration 05): an ASSUMED uniform-scale similarity for `stiga_se_fi_overhead`,
  with the scale taken from the catalog length of approx. 845 mm. It is for previews only. See `docs/board-trace.md`.

## Coordinate adapter: world to Blender, glTF and Three.js

Convert units and axes once, at the export boundary. Never convert per object or per frame.

| Target | Units | Up | Mapping from world (x, y, z) in mm |
| --- | --- | --- | --- |
| Canonical data | mm | +z | (x, y, z) |
| Blender scene | m (unit scale 1.0) | +Z | (x, y, z) / 1000. Same axes, only a unit change. |
| glTF 2.0 file | m | +Y | (x, z, -y) / 1000 |
| Three.js / Remotion ThreeCanvas | m | +Y | Same as glTF. Loaded glTF needs no further rotation. |

- Blender's glTF exporter with "+Y Up" enabled performs the (x, y, z) -> (x, z, -y) conversion.
  Model in Blender using world axes and let the exporter do that one conversion.
- Rotations about world +z become rotations about Three.js +Y with the same sign. Degrees in data
  become radians only inside code.
- Handedness is preserved: all three frames are right-handed. The conversion is a rotation plus
  a unit scale, never a mirror.
- The adapter is documentation only for now. It gets implemented and tested together with the
  fixture-pose functions (iteration 09) and the Blender export (iteration 11).
