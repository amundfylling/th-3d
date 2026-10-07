# Game mechanics: the ITHF rules and one recorded match

Status: written on 2026-10-07 at the user's request. This is not a numbered iteration and nothing was built. The
user said: *"Here is one game from a handheld camera ... probably the trickiest angle you can possibly get. If we make
it work here we make it work for proper setups too ... I would like you to get a full understanding of the game
mechanics before continuing with anything more complex. Document it in the repo. Don't make assumptions, ask me if
you are unsure."*

This page separates three kinds of statement:
- **Rule**: from the official text, with its rule number.
- **Observed**: seen or measured in the match video, with the video time.
- **Open**: not known. Each one is a question for the user in the last section. Nothing open is assumed anywhere else
  in the repo.

| Source | Path |
| --- | --- |
| ITHF Game Rules, valid from 21 Aug 2023 (6 pages; fetched from the URL the user gave) | `references/rules/ithf-game-rules.pdf` |
| Fylling vs Moe, Trondheim Open 2022, final (user upload) | `references/games/fylling-vs-moe-trondheim-open-2022-final.mov` |

Both files are indexed in `references/index.json` with sha256 and size.

## 1. The rules, as they matter for analysing a match

The rules PDF is the 2023 version. The match was played in 2022, before it took effect. Only rule 6.1 was changed by
the 2023 vote (printed in red). Which wording applied in 2022 is open (Q3).

### Equipment and figures (rules 2-3)

- Stiga games only (2.1). The goal cups (the goal inserts) are removed (2.2). The game is fastened to the table (2.3).
  The surface speed is the factory speed (2.4).
- A player may put a puck deflector in the opponent's goal, but must offer the opponent the same (2.5).
- Figures are the Play-off figures: **every figure has its stick on the same side** (3.1). This matches rule 5 of
  `CLAUDE.md` (fixed physical handedness).

### Time (rule 4)

- A match lasts **5 minutes** (4.1). **The clock runs even while the puck is out of play** (4.2): there are no
  stoppages of time for goals, face-offs or retrievals.
- An audio timer is used (4.3):
  - a clear signal 15-30 s before the start;
  - interval signals at thirds or at minutes;
  - music during the last 30 s;
  - a clear final signal (4.4).
- Interrupted matches keep their goals (4.5). A play-off draw goes to sudden-death overtime that starts with a new
  face-off (4.8).
- Lost time from an interruption is added (10.2). A broken timer suspends play (10.5).

### Face-offs (rule 5)

- **The match starts with the puck on the centre spot**, and play begins at the opening signal (5.1). Playing it
  before the signal gives a face-off.
- Every later face-off is a **drop on the centre spot** (5.2):
  - the puck is released visibly, about 5 cm above the figures' heads, flat side down, with a still hand (5.4);
  - the centres and left defenders wait on their own side of the red centre line, outside the centre circle, and may
    not touch the puck before it lands (5.3);
  - the dropper makes sure the opponent is ready; a bad drop may be redone (5.5).
- **No valid goal for 3 s after a face-off** (5.6). A goal after a face-off also needs one of the following, all at
  least 3 s after the face-off (5.7):
  - (a) the puck touches a side board;
  - (b) the puck touches a figure other than the attacking centre or the defending goalie;
  - (c) a deliberate pass to the centre.
- Rule 5 does not say who drops after a goal. Rules 8.2, 9.7 and 11 say the opponent drops in those cases. Open (Q5).

### Goals (rule 6)

- **6.1 (2023 text):** a goal is scored when the puck was directed between the posts, in front of and below the
  crossbar, completely crossed the red goal line, and did not fly back out (crossing this line again or stopping on
  it).
