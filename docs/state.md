# Project state

## Current position

- Last completed iteration: **05 - Trace only the installed board boundary** (2026-09-30), plus the post-05
  decisions of the same day (docs/decisions.md D1-D5). The user delegated the board-trace review to the AI.
  AI review accepted the trace from recorded evidence. No personal user approval is claimed.
- Batch run 06-20 complete. Last completed: **20 - Review the model and incorporate calibration** (2026-09-30). Next: **21** (blocked on user review feedback + a real shot recording).
- **Player figures (user request, done before 21, 2026-09-30):** the skater and goalie proxies and the ten
  placeholders are replaced by two rigid STIGA molds (skater shared by all ten skaters, goalie by both goalies)
  in Sweden/Finland kits, fitted to the user's photos/videos (`references/players_images`) and the official
  overhead: mount socket (fixture axis) under the left skate (skater) / right skate (goalie), stick, blade,
  skates, uniform and back prints. geometry_version **0.6.0**. Details, results and open questions:
  `docs/players.md`. AI review only; no user approval recorded.
- **Figure refinement round 2 (user request, 2026-10-01):** visible-fidelity pass on the skater (arms/torso,
  helmet, face, collar, gloves) and goalie (mask with painted skin gaps, pads, blocker, catcher), block-number
  lettering traced from the photos, calibrated plastic colours; matched-camera close-up sheets including
  held-out views (`validation/players/closeups-{skater,goalie}.png`). Still before iteration 21.
- **Goalie measured (user, 2026-10-01):** height 54 mm, blade 26 x 5.5 mm recorded as `user_measurement`;
  goalie scale and blade set from them (k 1.142); skater scale unchanged (overhead-fitted) until measured.
- **Track fix (user, 2026-10-01):** E-RW and W-RW followed a stick lying on the slot in the official
  overhead; operator occlusion boxes in the tracer straighten them (docs/tracks.md); rink, scene, renders and
  Remotion stills regenerated.
- **Figure refinement round 3 (user request, 2026-10-01):** moulded contours - skater gloves (fists), lathe
  gauntlet cuffs, helmet, face, collar; goalie mask (eye hollows, ridge), skin crescents, pads, catcher (pocket,
  thumb ridge); blue albedo desaturated. Cameras frozen; before/after sheet
  `validation/players/closeups-before-after.png` (held-out views in red). Goalie 54 mm / 26 x 5.5 mm kept.
  Remaining mismatches and next inputs: `docs/players.md`. AI review only. Still before iteration 21.
- **Figure refinement round 4 (user request, 2026-10-01):** skater upper cuff as a broad lofted cuff across the
  chest, moulded gloves with shallow ridges; goalie pads rebuilt as moulded volumes (rounded upper, knee,
  tapered lower), smooth refined skin borders, wider crescents, real neck below the back plate. New view policy:
  inspected views are fitting references; 8 fresh frames scored as INDEPENDENT checks. Silhouette regressions
  reported in `docs/players.md`. AI review only. Still before iteration 21.
- **Figure refinement round 5 (user request, 2026-10-01):** goalie blocker refitted from four front views
  (larger board turned to the front-right, hand holds the paddle behind it, stick heel moved to the photographed
  bend); smooth tapered lower pads; softened skater cuff rim; `finish` data (roughness/clear coat) and new
  close-up lighting (studio HDRI); Remotion figure environment map for the metal sticks. Skater scale frozen.
  Neutral-shape and final-material before/after sheets; silhouette results in `docs/players.md`. AI review only.
- **Figure refinement round 6 (user request, 2026-10-01, skater only):** boxy helmet without knobs, face moved
  forward with a tapered jaw, rolled collar band lying on the jersey with a front V, flat upper gauntlet over the
  hand. Goalie unchanged; skater scale frozen (height 51.32 mm from the shape change). Clay, material,
  full-figure and Remotion before/after sheets; IoU and remaining mismatches in `docs/players.md`. AI review only.
- **Figure refinement round 7 (user request, 2026-10-02, skater only):** thin collar band projected onto the
  real jersey surface (front V, shoulders, no back-left arc), neck strip visible below the helmet at the back,
  softened helmet corners and crown. Slight silhouette regressions reported in `docs/players.md`. Goalie and
  skater scale unchanged. AI review only.
- **Figure refinement round 8 (user request, 2026-10-02, skater only):** broad but thin collar footprint (three
  conforming strips, measured asymmetric path), level rear helmet edge without the notch, neck column kept below
  it, crown fill removed (top at the profile reading; skater 51.24 mm at the frozen scale). Round 6/7/8 sheets and
  contour overlays; IoU between rounds 6 and 7. AI review only.
- **Figure refinement round 9 (user request, 2026-10-02, skater face only):** wedge-shaped face turned with the
  head (broad under the helmet, narrow chin, level jaw), small nose and mouth line; traced against the front,
  profile and elevated frames. Nothing else changed. AI review only.
- **Figure refinement round 10 (user request, 2026-10-02, skater upper/right cuff only, from 388df23):** cuff
  opening levelled (inner corner lowered ~1.2), elbow tip lengthened, saddle removed from the rim, wrist end
  widened slightly around the stick; boundary/rim overlays and hand-marked rim lines; exposure frozen between
  before and after; former INDEPENDENT frames relabelled regression references. AI review only. No animation.
- **Figure refinement round 11 (user request, 2026-10-02, shared skater face only, from 0227dc6):** the five
  face ellipsoids and the carved mouth are replaced by one continuous lofted face surface
  (`assets/blender/face_loft.py`; `skater.parts.face.face_lofts.envelope`): envelope fitted first without
  features through the frozen cameras, then a shallow nose ridge, faint mouth crease and slight chin relief.
  Demonstrated conflict (not resolved, helmet frozen): the frozen helmet's front edge ends ~1.3-1.8 units higher
  than the photographed skin top, so a forehead band that is helmet in the photos is skin in the model. Helmet,
  neck, collar, body, cuff, pose, scale, axis, stick, materials, lighting and goalie unchanged. AI review only.
  No animation.
- **Figure refinement round 12 (user request, 2026-10-02, shared skater face only, from c54ff1c):** the face
  is now a stack of horizontal cross-sections (`assets/blender/face_sections.py`; `face_loft.py` removed). It has
  a pointed front with a centreline, relief only on the centreline, a rigid jaw tilt, and a face-neck fillet.
  Placement uses landmarks triangulated in the frozen helmet's frame (the whole-figure cameras misplace the head
  by 0.6-3.1 units in several frames): turned 28 deg about the neck axis, nose under the helmet front edge.
  Unresolved: left/right height disagreement and the right-side helmet edge (1.0-1.7 units high; no helmet
  change). AI review only. No animation.
- **Figure refinement round 13 (user request, 2026-10-03, skater head):** root cause of the "weird face" in
  rounds 9-12: the face was turned 28-38 deg under a helmet facing straight ahead, and was fitted through cameras
  that shifted with the head. The helmet and face are now one rigid head (`skater.head_pose`: turned 20 deg left,
  tipped 5 deg forward, no side tilt), with the face centred in a wider front opening. The upper torso and
  collar are raised 1 unit. Cameras were refitted on the body only, then on the final figure. Evidence:
  `data/head-pose-r13.json`. Unresolved: a ~1.5-unit left/right side-view disagreement, and a side tilt known only
  to about +/-10 deg. Silhouette IoU 0.8191 / 0.8071 / 0.8054 (fitted / held-out / regression refs). Skater height 51.09 mm
  (head tip; scale unchanged). Goalie unchanged. AI review only. No animation.
- **Iteration 21 (2026-10-04): observations from one real shot.** Recording "#17 Shovel" (user upload; screen
  recording of a third-party video, full speed then replay; different STIGA table edition and pack). Content
  24.9 fps; segment-1 homography RMS 6.1 px (leave-one-out 13.5 px). Shooter W-C (shovel from the near slot end),
  passer W-RW; events stored as intervals (pass 1.25-1.33 s, reception 1.33-1.40 s, goal entry 1.40-1.53 s, seen in
  the replay only). Record `shots/21-shovel/observations.json`, contact sheet `validation/21-contact-sheet.png`,
  notes `docs/shot21.md`. AI observation, not user-reviewed. No motion fitting or animation. (Goal side corrected
  in iteration 22: the puck enters on the goalie's RIGHT, +y.)
- **Iteration 22 (2026-10-04): constrained reconstruction, ACCEPTED by the user (2026-10-04).** One trace
  `data/traces/shovel-17.trace.json` (`shot-trace/1`, status `accepted`, review recorded). It holds:
  - W-C and W-RW slot arcs and rotations; W-C rotation measured from blade marks (faces back while receiving);
    W-RW backhand release while rotating counter-clockwise (both contacts confirmed by the user);
  - static E-G/E-RD/E-LD;
  - the finite puck with phases;
  - events in source time: release 1.772, reception 1.834, separation 1.855 (rule), goal entry 1.901 s, far corner
    (+y 14.2 mm); all observed events inside their intervals.
  **Assumed value:** the rigid-carry rule sends the shot at 7.0 deg, through the static goalie. On the user's
  answer (puck in the far corner; aim it there), the direction is 11.2 deg, the smallest angle that clears the
  goalie and the far post. The puck brushes W-C's right skate by 2.65 mm as it slides off (skate contact size
  unknown). The replay is no longer used as evidence (user: possibly a different take).
  Main artifact `validation/22-diagnostics.png`; notes `docs/shot22.md`; evaluator `src/model/trace.ts`.
