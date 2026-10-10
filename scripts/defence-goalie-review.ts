// Overhead close-ups of goalie poses for the defence video (user review before the full render), with the
// pose-preview composition: out/defence-goalie/<name>.png and out/defence-goalie/camera.json.
//   node scripts/defence-goalie-review.ts <variants.json>
// variants.json: { puck: [x, y], lw/wc/rd: {arc_mm, theta_deg}, variants: { name: {arc_mm, theta_deg} } }
import { bundle } from "@remotion/bundler";
import { openBrowser, renderStill, selectComposition } from "@remotion/renderer";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const BROWSER = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
const v = JSON.parse(readFileSync(process.argv[2]!, "utf8"));
const camera = { cx: 225, cy: 95, widthMm: 340 };
mkdirSync("out/defence-goalie", { recursive: true });
const serveUrl = await bundle({ entryPoint: path.resolve("remotion/index.ts") });
const browser = await openBrowser("chrome", { browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" } });
const base = { serveUrl, browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" as const }, puppeteerInstance: browser };
for (const [name, g] of Object.entries(v.variants) as [string, { arc_mm: number; theta_deg: number }][]) {
  const inputProps = { poses: { "W-LW": { arc_mm: 60, theta_deg: 0 }, "W-C": { arc_mm: 200, theta_deg: 0 }, "E-RD": v.rd, "E-G": { arc_mm: g.arc_mm, theta_deg: g.theta_deg } }, puckMm: v.puck, camera };
  const comp = await selectComposition({ ...base, id: "pose-preview", inputProps });
  await renderStill({ ...base, composition: comp, frame: 0, output: `out/defence-goalie/${name}.png`, inputProps });
  console.log("wrote", `out/defence-goalie/${name}.png`);
}
await browser.close({ silent: true });
writeFileSync("out/defence-goalie/camera.json", JSON.stringify({ ...camera, width_px: 1600, height_px: 1300 }) + "\n");
