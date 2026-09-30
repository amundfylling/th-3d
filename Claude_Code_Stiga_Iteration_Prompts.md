# Claude Code prompts: STIGA Play Off 21 in small iterations

Start with an empty GitHub repository containing `Stiga_Play_Off_21_References.pdf`. The prompts also work if the PDF is in a subfolder or has been renamed: iteration 01 locates it.

The goal is reusable, photorealistic 3D shot videos built around the actual STIGA Play Off 21 hardware. These are instructions for future work in Claude Code. No model, application or animation has been created by this prompt pack.

## How to use this pack

- Send one numbered prompt at a time. Inspect the named result before sending the next prompt.
- Continue on the same working branch. Before starting a fresh cloud session, ensure that branch contains the previous iteration's files and commits; select it for the new session. An empty or older branch will not contain the progress.
- Iterations 01-20 build and review the reusable model. They do not create animated shots. Iterations 21-25 are for later, after the model review and a real shot recording.
- A task can be implemented while its measurements remain provisional. Neither a successful build nor an attractive render proves dimensional accuracy.
- The PDF is a reference guide, not a complete engineering specification. It contains nominal sizes, photographs and links. It does not provide measured tracks, blade offsets, stops or complete figure geometry.
- This particular guide retains the five gallery photographs as full-resolution embedded images on pages 2-4. Iteration 02 extracts those first; network access is needed only for additional references or verification that cannot be recovered from the PDF.
- If downloading originals is blocked, use the reference-download recovery prompt below. If a required render cannot run, keep the implementation marked unverified; do not treat an unexecuted script as proof.

You can optionally add this Markdown file to the repository too. Then send:

```text
Read Claude_Code_Stiga_Iteration_Prompts.md and execute iteration 01 only, including its finish criteria. The reference PDF is already in this repository. Stop after that iteration.
```

For later iterations, change the number:

```text
Read CLAUDE.md, docs/state.md and Claude_Code_Stiga_Iteration_Prompts.md. Execute iteration 02 only. Check its prerequisites, follow its scope and finish criteria, update the handoff, and stop.
```

If you add only the PDF, copy the individual numbered prompts below directly into Claude Code instead.

## Iteration map

| Iteration | One main result | Review before continuing |
| --- | --- | --- |
| 01 | Project instructions and handoff | Correct model, scope and unknowns |
| 02 | Original source assets | Correct variant and image quality |
| 03 | Minimal TypeScript tooling | Commands run in the cloud environment |
| 04 | Geometry data contract | Nominal, traced and measured values remain distinct |
| 05 | Board boundary overlay | Boundary matches the installed rink |
| 06 | Defender and centre track overlays | Six independently identified paths |
| 07 | Winger track overlays | Four curved paths and behind-goal sections |
| 08 | Goalie paths and goal regions | Two goalie paths and actual hardware setup |
| 09 | Pure fixture-pose functions | Correct axes, angle convention and handedness |
| 10 | One skater's contact specification | Pivot, blade and feet are explicit |
| 11 | Static rink asset in Blender | Shape, scale and export convention |
| 12 | Goals, screens and puck | Clearances and unresolved dimensions |
| 13 | One skater's blade/foot asset | Contact shapes and fixture origin |
| 14 | The same skater's rigid body | Recognizable molded STIGA shape |
| 15 | One goalie asset | Its own geometry and fixture origin |
| 16 | Complete static assembly | Correct players, placement and asset identity |
| 17 | Rink materials and graphics | Correct artwork and molded surfaces |
| 18 | Figure materials and graphics | Correct uniforms, sticks, skates and puck |
| 19 | Static Remotion 3D integration | Same geometry, units and cameras |
| 20 | Model review and calibration checkpoint | Exactness and visual quality assessed separately |
| 21 | Observations from one real shot | Capture timestamps, poses and uncertain contacts |
| 22 | One accepted motion trace | Contact stills and trajectory review |
| 23 | Frame-driven shot playback | Deterministic seeking and fixed camera |
| 24 | Replay and teaching overlays | Presentation preserves the physical trace |
| 25 | First video export | Output settings, complete playback and reusable recipe |

## 01 - Establish the project and its working rules

