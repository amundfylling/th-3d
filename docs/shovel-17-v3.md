# Shovel #17 on the move engine with the STL skater (2026-10-19, PROPOSED)

User request (2026-10-19): "Can you create the 3D animation of the shovel with the new players and the latest logic?"
"The shovel" is Shovel #17 (iterations 21-25, `docs/shot22.md`), the only shovel in the repo. "New players" is the STL
skater (`docs/skater-stl.md`); "latest logic" is the move engine with solved meets and tunes (`docs/shot-encyclopedia.md`
section 4b), the contact-physics and slide-or-bounce rules, the video workflow (`docs/video-workflow.md`) and the
puck.no theme (`docs/theme.md`).

The accepted trace `trace.shovel-17.v2` stays as it is (recorded-shot reconstruction, `scripts/shot22-trace.py`). This is
a second, DESIGNED version beside it: `moves/shovel-17-v3/` (move and story), `data/traces/shovel-17-v3.trace.json`,
`shots/shovel-17-v3/checks.json`, `validation/moves/shovel-17-v3-{sheet.png,robustness.json}`, the video
`validation/moves/shovel-17-v3.mp4` (composition `move-shovel-17-v3`).

## Why a new version and not a re-render

The v2 trace needs things the latest rules no longer allow: one approved 2.65 mm overlap (the shot brushes W-C's right
skate) and a rigid 4.4 m/s carry after a 1.8 m/s pass that meets W-C's back side-on (a relative impact far above the
500 mm/s limit; the trace predates "Slide or bounce" and was never checked against it). On the engine every contact is
computed from the figure motion, so the move had to be redesigned so that it works physically.

## The move

| Phase | What happens | Values |
| --- | --- | --- |
| Set-up | W-RW back to the goal near the centre line (arc 20 mm), puck at rest behind the back of its blade; W-C back to the goal at the bottom of its slot (heading -197.6 deg, as observed) | E-G, E-RD, E-LD as in v2 |
| Pass | W-RW turns counter-clockwise (-120 -> -60 deg, from 0.2 s). The back of the blade pushes the puck across | 50 touches, peak 144 mm/s; leaves at about 600 mm/s, 77 deg |
| Reception | W-C steps up its slot so the back of its skates is where the pass arrives (meet `c_catch`, solved on the puck's real path) and turns counter-clockwise with the puck as it lands (-197.6 -> -155 deg in 80 ms): a soft reception | puck arrives at 310 mm/s |
| Shovel | W-C runs up the slot (to 1.4 m/s in 0.12 s) with the puck against the back of its skates and keeps turning (-155 -> -146 deg) | 69 touches, peak 249 mm/s; leaves at 1.4 m/s, 7 deg |
| Goal | far corner, past the goalie's right pad | goal line y = +18.8 mm (mouth window -28.7..29.8) |

A tune (`tunes`) sets the pass turn's duration (0.139 s nominal) so the pass reaches the centre at 316 mm/s on any ice.

## Checks

- No overlap anywhere (finite puck, all 12 figures, boards, posts, cage, every 0.25 ms, 0.1 mm, no exceptions).
- Slide check passed: figure contacts peak 249 mm/s (limit 500), no board or post contact.
- No unexplained motion change; contact sequence W-RW blade -> W-C skate -> goal net.
- Robust in **11 of 11** engine variants (geometry +-0.001 mm, footprints +-2%, puck start +0.2 mm, friction +-25%,
  restitution 0.3/0.7); goal line y 17.0-20.3 mm in all of them.

## Differences from the recording (also in the move file's `limitations`)

- No foot drag-back: the move starts where the v2 drag ended (puck behind the right wing).
- Slower: pass about 0.6 m/s (recording 1.8), shot 1.4 m/s (rule value 4.4). The recorded speeds cannot be received or
  carried as a push under the 500 mm/s figure-impact limit.
- The centre's turns during the reception and the push are designed (not observed).
- Reading not approved by the user yet (`approved_reading: null`); status proposed.

## Reproduce

```sh
python3 scripts/build-move.py shovel-17-v3 --robustness --video-spec
npm run video:stills -- move:shovel-17-v3
npm run video:final  -- move:shovel-17-v3 --cache
```
