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

## Refinement round 2 (2026-10-01): visible fidelity

User review: "substantially improved, but not yet visually accurate enough" - refine the skater's arms/torso,
helmet and face, the goalie's mask, pads and gloves, and the actual block-number lettering; show close-up
matched-camera comparisons including views not used for fitting; prioritise visible fidelity over the
silhouette thresholds. AI review only.

**Comparison method** (`assets/blender/render_closeups.py`, `npm run players:closeups`): every fitted view and
every HELD-OUT view is rendered with Cycles from its fitted camera at the photo crop's framing; the render's
exposure and illuminant are matched to the photo (median figure luminance, table tint), shape and relative
colours untouched. Feature windows (skater: head, arms/torso, back print, gloves; goalie: mask, pads, gloves,
back print) are projected from the mold frame and cut identically from photo and render.
Held-out views (`<kind>-heldout-fit.json`; cameras fitted only after the shape, never used to shape it):
skater 01.50 s, 14.50 s, 22.60 s; goalie photo-top, video 16.75 s, lying-back, lying-back-2, underside.
`skater-video-t13.25` (lying on its back, a near-orthographic front view) moved from held-out to the fitting
set because it was used as a modelling reference for the face, gloves and gauntlets.
Cameras: the fitted azimuth is now kept within 60 deg of the known view direction (front and back silhouettes
of a flat-lying figure are near mirror images; one view had flipped).

**Skater changes**: whole upper body moved 1.5-2 mm forward over the support leg and the shoulders lowered
(the profile showed a more upright, forward torso); head pitched 20 deg down with a longer, narrower face (brow,
nose, cheeks, pointed chin), lower helmet with a brim and small ear guards; thick neck and traps so the
helmet sits close to the collar from behind; collar as a smooth ring plus front V; lower (left) hand moved
onto the stick at the hip, rounded box gloves with thumbs, flared gauntlet cuffs on both forearms
(hard-surface cones); narrower left side and lower jersey hem. New element types: rotated ellipsoids,
bevelled rounded boxes, cones and tori (`assets/blender/figure_molds.py`).

**Goalie changes**: egg-shaped helmet with a sculpted front mask (brow, nose, cheeks, chin) and a back strap;
the skin seen through the gaps between mask and back plate is painted onto the mesh as crescents
(`paint` in data/figure-molds.json, az/el polygons about the head centre; back photos IMG_2566/2567/2570, side
IMG_2572); V collar ring; ribbed leg pads in two sections with two knee straps; flat blocker board (tilted,
rounded rim, 14 moulded holes, handle peg) with the hand behind it; catcher with cuff, pocket, thumb and web;
yellow jersey ends above the pads.

**Lettering** (`assets/blender/print_glyphs.py`): the jersey numbers are collegiate BLOCK digits - uniform
bars, chamfered corners, rectangular counters, short spurs - with a thin kit-colour gap and a thin dark
outline; the country name is a straight plain sans (not arched), as on the photos. Proportions read from the
goalie's 30 (IMG_2566): width 0.69 H, bar 0.225 H, chamfer 0.095 H. Layout per mold in `print_layout`.

**Colours**: plastic albedo in `data/figure-molds.json` `albedo_srgb` (deep royal blue, orange-yellow, white,
orange skin), hue/saturation checked on the user photos, white balance from the official overhead.

## Goalie measurements (2026-10-01)

The user measured the actual goalie with a ruler (endpoint sketch:
`references/user_measurements/goalie-measurements-2026-10-01.png`, index id `user_goalie_measurement_sketch`;
source `user_measurement_2026_10_01_goalie`, kind `user_measurement`):

| Quantity | Value | Endpoints |
| --- | --- | --- |
| Overall height | **54 mm** | mask top to the bottom of the figure (socket underside = ice plane) |
| Stick blade length | **26 mm** | along the blade's lower edge, heel bend to toe |
| Stick blade height | **5.5 mm** | vertical height of the blade plank (at the toe) |