```text
We are starting a new project in this repository. I want photorealistic 3D Remotion videos explaining shots on my STIGA Play Off 21. Implement iteration 01 only: project instructions and a reference brief. Do not create application code, 3D assets or animations yet.

Locate the reference PDF already in the repo, preferably Stiga_Play_Off_21_References.pdf. Read its text, inspect its images where your tools permit, and extract its hyperlinks. Preserve the PDF unchanged. Identify whether it is the eight-page research guide or a manufacturer manual; do not attribute measurements to pages that do not contain them. Report any visual content you could not inspect.

Create only:
- CLAUDE.md: concise project instructions, preferably under 100 lines.
- docs/reference.md: PDF path, document identity, source/page pointers, model/variant, published dimensions, conflicts and missing evidence.
- docs/state.md: last completed iteration, next iteration, verification status, key decisions, missing inputs and paths to review artifacts. Keep a short iteration history here.

Put these working rules in CLAUDE.md:
1. Read docs/state.md before each task. Complete only the requested iteration and stop.
2. Preserve the references. Use one canonical geometry specification and stable player/asset IDs.
3. Every geometric value has a unit, source and status: measured, catalog_nominal, traced, assumed or unknown. Unspecified uncertainty is null, never zero. Preview assumptions remain visible in data and review notes.
4. The target is Play Off 21 family 71-1145-XX. Public Sweden/Finland pictures are a reference variant; my actual parts, teams and artwork take precedence when supplied.
5. Skaters are rigid molded pieces with path position and rotation around the actual fixture axis. No articulated skating, arm movement or independent stick swing. Preserve physical handedness for both teams. Treat the goalie separately.
6. Curved-track travel does not establish automatic tangent-facing rotation. Rod-to-figure transfer functions, stops and backlash need evidence.
7. Keep motion data separate from camera, replay speed and overlays. Future Remotion frames evaluate a saved trace at time t; they must not depend on a live physics loop or frame order.
8. Start with recorded-shot reconstruction. Do not build a general physics simulator in these iterations.
9. Run checks relevant to the change. Review visual artifacts when possible. Never claim an unexecuted build or unseen render passed.
10. Finish each iteration with changed paths, checks actually run, one main artifact to inspect, unresolved assumptions and the next step. Update docs/state.md. Commit that iteration's changes on the current working branch when git permits; do not merge or force-push.

Keep future file structure simple: references/, data/, src/model/, assets/, validation/, and docs/. Record that there are no animated shots before iteration 23.

Finish with the reference brief and a short list of the most important missing measurements. Stop.
```

Review: it should recognize the conflicting overall lengths and distinguish the playing area from the housing. It should not promise an exact physical replica from the PDF alone.

## 02 - Recover the original reference assets

```text
Read CLAUDE.md and docs/state.md. Implement iteration 02 only: obtain the original reference assets.

First inventory and extract the PDF's native embedded images, not screenshots of rendered pages. This eight-page guide retains the 5636 x 5636 overhead on page 2, two 5154/5192-pixel oblique images on page 3 and two 5210/5208-pixel side images on page 4. Verify those dimensions in the actual file, inspect their view identities and extract the bare sheet on page 5 too. A differently supplied PDF may not retain these assets: check rather than assume.

Use the PDF's embedded hyperlinks and linked manufacturer page to associate each asset with its public source. Download an original only where recovery or source verification requires it; also obtain the complete Play Off 21 A06 manual if its link is reachable. Do not substitute thumbnails or enlarge a PDF extraction and call it an original.

Store recovered/downloaded assets under references/originals/. Create references/index.json with stable source IDs, public URL, local path, native image dimensions, SHA-256, view, variant/artwork and limitations. Distinguish pdf_embedded from downloaded_original provenance and record the PDF/page for extracted assets. Do not claim byte identity with a remote original unless verified. Add the manual's actual assembly and parts page numbers to docs/reference.md.

The bare sheet has older artwork and may extend beneath the boards. Label that difference. Identify useful loose-figure views still missing.

If network access blocks a download, retain its resolved URL and failed status. Continue with sufficient native PDF assets where available; label any low-resolution extraction as a fallback. Report the required host or missing source; do not invent another URL or claim the download worked.

Follow the iteration finish rules in CLAUDE.md and stop.
```

Review: the five official square originals should be around 5,000 pixels, with substantial white margins. The installed rink and bare sheet should not silently share artwork.

## 03 - Bootstrap the smallest useful tooling

