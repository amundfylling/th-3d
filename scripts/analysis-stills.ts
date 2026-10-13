// Kept for older notes: selected frames of an analysis composition as PNGs (scripts/video.ts stills does more).
//   node scripts/analysis-stills.ts <scale> <frame> [<frame> ...]                ->  out/analysis/fNNNN.png (analysis-shovel-17)
//   COMP=analysis-spjass node scripts/analysis-stills.ts <scale> <frame> ...     ->  out/analysis-spjass/fNNNN.png
import { spawnSync } from "node:child_process";

const [scale = "0.5", ...frames] = process.argv.slice(2);
const comp = process.env.COMP ?? "analysis-shovel-17";
const out = comp === "analysis-shovel-17" ? "out/analysis" : `out/${comp}`;
const r = spawnSync(process.execPath, ["scripts/video.ts", "stills", comp, "--scale", scale, "--frames", frames.join(","), "--out", out], { stdio: "inherit" });
process.exit(r.status ?? 1);
