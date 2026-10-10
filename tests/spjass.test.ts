import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { analysisFrame, resolveAnalysis, windowOpacity, type AnalysisSpec } from "../src/model/analysis.ts";
import { traceEvaluator, type ShotTrace } from "../src/model/trace.ts";

const read = (p: string): string => readFileSync(p, "utf8");
const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");
const compositionSha = (files: string[]): string => createHash("sha256").update(files.map((f) => `${f}:${sha(f)}`).join("\n")).digest("hex");
const trace = JSON.parse(read("data/traces/spjass.trace.json"));
const checks = JSON.parse(read("shots/spjass/checks.json"));
const obs = JSON.parse(read("shots/spjass/observations.json"));
const spec = JSON.parse(read("data/presentations/spjass.analysis.json")) as AnalysisSpec;
const A = resolveAnalysis(spec, trace);
const N = A.durationInFrames;
const ev = (id: string): { t_estimate: number; [k: string]: unknown } => trace.events.find((e: { id: string }) => e.id === id);

test("spjass: the TikTok source is preserved and the camera fit is recorded", () => {
  assert.equal(sha(obs.source.path), obs.source.sha256, "references/shots/spjass-tiktok.mp4 changed");
  const idx = JSON.parse(read("references/index.json"));
  assert.ok(idx.sources.some((s: { local_path: string; sha256: string }) => s.local_path === obs.source.path && s.sha256 === obs.source.sha256), "listed in references/index.json");
  assert.ok(obs.camera_take1.rms_px < 6 && obs.camera_take1.leave_one_out_rms_px < 12);
});

test("spjass: contact physics - no overlap anywhere, every puck motion change has a named contact", () => {
  assert.equal(checks.trace_id, trace.trace_id);
  assert.ok(checks.sampling_s <= 0.00025 && checks.penetration_tolerance_mm <= 0.1);
  assert.deepEqual(checks.unexpected_penetrations, []);
  assert.deepEqual(checks.approved_exceptions, []);
  assert.equal(checks.unexplained_count, 0, "velocity changes outside contacts and the fitted ice friction");
  // the contacts are exactly: blade flick, blade shot, back of the net
  assert.deepEqual(checks.contacts.map((c: { obstacle: string }) => c.obstacle), ["W-C:stick/blade", "W-C:stick/blade", "goal_net"]);
  assert.equal(ev("contact.flick").part, "W-C:stick/blade");
  assert.equal(ev("contact.shot").part, "W-C:stick/blade");
  // pushes stay within a plausible blade-puck friction cone (impulse vs model contact normal)
  assert.ok(Math.abs(checks.flick.impulse_minus_normal_deg) <= 20 && Math.abs(checks.shot.impulse_minus_normal_deg) <= 20);
  // into the goal, inside the posts
  const g = checks.goal_line;
  assert.ok(g.crossing_y_mm > g.inside_mouth_window_y_mm[0] && g.crossing_y_mm < g.inside_mouth_window_y_mm[1]);
});

test("spjass: the trace follows the TikTok where it is sharp", () => {
  for (const r of trace.puck.observations_vs_trace_mm) {
    if (r.frame >= 118 && r.frame <= 131) assert.ok(r.residual_mm <= 1.0, `frame ${r.frame}: ${r.residual_mm} mm`);
  }
  // order of events and the observed timing
  const order = ["turn.onset", "contact.flick", "spin.onset", "contact.shot", "goal_entry", "goal_net"].map((id) => ev(id).t_estimate);
  for (let i = 1; i < order.length; i++) assert.ok(order[i]! > order[i - 1]!);
  assert.ok(Math.abs(ev("contact.flick").t_estimate * 30 - 124) < 0.5, "flick at frame 124");
  assert.ok(ev("contact.shot").t_estimate * 30 > 131 && ev("contact.shot").t_estimate * 30 < 132, "shot between frames 131 and 132");
  // W-C turns counter-clockwise for the flick, then spins clockwise for the shot (unwrapped theta)
  const ev_ = traceEvaluator(trace as ShotTrace);
  const th = (t: number): number => ev_(t).figures["W-C"]!.theta_deg;
  assert.ok(th(ev("contact.flick").t_estimate) > th(ev("turn.onset").t_estimate) + 45);
  assert.ok(th(ev("contact.shot").t_estimate) < th(ev("spin.onset").t_estimate) - 250);
});