```text
Read CLAUDE.md and docs/state.md. Implement iteration 03 only: a minimal TypeScript workspace for geometry data and static diagnostic artifacts.

Inspect the cloud environment first. Record Node, package manager and Python versions, plus whether Blender and a usable headless browser are present. Do not assume a desktop, GPU or Blender installation.

Use one root package.json, TypeScript and the minimum runner needed for local scripts. Add typecheck and a simple runnable smoke command. Commit a lockfile. Ignore dependency directories, caches and bulk render outputs. Do not install Remotion, build a website, configure a database or introduce a monorepo yet.

Create a tiny script that reads a small JSON fixture and emits one static diagnostic SVG with a labelled coordinate origin. This checks the data-to-artifact route, not the hockey model.

Write the exact working commands in the README and environment findings in docs/tools.md. Run the smoke command and typecheck. Follow the iteration finish rules and stop.
```

Review: the smoke SVG opens, and the commands were actually run.

## 04 - Establish one geometry data contract

```text
Read CLAUDE.md and docs/state.md. Implement iteration 04 only: the canonical geometry schema and its evidence policy.

Create typed definitions and data/geometry.json. Use rink-centred x/y coordinates in millimetres and z upward for calibrated geometry; preserve raw image-pixel traces with their source-image identity and explicit mapping into world space. Do not pretend an uncalibrated photograph already gives exact millimetres.

Represent the inner board boundary, outer housing, markings, individual fixture paths, visible slot limits, measured usable stops, goal setup, figure/asset IDs, pivot-local contact shapes and puck. Include geometry version, source IDs, statuses and uncertainty.

Import only evidenced catalog values. Preserve the 960 mm versus approximately 940 mm overall-length conflict. Keep absent dimensions null. Any chosen preview scale must be explicitly assumed, uniformly applied and replaceable; never stretch x and y separately to force catalog dimensions to fit a picture.

Document the intended Blender/glTF/Three coordinate adapter so units and axes convert once. Do not trace the rink, create meshes or implement movement yet.

Verify the file against its schema, follow the iteration finish rules and stop.
```

Review: unknown stops, pivot offsets and puck thickness remain unknown. A chosen preview assumption has not become a measurement.

## 05 - Trace only the installed board boundary

```text
Read CLAUDE.md and docs/state.md. Implement iteration 05 only: a provisional trace of the inner board boundary from the highest-quality installed overhead photograph.

Preserve the source. Trace the straight sections and rounded corners into the canonical geometry data using identifiable source-image landmarks. Distinguish the ice contact boundary from the outer housing and the loose sheet perimeter. Keep occluded sections and any symmetry assumptions labelled.

Generate validation/05-board-overlay.svg with the unchanged photograph, trace, landmark IDs, source-pixel coordinates and any provisional scale/projection notes. Preserve aspect ratio. If you rectify the ice plane, save the transform and landmark residuals; do not apply that plane transform to elevated figures.

Provide an evidence-based error estimate where a landmark can be checked. Do not report millimetre accuracy without calibrated scale. If you cannot inspect or trace the image with available tools, mark the trace blocked rather than fabricate coordinates.

Do not add tracks or 3D geometry. Follow the iteration finish rules and stop.
```

Review: the line follows the installed inner boards, especially the corners. The photo must not be stretched to make an overlay look correct.

## 06 - Trace the defenders and centres

```text
Read CLAUDE.md and docs/state.md. Implement iteration 06 only: the two defenders and centre for each team, six paths total.

Use the installed overhead image and bare-sheet reference. Assign stable team/role IDs and document which side is team A. Trace every path independently; preserve the diagonal centre routes. Do not derive the opposing team by mirroring without checking its image evidence.

Store source-pixel centreline points, curve representation, observed endpoints, provenance and occlusions in the canonical data. Separate a visible slot centreline from a measured fixture-axis path, and visible slot ends from actual usable travel stops. Unknown offsets and stops remain unknown.

Generate validation/06-straight-tracks.svg with the photographs and colour-coded labelled paths. Do not add wingers, moving figures or 3D assets.

Verify path count and identity, follow the iteration finish rules and stop.
```

## 07 - Trace the four winger paths

