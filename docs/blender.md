# Blender route (iterations 11-18)

## Environment

- **Blender** 4.5.14 LTS, as the PyPI module `bpy`, in `/root/venvs/blender` (Python 3.11.15).
  - It is not a desktop install: blender.org download hosts are blocked by the network policy.
  - Extra packages in the venv: `shapely` 2.1.2, `mapbox_earcut`, `numpy<2` (1.26.4, required by bpy 4.5), `pillow`, `opencv-python-headless<4.11` (4.10.0).
- **Setup** in a fresh container:
  ```sh
  python3 -m venv /root/venvs/blender
  /root/venvs/blender/bin/pip install "bpy==4.5.*" shapely mapbox_earcut "numpy<2" pillow "opencv-python-headless<4.11"
  ```
- **Rendering:** Cycles on the CPU (4 cores), fixed seed, OpenImageDenoise. There is no GPU. EEVEE is not used.

## Rink (iteration 11)

```sh
/root/venvs/blender/bin/python assets/blender/build_rink.py   # about 1.5 min: .blend, .glb, 3 stills, report
/root/venvs/blender/bin/python assets/blender/verify_rink.py  # scale check on the unlit ID render
```

| Output | Content |
| --- | --- |
| `assets/rink/rink.blend` | Editable scene: Ice, InnerBoards, HousingBase, HousingRim; clay materials; cameras OverheadOrtho and SideOblique; a sun. |
| `assets/rink/rink.glb` | The same four meshes, exported with +Y up. |
| `validation/11-rink-overhead.png`, `11-rink-side.png` | Lit clay review stills. |
| `validation/11-rink-overhead-id.png` | Unlit ID render (ice white, boards red, housing blue, holes black), used for measurement. |
| `validation/11-rink-report.json`, `11-rink-verify.json` | Build parameters and scale checks. |

## Units and axes (converted once)

