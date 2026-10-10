// Shot encyclopedia (docs/shot-encyclopedia.md): every move built by the move engine (moves/<id>/move.json,
// scripts/build-move.py) is checked here, so a new move gets these tests by being built.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { analysisFrame, resolveAnalysis, type AnalysisSpec } from "../src/model/analysis.ts";
import { traceEvaluator, type ShotTrace } from "../src/model/trace.ts";

const read = (p: string): string => readFileSync(p, "utf8");
const json = (p: string) => JSON.parse(read(p));
const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");
const MOVES = readdirSync("moves").filter((d) => existsSync(`moves/${d}/move.json`)).map((d) => ({ dir: d, spec: json(`moves/${d}/move.json`) }));
const BUILT = MOVES.filter((m) => !m.spec.legacy && existsSync(`data/traces/${m.dir}.trace.json`));

test("encyclopedia: move files are well formed", () => {
  assert.ok(MOVES.length >= 2);
  for (const { dir, spec } of MOVES) {
    assert.equal(spec.schema, "move-spec/1", dir);
    assert.equal(spec.id, dir);
    assert.ok(["proposed", "accepted"].includes(spec.status), dir);
    assert.ok(spec.trace_id && spec.window_s.length === 2 && spec.puck?.start, dir);
    // an accepted move needs the user's approved reading (CLAUDE.md: no personal approval is ever claimed silently)
    if (spec.status === "accepted") assert.ok(spec.approved_reading, `${dir}: accepted without an approved reading`);
  }
});

test("encyclopedia: contact footprints match the molds, figure scale and puck they were exported from", () => {
  const f = json("data/figures/contact-footprints.json");
  for (const [p, h] of Object.entries(f.inputs_sha256)) assert.equal(sha(p), h, `${p} changed: re-run scripts/shotlib/export_footprints.py`);
  assert.equal(f.puck_thickness_mm, json("validation/12-hardware-report.json").puck.thickness_mm_preview);
});

test("encyclopedia: the engine reproduces the hand-built IKV trace exactly", () => {
  const r = json("validation/moves/invers-kryssar-velodrom-equivalence.json");
  assert.equal(r.identical_within_0_01_mm, true);
  assert.equal(r.max_puck_node_diff_mm, 0);
});

for (const { dir, spec } of BUILT) {
  const trace = json(`data/traces/${dir}.trace.json`);
  const checks = json(`shots/${dir}/checks.json`);

  test(`encyclopedia ${dir}: contact physics, slide check and expectations passed on the saved trace`, () => {
    assert.equal(trace.trace_id, spec.trace_id);
    assert.equal(checks.trace_id, trace.trace_id);
    assert.equal(trace.status, spec.status);
    assert.equal(trace.source.move_file_sha256, sha(`moves/${dir}/move.json`), "move file changed since the build: rebuild");
    assert.equal(trace.engine.contact_footprints_sha256, sha("data/figures/contact-footprints.json"), "footprints changed since the build: rebuild");
    assert.ok(checks.passed);
    assert.ok(checks.sampling_s <= 0.00025 && checks.penetration_tolerance_mm <= 0.1);
    assert.deepEqual(checks.unexpected_penetrations, []);
    assert.deepEqual(checks.approved_exceptions, []);
    assert.equal(checks.unexplained_count, 0);
    assert.ok(checks.slide_check.passed);
    for (const c of checks.slide_check.per_contact) assert.ok(c.peak_impact_mm_s <= checks.slide_check.figure_impact_max_mm_s, c.contact);
    for (const e of checks.expectations) assert.ok(e.passed, e.what);
    for (const c of spec.contacts ?? []) assert.ok(trace.events.some((e: { id: string }) => e.id === `contact.${c.id}`), c.id);
  });

  test(`encyclopedia ${dir}: robust (the outcome holds when the uncertain inputs change)`, (t) => {
    const p = `validation/moves/${dir}-robustness.json`;
    if (!existsSync(p)) return t.skip("no robustness run (scripts/build-move.py --robustness)");
    const r = json(p);
    assert.equal(r.trace_id, trace.trace_id);
    assert.equal(r.robust, true, JSON.stringify(r.rows.filter((x: { outcome_ok: boolean; slide_ok: boolean }) => !(x.outcome_ok && x.slide_ok)).map((x: { variant: string }) => x.variant)));
  });

  test(`encyclopedia ${dir}: src/model/trace.ts plays the trace as the engine computed it`, () => {
    const e = traceEvaluator(trace as ShotTrace);
    const moving = Object.keys(spec.figures).filter((p) => !spec.figures[p].static);
    for (const s of trace.evaluation_samples) {
      const v = e(s.t);
      for (const pid of moving) assert.ok(Math.abs(v.figures[pid]!.theta_deg - s[pid].theta_deg) < 1e-3 && Math.abs(v.figures[pid]!.arc_mm - s[pid].arc_mm) < 1e-3, `${pid} t ${s.t}`);
      assert.ok(Math.abs(v.puck.x_mm - s.puck[0]) < 1e-3 && Math.abs(v.puck.y_mm - s.puck[1]) < 1e-3, `t ${s.t}`);
    }
  });

  if (spec.story) {
    test(`encyclopedia ${dir}: generated video spec resolves, is registered, camera stays smooth`, (t) => {
      const sp = json(`data/presentations/${dir}.analysis.json`) as AnalysisSpec;
      assert.equal(sp.trace_id, trace.trace_id);
      assert.match(read("remotion/encyclopedia-registry.ts"), new RegExp(`id: "${dir}"`));
      const A = resolveAnalysis(sp, trace);
      let prev = analysisFrame(A, 0).camera;
      for (let f = 1; f < A.durationInFrames; f++) {
        const c = analysisFrame(A, f).camera;
        assert.ok(Math.hypot(...(c.positionMm.map((v, k) => v - prev.positionMm[k]!) as [number, number, number])) < 60, `frame ${f}`);
        assert.ok(c.positionMm[2] > 100);
        prev = c;
      }
      const p = `validation/moves/${dir}-video-report.json`;
      if (!existsSync(p)) return t.skip("no render yet (node scripts/analysis-render.ts move:<id>)");
      const r = json(p);
      assert.equal(r.trace.sha256, sha(`data/traces/${dir}.trace.json`), "trace changed since the render");
      assert.equal(r.analysis_spec.sha256, sha(`data/presentations/${dir}.analysis.json`), "video spec changed since the render");
      assert.equal(r.output.frames, A.durationInFrames);
      assert.deepEqual(r.checks.frames_differing_from_pure, []);
    });
  }
}

test("encyclopedia: the index covers the whole NTHF catalogue", () => {
  const idx = json("data/encyclopedia/index.json");
  assert.equal(idx.moves.length, json("data/combinations/nthf-catalogue.json").combinations.length);
  for (const { dir, spec } of MOVES) {
    if (!spec.nthf) continue;
    const row = idx.moves.find((r: { name: string }) => (r.name.split("/")[0] ?? "").trim() === spec.nthf.name);
    assert.ok(row, `${dir} not in the index`);
  }
});