```text
Read CLAUDE.md and docs/state.md. Implement iteration 07 only: the left and right winger paths for both teams, four paths total.

Use the bare sheet for unobstructed topology and the installed overhead for alignment to the board and goals. Trace the straight sections, curves and behind-goal sections into the canonical data. Keep uncertain endpoints and any differences between the two reference images explicit.

Do not approximate a curved route as a straight line. Use sufficient curve detail to match observed landmarks, with a documented source-pixel fitting error. Do not assume the figure faces the tangent or that rod travel equals path arc length.

Generate validation/07-winger-tracks.svg and a static set of marked sample points along each curve. Identify where usable travel still requires a hardware recording. Do not animate.

Follow the iteration finish rules and stop.
```

## 08 - Add goalie paths and goal regions

```text
Read CLAUDE.md and docs/state.md. Implement iteration 08 only: the two goalie paths and two goal regions in the planar specification.

Identify each goalie path, the goal position, visible opening and behind-goal space from the references. Do not use a generic skater path for a goalie. Preserve uncertainty about the actual fixture pivot, travel stops, post dimensions and opening height.

Represent goal configuration as data: retail supplied inserts versus the actual demonstration setup. The guide notes that ITHF tournament setups remove white net inserts and goal cups. If my setup has not been supplied, keep it unresolved and make the preview assumption explicit.

Generate validation/08-goals-and-goalies.svg showing both goalie routes, goal regions and unresolved dimensions. This completes the inventory of ten outfield routes and two goalie routes; it does not establish their measured usable travel.

Follow the iteration finish rules and stop.
```

## 09 - Implement the fixture-pose mathematics

```text
Read CLAUDE.md and docs/state.md. Implement iteration 09 only: pure, renderer-independent pose functions in src/model/.

Define each skater's state as path position u plus continuous rotation theta about its fixture axis. Use a documented normalized arc-length parameter for preview travel; do not call it physical rod displacement. Keep actual rod mapping and measured stops separate. Keep rotation independent of the path tangent unless measured coupling is supplied. Give the goalie its own pose adapter.

Implement path sampling, pivot pose and rigid transformation of local points. Preserve continuous angles and physical handedness. Opposing-team placement uses proper rotations, not a negative-scale mirror that changes stick handedness.

Add focused numerical checks for curve continuity, boundary inputs, an angle passing through 360 degrees, one known pivot-local point and preservation of handedness. Flag invalid states rather than silently inventing a valid pose. Unknown fixture offsets remain explicit preview assumptions.

Generate a static pose-debug SVG using several sample states. No time animation or puck motion. Follow the iteration finish rules and stop.
```

## 10 - Define one skater's contact geometry

```text
Read CLAUDE.md and docs/state.md. Implement iteration 10 only: the pivot-local blade and relevant foot/skate contacts for one representative skater.

Identify which physical figure the reference supports. Inventory its mounting axis, blade outline and offset, feet/skates, and relevant contact heights. Use supplied measurements or scale-bearing views when available. Otherwise keep the real values unknown and create separately labelled provisional contact geometry for debugging; explain the evidence and assumptions behind it.

Store this in the canonical data. Use the existing rigid-transform functions to generate validation/10-skater-contacts.svg at several orientations, including a finite-radius puck beside the blade. The puck diameter is nominal until checked; thickness is not established by a close-up photograph.

Demonstrate that blade and foot points remain fixed relative to the figure, rotate around the fixture and preserve handedness. Do not assign outgoing puck velocity or build a collision solver.

Follow the iteration finish rules and stop.
```

Review: this is a critical measurement checkpoint. A correct-looking figure with an incorrect pivot or blade offset produces incorrect shots.

## 11 - Build only the static rink asset in Blender

```text
Read CLAUDE.md and docs/state.md. Implement iteration 11 only: a repeatable headless Blender route and a static rink asset.

Use Blender if available. If absent, try a documented compatible headless installation within the cloud environment's permissions and network access. Record the version and exact command. If this is blocked, write the reproducible asset-generation script and setup instructions, mark execution unverified, and stop; do not replace photorealistic 3D with a flat illustration.

Create the ice, traced slots, inner boards and outer housing from canonical geometry. Keep measured geometry and explicit preview assumptions distinct, especially housing and board heights. Use neutral clay materials. No goals, figures, puck, printed graphics or animation.

Save an editable .blend, the regeneration script and a GLB export. Define where millimetres become metres and account for Blender's glTF axis conversion exactly once. Render overhead and side stills when possible and verify scale against known reference data.

Follow the iteration finish rules and stop.
```

