# Game mechanics: the ITHF rules and one recorded match

Status: written on 2026-10-07 at the user's request. This is not a numbered iteration and nothing was built. The
user said: *"Here is one game from a handheld camera ... probably the trickiest angle you can possibly get. If we make
it work here we make it work for proper setups too ... I would like you to get a full understanding of the game
mechanics before continuing with anything more complex. Document it in the repo. Don't make assumptions, ask me if
you are unsure."*

**Answers from the user (2026-10-07)** are recorded as A1-A10 in section 6 and used throughout. The most important:
Fylling is the left player; the match was 1-1 after 5 minutes and Fylling won 2-1 in overtime; the table has the same
layout as the repo's model; "puck on a player" means the figure's area: the puck is on a figure when no other figure
can reach it.

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
the 2023 vote (printed in red). The user: the version "does not matter in this case" (A3).

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
- Rule 5 does not say who drops after a goal. Rules 8.2, 9.7 and 11 say the opponent drops in those cases. The user:
  there is "no clear rule", and there was no referee in this match (A5). So the dropper after a goal is not fixed.

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
  - The user confirmed it is the same table family and slot layout as the repo's model (A9). Only the artwork
    differs, so the repo's geometry can be used to calibrate this video.
- Teams: yellow/blue figures against white/blue figures.
- The goal at the left end has a yellow goalie. The right goalie's colour was not confirmed at this resolution.
- Two red goal cages. The user: the cups were removed and deflectors were used (A6).
- **The players stand at the two short ends.** Rods come out at the ends (visible on the left).
  - The left player wears a dark shirt and red trousers.
  - The right player wears a grey T-shirt and glasses.
  - **Fylling is the left player and Moe the right player** (A1).
  - Each player's goalie rod comes out behind the goal at their own end, so Fylling defends the left goal (the yellow
    goalie) and attacks the right goal; Moe the reverse. The team colours follow from the rods, not from a user
    statement.

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
- The user confirmed the start and final signals and the thirds (A4).

### The start (observed)

- From about 3.5 s to 7.1 s the puck rests on the centre spot with the figures still.
- By 7.9 s the centre figures move (motion blur) and the puck has left the spot.
- This matches rule 5.1 and the start signal at about 7.5 s.

## 4. Goals, stoppages and hands in the recording

### What the result implies

- **1-1 at full time (A2):** the recording holds exactly two valid goals, one by each player. Fylling (left) scores in
  the right goal, Moe (right) in the left goal.
- **The overtime goal is not in the recording.** The video ends at 310.25 s, 2.75 s after the final signal, and
  overtime starts with a new face-off (4.8).
- **No calls in this match** (A7, "I don't think so"): no passive-play, 5-second, block, hand or interruption
  face-offs. So, apart from the opening, the only face-offs in regulation time should be the two after the goals.

### Hands near the ice

Hands were found by differencing each stabilised frame from the median background, combined with a skin-colour test
(20 episodes; the detector is unreliable, and many hits are hands on the rods or at the board edges). Five were
inspected frame by frame, zoomed:

| Video time | What is visible | Reading |
| --- | --- | --- |
| 24.8-25.4 | the right player's hand comes in over the right half, down to the figures in front of the right goal; the puck was not located in these frames | not decided; looks like a hand at the figures, not a retrieval |
| 89.6 | the left player's hand reaches to a figure left of centre while the puck is near the right face-off circle | a hand at a figure, not a drop |
| 132.4-133.2 | the puck lies **behind** the right goal (between the cage and the end board); a hand follows at 133.7-134.6 | not a goal |
| 175.9-176.6 | the puck behind the right goal again | not a goal |
| 176.8-177.4 | the left player's hand pinches the head of his own goalie and lets go; the goalie's pose changes slightly; the puck is at the other end | **adjusting or tapping down a figure** (rule 9.1, 9.3), not a stoppage |

So the hands over the ice are **mostly players adjusting their own figures**, not face-offs. Rule 9.1 allows tapping
down only with complete possession; whether these were legal is not judged here.

Other untested episodes (video time, s): 51.5-52.0, 58.8-59.0, 92.8-94.5, 115.1, 125.0, 154.7-155.7, 206.1, 220.0-220.4,
230.8-231.6, 239.3-240.4, 249.0-252.0, 257.9-258.4, 294.6-294.9, 298.1-299.4; 309.3-310.2 is after the final signal.

### Not found yet: the two goals

- The puck rests visibly on the centre spot only before the start (3.3-7.8 s). A dark-pixel test on the centre spot
  found one other run of at least 0.4 s (177.6-178.5 s). There, figures crowd the centre circle, and no drop is visible
  just before it.
- A dark-pixel test inside the right cage found only the two behind-the-goal episodes above.
- The inside of the left cage is seen through the red net from behind. The test cannot see a puck there.
- **So I have not located either goal.** I am asking for their times (Q11) rather than guessing.

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

## 6. Questions and answers

The user's answers (2026-10-07), verbatim where short:

| # | Question | Answer |
| --- | --- | --- |
| A1 | Who is who? | "left": **Fylling is the left player** (dark shirt, red trousers), Moe the right (grey T-shirt, glasses). |
| A2 | The result | "2-1 overtime to Fylling. So 1-1 after 5 minutes." |
| A3 | Rule version (2022 vs the 2023 PDF) | "does not matter in this case" |
| A4 | Timer signals at about 7.5 s and 307.5 s, interval signals at thirds | "yes" |
| A5 | Who drops after a goal; a referee? | "no clear rule. No referee was there" |
| A6 | Cups removed; deflectors used? | "yes and yes" |
| A7 | Any passive-play, 5-second, block, hand or interruption calls? | "i dont think so" |
| A8 | Unofficial habits that would show in a recording? | "no" |
| A9 | Same table family and slot layout as the repo's model? | "yes" |
| A10 | What "puck on a player" means for the possession counts | "figures area I would say. If no other figures can reach the puck" |

**The possession definition (A10), as I read it.** The puck is *on* a figure while it lies where that figure, and no
other figure, can reach it. That is the "figure's area" of rule 8.3.
- Each figure's area is everything its stick and body can touch, over all slot positions and rotations. It comes from
  the table geometry (A9: the repo's slots apply), not from the video.
- Where two or more figures' areas overlap, the puck is on nobody.
- Touches do not matter by themselves: the count follows where the puck *is*.

### Open questions

11. **When were the two regulation goals?** Roughly, in video time, and who scored first. I could not find either
    (section 4).
12. **"No other figures":** does that mean no figure of *either* team, or only no *opposing* figure? For example, the
    puck between your own centre and your own wing, out of the opponent's reach: is that on nobody, or on your team?
13. **The count:** per figure (6 per side), or per player? And as time on the puck, the number of times, or both?
14. **The goalie:** does the puck in the goalie's area count as on the goalie, like any other figure?
15. **Dead puck:** is the puck on nobody during a stoppage, a retrieval, or while a hand adjusts a figure?
