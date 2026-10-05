// Iteration 23: renders and checks the accepted-trace shot composition (remotion/ShotPlayback.tsx).
//
//   node scripts/shot23-render.ts [--no-clip]
//
// 1. Diagnostic stills at the trace's contact times (composition shot23-at-time, frame 0 at startS = event time).
// 2. Order independence: selected frames of shot23-shovel-17 are rendered twice, each pass in a different shuffled
//    order; the logged numeric state and the PNG bytes must be identical between passes and equal to the pure
//    Node evaluation (src/model/shot-pose.ts).
// 3. Proof clip (half resolution, H.264) of the whole composition; every frame's logged state is compared with the
//    pure evaluation too.
// Results: validation/23-render-checks.json; images in out/23/ and validation/23-proof-clip.mp4.
import { bundle } from "@remotion/bundler";
import { openBrowser, renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { shotFrameEvaluator, type ShotFrameState } from "../src/model/shot-pose.ts";
import type { ShotTrace } from "../src/model/trace.ts";

const BROWSER = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
const OUT = "out/23";
const trace = JSON.parse(readFileSync("data/traces/shovel-17.trace.json", "utf8"));
const geometry = JSON.parse(readFileSync("data/geometry.json", "utf8"));
const pure = shotFrameEvaluator(trace as ShotTrace, geometry);
const noClip = process.argv.includes("--no-clip");
mkdirSync(OUT, { recursive: true });

type Logged = { frame: number; t: number; figures: Record<string, number[]>; puck: number[]; phase: string | null; readback_max_diff: number };
const r4 = (v: number): number => Math.round(v * 1e4) / 1e4;
const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");

/** Same rounding as the browser log, for an exact comparison. */
function pureLogged(s: ShotFrameState): Omit<Logged, "readback_max_diff"> {
  const figures: Record<string, number[]> = {};
  for (const [pid, f] of Object.entries(s.figures)) figures[pid] = [r4(f.arcMm), r4(f.thetaDeg), r4(f.pivotMm[0]), r4(f.pivotMm[1]), r4(f.headingDeg)];
  return { frame: s.frame, t: r4(s.t), figures, puck: [r4(s.puckMm[0]), r4(s.puckMm[1])], phase: s.puckPhase };
}

function maxDiff(a: Omit<Logged, "readback_max_diff">, b: Omit<Logged, "readback_max_diff">): number {
  let w = Math.abs(a.t - b.t) + Math.abs(a.puck[0]! - b.puck[0]!) + Math.abs(a.puck[1]! - b.puck[1]!);
  for (const [pid, v] of Object.entries(a.figures)) v.forEach((x, i) => (w = Math.max(w, Math.abs(x - b.figures[pid]![i]!))));
  return a.phase === b.phase ? w : Infinity;
}

// Seeded shuffle (deterministic, documented): mulberry32.
function shuffled<T>(xs: T[], seed: number): T[] {
  let s = seed >>> 0;
  const rnd = (): number => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const a = [...xs];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [a[i], a[j]] = [a[j]!, a[i]!];
  }
  return a;
}

