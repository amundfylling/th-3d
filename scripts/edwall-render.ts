// Edwall hat-trick analysis videos (compositions analysis-edwall-g2-goal2..4, remotion/EdwallAnalysis.tsx): renders one
// to a 1920 x 1080, 30 fps H.264 MP4 and checks it, exactly as scripts/analysis-render.ts (copied so the shared render
// script and Root stay untouched; the bundle entry is remotion/edwall-index.ts).
//
//   node scripts/edwall-render.ts g2-goal2|g2-goal3|g2-goal4
//
// Checks: every frame's logged physical state equals the pure Node evaluation of the trace at the source time of the
// analysis timeline; every frame's canvas camera equals the pure camera track; the file is below 25 MB.
// Report: validation/analysis-edwall-<goal>-report.json. Video: validation/analysis-edwall-<goal>.mp4.
import { bundle } from "@remotion/bundler";
import { openBrowser, renderMedia, selectComposition } from "@remotion/renderer";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { analysisFrame, resolveAnalysis, type AnalysisSpec } from "../src/model/analysis.ts";
import { shotTimeEvaluator } from "../src/model/shot-pose.ts";
import type { ShotTrace } from "../src/model/trace.ts";

const BROWSER = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
const VIDEOS = Object.fromEntries((["g2-goal2", "g2-goal3", "g2-goal4"] as const).map((g, i) => [g, {
  composition: `analysis-edwall-${g}`, spec: `data/presentations/edwall-${g}.analysis.json`, trace: `data/traces/edwall-${g}.trace.json`,
  files: ["remotion/EdwallAnalysis.tsx", "remotion/AnalysisVideo.tsx"], tag: `edwall${i + 1}`, out: `validation/analysis-edwall-${g}.mp4`,
  report: `validation/analysis-edwall-${g}-report.json`, title: `Edwall hat-trick goal ${i + 1} of 3 (NM26 semi-final game 2, ${g}) - sports-analysis video`,
}])) as Record<string, { composition: string; spec: string; trace: string; files: string[]; tag: string; out: string; report: string; title: string }>;
const NAME = process.argv[2] ?? "g2-goal2";
const V = VIDEOS[NAME];
if (!V) throw new Error(`unknown video ${NAME}; one of ${Object.keys(VIDEOS).join(", ")}`);
const COMPOSITION = V.composition;
const SPEC = V.spec;
const OUT = { path: V.out, codec: "h264" as const, crf: 20, pixelFormat: "yuv420p" as const, concurrency: 2 };
const REPORT = V.report;
const MAX_BYTES = 25 * 1000 * 1000;

const read = (p: string): string => readFileSync(p, "utf8");
const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");
/** Fingerprint of the files that define a composition (each file's path and SHA-256, in order). */
const compositionSha = (files: readonly string[]): string => createHash("sha256").update(files.map((f) => `${f}:${sha(f)}`).join("\n")).digest("hex");
const trace = JSON.parse(read(V.trace)) as ShotTrace;
const geometry = JSON.parse(read("data/geometry.json"));
const spec = JSON.parse(read(SPEC)) as AnalysisSpec;
const analysis = resolveAnalysis(spec, trace as unknown as Parameters<typeof resolveAnalysis>[1]);
const manifest = JSON.parse(read("remotion/asset-manifest.json"));
const lock = JSON.parse(read("package-lock.json"));
const ver = (name: string): string => lock.packages[`node_modules/${name}`]?.version ?? "missing";
const stateAt = shotTimeEvaluator(trace, geometry);
const r4 = (v: number): number => Math.round(v * 1e4) / 1e4;

type Logged = { frame: number; t: number; figures: Record<string, number[]>; puck: number[]; phase: string | null; readback_max_diff: number };
type Cam = { frame: number; position: number[]; fov: number };

function pure(frame: number): Omit<Logged, "frame" | "readback_max_diff"> {
  const s = stateAt(analysisFrame(analysis, frame).t, frame);
  const figures: Record<string, number[]> = {};
  for (const [pid, f] of Object.entries(s.figures)) figures[pid] = [r4(f.arcMm), r4(f.thetaDeg), r4(f.pivotMm[0]), r4(f.pivotMm[1]), r4(f.headingDeg)];
  return { t: r4(s.t), figures, puck: [r4(s.puckMm[0]), r4(s.puckMm[1])], phase: s.puckPhase };
}

