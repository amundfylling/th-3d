# Project state

## Current position

- Last completed iteration: **01 - Establish the project and its working rules** (2026-09-30).
- Next iteration: **02 - Recover the original reference assets**.
- Code, 3D assets, animations: none. No animated shots exist or are planned before iteration 23.

## Verification status

| Item | Status |
| --- | --- |
| PDF text and hyperlinks | Extracted with PyMuPDF (all 8 pages, 11 link annotations, 5 unique URLs). |
| PDF embedded images | Inventoried from image-object dictionaries (10 images + 1 alpha mask); not yet extracted to files. |
| Visual inspection | All 8 pages viewed as ~110 dpi renders; manual p. 18 parts table read at native resolution. Gallery images not inspected at native resolution. |
| Web sources | Not fetched. |
| Builds / renders / tests | None exist; none run. |
| Dimensional accuracy | Nothing measured. All sizes are `catalog_nominal` or `unknown`. |

## Key decisions

- Target family 71-1145-XX; Sweden/Finland 71-1145-01 public gallery is the reference variant until
  the user supplies their own parts/teams/artwork.
- Conflicting overall lengths (960 vs 940 mm) are kept separate, not averaged. The approx. 845 x 457 mm
  playing area is not stretched to a housing size.
- Bare-sheet photo (older artwork) is used later for slot topology only, never for scale or artwork.
- Figures are rigid; motion data stays separate from camera and presentation (see CLAUDE.md).
- Planned structure: `references/`, `data/`, `src/model/`, `assets/`, `validation/`, `docs/`.

## Missing inputs (most important first)

1. Empty installed rink, perpendicular overhead, with scale markers in both directions
   (inner board boundary, track centrelines, slot ends).
2. Loose and installed figures with scale: fixture pivot, blade offset/profile, stick handedness,
   skate contacts, ice clearance, figure-height datum.
3. Travel stops and rod push/pull + twist recordings per control type (goalie, wing with link 7A,
   defence, centre).
4. Puck thickness, diameter, rim profile, mass; goal size, posts, clearance.
5. The user's actual teams/artwork and the goal configuration used (retail insert or ITHF setup).
6. Full manual A06 (only pages 2 and 18 are in the PDF) and the 1001 x 603 older-artwork overhead
   the guide mentions but does not contain.

## Review artifacts

- `docs/reference.md` - reference brief (main artifact of iteration 01).
- `CLAUDE.md` - project instructions.

## Iteration history

| Iteration | Date | Result | Checks run |
| --- | --- | --- | --- |
| 01 | 2026-09-30 | CLAUDE.md, docs/reference.md, docs/state.md | PDF text/link/image-object extraction; page renders viewed; PDF SHA-256 recorded, file unchanged |
