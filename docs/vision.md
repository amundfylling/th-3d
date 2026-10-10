# Vision and roadmap: where this project can go

Status: PROPOSED (2026-10-10, written at the user's request as workstream 8 of the parallel batch). Docs only; nothing
here is built by this document. It starts from the "Vision for the end result" answer in the project chat (2026-10-10)
and checks it against the repo.

Everything below is grounded in `docs/state.md`, `docs/nm26-figure-tracks.md`, `docs/nm26-game-patterns.md`,
`docs/rebuild-g2-edwall.md`, `docs/synthetic-goalie-pilot.md`, `docs/game-tracking.md`, `docs/review.md` and
`docs/table-hockey-playbook.md`. Workstreams 1-7 of the same batch (puck detector, Edwall rebuild, combination
recognition, tracker v3, all-goals replays, own-video pipeline, tests) were still running when this was written; their
results are not assumed here.

## 1. The one-line vision

**A match video in, an explained 3D shot out.** The project already does both halves separately: it explains designed
or reconstructed shots in 3D video, and it tracks real matches. The most valuable future joins them, first for
broadcast games, then for the user's own games, and collects the results in a shot encyclopedia.

## 2. What already works (the foundation)

| Capability | Evidence | Status |
| --- | --- | --- |
| Table model built on the real hardware | Rink, slots, goals, two rigid STIGA molds; `data/geometry.json`, `docs/players.md` | traced / assumed; only goalie height and blade measured |
| Trace format with physics gates | `shot-trace/1`; no-overlap check every 0.25 ms; `slide_check` (CLAUDE.md) | enforced by tests and the Remotion gate |
| Analysis videos from a shared template | `remotion/AnalysisVideo.tsx`; five videos (Shovel #17, Spjass, Näcka, IKV, defence vs LW) | Shovel accepted, the rest PROPOSED |
| Designed traces from text and sketches | Näcka, IKV (sketch approved by the user), defence | PROPOSED |
| Rules, playbook and the NTHF catalogue | `docs/game-mechanics.md`, `docs/table-hockey-playbook.md`, 121 moves in `data/combinations/nthf-catalogue.json` | sourced |
| Broadcast tracking, all seven NM26 games | One calibration for all games; puck track; every goal timed from the score box (`timeline.json`) | PROPOSED |
| Figure poses from synthetic renders | Goalie model C (facing 5° median on held-out games); skater v2b (rotation 7°, slot 1.3 mm against 152 user labels) | PROPOSED |
| Figure tracks, all 12 figures, all games | 23,756 frames; cleaned tracks with ~0.8% jumps at 30 fps | PROPOSED |
| Patterns that carry real information | The centre's position separates Spade, short and ordinary centrifuge; the Edwall hat-trick has one setup; Nygård plays through his left wing | PROPOSED, small samples |
| User-in-the-loop review pages | Pass review, goalie and skater label pages, goal label page (25 of 40 labelled) | in use |
| Own match (handheld phone) | Possession per skater, passes; puck seen in 40% of frames | PROPOSED, weak |

**The known gaps** that limit everything above:
- **The puck in flight.** It is a grey smudge; the automatic track misses passes and shots in the goal windows
  (`docs/rebuild-g2-edwall.md`). Workstream 1 targets this.
- **No stoppage detector** (goals, face-offs, hands on the ice).
- **No physical measurements** of the user's table beyond the goalie (`docs/review.md`: mechanism evidence "none").
- **Photorealism not reached.** Remotion/Three has no shadows; the bounded Cycles benchmark was never run.
- **Own video is handheld** and low resolution (640 × 360), so the puck is seen in only 40% of frames.
- **Nothing on real matches is user-confirmed** beyond the label sets.

## 3. Directions, ranked

Value: how much it gives the user (understanding, improving their own play, something worth sharing). Effort: in
thread sessions of the kind this project runs, S = one session, M = two to four, L = five or more or blocked on new
inputs. Ranking weighs value against effort and how much each item unlocks for the next.

| Rank | Direction | Value | Effort | Main dependency |
| --- | --- | --- | --- | --- |
| 1 | First real goal rebuilt in 3D (Edwall hat-trick) | High | S-M | puck in flight (workstream 1) |
| 2 | Shot encyclopedia (NTHF moves as explained videos) | High | M, then S per move | none; template exists |
| 3 | Own games: fixed-camera recording and match report | Very high | M | a phone mount over the user's table |
| 4 | NM26 goal atlas (every goal: replay, combination, setup) | High | S | workstreams 3 and 5 |
| 5 | Semi-automatic rebuild (tracks propose, user confirms, video renders) | Very high | L | 1 and 4 |
| 6 | Coaching tool (drills, "your attempt vs the reference") | High | M-L | 2 and 3 |
| 7 | Measure the user's table (a short measurement session) | Medium | S | user's time |
| 8 | Player scouting reports | Medium | S per player | more matches |
| 9 | Interactive 3D match explorer | Medium | M | 4 |
| 10 | Photoreal hero renders (Cycles) | Medium | S-M | none |
| 11 | Phone-format exports for sharing (9:16 clips) | Medium | S | 2 |
| 12 | A "what-if" physics sandbox | Low now | L | outside the current rules |

### 1. First real goal rebuilt in 3D: the Edwall hat-trick

- **What:** Nygård's three "Edwallskyffel lang" goals (game 2) as PROPOSED traces that pass the contact and slide
  checks, and one analysis video that overlays the three to show the identical setup.
- **Why first:** it closes the loop from broadcast video to explained 3D shot once. Every later item that uses real
  matches (4, 5, 6, 9) reuses the same steps. It also tests the figure tracks against a demanding use.
- **What already exists:** evidence packs and contact sheets, cleaned figure tracks for every frame of the three goal
  windows (`rebuild/g2-goal*-figures.json`), a measured repeatable setup (right wing u 0.11-0.15 facing 208-224°,
  centre at the back of its slot facing 302-329°).
- **Gap:** puck positions frame by frame in the last 0.6 s. If the detector is not enough, a user tap page for about
  60 frames is a cheap fallback (the label pages already exist).
- **Done when:** three traces saved with their checks, one video, and the user's verdict on whether it looks like the
  broadcast.
- **In flight:** workstream 2 of this batch.

### 2. Shot encyclopedia

- **What:** a growing library of explained moves: one short analysis video per NTHF combination, an index page by
  family, difficulty and scoring figure, and links to real examples where the NM26 tracks have one.
- **Why:** it is the project's original goal ("videos that explain shots") and the template is proven five times. The
  catalogue gives 121 named moves with text; the playbook groups them into families.
- **Effort:** the first step is M: make the designed-trace step reusable (today each trace has its own script:
  `nacka-trace.py`, `ikv-trace.py`, `defence-trace.py`). A shared library of moves (turn, step, push, soft catch,
  board run) with the slide and contact checks built in would make each new move about one session.
- **Order:** start with the moves that matter in real play: the two most common real patterns (left defence → left
  wing outlet, right wing → left wing rim pass, `docs/nm26-game-patterns.md` §5), then the shovels (25 in the
  catalogue, the most frequent real goals), then the centre tricks.
- **Risk:** designed traces are only as true as the description. Each should carry the user's approval of a sketch
  first, as IKV did; where a real example exists in NM26, compare against it.
- **Done when (first milestone):** ten moves, an index page, each move user-approved or marked PROPOSED.

### 3. Own games: fixed-camera recording and a match report

- **What:** the user records their own matches from a fixed phone over the table; the pipeline returns possession per
  figure, pass map, shot list, goal replays and a short report.
- **Why:** this is where the user's own play improves. NM26 shows what the synthetic approach can read from a fixed
  camera; the handheld recording shows what it cannot (40% puck visibility, `docs/game-tracking.md`).
- **The cheap lever:** a fixed camera. A phone on a stand, as overhead as possible, at 60 fps if the phone allows.
  That removes stabilisation, gives one calibration per session (as NM26 has one for seven games) and makes the
  synthetic renders a direct match for the camera.
- **Effort:** M. One calibration and plate set for the user's table, a camera solve, then the existing models,
  fine-tuned on renders in that camera (workstream 6 is testing this on the handheld match). The user's own table may
  differ in kits and artwork; a kit check like the NM26 one is needed.
- **Done when:** one recorded game produces a report the user agrees with on spot checks.

### 4. NM26 goal atlas

- **What:** every NM26 goal (40 labelled windows; 41 from the score box) with its top-down replay, the broadcast clip
  beside it, the combination family (user label or PROPOSED classifier) and the setup measures.
- **Why:** low effort now, because the tracks and labels exist, and it is the dataset that items 5, 6 and 8 need. It
  also answers "how are goals scored at the top level" with numbers.
- **In flight:** workstreams 3 (combination recognition) and 5 (all-goals replays). The remaining step is joining
  them into one page and asking the user to label the 15 unreviewed goals.

### 5. Semi-automatic rebuild

- **What:** from a goal window, the tracks propose a trace (figure paths from the smoothed tracks, puck contacts
  fitted between observations, checks run), the user confirms or corrects on a review page, and the video renders.
- **Why:** turns a rebuild from a one-off project into a routine, so the goal atlas can become a goals film of real
  3D reconstructions.
- **Effort:** L. Needs item 1 done once by hand, a reliable puck in flight, and a contact solver that turns noisy
  observations into a trace that passes the no-overlap and slide rules. Rule 8 (no general simulator) still holds: the
  solver fits contacts to observations, it does not simulate.
- **Keep the user in the loop.** The confirm step is what keeps the rebuilt goals true to what happened.

### 6. Coaching tool

- **What:** for a chosen move, a drill page: the reference video (item 2), the key contact and figure poses to aim
  for, and, once item 3 works, the user's own attempts tracked and compared (where the centre stood, how the figure
  turned, puck speed).
- **Why:** the shortest path from analysis to playing better. NM26 already shows which measures separate moves (the
  centre's slot position separates Spade, short and ordinary centrifuge).
- **Effort:** M-L, almost all of it in items 2 and 3.

### 7. Measure the user's table

- **What:** one short session where the user measures what the model only assumes: playing area, slot ends, the
  skater height, the pivot under the skate, blade size, puck diameter and thickness, goal opening (list in
  `docs/review.md` and `docs/players.md`).
- **Why:** cheap and raises the trust in every trace and contact check (today all contacts use the assumed preview
  scale). Not urgent for analysis; important for any claim of accuracy.

### 8. Player scouting reports

- **What:** per player: where their figures hold the puck, favourite outlets and goals, what they lose the puck to.
  The NM26 analysis already does this for two players (`docs/nm26-game-patterns.md` §6).
- **Value grows with matches.** One semi-final is a small sample; a second tournament (or the user's club games via
  item 3) is needed before it says much.

### 9. Interactive 3D match explorer

- **What:** scrub any moment of a game and see the 3D table with all twelve tracked figures, the puck and the
  possession. The 2D board page (`validation/game-possession-board.html`) is a start.
- **Why lower:** attractive, but the replays and the atlas carry most of the insight at less effort.

### 10. Photoreal hero renders

- **What:** run the bounded Cycles benchmark that `docs/review.md` specifies, then render one or two key shots in
  Cycles for the encyclopedia and the goals film.
- **Why:** "photorealistic" is in the project goal, and Cycles already looks better on the same scene. It does not
  change any analysis, so it ranks below the items that do.

### 11. Phone-format exports

- **What:** 9:16 versions of the analysis videos with captions, the format of the user's TikTok references.
- **Why:** low effort once the encyclopedia exists (a camera and layout variant in the template); useful for sharing
  with a club or online.

### 12. A "what-if" sandbox

- **What:** change a figure's pose and see whether the shot still goes in.
- **Why last:** it needs a general contact simulator, which rule 8 excludes for now, and the bounce behaviour the
  slide rule avoids. Revisit only after the semi-automatic rebuild has a working contact solver.

## 4. A realistic three-month path

1. **Month 1:** finish the Edwall rebuild (1), the goal atlas (4), the reusable designed-trace library and the first
   five encyclopedia moves (2). Buy or build the phone mount and record one own game (3).
2. **Month 2:** own-game pipeline on the fixed recording (3), ten encyclopedia moves, the table measurement session
   (7), the Cycles benchmark (10).
3. **Month 3:** the semi-automatic rebuild on the NM26 goals (5), the first drill pages (6), and a second tournament
   or a set of club games to prove the pipeline is not tuned to one video.

**The amazing but realistic end result:** a goals film of the NM26 semi-final rebuilt in 3D, each goal named by its
combination; a shot encyclopedia that links each move to a real goal; and a report for the user's own matches.

## 5. Things to avoid

- **Full automation without the user's check.** Every real-match result so far is PROPOSED; the label and review pages
  are a large part of what made the models good (skater slot error 18 mm → 1.3 mm from v1a to v2b, which added the
  user's labels and a new output head; the two effects were not separated).
- **A general physics simulator** before the contact solver exists (rule 8).
- **Tuning to one video.** One camera and one table are behind every NM26 number; test on a second source early.
- **Photorealism before content.** The template look is enough to explain shots; Cycles is for a few hero shots.

## 6. Questions for the user

1. Which matters most to you: understanding top-level play (1, 4, 5), explaining moves (2, 11) or improving your own
   game (3, 6)?
2. Can you record your own games from a fixed phone over the table? If so, from which side, and at what frame rate?
3. Should the encyclopedia follow the NTHF catalogue's order, or start with the moves you play yourself?
