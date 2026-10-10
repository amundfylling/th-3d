import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { analysisFrame, resolveAnalysis, windowOpacity, type AnalysisSpec } from "../src/model/analysis.ts";
import { traceEvaluator, type ShotTrace } from "../src/model/trace.ts";

const read = (p: string): string => readFileSync(p, "utf8");
const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");
const compositionSha = (files: string[]): string => createHash("sha256").update(files.map((f) => `${f}:${sha(f)}`).join("\n")).digest("hex");
const trace = JSON.parse(read("data/traces/invers-kryssar-velodrom.trace.json"));
const checks = JSON.parse(read("shots/invers-kryssar-velodrom/checks.json"));
const spec = JSON.parse(read("data/presentations/invers-kryssar-velodrom.analysis.json")) as AnalysisSpec;
const A = resolveAnalysis(spec, trace);
const N = A.durationInFrames;
const ev = (id: string): { t_estimate: number; [k: string]: unknown } => trace.events.find((e: { id: string }) => e.id === id);

test("invers kryssar med velodrom: NTHF source indexed, approved sketch kept", () => {
  const idx = JSON.parse(read("references/index.json"));
  const p = "references/combinations/puck-no-invers-kryssar-med-velodrom.html";
  const s = idx.sources.find((x: { local_path: string }) => x.local_path === p);
  assert.ok(s && sha(p) === s.sha256);
  assert.match(read(p), /passes along the boards behind the goal to the right wing, who shoots directly into the goal/);
  assert.ok(existsSync("validation/ikv-sketch.png"));
});

test("invers kryssar med velodrom: contact physics - no overlap, every motion change named", () => {
  assert.equal(checks.trace_id, trace.trace_id);
  assert.equal(trace.status, "proposed");
  assert.ok(checks.sampling_s <= 0.00025 && checks.penetration_tolerance_mm <= 0.1);
  assert.deepEqual(checks.unexpected_penetrations, []);
  assert.deepEqual(checks.approved_exceptions, []);
  assert.equal(checks.unexplained_count, 0);
  // right wing pushes the pass, left wing catches it softly, it slides on the board, the left wing pushes it into the
  // corner (pressed against the board), the boards carry it round, the right wing shoots, the net stops it
  const seq = checks.contact_sequence.filter((c: string, i: number, a: string[]) => i === 0 || c !== a[i - 1]);
  assert.deepEqual(seq, ["W-RW:stick/blade", "W-LW:stick/blade", "boards", "W-LW:stick/blade", "boards", "W-RW:stick/blade", "goal_net"]);
  // the velodrome really goes round behind the goal cage
  assert.ok(checks.velodrome.behind_goal_min_x_mm > 338 + 12.7, "behind the cage");
  const g = checks.goal_line;
  assert.ok(g.crossing_y_mm > g.inside_mouth_window_y_mm[0] && g.crossing_y_mm < g.inside_mouth_window_y_mm[1], "inside the posts");
});

test("invers kryssar med velodrom: slide or bounce (CLAUDE.md, user rule 2026-10-06) - no flick, glancing board contacts", () => {
  const sc = checks.slide_check;
  assert.equal(sc.figure_impact_max_mm_s, 500);
  assert.equal(sc.wall_impact_max_mm_s, 300);
  assert.ok(sc.passed);
  assert.deepEqual(sc.figure_violations, []);
  assert.deepEqual(sc.wall_violations, []);
  for (const c of sc.per_contact) assert.ok(c.peak_impact_mm_s <= sc.figure_impact_max_mm_s, c.contact);
  assert.ok(sc.peak_board_impact_mm_s <= sc.wall_impact_max_mm_s && sc.peak_post_impact_mm_s <= sc.wall_impact_max_mm_s);
  // the left wing's pass is a sustained forward push (many small touches), not one strike
  const push = sc.per_contact.find((c: { contact: string }) => c.contact === "lw_push");
  assert.ok(push.touches > 50 && push.peak_impact_mm_s < 150 && push.t[1] - push.t[0] > 0.15);
  const e = ev("contact.lw_push");
  assert.ok(Math.abs((e.release_direction_deg as number) + 90) < 3, "released along the end board");
  assert.ok((e.release_speed_mm_s as number) < 1600);
  // the left wing faces the way it pushes: mid-curve its heading follows the slot (no automatic tangent rotation: designed)
  assert.ok(Math.abs((ev("lw_push.corner").heading_deg as number) + 45) < 5);
});

