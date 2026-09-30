# Reference brief

Created in iteration 01, updated in iteration 02 (2026-09-30). Everything here comes from the one
PDF in the repository. None of the linked web sources could be fetched (network policy blocks
every linked host); see `references/index.json` -> `not_obtained`.

## Document identity

| Item | Value |
| --- | --- |
| Path | `Stiga_Play_Off_21_References.pdf` (repository root; the only PDF in the repo) |
| SHA-256 | `1c7355ef63d28a4c34adbb1983b29ed3ca4d8bae0e3d85ca8714117335d9a4cc` |
| Size / format | 4,691,349 bytes, PDF 1.4, 8 landscape pages (841.9 x 595.3 pt), no metadata |
| Identity | The **eight-page research guide** "STIGA PLAY OFF 21 / REFERENCE GUIDE", "Researched 30 September 2026". It is **not** a manufacturer manual. It embeds two manufacturer manual pages (manual pages 2 and 18) as images. |
| Status | Preserved unchanged. |

## Page map

Page numbers are guide pages (1-8). "Manual p. N" means a page of the STIGA manual A06 that the guide shows as an image.

| Page | Content | Embedded images (object pixel size) | Hyperlinks |
| --- | --- | --- | --- |
| 1 | Published nominal-size table and sourcing caveats | none | STIGA Sports gallery; STIGA Canada catalog |
| 2 | Official overhead, Sweden/Finland variant **71-1145-01**, current gallery artwork | 5636 x 5636 | `...71-1145-01_top-original.jpg` |
| 3 | Oblique A and Oblique B (opposite oblique views) | 5154 x 5154; 5192 x 5192 | STIGA Sports gallery |
| 4 | Side A and Side B (both long-side profiles) | 5210 x 5210; 5208 x 5208 | STIGA Sports gallery |
| 5 | Bare ice sheet with exposed slots, older sponsor artwork, STIGA Canada catalog | 2554 x 1617 | STIGA Canada catalog |
| 6 | Puck photo; Finland team pack in blister packaging | 1000 x 863; 800 x 600 (plus 800 x 600 grey alpha mask) | STIGA Canada catalog |
| 7 | Manual A06 p. 18: exploded view and parts list | 1273 x 1800 | OTTO-hosted manual PDF |
| 8 | Manual A06 p. 2: assembly steps; ITHF goal configuration; capture priorities | 1132 x 1600 | OTTO-hosted manual PDF; ITHF Tournament Rules |

Iteration 02 extracted all ten images to `references/originals/` and verified their decoded
pixel sizes against the captions (all match). See "Recovered reference assets" below.

### Hyperlinks extracted from the PDF

| Source | URL | Pages |
| --- | --- | --- |
| STIGA Sports product gallery (Sweden vs Finland) | https://www.stigasports.com/sv/product/play-off-21-sweden-vs-finland | 1, 3, 4 |
| STIGA Canada detailed catalog (Canada vs Sweden) | https://www.stigacanada.ca/stiga-playoff-21-hockey-table-game-can-swe/ | 1, 5, 6 |
| Official overhead original | https://stigasports.centracdn.net/client/dynamic/images/4501_fd13c1ad70-71-1145-01_top-original.jpg | 2 |
| STIGA manual A06 (OTTO-hosted) | https://d.otto.de/files/e1d0d65f-539e-4c0d-bcbf-fb4163cc1813.pdf | 7, 8 |
| ITHF Tournament Rules | https://www.ithf.info/stiga/ithf/docs/TournamentRules.pdf | 8 |

## Recovered reference assets (iteration 02)

Catalogue: `references/index.json` (stable IDs, SHA-256, native size, view, variant/artwork, limitations).

| ID | Local file | Native px | Provenance |
| --- | --- | --- | --- |
| `stiga_se_fi_overhead` | `references/originals/stiga-sports-71-1145-01-overhead.jpg` | 5636 x 5636 | pdf_embedded, guide p. 2 |
| `stiga_se_fi_oblique_a` | `references/originals/stiga-sports-71-1145-01-oblique-a.jpg` | 5154 x 5154 | pdf_embedded, guide p. 3 |
| `stiga_se_fi_oblique_b` | `references/originals/stiga-sports-71-1145-01-oblique-b.jpg` | 5192 x 5192 | pdf_embedded, guide p. 3 |
| `stiga_se_fi_side_a` | `references/originals/stiga-sports-71-1145-01-side-a.jpg` | 5210 x 5210 | pdf_embedded, guide p. 4 |
| `stiga_se_fi_side_b` | `references/originals/stiga-sports-71-1145-01-side-b.jpg` | 5208 x 5208 | pdf_embedded, guide p. 4 |
| `stiga_ca_bare_ice_sheet` | `references/originals/stiga-canada-bare-ice-sheet.jpg` | 2554 x 1617 | pdf_embedded, guide p. 5 - **older artwork** |
| `stiga_ca_puck` | `references/originals/stiga-canada-puck.jpg` | 1000 x 863 | pdf_embedded, guide p. 6 |
| `stiga_ca_team_pack_finland` | `references/originals/stiga-canada-finland-team-pack.png` | 800 x 600 RGBA | pdf_embedded, guide p. 6 |
| `stiga_manual_a06_p02` | `references/originals/stiga-manual-a06-p02-assembly.png` | 1132 x 1600 | pdf_embedded, guide p. 8 |
| `stiga_manual_a06_p18` | `references/originals/stiga-manual-a06-p18-specification.png` | 1273 x 1800 | pdf_embedded, guide p. 7 |

