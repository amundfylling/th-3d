# Skater from the Thingiverse STL (2026-10-12, PROPOSED)

User request (2026-10-12): use the STL files of a STIGA table-hockey player that the user found on Thingiverse to make
the skater in the 3D model as accurate as possible.

Source: `references/models/thingiverse-6898521/STIGA HOCKEY PLAYER - 6898521.zip` (index id
`thingiverse_6898521_stiga_hockey_player`). "STIGA HOCKEY PLAYER" by **MAVRIS**, https://www.thingiverse.com/thing:6898521,
licence **CC BY-SA**. The zip holds a body STL (19 854 triangles, one closed watertight shell, 56.85 mm tall in file
units) and a separate round printable stick. The derived assets `assets/figures/skater_stl_*` are under the same licence
and must keep this attribution.

**Status: PROPOSED, beside the parametric skater.** Nothing downstream is switched: `assets/figures/skater_{SWE,FIN}.glb`,
`data/geometry.json` contacts, `data/figures/contact-footprints.json`, the traces and the videos still use the parametric
mold (docs/players.md). AI review only.

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

## Switching to it (not done)

The footprint below the puck top changes (IoU 0.61 with the parametric one, up to 3.6 mm apart; the STL body is larger
at its size). Switching the assets therefore means: regenerate `data/figures/contact-footprints.json` and the
skater contact shapes, then re-run every saved trace's contact and slide checks (Shovel's W-RW foot drag is solved
against the foot outline and will move). Not started: it waits on the user's go-ahead (the look and the re-run of the shots).
