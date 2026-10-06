import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { analysisFrame, resolveAnalysis, windowOpacity, type AnalysisSpec } from "../src/model/analysis.ts";
import { traceEvaluator, type ShotTrace } from "../src/model/trace.ts";

const read = (p: string): string => readFileSync(p, "utf8");
const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");
const compositionSha = (files: string[]): string => createHash("sha256").update(files.map((f) => `${f}:${sha(f)}`).join("\n")).digest("hex");
const trace = JSON.parse(read("data/traces/defence-left-wing.trace.json"));
const checks = JSON.parse(read("shots/defence-left-wing/checks.json"));
const spec = JSON.parse(read("data/presentations/defence-left-wing.analysis.json")) as AnalysisSpec;
const A = resolveAnalysis(spec, trace);
const N = A.durationInFrames;
type Lane = { blocked_by: string | null; open: boolean };
const ev = (id: string): { t_estimate: number; lanes?: Record<string, Lane>; [k: string]: unknown } => trace.events.find((e: { id: string }) => e.id === id);

test("defence vs the left wing: sources indexed (the user's TikTok, the centrifuge lesson)", () => {
  const idx = JSON.parse(read("references/index.json"));
  for (const p of ["references/shots/defence-vs-left-wing-tiktok.mp4", "references/combinations/bordshockeyskolan-lektion-3-centrifugen.html"]) {
    const s = idx.sources.find((x: { local_path: string }) => x.local_path === p);
    assert.ok(s && sha(p) === s.sha256, p);
  }
});

test("defence vs the left wing: contact physics - the puck rests on the left wing's blade, nothing overlaps", () => {
  assert.equal(checks.trace_id, trace.trace_id);
  assert.equal(trace.status, "proposed");
  assert.ok(checks.sampling_s <= 0.00025 && checks.penetration_tolerance_mm <= 0.1);
  assert.deepEqual(checks.unexpected_penetrations, []);
  assert.deepEqual(checks.approved_exceptions, []);
  assert.equal(checks.unexplained_count, 0);
  assert.ok(checks.slide_check.passed);
  const e = traceEvaluator(trace as ShotTrace);
  const p0 = e(0), p1 = e(6);
  assert.deepEqual([p0.puck.x_mm, p0.puck.y_mm], [p1.puck.x_mm, p1.puck.y_mm]);
  const lw = checks.min_clearance_by_obstacle.find((r: { obstacle: string }) => r.obstacle === "W-LW");
  assert.ok(lw.min_clearance_mm >= 0 && lw.min_clearance_mm < 0.2, "puck touches the left wing's blade");
});

test("defence vs the left wing: the concept - which lane each set-up closes", () => {
  const L = (id: string) => ev(id).lanes!;
  // without a defence the straight shot goes in
  assert.equal(L("setup.neutral").straight_shot!.blocked_by, null);
  // passive (the box): the defender closes the straight shot, the pass is open, the centred goalie meets the centre's shot
  for (const id of ["passive.set", "mix.passive_1", "mix.passive_2"]) {
    assert.equal(L(id).straight_shot!.blocked_by, "E-RD", id);
    assert.equal(L(id).centrifuge_pass!.blocked_by, null, id);
    assert.equal(L(id).centre_shot!.blocked_by, "E-G", id);
  }
  // active: the goalie closes the straight shot at the near post, the defender cuts the centrifuge pass
  for (const id of ["active.set", "mix.active"]) {
    assert.equal(L(id).straight_shot!.blocked_by, "E-G", id);
    assert.equal(L(id).centrifuge_pass!.blocked_by, "E-RD", id);
  }
  // the goalie stands at the near post (+y, the left wing's side) when active, in the middle when passive
  const gy = (id: string) => (ev(id)["E-G_pivot_mm"] as number[])[1]!;
  assert.ok(gy("active.set") > 25 && Math.abs(gy("passive.set")) < 5);
  // when active the goalie turns its BACK to the puck (user, 2026-10-06): it faces away from the puck, square when passive
  const puck = trace.puck.nodes[0];
  for (const id of ["active.set", "mix.active"]) {
    const g = ev(id)["E-G_pivot_mm"] as number[], h = ev(id)["E-G_heading_deg"] as number;
    const away = (Math.atan2(g[1]! - puck.y_mm, g[0]! - puck.x_mm) * 180) / Math.PI;
    assert.ok(Math.abs(((h - away + 540) % 360) - 180) < 2, id);
  }
  for (const id of ["passive.set", "mix.passive_1", "mix.passive_2"]) assert.equal(ev(id)["E-G_heading_deg"], 180, id);
  // the mix really switches
  const setups = trace.events.filter((e: { setup?: string }) => e.setup).map((e: { setup: string }) => e.setup);
  assert.deepEqual(setups, ["neutral", "passive", "active", "passive", "active", "passive"]);
});

test("defence vs the left wing video: 1080p, readable chapters, still camera, puck always visible", () => {
  assert.equal(spec.trace_id, trace.trace_id);
  assert.ok(N / spec.fps >= 25 && N / spec.fps <= 45, `${N / spec.fps} s`);
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
  // every lane graphic refers to a lane recorded on its event
  for (const g of spec.graphics.filter((x) => x.type === "lane")) assert.ok(ev(g.event!).lanes?.[g.lane!], g.id);
  const occ = JSON.parse(read("validation/analysis-defence-lw-occlusion.json"));
  for (const [id, r] of Object.entries(occ) as [string, { frames_puck_mostly_hidden: number }][]) assert.equal(r.frames_puck_mostly_hidden, 0, id);
});

test("defence vs the left wing video: composition registered, export report matches", (t) => {
  assert.match(read("remotion/Root.tsx"), /id="analysis-defence-lw"/);
  assert.match(read("remotion/DefenceAnalysis.tsx"), /allowProposed: true/);
  const p = "validation/analysis-defence-lw-report.json";
  if (!existsSync(p)) return t.skip("no export yet (npm run video:analysis-defence-lw)");
  const r = JSON.parse(read(p));
  assert.equal(r.trace.sha256, sha("data/traces/defence-left-wing.trace.json"), "trace changed since the export: re-render");
  assert.equal(r.analysis_spec.sha256, sha("data/presentations/defence-left-wing.analysis.json"), "analysis spec changed since the export: re-render");
  assert.equal(r.analysis_spec.composition_sha256, compositionSha(r.analysis_spec.composition_files), "composition changed since the export: re-render");
  assert.equal(r.output.frames, N);
  assert.ok(r.output.below_25_mb && r.output.width === 1920 && r.output.height === 1080);
  assert.deepEqual(r.checks.frames_differing_from_pure, []);
  assert.equal(r.checks.frames_logged, N);
  if (existsSync(r.output.path)) assert.equal(sha(r.output.path), r.output.sha256);
});