## 12 - Add goal hardware and the puck

```text
Read CLAUDE.md and docs/state.md. Implement iteration 12 only: one goal assembly, one end screen and the puck as reusable static assets.

Use the oblique and side photographs and manufacturer assembly diagram. Respect the recorded goal configuration. Keep opening width/height, post dimensions, screen curvature and puck thickness measured or explicitly provisional. Do not treat the exploded illustration as a scale plan or retail packaging sizes as component geometry.

Create editable Blender assets and GLB exports with documented origins. Add them to the static rink at the specified positions without changing the accepted board and track traces. Render an oblique goal close-up and a side puck/ice-clearance view.

List unresolved clearances that affect contact accuracy. No player assets or animation. Follow the iteration finish rules and stop.
```

## 13 - Model one skater's blade and feet

```text
Read CLAUDE.md and docs/state.md. Implement iteration 13 only: the contact-bearing lower portion of the representative skater from iteration 10.

In Blender, build its stick blade and relevant feet/skates from the canonical contact specification and reference views. Put the asset root at the fixture axis, with the documented ice-plane height. Keep these parts rigidly attached. Do not add a human skeleton or independently animated stick.

Preserve source status for every dimension. Where evidence is missing, use the documented provisional profile rather than silently inventing a precise one.

Render top and side close-ups with pivot axes, contact outlines and a puck. Check the numerical render mesh against the stored contact shapes. Save the editable source and export, but do not build the torso, head or uniforms in this task.

Follow the iteration finish rules and stop.
```

## 14 - Complete that skater's rigid body shape

```text
Read CLAUDE.md and docs/state.md. Implement iteration 14 only: the torso, arms, legs and head of the same skater, using neutral materials.

Match the molded STIGA figure visible in the manufacturer views. Preserve the fixture origin and the blade/foot contact geometry from iteration 13. The body, limbs, stick and skates form one rigid assembly; no articulated pose or human skating cycle.

Use front, side and oblique silhouettes as the review targets. Mark unseen surfaces and unmeasured proportions as provisional. Do not substitute a generic hockey character and call it the same physical piece.

Render a small static view sheet: front, back, both sides and overhead. Clearly identify which views have actual reference evidence. Record whether other skater positions genuinely share this geometry or need another figure variant; do not assume all five outfield molds are identical.

No uniform artwork or animation. Follow the iteration finish rules and stop.
```

Review: refine a specific silhouette defect using the correction prompt below before moving to uniforms.

## 15 - Model one goalie separately

```text
Read CLAUDE.md and docs/state.md. Implement iteration 15 only: one rigid STIGA goalie asset.

Use the goalie references and documented goalie mechanism. Model its own body, stick/contact surfaces and mounting origin. Do not resize the skater asset to make a goalie. Preserve its actual handedness and represent unknown offsets and clearances explicitly.

Save the editable Blender asset and GLB. Produce static top, side and oblique views, including a puck beside its stick and the goalie in its goal region. Use neutral materials and fixed poses only.

Check that its origin and contact geometry agree with the pose adapter, and that no required clearance has been declared measured without evidence.

Follow the iteration finish rules and stop.
```

## 16 - Assemble the full game in one static pose

```text
Read CLAUDE.md and docs/state.md. Implement iteration 16 only: a complete static assembly driven by the canonical geometry and existing asset IDs.

Place ten skaters and two goalies using the fixture-pose functions. Reuse a skater mold only where the evidence supports it; otherwise keep a distinct proxy and mark the missing variant. Rotate the opposing team's figures without mirroring their handedness. Preserve the goals, screens and puck setup.

Add only simple static rods, handles and supports that are visible in the target views. Do not fabricate their hidden linkage or claim that a static rod pose proves the real control mapping.

Create a labelled overhead debug render and one neutral oblique render. Check player counts, path/role assignments, mounting axes, geometry units and obvious unintended intersections. Report unresolved asset types rather than hide them.

No animation or material-polishing work. Follow the iteration finish rules and stop.
```

## 17 - Finish the rink surfaces and artwork

