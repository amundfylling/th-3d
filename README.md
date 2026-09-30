# th-3d

Geometry data and static diagnostics for photorealistic 3D shot videos of the STIGA Play Off 21
table hockey game. Project rules: `CLAUDE.md`. Current state: `docs/state.md`.

## Requirements

- Node.js 22.18 or newer (runs `.ts` files directly via built-in type stripping; no extra runner).
- npm (lockfile: `package-lock.json`).

## Commands

```sh
npm ci              # install exact locked dev dependencies (TypeScript, @types/node)
npm run typecheck   # tsc --noEmit over scripts/ and src/
npm run smoke       # data/fixtures/smoke.json -> validation/03-smoke.svg
npm run validate    # data/geometry.json against schema, evidence policy and references/index.json
npm test            # evidence-policy tests (node:test)
npm run check       # typecheck + validate + test
npm run trace:board # iteration 05: trace inner board boundary -> data/geometry.json, validation/05-board-report.json (~20 s)
npm run render:board # validation/05-board-overlay.svg from the canonical data
```

Geometry conventions and evidence policy: `docs/geometry.md`. Board trace: `docs/board-trace.md`.

TypeScript files must use erasable syntax only (no enums, namespaces or parameter properties) and
import local modules with their `.ts` extension, because Node strips types without compiling.

Environment findings: `docs/tools.md`.
