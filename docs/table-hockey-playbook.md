# How table hockey is played: a playbook for future projects

Status: written on 2026-10-08 at the user's request: *"document how the game works in general. So future projects will
understand everything, not just the written rules. Like what are the common combinations etc."*

This is the starting point for any task about play: shots, combinations, tactics, tracking or videos.
- The written rules are digested in `docs/game-mechanics.md`; this page assumes them.
- For geometry, see `docs/geometry.md` and `data/geometry.json`.

**Every statement carries its source:**

| Tag | Source | Where |
| --- | --- | --- |
| **[NTHF]** | Norwegian Table Hockey Association: the combination catalogue (121 moves, difficulty 0-10) and the timer page | `references/combinations/puck-no-combination-catalogue-en.html` (parsed: `data/combinations/nthf-catalogue.json`), `references/rules/puck-no-timers-en.html` |
| **[BHS n]** | Bordshockeyskolan (Swedish table hockey school), lesson n (1-22 in English, 23-46 in Swedish) | `references/coaching/bordshockeyskolan-pages-2026-10-08.json` |
| **[ITHF x]** | ITHF game rules, rule x | `references/rules/ithf-game-rules.pdf`, `docs/game-mechanics.md` |
| **[Geometry]** | this repo's table model (slot centrelines, figure reach) | `data/geometry.json`, `data/games/nm26-semifinal/g1/passes.json` (reach) |
| **[NM26]** | measured or observed in the NM 2026 semi-final (7 games, Nygård vs Fjermestad). PROPOSED, from automatic tracks | `docs/nm26-game-patterns.md`, `data/games/nm26-semifinal/patterns.json` |
| **[TikTok]** | the user's instructional videos | `references/shots/*.mp4` |
| **[User]** | the user's answers and corrections | `docs/game-mechanics.md` section 6, the combination docs |

Where sources disagree or something is uncertain, it is said so and listed under **Open**. Nothing here overrides a
user statement.

## 1. The table, seen as a player

**What a player controls.**
- 12 figures, 6 per side: goalie (G), left and right defence (LD, RD), centre (C), left and right wing (LW, RW).
- Each figure stands on a rod from the player's end:
  - **push or pull** moves the figure along its slot ("forward" = toward the opponent's goal, as the catalogue's
    examples use it; its definition says the opposite, see Open 5 [NTHF]);
  - **turning** rotates it.
- Figures are rigid; the stick does not swing on its own (CLAUDE.md rule 5).
- **Two hands, eleven rods.**
  - Beginners hold the goalie with one hand. Good players let it go and use both hands on the outfield players [BHS 1].
  - Combinations that need a lever change mid-move are "three-hand combinations" (e.g. the Östlundare) [BHS 32].
  - Keep unused figures in fixed parking spots, so you can grab them without looking [BHS 28].
- **All sticks point the same way.**
  - Every figure holds its stick on the same side (rule 3.1) [ITHF 3.1].
  - At competitions all figures hold the stick to the left. Retail pre-painted teams mix left and right [BHS game
    care].
  - Every move below depends on that handedness.

**Parts of a figure that touch the puck** [NTHF, BHS]:
- **Blade (club, "klubba"):** forehand side and backhand side.
- **Heel and toe** of the blade.
- **Fixed foot** (the foot on the mounting) and **free foot** (the other).
- **Heel groove and toe groove:** the pockets where the puck sits against the figure.
- **The fork ("klykan")** between the stick and the fixed foot, where a carried puck rests.
- A puck you set up yourself may not be shot with the standing foot. Only the stick or the free foot may shoot it,
  unless the puck came from another figure [BHS 15]. Compare ITHF 6.4.