- The seven JPEGs are the PDF's own DCT streams with only the ASCII85 wrapper removed; their bytes were
  checked identical to the decoded embedded streams. Nothing was resampled or recompressed.
- The three PNGs hold the PDF's lossless (Flate) pixels; the team pack's alpha comes from its SMask.
- Byte identity with the remote originals is **unverified** (no download succeeded).
- The five gallery views are square frames with large white margins; the rink occupies roughly
  24-52% of each frame (`content_bbox_px` in the index).
- Camera sides: Oblique A and Side B look from the same long side (far boards: seko ... Gevalia,
  Texstar); Oblique B and Side A look from the other (far boards: Divello, Sievi, Fumex, Coca-Cola).
  Both long sides of the housing carry the "PLAY OFF 21 / STIGA" print.
- The side views are slightly elevated, not orthographic: the ice surface is visible.
- At native resolution jersey numbers, "SVERIGE"/"FINLAND" lettering and stick shafts are legible.
- Installed rink (current gallery) and bare sheet (older Canada catalog) carry different artwork and
  are kept as separate sources.

### Not obtained (network blocked)

| Item | URL / host | Why it matters |
| --- | --- | --- |
| Remote overhead original | `stigasports.centracdn.net` (URL above) | Byte-identity check only; the embedded 5636 px JPEG suffices for tracing |
| Direct URLs of obliques/sides | `www.stigasports.com` product page | Source association is page-level only |
| Canada catalog images and the 1001 x 603 older-artwork overhead | `www.stigacanada.ca` | Overhead is not embedded in the PDF at all |
| Complete manual A06 (20 pages per guide) | `d.otto.de` | Only pages 2 and 18 available; p. 17 figure variants missing |
| ITHF Tournament Rules | `www.ithf.info` | Section 3.3 known only from the guide's summary |

## Manufacturer manual page numbers

- Manual A06 **page 2**: supplied parts and assembly (seven steps). Verified by the page badge "2"
  printed on the embedded image.
- Manual A06 **page 18**: specification, exploded view and parts list. Verified by the page badge "18".
- Page 17 (figure variants) and the 20-page total are the guide's claims only; not verified because
  the complete manual could not be downloaded.

## Model and variant

- Target: **STIGA Play Off 21, family 71-1145-XX** (manual p. 2 header reads "PLAY OFF 21  71-1145-XX").
- Public reference variant: **Sweden vs Finland, 71-1145-01** (guide p. 2). Sweden wears yellow/blue,
  Finland white/blue in the gallery photos. Housing branding: "PLAY OFF 21 - Peter Forsberg
  edition of the original hockey game".
- Second public variant: STIGA Canada "Canada vs Sweden" catalog page. Its variant number is not
  given in the PDF. Its bare sheet (p. 5) and the 1001 x 603 overhead mentioned on p. 6 show
  **older artwork** and must not be mixed with the current gallery artwork.
- The user's own game (teams, artwork, parts, goal setup) takes precedence once supplied. Not supplied yet.

## Published dimensions (guide p. 1)

All are `catalog_nominal`, in millimetres, uncertainty `null` (not stated). None is `measured`.

| Feature | Value | Source (as cited on p. 1) | Qualification |
| --- | --- | --- | --- |
| Overall length x width | 960 x 500 | STIGA Sports | Whether rod ends/handles are included is unspecified |
| Overall length x width x height | approx. 940 x 502 x 83 | STIGA Canada | Conflicts with 960 mm length; height datum unspecified |
| Ice / actual playing area | approx. 845 x 457 | STIGA Canada | Must be checked against the inner board boundary |
| Figure height | approx. 57 | STIGA Canada | Height datum unspecified (ice? base? helmet top?) |
| Puck diameter | approx. 25.4 | STIGA Canada | Thickness not supplied; 25.4 mm is likely an inch conversion |
| End plexiglass height x length | approx. 70 x 622 | STIGA Canada | Whether 622 mm is the developed curved length or a chord is unknown |
| Absolute ice-sheet thickness | unknown | - | Only a "25% increase" is advertised |

The guide found no public manufacturer CAD or dimensioned engineering drawing.

## Parts identified (manual A06 p. 18, shown on guide p. 7)

Read from the embedded page image at native resolution. Qty columns: Play Off / Stanley Cup.