- **Revision 2026-10-05 (user feedback on the playback): W-RW foot drag-back plus the contact-physics rule.**
  - The stick went through the puck in W-RW's drag-back. The prep phase is now rebuilt: at every puck observation
    W-RW's slot position and heading are solved so the puck touches the foot, and between observations the puck
    slides along the figure. At the board end W-RW is turned slightly (+19 / -24 deg). Trace
    `trace.shovel-17.v2`, still `accepted`.
  - New rule in `CLAUDE.md` "Contact physics": no overlap anywhere, ever; whole-trace check every 0.25 ms, 0.1 mm
    tolerance. Now enforced by `tests/shot22.test.ts` and by the Remotion gate.
  - One user-approved exception: the far-corner shot brushes W-C's right skate by 2.65 mm (`inputs.json`
    `approved_overlap_exceptions`).
  - Artifact `validation/22-prep-foot-drag.png`; notes `docs/shot22.md` "Revision 2026-10-05". Iteration-23
    renders regenerated from v2.
- **Iteration 23 (2026-10-04): accepted trace played in Remotion with a fixed camera.**
  - Composition `shot23-shovel-17`: 30 fps, 51 frames, source time 0.5-2.167 s, fixed orthographic overhead
    camera, plain background. `shot23-at-time` renders one diagnostic frame at any source time.
  - Time = start + frame / fps. Each frame's state comes from the pure evaluator (`src/model/shot-pose.ts`); no
    `useFrame`, no clock.
  - The shot refuses to render on a geometry or asset version mismatch (`remotion/asset-manifest.json`, plus a hash
    of the loaded GLB).
  - Checks:
    - contact-time frames match the pure state exactly;
    - 12 frames rendered in two shuffled orders give identical state and PNG bytes;
    - all 51 proof-clip frames equal the pure evaluation.
  - Proof clip `validation/23-proof-clip.mp4`; main artifact `validation/23-diagnostics.png`; notes `docs/shot23.md`.
  - **Next: iteration 24** (slow replay and minimal overlays), after the user reviews the playback.
- **Iteration 24 (2026-10-05): one slow replay and minimal teaching overlays.**
  - Composition `shot24-shovel-17`: 223 frames at 30 fps, oblique benchmark camera. It plays the whole shot once at
    normal speed, then a 1/4-speed replay that pauses 2 s at the reception (`contact.W-C_reception`, 1.8343 s).
  - Overlays: title "#17 Shovel", a speed label, the key-contact explanation during the pause, and a yellow ring on
    the puck.
  - The presentation-time → source-time mapping is explicit data (`data/presentations/shovel-17.presentation.json`,
    `src/model/presentation.ts`). Trace and geometry are unchanged.
  - Checks: normal and replay frames at the same source time give identical state and identical PNG bytes (4 pairs);
    the pause frames are identical; the draft clip's frames equal the pure evaluation.
  - Main artifact `validation/24-comparison.png`, draft `validation/24-draft.mp4`, notes `docs/shot24.md`.
  - **Next: iteration 25** (export and document the first video) after the user reviews the presentation.
- **Iteration 25 (2026-10-05): first reusable video exported.**
  - `validation/25-shovel-17-final.mp4`: 1920 × 1080, 60 fps, H.264 CRF 18, 446 frames, 7.43 s.
  - Content: the approved iteration-24 presentation of the accepted trace v2, rendered directly with Remotion/Three.
    The Cycles benchmark was never run, so there is no switch.
  - Output settings: the prompt's proposal (no settings were agreed), recorded as a presentation choice.
  - Checks: a low-cost draft was rendered and reviewed first; every frame of the draft and the final equals the pure
    evaluation of the trace.
  - Rerender: `npm run video:shovel-17`. Versions, hashes and settings are in `validation/25-export-report.json`;
    notes in `docs/shot25.md`.
  - This is the last numbered iteration. Open items: the renderer decision, real figure measurements, the next shot.
- **Analysis video (2026-10-05, user request after iteration 25): "#17 The Shovel" breakdown.**
  - `validation/analysis-shovel-17.mp4`: 1920 × 1080, 30 fps, H.264, 748 frames (24.93 s); VAR-style story (full
    speed, rewind, pass freeze, reception freeze at the skates, slow-motion shovel, replay).
  - Separate composition `analysis-shovel-17` (`remotion/ShotAnalysis.tsx`); data
    `data/presentations/shovel-17.analysis.json`. Shot timeline, camera track (`src/model/camera-track.ts`) and
    graphics are independent pure functions of the frame. The trace, geometry, models and the earlier compositions
    are unchanged.
  - Checks: every frame's state equals the pure evaluation and every frame's camera equals the camera track
    (`validation/analysis-shovel-17-report.json`); size < 25 MB verified; `tests/analysis.test.ts`.
  - Rerender: `npm run video:analysis-shovel-17`. Notes: `docs/analysis-shovel-17.md`.
