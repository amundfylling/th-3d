// Renders selected frames of the analysis composition (review / tuning).
//   node scripts/analysis-stills.ts <scale> <frame> [<frame> ...]   ->  out/analysis/fNNN.png
import { bundle } from "@remotion/bundler";
import { openBrowser, renderStill, selectComposition } from "@remotion/renderer";
import { mkdirSync } from "node:fs";
import path from "node:path";

const BROWSER = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
const [scaleArg, ...frameArgs] = process.argv.slice(2);
const scale = Number(scaleArg ?? 0.5);
mkdirSync("out/analysis", { recursive: true });
const serveUrl = await bundle({ entryPoint: path.resolve("remotion/index.ts") });
const browser = await openBrowser("chrome", { browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" } });
const base = { serveUrl, browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" as const }, puppeteerInstance: browser };
const comp = await selectComposition({ ...base, id: "analysis-shovel-17", inputProps: { graphics: true } });
console.log("composition", comp.durationInFrames, "frames");
for (const f of frameArgs.map(Number)) {
  const out = `out/analysis/f${String(f).padStart(3, "0")}.png`;
  await renderStill({ ...base, composition: comp, frame: f, output: out, inputProps: { graphics: true }, scale,
    onBrowserLog: (l) => { if (/Error|error|FAIL/.test(l.text)) console.log(l.text.slice(0, 300)); } });
  console.log("wrote", out);
}
await browser.close({ silent: true });
