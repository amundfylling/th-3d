# Video theme: Norges Bordhockeyforbund (puck.no)

Status: PROPOSED (2026-10-11), waiting for the user's review of `validation/theme/nbhf-theme-sheet.png`.

The overlays of every analysis video (shared renderer `remotion/AnalysisVideo.tsx`: the move/encyclopedia videos,
IKV, Näcka, spjass, Shovel, defence) take their look from `remotion/theme.ts`. The default theme is `nbhf`; the
original dark broadcast look is kept as `classic` (`createAnalysisVideo({ ..., theme: "classic" })`).
Only presentation changes: the trace, the camera track, the rink, the figures and the contact gates are untouched.

## Source of the look

Taken from the site's own source, github.com/amundfylling/puck.no at commit 7ac88cab (2026-10-05), not from screenshots:

| token | value | source |
|---|---|---|
| brand red | `#c8102e` | `src/styles/global.css` `@theme --color-brand` |
| navy | `#0e2a57` (dark `#0a1f42`) | `--color-navy`, `--color-navy-dark` |
| ice | `#f4f7fb` | `--color-ice` |
| display font | Bricolage Grotesque (variable, 200-800, width 75-100 %) | `--font-display`, `@fontsource-variable/bricolage-grotesque` 5.3.0 |
| body font | Geist (variable) | `--font-body`, `@fontsource-variable/geist` 5.3.0 |
| logo | NBHF shield, `public/media/images/nbhf-logo.png` (1080 x 1080, transparent) | copied to `public/brand/nbhf-logo.png` |

Fonts are the Latin subsets of the Fontsource packages (`public/fonts/*-latin.woff2`, SIL OFL, licences beside them);
Latin covers æ ø å.

## How the site's design rules map to the video

The puck.no design rules (AGENTS.md "Design rules"): one accent colour (brand red), navy type on light surfaces, thin
dividers, status as a small dot plus text, no gradient overlays on pictures.

- Captions, tags, chapter panels, badge and end card: white panels, navy display type, slate body text, 6 px corners.
- The single accent: brand red for the primary graphics (arrows, rules, chapter number, key step). Other graphic
  roles keep their meaning: secondary = blue `#1f5fbf`, open lane = green `#16a34a`, blocked lane = rose `#d1495b`.
- Title card: a solid ice panel on the left with the shield, kicker in brand red, title in navy, a red edge line; no
  gradient over the picture.
- Bug (top left): small shield + kicker on white, video name on navy. Goal banner: navy with a red bar.
- Background around the rink: navy gradient instead of grey.

## Re-rendering

Changing the composition files changes the composition fingerprint, so the committed videos' export-report tests
(`npm test`: analysis, defence, ikv, nacka, spjass) fail with "composition changed since the export: re-render"
until each video is rendered again (`npm run video:analysis-*`, `node scripts/analysis-render.ts move:<id>`).