```text
Read CLAUDE.md and docs/state.md. Implement iteration 17 only: materials and graphics for the rink, housing, goals and end screens.

Use the selected Play Off 21 reference variant consistently. Match molded black/red plastic, printed ice, metal where visible, and transparent screens. Do not combine the older bare-sheet sponsor print with the current installed gallery unless that matches my actual game.

Recover or reconstruct artwork from evidenced sources, documenting its provenance and perspective correction. Do not bake upright figures, goals, their shadows or photograph highlights into the ice texture. Preserve calibrated UV scale and all geometry.

Render the existing overhead and oblique benchmark views with a restrained fixed light setup. Record texture gaps and material mismatches. Do not redesign player shapes, add camera movement or use lighting to conceal boundary errors.

Follow the iteration finish rules and stop.
```

## 18 - Finish figure and puck appearance

```text
Read CLAUDE.md and docs/state.md. Implement iteration 18 only: uniforms and materials on the existing skater, goalie and puck assets.

Use the actual selected teams when supplied; otherwise preserve the explicitly documented reference-variant choice. Match verified jersey colours, numbers, stick/skate colours, face/helmet appearance and molded-plastic surfaces. Keep unresolved logos or unseen decals identified rather than replace them with invented artwork.

Do not change fixture origins, contact geometry or accepted body shapes during this material task. Use the same scale and lighting as the benchmark.

Render front, side and blade/puck close-ups. Assess them at the intended output resolution and camera distance, not only in a distant full-rink view. List specific remaining visual defects.

Follow the iteration finish rules and stop.
```

## 19 - Integrate a static 3D scene in Remotion

```text
Read CLAUDE.md and docs/state.md. Implement iteration 19 only: static Remotion integration of the existing GLB assets and canonical pose data.

Consult current official Remotion and React Three Fiber documentation. Add a minimal React/TypeScript Remotion entry point with @remotion/three. Pin compatible dependencies and keep remotion and every @remotion/* package at exactly the same version. Preserve the existing geometry tooling and lockfile.

Create one static inspection composition with overhead, side and oblique camera choices. Every frame uses the same fixed pose. Load local assets reliably and wait for them before capturing a still. Implement the documented unit/axis adapter once; verify a known basis point and a blade orientation after import.

Run typecheck and render at least one actual PNG through Remotion when the browser environment permits. Check Chromium/WebGL capability using the current documented options. If blocked, mark rendering unverified and report the precise blocker.

No animated shot, live physics loop or camera animation. Follow the iteration finish rules and stop.
```

## 20 - Review the model and incorporate calibration

```text
Read CLAUDE.md and docs/state.md. Implement iteration 20 only: model review and calibration intake. Do not create a shot yet.

Inspect newly supplied measurements, scaled photographs or mechanism recordings, if present. Update only the canonical parameters that their evidence supports; preserve provenance and unresolved conflicts. Re-run affected overlays and pose checks. If a repair is substantial, describe one bounded correction task instead of rebuilding the whole model in this iteration.

Produce one static review sheet with overhead, side, oblique and blade/puck views. Compare matching camera projections and report geometry error separately from lighting/material appearance. Include the proposed output resolution and clearly state whether any one-output-pixel claim is actually supported.

Assess whether Remotion/Three meets the desired photorealism. If it does not, specify a small Blender Cycles benchmark task before selecting the final renderer; do not silently switch pipelines or declare the quality sufficient.

Record separately: implementation completeness, geometric evidence, physical-mechanism evidence and visual review status. List the few inputs still required for an exact model. Do not mark my visual approval or unknown dimensions as verified on my behalf.

Follow the iteration finish rules and stop. Iteration 21 requires my review feedback and a real shot recording.
```

Review: this is the checkpoint before shots. You can approve an illustrative prototype while measurements remain provisional, but it must retain that status. An exact-replica claim needs the relevant hardware evidence.

## 21 - Observe one real shot without reconstructing it yet

```text
Read CLAUDE.md and docs/state.md. Implement iteration 21 only: observations from one supplied real shot recording, using the reviewed model.

Check for my model-review feedback and the recording. If either is missing, state the required input and stop rather than invent approval or a clip. Use the simplest flat, direct shot available, with one active shooter and no unnecessary extra actions. If the supplied shot is substantially more complex, identify its smallest useful segment.

Inspect capture resolution, actual timestamps/frame timing and camera projection. Extract a small set of review stills around preparation, blade contact, release and goal entry. Record observed figure poses, puck centres, occlusion and timing uncertainty. Do not treat output-video fps as recording fps or infer an exact hidden contact.

Save a source/observation record under shots/ and a labelled contact sheet under validation/. Map observations to the existing stable figure and track IDs. Do not fit motion, simulate a puck or animate in this iteration.

Follow the iteration finish rules and stop.
```

