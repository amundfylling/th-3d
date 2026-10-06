# Defending against the left wing: three defences (concept video)

Status: made on 2026-10-06 at the user's request. Not a numbered iteration. The user asked: *"make an illustration
about the three ways to defend when the opponent has the puck on the left winger. Before making the video, make sure
that you understand the three ways. It does not have to be precisely the same placement as the video, the important
part is showing the concept ... you could show examples of how the defence stops some shots, e.g. the centrifuge or
the direct shot, but don't focus on the shots themselves"*.

The trace `trace.defence-left-wing.v1` is **proposed** and **designed**. It is a concept illustration, not a recorded
shot.

**The goalie when active: four user corrections, settled before any full render.**
1. *"The goalie does not have the back outwards and cover the corner in active and mixed. When it stands with face
   facing forward it does not cover the direct shot at all."* The goalie turns with its back to the puck.
2. *"the goalie should not stand all the way out to the right ... cover more of the middle. It should however leave
   little space for the direct shots."* It moves in from the near post.
3. *"Do not proceed with rendering the full video before getting this right. The goalie can be rotated slightly more
   and moved slightly more to the goalie's left."* The goalie's left is toward the middle (−y).
4. *"Rotate it even further and move it more to the left. It should cover as much space as possible on the left side
   while still covering direct shots."*

For the last one I scanned the goalie's position on its slot against its turn. For each pose, straight shots from the
left wing were swept with the finite puck to every point across the goal (every 0.5 mm). The table shows how many of
those targets are reached ("open"), and how far left the goalie reaches:

| Goalie y (mm) | +30° turn | +35° | +40° | +45° | +50° | +55° | reaches y (mm) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| −9 | 0 | 0 | 0 | 0 | 1 | 6 | −20 |
| **−10** | 0 | 0 | 0 | **0** | 3 | 8 | **−21** |
| −11 | 0 | 0 | 0 | 1 | 5 | 11 | −22 |
| −12 | 0 | 0 | 0 | 4 | 8 | 13 | −23 |
| −13 | 0 | 1 | 3 | 6 | 10 | 15 | −24 |
| −14 | 2 | 3 | 5 | 8 | 13 | 18 | −25 |

(Turn = beyond facing directly away from the puck. Coarser scan: at y = −15 mm and below, straight shots get through
at every turn.)

**Chosen:** y = −10 mm, turned 45° beyond facing away from the puck (heading about 340°, about 160°
counter-clockwise from square).
- It reaches 21 mm left of the middle.
- Every straight shot is stopped, and so is the centre's far-corner shot.
- The margin: 1 mm further left, or 5° more turn, would start to open straight shots.
- Review images for the user: `validation/defence-goalie-review.png` (overhead, previous vs new;
  `scripts/defence-goalie-review.ts`) and `validation/defence-goalie-active-still.png` (the video's active freeze).

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
| Active | y = −10 mm, **back to the corner**, turned 45° beyond facing away from the puck (heading about 340°) | out in the passing lane (slot position 89 mm), turned toward the puck | blocked by the goalie | cut by the defender | met by the goalie |
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
  - when active, the goalie stands where `inputs.json` puts it and faces away from the puck plus the extra turn,
    within 2°;
  - when passive it is square, in the middle;
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
| 16.5-24.2 s | **2 ACTIVE**: the goalie turns its back to the corner and covers as much of the far side as it can; the defender goes out; shot closed, pass cut |
| 24.2-31.4 s | **3 THE MIX**: PASSIVE → ACTIVE → PASSIVE at ×0.5, with the lane each phase closes |
| 31.4-35.4 s | summary card |

The camera stands behind the defended goal, high, like the TikTok, and stays still after the intro.

## Assumptions to review

1. **The reading of the three defences** (above), from the captions and the demonstrations.
2. **The left wing's position** (further out than in the TikTok) and the defender's two positions.
3. **The goalie when active:** y = −10 mm and heading about 340°, the limit found by the scan for this left-wing
   position. It follows the user's four corrections; neither is measured from the TikTok.
4. **The centrifuge** as the left wing's pass to the centre who shoots first time (Bordshockeyskolan). The user named
   it as an example; puck.no has no description.
5. **Lanes are straight lines** (flat shots and passes); lifted shots are not considered.
6. Preview figure, puck and goal sizes; the other figures stand in their assembly poses.
