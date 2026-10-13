// Renders the camera-angle study (composition angle-study): one still per angle at the last frame (whole move drawn),
// validation/move-pictures/angles/nacka-<angle>.png at 1920x1080; with --video the slow-motion clip instead (.mp4).
import { bundle } from "@remotion/bundler";
import { openBrowser, renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { mkdirSync } from "node:fs";
import path from "node:path";

const BROWSER = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
const stills = !process.argv.includes("--video");
const angles = process.argv.slice(2).filter((a) => !a.startsWith("--"));
const list = angles.length ? angles : ["overhead", "tilted", "oblique", "goalie"];
mkdirSync("validation/move-pictures/angles", { recursive: true });
mkdirSync("out/move-pictures", { recursive: true });
const serveUrl = await bundle({ entryPoint: path.resolve("remotion/index.ts") });
const browser = await openBrowser("chrome", { browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" } });
const base = { serveUrl, browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" as const }, puppeteerInstance: browser };
for (const angle of list) {
  const inputProps = { angle };
  const comp = await selectComposition({ ...base, id: "angle-study", inputProps });
  const onBrowserLog = (l: { text: string }) => { if (/rror|angle-check/.test(l.text)) console.log(l.text.slice(0, 200)); };
  if (stills) {
    const output = `validation/move-pictures/angles/nacka-${angle}.png`;
    await renderStill({ ...base, composition: comp, frame: comp.durationInFrames - 1, output, inputProps, onBrowserLog, scale: 1.5 });
    console.log("wrote", output);
  } else {
    const output = `validation/move-pictures/angles/nacka-${angle}.mp4`;
    const t0 = Date.now();
    await renderMedia({ ...base, composition: comp, codec: "h264", crf: 20, outputLocation: output, inputProps, concurrency: 2, onBrowserLog });
    console.log("wrote", output, `${Math.round((Date.now() - t0) / 1000)} s`);
  }
}
await browser.close({ silent: true });