const serveUrl = await bundle({ entryPoint: path.resolve("remotion/index.ts") });
const browser = await openBrowser("chrome", { browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" } });
const base = { serveUrl, browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" as const }, puppeteerInstance: browser };
const parse = (text: string): Logged | null => (text.startsWith("[shot23-state] ") ? (JSON.parse(text.slice(15)) as Logged) : null);

async function still(id: string, frame: number, output: string, inputProps: Record<string, unknown>, scale = 1): Promise<{ state: Logged; checks: string[]; sha256: string }> {
  const comp = await selectComposition({ ...base, id, inputProps });
  const logs: string[] = [];
  await renderStill({ ...base, composition: comp, frame, output, inputProps, scale, onBrowserLog: (l) => logs.push(l.text) });
  const states = logs.map(parse).filter((x): x is Logged => x !== null && x.frame === frame);
  if (!states.length) throw new Error(`${id} frame ${frame}: no state logged`);
  return { state: states[states.length - 1]!, checks: logs.filter((l) => l.startsWith("[shot23-check]")), sha256: sha(output) };
}

const report: Record<string, unknown> = { trace_id: trace.trace_id, trace_status: trace.status, geometry_version: trace.geometry_version, renderer: "Remotion 4.0.531, chrome-headless-shell, --gl=swangle (SwiftShader, CPU)" };

// 1. Diagnostic stills at the contact times.
const events = ["pass.release", "contact.W-C_reception", "shot.separation", "goal_entry"];
const diag = [];
for (const id of events) {
  const ev = trace.events.find((e: { id: string }) => e.id === id);
  const out = `${OUT}/diag-${id}.png`;
  const r = await still("shot23-at-time", 0, out, { startS: ev.t_estimate });
  const p = pureLogged(pure(0, 30, ev.t_estimate));
  diag.push({ event: id, t_event: ev.t_estimate, t_rendered: r.state.t, png: out, sha256: r.sha256, state: r.state, max_diff_vs_pure: maxDiff(r.state, p), checks: r.checks });
  console.log(`diag ${id} t=${r.state.t} diff ${maxDiff(r.state, p)}`);
}
report.diagnostic_stills = diag;

// 2. Shuffled, repeated frames (half resolution to save CPU time).
const frames = [0, 20, 36, 37, 38, 39, 40, 41, 42, 43, 45, 50];
const passes: Record<string, { order: number[]; states: Record<number, Logged>; sha: Record<number, string> }> = {};
for (const [name, seed] of [["A", 23], ["B", 2023]] as const) {
  const order = shuffled(frames, seed);
  const states: Record<number, Logged> = {}, shas: Record<number, string> = {};
  for (const f of order) {
    const r = await still("shot23-shovel-17", f, `${OUT}/order-${name}-f${String(f).padStart(3, "0")}.png`, {}, 0.5);
    states[f] = r.state;
    shas[f] = r.sha256;
  }
  passes[name] = { order, states, sha: shas };
  console.log(`pass ${name} order ${order.join(",")}`);
}
const orderRows = frames.map((f) => {
  const a = passes.A!.states[f]!, b = passes.B!.states[f]!;
  return { frame: f, t: a.t, state_identical: JSON.stringify(a) === JSON.stringify(b), png_identical: passes.A!.sha[f] === passes.B!.sha[f], max_diff_vs_pure: maxDiff(a, pureLogged(pure(f, 30, trace.time_base.window_s[0]))), readback_max_diff: Math.max(a.readback_max_diff, b.readback_max_diff) };
});
report.order_independence = { frames, order_A: passes.A!.order, order_B: passes.B!.order, rows: orderRows, pass: orderRows.every((r) => r.state_identical && r.png_identical && r.max_diff_vs_pure === 0) };
console.log("order independence", (report.order_independence as { pass: boolean }).pass);

// 3. Proof clip.
if (!noClip) {
  const comp = await selectComposition({ ...base, id: "shot23-shovel-17", inputProps: {} });
  const logs: Logged[] = [];
  const t0 = Date.now();
  await renderMedia({ ...base, composition: comp, codec: "h264", outputLocation: "validation/23-proof-clip.mp4", inputProps: {}, scale: 0.5, concurrency: 2, onBrowserLog: (l) => { const s = parse(l.text); if (s) logs.push(s); } });
  const byFrame = new Map(logs.map((s) => [s.frame, s]));
  const worst = Math.max(...[...byFrame.values()].map((s) => maxDiff(s, pureLogged(pure(s.frame, 30, trace.time_base.window_s[0])))));
  const stillMismatch = frames.filter((f) => byFrame.has(f) && JSON.stringify(byFrame.get(f)) !== JSON.stringify(passes.A!.states[f]));
  report.proof_clip = { path: "validation/23-proof-clip.mp4", frames: comp.durationInFrames, fps: comp.fps, size_px: [comp.width / 2, comp.height / 2], frames_logged: byFrame.size, max_diff_vs_pure: worst, frames_differing_from_stills: stillMismatch, render_seconds: Math.round((Date.now() - t0) / 1000), sha256: sha("validation/23-proof-clip.mp4") };
  console.log("clip", JSON.stringify(report.proof_clip));
} else report.proof_clip = { rendered: false };

await browser.close({ silent: true });
writeFileSync("validation/23-render-checks.json", JSON.stringify(report, null, 1) + "\n");
console.log("wrote validation/23-render-checks.json");
