// Move pictures (docs/move-pictures.md): renders the overhead stills for the puck.no picture recreations with the
// pose-preview composition. Reads out/move-pictures/jobs.json ([{ id, poses, puckMm, camera, widthPx, heightPx }],
// written by scripts/move-pictures/build.py) and writes out/move-pictures/<id>-base.png.
import { bundle } from "@remotion/bundler";
import { openBrowser, renderStill, selectComposition } from "@remotion/renderer";
import { readFileSync } from "node:fs";
import path from "node:path";

const BROWSER = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
const jobs = JSON.parse(readFileSync("out/move-pictures/jobs.json", "utf8")) as Array<Record<string, unknown> & { id: string }>;
const only = process.argv.slice(2);
const serveUrl = await bundle({ entryPoint: path.resolve("remotion/index.ts") });
const browser = await openBrowser("chrome", { browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" } });
const base = { serveUrl, browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" as const }, puppeteerInstance: browser };
for (const job of jobs) {
  if (only.length && !only.includes(job.id)) continue;
  const { id, ...inputProps } = job;
  const comp = await selectComposition({ ...base, id: "pose-preview", inputProps });
  const output = `out/move-pictures/${id}-base.png`;
  await renderStill({ ...base, composition: comp, frame: 0, output, inputProps,
    onBrowserLog: (l) => { if (/rror/.test(l.text)) console.log(l.text.slice(0, 300)); } });
  console.log("wrote", output);
}
await browser.close({ silent: true });
