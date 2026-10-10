# Rebuilding a real NM26 goal in 3D: Nygård's Edwall shovel hat-trick (game 2)

Status: started 2026-10-09. The user chose it (answer "Yes" to the proposal after the goal review). Everything PROPOSED.

**The goals** (user labels, `data/games/nm26-semifinal/goal-labels.json`): Nygård (white/blue, left end) scores three
times in 33 s of game 2, at game clock 2:32, 2:52 and 3:04 (video 924.1, 944.9, 956.9 s). The user names all three
"Edwallskyffel lang": the right wing carries the puck forward in the slot with the heel groove and passes in to the
centre, who shoots into the left corner (NTHF catalogue, difficulty 4). Scorer: centre; last pass: right wing.

**Evidence so far** (`scripts/nm26-rebuild-evidence.py <goal_id>`; goal ids g2-goal2, g2-goal3, g2-goal4):
- every frame of the last 4 s, registered to the reference frame (`out/nm26/rebuild/<goal_id>/frames/`, not committed);
- the automatic puck track and the defending (E, yellow) goalie's pose per frame from model C
  (`data/games/nm26-semifinal/rebuild/<goal_id>-evidence.json`);
- contact sheets every 0.2 s: `validation/rebuild-g2-goal2-sheet.jpg` (-3); the goalie arrow is model C's facing.

**What the sheets show** (goals 2 and 3 checked):
- The same move both times: the puck is with the W right wing at the near board, just inside the offensive blue line,
  0.6 to 0.2 s before the goal; the goal follows within a frame or two (the shot is faster than the 30 fps track).
- The automatic puck track jumps between unrelated places in these windows and misses the pass and the shot. A trace
  needs the puck positions read frame by frame in the last 0.6 s (by hand or a refined detector).
- The yellow goalie faces down and to the left in the picture (towards the near-side attack) in most frames.

**Next:**
1. Skater poses for W-RW and W-C (and the defenders near the play) from the skater model, once trained.
2. Puck positions frame by frame through the carry, the pass and the shot.
3. A trace that passes the contact-physics and slide checks (CLAUDE.md), then the analysis video.