**The slots** [Geometry]. Seen from the left end (team W, attacking to the right; the player's left is the far side):

| Figure | Slot | What it means in play |
| --- | --- | --- |
| G | 83 mm across its goal mouth | blocks; rarely plays the puck on |
| LD | 433 mm along the left side, from **behind its own goal** to just past the centre line | the main outlet: the build-up to the left wing starts here [BHS 24] |
| RD | 237 mm along the right side, from about its own goal line to the neutral zone; **cannot go behind its goal** [BHS 28] | shorter; build-ups are harder [BHS 26] |
| C | 250 mm along the middle, from its own side of the centre line to about 95 mm before the opponent's goal line | receives passes and shoots; does the centre tricks in front of goal |
| LW | 495 mm from the neutral zone along the left board, then **turning 90° behind the opponent's goal** | the corner and behind-the-goal player; "tricky, has a life of its own in the corner" [BHS 1, 3] |
| RW | 454 mm straight along the right board, deep into the opponent's corner | the classic shooter and passer to the centre (shovels) [BHS 2] |

**Who faces whom.** Every slot lies next to one opponent slot. Each 1-on-1 below is a duel that recurs all game:

| Attacker | Faces |
| --- | --- |
| LW | the opponent's RD |
| RW | the opponent's LD |
| LD | the opponent's RW |
| RD | the opponent's LW |
| C | the opponent's C |

- In the NM26 games the most common loss of possession is exactly LW → opponent's RD [NM26].

**The puck and the ice.**
- The puck is a light, thin disk. It slides when pushed and lifts or bounces when struck hard (CLAUDE.md "Slide or
  bounce").
- Players use the lift on purpose:
  - snappy hits put the puck "up in the corner" or over sticks [BHS 2, 13, 15, 24];
  - a puck "standing on end" is hard for the goalie [BHS 13, 19, 22].
- **Boards are a passing surface.** Rim passes behind the goal (velodrome), board-banked passes and shots are
  standard.
- Sponsor stickers on the boards make bounces unpredictable [BHS 25].
- **Competition goals have deep cups** (rebuilt), because a goal counts only if the puck stays in [BHS game care,
  ITHF 2.2, 6.1].
- Games are lubricated, and rods are pushed in after a match so they don't bend [BHS game care, teaching page].

## 2. The match in practice

- **Format:**
  - 5 minutes with a running clock (the clock does not stop for goals);
  - 30 s of music before the start signal and 30 s before the end signal;
  - signals at 1/3 and 2/3 (Norway) [NTHF timers, ITHF 4].
  - In NM26 the start and end tones are 300 s apart, and play stops at the end tone. Game 1 is the exception: play ran
    about 360 s (open in `docs/nm26-game-patterns.md`) [NM26].
- **Series and ends:**
  - a play-off is a best-of series;
  - the players switch ends 2-2-1-1-1 [User, NM26].
  - **The figures stay with the table**, so a player's figure colour changes with the end [NM26].
- **Overtime:** sudden death after a new face-off [ITHF 4.8]. In NM26, 3 of 7 games went to overtime. The puck waits
  about 21 s on the centre spot before the overtime face-off [NM26].
- **Face-offs:** dropped on the centre spot [ITHF 5]. Restarts after goals take a few seconds: the puck is taken out of
  the cage and dropped [NM26].
- **Etiquette:** a "gentleman's sport". Shake hands and thank your opponent before and after [BHS teaching page].
  - Without a referee, the players call stops and face-offs themselves (e.g. 5 seconds, passive play, hand on the puck)
    [ITHF 8-9].
  - In the Fylling vs Moe final no such calls were made [User A7].
- **Physical side** [BHS 5, 14]:
  - stand or sit (standing is now most common);
  - posture matters over a long tournament day (20-30 matches for a beginner);
  - keep your energy; train 15 minutes a day rather than once a week.

## 3. The phases of play

### 3.1 Build-up from defence ("uppspel")

When you win the puck back, don't throw it forward: "nine times out of ten it fails". Take it with the defenders and
the goalie, breathe, and build up [BHS 24, 36].

**From the left defence (the easiest)** [BHS 24]:
1. **Lifted pass to the left wing (the standard).** Carry the puck in the fork between the red and blue lines. Pull the
   defender back a few centimetres, then push hard: the fixed foot's base plate lifts the puck over the opponent's
   sticks to the left wing. The force decides where it lands, from 10 cm down the board to round behind the goal to the
   right wing. "The most common way elite players build up."
2. Turn the defender quickly and pass across, between the centres, to the right wing.
3. Push the puck between the opponent's right wing and the board while carrying it forward.
4. A fast diagonal from low in your own end to the right wing.
5. A small wiggle, then a heel pass over to the centre (sets up a centre trick).

- A trick some players use: hook the left wing's stick over the opponent's right-wing stick and pull, to open a few
  millimetres for the pass.

**From the right defence (harder; six variants)** [BHS 26]:
- heel pass to the right wing at the blue line;
- a lifted pass;
- a Näcka-like pass down past the opponent's LD;
- from the forehand side, straight up to the centre or to the right wing ("the one most elite players use");
- a shot at a post that either scores or deflects off a centre out to a wing;
- a pass to the left wing.

**Where passes cross the opponent's lines** [BHS 28]:
- most passes cross between the red line and the face-off circle, above all around the blue line;
- most centrifuges cross the right defence's slot where the face-off circle crosses it.

**[NM26]** This is what the top players do most:
- LD → LW is the most common pass for both players (51 times in 7 games). It is about 490 mm long, and 57% go off the
  boards.
- After it, the left wing usually holds the puck in the corner.

### 3.2 Keeping the puck

- **Possession is defence:** "as long as you have the puck, the opponent cannot score" [BHS 14, 36].
- The 5-second limit per figure applies [ITHF 8.3]. Passing is constructive play and resets it [BHS 23].
- **Safe places:** along the boards. But the opponent's RW reaches the LW's last stretch at the offensive blue line much
  further than you think, and can hit the LW's free foot [BHS 36].
- **Keep the stick tucked in** (e.g. at the top of the LD slot). A stick pointing into the middle gets hit and you lose
  the puck. Opponents can also hit your figures with theirs to knock the puck away [BHS 36].
- **Don't butt against a wall of defenders:** take the puck back home and start again [BHS 36]. Players who pass well
  make the opponent chase, and chasing opens their defence [BHS 23].
- **[NM26] Where the puck is:**
  - one figure alone has it 79% of the time;
  - the **wings own the corners** and have the puck alone 50% of the time;
  - Nygård's left wing holds it longest (median 3.3 s per hold).

### 3.3 Creating the chance ("inspel"): the main attacking families

**Right wing → centre: the shovel ("Skyffel") family** [BHS 2, 6, 21; NTHF].
- RW between the centre line and the offensive blue line, stick to the boards, back to the goal, the puck behind it.
  It turns and passes across. The centre, standing back in the circle with its back to the goal, pushes forward and
  shoots first time.
- **Near-post or far-post** by the centre's stick angle.
- **The threat that makes it work: the Maltsev.**
  - The RW skips the pass, runs to the goal line and shoots at the near post. This freezes the opponent's LD, which
    opens the shovel again [BHS 6].
  - It is also catalogued as Maltzev / Smygar [NTHF].
- **Variants:**
  - Lindahl and Edwall shovels (carry with the stick or the heel groove);
  - Hæl, Gangsøy, Petterson and Wilkens shovels;
  - Trulsen (backward);
  - the Mexikaner (off the end board);
  - innspill passes.
  - 25 in the catalogue; most are difficulty 4-6 [NTHF].
- "Right shovel straight at the goalie" is difficulty 2; "into the corner" is 4 [NTHF].

**Left wing → centre: the centrifuge ("Centrifug") family** [BHS 3, 8, 10, 17].
- The LW carries the puck on the backhand side up from the goal line (or from behind the goal) to the face-off circle.
  It passes across the centre slot just below the blue line; the centre shoots first time.
- "It actually gives **more goals than the shovel**", but takes longer to learn [BHS 3].
- **The Insult ("Förolämpningen"):** the LW threatens a centrifuge, walks along the boards and shoots straight in at the
  post when the defender commits to the pass [BHS 8].
- **The Hook ("Kroken"):** the LW passes back to the LD, which returns it at once; the LW, now lower, shoots [BHS 10].
- **Short centrifuge:** a hard pass from near the goal off the centre's stick [BHS 17].
- **How the LW handles the corner:** push without turning and the figure walks past the puck in the corner, catching it
  on the backhand. Turn clockwise in the corner and the puck runs along the boards to the RW [BHS 3]. This is the push
  pass along the boards that CLAUDE.md's "Slide or bounce" describes (`references/shots/lw-board-pass-example.mov`).

**Behind the goal: velodrome, carousel, Gretzky** [BHS 4, 16; NTHF].
- **Velodrome:** LW → a hard rim pass behind the goal → RW, which meets it at the face-off circle and turns it into the
  goal. "Push the puck with the figure rather than hitting it with the stick."
- **Fakie velodrome:** RW → round the back → LW.
- **Karusell:** a velodrome followed by a pass to the centre.
- **Classic Gretzky:** RW → board pass → LW standing behind the goal → first-time pass → centre, which scores in the gap
  between the post and the opponent's RD slot. It needs a lever change mid-move.
- **[NM26]** Nygård's RW → LW passes go off the boards 92% of the time (12 times): the fakie-velodrome / Gretzky
  pattern.

**Defender shots and castlings** [BHS 12, 15; NTHF].
- **Castling ("Rockad"):** RD → hard pass → LD pushed forward. The LD's foot or stick lifts the puck into the near
  corner. Best right after winning the puck while the opponent is still attacking; dangerous if the opponent holds the
  centre (own goals) [BHS 12].
- **Defender shot:** a flicked shot from just inside your own blue line, lifted over the opponent's centre and RD
  sticks [BHS 15].
- **Kniv ("knife") moves:** a pass to a defender who shoots first time (Senterkniv, Fakie kniv, Reiersen, General
  Reiersen, Rokkade) [NTHF].
- **Bulldozer:** the RD carries the puck to the centre, which turns and drives it in by force. Once banned; now legal.
  Use it when the opponent leaves the lane open; don't build a game on it [BHS 11].
- **Prototype, Mårdellare, Östlundare:** LD (or RD → LD) heel pass across to a centre waiting low at its own blue line,
  which pushes it in before the defence resets [BHS 29, 31, 32, 46].

**Centre tricks ("centerfinter"), when the puck reaches the centre in front of goal** [BHS 13, 19, 22, 30, 33-35, 37;
NTHF].
- The goalie is "a wall" for a straight shot. Move the puck sideways and shoot in one motion, faster than the goalie
  can follow.
- **The basic set** (the centre with its back to the goalie, the puck in a groove):
  - **Lillstøvel / Little Boot (3):** a free-foot kick left, then a stick shot by the left post. The easiest.
  - **Näcka / Nacka / "Sydney" (4):** a free-foot putt right, then a counter-turn snap into the right corner.
  - **Spjass (5):** the stick pushes the puck about 1 cm left, a full spin, then a shot into the left corner. Shares the
    Näcka's start, so the goalie can't read the side.
  - **Omvendspjass (5):** the mirror of the spjass.
  - **Lillhæl (5).**
  - **Hjerpe / Hjärpe (6)** and **Søren / Sören (6):** the puck rolled round the stick's toe to the other side of the
    slot, then pushed in.
  - **Kiosk:** a lifted shot into a top corner over the goalie's shoulder. It is done mostly with the RD [BHS 27]; the
    centre version is Senterkiosk (8) [NTHF].
- **Every trick has a twin feint** with the same start and the other corner:
  - Hjerpefinte, Sørenfinte, C 29 (vs Lillstøvel);
  - Näckafinte, Spjassfinte;
  - Hansen (looks like a Lillstøvel, ends as a Näcka).
- "Learn at least two centre tricks" [BHS 13].
- Grip matters, and experienced players read the fingers on the lever, so some hide them [BHS 13, 19].
- **[TikTok, User]** The repo's spjass and Näcka reconstructions (`docs/spjass.md`, `docs/nacka.md`) follow these
  descriptions.

**The governing principle: pairs.** Almost every move is taught with a partner from the same start position:

| Move | Partner |
| --- | --- |
| Shovel | Maltsev |
| Centrifuge | Insult, Hook |
| Lillstøvel | C 29, Hansen |
| Näcka | Spjass |
| Hjerpe | Hjerpefinte |
| Prototype | Mårdellare |

The defender cannot cover both, and showing one opens the other [BHS 6, 8, 10, 19, 30, 34].

### 3.4 Defence

**The goalie** [BHS 18, 14]:
- start in the middle of the goal, **back turned outward**, so rebounds go to the boards, not to the opponent's centre;
- when you attack, leave the goalie in front of the goal, not at a right angle at a post.
- **[User]** Against a left-wing attack, the active goalie turns its back to the puck and moves in from the near post to
  cover straight shots and the middle (`docs/defence-left-wing.md`).

**The systems** [BHS 18, 28; TikTok defence video]:
- **Box (passive):** goalie in the middle, defenders close to the posts.
  - Good for beginners and when leading.
  - "Free passage for passes to the centre", so it loses to good centre tricks.
- **Flipper (active):** the goalie covers the post nearest the puck; the defenders move up to block the passing lanes.
  - Move calmly to the right spot. "Racing back and forth in the slot only makes it easier for the opponent."
- **Mix:** most elite players combine both.
  - Box against fast shovels.
  - Flipper against a player who is less accurate on the shovel but strong at centre tricks.
  - The TikTok's three defences against a left wing (passive / active / mix) are the same idea
    (`docs/defence-left-wing.md`).

**Defender jobs** [BHS 28]:
- Block passes to the centre first, direct shots second.
- **Against a right-wing shovel:** put the LD in the pass lane, ready to drop a few cm when the RW tries to go round
  (and watch for the Maltsev).
- **Against a left-wing attack:** the RD sits low beside the post with the stick to the post, to cut the Gretzky pass.
  When the LW moves, the RD moves up to cover direct shots and follows the LW.
- Don't park a defender 4-7 cm out from the posts: it becomes a trampoline for missed passes into your own goal.
- **Counter shot:** a defender just below the passing lane can strike upward as the pass comes. It can fly into the
  other goal as a "bonus goal".

**[NM26]**
- LD → LW → lost to the opponent's RD is the most common three-step chain.
- The defender facing the left wing is the key defender in top play.

### 3.5 Transitions and counters

- **The counter:** a counterattack "with a 100% chance" is difficulty 1 [NTHF]. The course's advice is the opposite of
  hurrying: don't attack without a plan; build attacks from controlled possession [BHS 14, 36].
- **[NM26] Goals and leads:**
  - goals come late (37 in regulation; per minute of regulation 4, 6, 10, 10, 7);
  - the first scorer won only 2 of 7 games;
  - 3 of 7 games went to overtime.
  - "Keep a cool head when behind; one pass, one attack, one goal at a time" [BHS 36].

## 4. The NTHF catalogue at a glance

- **121 named combinations** [NTHF]:
  - 55 centre: 3 easy (0-3), 20 intermediate (4-6), 32 advanced (7-10);
  - 66 right wing: 5 easy, 40 intermediate, 21 advanced.
- The catalogue covers only the centre and the right wing. Left-wing play appears inside multi-figure moves.
- The full list with descriptions is in `data/combinations/nthf-catalogue.json`.
- **Naming** [NTHF]:
  - many moves are named after their inventor;
  - **fakie** = the mirrored version;
  - **invers** = the same move in reverse order;
  - a trailing **-o** = a harder variant.

| Family | Who scores | Examples (difficulty) | Count |
| --- | --- | --- | --- |
| Centre tricks (the centre's own puck) | C | Lillstøvel 3, Näcka 4, Spjass 5, Hjerpe 6, Søren 6, Senterkiosk 8, plus every feint | 20 |
| Right-wing shots | RW | Direkteskudd 3, Maltzev 3, Tomahawk 6 (off the boards), Brustadbu 7 (kiosk) | 18 |
| Shovels and innspill (RW → C) | C | Lindahl and Edwall shovels 4, Gangsøy 5, Mexikaner 5, Trulsen 4, Petterson 6 | 25 |
| Behind the goal | RW, LW or C | Fakie Velodrom 6, Langorv 6, Gretzky 7, Senter-Karusell 7, Invers Kryssar med Velodrom 7 | 10 |
| Via the left wing | LW or C | Agdur 6, Halv-Agdur 7, Invers Kryssar 7, Holms 8 | 9 |
| Agdur variants via a wing (reverse, fakie) | wing or C | Agduro 7, Fakie Agdur 6, Invers Agduro 8 | 7 |
| Defender one-timers | LD or RD | Senterkniv 7, Fakie kniv 6, Senter-Rokkade 6, Reiersen 7, Bacalao 8 | 17 |
| Off the boards, the goalie or another figure | C | Veggdyr 6, Senter-Ceuleman 6, Newton 7, Fakie Horvath 7 | 7 |
| Behind your own goal | RW, LW or C | Burkgurk 8, Jorda Rundt 9 | 4 |
| Goalie involved | G | Fakie Gutshot 7, Skalpell 9 | 3 |
| Right shovel straight in | RW | Marcus Andersson 7 | 1 |

- **Combination docs already in this repo:**
  - Spjass (`docs/spjass.md`);
  - Näcka (`docs/nacka.md`);
  - Invers Kryssar med Velodrom (`docs/invers-kryssar-velodrom.md`);
  - the shovel #17 (`docs/analysis-shovel-17.md`);
  - the left-wing defences (`docs/defence-left-wing.md`).

## 5. What top-level play looks like [NM26]

7 games, about 40 minutes of live play, both players at both ends. Details are in `docs/nm26-game-patterns.md`.

- **Tempo:**
  - about 20 puck movements of 100 mm or more per minute;
  - 13-20 changes of possession or battles per minute;
  - the median puck speed in flight is about 0.85 m/s;
  - 34-43% of flights touch the boards.
- **Territory:** the puck is in the neutral zone about 24% of the time and in the two ends the rest.
- **Most common sequences:**
  - LD → LW (build-up) → the LW holds in the corner → lost to the opponent's RD, or passed on (LW → RW behind the goal,
    LW → C);
  - RW → LW round the boards;
  - RW → C (shovel range) for Fjermestad.
- **Style axes:**
  - Nygård plays through his left wing (puck in his attacking end 42%, on his left side 47%, the LW 19% of all time);
  - Fjermestad uses both wings evenly and plays more short passes to the centre.
  - [BHS 20] describes the same kind of contrast between two Swedish champions: a fast, risky style against a slow,
    controlled one.
- **Scoring:** late goals, blown leads, frequent overtime (section 3.5).

## 6. Vocabulary

Swedish terms are from Bordshockeyskolan and Norwegian terms from the NTHF catalogue (Norwegian version). "—" means the
term is not used in those sources. I did not add words of my own.

| English (repo) | Swedish [BHS] | Norwegian [NTHF] | Meaning |
| --- | --- | --- | --- |
| figure | gubbe | — | a player figure |
| rod, lever | spak | — | the control rod |
| slot, track | spår | spor | the figure's slot in the ice |
| blade, stick | klubba | kølle | the stick |
| forehand / backhand | forehandsida / backhandsida | — | the stick's two sides |
| fixed foot / free foot | fasta foten / fria foten | — | the mounted foot and the other |
| fork | klyka | — | the pocket between the stick and the fixed foot |
| heel groove / toe groove | — | hælgrop / tågrop | where the puck rests for centre tricks (NTHF English: heel groove, toe groove) |
| goalie | målvakt | keeper | |
| defender | back (vänsterback, högerback) | back (venstreback, høyreback) | |
| wing | ytter (vänsterytter, högerytter) | ving (venstreving, høyreving) | |
| build-up | uppspel | — | passing out of defence |
| set-up pass | inspel | innspill | the last pass before the shot |
| centre trick | centerfint | — | a centre's sideways move plus a shot |
| shovel | skyffel | skyffel | RW → C first-time play ("høyreskyffel" = right shovel) |
| centrifuge | centrifug | — | LW → C first-time play |
| velodrome | velodrom | Velodrom | a rim pass behind the goal between the wings |
| castling | rockad | rokkade | a pass between the defenders and a shot |
| counterattack | — | kontring | |
| face-off circle | tekningscirkel | — | the circle in each end |
| boards / corner | sarg / sarghörn | vant | the boards |
| fakie / invers | — | fakie / invers | mirrored / reversed version of a move |

## 7. What this means for the project

- **Reconstructions and videos:**
  - pick moves from the families above;
  - the most common real moves are the LD → LW build-up, the centrifuge, the shovel and behind-the-goal passes;
  - the push-not-strike technique the course describes (velodrome: "push the puck with the figure") is the "Slide or
    bounce" rule.
- **Tracking:**
  - the 1-on-1 matchups (LW vs the opponent's RD, and so on) give the natural units of a possession battle;
  - each figure's reach area is the rule's "figure's area" [ITHF 8.3, User A10].
- **Kit colour is an end, not a player** (the figures stay with the table) [NM26].
- **Handedness is fixed** (all sticks left). Mirror moves (fakie) are not symmetric copies on the table: a left-side
  move uses different body parts than its right-side twin [NTHF, BHS 4, 19].

## 8. Open

1. **Left and right.** This repo's labels (left = +y for team W) match the course's descriptions:
   - the LW slot turns 90° behind the goal;
   - the RD slot cannot go behind its own goal.
   - The rod labelling on the user's own table is still unchecked (`docs/geometry.md`).
2. **Board-sticker bounces and the "groove" names** are from the course and the catalogue, not checked on the user's
   table.
3. **Club rules.** Which unwritten rules the user's club follows (passive-play calls, who drops after a goal) is still
   open (`docs/game-mechanics.md` A5, A7).
4. **The NM26 measurements** are from automatic tracks and not user-confirmed.
5. **"Forward" and "back" in the NTHF catalogue.**
   - Its definition (Norwegian and English): "forward" and "back" are the ends of the board nearest and furthest from the
     player.
   - Its own example: the centre is near the opponent's goalie when it stands forward in the slot. That needs forward =
     toward the opponent's goal.
   - This page follows the example. Which is meant?
