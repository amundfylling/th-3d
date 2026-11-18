// Builds the static interactive viewer into viewer/dist (docs/viewer.md): moves exported by scripts/viewer-export.ts,
// the page bundled by esbuild (three.js included), the optimised scene GLB copied. No server logic: host dist/ anywhere.
//   node scripts/viewer-build.ts [step_ms=2]
import { execFileSync } from "node:child_process";
import { cpSync, mkdirSync, rmSync, statSync } from "node:fs";
import { build } from "esbuild";

const step = process.argv[2] ?? "2";
const moves = ["hjerpefinte", "nacka", "spjass", "invers-kryssar-velodrom"];
rmSync("viewer/dist", { recursive: true, force: true });
mkdirSync("viewer/dist/moves", { recursive: true });
for (const m of moves) execFileSync("node", ["scripts/viewer-export.ts", m, `viewer/dist/moves/${m}.json`, step], { stdio: "inherit" });
await build({ entryPoints: ["viewer/src/main.ts"], bundle: true, minify: true, format: "esm", target: "es2020", outfile: "viewer/dist/viewer.js", legalComments: "none" });
cpSync("viewer/index.html", "viewer/dist/index.html");
cpSync("viewer/public/scene.glb", "viewer/dist/scene.glb");
console.log("viewer.js", (statSync("viewer/dist/viewer.js").size / 1024).toFixed(0), "KB");
