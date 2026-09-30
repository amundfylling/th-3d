# Tooling and environment

Inspected 2026-09-30 in the Claude Code cloud container (iteration 03).

| Tool | Finding |
| --- | --- |
| OS / CPU | Linux x86_64, 4 cores, ~15 GB RAM, no display (`DISPLAY` unset) |
| GPU | None detected (`nvidia-smi` absent) |
| Node.js | v22.22.2 at `/opt/node22/bin/node`; runs `.ts` natively (type stripping, no flag, no warning) |
| npm | 10.9.7 - chosen package manager |
| Other package managers | pnpm 10.33.0, yarn 1.22.22, bun 1.3.11 present; not used |
| TypeScript | 7.0.2 (project devDependency, exact pin); `@types/node` 22.20.4 |
| jpeg-js | 0.4.4 (devDependency, BSD-3-Clause). Pure-JS JPEG decoder for reading reference photos in TypeScript (iteration 05). Decodes the 5636 px overhead in about 11 s; pixel values match Pillow within ±1 |
| Python | 3.11.15. PyMuPDF 1.28.2, Pillow 12.3.0, NumPy 2.4.6 were pip-installed in iterations 01-02 for PDF/image work; they are not project dependencies and are not preinstalled |
| Blender | **Not installed** (`blender` not on PATH) |
| Headless browser | Chromium 141.0.7390.37 at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`; global Playwright 1.56.1. Verified: `chrome --headless=new --no-sandbox --disable-gpu --screenshot` renders the smoke SVG |
| Network | npm registry reachable. STIGA, OTTO and ITHF hosts blocked by environment policy (see `docs/state.md`) |

## Decisions

- One root `package.json`, npm, committed `package-lock.json`.
- No script runner (tsx/ts-node): Node 22.18+ executes erasable TypeScript directly. `tsc` only typechecks (`noEmit`).
- Not installed yet by design: Remotion, React/Three, bundlers, test frameworks, databases.
- Committed review artifacts: small SVGs in `validation/`. Ignored: `node_modules/`, caches, `validation/renders/`, `out/`.

## Rendering an SVG to PNG for review

```sh
/opt/pw-browsers/chromium-1194/chrome-linux/chrome --headless=new --no-sandbox --disable-gpu \
  --window-size=480,480 --screenshot=/path/to/out.png "file://$PWD/validation/03-smoke.svg"
```

The container is ephemeral: pip-installed Python packages and `node_modules/` must be reinstalled
in a fresh session (`npm ci`; `pip install pymupdf pillow numpy` if PDF/image work is needed).
