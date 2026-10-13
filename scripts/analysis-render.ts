// Kept for the existing npm scripts: renders the full analysis video and its export report with the shared command
// (scripts/video.ts final, direct WebGL renderer, the same checks as before).
//
//   node scripts/analysis-render.ts [shovel-17|spjass|ikv|nacka|defence-lw|move:<id>] [video.ts options]
import { spawnSync } from "node:child_process";

const [name = "shovel-17", ...rest] = process.argv.slice(2);
const r = spawnSync(process.execPath, ["scripts/video.ts", "final", name, ...rest], { stdio: "inherit" });
process.exit(r.status ?? 1);