test("spjass: the TypeScript evaluator reproduces the script's samples", () => {
  const e = traceEvaluator(trace as ShotTrace);
  for (const s of trace.evaluation_samples) {
    const v = e(s.t);
    assert.ok(Math.abs(v.figures["W-C"]!.arc_mm - s["W-C"].arc_mm) < 1e-3 && Math.abs(v.figures["W-C"]!.theta_deg - s["W-C"].theta_deg) < 1e-3, `t ${s.t}`);
    assert.ok(Math.abs(v.puck.x_mm - s.puck[0]) < 1e-3 && Math.abs(v.puck.y_mm - s.puck[1]) < 1e-3, `t ${s.t}`);
  }
});

test("spjass analysis: 1080p, 20-25 s, readable chapters with a still camera, smooth camera above the scene", () => {
  assert.equal(spec.trace_id, trace.trace_id);
  assert.equal(spec.width, 1920);
  assert.equal(spec.height, 1080);
  assert.ok(N / spec.fps >= 20 && N / spec.fps <= 25, `${N / spec.fps} s`);
  for (const c of A.chapters) {
    let still = 0;
    for (let f = Math.ceil(c.t0 * spec.fps); f < c.t1 * spec.fps; f++) if (analysisFrame(A, f).camera.mode === "hold" && windowOpacity(c, f / spec.fps) === 1) still++;
    assert.ok(still / spec.fps >= 3.5, `${c.item.id}: ${still / spec.fps} s still`);
    assert.ok(c.item.text.split(/\s+/).length / (still / spec.fps) <= 4, `${c.item.id}: reading pace`);
  }
  let prev = analysisFrame(A, 0).camera;
  for (let f = 1; f < N; f++) {
    const c = analysisFrame(A, f).camera;
    assert.ok(Math.hypot(...(c.positionMm.map((v, k) => v - prev.positionMm[k]!) as [number, number, number])) < 60, `frame ${f}`);
    assert.ok(c.positionMm[2] > 100, `frame ${f}: camera low`);
    prev = c;
  }
  // every explanation, slow motion and replay is shot from a still camera
  for (const s of A.timeline.segments.filter((x) => ["setup_freeze", "turn_in", "flick_freeze", "spin_in", "strike_freeze", "shot_out", "goal_freeze", "replay"].includes(x.id))) {
    for (let f = Math.ceil(s.f0); f < s.f1; f++) assert.equal(analysisFrame(A, f).camera.mode, "hold", `${s.id} frame ${f}`);
  }
  // freezes sit on the trace events
  const seg = (id: string) => A.timeline.segments.find((s) => s.id === id)!;
  assert.equal(analysisFrame(A, Math.ceil(seg("flick_freeze").f0) + 3).t, ev("contact.flick").t_estimate);
  assert.equal(analysisFrame(A, Math.ceil(seg("strike_freeze").f0) + 3).t, ev("contact.shot").t_estimate);
});

test("spjass analysis: the puck is visible in every explanation (ray cast against the figure meshes)", (t) => {
  const p = "validation/analysis-spjass-occlusion.json";
  if (!existsSync(p)) return t.skip("no occlusion report (npm run video:analysis-spjass)");
  const r = JSON.parse(read(p));
  for (const id of ["setup_freeze", "turn_in", "flick_freeze", "spin_in", "strike_freeze", "shot_out", "goal_freeze", "replay"]) {
    assert.equal(r[id].frames_puck_mostly_hidden, 0, id);
  }
});

test("spjass analysis: composition registered, proposed trace allowed explicitly, export report matches", (t) => {
  const root = read("remotion/Root.tsx");
  assert.match(root, /id="analysis-spjass"/);
  assert.match(read("remotion/SpjassAnalysis.tsx"), /allowProposed: true/);
  const p = "validation/analysis-spjass-report.json";
  if (!existsSync(p)) return t.skip("no export yet (npm run video:analysis-spjass)");
  const r = JSON.parse(read(p));
  assert.equal(r.trace.sha256, sha("data/traces/spjass.trace.json"), "trace changed since the export: re-render");
  assert.equal(r.analysis_spec.sha256, sha("data/presentations/spjass.analysis.json"), "analysis spec changed since the export: re-render");
  assert.equal(r.analysis_spec.composition_sha256, compositionSha(r.analysis_spec.composition_files), "composition changed since the export: re-render");
  assert.equal(r.output.width, 1920);
  assert.equal(r.output.height, 1080);
  assert.equal(r.output.frames, N);
  assert.ok(r.output.below_25_mb && r.output.bytes < 25e6);
  assert.deepEqual(r.checks.frames_differing_from_pure, []);
  assert.equal(r.checks.frames_logged, N);
  assert.equal(r.checks.camera_frames_logged, N);
  if (existsSync(r.output.path)) assert.equal(sha(r.output.path), r.output.sha256);
});