- The puck is taken out of the puck catcher, if there is one, before the next face-off (6.2).
- **Goals that do not count:**
  - pressing a motionless puck against the attacking player's goal cage or goalie, unless it touches a side board or
    another attacking figure on the way in (6.3);
  - stabilising the puck and then hitting it with the body (not the stick) of a figure, unless it touches a side
    board or either player's left or right winger on the way in (6.4). Scoring with the right foot used as a stick
    (by rotating the figure) is allowed;
  - a goal scored while the final buzzer is sounding (6.5);
  - a goal scored by moving the whole game (6.7);
  - a goal scored during an interruption (10.1, 10.3).
- A goal stands if a figure breaks while it is scored (6.6), and if the opponent was tapping figures down (9.2).

### Goal crease (rule 7)

- A puck stopped **on the goal line**: the defender may call "block", and a new face-off follows (7.1).
- A puck at full rest **in the crease**, not touching the line: the defender must play it (7.2).

### Possession (rule 8)

- **Passive play** means keeping the puck without a recognisable attempt to score (8.1). After the opponent says
  "passive play", the player has 3 s to shoot at goal or pass to their centre (other passes are allowed within the
  3 s). Otherwise there is a face-off, and the opponent drops the puck (8.2).
- **5 seconds:** if one figure keeps the puck without passing or shooting, the opponent may warn after 5 s. Within 1 s
  the puck must enter an area where an opposing figure can touch it. Otherwise the opponent may say "stop" and do a
  face-off (8.3).
- With a referee there is a possession timer that signals at 5 s and 6 s. The referee resets it "whenever the puck
  moves from one figure's area to another" (8.3). The rules have **a notion of a figure's area**, but they do not
  define it.
- Referees for disputes and repeat offenders (8.4, 8.5).

### Interference (rule 9)

- Figures that pop up on their pegs may be tapped down only by a player in complete possession (9.1). The opponent may
  stop and ask for it (9.3). Passing while tapping gives a face-off (9.4).
- Shaking the game so that the puck moves is forbidden (9.5). A figure that loses the puck that way gets it back
  (9.6).
- Hands and arms stay away from the ice. **If a hand touches the moving puck**, the opponent chooses: place the puck
  where it would probably have gone (in goal, beside a figure), or a face-off that the opponent may drop (9.7).

### Interruptions (rule 10)

- A major disturbance suspends the match at once. Examples: broken gear, the lights going out, several pucks on the
  ice. A minor one needs a "stop" call; otherwise any goal counts (10.1).
- When play resumes: **if a player had indisputable control, the puck goes back where it was; otherwise there is a
  face-off** (10.4).

### Rule 11: defender → goalie → other defender

A pass from a defender to the goalie that the opponent cannot intercept may not be followed by an uninterceptable
pass from the goalie to the other defender. If both happen in succession, there is a face-off, and the opponent may
drop.

## 2. The match as a sequence of states (from the rules only)

| State | Starts | Ends |
| --- | --- | --- |
| Before the match | the pre-start signal (15-30 s before) | the opening signal (5.1) |
| Live play | the opening signal, or a face-off drop landing | a goal, a stop, or the final signal |
| Dead puck | a goal (6.1), "block" (7.1), a passive or 5-second face-off (8.2, 8.3), a hand on the puck (9.7), a pass while tapping (9.4), rule 11, an interruption (10) | a face-off drop on the centre spot, or the puck placed back (9.6, 9.7, 10.4) |
| Protected after a face-off | the drop | 3 s have passed and condition 5.7 (a), (b) or (c) is met; until then a goal does not count |
| End | the final signal (a goal during it does not count, 6.5) | sudden-death overtime only in play-off matches (4.8) |

The clock runs in every state (4.2), so a match's 5 minutes include all dead-puck time.

What this means for analysing a recording, using the rules alone:
- Every goal is followed by a hand at the centre spot (the drop). Most other stoppages are too. Exceptions: the puck
  placed back by hand (9.6, 9.7, 10.4), and some calls that may happen without one (a "stop" call that is then waived).
- Who scored cannot be read from the score alone: a goal that does not count (5.6, 5.7, 6.3-6.5, 6.7, 10.3) looks the
  same on video.
