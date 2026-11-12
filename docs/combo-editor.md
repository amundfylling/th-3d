# Combo editor: a public web page for drawing combinations on the 3D table

Status: PROPOSED (2026-11-12, user request: "a static website that has the 3D model where you can create the
combinations with the arrows ... export it in the suitable formats ... possible to use AI ... a public link ... will not
cost anything to host ... very smooth to move the players and rotate the players").

Public address: **https://table-hockey-combo.pages.dev** (Cloudflare Pages, free plan, in the user's Cloudflare account
beside `table-hockey-h2h`). Everything lives in `site/`; it is a static page with no server of ours.

## What it does

- The table is the repo's own scene (`assets/scene/full_static_appearance.glb`: rink, goals, the twelve figures with
  the STL skater, the puck), seen in three.js with the lights of the video scene and a soft shadow.
- **Players:** drag a figure's body and it slides along its own slot; drag its stick (or the yellow ring and knob round
  a selected figure, or the mouse wheel, or the arrow keys) and it turns about its peg. Figures stay rigid (rule 5):
  the state is `(arc_mm, theta_deg)` exactly as in the traces and the pose-preview composition. A figure can be hidden,
  as the puck.no pictures leave one out.
- **Puck:** drag it on the ice; it stays inside the boards and snaps to the front or back of a blade within 7 mm.
- **Arrows and numbers:** pass/shot arrows (solid green) and run arrows (dashed grey) through any number of points,
  straight or curved, with colour and width; numbered circles for the touches. An arrow that ends at a number is
  shortened so its head stays visible, as in the move pictures. Arrows are drawn in front of the figures like the
  move pictures (switch in the Table panel to lay them on the ice instead).
- **Library:** the 121 move pictures (`data/move-pictures/`) as starting points, with search and a filter by player.
- **Views:** Attack (the move pictures' tilted 20 deg view), Attack +, Full rink, Top, Side, Behind goal, and free
  orbit / zoom / pan. A tall phone screen starts on Full rink.
- **Play:** the puck follows the arrows in order while they are drawn (the players stand still).
- **Export:** PNG (this view at 2x, 1920x1080, 4K, 1574x1100 like the move pictures, square, portrait; background as
  shown, transparent or white), video of the play-back (1920x1080, MP4 where the browser can record it, otherwise
  WebM), the JSON file, and a share link that holds the whole combination in the address (`#c=...`, deflate +
  base64url; about 800 characters for a library move). `#move=<id>` opens a library move.
- **Open:** a JSON file (button, drop on the page) or pasted JSON. Undo/redo (200 steps); the work is kept in the
  browser's local storage.
- **AI:** two ways, both without a server of ours. (1) "Ask Claude here" calls the Claude API from the browser with the
  user's own API key (kept in that browser's local storage, sent only to api.anthropic.com; official SDK, loaded only
  when used; model choice Opus 5.5 / Sonnet 5.5 / Haiku 5.5). (2) "Use any AI": the page copies a prompt (format guide +
  table reference + current combination + the request) for any chat AI and reads the pasted answer back. Either way
  the answer goes through the same validation as an opened file, and Undo restores the previous table.

## The format `th-combo/1`

One JSON object in world millimetres (docs/geometry.md): `figures` (`arc_mm` or `at_mm`, `theta_deg`, `hidden`),
`puck`, `arrows` (`points_mm`, `style`, `curved`, `color`, `width_mm`, `head`), `markers` (`label`, `x_mm`, `y_mm`),
optional `camera`. The exact text shown to people and sent to AIs is `formatGuide()` in `site/src/model.ts` (also under
Help on the page); it lists every slot with positions along it and the blade offset. Reading is lenient where a repair
is safe (a missing figure keeps its pose, an arc outside the slot is held inside, `at_mm` goes to the nearest slot
point, a puck outside the boards is moved in) and reports each repair; it refuses a wrong schema or non-numbers.

The format is the same information as the pose-preview props plus the arrows and contact points of
`out/move-pictures/<id>-geometry.json`, so a combo can be turned into a move-picture job by a small script if wanted.

## Files

