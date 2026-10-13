// The preview/render workflow (docs/video-workflow.md): frame selection, review stills, scene-cache identity and the
// presentation-only gate. Pure checks (no browser); the rendered evidence is in validation/video-workflow/.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { analysisFrame, resolveAnalysis, type AnalysisSpec } from "../src/model/analysis.ts";
import { shotTimeEvaluator } from "../src/model/shot-pose.ts";
import { framesOf, reviewStills, segmentRange, selectRanges } from "../scripts/video/plan.ts";
import { namespaceId, namespaceInputs, sceneState, stateKey } from "../scripts/video/scene-cache.ts";

const json = (p: string) => JSON.parse(readFileSync(p, "utf8"));
const geometry = json("data/geometry.json");
const TRACE = json("data/traces/hjerpefinte.trace.json");
const SPEC = json("data/presentations/hjerpefinte.analysis.json") as AnalysisSpec;

function keys(spec: AnalysisSpec, trace = TRACE, ns = "ns"): string[] {
  const A = resolveAnalysis(spec, trace);
  const at = shotTimeEvaluator(trace, geometry);
  return Array.from({ length: A.durationInFrames }, (_, f) => {
    const af = analysisFrame(A, f);
    return stateKey(ns, sceneState(at(af.t, f), af.camera));
  });
}
const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x));

test("video workflow: frame ranges and named segments", () => {
  const A = resolveAnalysis(SPEC, TRACE);
  assert.deepEqual(selectRanges(A, null, null), [{ from: 0, to: A.durationInFrames - 1 }]);
  assert.deepEqual(selectRanges(A, "10-20,21-30,40", null), [{ from: 10, to: 30 }, { from: 40, to: 40 }]);
  const r = segmentRange(A, "shot_freeze");
  const seg = A.timeline.segments.find((s) => s.id === "shot_freeze")!;
  assert.equal(r.to - r.from + 1, Math.ceil(seg.f1 - 1e-9) - Math.ceil(seg.f0 - 1e-9));
  for (const f of framesOf([r])) assert.equal(analysisFrame(A, f).segment.id, "shot_freeze");
  // adjacent segments merge into one clip; the frames are exactly the union
  const both = selectRanges(A, null, "shot_in,shot_freeze");
  assert.equal(both.length, 1);
  assert.equal(framesOf(both).length, framesOf([segmentRange(A, "shot_in")]).length + framesOf([r]).length);
  assert.throws(() => selectRanges(A, `0-${A.durationInFrames}`, null));
  assert.throws(() => segmentRange(A, "no_such_segment"));
});

test("video workflow: review stills cover the set-up, every contact, the freezes, camera moves, goal and end", () => {
  const A = resolveAnalysis(SPEC, TRACE);
  const st = reviewStills(A, TRACE.events);
  const why = st.flatMap((s) => s.reasons).join("\n");
  for (const re of [/title card/, /SET-UP/, /just before shot/, /at shot/, /just after shot/, /freeze shot_freeze/, /camera move setup -> beat_feint/, /freeze feint_freeze/, /goal at full speed/, /end card/]) assert.match(why, re);
  for (const s of st) assert.ok(s.frame >= 0 && s.frame < A.durationInFrames);
  // "at shot" is the slow-motion frame nearest the contact
  const at = st.find((s) => s.reasons.some((r) => r.startsWith("at shot")))!;
  const contact = TRACE.events.find((e: { id: string }) => e.id === "contact.shot").t_estimate;
  assert.ok(Math.abs(analysisFrame(A, at.frame).t - contact) < 0.003);
});

// trace v2 (2026-10-12); the v1 pilot had 631 frames, 325 time + camera pairs and 244 states (docs/video-workflow.md)
test("scene cache: the Hjerpefinte video has 807 frames and 311 distinct scene states (406 time + camera pairs)", () => {
  const k = keys(SPEC);
  assert.equal(k.length, 807);
  assert.equal(new Set(k).size, 311);
  const A = resolveAnalysis(SPEC, TRACE);
  const tc = new Set(Array.from({ length: 807 }, (_, f) => { const a = analysisFrame(A, f); return JSON.stringify([a.t, a.camera.positionMm, a.camera.targetMm, a.camera.fovDeg]); }));
  assert.equal(tc.size, 406);
});