## 22 - Fit and review one motion trace

```text
Read CLAUDE.md and docs/state.md. Implement iteration 22 only: a constrained reconstruction from the iteration 21 observations.

Check the recording and use its calibrated camera mapping where available. Fit the shooter's path position and continuous angle, plus the independently observed puck positions at source timestamps. Keep other figures in their observed static poses unless the recording requires their movement. Do not build a general physical simulator or generate an arbitrary aesthetically pleasing puck spline.

Preserve observed contact/release times and uncertain or occluded intervals. Check the finite-size puck against blade, foot, boards and goal clearance, including fast motion between samples. Relevant unknown contact dimensions must remain a limitation of the reconstruction.

Save one trace with geometry/asset version references, source time in seconds, contact events, provenance and uncertainty. Produce diagnostic stills just before, at and after release and goal entry. Mark it proposed until I review the contacts; do not silently label it accepted.

No movie export or presentation overlays. Follow the iteration finish rules and stop.
```

## 23 - Play the accepted trace with a fixed camera

```text
Read CLAUDE.md and docs/state.md. Implement iteration 23 only after my review feedback accepts the proposed trace or specifies the corrections.

Make the smallest corrections supported by that feedback, or stop if a substantial refit is required. Create one short Remotion shot composition using the accepted trace, fixed overhead camera and plain background. No narration, moving camera, replay or decorative effects.

Derive physical time from the requested frame and fps using useCurrentFrame(). Evaluate the saved trace as a pure function of time. Interpolate continuous angles without an unintended reversal through zero. Do not use R3F useFrame(), wall-clock deltas or accumulated simulation state to advance the shot.

Render diagnostic frames at specified contact times. Evaluate selected frames in a shuffled order and repeat them; check that numeric poses and contact timing are unchanged. Reject mismatched geometry/asset versions.

Save a minimal proof clip if rendering is available, otherwise mark the composition unverified. Follow the iteration finish rules and stop.
```

## 24 - Add one slow replay and minimal teaching overlays

```text
Read CLAUDE.md and docs/state.md. Implement iteration 24 only: presentation around the accepted shot.

Keep the physical trace and geometry unchanged. Show the same shot once at normal speed and once at slower speed, with a clear pause or label at the key contact. Use one clear camera view chosen from the approved static benchmarks. Keep the blade/puck contact visible.

Represent replay speed and pauses as an explicit presentation-time to source-time mapping. The replay must evaluate the same trace, not change puck velocity parameters or invent intermediate contact events. Keep captions and highlights separate from the mechanics.

Add only a short technique title, the key contact explanation and a restrained marker. Disable blur/depth of field where they hide that contact. Render a few normal/replay comparison stills and check that the same source time gives the same physical state.

Follow the iteration finish rules and stop.
```

## 25 - Export and document the first reusable video

```text
Read CLAUDE.md and docs/state.md. Implement iteration 25 only: export the reviewed first video and document how to reproduce it.

Use the renderer selected at the model benchmark, the accepted trace and approved presentation. Begin with one short low-cost draft render. Review the whole playback and key contact frames, then render the agreed final output settings. If no settings were agreed, propose a 1920x1080, 60 fps target and record it as a presentation choice, not additional geometry precision.

For the Remotion/Three route, render the approved composition directly. If Blender Cycles was selected, use the shared trace and camera/time mapping in the verified offline handoff, then compose its local footage in Remotion. If that handoff has not been built and verified, stop and name that bounded prerequisite instead of improvising a second animation.

Document exact commands, dependency/renderer versions, model and trace versions, output settings, observed limitations and the one command/input needed to rerender this shot. Keep bulk frame sequences and caches out of normal git commits.

This task does not add another shot or build a simulator. Follow the iteration finish rules and stop.
```

## Useful prompts between iterations

### Correct one specific defect

```text
Read CLAUDE.md and docs/state.md. Stay within the current iteration. Correct only this issue: [describe the defect and name the affected render/reference].

Use the stated evidence, preserve accepted geometry and unrelated assets, and regenerate only the affected review artifact. Show the before/after difference and any changed dimensions or assumptions. Run the relevant checks, update the handoff and stop. Do not advance to the next numbered iteration.
```

