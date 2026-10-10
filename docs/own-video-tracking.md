# Own-video tracking: the handheld match in a per-frame 3D camera

Status: built on 2026-10-10 (workstream 6 of the user's parallel batch: "apply the synthetic approach to the user's
handheld match ... figure and puck tracks for one full period"). Everything here is **PROPOSED**: there are no labels
for this video, and the calibration it rests on is assumed (docs/game-tracking.md).

**Result in one paragraph.** The camera is solved for every frame (7,756 frames). The 3D figure molds are fitted in that camera
for every frame of the 5:00 match (the whole game is one period; the timer signals at 100 s and 200 s are only
interval tones). The puck comes from the existing track (docs/game-tracking.md, seen in 40% of frames).
- **The camera works.** Residual 0.5 px; the slots and the figure heights line up.
- **Figure positions work for 5 of the 10 skaters:** the yellow W-LD, W-RD, W-LW and W-RW, and the white E-LD.
- **They fail for the two centres and for the white E-LW, E-RW and E-RD.** E-G is weak.
- **Rotation is not usable at this resolution.**

The NM26 networks were not reused: they are not in the repo (`out/` is not committed), and they read 80-90 px
figures, while a figure here is 20-35 px tall. Section 5 says exactly where the pipeline breaks and what would fix it.

| Step | Script | Output |
| --- | --- | --- |
| 1. Camera per frame | `scripts/own-video-camera.py` | `data/games/fylling-vs-moe-2022/own-video/camera-track.json`, check `validation/own-video-camera.jpg` |
| 2a. Pose scores (mold in the camera) | `scripts/own-video-figures.py` (`--kit-test` first) | `out/own-video/scores_*.npz` (cache, about 75 MB, not committed), `out/own-video/kit-test.json` |
| 2b. Paths over time | `scripts/own-video-figure-paths.py` | `data/games/fylling-vs-moe-2022/own-video/figure-tracks.json` |
| 3. Review | `scripts/own-video-review.py [clip start s]` | **`validation/own-video-tracks.jpg`**, `validation/own-video-tracks-clip.mp4`, `own-video/review.json` |
| Shared | `scripts/own_video_common.py` | camera, slots, molds, placement |
| Puck | unchanged `scripts/game-puck.py` | `data/games/fylling-vs-moe-2022/puck-track.json` |

Reproduce (venv with opencv-python-headless, numpy, scipy, trimesh, matplotlib; about 20 min on 4 CPUs, mostly 2a):

```sh
P=/root/venvs/blender/bin/python
$P scripts/own-video-camera.py
OMP_NUM_THREADS=1 $P scripts/own-video-figures.py --workers 4 --chunks 40
$P scripts/own-video-figure-paths.py
$P scripts/own-video-review.py 60
```

## 1. Camera per frame

The existing pipeline already maps every frame onto the ice plane: stabilisation (video → reference frame) and the
rink calibration (world mm → stabilised crop). Their product is one homography per frame, world (z = 0) → video px. A
plane homography fixes a pinhole camera once the intrinsics are known:
- **Intrinsics (assumed):** square pixels, principal point at the image centre, one focal length for the whole video
  (a phone, no zoom seen).
- **Focal length (fitted):** f = **518 px** (63° horizontal field of view). It minimises the median PnP residual over
  300 frames. The minimum is clear: 0.48 px at 518 px, against 0.8 px at 480 and 1.15 px at 600 (`focal_scan`).
- **Per frame:** `cv2.solvePnP` (IPPE) on a 9 × 5 grid of ice points gives R and t. The residual is 0.48 px median,
  0.88 px p95.
- **The camera:** a median 608 mm above the ice (p5-p95: 589-688 mm), 1.36 m from the rink centre, in front of the
  near long side.
- **Checks:**
  - Slots: on average 54% of the projected slot-centreline points fall on a pixel darker than both neighbours 4 px to
    the side (p10: 51%). This is a relative measure: blur, figures and the near board hide parts of the slots.
  - Heights, by eye (`validation/own-video-camera.jpg`, four frames over the match): every slot line sits on its dark
    slot, and a 51 mm mold at each slot's middle is as tall as the real figures.

**What is assumed:** the calibration's preview scale and goal.W at the video's left (inherited); the intrinsics; the
whole table as one plane in the stabilisation (the housing stands above the ice, so the camera is least exact in the
first 5 s, when the phone moves most).

## 2. Figures: analysis-by-synthesis in that camera

The figures are fitted to the video directly with the 3D model, with no network:
- **The candidate poses:** every figure's mold (`assets/figures/*.glb`, the same molds the NM26 renders use) is placed
  on its slot at every 5 mm and every 30° of heading.
- **Projection:** each pose is projected with the frame's camera.
- **Score:** each pose is compared with colour maps of the frame:
  - foreground: the colour difference from the empty-table background (warped into the frame);
  - kit maps: foreground pixels of each kit colour;
  - per pose: 40 jersey points are scored on the team's jersey map and 40 blue points (pants, skates, helmet) on the
    blue map.
- **Which kit is which end (measured):** `--kit-test` scores every slot with both kits on 300 frames. Team W (goal.W,
  the left player Fylling) wears **yellow** and team E **white**: 11 of 12 slots score higher with that kit (E-G does
  not).
- **Paths:** per figure, a Viterbi over all 7,500 match frames:
  - slot speed up to 1.2 m/s (assumed), with a quadratic cost;
  - heading steps penalised; any size is allowed, since figures spin.
- **Explain-away:** then two passes where a pose loses score when another figure's current path covers more than 25%
  of its image column. This rule had almost no effect (section 5).

**Output** (`figure-tracks.json`): per figure and frame:
- `u` (slot position 0-1);
- `heading_deg`;
- the pivot in mm;
- `score` (0-1; below 0.1 the figure is barely supported);
- `flip_margin` (score minus the score of the opposite heading; near 0 means front and back can't be told apart).

### Accuracy (indirect; there are no labels)

**Check against the puck** (`review.json`): the puck track is independent of the figure fit. When the seen puck lies in
a skater's exclusive reach area (`possession.json`), the figure that holds it should usually stand at it.
- The test: the distance from the puck centre to the tracked mold's lowest 12 mm (skates and blade), against the same
  skater's track taken at a random other time (null).
- Over all skaters, the tracked figure is within 20 mm of the puck in **29%** of these frames; the null manages **6%**.

| Figure | Kit | Score median | Frames with score < 0.1 | Flip margin median | Puck frames in its area | Puck-to-figure median: tracked / null | Within 20 mm: tracked / null | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| W-LD | yellow | 0.22 | 12% | 0.075 | 205 | 35 / 103 mm | 16% / 11% | partly |
| W-RD | yellow | 0.25 | 2% | 0.093 | 344 | 18 / 97 mm | 53% / 11% | **works** |
| W-C | yellow | 0.24 | 2% | 0.100 | 201 | 190 / 193 mm | 0% / 0% | **fails** |
| W-LW | yellow | 0.18 | 13% | 0.057 | 541 | 15 / 149 mm | 69% / 8% | **works** |
| W-RW | yellow | 0.22 | 11% | 0.070 | 82 | 43 / 166 mm | 33% / 12% | works, few frames |
| E-LD | white | 0.19 | 7% | 0.080 | 303 | 42 / 177 mm | 32% / 3% | works |
| E-RD | white | 0.16 | 24% | 0.071 | 37 | 162 / 149 mm | 5% / 0% | fails |
| E-C | white | 0.14 | 36% | 0.049 | 253 | 182 / 167 mm | 0% / 3% | **fails** |
| E-LW | white | 0.22 | 26% | 0.077 | 183 | 229 / 224 mm | 1% / 0% | **fails** |
| E-RW | white | 0.09 | 60% | 0.040 | 381 | 140 / 127 mm | 4% / 3% | **fails** |
| W-G | yellow | 0.23 | 0% | 0.070 | - | - | - | looks right on the sheets |
| E-G | white | 0.13 | 35% | 0.027 | - | - | - | weak |

The puck test is strict: the puck lies in a skater's exclusive area also while it slides through it untouched. That is
why even the good tracks are not near 100%. A fail is a track that does no better than the null.

**By eye** (`validation/own-video-tracks.jpg`, 12 random frames; `validation/own-video-tracks-clip.mp4`, 20 s from
match 60.5 s with a top-down board beside the video): most outlines sit on a figure.
- **The centres:** in the centre crowd W-C and W-RD can both claim the same yellow figure. When W-C moves up its slot
  toward goal.E (x 150-240 mm, where the puck is), the track stays at the back of the slot. The score along W-C's slot
  shows the forward figure as a second peak (0.21 against 0.26 at the back, match 82.3 s).
- **E-LW:** it sits for long stretches on a white patch on the Lidl circle by the near board. That is probably a
  reflection on the near plexiglass, which stays in the frame while the ice-stabilised background does not contain it.
- **E-RW (far board) and E-G:** white on the white boards and next to the goal net. Their kit map is weak (score
  median 0.09 and 0.13).

**Rotation is not usable.** A figure is 20-35 px tall, and the flip margin is a median 0.03-0.10 against scores of
about 0.2. The heading in the file is the best of 12 directions with a smoothness prior, not a measurement. Nothing
checks it.

## 3. Puck

The existing puck track (`puck-track.json`, docs/game-tracking.md) is used unchanged: a logistic classifier on hand
labels and a Viterbi, with the puck seen in 40% of match frames. The NM26 synthetic puck detector (workstream 1) is
trained in the broadcast camera. Using it here would need renders in this camera (section 5).

## 4. What one full period now has

| Track | Coverage | Quality |
| --- | --- | --- |
| Camera | every frame (7,756) | 0.5 px residual; heights by eye |
| Figures | every match frame (7,500 × 12) | positions usable for W-LD, W-RD, W-LW, W-RW, E-LD and W-G; not for W-C, E-C, E-LW, E-RW, E-RD; E-G weak; rotation unusable |
| Puck | 40% of match frames | as docs/game-tracking.md (10/16 spot checks clearly right, 0 clearly wrong) |

## 5. Where the pipeline breaks and what would fix it

1. **White kit on white ice** (E-RW, E-C, E-RD, E-G). The kit map needs foreground AND a white pixel. A white figure
   against the white ice or white boards gives little colour difference, and its shaded side is grey-blue, not white.
   - Same finding as the NM26 goalie pilot: the white end was the hard case there too.
   - **Fix:** a small detector trained on renders composited on plates of this video, with the per-frame camera from
     step 1. It learns the shading and the blue parts instead of a colour threshold. The pipeline for that exists
     (`scripts/synth/render-skater-crops.py`, `train-skater-pose.py`); it needs `bpy` and a few CPU hours, neither of
     which this run had.
2. **Two figures claiming one blob** (W-C / W-RD at the centre; E-C). Each figure is scored alone. The explain-away
   pass with image columns barely changed the result (within-20 mm share 28.8% at a 25% threshold against 28.5% at
   20% with a three times larger penalty).
   - **Fix:** a joint score. Render all twelve figures together with a depth buffer, so each pixel is explained by
     the nearest figure only, and search the poses jointly per frame (or as a 12-figure particle filter).
3. **Static false foreground** (E-LW on the Lidl circle). The background is stabilised on the ice plane, so anything
   that moves with the camera but is not on the ice is foreground: plexiglass reflections, the near board's top.
   - **Fix:** a per-video-pixel persistence mask, or rendered occlusion by the near board and plexiglass. The 3D camera
     makes the second possible once the board and plexiglass heights are known.
4. **Resolution.** 640 × 360 and a figure 20-35 px tall. Rotation needs more pixels: a recording at 1080p or higher, on
   a tripod (docs/game-tracking.md already recommends a fixed camera), would make the NM26 models' crop size reachable
   (80-90 px figures) and remove the stabilisation error.
5. **Puck.** Fine-tuning the NM26 synthetic puck detector needs renders in this camera (as in 1) and labels from
   `puck-labels.json` (1,967 hand labels exist) for a check.

## 6. Assumptions

- The camera intrinsics, one focal length for the video, the calibration's preview scale, goal.W at the left
  (inherited).
- The pivot on the slot centreline (as NM26).
- Figure speed at most 1.2 m/s.
- Kit colour thresholds (HSV) set by eye.
- The kit per end is measured on 300 frames, not user-confirmed: W yellow, E white.
- Accuracy is indirect: the puck consistency test and Claude's look at the sheets, no user labels.