| Fig. | Article | Description | Qty PO / SC | Note |
| --- | --- | --- | --- | --- |
| 1 | 7111-0393-01 | Ice sheet - Play Off | 1 / - | |
| 1 | 7111-0393-03 | Ice sheet - Stanley Cup | - / 1 | Same manual covers both games |
| 2 | 7111-0348-01 | Plexi glass | 2 / 2 | End screens |
| 3 | 7111-0526-01 | Goal | 1 / 1 | Kit of 2 |
| 4 | 7111-9072-02 | Goal counter strip | 1 / 1 | Kit of 2 |
| 5 | 7111-9016-00 | Handle, red | 2 / 2 | Kit of 6 |
| 6 | 7111-9083-02 | Control rod goalie | 2 / 2 | |
| 7 | 7111-9083-06 | Control rod left wing | 2 / 2 | |
| 7A | 7111-9073-01 | *Link | 2 / 2 | Kit of 2; drawn on the left-wing rod |
| 8 | 7111-9083-07 | Control rod left def. | 2 / 2 | |
| 9 | 7111-9083-01 | Control rod centre | 2 / 2 | |
| 10 | 7111-9083-03 | Control rod right def. | 2 / 2 | |
| 11 | 7111-9083-04 | Control rod right wing | 2 / 2 | |
| 12 | 7111-9079-01 | Puck | 1 / 1 | Kit of 3 |
| 13 | 7111-9074-01 / 7111-0574-01 / 7111-9074-11 | Foot (housing leg) White/Black, Black/Red, Black/Black | Black/Red: 1 / -; Black/Black: - / 1 | Kit of 4; these are table legs, not skates |
| 14 | 7111-0332-01 | Puck ejector | 2 / 2 | |
| 15 | 7111-0333-01 | Puck ejector arm | 2 / 2 | |
| 16 | 7111-0526-11 | Deflector | 1 / 1 | Kit of 2; the white goal insert |
| 17 | (no article) | Figures (goalie and skater drawn) | - | Manual p. 17 shows figure variants; not in this PDF |

Six control rods per team (goalie, LW, LD, C, RD, RW), i.e. one goalie and five skaters per side.
Footer of manual: 8200-0514-05 A06 / 2024-02-29 (as transcribed on guide p. 7).

The exploded view is not a scale drawing. It resolves identities only: no path coordinates,
pivot offsets, gear ratios, backlash, contact surfaces or travel stops.

## Goal configuration (guide p. 8)

- Retail assembly (manual p. 2): white insert/deflector inside the goal.
- ITHF Tournament Rules, valid from 8 September 2025, section 3.3 (as summarised by the guide):
  remove the supplied white goal-net inserts and goal cups; keep the plexiglass screens.
  The rules PDF itself was not read in this iteration.
- Decision pending: model the setup used in the user's demonstration.

## Conflicts and inconsistencies

1. **Overall length 960 mm (STIGA Sports) vs approx. 940 mm (STIGA Canada)**; width 500 vs 502 mm.
   Neither states whether rods/handles are included. Do not average; keep both as nominal.
2. **Playing area vs housing.** 845 x 457 mm is the ice/playing area, not the housing. The inner
   board boundary must be traced/measured; it is not derivable from the overall size.
3. **Bare sheet vs installed rink.** The p. 5 sheet may extend beneath the boards, so its outer edge
   is not the playable boundary; its artwork is older than the p. 2 overhead.
4. **Manual table, fig. 13**: English "Foot White/Black" vs French "Jambe Rouge/Noir" on the same row.
5. **Guide claims content that this PDF does not contain.** p. 6: "Also included: a 1001 x 603
   overhead photograph" - no such image object exists in the file. p. 7: "The complete 20-page
   manual is included in the pack" - only manual pages 2 and 18 are embedded; page 17 (figure
   variants) is absent.
6. The guide footer says "Source images preserved unchanged"; byte identity with the remote
   originals is not verifiable from the PDF (images are stored re-encoded as PDF image streams).

## Missing evidence

- Measured installed-rink boundary (inner board line) and ice-sheet thickness.
- Track (slot) centrelines and their travel stops for all 12 figures; the overhead hides parts of the tracks.
- Figure geometry: fixture pivot axis, blade offset and profile, stick handedness, skate contacts,
  ice clearance, and the height datum of the 57 mm figure height.
- Rod-to-figure transfer (push/pull to path position, twist to rotation), link 7A behaviour, gear
  ratios and backlash.
- Puck thickness, rim profile and mass; goal dimensions, posts and clearances.
- End-screen developed length vs chord, and screen mounting positions.
- Loose-figure photographs with scale; the team pack photo is distorted by packaging.
- Manual pages other than 2 and 18 (notably p. 17, figure variants).
- The user's actual teams, artwork and goal configuration.

## Visual content not fully inspected

- Iteration 02 viewed all ten extracted images as downscaled previews (max 1400 px) and spot-checked
  two native-resolution crops (overhead goal area, Side A figures). The full native frames have not
  been examined region by region; slot ends, stick sides and handedness remain unchecked.
- The puck and team-pack photos were viewed only at page-render size.
- Manual p. 2 (guide p. 8) was viewed at page-render size; manual p. 18 was examined at native
  resolution for the parts table.
- No linked web page, image or PDF was opened.
