import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { analysisFrame, badgeFor, resolveAnalysis, resolveTime, windowOpacity, type AnalysisSpec } from "../src/model/analysis.ts";
import { cameraAt, ease } from "../src/model/camera-track.ts";
import { shotTimeEvaluator } from "../src/model/shot-pose.ts";

const read = (p: string): string => readFileSync(p, "utf8");
const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");
const trace = JSON.parse(read("data/traces/shovel-17.trace.json"));
const geometry = JSON.parse(read("data/geometry.json"));
const spec = JSON.parse(read("data/presentations/shovel-17.analysis.json")) as AnalysisSpec;
const A = resolveAnalysis(spec, trace);
const N = A.durationInFrames;
const ev = (id: string): number => trace.events.find((e: { id: string }) => e.id === id).t_estimate;
const seg = (id: string) => A.timeline.segments.find((s) => s.id === id)!;
// output frames inside a segment (segment boundaries may be fractional frames)
const framesOf = (id: string): number[] => { const s = seg(id), a = Math.ceil(s.f0), b = Math.ceil(s.f1); return Array.from({ length: b - a }, (_, k) => a + k); };

test("analysis: 1080p 16:9, 20-25 s, built on the accepted trace", () => {
  assert.equal(spec.trace_id, trace.trace_id);
  assert.equal(trace.status, "accepted");
  assert.equal(spec.width, 1920);
  assert.equal(spec.height, 1080);
  const seconds = N / spec.fps;
  assert.ok(seconds >= 20 && seconds <= 25, `${seconds} s`);
  assert.equal(seg(spec.segments[0]!.id).f0, 0);
  for (let i = 1; i < A.timeline.segments.length; i++) assert.equal(A.timeline.segments[i]!.f0, A.timeline.segments[i - 1]!.f1, "segments are contiguous");
});

test("analysis: every frame is a pure function of the frame number (any order, repeated)", () => {
  const forward = Array.from({ length: N }, (_, f) => JSON.stringify(analysisFrame(A, f)));
  const order = Array.from({ length: N }, (_, f) => (f * 389) % N); // 389 is coprime with N: a scrambled permutation
  for (const f of order) assert.equal(JSON.stringify(analysisFrame(A, f)), forward[f], `frame ${f}`);
  const again = resolveAnalysis(spec, trace);
  assert.equal(JSON.stringify(analysisFrame(again, 321)), forward[321]);
});

test("analysis: the story order and the freezes sit on the trace events", () => {
  const order = A.timeline.segments.map((s) => s.id);
  const at = (id: string): number => order.indexOf(id);
  assert.ok(at("full") < at("pass_freeze") && at("pass_freeze") < at("reception_freeze") && at("reception_freeze") < at("carry") && at("carry") < at("replay"));
  const tOf = (id: string): number[] => framesOf(id).map((f) => analysisFrame(A, f).t);
  // full speed covers the whole shot, from the window start into the net
  assert.equal(badgeFor(seg("full"), spec, A.timeline.outFps), "FULL SPEED");
  assert.ok(tOf("full")[0]! <= ev("pass.release") - 1 && tOf("full").at(-1)! >= ev("goal_entry"));
  // a freeze holds the entire physical scene at one source time
  for (const [id, t] of [["pass_freeze", ev("pass.release")], ["reception_freeze", ev("contact.W-C_reception")], ["release_freeze", ev("shot.separation")]] as const) {
    for (const x of tOf(id)) assert.equal(x, t, `${id} holds at the event`);
    assert.equal(badgeFor(seg(id), spec, A.timeline.outFps), "FREEZE");
  }
  // the shovel is replayed in slow motion from the reception contact to the separation
  const carry = tOf("carry");
  assert.ok(carry[0]! >= ev("contact.W-C_reception") && carry[0]! - ev("contact.W-C_reception") < 0.002);
  assert.ok(seg("carry").rate * A.timeline.outFps / spec.fps <= 0.1);
  assert.ok(carry.at(-1)! < ev("shot.separation"));
  // the rewind runs backwards; every other play segment forwards
  const rw = tOf("rewind");
  for (let k = 1; k < rw.length; k++) assert.ok(rw[k]! < rw[k - 1]!);
  for (const s of A.timeline.segments.filter((x) => x.kind === "play")) {
    const ts = tOf(s.id);
    for (let k = 1; k < ts.length; k++) assert.ok(ts[k]! > ts[k - 1]!, `${s.id} forwards`);
  }
  // every source time shown lies inside the accepted trace window
  for (let f = 0; f < N; f++) {
    const t = analysisFrame(A, f).t;
    assert.ok(t >= trace.time_base.window_s[0] - 1e-9 && t <= trace.time_base.window_s[1] + 1e-9, `frame ${f}`);
  }
});

