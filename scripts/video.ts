// One command for previewing and exporting the analysis videos (docs/video-workflow.md).
//
//   node scripts/video.ts <command> <target> [<target> ...] [options]
//
// Commands
//   list                 the targets (hand-made analysis videos and every shot-encyclopedia move with a video)
//   stills               review stills: chosen automatically from the trace events and the presentation (set-up, just
//                        before / at / after each contact, explanation freezes, camera moves, goal, end card), or --frames.
//                        PNGs + index.json + contact sheet in out/review/<target>/
//   draft                low-resolution motion preview: the same frames, frame rate and camera timing at --scale (default
//                        0.5) -> out/video/<target>-draft[-<from>-<to>].mp4
//   final                the export: full resolution, every check of the committed exports, report next to the video
//                        (validation/...). With --frames/--segment: a partial final in out/video/ (no report replaced)
//   scene-cache          only fill the scene cache for the selected frames (and print its statistics)
//   probe-scenes         scene-state isolation check: scenes of several compositions in one tab, two orders
// Options
//   --frames 100-160,200    output frames (inclusive ranges)      --segment shot_in,shot_freeze   named segments
//   --scale 0.5             resolution factor (stills, draft: 0.5; final: 1)
//   --cache                 scene layer from the scene cache (misses rendered and verified first); default: direct WebGL
//   --browser <path>        browser executable (else REMOTION_BROWSER_EXECUTABLE, else Remotion's own, else Playwright's)
//   --gl <backend>          swangle (default, CPU) | angle | angle-egl | egl | vulkan | swiftshader
//   --concurrency 2         browser tabs rendering in parallel
//   --out <dir>             output directory (stills, draft, partial final)
//   --cold                  delete the bundler cache first (benchmarks)    --report <file>   timings as JSON
//
// One invocation copies the assets, bundles and opens the browser once for all targets.
import { bundle } from "@remotion/bundler";
import { openBrowser, renderFrames, renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { execFileSync, spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { analysisFrame, resolveAnalysis, type AnalysisSpec } from "../src/model/analysis.ts";
import { checkTraceCompatibility, shotTimeEvaluator, type AssetManifest } from "../src/model/shot-pose.ts";
import type { ShotTrace } from "../src/model/trace.ts";
import { framesOf, reviewStills, selectRanges, type Range } from "./video/plan.ts";
import { backendLabel, resolveRenderEnv, type RenderEnv } from "./video/render-env.ts";
import { namespaceId, namespaceInputs, SceneCache, sceneState, serveCache, stateKey, type Entry } from "./video/scene-cache.ts";
import { allTargets, compositionSha, resolveTarget, sha, type Target } from "./video/targets.ts";

// ---------------------------------------------------------------- arguments
const argv = process.argv.slice(2);
const cmd = argv[0];
const COMMANDS = ["list", "stills", "draft", "final", "scene-cache", "probe-scenes"];
if (!cmd || !COMMANDS.includes(cmd)) {
  console.error(`usage: node scripts/video.ts <${COMMANDS.join("|")}> <target...> [--frames a-b] [--segment id] [--scale s] [--cache] [--browser path] [--gl backend] [--concurrency n] [--out dir]`);
  process.exit(2);
}
const opt: Record<string, string | true> = {};
const names: string[] = [];
for (let i = 1; i < argv.length; i++) {
  const a = argv[i]!;
  if (!a.startsWith("--")) names.push(a);
  else if (["--cache", "--cold", "--no-graphics"].includes(a)) opt[a.slice(2)] = true;
  else opt[a.slice(2)] = argv[++i] ?? "";
}
const str = (k: string): string | null => (typeof opt[k] === "string" ? (opt[k] as string) : null);
const CONCURRENCY = Number(str("concurrency") ?? 2);
const USE_CACHE = opt.cache === true;
const GRAPHICS = opt["no-graphics"] !== true;

if (cmd === "list") {
  for (const t of allTargets()) console.log(`${t.name.padEnd(22)} ${t.composition.padEnd(24)} ${t.final.out}`);
  process.exit(0);
}
if (!names.length && cmd !== "probe-scenes") throw new Error("name at least one target (node scripts/video.ts list)");

// ---------------------------------------------------------------- timing / report
const T0 = Date.now();
const timings: Record<string, number> = {};
async function timed<T>(name: string, f: () => Promise<T> | T): Promise<T> {
  const t = Date.now();
  try {
    return await f();
  } finally {
    timings[name] = Math.round((Date.now() - t) / 100) / 10;
    console.error(`[video] ${name}: ${timings[name]} s`);
  }
}
const read = (p: string): string => readFileSync(p, "utf8");
const r4 = (v: number): number => Math.round(v * 1e4) / 1e4;
const lock = JSON.parse(read("package-lock.json"));
const ver = (n: string): string => lock.packages[`node_modules/${n}`]?.version ?? "missing";

// ---------------------------------------------------------------- preparation
/** public/ gets the scene GLB of assets/ (copied only when it differs) and the manifest must match it. */
function prepareAssets(): void {
  mkdirSync("public", { recursive: true });
  const src = "assets/scene/full_static_appearance.glb", dst = "public/full_static_appearance.glb";
  if (!existsSync(dst) || statSync(dst).size !== statSync(src).size || sha(dst) !== sha(src)) copyFileSync(src, dst);
  const manifest = JSON.parse(read("remotion/asset-manifest.json"));
  if (manifest.scene_glb.sha256 !== sha(dst)) execFileSync(process.execPath, ["scripts/shot23-manifest.ts"], { stdio: "inherit" });
}

/** Node-side gate before anything is rendered or a cached image is used (the composition repeats its own in the page). */
function gate(t: Target): string[] {
  const trace = JSON.parse(read(t.trace));
  const checks = JSON.parse(read(t.checks));
  const geometry = JSON.parse(read("data/geometry.json"));
  const passed = checkTraceCompatibility(trace, geometry.geometry_version, JSON.parse(read("remotion/asset-manifest.json")) as AssetManifest);
  if (trace.status !== "accepted" && !(t.allowProposed && trace.status === "proposed")) throw new Error(`${t.name}: trace ${trace.trace_id} is ${trace.status}`);
  if (checks.trace_id !== trace.trace_id) throw new Error(`${t.name}: checks are for ${checks.trace_id}, not ${trace.trace_id}`);
  if (checks.unexpected_penetrations?.length) throw new Error(`${t.name}: trace overlaps geometry`);
  const spec = JSON.parse(read(t.spec));
  if (spec.trace_id !== trace.trace_id) throw new Error(`${t.name}: presentation is for ${spec.trace_id}, trace is ${trace.trace_id}`);
  passed.push("contact_checks", "presentation_trace_id");
  if (t.move) {
    // the move's saved trace must still match its move file, engine and model, and its presentation today's story
    const py = process.env.PYTHON ?? "python3";
    const r = spawnSync(py, ["scripts/build-move.py", t.move, "--check"], { encoding: "utf8" });
    const rows = (() => { try { return JSON.parse(r.stdout) as { problems: string[] }[]; } catch { return null; } })();
    if (!rows) throw new Error(`${t.name}: could not run the move check (${py} scripts/build-move.py ${t.move} --check): ${r.stderr || r.error}`);
    if (rows[0]!.problems.length) throw new Error(`${t.name}: ${rows[0]!.problems.join("; ")}`);
    passed.push("move_motion_identity", "presentation_current");
  }
  return passed;
}

// ---------------------------------------------------------------- per-target pure evaluation
interface Loaded {
  t: Target;
  trace: ShotTrace & { trace_id: string; status: string; events: { id: string; t_estimate: number | null }[] };
  spec: AnalysisSpec;
  analysis: ReturnType<typeof resolveAnalysis>;
  stateAt: ReturnType<typeof shotTimeEvaluator>;
}
function load(t: Target): Loaded {
  const trace = JSON.parse(read(t.trace));
  const spec = JSON.parse(read(t.spec)) as AnalysisSpec;
  return { t, trace, spec, analysis: resolveAnalysis(spec, trace), stateAt: shotTimeEvaluator(trace, JSON.parse(read("data/geometry.json"))) };
}
type Logged = { frame: number; t: number; figures: Record<string, number[]>; puck: number[]; phase: string | null; readback_max_diff: number };
type Cam = { frame: number; position: number[]; fov: number };
function pure(L: Loaded, frame: number) {
  const af = analysisFrame(L.analysis, frame);
  const s = L.stateAt(af.t, frame);
  const figures: Record<string, number[]> = {};
  for (const [pid, f] of Object.entries(s.figures)) figures[pid] = [r4(f.arcMm), r4(f.thetaDeg), r4(f.pivotMm[0]), r4(f.pivotMm[1]), r4(f.headingDeg)];
  return { af, s, logged: { t: r4(s.t), figures, puck: [r4(s.puckMm[0]), r4(s.puckMm[1])], phase: s.puckPhase } };
}
const camDiff = (L: Loaded, c: Cam): number => {
  const p = analysisFrame(L.analysis, c.frame).camera;
  return Math.max(...p.positionMm.map((v, k) => Math.abs(v - c.position[k]!)), Math.abs(p.fovDeg - c.fov));
};

/** Collects the page logs of a render: states, cameras, cached-frame mappings, the WebGL renderer, failed checks. */
function logSink(tag: string) {
  const states = new Map<number, Logged>(), cams = new Map<number, Cam>(), cached = new Map<number, string>(), renderers = new Set<string>();
  const onBrowserLog = (l: { text: string }) => {
    const x = l.text;
    if (x.startsWith(`[${tag}-state] `)) { const s = JSON.parse(x.slice(tag.length + 9)) as Logged; states.set(s.frame, s); }
    else if (x.startsWith(`[${tag}-camera] `)) { const c = JSON.parse(x.slice(tag.length + 10)) as Cam; cams.set(c.frame, c); }
    else if (x.startsWith(`[${tag}-cached] `)) { const c = JSON.parse(x.slice(tag.length + 10)) as { frame: number; src: string }; cached.set(c.frame, c.src); }
    else if (x.startsWith("[gl-renderer] ")) { const g = JSON.parse(x.slice(14)); renderers.add(`${g.renderer} (${g.vendor}; ${g.version})`); }
    else if (/FAIL|Error/.test(x)) console.error(x.slice(0, 400));
  };
  return { states, cams, cached, renderers, onBrowserLog };
}

/** Frames whose logged state differs from the pure evaluation, the worst camera difference and the worst readback. */
function verifyLive(L: Loaded, sink: ReturnType<typeof logSink>, frames: number[]) {
  const differing: number[] = [], missing: number[] = [];
  let camWorst = 0, readback = 0;
  for (const f of frames) {
    const s = sink.states.get(f), c = sink.cams.get(f);
    if (!s || !c) { missing.push(f); continue; }
    if (JSON.stringify({ t: s.t, figures: s.figures, puck: s.puck, phase: s.phase }) !== JSON.stringify(pure(L, f).logged)) differing.push(f);
    camWorst = Math.max(camWorst, camDiff(L, c));
    readback = Math.max(readback, s.readback_max_diff);
  }
  return { differing, missing, camWorst: Math.round(camWorst * 1e4) / 1e4, readback };
}

// ---------------------------------------------------------------- main
const targets = cmd === "probe-scenes" ? [] : names.map(resolveTarget);
mkdirSync("out", { recursive: true });
await timed("prepare_assets", prepareAssets);
const gates = await timed("gates", () => Object.fromEntries(targets.map((t) => [t.name, gate(t)])));
const env: RenderEnv = await timed("resolve_browser", () => resolveRenderEnv({ browser: str("browser"), gl: str("gl") }));
console.error(`[video] browser ${env.browserExecutable} (${env.browserSource}, ${env.browserVersion}); --gl=${env.gl}; concurrency ${CONCURRENCY}`);
if (opt.cold) for (const d of ["node_modules/.cache"]) rmSync(d, { recursive: true, force: true });
const serveUrl = await timed("bundle", () => bundle({ entryPoint: path.resolve("remotion/index.ts") }));
const browser = await timed("open_browser", () => openBrowser("chrome", { browserExecutable: env.browserExecutable, chromiumOptions: env.chromiumOptions }));
const base = { serveUrl, browserExecutable: env.browserExecutable, chromiumOptions: env.chromiumOptions, puppeteerInstance: browser, timeoutInMilliseconds: Number(str("timeout") ?? 180000) };

// the WebGL implementation these flags give (cheap page, no scene): part of the scene-cache namespace and every report
const probe = await timed("probe_renderer", async () => {
  const sink = logSink("gl-probe");
  const comp = await selectComposition({ ...base, id: "gl-probe", inputProps: {} });
  const tmp = mkdtempSync("out/.probe-");
  await renderStill({ ...base, composition: comp, frame: 0, output: path.join(tmp, "p.png"), inputProps: {}, onBrowserLog: sink.onBrowserLog });
  rmSync(tmp, { recursive: true, force: true });
  return [...sink.renderers][0] ?? "unknown";
});
console.error(`[video] WebGL renderer: ${probe}`);

const results: Record<string, unknown>[] = [];
let server: Awaited<ReturnType<typeof serveCache>> | null = null;
const cacheServer = async () => (server ??= await serveCache());

try {
  if (cmd === "probe-scenes") results.push(await probeScenes());
  for (const t of targets) {
    const L = load(t);
    const scale = Number(str("scale") ?? (cmd === "final" ? 1 : 0.5));
    const ranges = selectRanges(L.analysis, str("frames"), str("segment"));
    const full = ranges.length === 1 && ranges[0]!.from === 0 && ranges[0]!.to === L.analysis.durationInFrames - 1;
    const res: Record<string, unknown> = { target: t.name, composition: t.composition, command: cmd, gate: gates[t.name], scale, concurrency: CONCURRENCY, mode: USE_CACHE ? "cached" : "direct" };
    const tt = Date.now();
    if (cmd === "stills") res.stills = await stills(L, scale);
    else if (cmd === "scene-cache") res.cache = await fillCache(L, framesOf(ranges), scale);
    else if (cmd === "draft" || cmd === "final") res.clips = await clips(L, ranges, scale, full);
    res.seconds = Math.round((Date.now() - tt) / 100) / 10;
    results.push(res);
  }
} finally {
  await browser.close({ silent: true });
  if (server) await (server as { close: () => Promise<void> }).close();
}
const summary = { command: cmd, targets: names, backend: backendLabel(env, [probe]), browser: { path: env.browserExecutable, source: env.browserSource, version: env.browserVersion }, gl: env.gl, webgl_renderer: probe, concurrency: CONCURRENCY, timings, total_seconds: Math.round((Date.now() - T0) / 100) / 10, results };
if (str("report")) writeFileSync(str("report")!, JSON.stringify(summary, null, 1) + "\n");
console.log(JSON.stringify(summary, null, 1));

// ---------------------------------------------------------------- commands
async function composition(L: Loaded, inputProps: Record<string, unknown>) {
  return selectComposition({ ...base, id: L.t.composition, inputProps });
}

/** Renders the given output frames as PNGs (one tab per concurrency slot); live WebGL or the cached scene layer. */
async function renderPngs(L: Loaded, frames: number[], scale: number, outDir: string, graphics: boolean, sceneSrc: string[] | null) {
  const inputProps = { graphics, frameMap: frames, sceneSrc };
  const comp = await composition(L, inputProps);
  const sink = logSink(L.t.tag);
  const tmp = mkdtempSync(path.join("out", ".frames-"));
  await renderFrames({ ...base, composition: comp, inputProps, imageFormat: "png", scale, concurrency: CONCURRENCY, outputDir: tmp, onStart: () => undefined, onFrameUpdate: () => undefined, onBrowserLog: sink.onBrowserLog });
  const files = readdirSync(tmp).filter((f) => f.endsWith(".png")).sort((a, b) => Number(/(\d+)\.png$/.exec(a)![1]) - Number(/(\d+)\.png$/.exec(b)![1]));
  if (files.length !== frames.length) throw new Error(`rendered ${files.length} images for ${frames.length} frames`);
  mkdirSync(outDir, { recursive: true });
  const out = files.map((f, i) => {
    const dst = path.join(outDir, `f${String(frames[i]).padStart(4, "0")}.png`);
    renameSync(path.join(tmp, f), dst);
    return dst;
  });
  rmSync(tmp, { recursive: true, force: true });
  return { out, sink };
}

async function stills(L: Loaded, scale: number) {
  const auto = !str("frames") && !str("segment");
  const list = auto ? reviewStills(L.analysis, L.trace.events) : framesOf(selectRanges(L.analysis, str("frames"), str("segment"))).map((frame) => ({ frame, reasons: ["requested"] }));
  const dir = str("out") ?? path.join("out/review", L.t.name.replace(":", "-"));
  rmSync(dir, { recursive: true, force: true });
  const frames = list.map((s) => s.frame);
  const src = USE_CACHE ? await cachedSources(L, frames, scale) : null;
  const { out, sink } = await renderPngs(L, frames, scale, dir, GRAPHICS, src?.urls ?? null);
  const live = verifyLive(L, sink, USE_CACHE ? [] : frames);
  const mapping = src ? verifyMapping(L, sink, frames, src) : null;
  if (live.differing.length || live.missing.length || live.camWorst > 0.02 || (mapping && mapping.errors.length)) throw new Error(`${L.t.name}: stills check failed ${JSON.stringify({ live, mapping })}`);
  const index = list.map((s, i) => ({ ...s, file: out[i] }));
  writeFileSync(path.join(dir, "index.json"), JSON.stringify({ target: L.t.name, composition: L.t.composition, scale, auto, mode: USE_CACHE ? "cached" : "direct", stills: index }, null, 1) + "\n");
  const sheet = path.join(dir, "contact-sheet.jpg");
  const py = spawnSync(process.env.PYTHON ?? "python3", ["scripts/video/contact-sheet.py", path.join(dir, "index.json"), sheet], { encoding: "utf8" });
  return { dir, count: out.length, frames, contact_sheet: py.status === 0 ? sheet : `not made (${(py.stderr || String(py.error)).trim().split("\n").pop()})`, renderers: [...sink.renderers], checks: { live, mapping }, cache: src?.stats ?? null };
}

/** Draft or final clips: one mp4 per contiguous range, live WebGL or composited over the scene cache. */
async function clips(L: Loaded, ranges: Range[], scale: number, full: boolean) {
  const out: Record<string, unknown>[] = [];
  const dir = str("out") ?? "out/video";
  mkdirSync(dir, { recursive: true });
  for (const r of ranges) {
    const frames = framesOf([r]);
    const exportFull = cmd === "final" && full && scale === 1 && !str("out");
    const suffix = full ? "" : `-${r.from}-${r.to}`;
    const file = exportFull ? L.t.final.out : path.join(dir, `${L.t.name.replace(":", "-")}-${cmd}${suffix}${scale !== 1 ? `-x${scale}` : ""}.mp4`);
    const src = USE_CACHE ? await cachedSources(L, frames, scale) : null;
    const inputProps = { graphics: GRAPHICS, sceneSrc: src?.urls ?? null };
    const comp = await composition(L, inputProps);
    const sink = logSink(L.t.tag);
    const t0 = Date.now();
    await timed(`${L.t.name}:${cmd}${suffix}`, () => renderMedia({
      ...base, composition: comp, inputProps, codec: "h264", crf: 20, pixelFormat: "yuv420p", outputLocation: file, scale, concurrency: CONCURRENCY,
      frameRange: [r.from, r.to], onBrowserLog: sink.onBrowserLog,
      onProgress: ({ renderedFrames }) => { if (renderedFrames % 100 === 0 && renderedFrames) console.error(`${file}: ${renderedFrames}/${frames.length}`); },
    }));
    const seconds = Math.round((Date.now() - t0) / 100) / 10;
    // frame accounting: every requested frame rendered exactly once, at the composition's frame rate and size
    const probeOut = JSON.parse(execFileSync(process.execPath, [path.resolve("node_modules/@remotion/cli/remotion-cli.js"), "ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,r_frame_rate,nb_frames,pix_fmt:format=duration", "-of", "json", file], { encoding: "utf8" }));
    const st = probeOut.streams[0];
    const accounting = {
      requested: frames.length, encoded: Number(st.nb_frames), fps: st.r_frame_rate, width: st.width, height: st.height,
      expected: { fps: `${L.analysis.spec.fps}/1`, width: Math.round(L.analysis.spec.width * scale), height: Math.round(L.analysis.spec.height * scale) },
    };
    const accountingOk = accounting.encoded === frames.length && accounting.fps === accounting.expected.fps && accounting.width === accounting.expected.width && accounting.height === accounting.expected.height;
    const live = verifyLive(L, sink, src ? [] : frames);
    const mapping = src ? verifyMapping(L, sink, frames, src) : null;
    const bytes = statSync(file).size;
    const row = { file, frames: [r.from, r.to], frames_count: frames.length, seconds, bytes, megabytes: Math.round(bytes / 1e4) / 100, accounting, accounting_ok: accountingOk, renderers: [...sink.renderers], live, mapping, cache: src?.stats ?? null };
    out.push(row);
    const failed = !accountingOk || live.differing.length || live.missing.length || live.camWorst > 0.02 || (mapping && mapping.errors.length) || (exportFull && bytes >= 25e6);
    if (exportFull) writeExportReport(L, file, comp, row, seconds);
    if (failed) throw new Error(`${L.t.name}: ${cmd} check FAILED ${JSON.stringify({ accounting, live, mapping })}`);
  }
  return out;
}

function writeExportReport(L: Loaded, file: string, comp: { width: number; height: number; fps: number; durationInFrames: number }, row: Record<string, unknown>, seconds: number) {
  const manifest = JSON.parse(read("remotion/asset-manifest.json"));
  const geometry = JSON.parse(read("data/geometry.json"));
  const probeOut = JSON.parse(execFileSync(process.execPath, [path.resolve("node_modules/@remotion/cli/remotion-cli.js"), "ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,r_frame_rate,nb_frames,pix_fmt:format=duration", "-of", "json", file], { encoding: "utf8" }));
  const live = row.live as ReturnType<typeof verifyLive>;
  const mapping = row.mapping as ReturnType<typeof verifyMapping> | null;
  const bytes = statSync(file).size;
  const report = {
    analysis: L.t.final.title,
    composition: L.t.composition,
    versions: {
      node: process.version, remotion: ver("remotion"), "@remotion/three": ver("@remotion/three"), three: ver("three"), "@react-three/fiber": ver("@react-three/fiber"),
      react: ver("react"), browser: env.browserVersion, gl: backendLabel(env, (row.renderers as string[]).length ? (row.renderers as string[]) : [probe]),
    },
    model: { geometry_version: geometry.geometry_version, scene_glb_sha256: manifest.scene_glb.sha256 },
    trace: { trace_id: L.trace.trace_id, status: L.trace.status, sha256: sha(L.t.trace) },
    analysis_spec: { analysis_id: L.spec.analysis_id, sha256: sha(L.t.spec), composition_files: L.t.files, composition_sha256: compositionSha(L.t.files) },
    output: {
      path: file, width: comp.width, height: comp.height, fps: comp.fps, frames: comp.durationInFrames, duration_s: comp.durationInFrames / comp.fps,
      codec: "h264", crf: 20, pixel_format: "yuv420p", ffprobe: probeOut, bytes, megabytes: Math.round(bytes / 1e4) / 100, below_25_mb: bytes < 25e6, sha256: sha(file),
    },
    checks: {
      // frames whose scene was drawn by WebGL in this render and logged its state (cached frames are counted in scene_cache)
      frames_logged: comp.durationInFrames - (mapping ? mapping.checked : 0), frames_differing_from_pure: live.differing, max_readback_diff: mapping && mapping.checked === comp.durationInFrames ? null : live.readback,
      camera_frames_logged: comp.durationInFrames - (mapping ? mapping.checked : 0), camera_max_diff_vs_track: mapping && mapping.checked === comp.durationInFrames ? null : live.camWorst,
      scene_cache: mapping ? { ...mapping, stats: row.cache } : null,
    },
    render: { mode: USE_CACHE ? "cached" : "direct", concurrency: CONCURRENCY, scale: 1, browser: env.browserExecutable, gl_flag: env.gl, webgl_renderers: row.renderers, probe_renderer: probe },
    render_seconds: Math.round(seconds),
  };
  writeFileSync(L.t.final.report, JSON.stringify(report, null, 1) + "\n");
  console.error(`[video] wrote ${file} and ${L.t.final.report}`);
}

// ---------------------------------------------------------------- scene cache
async function openCache(L: Loaded, scale: number) {
  const background = sceneBackground(L);
  const inputs = namespaceInputs({ browserVersion: env.browserVersion, gl: env.gl, webglRenderer: probe, width: L.analysis.spec.width, height: L.analysis.spec.height, scale, background });
  const ns = namespaceId(inputs);
  return new SceneCache(ns, inputs);
}

/** The CSS background behind the canvas: the theme of the composition (read from its config, remotion/theme.ts). */
function sceneBackground(L: Loaded): string {
  const themes = read("remotion/theme.ts");
  const id = L.t.move ? (/theme: "(\w+)" \}/.exec(read("remotion/encyclopedia-registry.ts").split("\n").find((l) => l.includes(`id: "${L.t.move}"`)) ?? "")?.[1] ?? "classic") : (/theme: "(\w+)"/.exec(read(L.t.files[0]!))?.[1] ?? /DEFAULT_THEME: Theme\["id"\] = "(\w+)"/.exec(themes)![1]!);
  const block = themes.slice(themes.indexOf(`  ${id}: {`));
  const bg = /background: (`[^`]*`|"[^"]*")/.exec(block)?.[1];
  if (!bg) throw new Error(`theme ${id}: no background`);
  return `${id}:${bg}`;
}

/** Scene state key of every frame; the cache entries they need; renders and verifies the missing ones. */
async function fillCache(L: Loaded, frames: number[], scale: number) {
  const cache = await openCache(L, scale);
  const keyOf = new Map<number, string>();
  const stateOf = new Map<string, ReturnType<typeof sceneState>>();
  const firstFrame = new Map<string, number>();
  for (const f of frames) {
    const { af, s } = pure(L, f);
    const st = sceneState(s, af.camera);
    const k = stateKey(cache.ns, st);
    keyOf.set(f, k);
    if (!stateOf.has(k)) { stateOf.set(k, st); firstFrame.set(k, f); }
  }
  const missing = [...stateOf.keys()].filter((k) => !cache.entry(k));
  let renderSeconds = 0;
  const renderers = new Set<string>();
  if (missing.length) {
    const reps = missing.map((k) => firstFrame.get(k)!);
    const t0 = Date.now();
    const tmp = mkdtempSync(path.join("out", ".scene-"));
    const { out, sink } = await timed(`${L.t.name}:scene_renders(${reps.length})`, () => renderPngs(L, reps, scale, tmp, false, null));
    renderSeconds = Math.round((Date.now() - t0) / 100) / 10;
    sink.renderers.forEach((r) => renderers.add(r));
    // the namespace and every entry name the probe's renderer: the scene renders must report exactly that one
    if (!sink.renderers.size) throw new Error(`${L.t.name}: the scene renders logged no WebGL renderer; nothing cached`);
    for (const r of sink.renderers) if (r !== probe) throw new Error(`scene renders used ${r}, the probe said ${probe}: not caching`);
    const v = verifyLive(L, sink, reps);
    if (v.differing.length || v.missing.length || v.camWorst > 0.02 || v.readback > 1e-3) throw new Error(`${L.t.name}: scene renders failed verification ${JSON.stringify(v)}; nothing cached`);
    reps.forEach((f, i) => {
      const k = missing[i]!;
      cache.put(k, out[i]!, {
        rendered: { target: L.t.name, composition: L.t.composition, frame: f, at: new Date().toISOString(), render_seconds_batch: renderSeconds },
        verification: { state_equal_to_pure: true, readback_max_diff: sink.states.get(f)!.readback_max_diff, camera_max_diff_mm: Math.round(camDiff(L, sink.cams.get(f)!) * 1e4) / 1e4, webgl_renderer: probe },
        state: stateOf.get(k)!,
      });
    });
    rmSync(tmp, { recursive: true, force: true });
  }
  return { cache, keyOf, stats: { namespace: cache.ns, frames: frames.length, unique_scene_states: stateOf.size, cache_hits: stateOf.size - missing.length, scene_renders: missing.length, scene_render_seconds: renderSeconds, frames_without_a_new_render: frames.length - missing.length, entries_in_namespace: cache.size() } };
}

/** URLs of the cached scene image for each output frame (sparse array over the composition, filled for `frames`). */
async function cachedSources(L: Loaded, frames: number[], scale: number) {
  const { cache, keyOf, stats } = await fillCache(L, frames, scale);
  const srv = await cacheServer();
  const urls: string[] = new Array(L.analysis.durationInFrames).fill("");
  for (const f of frames) urls[f] = `${srv.base}/${cache.ns}/${keyOf.get(f)}.png`;
  return { urls, keyOf, cache, stats };
}

/** Every composited frame showed the image of its own scene state, and that image's verified record matches it. */
function verifyMapping(L: Loaded, sink: ReturnType<typeof logSink>, frames: number[], src: Awaited<ReturnType<typeof cachedSources>>) {
  const errors: string[] = [];
  const entries = new Set<string>();
  let readback = 0, camWorst = 0;
  for (const f of frames) {
    const shown = sink.cached.get(f);
    if (shown === undefined) { errors.push(`frame ${f}: no cached-scene log`); continue; }
    const k = src.keyOf.get(f)!;
    if (!shown.endsWith(`/${k}.png`)) { errors.push(`frame ${f}: showed ${shown.slice(-20)}, expected ${k.slice(0, 12)}`); continue; }
    const e = src.cache.entry(k) as Entry | null;
    if (!e) { errors.push(`frame ${f}: entry ${k.slice(0, 12)} missing or unverified`); continue; }
    const { af, s } = pure(L, f);
    if (JSON.stringify(e.state) !== JSON.stringify(sceneState(s, af.camera))) errors.push(`frame ${f}: entry state differs from the frame's pure state`);
    entries.add(k);
    readback = Math.max(readback, e.verification.readback_max_diff);
    camWorst = Math.max(camWorst, e.verification.camera_max_diff_mm);
  }
  if (sink.states.size) errors.push(`${sink.states.size} frames drew WebGL during a cached composite`);
  // the worst differences recorded when the reused entries were rendered (their own scene renders, not new readbacks)
  return { checked: frames.length, entries_used: entries.size, errors, entries_max_readback_diff: readback, entries_camera_max_diff_mm: camWorst };
}

