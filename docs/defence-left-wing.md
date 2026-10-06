# Defending against the left wing: three defences (concept video)

Status: made on 2026-10-06 at the user's request. Not a numbered iteration. The user asked: *"make an illustration
about the three ways to defend when the opponent has the puck on the left winger. Before making the video, make sure
that you understand the three ways. It does not have to be precisely the same placement as the video, the important
part is showing the concept ... you could show examples of how the defence stops some shots, e.g. the centrifuge or
the direct shot, but don't focus on the shots themselves"*.

The trace `trace.defence-left-wing.v1` is **proposed** and **designed**. It is a concept illustration, not a recorded
shot.

**User correction (before the first render was finished):** *"The goalie does not have the back outwards and cover
the corner in active and mixed. When it stands with face facing forward it does not cover the direct shot at all."*
- When active, the goalie now turns at the near post until it faces directly away from the puck. Its back is toward
  the corner and the left wing, and its whole width lies across the straight-shot line. That is a turn of about 120°
  counter-clockwise from square.
- When passive it stays square in the middle.
- The video shows the turn with an arrow, "BACK TO THE CORNER".

| Item | Path |
| --- | --- |
| Source (user upload, preserved, indexed) | `references/shots/defence-vs-left-wing-tiktok.mp4` (TikTok, @tablehockeyglobal, 57 s) |
| The centrifuge (found for the user's term, indexed) | `references/combinations/bordshockeyskolan-lektion-3-centrifugen.html` |
| Design choices | `shots/defence-left-wing/inputs.json` |
| Trace | `data/traces/defence-left-wing.trace.json` (`scripts/defence-trace.py`); checks `shots/defence-left-wing/checks.json`; top view `validation/defence-trace.png` |
| Analysis spec | `data/presentations/defence-left-wing.analysis.json` |
| Composition | `analysis-defence-lw` (`remotion/DefenceAnalysis.tsx` + the shared `remotion/AnalysisVideo.tsx`) |
| Video | `validation/analysis-defence-lw.mp4`; report `validation/analysis-defence-lw-report.json`; review sheet `validation/analysis-defence-lw-review.png`; puck visibility `validation/analysis-defence-lw-occlusion.json` |
| Tests | `tests/defence.test.ts` |

Reproduce: `npm run trace:defence-lw`, then `npm run video:analysis-defence-lw` (about 80 min on the 4-CPU
container).

## What the TikTok says and shows

The narration comes from the burned-in captions, read frame by frame. Speech recognition isn't available here, and
a few words between caption blocks are missing (marked "..."):

> Somebody is attacking from their left wing. Here are three defenses you can use.
> **First:** a box one, the passive one. Just stand in [front] and close down the option for them to shoot straight
> into the net. They need to use any combinations and they need to be precise. So this would be the best way for the
> beginners.
> **Second option** is the active defense, where you basically go and close down the option to go straight into the
> net by the goalie, and then with the defender you need to take the passes out and block the possible combinations
> going around.
> **The third option** is the mix, basically more advanced gameplay where you go active, active, active and then go
> passive ... in front, or you can use the back as well ... on what your opponent is doing. Either shooting the short
> goals in this corner or far corner, goals in far corner.

The demonstrations are a top-down camera over one end:
- The yellow team defends the goal at the bottom of the picture.
- The attacking white/blue left wing (#64) has the puck in the corner at the goal line.

| Defence | Frames | Yellow goalie (#30) | Yellow defender (#82), on the left wing's side |
| --- | --- | --- | --- |
| Passive ("box") | 175-500 | stays in the middle of the goal | moves down next to the near post, in front of the goal, on the straight-shot line |
| Active | 610-1000 | moves to the near post and closes the straight shot | moves out toward the slot and keeps moving to cut the passes (frames 850-990) |
| Mix | 1140-1232 | switches between middle and near post | switches between the passive spot (down at the post, at 1220 turned round: "the back") and the active spot up the slot |

At the end (frames 1470-1610) the presenter places pucks by hand to show what the attacker is looking for: a goal in
the short (near) corner or in the far corner.

**The centrifuge** (Swedish *centrifugen*; Bordshockeyskolan lesson 3): the left wing carries the puck up from the goal
line and passes it into the slot. The centre waits there with the stick aimed at the goal and shoots first time. On
puck.no it is only mentioned ("see Sentrifugo") and has no page of its own.

## How the video shows it

All three defences are set against the same situation:
- **The attacker:** W-LW holds the puck at the +y boards, level with the face-off circle. W-C waits in the slot.
- **The defenders:** the goalie E-G and the defender on the left wing's side, E-RD (its slot runs along the near-post
  side of the goal).
- **The attacker's options** are drawn as **lanes**:
  - the straight shot at the goal;
  - the centrifuge pass to the centre;
  - the centre's first-time shot into the far corner.
- Each lane is swept with the finite puck. Where it would first touch the goalie or the defender it ends in a red
  cross; otherwise it is green (open).
- The lanes are graphics only. The puck itself never leaves the left wing's blade, so no blocked shot is simulated: a
  hard shot that hits a figure would rebound, which the traces do not model (CLAUDE.md "Slide or bounce").

| Set-up | Goalie | Defender | Straight shot | Centrifuge pass | Centre's shot |
| --- | --- | --- | --- | --- | --- |
| Neutral (no defence) | middle | half-way up its slot | **open** (goal) | — | — |
| Passive (the box) | middle (y = 0) | in front of the goal on the straight-shot line (slot position 164 mm) | blocked by the defender | open | met by the goalie |
| Active | near post (y = 33 mm), **back to the puck** (heading 300°) | out in the passing lane (slot position 89 mm), turned toward the puck | blocked by the goalie | cut by the defender | open, if a pass got through (the risk of going active; not shown) |
| Mix | switches: passive → active → passive | | as above in each phase | | |

Positions follow the idea of each defence, not the TikTok's exact spots (the user allowed this):
- **The left wing stands further out** than in the TikTok's corner. From near the goal line, a flat straight shot
  can't pass the near post of our preview goal:
  - the window between the posts is under 8°;
  - the clearance from the post is less than the puck radius plus the post radius.
  - So there would be no straight-shot lane for the defence to close. From the face-off circle the window is 11°.
- **The defender's positions** are where the straight-shot line (passive) and the centrifuge-pass line (active) cross
  its slot.
- **Not shown:** "In front, or you can use the back as well" in the mix. In the TikTok the defender sometimes blocks
  turned round, with its back. The defender here always turns to face the puck.

## Checks

- **Contact physics** (`shots/defence-left-wing/checks.json`). The finite puck is checked against all 12 figures, the
  boards and the posts every 0.25 ms:
  - no overlap and no exception;
  - the puck only touches the left wing's blade (0.05 mm clearance);
  - nothing changes its motion (the slide check has no impacts).
- **The concept** (`tests/defence.test.ts`):
  - neutral: the straight shot is open;
  - every passive phase: the defender blocks the straight shot, the pass is open, the goalie meets the centre's shot;
  - every active phase: the goalie blocks the straight shot and the defender cuts the pass;
  - the goalie is at the near post when active and in the middle when passive;
  - when active, the goalie faces away from the puck (back to the corner), within 2°; when passive it is square;
  - the mix switches passive → active → passive.
- **Video:**
  - each chapter is shown at least 3.5 s with a still camera, at no more than 4 words per second;
  - camera steps stay under 60 mm per frame;
  - the puck is visible in every frame (ray-cast against the figure meshes);
  - every frame's state equals the pure evaluation (render report).
- **Other videos unchanged.** The shared `remotion/AnalysisVideo.tsx` gained the lane graphic, red and green accents
  and a label for the banner. Frames 30, 200, 400, 510, 660 and 730 of the Shovel, spjass, Näcka and IKV videos are
  byte-identical before and after. This is recorded in their reports as `composition_refactor`; they were not
  re-rendered.

## Video structure (35.4 s)

| Time | Shows |
| --- | --- |
| 0-1.5 s | title |
| 1.5-7.5 s | **THE LEFT WING HAS THE PUCK**: the two threats (straight shot; centrifuge pass and the centre's shot) |
| 7.5-16.5 s | **1 PASSIVE · THE BOX**: the defender and goalie set up; shot blocked, pass open, goalie there |
| 16.5-24.2 s | **2 ACTIVE**: the goalie to the near post, turning its back to the corner; the defender out; shot closed, pass cut |
| 24.2-31.4 s | **3 THE MIX**: PASSIVE → ACTIVE → PASSIVE at ×0.5, with the lane each phase closes |
| 31.4-35.4 s | summary card |

The camera stands behind the defended goal, high, like the TikTok, and stays still after the intro.

## Assumptions to review

1. **The reading of the three defences** (above), from the captions and the demonstrations.
2. **The left wing's position** (further out than in the TikTok) and the defender's two positions.
3. **The goalie's turn when active:** it faces directly away from the puck (about 120°). That follows the user's
   description; the exact angle is not measured.
4. **The centrifuge** as the left wing's pass to the centre who shoots first time (Bordshockeyskolan). The user named
   it as an example; puck.no has no description.
5. **Lanes are straight lines** (flat shots and passes); lifted shots are not considered.
6. Preview figure, puck and goal sizes; the other figures stand in their assembly poses.
