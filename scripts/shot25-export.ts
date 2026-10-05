// Iteration 25: export the first reusable video - the approved iteration-24 presentation of the accepted trace,
// rendered directly with Remotion/Three (the renderer in use; the Cycles benchmark was never run).
//
//   node scripts/shot25-export.ts            draft (480 x 270) then final (1920 x 1080), both 60 fps
//   node scripts/shot25-export.ts --draft    draft only (out/25/, not committed)
//   node scripts/shot25-export.ts --final    final only
//
// Every rendered frame's logged physical state is compared with the pure Node evaluation of the same trace.
// Report: validation/25-export-report.json. Final video: validation/25-shovel-17-final.mp4.
import { bundle } from "@remotion/bundler";
import { openBrowser, renderMedia, selectComposition } from "@remotion/renderer";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { resolveTimeline, sourceAtFrame, type PresentationSpec } from "../src/model/presentation.ts";
import { shotTimeEvaluator } from "../src/model/shot-pose.ts";
import type { ShotTrace } from "../src/model/trace.ts";

const BROWSER = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
const COMPOSITION = "shot25-shovel-17-final";
const FINAL = { path: "validation/25-shovel-17-final.mp4", scale: 1, codec: "h264" as const, crf: 18, pixelFormat: "yuv420p" as const };
const DRAFT = { path: "out/25/draft-480x270-60fps.mp4", scale: 0.25, codec: "h264" as const, crf: 23, pixelFormat: "yuv420p" as const };
const REPORT = "validation/25-export-report.json";
const CONCURRENCY = 3;
import { execFileSync } from "node:child_process";
const BROWSER_VERSION = execFileSync(BROWSER, ["--version"], { encoding: "utf8" }).trim();

const args = new Set(process.argv.slice(2));
const doDraft = !args.has("--final");
const doFinal = !args.has("--draft");
mkdirSync("out/25", { recursive: true });

const read = (p: string): string => readFileSync(p, "utf8");
const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");
const trace = JSON.parse(read("data/traces/shovel-17.trace.json"));
const geometry = JSON.parse(read("data/geometry.json"));
const spec = JSON.parse(read("data/presentations/shovel-17.presentation.json")) as PresentationSpec;
const manifest = JSON.parse(read("remotion/asset-manifest.json"));
const lock = JSON.parse(read("package-lock.json"));
const ver = (name: string): string => lock.packages[`node_modules/${name}`]?.version ?? "missing";
const stateAt = shotTimeEvaluator(trace as ShotTrace, geometry);
const r4 = (v: number): number => Math.round(v * 1e4) / 1e4;

type Logged = { frame: number; t: number; figures: Record<string, number[]>; puck: number[]; phase: string | null; readback_max_diff: number };
const parse = (text: string): Logged | null => (text.startsWith("[shot24-state] ") ? (JSON.parse(text.slice(15)) as Logged) : null);

const serveUrl = await bundle({ entryPoint: path.resolve("remotion/index.ts") });
const browser = await openBrowser("chrome", { browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" } });
const base = { serveUrl, browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" as const }, puppeteerInstance: browser };
const comp = await selectComposition({ ...base, id: COMPOSITION, inputProps: { overlays: true } });
const tl = resolveTimeline(spec, trace, comp.fps);

function pure(frame: number): Omit<Logged, "frame" | "readback_max_diff"> {
  const s = stateAt(sourceAtFrame(tl, frame).t, frame);
  const figures: Record<string, number[]> = {};
  for (const [pid, f] of Object.entries(s.figures)) figures[pid] = [r4(f.arcMm), r4(f.thetaDeg), r4(f.pivotMm[0]), r4(f.pivotMm[1]), r4(f.headingDeg)];
  return { t: r4(s.t), figures, puck: [r4(s.puckMm[0]), r4(s.puckMm[1])], phase: s.puckPhase };
}

async function render(o: typeof FINAL): Promise<Record<string, unknown>> {
  const logs = new Map<number, Logged>();
  const t0 = Date.now();
  await renderMedia({ ...base, composition: comp, codec: o.codec, crf: o.crf, pixelFormat: o.pixelFormat, outputLocation: o.path, inputProps: { overlays: true },
    scale: o.scale, concurrency: CONCURRENCY, onBrowserLog: (l) => { const s = parse(l.text); if (s) logs.set(s.frame, s); },
    onProgress: ({ renderedFrames }) => { if (renderedFrames % 50 === 0) console.log(`${o.path}: ${renderedFrames}/${comp.durationInFrames}`); } });
  const differing = [...logs.values()].filter((s) => JSON.stringify({ t: s.t, figures: s.figures, puck: s.puck, phase: s.phase }) !== JSON.stringify(pure(s.frame))).map((s) => s.frame);
  return { path: o.path, width: Math.round(comp.width * o.scale), height: Math.round(comp.height * o.scale), fps: comp.fps, frames: comp.durationInFrames,
    duration_s: comp.durationInFrames / comp.fps, codec: o.codec, crf: o.crf, pixel_format: o.pixelFormat, concurrency: CONCURRENCY,
    frames_logged: logs.size, frames_differing_from_pure: differing, max_readback_diff: Math.max(...[...logs.values()].map((s) => s.readback_max_diff)),
    render_seconds: Math.round((Date.now() - t0) / 1000), bytes: statSync(o.path).size, sha256: sha(o.path) };
}

const report: Record<string, unknown> = existsSync(REPORT) ? JSON.parse(read(REPORT)) : {};
Object.assign(report, {
  shot: "#17 Shovel",
  composition: COMPOSITION,
  route: "Remotion/Three, rendered directly (renderer decision: docs/review.md - Cycles benchmark not run, not switched)",
  versions: {
    node: process.version, remotion: ver("remotion"), "@remotion/three": ver("@remotion/three"), "@remotion/renderer": ver("@remotion/renderer"),
    three: ver("three"), "@react-three/fiber": ver("@react-three/fiber"), react: ver("react"), browser: `chrome-headless-shell ${BROWSER_VERSION}`,
    gl: "swangle (SwiftShader, CPU)",
  },
  model: { geometry_version: geometry.geometry_version, scene_glb_sha256: manifest.scene_glb.sha256, asset_sha256: manifest.asset_sha256 },
  trace: { trace_id: trace.trace_id, status: trace.status, sha256: sha("data/traces/shovel-17.trace.json"), approved_exceptions: trace.review?.revisions?.at(-1)?.approved_exceptions ?? [] },
  presentation: { presentation_id: spec.presentation_id, sha256: sha("data/presentations/shovel-17.presentation.json"), presentation_fps: spec.fps, output_fps: comp.fps, camera: spec.camera },
  output_settings_status: "presentation choice proposed by the iteration-25 prompt (no settings were agreed): 1920 x 1080, 60 fps, H.264 CRF 18, yuv420p; not additional geometry precision",
});
if (doDraft) {
  report.draft = await render(DRAFT);
  console.log("draft", JSON.stringify(report.draft));
}
if (doFinal) {
  report.final = await render(FINAL);
  console.log("final", JSON.stringify(report.final));
}
await browser.close({ silent: true });
writeFileSync(REPORT, JSON.stringify(report, null, 1) + "\n");
console.log(`wrote ${REPORT}`);
