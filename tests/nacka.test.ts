import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { analysisFrame, resolveAnalysis, windowOpacity, type AnalysisSpec } from "../src/model/analysis.ts";
import { traceEvaluator, type ShotTrace } from "../src/model/trace.ts";

const read = (p: string): string => readFileSync(p, "utf8");
const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");
const compositionSha = (files: string[]): string => createHash("sha256").update(files.map((f) => `${f}:${sha(f)}`).join("\n")).digest("hex");
const trace = JSON.parse(read("data/traces/nacka.trace.json"));
const checks = JSON.parse(read("shots/nacka/checks.json"));
const spec = JSON.parse(read("data/presentations/nacka.analysis.json")) as AnalysisSpec;
const A = resolveAnalysis(spec, trace);
const N = A.durationInFrames;
const ev = (id: string): { t_estimate: number; [k: string]: unknown } => trace.events.find((e: { id: string }) => e.id === id);

test("näcka: the NTHF sources are preserved and indexed", () => {
  const idx = JSON.parse(read("references/index.json"));
  for (const p of ["references/combinations/puck-no-nacka.html", "references/combinations/trick-nacka.png", "references/combinations/puck-no-spjass.html", "references/combinations/trick-spjass.png"]) {
    const s = idx.sources.find((x: { local_path: string }) => x.local_path === p);
    assert.ok(s, `${p} indexed`);
    assert.equal(sha(p), s.sha256, `${p} changed`);
  }
  assert.match(read("references/combinations/puck-no-nacka.html"), /passes with the heel a few centimeters out to the right, and shoots with the blade into the right corner/);
});

test("näcka: contact physics - no overlap anywhere, every puck motion change has a named contact", () => {
  assert.equal(checks.trace_id, trace.trace_id);
  assert.equal(trace.status, "proposed");
  assert.ok(checks.sampling_s <= 0.00025 && checks.penetration_tolerance_mm <= 0.1);
  assert.deepEqual(checks.unexpected_penetrations, []);
  assert.deepEqual(checks.approved_exceptions, []);
  assert.equal(checks.unexplained_count, 0);
  // the heel (skate) passes, the blade shoots, the net stops the puck - nothing else touches it
  const kinds = [...new Set(checks.contacts.map((c: { obstacle: string }) => c.obstacle))];
  assert.deepEqual(kinds, ["W-C:skate/body", "W-C:stick/blade", "goal_net"]);
  const firstBlade = checks.contacts.findIndex((c: { obstacle: string }) => c.obstacle === "W-C:stick/blade");
  assert.ok(checks.contacts.slice(0, firstBlade).every((c: { obstacle: string }) => c.obstacle === "W-C:skate/body"), "heel pass before the shot");
});

test("näcka: matches the NTHF description - pass a few cm to the right, shot into the right corner", () => {
  const c = trace.comparison_with_illustration;
  assert.ok(c.pass_length_mm >= 25 && c.pass_length_mm <= 60, `pass ${c.pass_length_mm} mm`);
  assert.ok(c.pass_mm[1] < -15, "pass to the right (-y, seen from behind the centre)");
  const g = checks.goal_line;
  assert.ok(g.crossing_y_mm < 0 && g.crossing_y_mm > g.inside_mouth_window_y_mm[0], "right corner, inside the post");
  // W-C turns clockwise for the heel pass, then back counter-clockwise for the shot
  const e = traceEvaluator(trace as ShotTrace);
  const th = (t: number): number => e(t).figures["W-C"]!.theta_deg;
  assert.ok(th(ev("turn_back.onset").t_estimate) < th(ev("turn.onset").t_estimate) - 20);
  assert.ok(th(ev("contact.shot").t_estimate) > th(ev("turn_back.onset").t_estimate) + 20);
  for (const s of trace.evaluation_samples) {
    const v = e(s.t);
    assert.ok(Math.abs(v.figures["W-C"]!.arc_mm - s["W-C"].arc_mm) < 1e-3 && Math.abs(v.puck.x_mm - s.puck[0]) < 1e-3 && Math.abs(v.puck.y_mm - s.puck[1]) < 1e-3, `t ${s.t}`);
  }
});

test("näcka analysis: 1080p, 20-25 s, readable chapters with a still camera, smooth camera, puck visible", () => {
  assert.equal(spec.trace_id, trace.trace_id);
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
    assert.ok(c.positionMm[2] > 100);
    prev = c;
  }
  const p = "validation/analysis-nacka-occlusion.json";
  if (existsSync(p)) {
    const r = JSON.parse(read(p));
    for (const id of ["setup_freeze", "pass_in", "pass_freeze", "slide_in", "strike_freeze", "shot_out", "goal_freeze", "replay"]) assert.equal(r[id].frames_puck_mostly_hidden, 0, id);
  }
});

test("näcka analysis: composition registered, export report matches", (t) => {
  assert.match(read("remotion/Root.tsx"), /id="analysis-nacka"/);
  assert.match(read("remotion/NackaAnalysis.tsx"), /allowProposed: true/);
  const p = "validation/analysis-nacka-report.json";
  if (!existsSync(p)) return t.skip("no export yet (npm run video:analysis-nacka)");
  const r = JSON.parse(read(p));
  assert.equal(r.trace.sha256, sha("data/traces/nacka.trace.json"), "trace changed since the export: re-render");
  assert.equal(r.analysis_spec.sha256, sha("data/presentations/nacka.analysis.json"), "analysis spec changed since the export: re-render");
  assert.equal(r.analysis_spec.composition_sha256, compositionSha(r.analysis_spec.composition_files), "composition changed since the export: re-render");
  assert.equal(r.output.frames, N);
  assert.ok(r.output.below_25_mb && r.output.width === 1920 && r.output.height === 1080);
  assert.deepEqual(r.checks.frames_differing_from_pure, []);
  assert.equal(r.checks.frames_logged, N);
  if (existsSync(r.output.path)) assert.equal(sha(r.output.path), r.output.sha256);
});
