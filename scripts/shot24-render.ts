// Iteration 24: renders and checks the presentation composition shot24-shovel-17 (remotion/ShotPresentation.tsx).
//
//   node scripts/shot24-render.ts [--no-clip]
//
// 1. Normal/replay comparison: pairs of presentation frames that map to the SAME source time (normal frame 30 + k and
//    replay frame 95 + 4 (k - 33)) are rendered with the overlays off; their logged physical state and PNG bytes must be
//    identical, and equal to the pure Node evaluation. The same pairs are rendered with overlays for the review sheet.
// 2. Contact pause: frames across the pause show the same state and identical pixels, at exactly the trace's
//    reception time.
// 3. Draft clip of the whole composition (half resolution); every frame's logged state equals the pure evaluation.
// Results: validation/24-render-checks.json, out/24/*.png, validation/24-draft.mp4.
import { bundle } from "@remotion/bundler";
import { openBrowser, renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { resolveTimeline, sourceAtFrame, type PresentationSpec } from "../src/model/presentation.ts";
import { shotTimeEvaluator, type ShotFrameState } from "../src/model/shot-pose.ts";
import type { ShotTrace } from "../src/model/trace.ts";

const BROWSER = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
const OUT = "out/24";
const trace = JSON.parse(readFileSync("data/traces/shovel-17.trace.json", "utf8"));
const geometry = JSON.parse(readFileSync("data/geometry.json", "utf8"));
const spec = JSON.parse(readFileSync("data/presentations/shovel-17.presentation.json", "utf8")) as PresentationSpec;
const tl = resolveTimeline(spec, trace);
const stateAt = shotTimeEvaluator(trace as ShotTrace, geometry);
const noClip = process.argv.includes("--no-clip");
mkdirSync(OUT, { recursive: true });

type Logged = { frame: number; t: number; figures: Record<string, number[]>; puck: number[]; phase: string | null; readback_max_diff: number };
type Phys = Omit<Logged, "frame" | "readback_max_diff">;
const r4 = (v: number): number => Math.round(v * 1e4) / 1e4;
const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");
const phys = (s: Logged | Phys): Phys => ({ t: s.t, figures: s.figures, puck: s.puck, phase: s.phase });

function pure(frame: number): Phys {
  const s: ShotFrameState = stateAt(sourceAtFrame(tl, frame).t, frame);
  const figures: Record<string, number[]> = {};
  for (const [pid, f] of Object.entries(s.figures)) figures[pid] = [r4(f.arcMm), r4(f.thetaDeg), r4(f.pivotMm[0]), r4(f.pivotMm[1]), r4(f.headingDeg)];
  return { t: r4(s.t), figures, puck: [r4(s.puckMm[0]), r4(s.puckMm[1])], phase: s.puckPhase };
}

const serveUrl = await bundle({ entryPoint: path.resolve("remotion/index.ts") });
const browser = await openBrowser("chrome", { browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" } });
const base = { serveUrl, browserExecutable: BROWSER, chromiumOptions: { gl: "swangle" as const }, puppeteerInstance: browser };
const parse = (text: string): Logged | null => (text.startsWith("[shot24-state] ") ? (JSON.parse(text.slice(15)) as Logged) : null);
const comps: Record<string, Awaited<ReturnType<typeof selectComposition>>> = {};

async function still(frame: number, overlays: boolean, scale: number): Promise<{ state: Logged; png: string; sha256: string }> {
  const key = String(overlays);
  comps[key] ??= await selectComposition({ ...base, id: "shot24-shovel-17", inputProps: { overlays } });
  const png = `${OUT}/f${String(frame).padStart(3, "0")}-${overlays ? "overlay" : "plain"}.png`;
  const logs: Logged[] = [];
  await renderStill({ ...base, composition: comps[key]!, frame, output: png, inputProps: { overlays }, scale, onBrowserLog: (l) => { const s = parse(l.text); if (s && s.frame === frame) logs.push(s); } });
  if (!logs.length) throw new Error(`frame ${frame}: no state logged`);
  return { state: logs[logs.length - 1]!, png, sha256: sha(png) };
}

const report: Record<string, unknown> = {
  presentation_id: spec.presentation_id, trace_id: trace.trace_id, camera: spec.camera, fps: tl.fps, frames: tl.durationInFrames,
  timeline: tl.segments.map((s) => ({ id: s.id, kind: s.kind, frames: [Number(s.f0.toFixed(3)), Number(s.f1.toFixed(3))], rate: s.rate,
    source_s: s.kind === "hold" ? [s.t, s.t] : [tl.windowStartS + s.u0 / tl.fps, tl.windowStartS + (s.u0 + (s.f1 - s.f0) * s.rate) / tl.fps] })),
  renderer: "Remotion 4.0.531, chrome-headless-shell, --gl=swangle (SwiftShader, CPU); no motion blur or depth of field",
};

// 1. normal vs replay at the same source time
const pairs = [34, 36, 38, 40].map((k) => ({ k, normal: 30 + k, replay: 95 + 4 * (k - 33) }));
const rows = [];
for (const p of pairs) {
  const a = await still(p.normal, false, 0.5);
  const b = await still(p.replay, false, 0.5);
  const same_t = sourceAtFrame(tl, p.normal).t === sourceAtFrame(tl, p.replay).t;
  rows.push({ source_frame: p.k, normal_frame: p.normal, replay_frame: p.replay, t: a.state.t, source_time_bit_identical: same_t,
    state_identical: JSON.stringify(phys(a.state)) === JSON.stringify(phys(b.state)), png_identical: a.sha256 === b.sha256,
    equals_pure: JSON.stringify(phys(a.state)) === JSON.stringify(pure(p.normal)) });
  console.log("pair", JSON.stringify(rows[rows.length - 1]));
}
report.normal_vs_replay = { rows, pass: rows.every((r) => r.source_time_bit_identical && r.state_identical && r.png_identical && r.equals_pure) };

// 2. the contact pause: same state and pixels throughout, at the reception time
const pause = tl.segments.find((s) => s.id === "contact_pause")!;
const pf = [Math.ceil(pause.f0), Math.round((pause.f0 + pause.f1) / 2), Math.ceil(pause.f1) - 1];
const ps: { frame: number; state: Logged; png: string; sha256: string }[] = [];
for (const f of pf) ps.push({ frame: f, ...(await still(f, false, 0.5)) });
const tc = trace.events.find((e: { id: string }) => e.id === "contact.W-C_reception").t_estimate;
report.contact_pause = { frames: pf, t_contact: tc, t_logged: ps.map((x) => x.state.t), state_identical: ps.every((x) => JSON.stringify(phys(x.state)) === JSON.stringify(phys(ps[0]!.state))),
  png_identical: ps.every((x) => x.sha256 === ps[0]!.sha256), pass: ps.every((x) => x.state.t === r4(tc) && x.sha256 === ps[0]!.sha256) };
console.log("pause", JSON.stringify(report.contact_pause));

// review stills with overlays (full resolution): one pair and the pause
const review = [];
for (const f of [70, 123, pf[1]!, 20, 190]) {
  const r = await still(f, true, 1);
  review.push({ frame: f, segment: sourceAtFrame(tl, f).segment.id, t: r.state.t, png: r.png });
}
report.review_stills = review;

// 3. draft clip
if (!noClip) {
  const comp = await selectComposition({ ...base, id: "shot24-shovel-17", inputProps: { overlays: true } });
  const logs = new Map<number, Logged>();
  const t0 = Date.now();
  await renderMedia({ ...base, composition: comp, codec: "h264", outputLocation: "validation/24-draft.mp4", inputProps: { overlays: true }, scale: 0.5, concurrency: 2,
    onBrowserLog: (l) => { const s = parse(l.text); if (s) logs.set(s.frame, s); } });
  const bad = [...logs.values()].filter((s) => JSON.stringify(phys(s)) !== JSON.stringify(pure(s.frame))).map((s) => s.frame);
  report.draft_clip = { path: "validation/24-draft.mp4", frames: comp.durationInFrames, fps: comp.fps, size_px: [comp.width / 2, comp.height / 2], frames_logged: logs.size,
    frames_differing_from_pure: bad, max_readback_diff: Math.max(...[...logs.values()].map((s) => s.readback_max_diff)), render_seconds: Math.round((Date.now() - t0) / 1000), sha256: sha("validation/24-draft.mp4") };
  console.log("clip", JSON.stringify(report.draft_clip));
} else report.draft_clip = { rendered: false };

await browser.close({ silent: true });
writeFileSync("validation/24-render-checks.json", JSON.stringify(report, null, 1) + "\n");
console.log("wrote validation/24-render-checks.json");