- **Units.** `stiga_blender.m()` is the only mm-to-m conversion. The Blender scene is in metres with the world axes unchanged (x toward goal.E, y toward the overhead's image top, z up).
- **Axes.** The glTF exporter's +Y-up option does the single axis conversion (x, y, z) → (x, z, −y). The tests read the GLB accessor bounds and compare them with `worldMmToGltfM` of the canonical boundary. The nodes carry no rotation and no scale.

## Geometry sources

| Part | Source | Status |
| --- | --- | --- |
| Ice outline | `board.inner_boundary.world` (traced shape, ASSUMED preview scale) | assumed |
| Slots (12 holes) | `fixture_paths.*.centreline`, buffered by the traced slot width (6.8–7.2 mm at the preview scale), round caps | assumed |
| Goal cut-outs (2 holes) | `trace.goal.*.cutout.overhead` mapped to world | assumed |
| Board height 30, wall 9, ice sheet 1.5, housing margin 16, depth below ice 53 mm | `preview_parameters` (evidence notes in the data) | assumed; physical values unknown |

The implied housing is 877 × 502 mm. The width lies within the two agreeing catalog width claims
(500 and approx. 502 mm). The length is **not** fitted to the conflicting 960 / approx. 940 mm claims:
the real ends (rod mechanisms, handles) extend further than this preview. Legs, rods, handles, screens
and goals are not in this asset.

## Scale checks (iteration 11)

- **GLB:** the ice extent equals the canonical boundary within 0.1 mm; ice top at Y = 0; board top at the preview height.
- **Unlit orthographic render** (0.507 mm/px): the ice extent matches the data within **0.2 mm** (tolerance 2 px = 1.0 mm). 100% of the sampled centreline points of all 12 slots fall on hole pixels.
- **Corrected check:** a first version measured the lit still. Board shadows darken the ice edge there, so that check was invalid. It was replaced by the unlit ID render; the tolerance was not relaxed.

## Goal, end screen, puck (iteration 12)

```sh
/root/venvs/blender/bin/python assets/blender/build_hardware.py   # about 4.5 min, 4 Cycles renders
```

| Asset | Origin and axes | Geometry source |
| --- | --- | --- |
| `assets/goal/goal.blend/.glb` | Mouth centre on the ice (goal line, z 0). +x out of the goal into the rink, +z up. | Mouth width 88.8 mm: the mean of the post-top spacings, W 90.6 / E 86.9 mm (elevated points, preview scale). Depth 51.6 mm from the elevated cage outlines. Height 50, post radius 1.5, bar radius 0.9 mm, top at 0.6 of the depth: `preview_parameters`. Configuration: no insert, no goal cup (user D5). |
| `assets/screen/end_screen.blend/.glb` | End-centre of the W end, on the ice, outside the boards. | Follows the board outline, offset by wall + ½ screen thickness. Catalog approx. 622 mm treated as the developed length (datum unknown) and approx. 70 mm height. Thickness 2 mm (preview). |
| `assets/puck/puck.blend/.glb` | Bottom centre (ice contact), +z up. | Diameter approx. 25.4 mm (catalog nominal). Thickness 12 mm and edge radius 2 mm are preview values (evidence note in the data). |
| `assets/scene/static_hardware.blend/.glb` | World | The rink, plus goals at the traced goal-line centres (W, and E rotated 180°), screens at both ends (E by rotation; it sits 2.6 mm from the E board face), and the puck at its reference-photo position on the W-C slot. |

Stills: `validation/12-goal-oblique.png`, `12-puck-side.png`, `12-overview.png`. Numbers:
`validation/12-hardware-report.json`. The tests check the asset origins and dimensions, and that the
rink meshes in the assembled scene are unchanged.

Known cosmetic defect: a small shading notch where the crossbar meets the +y post.

### Unresolved clearances that affect contact accuracy

1. **Puck thickness and rim profile.** They set the contact height on the blade and whether the puck rides over a slot edge. Preview 12 mm, unknown.
2. **Blade height and bottom above the ice** (iteration 10 unknowns). Together with the puck thickness they decide whether a blade can reach under or over the puck.
3. **Goal opening height and width at ice level, post diameter, crossbar height.** They decide what counts as a goal and where the puck bounces off the frame. The mouth width comes from elevated post tops only.
4. **Goal position relative to the goal line and cut-out at ice level.** Only elevated features were traced.
5. **Slot width and edge profile at the ice surface.** The width comes from the overhead at the preview scale (6.8–7.2 mm). The puck can catch in a slot or be deflected by it.
6. **Ice-sheet step at the board base and screen gaps.** They affect rebounds along the boards and ends.
7. **Board height and wall thickness** (preview 30 / 9 mm). They set rebound heights and whether the puck can leave the rink.

## Representative skater, lower part (iteration 13)

```sh
/root/venvs/blender/bin/python assets/blender/build_skater_lower.py   # about 1.5 min
```

- **Output:** `assets/figures/skater_W-RD_lower.blend/.glb`. It is **one rigid object**, `SkaterLower.W-RD`, with no skeleton and no separate stick.
- **Origin:** the fixture axis at the ice plane (preview origin height 0). +x is the figure's heading and +y its left.
- **Built from** `figure_assets[fig.W-RD].contact_shapes`, which are PROVISIONAL debug geometry (`assume.debug_contacts.W-RD`):
  - blade: 1.2 mm thick, thickened toward the figure so the stored outer face is on the surface;
  - shaft: 64-sided rod, radius 1.3 mm, starting where the stored line reaches z = r so it does not cut the ice;
  - skates: 2.5 × 3 mm blocks.
  The build sizes are in `preview_parameters`.
- **Check** (`validation/13-skater-lower-report.json`): BVH distance from the stored contact polylines to the mesh is at most 0.0016 mm (tolerance 0.01), and nothing is below the ice.
  - The first run failed: the shaft had 0.025 mm facet error with 16 sides, and the rod dipped 1 mm under the ice. Both were fixed in the build; the tolerance was not changed.
- **Stills:** `validation/13-contacts-top.png` and `13-contacts-side.png` (side seen from behind the figure). They show the pivot axes (red +x, green +y, black z), orange contact outlines, and the puck on the blade's forward face.
- **Visible limitation:** the debug blade is 4 mm high against a 12 mm preview puck. Both are unmeasured.