- **Spjass (2026-10-06, user request "Create an animation for it", from the user's TikTok): reconstructed and animated.**
  - Source preserved: `references/shots/spjass-tiktok.mp4` (indexed). Take 1 (top-down, unmirrored) calibrated,
    RMS 4 px. Puck tracked; W-C poses from blade-toe marks; E-G from its blade.
  - Trace `trace.spjass.v1`, **proposed** (not reviewed by the user): W-C turns counter-clockwise and flicks the puck
    to its +y side with the back of the blade, then spins clockwise while stepping up its slot and shoots with the
    front of the blade between the goalie and the +y post.
    - Contact checks: no overlap, all 12 figures, every 0.25 ms. Every puck motion change is a named contact (blade,
      blade, goal net) or the fitted ice friction.
    - Agreement: take-1 residuals 0.1-0.3 mm on the sharp frames.
    - Assumptions: the shot direction (corridor centre, 3° from the blurred line), the spin and lunge timing in the
      blur, and the flick contact pose (8.5° from the reading).
  - Video `validation/analysis-spjass.mp4` (composition `analysis-spjass`, 1080p 30 fps, 24.7 s), built from the
    shared `remotion/AnalysisVideo.tsx`. The Shovel composition was refactored onto it; six frames are byte-identical,
    so the Shovel video was not re-rendered.
  - Rerender: `npm run trace:spjass`, `npm run video:analysis-spjass`. Notes: `docs/spjass.md`.
  - **Next:** the user reviews the trace (`validation/spjass-trace.png`, the video). Open points: the shot direction,
    and whether the TikTok's spoken explanation names a different technique.
  - Cross-check (2026-10-06): the NTHF description of the Spjass matches the reconstruction in every step.
- **Näcka (2026-10-06, user request with https://www.puck.no/en/combinations/nacka/): designed and animated.**
  - Sources preserved and indexed: `references/combinations/` (NTHF pages and illustrations for Näcka and Spjass).
    No recording exists: the trace `trace.nacka.v1` (**proposed**) is designed from the description and illustration,
    with the spjass set-up and rates.
  - The move: a clockwise turn, the back of the right skate passes the puck 37.5 mm out to the right, then a
    counter-clockwise turn back with a 43 mm step up the slot; the blade face shoots it into the right corner.
  - Checks: no overlap; the contacts are heel, blade and net only.
  - Assumed: all timing, and the goalie standing toward the left post.
  - Video `validation/analysis-nacka.mp4` (composition `analysis-nacka`). Notes: `docs/nacka.md`. Rerender:
    `npm run trace:nacka`, `npm run video:analysis-nacka`.
- **Invers Kryssar med Velodrom (2026-10-06): sketch approved by the user ("The picture is correct"), then animated.
  v2 the same day after the user's feedback.**
  - NTHF page (no illustration) and the base move saved in `references/combinations/`.
  - Approved sketch: `validation/ikv-sketch.png` (composition `pose-preview`, `scripts/ikv-sketch.py`).
  - v1 (superseded): the back of the left wing's blade flicked the puck into the corner at 4.7 m/s. The user's
    judgement: the puck would bounce, not slide. The left wing must face forward and push the puck into the curve.
    - Example clip for the physics: `references/shots/lw-board-pass-example.mov` (a different combination, indexed).
    - New project rule: `CLAUDE.md` "Slide or bounce". Figure contacts are limited to 500 mm/s impact and board or
      post contacts to 300 mm/s (assumed limits). It is checked as `slide_check`.
  - Trace `trace.invers-kryssar-velodrom.v2` (**proposed**, designed):
    - the right wing pushes the cross pass from the resting puck (impact 42 mm/s);
    - the left wing turns from facing the pass to facing forward and catches it softly (166 mm/s); it slides on the
      board (255 mm/s, glancing);
    - the left wing skates up its slot behind it and pushes it through the curve with the front of the blade: 277 touches,
      peak 93 mm/s, released along the end board at 1.31 m/s;
    - the velodrome passes behind the cage;
    - the right wing gives way down his slot as it arrives (227 mm/s) and turns it into the middle of the goal.
    - Checks: no overlap, 0 unexplained velocity changes, slide check passed.
  - **Deviations from the sketch:**
    - the left wing receives near the blue line and carries the puck into the corner;
    - the right wing receives about 26 cm from the goal line, not 18 cm.
  - Assumed: the slide limits; the catch; release at 1.3 m/s (the example looks about 1.0 m/s, uncalibrated); the
    goalie toward the left post; all timing.
  - Video `validation/analysis-ikv.mp4` (composition `analysis-ikv`, 29.7 s). Notes:
    `docs/invers-kryssar-velodrom.md`. Rerender: `npm run trace:ikv`, `npm run video:analysis-ikv`.
- **Defending against the left wing (2026-10-06): concept video of three defences, from the user's TikTok.**
  - Source: `references/shots/defence-vs-left-wing-tiktok.mp4` (indexed). Narration read from the burned-in captions.
    The centrifuge comes from `references/combinations/bordshockeyskolan-lektion-3-centrifugen.html`.
  - The three defences:
    - **passive / the box:** the defender in front of the goal on the straight-shot line, the goalie in the middle;
    - **active:** the goalie turned with its back to the corner, covering as much of the far side as it can while
      every straight shot is still stopped (y = −10 mm, heading about 340°; four user corrections and a scan,
      2026-10-06), the defender out cutting the passes;
    - **the mix:** switching between them.
  - Trace `trace.defence-left-wing.v1` (**proposed**, designed). E-RD and E-G move between the set-ups. The puck stays
    on W-LW's blade.
  - The attacker's options are lanes swept with the finite puck: the straight shot, the centrifuge pass and the
    centre's shot. They are drawn as graphics, open or crossed out where first stopped.
  - The user approved the goalie pose (`validation/defence-goalie-review.png`: "Lets implement the video!") before
    the full render.
  - Video `validation/analysis-defence-lw.mp4` (composition `analysis-defence-lw`, 35.4 s, 3.81 MB).
    - Render report: 1061/1061 frames equal the pure evaluation; the camera is within 0.005 mm of its track. Notes:
    `docs/defence-left-wing.md`. Rerender: `npm run trace:defence-lw`, `npm run video:analysis-defence-lw`.
  - `remotion/AnalysisVideo.tsx` gained a `lane` graphic. The other four analysis videos are verified byte-identical
    on six frames each; recorded as `composition_refactor` in their reports.
- **Game mechanics (2026-10-07): ITHF rules and one recorded match, documented, nothing built.** The user asked for
  a full understanding of the game before anything more complex, and to ask rather than assume.
  - Sources (indexed): `references/rules/ithf-game-rules.pdf` (ITHF Game Rules, valid from 21 Aug 2023) and
    `references/games/fylling-vs-moe-trondheim-open-2022-final.mov` (one full match, handheld phone, 640 × 360, 25 fps).
  - `docs/game-mechanics.md`: a rules digest for analysis, the match as states, the established video facts, the
    unclassified hand episodes, why this angle is hard, and 10 questions for the user.
  - Established from the audio timer: the match runs from video time about 7.5 s to 307.5 s (start and final tone
    300 s apart, interval signals at 107.8 s and 207.7 s, music in the last 30 s). The puck rests on the centre spot
    before the start.
  - User answers A1-A10 (same day): Fylling is the left player; 1-1 after 5 min, Fylling won 2-1 in overtime (the
    overtime is not in the recording); no calls; same table layout as the repo's model; "puck on a player" = the
    figure's area, i.e. no other figure can reach the puck.
  - Five hand episodes inspected: hands at figures (one is the left player adjusting his own goalie at 176.8-177.4 s),
    the puck twice behind the right goal; none is a goal. **The two regulation goals are not located yet.**
  - Second answers A11-A15: the possession count is per skater (goalies not counted); the measures are time and
    number of times; a stoppage of more than 10 s puts the puck on nobody, a shorter one leaves it on the controlling
    figure. Definition in docs/game-mechanics.md section 6.
  - Open: Q11 (the goal times; the user will check) and Q16 (a long stoppage: on nobody from its start or from 10 s
    on).
- **Match tracking, first version (2026-10-07, user: "Start the tracking without those answers"). PROPOSED.**
  - Pipeline `npm run game:track`:
    - stabilisation of every frame;
    - rink-plane calibration to the repo geometry (goal.W at the video's left, assumed from symmetry);
    - puck candidates, a logistic classifier on 1967 hand labels, a Viterbi track (puck seen in 40% of match frames);
    - possession per skater by exclusive reach areas (A10-A15).
  - User settings (A17, A18): minimum episode 0.5 s, maximum gap 7 s.
  - Result `validation/game-possession.png`, `data/games/fylling-vs-moe-2022/possession.json`: Fylling
    121.9 s / 51 times, Moe 81.8 s / 39, nobody 96.3 s.
  - Review (`review.json`): 10/16 tracked spot-check frames clearly right, 0 clearly wrong; of 22 checkable episodes 8
    consistent, 7 plausible, 5 not verifiable, 2 probably wrong (false detections on the near board edge).
  - Passes (`passes.json`): Fylling 17 passes / 13 lost, Moe 10 / 10 (assumed definition).
    Pass lines are straight-line fits to the puck detections, from a detection in the passer's reach to one in the
    receiver's reach, with board bounces; 25 of 50 have a measured line, the rest are hidden and not drawn.
  - Interactive board page `validation/game-possession-board.html` (`npm run game:board`; published as a private
    artifact for the user). Figure poses on it are illustrative, not tracked.
  - Weaknesses and next steps: `docs/game-tracking.md`. Stoppages (goals, face-offs) are not detected yet.
- **NM 2026 semi-final, Nygård vs Fjermestad (2026-10-07): all seven games added by the user (GitHub release, not in
  git; indexed by URL and sha256).** Game 1 investigated for exact pass mapping; nothing built yet.
  - Findings: game 1 runs from about 22 s to about 535 s of the video (3-3, then Fjermestad's overtime goal); all
    frames register to the table; the puck is a clear disk at rest and a grey smudge in flight; about 0.6 / 1.5 mm per
    px.
  - Recommendation: a scripted two-kind puck detector plus a motion tracker, flights fitted between contacts, and a
    user confirm page.
  - Investigation: `docs/nm26-game1-investigation.md`.
  - **Game 1 pass mapping, first version (PROPOSED, `npm run nm26:g1`, `docs/nm26-passes.md`):**
    - calibration: slot fit median 0.86 px;
    - puck positions in 73% of frames;
    - candidates: 67 passes, 64 turnovers, 13 shots.
    - The review page `validation/nm26-g1-review.html` (artifact with a `db`) collects the user's verdicts and missed
      passes.
    - **Claude's review (2026-10-08, PROPOSED, `data/games/nm26-semifinal/g1/review-claude.json`):** all 136
      candidates judged from image rows, each with a confidence 0-100. Result: 74 correct, 15 fix, 24 wrong, 23 unsure;
      92 below 50. The user asked for it and said their own 10 marks were not done properly, so these 10 were
      re-judged too. The page now shows Claude's verdict, sorts and filters by confidence, and has "Use Claude's
      answer" and "Clear my mark" buttons.
    - Main error sources found: stoppages with a hand in the rink (8), out-and-back tracking jumps with few detections,
      and moves split mid-flight. Next: the user checks the low-confidence cards; then build the confirmed pass map and
      add stoppage removal and jump rejection to the pipeline.
- **Playbook (2026-10-08, `docs/table-hockey-playbook.md`):** how the game is played beyond the written rules, for
  future projects.
  - **Sources:** the NTHF combination catalogue (121 moves, parsed to `data/combinations/nthf-catalogue.json`), all 46
    Bordshockeyskolan lessons and the NTHF timer page (all saved under `references/` and indexed), the repo geometry, the
    NM26 measurements and the user's TikToks.
  - **Contents:** figures and slots, 1-on-1 matchups, build-up from each defender, keeping the puck, the attacking
    families with their feint pairs, defence (Box, Flipper, mix), the catalogue by family, top-level play, and a
    vocabulary with source-attested Swedish and Norwegian terms.
  - **Open:** the catalogue's "forward/back" definition contradicts its own example.
- **NM26, how the game works (2026-10-08, `docs/nm26-game-patterns.md`):**
  - **Ends and kit colours:** the figures stay with the table ends: white/blue at the left end, yellow at the right.
    - The players switch ends 2-2-1-1-1, so Nygård plays the yellow figures in games 3, 4 and 6.
    - The score box counts goals by end. Read that way, all seven results match the user's.
  - **Game structure:** timer tones give 5-minute games; game windows and every goal (41) are in
    `data/games/nm26-semifinal/timeline.json`.
  - **Tracking:** all seven games are tracked on one calibration (games 2-7 register to game 1's reference frame;
    `calibration_from` in `config.json`). Patterns are in `data/games/nm26-semifinal/patterns.json`
    (`npm run nm26:patterns`), with control maps `validation/nm26-control-*.png`. All PROPOSED.
  - **Main patterns:**
    - left defence → left wing is the standard outlet for both players;
    - the left wing holds the puck in the attacking corner, and the opponent's right defence wins it back;
    - Nygård plays through his left wing (19% of all puck time, median hold 3.3 s; rim passes right wing → left wing);
    - Fjermestad uses both wings evenly;
    - leads don't hold: the first scorer won 2 of 7 games.
  - **Open:** game 1 ran 360 s before play stopped, not 300 s; the two Nygård goals 3 s apart in game 1; exact goal
    moments; the 21 s centre-spot wait before overtime.
- **Synthetic goalie-pose pilot (2026-10-09, `docs/synthetic-goalie-pilot.md`, PROPOSED):** renders of the 3D model
  in the NM26 broadcast camera train a goalie-pose network with no hand labels.
  - **Camera:** `data/games/nm26-semifinal/camera-ref.json` (assumed; decomposed from the ice-plane calibration, one
    degree of freedom fixed; serves all seven games after registration).
  - **Scripts:** `scripts/synth/` (renderer, compositor on real clean plates, trainer, silhouette fitter, real
    evaluation). Renders, plates and the model are generated under `out/synth/` (not committed).
  - **Results:** synthetic validation θ median 1.2°, u error 0.8 mm. On 120 real crops (no labels): slot position
    agrees with a silhouette search to 5 mm median; rotation axis 12° at E (yellow) but 31° at W (white), with
    front/back jumps at W. Overlay `validation/synth-goalie-pilot-real.jpg`.
  - **User labels (2026-10-09):** the user marked the facing of all 200 crops on the label page
    https://claude.ai/artifact/PZYZ99CUBmmQkp8pjKnbr6 (`data/games/nm26-semifinal/goalie-facing-labels.json`,
    `scripts/synth/goalie-facing-eval.py`). Model facing error: median 19° (E 14°, W 23°); front/back wrong in 4.5%
    (E 0%, W 9%, one recurring W pose: `validation/goalie-facing-worst.jpg`).
  - **White-goalie fix (2026-10-09, user request):** the NM26 W goalie has blue legs/pads, a "1" back print and a darker
    blue (renderer option `W nm26`, assumed from crops); 2,500 new W renders; model C (`out/synth/goalie-pose-v2c.pt`,
    renders + the user's labels of games 1, 2, 4, 6, slot targets from the renders-only model). On the held-out games
    3, 5, 7: facing median 5° at both ends, no front/back errors, no jumps in 10 s of video; slot within 4-6 mm of the
    silhouette search. Before/after: `validation/goalie-facing-fixed.jpg`.
  - **Correction:** the first run's synthetic validation was all E (seeds ending in 9 are odd).
  - **Open:** label precision not measured; test set small (88 crops); slot position not user-checked.
- **Skater poses (2026-10-09, `docs/synthetic-goalie-pilot.md` section 5, PROPOSED):** 6,000 skater renders (NM26 kit
  blue), the user's 352 real skater labels, model v2b (`out/synth/skater-pose-v2b.pt`, predicts the pivot pixel and
  the rotation). On held-out games 3, 5, 7: rotation 7° median, no front/back errors, slot position 1.3 mm from the
  user's feet taps. Sheet `validation/skater-pose-v2b-real.jpg`. Next: run it over the Edwall hat-trick frames.
- **Figure tracks, all seven NM26 games (2026-10-10, `docs/nm26-figure-tracks.md`, PROPOSED):** both models over every
  game (5 fps; 30 fps around goals; 23,756 frames). Pivot median 3-4 mm from the slots; ~6% slot and ~4% rotation jumps
  at 30 fps (needs smoothing). Findings: the scoring centre's position separates the combinations (Spade at the back
  of the slot, centrifuge at the front, short centrifuge in between); the Edwall hat-trick has one repeatable setup.
  Cleaned tracks (`figure-tracks-smooth.json`, `scripts/synth/smooth-tracks.py`): jumps at 30 fps from ~7% to ~0.8%.
- **First real goal to rebuild (2026-10-09, user's choice):** Nygård's three "Edwallskyffel lang" goals in game 2
  (`docs/rebuild-g2-edwall.md`). Evidence packs (frames, puck track, goalie poses) are built; skater poses and a
  frame-by-frame puck read come next. Goal review page (user labels, 25 of 40 so far):
  https://claude.ai/artifact/8CQAfC4k7Qjrmnz573zLUT → `data/games/nm26-semifinal/goal-labels.json`.
- **Parallel batch 2026-10-10 (eight workstreams), consolidated on branch `claude/consolidation-batch-2026-10-10`.
  Everything below is PROPOSED model output or design; nothing is user-confirmed except the Hjerpefinte reading. Not
  merged to main.** The old inputs stay in place: `<game>/puck-track.json` and `<game>/figure-tracks(-smooth).json` are
  unchanged, and no downstream analysis was re-run on the new tracks at consolidation.
  1. **Synthetic puck detector** (`docs/synthetic-puck.md`): Blender puck renders composited on real frames train a
     detector; all seven games re-tracked to `<game>/puck-track-synth.json`. Live-play coverage 70.3% → 76.4%; last
     2 s before the 25 marked goals 78.0% → 84.3%; no impossible steps (old 0.3%); Claude's 56-frame review: on the
     puck about 89% (old 78%). Shot flights are still missed (real smudge recall 44%). **x/y is the puck centre, about
     13 mm nearer the camera (−y) than the old blob convention.** Recommended to replace `puck-track.json` (not done).
  2. **Edwall hat-trick rebuild v2** (`docs/rebuild-g2-edwall-v2.md`): traces `data/traces/edwall-g2-goal{2,3,4}.trace.json`
     pass the contact and slide checks; videos `validation/analysis-edwall-g2-goal{2,3,4}.mp4` (own Remotion entry
     `remotion/edwall-index.ts`, `node scripts/edwall-render.ts <goal>`). Fails its own carry-force check in all three
     (the carry is kinematic: no heel groove in the figure geometry); the shot is hidden and designed (goal 4 shoots
     with the back of the figure); the puck's rest is probably 44 mm off (snapped to the board; the detector and the
     hand readings agree on y ≈ −178).
  3. **Combination recognition** (`docs/nm26-combinations.md`, `scripts/nm26-combo-recognition.py [--puck <file>]`):
     vote of tree, 1-NN and playbook rules 23/25 leave-one-out at the user's goal moment (20/25 at the estimated
     moment); PROPOSED labels for the 15 unreviewed goals in `combo-labels.json` (11 high, 4 medium). The two
     single-example families (wing goal, rebound) are always missed.
  4. **Tracker v3** (`docs/tracker-v3.md`, `scripts/synth/track-figures-v3.py`): candidates + presence output + temporal
     decoder; `<game>/figure-tracks-v3.json` for all seven games (same columns as `figure-tracks-smooth.json`). On the
     labels gross slot errors 0.9% → 0.3%, flips 0.3% → 0; in 48 goal-window disagreements v3 right 31, v2 right 2
     (Claude's visual check). Rotation of the rebuilt model 8.3° vs v2b 7.0°. Recommended to switch readers to v3
     (not done).
  5. **All-goals replays** (`validation/replays/README.md`, `scripts/nm26-replays.py`, `npm run nm26:replays`): 40
     top-down replays with registered broadcast clips and a phone review page (`validation/replays/index.html`,
     37.5 MB). Built from the old puck track and the v2 smoothed tracks; g4-goal5 has no box time and no replay.
  6. **Own-video tracking** (`docs/own-video-tracking.md`, `scripts/own-video-*.py`): per-frame camera for the handheld
     match (f 518 px, residual 0.48 px) and analysis-by-synthesis figure tracks
     (`data/games/fylling-vs-moe-2022/own-video/`). Positions usable for W-LD, W-RD, W-LW, W-RW, E-LD (and W-G); they
     fail for both centres, E-LW, E-RW, E-RD; rotation unusable at 640 × 360.
  7. **Tests and reproducibility** (`docs/pipeline.md`): 36 Python unit tests in `tests/synth/` run by `npm test`; the NM26
     rebuild runner `scripts/pipeline/nm26_rebuild.py` (`npm run rebuild:nm26*`), verified from a fresh container (40
     outputs byte-identical). Models are not rebuildable: the `.pt` files are not committed, the training command lines
     were not recorded, and the goal-box plates have no script.
  8. **Vision and shot encyclopedia** (`docs/vision.md`, `docs/shot-encyclopedia.md`): 12 ranked directions (the user
     chose the encyclopedia); move engine `scripts/shotlib/`, move files `moves/<id>/move.json`, `scripts/build-move.py`,
     contact footprints, robustness check, generated videos (`move-<id>` compositions via `remotion/encyclopedia-registry.ts`),
     index of all 121 NTHF moves (`data/encyclopedia/index.json`). The engine reproduces the IKV trace exactly. New move
     Hjerpefinte (`validation/moves/hjerpefinte.mp4`): reading approved by the user 2026-10-10 (same stance threatens a
     Hjerpe so the goalie opens the right corner); the goalie lean (+28 mm) is assumed; the trace stays proposed.
     Finding: IKV v2 holds in only 1 of 11 robustness variants (fixed-clock chain).
  - **Consolidation (2026-10-10):** the eight branches merged in order with no textual conflicts. Added to the runner:
    the puck-detector and tracker-v3 model steps, a new default stage `analysis` (combination recognition, puck-track
    comparison), the replays in `pages`, a non-default stage `edwall`, and a SOURCES entry for Claude's puck review
    (`docs/pipeline.md` section 5). `assets/blender/__pycache__/*.pyc` removed from the index. Checks: `npm run check`
    165/165 tests pass (typecheck and validate pass); Python tests 36/36; the `analysis` stage and the Edwall video specs
    rebuild byte-identical; the Hjerpefinte move rebuilds identically (except the recorded git commit).
  - **Next (recommended):** switch to `puck-track-synth.json` and `figure-tracks-v3.json` and re-run passes, combinations
    and replays (with a ~100-tap user truth set); solved receptions in the move engine; publish the trained `.pt` models
    as release assets with their sha256.
- **NM26 on the new tracks (2026-10-10, step 1 of the consolidation summary, branch `claude/switch-new-tracks-0nujjo`,
  `docs/nm26-new-tracks.md`, PROPOSED):** the analysis reads `puck-track-synth.json` and `figure-tracks-v3.json`
  (`scripts/nm26_tracks.py`; a `slow` flag replaces the old `disk`). Re-run: passes, patterns, figure analysis,
  combinations, the 40 replays, the Edwall refit. Fewer, longer flights (shots 61 → 49, battles 482 → 338); the two
  tracks agree on only about a third of the passes; a shot in the last 2 s before a user goal 3/25 → 1/25. Combination
  vote at the user's moment 23/25 unchanged, at the estimated moment 20 → 18 (goal-moment median error 0.32 → 0.78 s,
  replay rule tuned on the old track); eight PROPOSED label changes. Edwall: goal 3 rebuilt as v2 (rest on the readings,
  blade shovel; carry-force check still fails); goals 2 and 4 found no scoring v2 fit and stay v1. Thresholds not
  retuned. **User taps done (2026-10-10,** 96 frames where the tracks disagree,
  `validation/tap-review/results.json`): figures v3 26/30 right vs old 1/30 (median 7 vs 94 mm); puck new 32/63 vs old
  18/63, median 10 vs 34 mm where a position exists, last 2 s before goals 7/10 vs 1/10. Both tracks still report a puck
  the user could not see in about 2/3 of the "none" frames (next: the detector's false alarms). Taps mark the visible
  puck centre, scored after moving them up the documented 8.8 px. Edwall videos not re-rendered.
- **Puck at the shot (2026-10-11, thread "Puck at the shot", `docs/synthetic-puck.md` section 8, PROPOSED):** a second
  puck track `<game>/puck-track-synth-v2.json` (tracker 2 on the v1 detector) and its `<game>/passes-synth-v2.json`, beside
  v1; the analysis is NOT switched (v2 ties on shots). Tracker 2 removes still low-score runs (dark ice marks: the ISOVER
  "o" at the W near board, the centre spot) and re-tracks: false alarms on the user's "not in this picture" taps 13 → 4
  of 21, tap frames right 32 → 41 of 63, median error 10 mm unchanged, coverage 76 → 70% of live play (28-row review: 2
  removed rows were the puck). Shots before the 25 user goals stay 1/25: the broadcast does not show most shots (the puck
  vanishes under the shooter's blur and behind the goalie in 1-3 frames). A fine-tune on 800 shot renders (detector v2,
  not adopted, `/mnt/project-files/puck-det-v2-workdir/`) and a shot-completion rule (8/25, but every added position on
  the goalie or a figure; off, user asked) did not change that. Scores: `validation/puck-track-v2-eval.json`.
- Geometry version: `0.5.0` (`data/geometry.json`). Board boundary, all 12 slots and both goal regions traced in pixels;
  goal setup = without inserts (user). No meshes or movement.
- Animated shots: the iteration-23 playback (`shot23-shovel-17`) and the iteration-24 presentation (`shot24-shovel-17`) of the accepted trace.

## Batch run result (docs/autonomous-run.md)

**Batch 06-20 finished 2026-09-30: all iterations completed with recorded verification. Stopped after 20 as instructed.**
No animated shots were started. **Iterations 21-25 done (see above): the first video is exported. No further numbered iteration is defined.**

Iteration 20 closed without repair cycles:
- [x] Intake recorded: nothing supplied; checks re-run (84/84 tests, validate).
- [x] Reprojection check: slots mean offset <= 1.7 px, ice edge median 0.75 px (pipeline consistency only).
- [x] Review sheet validation/20-review-sheet.png (matched overhead; side/oblique qualitative; blade/puck provisional), AI-reviewed; geometry and appearance reported separately.
- [x] Output 1920x1080 proposed; the one-output-pixel claim is explicitly NOT supported.
- [x] Remotion/Three judged below photorealism; a bounded Cycles benchmark task specified, not started, no pipeline switch.
- [x] Four separate statuses and the required inputs in docs/review.md; user approval NOT recorded.

## Verification status

| Item | Status |
| --- | --- |
| PDF text and hyperlinks | Extracted (iteration 01). PDF unchanged, SHA-256 `1c7355ef...9a4cc`. |
| Embedded images | All 10 extracted to `references/originals/` (7 JPEG byte-identical to the PDF's DCT streams, 3 lossless PNG). Native sizes verified against captions. SHA-256 in `references/index.json`. |
| View identities | Confirmed by viewing each image (downscaled previews) plus two native-resolution crops. |
| Remote originals | **Not obtained.** Network policy blocks `stigasports.centracdn.net`, `www.stigasports.com`, `www.stigacanada.ca`, `d.otto.de`, `www.ithf.info` (curl CONNECT 403; WebFetch EGRESS_BLOCKED). Byte identity with remote files unverified. |
| Tooling (iteration 03) | `npm ci`, `npm run typecheck`, `npm run smoke` all run and pass (clean reinstall from lockfile). Typecheck confirmed to fail on a deliberate type error. Smoke SVG rendered in headless Chromium and viewed. |
| Geometry contract (iteration 04) | `npm run check` passes: typecheck (incl. tsc cross-check that runtime schema matches the interfaces; a removed field was confirmed to fail), `npm run validate` (schema + policy + reference hashes), 15 policy tests (canonical file valid; 12 invalid mutations rejected; similarity-uniformity helper). |
| Board trace (iteration 05) | 1431/1440 rays detected and consistent; 2 short interpolated stretches. Fit RMS <= 2.73 px (long sides bow outward up to 10.1 px; quadratic RMS <= 0.49 px); corner radii 610-625 px. Trace uncertainty 21 px (dominated by the ~15 px dark strip at the board base); uniform-mapping bound 16.5 px. Rerun reproduces byte-identical outputs. Overlay rendered in headless Chromium and inspected by me (corners, landmark, gap insets). |
| Post-05 review evidence | `node scripts/check-board-evidence.ts` -> `validation/05-evidence-check.json`. Strip width 7.3-8.1 px per 1000 px radius (vertical board face). Marking lines bow 19% / 47% of the lens-model prediction (lens explains only part of the board bow). `npm run check` passes (18 tests). |
| Slot traces (iterations 06-08) | 12 paths x 2 photos. Overhead fit RMS <= 0.74 px, width 38-40 px; bare->overhead homography over 10 outfield slots RMS 2.54 px (goalie slots excluded: symmetric ~7 px offset); every hidden end extends forward (+22 to +167 px). Goal cut-outs mapped onto goal lines within 8 px. Overlays 06/07/08 AI-reviewed. 23/23 tests. |
| Pose maths (iteration 09) | 10 pose tests pass (continuity on all 12 paths, boundaries, 360 deg, known point, handedness det +1, goalie adapter, glTF adapter). Debug SVG AI-reviewed. |
| Contacts (iteration 10) | Provisional debug contacts for W-RD only; rigidity, rotation and handedness tests pass; review sheet AI-reviewed. Real pivot, blade and skate values UNKNOWN. |
| Blender (iteration 11) | bpy 4.5.14 LTS (PyPI) in /root/venvs/blender; Cycles CPU. Rink built headless; GLB bounds and ID-render scale checks pass (tests 40/40). See docs/blender.md. |
| Figure molds (2026-09-30) | `npm run check` passes (73 tests: typecheck, validate, figures/assembly/appearance/Remotion tests). Silhouette IoU skater 0.808 (7 views) / goalie 0.816 (8 views); overhead k = 1.071 mm/mold unit (4 Sweden skaters, IoU 0.69-0.79); stick check within 1.5 mm; assembly without intersections; Remotion import checks pass; reprojection worst slot mean 0.80 px (check made colour-aware: figure plastic over the E-G slot, recorded in scripts/review-reprojection.ts). Renders inspected (AI review). |
| Dimensional accuracy | Goalie height and stick blade measured by the user (2026-10-01). Everything else not measured. All sizes are `catalog_nominal`, `assumed` (preview scale) or `unknown`. |
| Batch consolidation (2026-10-10) | Branch `claude/consolidation-batch-2026-10-10`: `npm run check` passes (typecheck, validate, 165/165 tests, including the 36 Python tests in `tests/synth/`). Rebuild runner: `analysis` stage and Edwall video specs byte-identical to the committed files; model, video and mesh steps not run (no video, Blender or PyTorch in that container). |
| NM26 new tracks (2026-10-10) | Branch `claude/switch-new-tracks-0nujjo`: `npm run check` passes (typecheck, validate, 165/165 tests; Python tests 43/43 incl. 7 new track-selection tests). `npm run rebuild:nm26:analysis` reruns cleanly (its outputs differ from main by design). Old inputs reproduce the old outputs (env override). Edwall goals 2 and 4 v1 traces rebuild identical apart from the git commit. Not run: Edwall videos, g1 review page, evidence sheets. Taps pending. |

## Key decisions

- Figures (2026-09-30): one skater mold and one goalie mold (user statement: every skater identical; teams
  differ only in kit colour and country name). Team W = Finland kit, E = Sweden kit (D4). Figure scale from the
  official overhead at the assumed preview scale, shared by both molds (`assume.figure_mold_scale`); the
  iteration 13-15 proxies, debug contacts and their scripts were removed (git history keeps them).

- Sponsors dropped (user, D6, 2026-09-30): the ice carries hockey markings only; the reference print is kept as `assets/rink/textures/ice_basecolor_reference.png`.

- Target family 71-1145-XX; Sweden/Finland 71-1145-01 public gallery is the reference variant until
  the user supplies their own parts/teams/artwork.
- Conflicting overall lengths (960 vs 940 mm) are kept separate, not averaged. The approx. 845 x 457 mm
  playing area is not stretched to a housing size.
- Bare-sheet photo (older artwork, may extend beneath the boards) is for slot topology only, never
  for scale or installed-rink artwork.
- The PDF-embedded gallery images (5154-5636 px) are the working originals; remote downloads are only
  needed for byte-identity verification, not for tracing.
- Figures are rigid; motion data stays separate from camera and presentation (see CLAUDE.md).
- Tooling: npm + TypeScript 7.0.2 typecheck only; Node 22.18+ runs `.ts` directly (erasable syntax,
  `.ts` import extensions). No tsx/ts-node, Remotion, bundler or test framework yet. See `docs/tools.md`.
- Geometry: world mm, origin at the centre of the inner board boundary on the ice top (z = 0), +x toward
  `goal.E` (image-right of the official overhead), +y toward its image-top side, +z up. Teams named by
  side (`W`, `E`); reference variant Finland = W, Sweden = E. Details: `docs/geometry.md`.
- The runtime schema is hand-written typed combinators (no JSON Schema dependency); tsc enforces that it
  matches the TypeScript interfaces.
- Catalog values imported as `catalog_nominal`: housing claims 960 x 500 and approx. 940 x 502 x 83 (unresolved
  conflict), playing area approx. 845 x 457, skater figure height approx. 57 (datum unknown; not applied to
  goalies), end screen approx. 70 x 622 (length datum unknown), puck diameter approx. 25.4. Everything else null.
- No preview scale chosen in iteration 04. Iteration 05 added `map.overhead.preview`: ASSUMED uniform 0.179597 mm/px
  (catalog approx. 845 mm = traced length 4705 px). Implied width 468.8 mm vs catalog approx. 457 mm - reported, not
  forced. The mm outline (`board.inner_boundary.world`) is `assumed`; corner radius and board length in mm stay unknown.
- Board trace = ice side of the near-black strip at the board base (`assume.board_edge_is_ice_contact`); not the
  top rail, housing or loose-sheet perimeter. Method and checks: `docs/board-trace.md`.
- Observations to carry forward: long sides bow outward (lens or real boards, unresolved); every marking line
  leans ~0.35 deg relative to the board axis (sheet possibly rotated in the boards); ~0.5% keystone left-right.
- Image decoding in TypeScript uses jpeg-js (devDependency).
- Goal setup: without inserts or goal cups, screens kept (user, D5). Team/position convention unchanged (user: keep it consistent, D4).
- Planned structure: `references/`, `data/`, `src/model/`, `assets/`, `validation/`, `docs/`.

## Before iteration 06

- Board-trace review: done by AI review under delegation (D1-D3). The user may still override it.
- Iteration 06 traces tracks in the same overhead. Per D3, tracks follow the printed sheet (possibly rotated ~0.3 deg
  in the boards) and are not straightened to the board axis.

## Missing inputs (most important first)

1. Empty installed rink, perpendicular overhead, with scale markers in both directions
   (inner board boundary, track centrelines, slot ends).
2. **(critical, blocks shot accuracy)** Loose and installed figures with scale: fixture pivot, blade offset/profile, stick handedness,
   skate contacts, ice clearance, figure-height datum. No loose-figure views exist at all
   (full list under `missing_views` in `references/index.json`).
3. Travel stops and rod push/pull + twist recordings per control type (goalie, wing with link 7A,
   defence, centre).
4. Puck thickness, diameter, rim profile, mass; goal size, posts, clearance.
5. The user's actual teams/artwork. (Goal configuration now known: without inserts, D5.)
6. Blocked downloads: full manual A06 (`d.otto.de`), ITHF Tournament Rules (`www.ithf.info`; the Game Rules were
   fetched on 2026-10-07), the 1001 x 603
   older-artwork overhead (`www.stigacanada.ca`; not in the PDF). Allow these hosts in the cloud
   environment's network settings, or upload the files to `references/originals/`.

## Review artifacts

- **NM26 new tracks (2026-10-10, PROPOSED):** `docs/nm26-new-tracks.md`, tap page https://claude.ai/artifact/21hTqYXsKVvuYDcZHGuWXp
  (`validation/tap-review/`), `validation/nm26-track-switch.json`, `validation/edwall-g2-goal3-trace.png`, `validation/replays/`.
- **Batch 2026-10-10 (all PROPOSED):** `validation/analysis-edwall-g2-goal{2,3,4}.mp4` (with `-review.jpg`,
  `-report.json`; `edwall-g2-goal*-trace.png`), `validation/moves/hjerpefinte.mp4` (sheet
  `validation/moves/hjerpefinte-sheet.png`), `validation/replays/index.html` (40 goal replays and clips),
  `validation/synthetic-puck-*.jpg`, `validation/tracker-v2-v3-*.jpg`, `validation/nm26-combo-spots.png`,
  `validation/own-video-tracks.jpg` and `own-video-tracks-clip.mp4`. Notes: the docs listed in "Current position".
- **`validation/analysis-ikv.mp4`** - Invers Kryssar med Velodrom analysis video, with `analysis-ikv-review.png`,
  `analysis-ikv-report.json`, `analysis-ikv-occlusion.json`; sketch `validation/ikv-sketch.png`; trace sheet
  `validation/ikv-trace.png`. Notes: `docs/invers-kryssar-velodrom.md`.
- **`validation/analysis-nacka.mp4`** - Näcka analysis video, with `analysis-nacka-review.png`,
  `analysis-nacka-report.json`, `analysis-nacka-occlusion.json`; trace sheet `validation/nacka-trace.png`.
  Notes: `docs/nacka.md`.
- **`validation/analysis-spjass.mp4`** - spjass analysis video, with `analysis-spjass-review.png`,
  `analysis-spjass-report.json`, `analysis-spjass-occlusion.json`; trace sheet `validation/spjass-trace.png`;
  observations `validation/spjass-observations.png`. Notes: `docs/spjass.md`.
- **`validation/analysis-shovel-17.mp4`** - analysis video, with `analysis-shovel-17-review.png` and
  `analysis-shovel-17-report.json`. Notes: `docs/analysis-shovel-17.md`.
- **`validation/22-diagnostics.png`** - iteration 22 main artifact (proposed trace, nine stills around release,
  reception and goal entry), plus `22-trace-overview.png`. Notes: `docs/shot22.md`.
- **`validation/21-contact-sheet.png`**, `21-camera-calibration.png` - iteration 21. Notes: `docs/shot21.md`.
- **`validation/20-review-sheet.png`** - iteration 20 main artifact. Review: `docs/review.md`.
- **`validation/19/19-checks.png`**, `19-overhead.png`, `19-side.png`, `19-oblique.png` - iteration 19 Remotion stills. Docs: `docs/remotion.md`.
- **`validation/18-oblique-1080p.png`** and `18-*` close-ups - iteration 18 (assets/scene/full_static_appearance).
- **`validation/17-overhead-vs-reference.png`**, `17-oblique.png` - iteration 17 (assets/scene/full_static_materials, ice texture). Docs: `docs/materials.md`.
- **`validation/16-overhead-labelled.png`**, `16-oblique.png` - iteration 16 (assets/scene/full_static).
- **`validation/15-goalie-oblique.png`**, `15-goalie-side.png`, `15-goalie-top.png` - iteration 15 (assets/figures/goalie_W-G).
- **`validation/14-view-sheet.png`**, `14-silhouette-top.png` - iteration 14 (assets/figures/skater_W-RD). Docs: `docs/figures.md`.
- **`validation/13-contacts-top.png`**, `13-contacts-side.png` - iteration 13 (assets/figures/skater_W-RD_lower).
- **`validation/12-goal-oblique.png`**, `12-puck-side.png`, `12-overview.png` - iteration 12 (assets/goal, screen, puck, scene/static_hardware).
- **`validation/11-rink-overhead.png`**, `11-rink-side.png` - iteration 11 clay rink (assets/rink/rink.blend, rink.glb). Docs: `docs/blender.md`.
- **`validation/10-skater-contacts.svg`** - iteration 10 (critical checkpoint; provisional contacts). Docs: `docs/contacts.md`.
- **`validation/09-pose-debug.svg`** - iteration 09 (static sample poses). Docs: `docs/pose.md`.
- **`validation/08-goals-and-goalies.svg`** - iteration 08 (12-route inventory, goal regions, unresolved dimensions). Docs: `docs/goals.md`.
- **`validation/07-winger-tracks.svg`** - iteration 07 (4 wingers, sample points, end insets).
- **`validation/06-straight-tracks.svg`** - iteration 06 (both photos, 6 colour-coded paths, 12 end insets, evidence table). Method: `docs/tracks.md`.
- **`validation/05-board-overlay.svg`** - main artifact of iteration 05 (unchanged photo at native size, trace,
  landmark IDs with pixel coordinates, 9 zoom insets, notes). Numbers: `validation/05-board-report.json`.
- `docs/board-trace.md` - trace method, checks, error estimate, assumptions.
- `docs/decisions.md` - decision log (D1-D5); `validation/05-evidence-check.json` - evidence for D2/D3.
- `data/geometry.json` - canonical geometry (iteration 04; all physical unknowns null).
- `docs/geometry.md` - coordinate system, IDs, evidence policy, Blender/glTF/Three adapter.
- `validation/03-smoke.svg` - toolchain smoke diagnostic (iteration 03; not hockey geometry).
- `docs/tools.md` - environment findings; `README.md` - working commands.
- `references/index.json` - source catalogue (main artifact of iteration 02).
- `references/originals/` - the ten recovered images.
- `docs/reference.md` - reference brief, now with recovered assets and manual page numbers.
- `CLAUDE.md` - project instructions.

## Iteration history

| Iteration | Date | Result | Checks run |
| --- | --- | --- | --- |
| 01 | 2026-09-30 | CLAUDE.md, docs/reference.md, docs/state.md | PDF text/link/image-object extraction; page renders viewed; PDF SHA-256 recorded, file unchanged |
| 02 | 2026-09-30 | 10 PDF-embedded images in references/originals/, references/index.json, manual pages 2/18 in docs/reference.md | Byte comparison of extracted JPEGs vs decoded PDF streams (7/7 identical); decoded sizes vs captions (10/10 match); SHA-256 computed; JSON parse check; previews and 2 native crops viewed; download attempts for 5 hosts (all blocked); PDF SHA-256 unchanged |
| 03 | 2026-09-30 | package.json, package-lock.json, tsconfig.json, .gitignore, scripts/smoke.ts, data/fixtures/smoke.json, validation/03-smoke.svg, README.md, docs/tools.md | Environment inspected; `npm ci` clean reinstall; `npm run typecheck` pass (and fails on a probe error); `npm run smoke` pass; SVG screenshot in headless Chromium viewed |
| 04 | 2026-09-30 | src/model/{geometry,geometry-schema,check,validate}.ts, data/geometry.json, scripts/validate-geometry.ts, tests/geometry.test.ts, docs/geometry.md | `npm run check` (typecheck, validate, 15 tests) pass; schema-drift probe fails as intended |
| 05 | 2026-09-30 | scripts/trace-board.ts, scripts/render-board-overlay.ts, src/model/{fit,raster}.ts, data/geometry.json 0.2.0 (trace, 10 landmarks, 4 assumptions, preview mapping), validation/05-board-{overlay.svg,report.json}, docs/board-trace.md; jpeg-js added | `npm run check` (typecheck, validate, 17 tests) pass; tracer rerun byte-identical; source photo hash unchanged; overlay screenshot inspected (main view + insets); user visual approval not received |
| 05+ | 2026-09-30 | User answers recorded: goal setup without inserts, convention kept, review delegated. scripts/check-board-evidence.ts, validation/05-evidence-check.json, docs/decisions.md; `user_statement` source kind; geometry 0.3.0 | Evidence script run; trace rerun (points unchanged); overlay re-rendered; `npm run check` 18/18 pass |
| 06 | 2026-09-30 | slot tracer (src/model/slot-trace.ts, homography.ts, scripts/trace-slots.ts, render-tracks-overlay.ts), data/slot-seeds.json, 12 slot traces + 24 end landmarks, geometry 0.4.0 (fixture_axis_path, identity_evidence, team label, trace stats), validation/06-straight-tracks.svg, slots-report.json, docs/tracks.md | `npm run check` 20/20; overlay AI-reviewed; 2 repair cycles |
| 07 | 2026-09-30 | 4 winger traces (both photos), tracer robustness fixes (06 re-traced), measured bare curve seeds, validation/07-winger-tracks.svg, recording-needs list in docs/tracks.md | `npm run check` 21/21; overlays 06 and 07 AI-reviewed; 2 repair cycles |
| 08 | 2026-09-30 | goalie slot traces, hidden-end handling (all traces refreshed), goal regions (scripts/trace-goals.ts, render-goals-overlay.ts), Goal schema traces/landmarks, validation/08-goals-and-goalies.svg, goals-report.json, docs/goals.md | `npm run check` 23/23; overlays 06-08 re-rendered, 08 AI-reviewed; 2 repair cycles |
| 09 | 2026-09-30 | src/model/pose.ts, paths.ts, coordinates.ts; tests/pose.test.ts; assumption assume.fixture_axis_on_slot_centreline; validation/09-pose-debug.svg; docs/pose.md | `npm run check` 33/33; debug SVG AI-reviewed; 1 presentation repair |
| 10 | 2026-09-30 | scripts/define-contacts.ts, render-contacts.ts; schema (provisional contact shapes, inventory); fig.W-RD inventory + provisional contacts; W-RD stick left; validation/10-skater-contacts.svg; docs/contacts.md; tests/contacts.test.ts | `npm run check` 37/37; sheet AI-reviewed; 1 presentation repair |
| 11 | 2026-09-30 | assets/blender/stiga_blender.py, build_rink.py, verify_rink.py; assets/rink/rink.blend + rink.glb; preview_parameters (schema + data); slot tracer fixes (Hermite gaps, curve-following hidden ends, goalie seeds); validation/11-*; docs/blender.md; tests/rink-asset.test.ts | `npm run check` 40/40; stills AI-reviewed; 2 repair cycles |
| 12 | 2026-09-30 | assets/blender/build_hardware.py; assets/goal, screen, puck, scene/static_hardware (.blend/.glb); hardware preview_parameters; 'ratio' unit; side A and puck sources; geometry 0.5.0; validation/12-*; tests/hardware-assets.test.ts | `npm run check` 46/46; 3 stills AI-reviewed; 2 repair cycles |
| 13 | 2026-09-30 | assets/blender/build_skater_lower.py; assets/figures/skater_W-RD_lower.blend/.glb; contact build sizes; validation/13-*; tests/skater-lower.test.ts | `npm run check` 52/52; close-ups AI-reviewed; 2 repair cycles |
| 14 | 2026-09-30 | assets/blender/build_skater_body.py; assets/figures/skater_W-RD.blend/.glb; traced top silhouette (trace.figure.W-RD...); W-RD inventory (body proxy, mold sharing, skate conflict); validation/14-*; docs/figures.md; tests/skater-body.test.ts | `npm run check` pass; silhouette IoU 0.816; view sheet AI-reviewed; 1 repair cycle |
| 15 | 2026-09-30 | scripts/define-goalie.ts; assets/blender/build_goalie.py; shared metaball/silhouette helpers; assets/figures/goalie_W-G.*; W-G traces/contacts/inventory; goalie_height preview; validation/15-*; tests/goalie.test.ts | `npm run check` pass; IoU 0.794; renders AI-reviewed; 1 repair cycle |
| 16 | 2026-09-30 | scripts/assembly-poses.ts; assets/blender/build_assembly.py; assets/scene/full_static.*; validation/16-*; tests/assembly.test.ts | `npm run check` pass; renders AI-reviewed; 1 repair cycle |
| 17 | 2026-09-30 | assets/blender/make_ice_texture.py, build_materials.py; assets/rink/textures/ice_basecolor.png; assets/scene/full_static_materials.*; validation/17-*; docs/materials.md; tests/materials.test.ts; venv pinned numpy<2 + opencv 4.10 | `npm run check` pass; renders AI-reviewed; 3 repair cycles + 1 failed run (all fixed) |
| 18 | 2026-09-30 | assets/blender/build_appearance.py, render_appearance.py; materials on skater_W-RD, goalie_W-G, puck; assets/scene/full_static_appearance.*; validation/18-*; tests/appearance.test.ts | `npm run check` pass; renders AI-reviewed; 1 repair cycle |
| 19 | 2026-09-30 | remotion/ (index, Root, StaticInspection, cameras, checks); pinned remotion 4.0.531, react 19.2.0, three 0.186.1, R3F 9.4.0; tsconfig JSX/DOM; validation/19/*; docs/remotion.md; tests/remotion-setup.test.ts | typecheck + 83 tests pass; 4 Remotion stills rendered and AI-reviewed; import checks PASS; 2 repair cycles |
| 20 | 2026-09-30 | scripts/review-reprojection.ts, png-read.ts, review-sheet.py; validation/20-review-sheet.png, 20-reprojection.json; docs/review.md; reprojection test | `npm run check` 84/84; review sheet AI-reviewed; 0 repair cycles |
| D6 | 2026-09-30 | Sponsors dropped from the ice (assets/blender/drop_sponsors.py); the 17-20 renders, Remotion stills and review sheet regenerated; .blend1 backups untracked | `npm run check` 85/85; renders AI-reviewed; Remotion import checks PASS |
| 22 | 2026-10-04 | scripts/shot22-trace.py; shots/22-shovel/{inputs,checks}.json; data/traces/shovel-17.trace.json (proposed); src/model/trace.ts; tests/shot22.test.ts; validation/22-diagnostics.png, 22-trace-overview.png; docs/shot22.md; goal-side correction in docs/shot21.md, shots/21-shovel/{observations,marks}.json, scripts/shot21-observe.py | trace script run (and a +18 mm sensitivity run); `npm run check`; diagnostics and overview images AI-reviewed; replay frames re-checked; TS evaluator matches the script's samples |
| 22r | 2026-10-04 | User review applied: inputs.json user_review; trace status accepted with the far-corner shot direction (assumed, 11.2 deg); replay marked not-evidence; shot22 tests, docs/shot21.md, docs/shot22.md | trace script rerun; `npm run check` 97/97; diagnostics and overview images AI-reviewed |
| 23 | 2026-10-04 | src/model/shot-pose.ts; remotion/ShotPlayback.tsx, Root.tsx (shot23-shovel-17, shot23-at-time), cameras.ts (SHOT_CAMERA), asset-manifest.json; scripts/shot23-{manifest.ts,render.ts,sheet.py}; tests/shot23.test.ts; validation/23-{diagnostics.png,render-checks.json,proof-clip.mp4}; docs/shot23.md, docs/remotion.md; package.json (shot:23, remotion:assets writes the manifest) | `npm run check`; Remotion stills at 4 contact times; 12 frames x 2 shuffled orders (identical state and PNG bytes); proof clip 51 frames (state = pure evaluation); sheet and clip frames AI-reviewed |
| 22r2 | 2026-10-05 | User feedback: W-RW foot drag-back; CLAUDE.md contact-physics rule. scripts/shot22-trace.py (foot-contact solver, outline sliding, pushing contact, whole-trace check, W-C turn scan, approved exceptions, prep sheet); shots/22-shovel/inputs.json (prep_heading_marks, user instruction, approved exception); trace v2; validation/22-prep-foot-drag.png; Remotion contact gate; shot22/23 tests; iteration-23 renders regenerated | trace script run; no overlap except the approved one; `npm run check`; prep sheet, Remotion stills and clip AI-reviewed |
| 24 | 2026-10-05 | data/presentations/shovel-17.presentation.json; src/model/presentation.ts; src/model/shot-pose.ts (shotTimeEvaluator); remotion/ShotScene.tsx (shared scene), ShotPresentation.tsx, Root.tsx (shot24-shovel-17); scripts/shot24-{render.ts,sheet.py}; tests/shot24.test.ts; validation/24-{comparison.png,render-checks.json,draft.mp4}; docs/shot24.md, docs/remotion.md; package.json (shot:24) | `npm run check`; 4 normal/replay pairs identical in state and PNG bytes; contact pause identical; draft clip 223 frames = pure evaluation; stills and clip AI-reviewed |
| 25 | 2026-10-05 | src/model/presentation.ts (output fps multiple); remotion/ShotPresentation.tsx (timeline per fps), Root.tsx (shot25-shovel-17-final, 1920x1080 60 fps); scripts/shot25-{export.ts,keyframes.ts,review.py}; tests/shot25.test.ts; validation/25-{shovel-17-final.mp4,export-report.json,final-review.png}; docs/shot25.md; package.json (video:shovel-17) | draft 480x270 60 fps rendered and reviewed (all frames = pure evaluation); final 1920x1080 60 fps rendered, every frame = pure evaluation, review sheet AI-reviewed; `npm run check` |
| A1 | 2026-10-05 | Analysis video (user request): src/model/{analysis.ts,camera-track.ts}, presentation.ts (rewind); data/presentations/shovel-17.analysis.json; remotion/ShotAnalysis.tsx, Root.tsx (analysis-shovel-17); public/fonts (Barlow, OFL); scripts/analysis-{stills.ts,render.ts,review.py}; tests/analysis.test.ts; validation/analysis-shovel-17.{mp4,-report.json,-review.png}; docs/analysis-shovel-17.md; package.json (video:analysis-shovel-17) | tuning stills reviewed across all segments; final 1080p render, every frame = pure evaluation and camera track; file size checked < 25 MB; review sheet AI-reviewed; `npm run check` |
| S1 | 2026-10-06 | Spjass from the user's TikTok: references/shots/spjass-tiktok.mp4 (+ index); shots/spjass/{marks,observations,inputs,checks}.json; scripts/spjass-{observe,trace}.py; data/traces/spjass.trace.json (proposed); data/presentations/spjass.analysis.json; remotion/AnalysisVideo.tsx (shared; ShotAnalysis.tsx refactored onto it), SpjassAnalysis.tsx, Root.tsx (analysis-spjass); scripts/analysis-occlusion{-dump.ts,.py}, analysis-render.ts (per video), analysis-stills.ts (COMP), analysis-review.py (spec args); src/model/analysis.ts (graphic fields); tests/spjass.test.ts, tests/analysis.test.ts; validation/spjass-*.png, analysis-spjass*; docs/spjass.md; package.json (trace:spjass, video:analysis-spjass) | observation and trace scripts run; contact checks (no overlap, 0 unexplained); stills reviewed for every segment; puck visibility ray-cast; Shovel refactor byte-identical on 6 frames; final 1080p render with per-frame state and camera checks; `npm run check` |
| N1 | 2026-10-06 | Näcka from the NTHF page: references/combinations/* (+ index); shots/nacka/{inputs,checks}.json; scripts/nacka-trace.py; data/traces/nacka.trace.json (proposed, designed); data/presentations/nacka.analysis.json; remotion/NackaAnalysis.tsx, Root.tsx (analysis-nacka); scripts/analysis-render.ts (nacka); tests/nacka.test.ts; validation/nacka-trace.png, analysis-nacka*; docs/nacka.md, docs/spjass.md (NTHF cross-check); package.json (trace:nacka, video:analysis-nacka) | trace script run (contact checks clean); turn-profile and shot scans; stills reviewed; puck visibility ray-cast; final 1080p render with per-frame state and camera checks; `npm run check` |
| V1 | 2026-10-06 | Invers Kryssar med Velodrom: NTHF pages; sketch (scripts/ikv-sketch.py, ikv-sketch-render.ts, remotion/PosePreview.tsx, validation/ikv-sketch.png) approved by the user; scripts/ikv-trace.py (moving-blade collisions, board sliding, open-mouth cage); data/traces/invers-kryssar-velodrom.trace.json (proposed); shots/invers-kryssar-velodrom/{sketch,sketch-geometry,inputs,checks}.json; data/presentations/invers-kryssar-velodrom.analysis.json; remotion/IkvAnalysis.tsx, Root.tsx (analysis-ikv, pose-preview); tests/ikv.test.ts; validation/ikv-trace.png, analysis-ikv*; docs/invers-kryssar-velodrom.md; package.json (trace:ikv, video:analysis-ikv) | sketch clearances; staged strike scans; contact checks clean; stills reviewed, views reframed; puck visibility ray-cast (all frames visible); final 1080p render with per-frame state and camera checks; `npm run check` |
| V2 | 2026-10-06 | Invers Kryssar med Velodrom v2 (user: the left wing's flick would bounce; push forward-facing into the curve): example clip references/shots/lw-board-pass-example.mov (indexed); CLAUDE.md rule "Slide or bounce"; scripts/ikv-trace.py (quintic arc moves, slot-following rod turn, impact logging, slide_check, contact episodes, new events); shots/invers-kryssar-velodrom/{inputs,checks}.json; data/traces/invers-kryssar-velodrom.trace.json (v2, proposed); data/presentations/invers-kryssar-velodrom.analysis.json (v2: catch and corner push in chapter 2); remotion/IkvAnalysis.tsx (end card); tests/ikv.test.ts; validation/ikv-trace.png, analysis-ikv*; docs/invers-kryssar-velodrom.md | example clip puck track; parameter scans (catch, chase, push, shot); contact and slide checks clean; stills reviewed (push view moved: the left wing hid the puck; broadcast raised); puck visibility ray-cast (all frames visible); final 1080p render with per-frame state and camera checks; `npm run check` |
| D1 | 2026-10-06 | Defending against the left wing (passive / active / mix), concept video from the user's TikTok: references/shots/defence-vs-left-wing-tiktok.mp4 and references/combinations/bordshockeyskolan-lektion-3-centrifugen.html (indexed); scripts/defence-trace.py; shots/defence-left-wing/{inputs,checks}.json; data/traces/defence-left-wing.trace.json (proposed); data/presentations/defence-left-wing.analysis.json; remotion/DefenceAnalysis.tsx, Root.tsx (analysis-defence-lw), AnalysisVideo.tsx (lane graphic, red/green accents, banner label); src/model/analysis.ts; scripts/analysis-render.ts; tests/defence.test.ts; validation/defence-trace.png, analysis-defence-lw*; four analysis reports (composition_refactor); docs/defence-left-wing.md; package.json (trace:defence-lw, video:analysis-defence-lw) | captions read frame by frame; lane sweeps with the finite puck; contact checks clean; stills reviewed (camera closer, labels moved); other analysis videos byte-identical on 6 frames each; puck visibility ray-cast (all frames visible); final 1080p render with per-frame state and camera checks; `npm run check` |
| G1 | 2026-10-07 | Game mechanics (user request): references/rules/ithf-game-rules.pdf, references/games/fylling-vs-moe-trondheim-open-2022-final.mov (indexed); docs/game-mechanics.md; docs/state.md; CLAUDE.md | rules PDF read in full; video probed (ffprobe); audio spectrogram for the timer signals; frame registration and contact sheets around the start and the hand episodes (scratch only); no build or test changes |
| G2 | 2026-10-07 | Match tracking (user request): scripts/game_common.py, game-{stabilise,calibrate,puck,possession,review}.py; data/games/fylling-vs-moe-2022/{stabilisation.json, background.png, calibration-inputs.json, calibration.json, puck-labels.json, puck-track.json, possession.json, review.json}; validation/game-{calibration,figure-areas,possession}.png, game-{puck-spotcheck,possession-review}.jpg; tests/game-tracking.test.ts; docs/game-tracking.md; package.json (game:track); docs/state.md; CLAUDE.md | full pipeline run; calibration overlay reviewed; classifier cross-validated in time blocks; 40 random frames and 24 random episodes reviewed by eye; false-detection hotspots inspected and fixed; sensitivity table; `npm run check` |