- Rules 5.7, 6.3, 6.4, 8.3 and 11 depend on **which figure** touched the puck, not only which player.

## 3. The match video: what is established

### File

- H.264 640 × 360, 25 fps, 7756 frames, 310.25 s; AAC stereo 44.1 kHz.

### Table and setup (observed)

- A STIGA Play Off 21. The near side reads "PLAY OFF 21" and "PETER FORSBERG EDITION OF THE ORIGINAL HOCKEY GAME".
- The ice artwork differs from the repo's Sweden/Finland reference (71-1145-01):
  - a blue centre circle with a logo;
  - yellow circles at both goals;
  - sponsor logos (MECA, SPORT, Lidl) on the ice and boards.
  - Whether this is the same table family and slot layout is open (Q9).
- Teams: yellow/blue figures against white/blue figures.
- The goal at the left end has a yellow goalie. The right goalie's colour was not confirmed at this resolution.
- Two red goal cages, no visible inserts. The game rules require the cups to be removed (2.2); whether a
  deflector was used is open (Q6).
- **The players stand at the two short ends.** Rods come out at the ends (visible on the left).
  - The left player wears a dark shirt and red trousers.
  - The right player wears a grey T-shirt and glasses.
  - Which of them is Fylling and which is Moe is open (Q1).

### Camera (observed)

- Handheld, at the near long side, low and oblique. The whole rink is in view, about 380 px wide.
- The puck is about 10 px and a figure about 20 px tall. The far half of the rink is foreshortened, and the near board
  hides the bottom of the near figures.
- 0-5 s: the camera moves and translates. After that it holds roughly still, with small handheld drift.
  - Each frame was registered to frame 3000 with ORB features and a RANSAC homography (scratch analysis only, not in
    the repo). This works after about 5 s and is poor during the opening move.

### Timeline from the audio timer (observed)

The timer is audible. A spectrogram of the soundtrack shows:

| Video time | Sound | Fits rule |
| --- | --- | --- |
| about 7.5-12 s | a steady tone with harmonics at about 500, 1300, 1620, 2050, 2600 and 3200 Hz | the start signal (5.1) |
| 107.8 s | a short tonal signal | interval signal at one third (100 s of match time) (4.4) |
| 207.7 s | a short tonal signal | interval signal at two thirds (200 s) (4.4) |
| about 277.5-302.5 s | music (harmonic patterns) | music for the last 30 s (4.4) |
| about 307.5 s to the end (310.25 s) | the same tone as the start | the final signal (4.4) |

- The tone appears at 7.5 s and again at 307.5 s, exactly 300 s apart: **the match runs from video time about 7.5 s
  to 307.5 s**.
- The two interval signals fall at 100 s and 200 s of match time, which fits thirds.
- The music starts about 30 s before the end, but the onset is not sharp.
- The pre-start signal (15-30 s before) is not in the video; the recording starts about 7.5 s before the start.
- Whether these sounds are the ones the players heard is open (Q4).

### The start (observed)

- From about 3.5 s to 7.1 s the puck rests on the centre spot with the figures still.
- By 7.9 s the centre figures move (motion blur) and the puck has left the spot.
- This matches rule 5.1 and the start signal at about 7.5 s.

## 4. Observed but not interpreted

A hand over or near the ice marks a dead puck (a face-off drop or a retrieval), or a possible infringement. Hands
were found by differencing each stabilised frame from the median background, combined with a skin-colour test. The
detector is **unreliable**:
- many hits are hands on the rods or at the board edges, not over the ice;
- a drop by a hand of the same colour as the background can be missed.

Candidate episodes (video time, s):

