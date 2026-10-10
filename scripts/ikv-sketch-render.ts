// Renders the two overhead stills of the Invers Kryssar med Velodrom sketch (start and catch) with the pose-preview
// composition: out/ikv/sketch-start.png, out/ikv/sketch-end.png and the camera mapping out/ikv/camera.json.
import { bundle } from "@remotion/bundler";
import { openBrowser, renderStill, selectComposition } from "@remotion/renderer";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const BROWSER = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
const g = JSON.parse(readFileSync("shots/invers-kryssar-velodrom/sketch-geometry.json", "utf8"));
const camera = { cx: 150, cy: 0, widthMm: 640 };
mkdirSync("out/ikv", { recursive: true });
const pose = (k: string) => ({ arc_mm: g.poses[k].arc_mm, theta_deg: g.poses[k].theta_deg });
const views = {
  start: { poses: { "W-RW": pose("rw_start"), "W-LW": pose("lw_receive"), "W-C": pose("wc_static") }, puckMm: g.puck.start },
  end: { poses: { "W-RW": pose("rw_receive"), "W-LW": pose("lw_receive"), "W-C": pose("wc_static") }, puckMm: g.puck.rw_contact },
};
const serveUrl = await bundle({ entryPoint: path.resolve("remotion/index.ts") });
const browser = await openBrowser("chrome", { browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" } });
const base = { serveUrl, browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" as const }, puppeteerInstance: browser };
for (const [name, v] of Object.entries(views)) {
  const inputProps = { ...v, camera };
  const comp = await selectComposition({ ...base, id: "pose-preview", inputProps });
  await renderStill({ ...base, composition: comp, frame: 0, output: `out/ikv/sketch-${name}.png`, inputProps,
    onBrowserLog: (l) => { if (/rror/.test(l.text)) console.log(l.text.slice(0, 300)); } });
  console.log("wrote", `out/ikv/sketch-${name}.png`);
}
await browser.close({ silent: true });
writeFileSync("out/ikv/camera.json", JSON.stringify({ cx: camera.cx, cy: camera.cy, width_mm: camera.widthMm, width_px: 1600, height_px: 1300 }) + "\n");
