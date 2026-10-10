# NM 2026 semi-final: how the game works and the common patterns

Status: written on 2026-10-08 at the user's request: *"use the video to gain a full understanding of how the game works
and document any new findings. What are the common patterns etc."*

**Status of the findings:**
- Every finding is from the NM26 broadcast video: Nygård vs Fjermestad, seven games, 59 minutes.
- **Observed** findings come from the timer tones, the score graphics, the picture-in-picture camera or the frames, with
  video times.
- **Measured** findings come from the automatic puck tracks of all seven games. Those are PROPOSED: not user-confirmed,
  and the error sources are in `docs/nm26-passes.md`.
- **Open** points are questions for the user (section 8). Nothing open is assumed elsewhere in the repo.

What was already known (rules, the Fylling vs Moe match) is in `docs/game-mechanics.md`.

**Data:**

| What | Where |
| --- | --- |
| Game windows, timer tones, every goal from the score graphics, ends | `data/games/nm26-semifinal/timeline.json` |
| Puck tracks and flight events, games 2-7 (new; game 1 as before) | `data/games/nm26-semifinal/g2/` … `g7/` |
| Cross-game numbers (zones, possession per role, holds, chains, passes by role, tempo) | `data/games/nm26-semifinal/patterns.json` (`scripts/nm26-patterns.py`) |
| Where each player's figures have the puck | `validation/nm26-control-nygard.png`, `validation/nm26-control-fjermestad.png` |

## 1. The match format (observed)

**Timer tone.** Each game starts with a tone of about 1.85 kHz with harmonics, about 3.4 s long. The same tone ends
the game 300 s later. The pairs found in the audio:

| Game | Start tone (video s) | End tone | Regulation ends | Overtime |
| --- | --- | --- | --- | --- |
| 1 | 21.6 | not heard | **about 382 s (see below)** | yes, winner at about 533 s |
| 2 | 772.4 | 1073.5 | at the tone | no |
| 3 | 1356.1 | 1654.5 | at the tone | no |
| 4 | 1771.6 | not heard (masked) | about 2072 s | yes |
| 5 | 2322.3 | 2622.9 | at the tone | yes, winner shown at 2680 s |
| 6 | 2779.7 | 3080.6 | at the tone | no |
| 7 | 3253.7 | after the video ends | — | no |

- **Games are 5 minutes, and the clock runs through goals** (rule 4.2). In game 2 the puck stops moving within the
  2.5 s window of the end tone. In games 3-5 the movement fades within 15-20 s after the tone (handling and the
  puck being collected).
- **Game 1 is the exception.** Play runs without any stop of 5 s or more from 21.6 s to about 382 s: 360 s, not 300 s.
  - No end tone is heard at 321.6 s, and play continues through it.
  - At about 382 s, play stops with the puck resting in the neutral zone and the players away from the rods.
  - Hands are on the ice from about 405 s.
  - The puck rests on the centre spot from 447.9 s to 468.8 s, then overtime starts.
  - I don't know why (open question Q1).
- **Before overtime, the puck rests on the centre spot for about 21 s** (game 1: 447.9-468.8 s; game 5:
  2633.9-2654.7 s). This looks like a fixed wait before the overtime face-off.
- **Breaks between games:** about 4-5 minutes after games 1 and 2, then 1.5-3 minutes.

## 2. Ends, figures and the score graphics (observed, new)

**The figures stay with the table; the players move.**
- The left end always has the white/blue figures and the right end the yellow figures. The goalie colours are the same
  in every game.
- The players switch ends **2-2-1-1-1**:
  - Nygård is at the left end (white/blue figures) in games 1, 2, 5 and 7;
  - he is at the right end (**yellow** figures) in games 3, 4 and 6.
  - The picture-in-picture camera of the players shows who stands where.
- So a kit colour does not identify a player. `config.json` now records the figures by end
  (`figure_colours_by_end`) and the left-end player per game (`team_W`).

**The score graphics count goals by end, not by player.**
- The box prints "Nygård" over the left cell and "Fjermestad" over the right one, but each cell counts the goals of an
  **end**.
- Read that way, all seven results match the user's.
- The series score in the box is not reliable: it shows 2-1 after game 3 and 3-2 from 2899 s, where the results give
  1-2 and 2-3.