| path | what |
|---|---|
| `site/src/model.ts` | the combo document, validation, slot and board maths, arrow geometry, share links, format guide (pure, tested) |
| `site/src/stage.ts` | three.js scene: loading, posing, arrows, markers, handles, picking, cameras, export frames |
| `site/src/main.ts` | state, undo, pointer tools, inspector, dialogs, play-back, export |
| `site/src/ai.ts` | prompt, answer parsing, the Claude call |
| `site/scripts/build-assets.mjs` | writes `public/table.glb` (17.1 MB -> 1.4 MB: welded, simplified to about 40 % of the triangles with an error bound of 0.06 % of each mesh's size, quantised, meshopt, WebP textures) and `src/generated/rink.json` (slots, boards, goals from `data/geometry.json` and the hardware report). Both are generated, not committed. |
| `site/scripts/build-library.py` | writes the committed `public/library.json` from `data/move-pictures/` with the move-picture builder (`npm run site:library`; rerun after the specs or the builder change) |
| `site/scripts/deploy-cloudflare.mjs` | publishes `site/dist` (below) |
| `site/tests/model.test.ts` | Node tests |

Run: `npm run site:install` once, then `npm run site:dev` (http://127.0.0.1:5180), `npm run site:test`,
`npm run site:build`, `npm run site:deploy`. `window.comboEditor` (`getCombo`, `setCombo`, `screenOf`, `figurePoint`,
`formatGuide`) is a handle for scripts and browser tests.

## Hosting

Cloudflare Pages project `table-hockey-combo`, direct upload, no build on Cloudflare's side. `npm run site:deploy`
needs `CLOUDFLARE_API_TOKEN` (Pages: Edit). It sends the built files inside the deployment request, as data modules of
a small Pages worker that serves them with content types, ETags and cache rules (hashed assets for a year, the rest for
five minutes). Reason: `wrangler pages deploy` uploads files with a short-lived upload token in the Authorization
header, and the cloud sessions reach Cloudflare through a proxy that sets that header itself, so the upload is refused
there (code 8000013). From a machine with a normal token `npx wrangler pages deploy site/dist --project-name
table-hockey-combo` works too and serves the files as plain static assets. The free plan allows 100 000 worker requests
a day (a visit is about ten). A deployment is not automatic: rerun the deploy after a merge. `CF_PAGES_BRANCH=<name>`
gives a preview address instead of the public one.

## Checks run (2026-11-12)

- `npm run site:test`: 8/8. The editor's pivot, heading and blade point equal the repo's pose code
  (`src/model/pose.ts`) for all twelve figures; all 121 library moves read without a repair and survive a second read
  unchanged; repairs and refusals of hand-written JSON; the puck clamp; share-link round trip; AI answer parsing.
- Headless Chromium (software WebGL) on the built site, 1440x860 with a mouse and an iPhone 13 screen with touch: body
  drag (arc changes, turn kept), stick drag, ring drag with Shift (5 deg steps), wheel, arrow keys, undo, puck drag
  with blade snap (lands on the computed blade spot), arrow and number tools, arrow selection and editing, PNG (two
  sizes, transparent), JSON, share link opened in a fresh browser (equal combo), library search and load, play-back,
  video download (MP4), the any-AI prompt and answer path. No console errors. The page draws nothing while idle.
- The public deployment was opened in the same browser: loads, fonts and model served.
- NOT run: "Ask Claude here" against the real API (no key in the session); it type-checks against the SDK and its
  error paths are plain. Real phones, Safari and Firefox were not tried. Frame rate on a real GPU was not measured
  (the scene is about 0.5 million drawn triangles; the software renderer here needs about 170 ms a frame).

## Assumptions and limits

- A combo is an illustration like the move pictures, NOT a trace: the editor does not run the contact check or the
  slide check, and the puck can be dragged onto a figure. Nothing made here may be saved as a trace or played by the
  video pipeline without going through `scripts/verify-trace.py` and the slide check.
- The library inherits the move pictures' status (PROPOSED; poses read off puck.no or designed from the NTHF text).
  The start-position bubble of the four fakie centre tricks (`ghost`) is not carried over.
- Kit colours follow the table ends as in the scene: W (attacks toward +x, up in the Attack view) is white/blue, E is
  yellow. The page calls them White and Yellow.
- "Stick" for the turn-by-dragging rule is ASSUMED to be any hit more than 15 mm to the figure's left of the peg and
  below 26 mm; the goalies only turn by the ring, wheel, keys or slider.
- The puck snap spot is the move pictures' (`blade middle [2.8, 33.1] mm` +- puck radius + 1.6 mm), ASSUMED there.
- The web model is simplified and its end screens are plain transparency (no refraction pass); the committed GLB is
  untouched and stays the reference for renders.
- Video: only the puck and the arrows move. Recording uses the browser's MediaRecorder, so the codec depends on the
  browser, and the recording is real time.
- Credits on the page: the skater derives from MAVRIS's Thingiverse model (CC BY-SA, attribution and licence under
  Help); the page says it is a fan project and not affiliated with STIGA.
