# Player figures: rigid STIGA molds (2026-09-30, before iteration 21)

User request: replace the goalkeeper and skater proxies with accurate rigid STIGA figures (mounting axis,
stick, blade, skates, uniform) from the photos and videos in `references/players_images` (main branch).
User statement (source `user_statement_2026_09_30_players`): *every player is identical, except the
goalkeeper; Sweden and Finland differ only by kit colour and the country name on the back.*

AI review only; no personal user approval is recorded.

## Evidence

| Input | Use |
| --- | --- |
| 9 HEIC photos (IMG_2564-2572), Sweden goalie no. 30 | front, back, top, side, underside (mount socket), lying views |
| IMG_2573.mp4 (17 s), goalie | 0-11 s turntable (phone still, figure turned by a finger), then close-ups |
| IMG_2574.mp4 (24 s), Sweden skater no. 21 | 0-11 s turntable, then hand-held close-ups incl. the socket |
| Official overhead (`stiga_se_fi_overhead`) | top views of all 12 figures at the (assumed) preview scale: absolute scale, poses, stick layout |
| Finland team pack (`stiga_ca_team_pack_finland`) | five identical Finland skaters + goalie side by side at one depth: goalie and skater equally tall |

Originals are unchanged and hashed in `references/index.json` (`user_*` entries). Decoded, cropped stills:
`references/derived/players/*.jpg` + `manifest.json` (crop boxes in full-frame px, EXIF, tone mapping;
`npm run players:frames`). Video frames are HLG BT.2020 10-bit, tone-mapped to BT.709 with a fixed filter.

**No photo contains a scale object near the figure** (the tape measure lies far behind it). The photos give
shape and proportions; absolute size comes only from the official overhead, itself at the ASSUMED preview scale.

## Observations (traced)

- **Mount (fixture axis).** Skater: a flared cylindrical socket with a rectangular key bore under the **left**
  skate (the stick side) - the figure stands on it and turns about its axis. Goalie: the same kind of socket
  under the goalie's **right** skate; the left leg ends in a pad block.
- **Skater pose (one mold for all ten skaters).** Upright skating crouch (torso ~30 deg forward), left leg
  planted on the socket, right leg pushed back and out with its skate runner on the ice. Right (upper) hand
  at chest height, left (lower) hand at the hip: **left shot**. All ten skaters in the official overhead
  show the same top-view pose; the team pack shows five identical Finland skaters.
- **Skater stick.** Metal wire through both gloves, bent at the heel into a flattened blade standing on its
  edge on the ice toward the figure's left. Overhead (on the ice, no relief error): heel ~21.9 mm left of the
  axis, blade ~20.2 mm long (E-RD, W-RD, E-C, E-LD; E-LW excluded, blade partly hidden by the goal cage).
- **Goalie.** Blue mask with cage and skin patches behind the straps; yellow/white jersey shoulders and
  chest; blue arm pads; ribbed blue leg pads in front of yellow/white socks; blocker (right hand) with a
  border of small holes and a blue handle peg; catcher (left) at the hip; wide tan stick: paddle from the
  blocker down to a heel between the pads, blade across the front to the goalie's left, longer than the body
  is wide.
- **Uniform.** Kit colour on jersey and socks (Sweden yellow, Finland white); helmet, gloves, pants, boots,
  goalie pads/mask in one blue for both teams (overhead medians of all Finland vs all Sweden blue pixels:
  (19, 89, 142) vs (18, 87, 139)); skin face. Back print: country name arched over the number.
- **Numbers** (`data/figure-molds.json` `prints`): official overhead reference variant W-LD 5, W-RD 4, W-C 64,
  W-LW 26, W-RW unread, W-G 31 (low confidence), E-LD 5, E-RD 2, E-C 21, E-LW 92, E-RW 13 (low confidence),
  E-G 30. The user's skater is no. 21 and goalie no. 30 - the same as the reference E-C and E-G.

## Method

1. **Stills** (`npm run players:frames`): crops around the figure, full resolution; crop boxes kept so every
   camera is fitted in full-frame pixels (photos: 26 mm-equivalent focal length from EXIF, 4290 px; video
   focal fitted within 2600-3600 px).
2. **Mold layout** (`data/figure-molds.json`): each colour region is a smooth metaball part (ellipsoids,
   capsules, rounded boxes); the parts overlap like two-shot moulded plastic and are joined into ONE rigid
   mesh. Lathe socket with key bore, wire stick (skater) / flat paddle and blade (goalie), skate runner,
   goalie pad ribs and blocker holes. Frame: origin = fixture axis at the socket underside, +x facing,
   +y the figure's left (docs/geometry.md pivot-local frame).
3. **Camera-matched silhouettes** (`npm run players:fit`, `scripts/fit-figure-views.py`): per view the camera
   (azimuth, elevation, roll, aim, distance, video focal) is optimised for the IoU between the model
   silhouette and the colour-segmented photo (metal stick excluded; frames where a finger touches the figure
   drop skin-coloured pixels on both sides). Output sheets show photo | mismatch | shaded model render.