| Video time | What is visible | Possible meaning (not decided) |
| --- | --- | --- |
| 24.9-25.5 | the right player's hand reaches over the right goal | puck taken out of the goal after a goal against the right player? |
| 25.7-27.5 | no clear drop at the centre spot; at 26.4 s the puck is near the left board, by the left goal | ? |
| 51.5-52.0 | hand | ? |
| 58.8-59.0 | hand | ? |
| 89.0-92.2 | a hand from the far side over the left/centre area (89.0-89.7); the puck near the right face-off circle (87-92) | ? |
| 92.8-94.5 | hand | ? |
| 115.1 | hand | ? |
| 125.0 | hand | ? |
| 133.7-134.6 | hand | ? |
| 154.7-155.7 | hand | ? |
| 176.7-177.6 | hand | ? |
| 206.1 | hand | ? |
| 220.0-220.4 | hand | ? |
| 230.8-231.6 | hand | ? |
| 239.3-240.4 | hand | ? |
| 249.0-252.0 | hand | ? |
| 257.9-258.4 | hand | ? |
| 294.6-294.9 | hand | ? |
| 298.1-299.4 | hand | ? |
| 309.3-310.2 | hand, after the final signal | the end of the match |

I have **not** decided from the video which of these are goals, face-offs, retrievals or nothing. At 360p, with this
angle, a puck entering a goal and a drop on the centre spot cannot be told apart reliably. The score and the goal
times are needed from the user (Q2) as ground truth.

## 5. What makes this recording hard (for any later analysis)

- **The puck is about 10 px.** In motion it blurs into a streak. It disappears behind figures, the goal cages and the
  near board.
- **Figures are about 20 px tall, and both teams share blue.** Telling which figure touched the puck (rules 5.7, 6.3,
  6.4, 8.3, 11) is near the limit of the image.
- **The perspective is strong:** across the rink, a millimetre spans roughly half as many pixels as along it (read
  from one frame), and the far side is smaller than the near side. A rink-plane homography is needed before any
  distance or speed.
- **Handheld drift:** every frame needs its own registration. The first 5 s are poor.
- **Hands and rods** at the near side and the ends cover the ice edges.
- **The sound helps:** the timer gives the match clock without reading any screen.

## 6. Questions for the user

Q1-Q2 and Q9-Q10 matter most before any modelling.

1. **Who is who?** Is Fylling the player at the left end (dark shirt, red trousers) or the right end (grey T-shirt,
   glasses)? Which team colour does each play: yellow or white/blue? Did they switch ends at any point?
2. **The result:** the final score, and if you know them, the goals in order (who scored, roughly when). They are the
   ground truth for the candidate episodes in section 4. Was there overtime (rule 4.8)?
3. **Rule version:** which rules applied at Trondheim Open 2022? The PDF is the 2023 version, and 6.1 changed in 2023.
   Is the old 6.1 wording needed?
4. **Timer:** were the start and final signals the ones heard at about 7.5 s and 307.5 s? Were the interval signals
   at thirds (100 s and 200 s)?
5. **Who drops after a goal:** the player who conceded, the scorer, or a neutral dropper? Was there a referee?
6. **Goals:** were the cups removed at this tournament table (your own table has none: docs/decisions.md D5)? Were
   deflectors used (rule 2.5)?
7. **Calls in this match:** were there any "passive play", "5 seconds", "block", hand-on-puck or interruption calls?
   If so, roughly when?
8. **Unofficial habits:** is there anything players commonly do that the rules don't describe and that would appear
   in a recording? For example, placing the puck instead of dropping it, or retrieving the puck from under the boards.
9. **The table:** is this the same table family and slot layout as the repo's model (Play Off 21, 71-1145-XX)? Or is
   the "Peter Forsberg edition" a different variant? It decides whether the repo's geometry can be used to calibrate
   this video.
10. **"Puck on a player" for the possession counts** (the earlier proposal): which definition do you want?
    - every touch by a figure;
    - control (the puck stays with one figure);
    - the "figure's area" of rule 8.3, as a referee would judge it.
    - Do goalie touches count? Do touches during a face-off scramble count?