- The box updates at about the restart drop, so a goal happens a few seconds before its box time. In game 1 the box
  changes just when the puck reappears on the centre spot (181, 233 and 243 s).

**The camera.**
- One fixed camera. It was moved once, between games 2 and 3: games 3-7 are about 12% zoomed in.
- Every frame of every game registers to game 1's reference frame (190-420 matched features).
- So **one calibration covers all seven games**. The slot centrelines sit on the slots in game 3's background.
- Registration failed only for 8 s in game 6 (3047-3055 s), when something blocked the camera.

## 3. Goals (observed, from the score graphics)

| Game | Result (Nygård first) | Goals in game time (s), scorer | Overtime |
| --- | --- | --- | --- |
| 1 | 3:4 | 70 N, 73 N, 159 F, 212 F, 221 N, 267 F | F (about 511 s game time) |
| 2 | 3:1 | 112 F, 158 N, 177 N, 188 N | — |
| 3 | 3:5 | 43 N, 53 F, 73 F, 156 F, 178 N, 190 F, 215 N, 282 F | — |
| 4 | 3:2 | 95 N, 283 F, 288 F, ≈300 N (box at 308) | N (never shown) |
| 5 | 3:4 | 34 F, 74 F, 205 F, 239 N, 253 N, 286 N | F |
| 6 | 5:1 | 33 N, 125 N, 136 F, 175 N, 211 N, 227 N | — |
| 7 | 1:3 | 129 N, 147 F, 228 F, 262 F | — |

The times are box-change times, so each goal is a few seconds earlier. The two Nygård goals 3 s apart in game 1
(70 s, 73 s) may be a late entry (Q2).

**Patterns:**
- **41 goals:** Nygård 21, Fjermestad 20. 37 are in regulation, about 7.4 per game.
- **3 of 7 games went to overtime** (1, 4 and 5). Overtime play lasted about 64 s in game 1, about 25 s in game 5 and
  under 2 minutes in game 4.
- **Goals come late:** by minute of regulation (box times) 4, 6, 10, 10, 7. Seven come in the last minute, and two late equalisers
  forced overtime (game 4 at about 300 s, game 5 at 286 s).
- **Leads don't hold:** the first scorer won only 2 of 7 games.
  - Game 1: Nygård led 2-0 and lost.
  - Game 5: Fjermestad led 3-0, Nygård tied it, Fjermestad won in overtime.
  - Game 4: Nygård led 1-0, trailed 1-2 and won in overtime.
- **End:** the right-end (yellow) figures scored 23 and the left-end figures 18. That is not a clear table effect with
  this many goals.

I did not pin down each goal's exact moment or shot: the puck is hidden in the cage and the track continues through the
retrieval. To study how goals are scored, each goal's moment is needed, from a cage view detector or from the user (Q3).

## 4. How play flows (measured, 7 games, about 40 minutes of live play)

- **Tempo:**
  - 15-25 puck flights of at least 100 mm per minute of play, median 20;
  - 13-20 changes of possession or battles per minute.
- **Puck speed:**
  - the median flight is 0.8-0.9 m/s in every game;
  - in game 1, 10% exceed about 2.2 m/s;
  - 34-43% of flights use the boards.
- **Where the puck is, from each player's own end:**
  - 24% of the time in the neutral zone;
  - Nygård's attacking end 42%, Fjermestad's attacking end 34%.
- **Who can reach it:**
  - one figure alone 79.3% of the time;
  - two or more figures 20.4% (contested, mostly battles and the face-off area);
  - no figure 0.3%.
  - Goalies are almost never alone: their area overlaps the defenders'.
- **Wings own the corners.** The corner and the end board behind the opponent's goal belong to the attacking wings,
  and that is where the puck spends most time. The left wing and right wing of the two players together have the puck
  alone 50% of the time. The defenders and centres have it 29%, the goalies 0.2%.

## 5. Common patterns (measured)

**Seen from each player's own end: he attacks to the right, and "left" is his left.**

1. **Left defence → left wing is the standard outlet**, for both players:
   - Nygård 30 times, Fjermestad 21;
   - about 490 mm;
   - 57% off the boards: along the left board, often into the corner beside or behind the goal.