Uncertainty was not stated and stays null. Effects:
- **Goalie scale** k = 54 / mold height = **1.142 mm per mold unit** (`goalie.scale` in data/figure-molds.json,
  status measured; `assets/blender/build_figures.py` `calibrate_goalie()`). The goalie no longer shares the
  skater scale; `figure_height` of fig.W-G / fig.E-G is `measured` (54 mm). The asset measures 54.0 mm.
- **Blade** rebuilt to 26.0 x 5.5 mm (it was 27.3 x 3.0 mm at the old shared scale: the measured blade is
  shorter relative to the body and almost twice as tall); the paddle now meets the blade top.
- **Independent check of the preview scale**: the goalie-only best fit to the traced W-G silhouette on the
  official overhead (assumed 0.1796 mm/px) is reported in `validation/players/overhead-fit.json`
  (`goalie_measured_over_overhead_best`); a ratio near 1 supports the assumed rink scale. The rink scale is
  NOT changed from it (one figure, hand-traced white-on-white silhouette).
- **Skater** dimensions stay independent (overhead-fitted, `assume.figure_mold_scale`) until measured.
- Results: goalie asset 54.0 mm high, blade 26.0 x 5.5 mm (`validation/players/goalie-dimensions.png`);
  goalie silhouettes mean IoU 0.826 (8 fitted views) and 0.814 (7 held-out views, incl. the rotation video);
  overhead check: measured goalie k / goalie-only best k at the assumed preview scale = 0.991.
- Rotation video frames 2.5 s and 10.0 s were added as held-out goalie views; camera fitting now drops the tan
  stick (with skin) in views where a finger touches the figure, keeps a per-view azimuth tolerance and never
  places the camera below the table.

## Refinement round 3 (2026-10-01): moulded contours

User request: one bounded round toward faithful replicas - skater gloves, gauntlet cuffs and wrists (plus helmet,
face, collar where supported), goalie mask and exposed skin, pads (rounded contours, knee) and catcher (pocket,
thumb); geometry first, colour after; consistent cameras and lighting; held-out angles; AI review only.

**Method.** Cameras frozen for the whole round (`validation/players/*-fit.json` from round 2). New
`scripts/fit-figure-views.py --fixed` scores the silhouette at the stored cameras without refitting. The BEFORE
close-ups were rendered from the pre-round molds with the same cameras and lights; the AFTER close-ups from the new
molds (`scripts/closeup-before-after.py` -> `validation/players/closeups-before-after.png`). Reference crops were
read through the fitted cameras at full resolution.

**Skater (shared mold).**
- Gloves: rebuilt as fists around the actual stick line - back of hand, palm, four knuckle/finger rolls wrapped
  around the shaft, thumb along it, and a wrist piece entering the cuff (metaball, so the wrist blends). Chunky,
  about cuff-mouth wide, as in the front views (t13.25, t14.50).
- Gauntlets: new lathe `cuff` primitive - trumpet flare from wrist to an open, oval, recessed mouth with a rolled
  rim and an oblique cut; the upper (right) cuff now opens forward at the shoulder instead of pointing sideways.
- Helmet: ear guards removed (the face skin continues under the edge in the profile views); larger, rounder back;
  low centre ridge (t03.00 back view).
- Face: narrower forehead and jaw, longer face, stronger nose and chin.
- Collar: flat band lying on the jersey (elliptical cross-section torus) with a flat V front, instead of a tube.

**Goalie (shared mold; height and blade unchanged: 54.0 mm, blade 26.0 x 5.5 mm).**
- Mask: smooth egg front with a vertical centre ridge, brow line and two shallow eye hollows (negative metaball
  elements); cheek and nose bumps and the back strap removed (the back plate is smooth in IMG_2566).
- Skin: narrow crescents curving from the crown to the jaw either side of the back plate, about 120 deg from the
  facing direction, plus the nape below the plate (back, top and side photos).