// ---------------------------------------------------------------- scene isolation probe
async function probeScenes() {
  // the same scenes drawn alone (each in a fresh tab) and one after another in ONE tab, in two orders
  const items = [{ video: "analysis-shovel-17", frame: 300 }, { video: "move-hjerpefinte", frame: 330 }, { video: "analysis-ikv", frame: 450 }, { video: "analysis-nacka", frame: 400 }];
  const scale = Number(str("scale") ?? 0.25);
  const dir = str("out") ?? "out/scene-probe";
  rmSync(dir, { recursive: true, force: true });
  const render = async (list: typeof items, name: string) => {
    const comp = await selectComposition({ ...base, id: "scene-probe", inputProps: { items: list } });
    const sub = path.join(dir, name);
    mkdirSync(sub, { recursive: true });
    // concurrency 1: every item is drawn in the same tab, after the ones before it
    await renderFrames({ ...base, composition: comp, inputProps: { items: list }, imageFormat: "png", scale, concurrency: 1, outputDir: sub, onStart: () => undefined, onFrameUpdate: () => undefined });
    return readdirSync(sub).filter((f) => f.endsWith(".png")).sort().map((f) => sha(path.join(sub, f)));
  };
  const alone: string[] = [];
  for (const [i, it] of items.entries()) alone.push((await render([it], `alone-${i}`))[0]!);
  const fwd = await render(items, "forward");
  const rev = await render([...items].reverse(), "reverse");
  const rows = items.map((it, i) => ({ ...it, alone: alone[i]!.slice(0, 16), forward: fwd[i]!.slice(0, 16), reverse: rev[items.length - 1 - i]!.slice(0, 16), identical: alone[i] === fwd[i] && alone[i] === rev[items.length - 1 - i] }));
  const ok = rows.every((r) => r.identical);
  console.error(`[video] scene probe: ${ok ? "PASS" : "FAIL"} ${JSON.stringify(rows)}`);
  if (!ok && !opt["expect-fail"]) process.exitCode = 1;
  return { probe: "scene isolation", scale, items: rows, passed: ok };
}
