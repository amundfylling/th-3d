# Goalie bent toward the photos (2026-11-11, PROPOSED)

User request (2026-11-11): make the goalkeeper more like the original. No 3D model of the STIGA goalie was found online
(searched Thingiverse, Printables, MakerWorld, Cults, CGTrader, MyMiniFactory; the hits are fantasy "table hockey
player teams", no STIGA goalie), so unlike the skater (docs/skater-stl.md) there is no scan to switch to.

**Status: PROPOSED, NOT in use.** The new assets `assets/figures/goalie_warp_{SWE,FIN}.blend|.glb` sit beside the
current goalie. `assets/figures/goalie_{SWE,FIN}.*`, the contact shapes in `data/geometry.json`, the footprints, the
traces and the videos are unchanged. Switching is the user's decision (see "Switch"). AI review only.

## What was done

The hand-built parametric goalie (data/figure-molds.json, 13 rounds of hand tuning, docs/players.md) had the right parts
but the wrong posture and proportions: balloon shoulders, an upright body and head. It is now bent by a smooth 3D
displacement field fitted to the outlines of the figure in the user's own photos and video frames
(`scripts/goalie-silhouette-warp.py`, field in `data/figures/goalie-warp.json`):

- x -> x + u(x) in mold units, u trilinear on a 2.5-unit lattice. All parts, paint borders, pad ribs and blocker holes
  ride along; the field is continuous, so nothing detaches.
- At each camera-matched view, the model's rim vertices are pulled onto the photo outline (point-to-plane, all views in
  one least-squares solve with a smoothness term), 30 small steps, cameras refitted every third step.
- Held fixed: the mount socket (fixture axis), everything touching the ice, and the top of the mask, so the measured
  height (54 mm) and the scale k (1.14219) do not change. The tan stick moves rigidly in plan only (turned about z,
  slid on the ice), so the measured blade (26 x 5.5 mm) keeps its size and stays flat.
- Fitting views: the 8 fitting views and the 5 former held-out views without a finger in frame. NOT used: the 6 finger
  frames and the 4 regression frames.

## Result

Mean silhouette IoU, cameras refitted from the stored ones for both shapes (`fit-figure-views.py --reuse`; the same
procedure as the STL skater comparison). Files: `validation/players/warp/` (new) and `validation/players/warp/base/`
(current mold, same procedure).

| Views | Current goalie | Warped goalie |
| --- | --- | --- |
| 8 fitting views (used) | 0.858 | **0.915** |
| 5 former held-out views without a finger (used) | 0.813 | **0.881** |
| 10 frames NOT used (6 finger frames + 4 regression frames) | 0.815 | **0.833** |

The unused frames are mixed: 6 of 10 improve (up to +0.07), 4 get worse (t03.75 -0.02, t06.25 -0.03, t09.00 -0.01,
t06.75 -0.05). All four are turntable frames with a finger on the figure and motion blur, where the camera fit itself is
weak; they are reported, not explained away.

Displacement: mean 1.2, max 3.4 mold units (1.4 / 3.9 mm). Asset measures (`validation/players/warp/figures-report.json`):
height 53.99 mm (was 54.00), socket base 12.35 mm (12.34), stick lowest point 0.0 mm, stick extent along the blade
unchanged (26.68 mm); the blade toe moved from (7.5, 34.5) to (9.6, 34.7) mm (the stick turned about 3 deg in plan);
footprint x -11.8..12.3 mm (was -9.2..11.5), y -15.2..34.7 mm (was -14.5..34.5).

Main artifact: `validation/players/warp/figures-vs-photos.png` (photo | current | warped, each at its own fitted camera).
Also `validation/players/warp/figures-views.png` (rows: current Sweden, warped Sweden, warped Finland).

What changed visibly: sloping, narrower shoulders; the body and head lean forward as on the real figure; fuller back;
arms closer to the body.

## Known defects (AI review)

- Silhouettes cannot see inside the outline. Still hand-built and still unlike the original: the mask face (the real
  one is more angular with a long chin), the chest (the real one has moulded pectorals and a sharper collar V), the pad
  fronts (the real rolls are shorter and sit above a different lower pad), the catcher pocket and the blocker handle.
- The jersey back is slightly wavy (lattice-scale ripples) and the back print wraps a little further round the side.
- Paint borders are the old ones, moved with the surface.
- The contact shapes (pads, blade, body) were NOT rebuilt from this shape.

## Switch (not done)

A switch would follow the skater precedent: `data/figure-molds.json` goalie gets `"warp_source":
"data/figures/goalie-warp.json"`, `figure_molds.build_goalie` / `build_figures.build_mold` apply
`warp_vertices`, the goalie contacts in `data/geometry.json` and `data/figures/contact-footprints.json` are rebuilt, and
every trace is rechecked under the contact-physics and slide rules (the pads and the blade moved by up to about 2.5 mm).

## A better source would beat this

The remaining differences are details that only a real 3D capture gives. A phone photogrammetry scan of the goalie
(for example 60-100 sharp photos all round at three heights on a matt, textured surface, or a scan app export as
OBJ/STL/GLB) could replace the body the same way the Thingiverse STL replaced the skater.

## Rebuild

```sh
/root/venvs/blender/bin/python assets/blender/preview_molds.py goalie      # out/figures/goalie.npz
/root/venvs/blender/bin/python scripts/goalie-silhouette-warp.py fit       # about 20 min; rewrites data/figures/goalie-warp.json
npm run players:goalie-warp                                                 # apply the stored field + build assets and sheets
```
The venv needs `scipy` besides the packages in docs/blender.md. The scoring runs are
`scripts/fit-figure-views.py goalie --mesh out/figures/goalie-warp.npz --out validation/players/warp --reuse [--heldout|--independent]`.