- Pads: rounder blocks; fat vertical rolls above and below a thick double knee band.
- Catcher: boot-shaped mitt - narrow at the cuff, widening into a lobe that reaches outward and down to the knee
  band - with a diagonal thumb ridge and a carved pocket.

**Colour (after geometry).** Same-camera hue/saturation comparison over 12 views: blue hue matched within 2
(OpenCV units) but rendered too saturated (~185 vs ~145); blue albedo changed [30,100,182] -> [62,105,181].
Yellow left unchanged (hue within 2; the remaining saturation gap is mostly the clear-coat highlight).

**Results (cameras frozen, scored with `--fixed`).**

| Silhouette IoU | before (round 2) | after (round 3) |
| --- | --- | --- |
| Skater, 8 fitted views | 0.8076 | 0.7920 (min 0.688) |
| Skater, 3 held-out views | 0.7952 | 0.7684 |
| Goalie, 8 fitted views | 0.8256 | 0.8302 |
| Goalie, 7 held-out views | 0.8139 | 0.8164 |

The skater drop comes from the reshaped arms at cameras that were fitted to the old arms; it is reported, not
optimised away (a refit would hide shape changes). Skater overhead scale k 1.0866 -> 1.0864 (height 51.84 mm,
unchanged within 0.01 mm). Goalie: 54.0 mm, blade 26.0 x 5.5 mm (unchanged). Assembly: no intersections.
Fidelity was judged separately from these numbers, on the before/after sheet (AI review, not the user's).

**AI review of the before/after sheet.** Improved: skater gloves now read as fists with knuckles around the
shaft; gauntlets flare to an open, rimmed mouth; the face is longer and narrower; the collar is a flat band.
Goalie mask has eye hollows and a centre ridge; the back skin forms the "( )" crescents seen in the photos; the
catcher reads as a boot-shaped mitt with a pocket. Still wrong (round 3):
- Skater upper (right) gauntlet is narrower and rounder than the photo's broad, flat cuff that covers the chest;
  held-out t22.60 shows the arm standing out from the body.
- Skater helmet sits slightly high and has no visible visor/brim edge; face features remain softer than the
  moulding.
- Goalie pads changed little in appearance: the rolls read as highlight bars at the pad tops; the real lower
  pads taper toward the boots.
- Goalie side view: the exposed cheek skin is smaller than in the photo. Front: a small skin chin/V shows that
  the photo does not.
- Goalie catcher cuff is still a separate cone; the mask front is more specular than the photo.

## Refinement round 4 (2026-10-01): upper cuff, gloves, pads, mask skin

User request: one bounded round on the largest mismatches of the round-3 before/after sheet - skater gloves too
swollen and the upper (right) cuff projecting outward; goalie pads still rectangular panels with repeated ribs;
jagged skin-colour borders around the mask and their width. Same cameras and lighting for before/after; views
that guide modelling are fitting references; fresh frames reserved for independent checks.

**View policy.** All 29 previously extracted views (fitted + former held-out) had been inspected while
modelling, so they now count as fitting references ("inspected" in the sheets; `<kind>-heldout-fit.json`
keeps its name). Eight fresh turntable frames were extracted for this round (`scripts/extract-player-frames.py`,
existing stills untouched): skater 2.25/5.25/9.25/10.25 s, goalie 3.75/6.25/9.00/11.00 s. Their times were
chosen from the interpolated camera azimuth, not by looking at them; their cameras were fitted ONCE on the
round-3 model (`fit-figure-views.py --independent`, which favours the old shape) and then frozen. They were
first looked at after modelling ended and did not guide any change.

**Method.** Landmarks read in several fitted photos were triangulated through the frozen cameras (upper-cuff
outer tip ~(1.7, -19.6, 31.9), inner top corner ~(6.0, -4.6, 32.0) mold units: the cuff spans the chest
under the upper arm). Shapes were iterated with fast Cycles renders at the fitted cameras; azimuth/elevation
lines projected through the cameras were used to read the skin borders on the mask.

**Skater (shared mold).**
- Upper (right) arm: the upper arm now runs out to the elbow beside the chest (was forward), and the gauntlet
  is a new `lofts` primitive (`loft_cuff`): a broad, flat funnel lying across the chest with its oval mouth
  (15 x 7 mold units) opening upward under the upper arm, a rolled rim, a recessed opening and a rounded base;
  it narrows down to the hand at the top of the stick, which it covers (the stick emerges below it, as in the
  front photos). The lower (left) gauntlet is also a loft, smaller and closer to the body.
- Gloves: one moulded hand block per glove (metaball rounded box with flat faces, `mboxes`), extending from the
  stick toward the wrist, with three shallow finger grooves carved across the knuckle end, a small thumb and a
  wrist stub - replacing the round-3 fists with individual finger bumps.

**Goalie (shared mold; 54.0 mm, blade 26.0 x 5.5 mm unchanged).**
- Pads: rebuilt as two moulded parts (`pad_l`, `pad_r`) instead of boxes plus separate ribs. Volumes first: a
  rounded upper (thigh) block, a forward knee block about mid-height (raised ~5 mold units to match the front
  photos), and a lower (shin) section of two blended blocks tapering toward the boot. Surface detail second:
  tall vertical rolls with rounded tops and carved grooves on the upper section, shallower tapered rolls on the
  lower section, two knee ridges. The contact footprint moved to `goalie.pad_footprint` (unchanged values).
- Mask skin: borders are now subdivided along the paint polygons before colouring (`refine`, 3 levels), so they
  are smooth instead of stepping along mesh faces. Crescents widened (about 26-34 deg of azimuth at ear level,
  narrower toward the crown) and moved round to the sides, following the side photo. The back plate now ends
  above a real skin neck (the lower back of the mask shell is carved, the neck raised) instead of a painted
  nape band; the back collar ring sits slightly lower.

**Results (cameras frozen, `--fixed`).**

| Silhouette IoU | round 3 (before) | round 4 (after) |
| --- | --- | --- |
| Skater, 8 fitted views | 0.7920 | 0.8043 |
| Skater, 3 inspected (former held-out) | 0.7684 | 0.7843 |
| Skater, 4 INDEPENDENT fresh frames | 0.7725 | 0.7669 (regression) |
| Goalie, 8 fitted views | 0.8302 | 0.8289 (regression) |
| Goalie, 7 inspected (former held-out) | 0.8164 | 0.8139 (regression) |
| Goalie, 4 INDEPENDENT fresh frames | 0.8051 | 0.7993 (regression) |

The independent cameras were fitted on the round-3 model, which biases those scores toward the old shape. The
skater overhead scale re-fitted from 1.0864 to 1.0814 (skater height 51.84 -> 51.60 mm) because the arm changed
the top-view silhouette. Assembly: no intersections. Visual fidelity was judged separately on
`validation/players/closeups-before-after.png` (AI review, not the user's).

**AI review.** Improved: the upper cuff no longer projects as a trumpet; it is a broad cuff under the arm in the
front, elevated and independent frames (2.25 s, 10.25 s) and is hidden at the back (5.25 s), as in the photos.
Gloves read as moulded mitts with shallow ridges. Goalie pads show rounded tubular upper rolls, a distinct knee
band and a narrower lower section; skin borders are smooth; the neck shows below the back plate. Still wrong:
- Skater upper cuff: rim reads as a sharp flat lid and the funnel sides as straight cone faces; the photo cuff is
  more bulbous and reaches lower on its outer side. The lower (left) glove sits slightly off the photo position.
- Goalie mask skin: in the back views (incl. independent 9.00 s) the crescents are now too wide in their upper
  half and the neck block is smaller than in the photos; the side photo needs the wider band. This conflict
  points at the mask/head shape (the az/el paint follows the model's head, which is lower and rounder at the
  back), not only at the paint.
- Goalie pads: a horizontal waist crease where the two lower blocks blend; the lower section is mostly hidden
  by the stick/blocker in the photos, so its taper is weakly constrained.
- Goalie blocker board: seen nearly edge-on in the front views while the photos show its face, and it is
  smaller than the real board, so the model shows pad area the real blocker covers. Not changed this round.

## Refinement round 5 (2026-10-01): blocker, softer cuff, clean lower pads, finish and lighting

User request: one focused round from the existing photos and videos only (no new captures): goalie blocker
orientation, size and connection to the hand/stick first; then soften the skater's upper cuff rim and cup
contour and remove the creases/scallops of the goalie's lower pads; then highlights, roughness and clear coat
together with useful reflections for the metal stick. Measured goalie dimensions kept; skater scale frozen.

**View policy.** The round-4 independent frames were inspected after round 4 and moved to the inspected set
(`<kind>-heldout-fit.json`, cameras unchanged). Eight fresh turntable frames are this round's INDEPENDENT checks
(skater 0.75/3.75/6.75/8.00 s, goalie 1.25/6.75/7.25/8.40 s), chosen by interpolated azimuth without looking,
cameras fitted once on the round-4 model and frozen. Goalie 4.25 s was dropped before any modelling because its
camera fit failed (elevation ran into the bound, IoU 0.65) and replaced by 7.25 s; goalie turntable fits now
bound the elevation to +-15 deg of the neighbours' value.

**Goalie blocker (shape, from four front views).** Board corners were read in photo-front, front-oblique and
video 0.50 s / 2.50 s and fitted as one rigid rectangle through the frozen cameras (least squares, 9 px RMS).
Result: the board is about 7.8 x 12.0 mold units (8.9 x 13.7 mm at k 1.142; was 5.2 x 9.2 units), its face
turned to azimuth -21 deg (front-right; it was nearly edge-on to the front camera), standing upright in front of
the right pad. Depth along the view direction is the weakly constrained coordinate: it was set so the board's
back face clears the pad fronts and the paddle runs behind it, which costs ~6 px RMS against the corners (15 vs
9 px). The hand block sits behind the board's upper inner corner and holds the paddle top; the peg (thumb
guard) points out to the goalie's right as in the side photo and video 5.00 s. Stick: the heel triangulated
from three views lies at y 7.4 (was 1.8): the blade moved 5.6 units toward the catcher side with its measured
26 x 5.5 mm size unchanged, and the paddle now runs from the hand behind the board to that heel, its flat face
turned to the board's direction (`stick.paddle_face`). Holes: two columns of six and a top row of three, as in
the photos.

**Goalie lower pads.** The two blended blocks and the raised roll capsules are replaced by one shin section of
15 closely stacked rounded slices tapering linearly toward the boot (no waist crease) with three shallow carved
grooves (no scallops). Upper pad, knee and rolls unchanged.

**Skater upper cuff.** `loft_cuff` gained `bulge` (fuller sides), `warp` (saddle-shaped mouth instead of a flat
lid) and `subsurf` (Catmull-Clark smoothing); the rim is thicker and rounded (lip 1.1) and the recess shallower,
so the opening no longer reads as an empty cup. Same position and size as round 4. Lower cuff likewise.

**Finish and lighting.** `data/figure-molds.json` `finish` (status assumed, set by comparison with the photos):
plastic roughness 0.40 + clear coat 0.30 with coat roughness 0.12 (was 0.30 + a mirror-like coat), skin 0.45,
metal 0.28. Close-up renders: Blender's bundled "interior" studio HDRI as world (strength 0.55, transparent
film) plus a small 6 cm key 30 cm above, replacing the grey world and the 25 cm area light 25 cm above that
painted broad white patches. Remotion: a procedural RoomEnvironment map on the figure materials only (metal 1.0,
plastic 0.12) so the sticks reflect instead of rendering black; the rink keeps its iteration-19 lighting (the
reprojection check still passes).