2. **The left wing then holds the puck in the attacking corner**, and the opponent's right defence takes it back:
   - left wing → opponent's right defence is Nygård's most common change of possession (31);
   - the most common three-step chain for both players is **left defence → left wing → lost to the opponent's right
     defence** (Nygård 11, Fjermestad 8).
3. **Right wing → left wing behind the goal:**
   - Nygård 12 times, 92% off the boards (a rim pass round the end board), median 1.3 m/s;
   - Fjermestad 13 times, 46% off the boards.
4. **Wing → centre for the shot area:**
   - Fjermestad plays right wing → centre 16 times (short, 145 mm);
   - Nygård plays left wing → centre or right wing → centre 7 times each.
5. **Turnovers come where possession is longest:** the corners. A wing that holds the puck invites the opponent's
   defender on that side.
6. **Centre spot:** besides face-offs, the puck rests on the centre spot before each overtime and at the start of each
   game (1.5-2.3 s before the tone, in 6 of 7 games).

## 6. The two players (measured; switching ends separates the player from the table)

| From each player's own end | Nygård | Fjermestad |
| --- | --- | --- |
| Puck in his attacking end | **42%** | 34% |
| Puck on his left side (more than 60 mm off centre) | **47%** | 33% |
| His figures have the puck alone | 38.5% | 40.6% |
| Of which on the left wing | **19%** | 12% |
| Of which on the right wing | 7% | **12%** |
| Left wing holds: number, total, median, 90th percentile | 104, 358 s, **3.3 s**, 6.4 s | 81, 233 s, 2.0 s, 6.4 s |
| Right wing holds | 65, 134 s, 1.1 s | 71, 212 s, 2.1 s |
| Flights from his figures: passes, lost, shots (automatic) | 142, 131, 23 | 140, 146, 30 |

- **Nygård plays through his left wing.**
  - He puts the puck into the corner to his left in the opponent's end, holds it longer than anyone (median 3.3 s),
    works the end board behind the goal, and uses the rim pass right wing → left wing.
  - His control map is one band from the left corner round the end board (`validation/nm26-control-nygard.png`).
  - It is the same in every game, at either end: the puck is on the far side at the left end and on the near side at
    the right end. So the side asymmetry of a single game is the player's, not the table's.
- **Fjermestad uses both wings evenly**, holds less long, and plays more short passes to the centre and from the right
  defence.
  - His control map has a strong right-defence area in his own end and a right-wing area at the near board
    (`validation/nm26-control-fjermestad.png`).
  - The automatic shot count is higher (30 vs 23), but shots are undercounted for both (`docs/nm26-passes.md`).
- **Territory did not decide the games.**
  - Nygård had more of the puck in the attacking end in 5 of 7 games. His best territorial game (game 1, 52% vs 30%)
    was a loss, and he won games 2, 4 and 6.
  - Possession alone per game (`patterns.json` → `per_game`) does not track the results either.

## 7. What this means for the analysis

- **Kit colour is an end, not a player:** every per-player statistic must use the per-game end (`team_W`). The scripts
  do.
- **Dead time:** the box changes at the restart drop, so 10 s before each change removes the goal, the retrieval and
  the drop (used here). A proper stoppage detector (hands, the puck in the cage) is still missing.
- **Goals:** the box gives who scored and roughly when. The exact moment needs a cage view or the user.
- **Typical moves for videos:** the left-defence → left-wing outlet along the board and the right-wing → left-wing rim
  pass are the most common real moves. They are candidates for shot reconstructions like the earlier traces.

## 8. Open questions

1. **Game 1 ran 360 s before the stop at about 382 s, not 300 s.** Was the clock set wrongly, or was there an
   interruption I could not see? What happened between 382 s and the overtime face-off at 468.8 s?
2. Game 1: the box shows Nygård 1-0 at 92 s and 2-0 at 95 s. Two goals 3 s apart, or one goal entered late?
3. Would you give the exact times of some goals (or confirm the box times minus a few seconds)? Then I can study how
   goals are scored.
4. Is the 21 s wait on the centre spot before overtime a rule (an overtime start signal), or this tournament's practice?