4. **Keypoints** (`data/figure-keypoints.json`, `scripts/triangulate-figure-keypoints.py`): socket, stick heel,
   stick top, chin, nape, number, right boot read on gridded turntable frames and bundle-adjusted (shared
   camera; RMS 23 px on ~1100 px figures). Used to anchor the stick and head before shape fitting.
5. **Shape refinement** (`scripts/fit-figure-shape.py`): joint coordinate descent over element joints and
   sizes against all skater views (primitive-union proxy, weak prior 4 mm); 2 rounds, proxy IoU 0.743 -> 0.786,
   no joint moved more than 1.1 mm. Gloves, stick and socket stay fixed.
6. **Absolute scale and poses** (`npm run players:overhead`): the overhead is modelled as a pinhole camera above
   the ice (relief of elevated parts; camera fitted at about (28, -29, 1108) mm); each Sweden skater's socket is
   constrained to its slot centreline with free arc position and heading; one scale k for all skaters.
7. **Assets** (`npm run blender:figures`): k applied, Sweden/Finland kit materials (colours sampled from the
   overhead, validation/18-colour-samples.json), back-print decals as separate child meshes (per player in
   the scene), GLB export, orthographic view sheet and camera-matched Cycles renders.
8. **Data** (`npm run players:define`): sources, assumptions, contacts, inventories -> data/geometry.json
   (geometry_version 0.6.0); then `assembly:poses` and the scene chain (docs/tools.md).

## Results (AI review; thresholds fixed before fitting)

| Check | Result | Threshold |
| --- | --- | --- |
| Skater silhouettes, 7 turntable views | mean IoU **0.808** (0.735-0.870) | mean >= 0.78, each >= 0.65 |
| Goalie silhouettes, 8 photo/video views | mean IoU **0.816** (0.783-0.840) | mean >= 0.78, each >= 0.65 |
| Overhead, 4 Sweden skaters (colour masks) | IoU 0.69-0.79, mean 0.745; k = **1.071** mm/mold unit | each >= 0.65 |
| Overhead stick check (on the ice) | heel 22.1 mm lateral, blade 19.5 mm (mean of 4); model 22.5 / 20.6 mm | within 1.5 mm |
| Finland W-RD / W-G traced silhouettes (check only) | IoU 0.68 / 0.69 | - |
| Assembly (12 figures) | no intersections, nothing below the ice, vertical axes, det +1 | pass |
| Remotion import checks | fixture axis 0.0004 mm, blade direction/handedness, units | pass |

Resulting assets (`validation/players/figures-report.json`): skater height **51.2 mm** (ice to helmet top),
socket base diameter 12.0 mm, stick heel (3.2, 22.5) mm, blade 20.6 x 3.2 mm; goalie height 50.4 mm, socket
11.6 mm, blade 27.0 x 3.0 mm across the front toward its left. About 50k (skater) / 66k (goalie) triangles.

Main artifacts: `validation/players/figures-vs-photos.png` (camera-matched renders beside the photos),
`validation/players/figures-views.png` (both kits, five views), `validation/players/skater-fit.png`,
`goalie-fit.png`, `overhead-fit.png`, `validation/16-oblique.png`, `validation/19/19-oblique.png`.

## Limits and open items

- **Absolute size is not measured.** It rests on the overhead at the ASSUMED preview scale. The catalog's
  "figure height approx. 57 mm" (datum unspecified) is 5.8 mm above the fitted skater height - not resolved.
- **Goalie scale conflict.** The goalie alone fits the (hand-traced, white-on-white) W-G silhouette best at
  k = 1.18 (IoU 0.70) vs the shared 1.071; the Finland team pack shows goalie and skaters equally tall, so the
  shared k is used (`assume.figure_mold_scale`). A ruler measurement resolves it.
- Remaining shape errors (AI review): skater right-arm path and hips in profile (IoU 0.73-0.76 at 3.0 s and
  8.5 s); no facial features; print fonts approximate; socket bore, blade/wire thickness assumed
  (`assume.figure_mold_hidden_details`). Metal sticks render nearly black in Remotion/Three (no environment map).
- Poses: six figures (E-LD, E-RD, E-C, E-LW, W-RD, W-G) stand at their overhead-fitted pivot and heading; the
  other six use the hidden-stretch rule at theta 0. E-LW is turned -4 deg to clear the solid preview goal (its
  blade tucks under the cage in the photo). Rod travel, stops and transfer remain unknown.
- Jersey numbers are the reference variant's; the user's own set is unknown beyond no. 21 and no. 30.

## Questions for the user

1. Could you measure one skater and the goalie with a ruler: height (table to helmet top), socket base
   diameter, and the distance from the socket centre to the stick heel and to the blade tip?
2. Which jersey numbers do your Sweden and Finland figures carry, per position?
3. Is the Finland kit white with the same blue parts (as in the official pictures), and is anything printed on
   the front or sleeves?