test("scene cache: overlay-only changes keep every key; camera and trace changes invalidate exactly the affected frames", () => {
  const base = keys(SPEC);
  // wording, labels, chapter and graphic windows, theme-level overlay choices: not scene inputs
  const text = clone(SPEC);
  for (const c of text.chapters) c.text = c.text.toUpperCase() + " (edited)";
  for (const g of text.graphics) if (g.label) g.label = "EDITED";
  text.graphics = text.graphics.filter((g) => g.type !== "puck_trail");
  assert.deepEqual(keys(text), base);
  // camera: one view moved by 1 mm -> the frames that see that view change, the rest keep their keys
  const cam = clone(SPEC);
  cam.views.beat_shot!.positionMm[2] += 1;
  const kc = keys(cam);
  const changed = kc.filter((k, i) => k !== base[i]).length;
  assert.ok(changed > 100 && changed < 807, `${changed}`);
  assert.equal(kc[0], base[0]);
  // trace: one figure keyframe nudged -> keys change from that time on (the scene drawn is different)
  const tr = clone(TRACE);
  const wc = tr.figures["W-C"];
  wc.theta_keyframes[wc.theta_keyframes.length - 1].theta_deg += 0.5;
  const kt = keys(SPEC, tr);
  assert.ok(kt.some((k, i) => k !== base[i]));
  // the very first frames (before the turn) are unchanged: the key is the pose, not the trace file
  assert.equal(kt[0], base[0]);
});

test("scene cache: the namespace changes with the renderer, model, backend, size and background", () => {
  const b = { browserVersion: "Chromium 141", gl: "swangle", webglRenderer: "SwiftShader", width: 1920, height: 1080, scale: 1, background: "classic:x" };
  const ns = namespaceInputs(b);
  const id = namespaceId(ns);
  assert.equal(namespaceId(namespaceInputs(b)), id);
  for (const k of ["remotion/SceneLayer.tsx", "remotion/ShotScene.tsx", "public/full_static_appearance.glb", "remotion/asset-manifest.json"]) {
    assert.ok(k in ns.files, k);
    assert.notEqual(namespaceId({ ...ns, files: { ...ns.files, [k]: "0".repeat(64) } }), id, k);
  }
  for (const [k, v] of [["gl", "angle"], ["webglRenderer", "ANGLE (NVIDIA)"], ["scale", 0.5], ["background", "nbhf:y"], ["browserVersion", "Chromium 142"]] as const) {
    assert.notEqual(namespaceId(namespaceInputs({ ...b, [k]: v })), id, k);
  }
  assert.notEqual(namespaceId({ ...ns, packages: { ...ns.packages, three: "0.187.0" } }), id);
});

test("presentation-only route: the gate passes today and refuses stale motion, engine or checks", () => {
  const tmp = mkdtempSync(path.join(tmpdir(), "gate-"));
  const files = ["moves/hjerpefinte", "data/traces/hjerpefinte.trace.json", "shots/hjerpefinte/checks.json", "data/presentations/hjerpefinte.analysis.json",
    "scripts/shotlib", "data/geometry.json", "validation/12-hardware-report.json", "validation/16-assembly-poses.json", "data/figures/contact-footprints.json",
    "shots/spjass/checks.json", "remotion/asset-manifest.json", "data/figure-molds.json", "assets/figures/skater_FIN.glb", "assets/figures/goalie_SWE.glb"];
  for (const f of files) { mkdirSync(path.dirname(path.join(tmp, f)), { recursive: true }); cpSync(f, path.join(tmp, f), { recursive: true }); }
  const gate = (): string[] => {
    const r = spawnSync("python3", ["-c", `import sys, json; from pathlib import Path; sys.path.insert(0, "scripts"); from shotlib import identity; identity.REPO = Path(${JSON.stringify(tmp)}); print(json.dumps(identity.presentation_gate("hjerpefinte")))`], { encoding: "utf8" });
    assert.equal(r.status, 0, r.stderr);
    return JSON.parse(r.stdout);
  };
  const edit = (p: string, f: (x: Record<string, any>) => void) => { const x = json(path.join(tmp, p)); f(x); writeFileSync(path.join(tmp, p), JSON.stringify(x, null, 1) + "\n"); };
  try {
    assert.deepEqual(gate(), []);
    // a story edit: the motion is still valid, only the generated presentation is out of date
    edit("moves/hjerpefinte/story.json", (s) => { s.title = "EDITED"; });
    assert.deepEqual(gate(), ["the story changed since the presentation was generated (regenerate: --presentation)"]);
    // a motion edit in move.json: refused until rebuilt
    edit("moves/hjerpefinte/move.json", (m) => { m.window_s[1] += 0.01; });
    assert.ok(gate().includes("the motion in move.json changed since the build"));
    cpSync("moves/hjerpefinte/move.json", path.join(tmp, "moves/hjerpefinte/move.json"));
    // engine code, a model file, failed checks
    writeFileSync(path.join(tmp, "scripts/shotlib/puck.py"), readFileSync("scripts/shotlib/puck.py", "utf8") + "\n# edit\n");
    assert.ok(gate().includes("engine code (scripts/shotlib) changed since the build"));
    cpSync("scripts/shotlib/puck.py", path.join(tmp, "scripts/shotlib/puck.py"));
    edit("shots/hjerpefinte/checks.json", (c) => { c.passed = false; });
    assert.ok(gate().includes("checks did not pass"));
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});