const serveUrl = await bundle({ entryPoint: path.resolve("remotion/edwall-index.ts") });
const browser = await openBrowser("chrome", { browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" } });
const base = { serveUrl, browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" as const }, puppeteerInstance: browser };
const comp = await selectComposition({ ...base, id: COMPOSITION, inputProps: { graphics: true } });

const states = new Map<number, Logged>();
const cams = new Map<number, Cam>();
const t0 = Date.now();
await renderMedia({
  ...base, composition: comp, codec: OUT.codec, crf: OUT.crf, pixelFormat: OUT.pixelFormat, outputLocation: OUT.path, inputProps: { graphics: true },
  concurrency: OUT.concurrency,
  onBrowserLog: (l) => {
    if (l.text.startsWith(`[${V.tag}-state] `)) { const s = JSON.parse(l.text.slice(V.tag.length + 9)) as Logged; states.set(s.frame, s); }
    if (l.text.startsWith(`[${V.tag}-camera] `)) { const c = JSON.parse(l.text.slice(V.tag.length + 10)) as Cam; cams.set(c.frame, c); }
  },
  onProgress: ({ renderedFrames }) => { if (renderedFrames % 50 === 0) console.log(`${OUT.path}: ${renderedFrames}/${comp.durationInFrames}`); },
});
await browser.close({ silent: true });

const differing = [...states.values()].filter((s) => JSON.stringify({ t: s.t, figures: s.figures, puck: s.puck, phase: s.phase }) !== JSON.stringify(pure(s.frame))).map((s) => s.frame);
let camWorst = 0;
for (const c of cams.values()) {
  const p = analysisFrame(analysis, c.frame).camera;
  camWorst = Math.max(camWorst, ...p.positionMm.map((v, k) => Math.abs(v - c.position[k]!)), Math.abs(p.fovDeg - c.fov));
}
const bytes = statSync(OUT.path).size;
const probe = JSON.parse(execFileSync("npx", ["remotion", "ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,r_frame_rate,nb_frames,pix_fmt:format=duration", "-of", "json", OUT.path], { encoding: "utf8" }));

const report = {
  analysis: V.title,
  composition: COMPOSITION,
  versions: {
    node: process.version, remotion: ver("remotion"), "@remotion/three": ver("@remotion/three"), three: ver("three"), "@react-three/fiber": ver("@react-three/fiber"),
    react: ver("react"), browser: `chrome-headless-shell ${execFileSync(BROWSER, ["--version"], { encoding: "utf8" }).trim()}`, gl: "swangle (SwiftShader, CPU)",
  },
  model: { geometry_version: geometry.geometry_version, scene_glb_sha256: manifest.scene_glb.sha256 },
  trace: { trace_id: trace.trace_id, status: trace.status, sha256: sha(V.trace) },
  analysis_spec: { analysis_id: spec.analysis_id, sha256: sha(SPEC), composition_files: V.files, composition_sha256: compositionSha(V.files) },
  output: {
    path: OUT.path, width: comp.width, height: comp.height, fps: comp.fps, frames: comp.durationInFrames, duration_s: comp.durationInFrames / comp.fps,
    codec: OUT.codec, crf: OUT.crf, pixel_format: OUT.pixelFormat, ffprobe: probe, bytes, megabytes: Math.round(bytes / 1e4) / 100,
    below_25_mb: bytes < MAX_BYTES, sha256: sha(OUT.path),
  },
  checks: {
    frames_logged: states.size, frames_differing_from_pure: differing, max_readback_diff: Math.max(...[...states.values()].map((s) => s.readback_max_diff)),
    camera_frames_logged: cams.size, camera_max_diff_vs_track: Math.round(camWorst * 1e4) / 1e4,
  },
  render_seconds: Math.round((Date.now() - t0) / 1000),
};
writeFileSync(REPORT, JSON.stringify(report, null, 1) + "\n");
console.log(JSON.stringify(report.output), JSON.stringify(report.checks));
if (differing.length || states.size !== comp.durationInFrames || cams.size !== comp.durationInFrames || camWorst > 0.02 || bytes >= MAX_BYTES) {
  console.error("analysis render check FAILED");
  process.exit(1);
}
console.log(`wrote ${OUT.path} (${report.output.megabytes} MB) and ${REPORT}`);
