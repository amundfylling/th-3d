# Skater from the Thingiverse STL (2026-10-12, PROPOSED)

User request (2026-10-12): use the STL files of a STIGA table-hockey player that the user found on Thingiverse to make
the skater in the 3D model as accurate as possible.

Source: `references/models/thingiverse-6898521/STIGA HOCKEY PLAYER - 6898521.zip` (index id
`thingiverse_6898521_stiga_hockey_player`). "STIGA HOCKEY PLAYER" by **MAVRIS**, https://www.thingiverse.com/thing:6898521,
licence **CC BY-SA**. The zip holds a body STL (19 854 triangles, one closed watertight shell, 56.85 mm tall in file
units) and a separate round printable stick. The derived assets `assets/figures/skater_stl_*` are under the same licence
and must keep this attribution.

**Status: PROPOSED, and in use since 2026-10-12** (user: "Switch now"). The skater assets
`assets/figures/skater_{SWE,FIN}.glb`, the contact shapes in `data/geometry.json`, `data/figures/contact-footprints.json`, the
traces and the videos use the STL body (section "Switch" below). The comparison assets `assets/figures/skater_stl_*` and
`validation/players/stl/` stay as the record of the side-by-side check. AI review only.

## Result

| Check (same procedure for both shapes) | Parametric mold | STL body |
| --- | --- | --- |
| Turntable silhouettes, 8 fitting views (`skater-fit.json`) | mean IoU 0.819 | **0.932** |
| 11 former held-out views (`skater-heldout-fit.json`) | 0.807 | **0.922** |
| 4 regression-reference views (`skater-independent-fit.json`) | 0.805 | **0.904** |
| Official overhead, 4 Sweden skaters (`overhead-fit.json`) | mean 0.773 at k 1.0814 | 0.778 at k **1.2027** |

The STL is the same mold as the user's skater no. 21 (same pose, left shot, left boot on the socket, right leg pushed
back) and fits every turntable view better; the gain is largest on the side views (t03.00: 0.72 -> 0.92, t08.50: 0.78 ->
0.95). Cameras are refitted per shape from the stored ones (`--reuse`), the metal stick is excluded from the masks as
before. Main artifacts: `validation/players/stl/figures-vs-photos.png` (camera-matched Cycles renders beside the photos),
`validation/players/stl/figures-views.png` (rows: parametric Sweden, STL Sweden, STL Finland).

## Size (user decision 2026-10-12)

The user chose the STL file's own size: **56.85 mm** tall (ice to helmet top), file mm = asset mm (k = 1.19154 mm per
mold unit). It is not a ruler measurement of the user's skater. Checks: the overhead fit rerun with the STL shape gives
57.4 mm (k 1.2027, ASSUMED preview scale; the same fit gave 51.1 mm with the parametric mold), the catalog says approx.
57 mm; the measured goalie is 54 mm.

## Method (`npm run players:stl`)

1. `scripts/stl-skater.py align`: axis = centre of the STL's round base disc (the mount socket), underside -> z = 0;
   uniform scale and yaw fitted to the parametric mold (yaw 30.0 deg; residual median 0.85 mold units) so mold units, the
   fitted photo cameras and the back-print projector keep their meaning. -> `data/figures/skater-stl.json` (alignment),
   `out/figures/skater-stl.npz`.
2. `scripts/fit-figure-views.py skater --mesh out/figures/skater-stl.npz --out validation/players/stl` (fitting,
   `--heldout`, `--independent`), and `scripts/fit-figure-overhead.py --mesh-dir <dir with the STL npz as skater.npz>
   --out validation/players/stl` (new `--out` option; default unchanged).
3. `scripts/stl-skater.py finish`: scale = the STL file's size (the overhead fit is kept as a check); the wire stick keeps the traced blade in **mm**
   (heel (3.24, 22.71), toe (2.38, 43.47), height 3.24 mm, the same as the contact blade in data/geometry.json; the overhead
   rerun reads heel 22.5 mm lateral, blade 19.5 mm), the shaft top stays in the upper glove; a metal runner under the
   STL's right boot (the boot floats about one runner height above the ice).
4. `scripts/stl-skater.py paint`: colour regions (kit / blue / skin) per triangle of the once-subdivided body (79 416
   triangles), voted from 21 turntable frames at the cameras fitted to the STL (camera IoU >= 0.85; painter's z-buffer;
   weight = facing; skin only above z = 36 mold units), unseen triangles filled from neighbours, 20 smoothing passes ->
   `data/figures/skater-stl-paint.json`, `validation/players/stl/paint-check.png`.
5. `assets/blender/build_skater_stl.py`: Sweden/Finland materials and back prints as build_figures.py ->
   `assets/figures/skater_stl_{SWE,FIN}.blend|.glb` (79.5k triangles), `validation/players/stl/figures-report.json`.

## Known defects (AI review)

- Colour borders are ragged where they follow the scan's triangles (sock tops, pants hem, collar); a few small blue
  islands on the jersey sides.
- The STL surface is lumpy (a hand sculpt); fine moulded details of the parametric rounds (glove ridges, lettering
  relief) are not in it.
- The socket's key bore is not modelled on this body (hidden underside).
- The STL's own stick is not used (round printable rod at another angle).

## Switch (user: "Switch now", 2026-10-12)

How: `data/figure-molds.json` skater gets `"mesh_source": "data/figures/skater-stl.json"`. `assets/blender/figure_molds.py`
then builds the skater as the STL body (per-face colours from `skater-stl-paint.json`), the wire shaft, blade and runner
from the spec; `build_figures.py` takes k from the spec and the STL camera fits; `scripts/define-figure-molds.ts` writes
the STL contacts and sources into `data/geometry.json`; `scripts/shotlib/export_footprints.py` hashes the STL inputs.

The blade is the traced one in mm (heel 22.7 mm, toe 43.5 mm lateral). The old spjass-family traces read the
parametric mesh at k 1.0814, whose blade toe sat about 4 mm nearer the axis (39.5 mm). The body is also larger.

| Trace | Result with the STL skater | Change |
| --- | --- | --- |
| Shovel #17 (accepted) | passes; W-C skate exception still 2.05 mm (max 2.7) | none |
| spjass, defence, Hjerpefinte v1, Edwall goal 2 | pass | none |
| Näcka | the shot hit the goalie's stick | lunge ends 44.0 mm up the slot (slot end allows 44.1), turn back 8 deg less; goal at y -28.1 (window -28.7) |
| IKV v2 | reception sent the puck off line; the longer blade met the puck early and hard | LW reception turn 240 ms (was 200); RW slides 18 ms earlier at 562 mm/s, faces 192 deg, turns 192 -> 293 deg in 120 ms (search over five values); window 2.45 s; LW push peak 190 mm/s (was 93; rule 500), shot 472 mm/s, boards 288 mm/s; wide and replay cameras raised (the taller wing hid the puck) |
| Edwall goals 3 and 4 | no goal | refitted (`--fit pass`, `--fit shot`; goal 3 needed a larger search: shot maxiter 60, popsize 15) |

IKV's engine port (`moves/invers-kryssar-velodrom/move.json`) follows the same values and still reproduces the trace
exactly. Not rechecked: IKV v3 (PR #9) and Hjerpefinte v2 (PR #12) on their own branches, and the NM26 analysis (it reads
`out/figures/skater.npz` reach; not rebuilt).