test("analysis: the camera moves during freezes (scene still) and stands still while the viewer reads", () => {
  // camera moves happen while the scene is frozen (hold), so a freeze holds the whole physical scene
  for (const id of ["to_reception", "to_shovel"]) {
    const fs = framesOf(id);
    assert.equal(new Set(fs.map((f) => analysisFrame(A, f).t)).size, 1, `${id}: scene frozen`);
    assert.ok(fs.some((f) => analysisFrame(A, f).camera.mode === "move"), `${id}: camera moves`);
  }
  // every explained moment and every slow-motion segment is shot from a stationary camera
  for (const id of ["pass_in", "pass_freeze", "reception_in", "reception_freeze", "shovel_read", "carry", "release_freeze", "shot_out", "goal_freeze", "replay"]) {
    for (const f of framesOf(id)) assert.equal(analysisFrame(A, f).camera.mode, "hold", `${id} frame ${f}`);
  }
  // each chapter caption is fully shown for at least 3.5 s with the camera still, at no more than 4 words per second
  for (const c of A.chapters) {
    let still = 0;
    for (let f = Math.ceil(c.t0 * spec.fps); f < c.t1 * spec.fps; f++) if (analysisFrame(A, f).camera.mode === "hold" && windowOpacity(c, f / spec.fps) === 1) still++;
    const words = c.item.text.split(/\s+/).length;
    assert.ok(still / spec.fps >= 3.5, `${c.item.id}: ${still / spec.fps} s still`);
    assert.ok(words / (still / spec.fps) <= 4, `${c.item.id}: ${words} words in ${still / spec.fps} s`);
  }
});

test("analysis: camera moves are smooth, never cut, and stay above every object in the scene", () => {
  let prev = analysisFrame(A, 0).camera;
  let minZ = Infinity;
  for (let f = 1; f < N; f++) {
    const c = analysisFrame(A, f).camera;
    const step = Math.hypot(...c.positionMm.map((v, k) => v - prev.positionMm[k]!) as [number, number, number]);
    assert.ok(step < 60, `frame ${f}: camera jumps ${step.toFixed(1)} mm`);
    assert.ok(Math.abs(c.fovDeg - prev.fovDeg) < 1, `frame ${f}: fov jump`);
    minZ = Math.min(minZ, c.positionMm[2]);
    prev = c;
  }
  // tallest objects: end screens 70 mm, figures about 54 mm, boards 30 mm (data/geometry.json); near plane 4 mm
  const tallest = Math.max(70, ...geometry.figure_assets.map((a: { figure_height: { value: number } }) => a.figure_height.value));
  assert.ok(minZ > tallest + 30, `lowest camera ${minZ} mm`);
  // eased: zero speed at the ends of a move
  assert.equal(ease(0), 0);
  assert.equal(ease(1), 1);
  const v = { a: { positionMm: [0, -100, 100] as [number, number, number], targetMm: [0, 0, 0] as [number, number, number], fovDeg: 30 }, b: { positionMm: [100, 0, 100] as [number, number, number], targetMm: [0, 0, 0] as [number, number, number], fovDeg: 30 } };
  const keys = [{ t: 0, view: "a" }, { t: 1, view: "b", lift: 50 }];
  assert.deepEqual(cameraAt(v, keys, 0).positionMm, v.a.positionMm);
  assert.ok(Math.abs(cameraAt(v, keys, 1 - 1e-9).positionMm[0] - 100) < 1e-6);
  assert.ok(Math.abs(cameraAt(v, keys, 0.5).positionMm[2] - 150) < 1e-6, "lift peaks mid-move");
});