### Bring in a few new measurements

```text
Read CLAUDE.md and docs/state.md. Incorporate only the new measurements or scaled photographs I have supplied with this message. Identify their units, datum, source and affected parameters. Keep ambiguous values unresolved.

Update canonical data, regenerate affected overlays or stills, and report which provisional assumptions were replaced. If geometry versions change, identify any shot traces that now need revalidation. Do not redesign unrelated parts or continue to another iteration.
```

### Recover from blocked reference downloads

```text
Read CLAUDE.md and docs/state.md. Complete only the reference assets that failed to download. First check for originals I have now uploaded to references/originals/. Match them to recorded source URLs, dimensions and view identities.

If network configuration is the blocker, report the exact hosts required and the failed assets. Check native PDF images before using rendered-page screenshots; this guide embeds the gallery at its full pixel dimensions. Keep extracted-image provenance explicit, and label genuinely downsampled copies as fallbacks. Do not claim original-resolution tracing from a downsampled guide screenshot. Update references/index.json and the handoff, then stop.
```

### Resume in a fresh session

```text
Read CLAUDE.md, docs/state.md, the current geometry version and the relevant existing files before changing anything. Confirm this branch contains the last completed iteration. Summarize the actual implemented and verified state in five lines.

Then implement only iteration [number] from Claude_Code_Stiga_Iteration_Prompts.md, if that file is present, or from the task text I supply below. Preserve existing reviewed work. If a prerequisite is missing or the branch is stale, report it and stop instead of rebuilding from memory.
```

### Refine photorealism with one controlled comparison

```text
Read CLAUDE.md and docs/state.md. Improve only [one asset/material/silhouette defect] in [named benchmark view]. Use [named source photograph or measured view] as the reference. Keep the camera, lighting and unrelated geometry fixed unless the stated defect is itself a camera or lighting mismatch.

Render a before/after comparison at the target resolution, explain the one change, and list remaining defects. Do not run an open-ended visual makeover, alter contact geometry without evidence or introduce motion.
```

### Optional Blender Cycles quality benchmark

```text
Read CLAUDE.md and docs/state.md. Complete only a static Blender Cycles benchmark for the existing approved scene. Use the same geometry, fixture poses, output resolution and matching camera projection as the Remotion benchmark.

Render one full-rink oblique still and one blade/puck close-up with documented materials, lighting, samples and seed. Compare the specific plastic, transparent-screen, shadow and figure-detail problems identified in the browser benchmark. Report render time and the remaining appearance differences.

Do not build an animated offline renderer in this task. Recommend the final rendering route based on these actual stills, update the handoff and stop.
```

### Optional offline trace-rendering handoff

```text
Read CLAUDE.md and docs/state.md. Build only the Blender Cycles handoff for an already accepted motion trace and camera specification.

Export deterministic source-time pose samples into the existing Blender scene, with the same units, fixture axes, continuous angles and presentation-time mapping used by Remotion. Validate at three named contact times by comparing numerical world-space pivots and blade points across both routes.

Render a very short proof sequence, then load that local sequence/footage in a minimal Remotion composition without independently animating its figures. Record asset readiness, colour handling, frame timestamps, export settings and reproducible commands. Do not render the full final video until this proof has been inspected.
```

## Technical references for the executing agent

Checked 30 September 2026. Fetch current documentation when implementing package-specific APIs rather than assuming these details will remain unchanged.

- [Claude Code cloud sessions](https://code.claude.com/docs/en/claude-code-on-the-web): sessions work with repository branches and configurable cloud environments. Preserve progress on the branch used by a new session.
- [Claude Code project instructions](https://code.claude.com/docs/en/memory): root CLAUDE.md provides persistent project context. These instructions guide the agent; they are not a technical enforcement mechanism.
- [Remotion Three integration](https://www.remotion.dev/docs/three): ThreeCanvas integrates React Three Fiber with Remotion and frame-driven evaluation.
- [Remotion animation properties](https://www.remotion.dev/docs/animating-properties): evaluate motion from the requested frame.
- [Remotion version compatibility](https://www.remotion.dev/docs/version-mismatch): all Remotion packages should have the same exact version.

The task boundaries, sequencing and review points above are workflow recommendations. The geometric evidence remains the PDF, recovered source assets and the actual hardware measurements supplied later.
