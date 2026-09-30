# Blender route (iterations 11-18)

## Environment

- **Blender** 4.5.14 LTS, as the PyPI module `bpy`, in `/root/venvs/blender` (Python 3.11.15).
  - It is not a desktop install: blender.org download hosts are blocked by the network policy.
  - Extra packages in the venv: `shapely` 2.1.2, `mapbox_earcut`, `numpy`, `pillow`.
- **Setup** in a fresh container:
  ```sh
  python3 -m venv /root/venvs/blender
  /root/venvs/blender/bin/pip install "bpy==4.5.*" shapely mapbox_earcut numpy pillow
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