test("invers kryssar med velodrom: the reading - cross pass to the left wing, shot by the right wing", () => {
  const e = traceEvaluator(trace as ShotTrace);
  const pAt = (t: number): [number, number] => { const s = e(t); return [s.puck.x_mm, s.puck.y_mm]; };
  // the cross pass goes from the right wing's side (-y) to the left wing's side (+y)
  assert.ok(pAt(ev("pass.release").t_estimate)[1] < -100 && pAt(ev("contact.lw_catch").t_estimate)[1] > 100);
  // the shot is taken from the right wing's board side and enters the goal
  assert.ok(pAt(ev("contact.shot").t_estimate)[1] < -150);
  const order = ["pass.start", "pass.release", "contact.lw_catch", "board.after_catch", "contact.lw_push", "lw_push.corner", "velodrome.start", "velodrome.end", "contact.shot", "goal_entry", "goal_net"].map((id) => ev(id).t_estimate);
  for (let i = 1; i < order.length; i++) assert.ok(order[i]! > order[i - 1]!);
  for (const s of trace.evaluation_samples) {
    const v = e(s.t);
    for (const pid of ["W-RW", "W-LW"]) assert.ok(Math.abs(v.figures[pid]!.theta_deg - s[pid].theta_deg) < 1e-3 && Math.abs(v.figures[pid]!.arc_mm - s[pid].arc_mm) < 1e-3, `t ${s.t}`);
    assert.ok(Math.abs(v.puck.x_mm - s.puck[0]) < 1e-3 && Math.abs(v.puck.y_mm - s.puck[1]) < 1e-3, `t ${s.t}`);
  }
});

test("invers kryssar med velodrom analysis: 1080p, readable chapters, smooth camera, puck always visible", () => {
  assert.equal(spec.trace_id, trace.trace_id);
  assert.ok(N / spec.fps >= 20 && N / spec.fps <= 30, `${N / spec.fps} s`);
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
  const occ = JSON.parse(read("validation/analysis-ikv-occlusion.json"));
  for (const [id, r] of Object.entries(occ) as [string, { frames_puck_mostly_hidden: number }][]) assert.equal(r.frames_puck_mostly_hidden, 0, id);
});

test("invers kryssar med velodrom analysis: composition registered, export report matches", (t) => {
  assert.match(read("remotion/Root.tsx"), /id="analysis-ikv"/);
  assert.match(read("remotion/IkvAnalysis.tsx"), /allowProposed: true/);
  const p = "validation/analysis-ikv-report.json";
  if (!existsSync(p)) return t.skip("no export yet (npm run video:analysis-ikv)");
  const r = JSON.parse(read(p));
  assert.equal(r.trace.sha256, sha("data/traces/invers-kryssar-velodrom.trace.json"), "trace changed since the export: re-render");
  assert.equal(r.analysis_spec.sha256, sha("data/presentations/invers-kryssar-velodrom.analysis.json"), "analysis spec changed since the export: re-render");
  assert.equal(r.analysis_spec.composition_sha256, compositionSha(r.analysis_spec.composition_files), "composition changed since the export: re-render");
  assert.equal(r.output.frames, N);
  assert.ok(r.output.below_25_mb && r.output.width === 1920 && r.output.height === 1080);
  assert.deepEqual(r.checks.frames_differing_from_pure, []);
  assert.equal(r.checks.frames_logged, N);
  if (existsSync(r.output.path)) assert.equal(sha(r.output.path), r.output.sha256);
});
