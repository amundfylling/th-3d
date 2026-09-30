# Player figures: rigid STIGA molds (2026-09-30, before iteration 21)

User request: replace the goalkeeper and skater proxies with accurate rigid STIGA figures (mounting axis,
stick, blade, skates, uniform) from the photos and videos in `references/players_images` (main branch).
User statement (source `user_statement_2026_09_30_players`): *every player is identical, except the
goalkeeper; Sweden and Finland differ only by kit colour and the country name on the back.*

AI review only; no personal user approval is recorded.

## Evidence

| Input | Use |
| --- | --- |
| 9 HEIC photos (IMG_2564-2572), Sweden goalie no. 30 | front, back, top, side, underside (mount socket), lying views |
| IMG_2573.mp4 (17 s), goalie | 0-11 s turntable (phone still, figure turned by a finger), then close-ups |
| IMG_2574.mp4 (24 s), Sweden skater no. 21 | 0-11 s turntable, then hand-held close-ups incl. the socket |
| Official overhead (`stiga_se_fi_overhead`) | top views of all 12 figures at the (assumed) preview scale: absolute scale, poses, stick layout |
| Finland team pack (`stiga_ca_team_pack_finland`) | five identical Finland skaters + goalie side by side at one depth: goalie and skater equally tall |

Originals are unchanged and hashed in `references/index.json` (`user_*` entries). Decoded, cropped stills:
`references/derived/players/*.jpg` + `manifest.json` (crop boxes in full-frame px, EXIF, tone mapping;
`npm run players:frames`). Video frames are HLG BT.2020 10-bit, tone-mapped to BT.709 with a fixed filter.

**No photo contains a scale object near the figure** (the tape measure lies far behind it). The photos give
shape and proportions; absolute size comes only from the official overhead, itself at the ASSUMED preview scale.

## Observations (traced)

- **Mount (fixture axis).** Skater: a flared cylindrical socket with a rectangular key bore under the **left**
  skate (the stick side) - the figure stands on it and turns about its axis. Goalie: the same kind of socket
  under the goalie's **right** skate; the left leg ends in a pad block.
- **Skater pose (one mold for all ten skaters).** Upright skating crouch (torso ~30 deg forward), left leg
  planted on the socket, right leg pushed back and out with its skate runner on the ice. Right (upper) hand
  at chest height, left (lower) hand at the hip: **left shot**. All ten skaters in the official overhead
  show the same top-view pose; the team pack shows five identical Finland skaters.
- **Skater stick.** Metal wire through both gloves, bent at the heel into a flattened blade standing on its
  edge on the ice toward the figure's left. Overhead (on the ice, no relief error): heel ~21.9 mm left of the
  axis, blade ~20.2 mm long (E-RD, W-RD, E-C, E-LD; E-LW excluded, blade partly hidden by the goal cage).
- **Goalie.** Blue mask with cage and skin patches behind the straps; yellow/white jersey shoulders and
  chest; blue arm pads; ribbed blue leg pads in front of yellow/white socks; blocker (right hand) with a
  border of small holes and a blue handle peg; catcher (left) at the hip; wide tan stick: paddle from the
  blocker down to a heel between the pads, blade across the front to the goalie's left, longer than the body
  is wide.
- **Uniform.** Kit colour on jersey and socks (Sweden yellow, Finland white); helmet, gloves, pants, boots,
  goalie pads/mask in one blue for both teams (overhead medians of all Finland vs all Sweden blue pixels:
  (19, 89, 142) vs (18, 87, 139)); skin face. Back print: country name arched over the number.
- **Numbers** (`data/figure-molds.json` `prints`): official overhead reference variant W-LD 5, W-RD 4, W-C 64,
  W-LW 26, W-RW unread, W-G 31 (low confidence), E-LD 5, E-RD 2, E-C 21, E-LW 92, E-RW 13 (low confidence),
  E-G 30. The user's skater is no. 21 and goalie no. 30 - the same as the reference E-C and E-G.