test("analysis: graphics and captions resolve, anchor to real figures and stay within the video", () => {
  const ev0 = shotTimeEvaluator(trace, geometry)(1, 0);
  for (const g of A.graphics) {
    assert.ok(g.t0 >= 0 && g.t1 <= N / spec.fps + 1e-9, g.item.id);
    if (g.item.target) assert.ok(ev0.figures[g.item.target], `${g.item.id}: ${g.item.target} is a traced figure`);
  }
  for (const c of A.chapters) assert.ok(c.t0 >= 0 && c.t1 <= N / spec.fps + 1e-9, c.item.id);
  // chapters never overlap each other
  const ch = [...A.chapters].sort((a, b) => a.t0 - b.t0);
  for (let i = 1; i < ch.length; i++) assert.ok(ch[i]!.t0 >= ch[i - 1]!.t1 - 0.4 + 1e-9, "chapters cross-fade at most");
  assert.throws(() => resolveTime("nowhere.start", A.timeline), /unknown segment/);
  assert.throws(() => resolveTime("intro.middle", A.timeline), /bad time reference/);
  // the contact marker shows the reception contact, the pass arrow the release
  const at = (id: string, t: number): boolean => { const g = A.graphics.find((x) => x.item.id === id)!; return t >= g.t0 && t <= g.t1; };
  assert.ok(framesOf("reception_freeze").slice(15).every((f) => at("contact", f / spec.fps)));
  assert.ok(at("pass_dir", (seg("pass_freeze").f0 + 30) / spec.fps));
});

test("analysis: the composition uses only the pure evaluators and keeps the diagnostic compositions", () => {
  const src = read("remotion/ShotAnalysis.tsx");
  assert.doesNotMatch(src, /useFrame\s*\(|Date\.now|performance\.now|Math\.random|requestAnimationFrame/);
  assert.match(src, /shotTimeEvaluator/);
  assert.match(src, /assertShotRenderable/);
  // the canvas camera must be one object for the life of the tab: a new camera per frame grew the renderer's memory
  // by about 140 MB per 1080p frame until the container killed ffmpeg (first full render, frame 94)
  assert.doesNotMatch(src, /camera=\{[^}]*new THREE\./);
  assert.match(src, /camera=\{canvasCamera\}/);
  const root = read("remotion/Root.tsx");
  for (const id of ["analysis-shovel-17", "shot23-shovel-17", "shot23-at-time", "shot24-shovel-17", "shot25-shovel-17-final", "static-checks"]) assert.match(root, new RegExp(`id="${id}"`), id);
  for (const f of ["Barlow-Medium.ttf", "Barlow-SemiBold.ttf", "BarlowCondensed-SemiBold.ttf", "BarlowCondensed-ExtraBold.ttf", "OFL.txt"]) assert.ok(existsSync(`public/fonts/${f}`), f);
});

test("analysis: export report matches the committed inputs and the delivered video", (t) => {
  const p = "validation/analysis-shovel-17-report.json";
  if (!existsSync(p)) return t.skip("no export yet (npm run video:analysis-shovel-17)");
  const r = JSON.parse(read(p));
  assert.equal(r.trace.sha256, sha("data/traces/shovel-17.trace.json"), "trace changed since the export: re-render");
  assert.equal(r.analysis_spec.sha256, sha("data/presentations/shovel-17.analysis.json"), "analysis spec changed since the export: re-render");
  assert.equal(r.analysis_spec.composition_sha256, sha("remotion/ShotAnalysis.tsx"), "composition changed since the export: re-render");
  assert.equal(r.model.scene_glb_sha256, JSON.parse(read("remotion/asset-manifest.json")).scene_glb.sha256);
  assert.equal(r.output.width, 1920);
  assert.equal(r.output.height, 1080);
  assert.equal(r.output.frames, N);
  assert.ok(r.output.below_25_mb && r.output.bytes < 25e6);
  assert.deepEqual(r.checks.frames_differing_from_pure, []);
  assert.equal(r.checks.frames_logged, N);
  assert.equal(r.checks.camera_frames_logged, N);
  assert.ok(r.checks.camera_max_diff_vs_track <= 0.02);
  if (existsSync(r.output.path)) assert.equal(sha(r.output.path), r.output.sha256);
});