**Comparisons.** `validation/players/closeups-before-after-neutral.png` (grey clay, same cameras and lights
before and after: shape only) and `validation/players/closeups-before-after.png` (final materials: before =
round-4 lighting and finish, after = round-5). Remotion: `validation/players/remotion-before-after.png`.

**Silhouette IoU (frozen cameras).**

| Set | before (round 4) | after (round 5) |
| --- | --- | --- |
| Skater, 8 fitted views | 0.8043 | 0.8028 |
| Skater, 7 inspected | 0.7744 | 0.7724 |
| Skater, 4 INDEPENDENT | 0.8114 | 0.8087 |
| Goalie, 8 fitted views | 0.8289 | 0.8409 |
| Goalie, 11 inspected | 0.8086 | 0.8038 |
| Goalie, 4 INDEPENDENT | 0.8124 | 0.8103 |

The skater changed only in the cuff rim (small regressions, within ~0.003). The goalie gains on the fitted front
views (larger, turned blocker) and loses slightly on the inspected and independent sets - mostly back/top views
where the moved blade and larger board now extend further than the photographed silhouette (8.40 s: 0.795 ->
0.787). Skater scale frozen at k 1.0814 (overhead refit skipped). Goalie 54.0 mm, blade 26.0 x 5.5 mm.

