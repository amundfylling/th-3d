# Fixture-pose mathematics (iteration 09)

Pure, renderer-independent functions: `src/model/pose.ts`, `src/model/paths.ts` and
`src/model/coordinates.ts`. Tests: `tests/pose.test.ts`. Debug view: `validation/09-pose-debug.svg`
(`npm run render:pose09`). AI review only.

## State

| Field | Meaning |
| --- | --- |
| `u_preview` in [0, 1] | **Normalised arc-length preview parameter** along the path's visible slot centreline (0 = start end, 1 = end end). It is **not** rod displacement and **not** a physical travel stop. The rod-to-path mapping and the stops are unknown (docs/tracks.md). |
| `thetaDeg` | **Continuous** rotation about the fixture axis relative to the team's home heading, in degrees, never wrapped (361 stays 361). `unwrapDeg` keeps sampled sequences continuous. **Not coupled to the slot tangent.** A coupling needs a measured transfer function. |

## Pose

- `skaterPose(path, team, state, opts)` and `goaliePose(...)` are separate adapters. Each rejects the other's path kind.
- **Pivot.** The fixture axis sits at the path point, plus an optional `fixtureOffsetMm` [along, left], at height `originHeightMm`. Without an offset, the pose reports the preview assumption `assume.fixture_axis_on_slot_centreline` (also in `data/geometry.json`).
- **Heading.** `HOME_HEADING_DEG[team] + thetaDeg`: W = 0°, E = 180°. The opposing team is placed by a **proper rotation**. The linear part always has determinant +1, which the tests check. There is never a negative-scale mirror, so stick handedness is preserved.
- **Transform.** `matrix` maps pivot-local points (+x = figure heading, +y = figure's left, +z = up the fixture axis) to world mm. `toWorld(pose, points)` applies it.
- **Invalid states are flagged, never clamped.** `{ ok: false, reason }` for: u outside [0, 1], NaN or infinite values, a skater/goalie path mismatch. `pathSampler` throws on degenerate paths.

## Coordinate adapter (implemented once)

`worldMmToGltfM`, `gltfMToWorldMm`, `worldMatrixToGltf`:

- Axes: world (x, y, z) mm maps to glTF/Three (x, z, −y) / 1000 m.
- Yaw: a rotation about world +z equals a rotation about glTF +Y with the same sign.
- Tested for basis vectors, round trip, transform commutation, the yaw sign and det +1.

## Assumptions still open

- **Paths.** Paths come from the visible slot centrelines at the ASSUMED preview scale. The fixture-axis path, fixture offsets, rotation limits, the rod mapping and the stops are unknown.
- **Goalies.** The goalie pose uses the same mathematics, in its own adapter. Goalie-specific constraints (rotation limits, pivot offset) will be added there when measured.