**AI review (not the user's).** Improved: the blocker now shows its broad dotted face in all front views and
covers the right pad as in the photos, the paddle disappears behind it, and the blade bend sits where the photos
show it; the lower pads are smooth and tapered; the cuff rim is rounded; highlights are small and the metal
sticks read as metal. Still wrong / uncertain:
- Blocker depth (distance in front of the pads) is inferred, not observed; the peg end is triangulated from two
  views only; the photographed board corners are slightly rounder than the model's.
- The blade's angle and the paddle's exact path are approximate (heel from three views; toe readings disagree by
  ~3 units between views), and in the independent back views the blade end now extends past the photo.
- Skater upper cuff: still a single funnel; the photo cuff is lumpier and its rim less regular. The lower pads'
  grooves are inferred (the stick and blocker hide most of the shin in the photos).
- Remotion figures are slightly lighter/less saturated than before (blue median 51,94,164 vs 39,84,156; the
  calibrated albedo is 62,105,181).

## Limits and open items

- **Absolute size is not measured.** It rests on the overhead at the ASSUMED preview scale. The catalog's
  "figure height approx. 57 mm" (datum unspecified) is 5.8 mm above the fitted skater height - not resolved.
- **Goalie scale**: resolved by the user's measurement (54 mm, 2026-10-01); see above.
- Remaining visible differences: see "Refinement round 5" above. Socket bore, blade/wire thickness assumed
  (`assume.figure_mold_hidden_details`). Remotion metal sticks now reflect a procedural room
  environment (round 5).
- Poses: six figures (E-LD, E-RD, E-C, E-LW, W-RD, W-G) stand at their overhead-fitted pivot and heading; the
  other six use the hidden-stretch rule at theta 0. E-LW is turned -4 deg to clear the solid preview goal (its
  blade tucks under the cage in the photo). Rod travel, stops and transfer remain unknown.
- Jersey numbers are the reference variant's; the user's own set is unknown beyond no. 21 and no. 30.

## Questions for the user

1. Could you measure one skater with a ruler (height from the table to the helmet top, blade length and
   height, socket base diameter, distance from the socket centre to the blade heel)? The goalie is measured.
   Also useful for the next shape round: sharp, evenly lit close-up stills (no motion blur) of one skater's
   upper (right) gauntlet and glove from the front and from the side; a straight back and a straight side
   photo of the goalie's head (crescent width and neck); a front and a side close-up of the goalie's blocker
   and a ruler measurement of the blocker board (width x height).
2. Which jersey numbers do your Sweden and Finland figures carry, per position?
3. Is the Finland kit white with the same blue parts (as in the official pictures), and is anything printed on
   the front or sleeves?
