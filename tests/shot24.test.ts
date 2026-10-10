import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolveTimeline, sourceAtFrame, type PresentationSpec } from "../src/model/presentation.ts";
import { shotFrameEvaluator, shotTimeEvaluator } from "../src/model/shot-pose.ts";
import type { ShotTrace } from "../src/model/trace.ts";

const trace = JSON.parse(readFileSync("data/traces/shovel-17.trace.json", "utf8"));
const geometry = JSON.parse(readFileSync("data/geometry.json", "utf8"));
const spec = JSON.parse(readFileSync("data/presentations/shovel-17.presentation.json", "utf8")) as PresentationSpec;
const tl = resolveTimeline(spec, trace);
const stateAt = shotTimeEvaluator(trace as ShotTrace, geometry);
const [W0, W1] = trace.time_base.window_s as [number, number];
const tContact = trace.events.find((e: { id: string }) => e.id === "contact.W-C_reception").t_estimate as number;

test("iteration 24: explicit presentation -> source time mapping for the accepted trace", () => {
  assert.equal(spec.trace_id, trace.trace_id);
  assert.equal(trace.status, "accepted");
  const kinds = tl.segments.map((s) => `${s.kind}:${s.rate}`);
  assert.ok(kinds.includes("play:1"), "one pass at normal speed");
  assert.ok(tl.segments.some((s) => s.kind === "play" && s.rate < 1), "a slower replay");
  for (const s of tl.segments) assert.ok(s.kind === "hold" ? s.rate === 0 : s.rate === 1 || s.rate === 0.25, `${s.id} rate ${s.rate}`);
  // the normal-speed pass shows the whole iteration-23 shot, frame for frame
  const ev23 = shotFrameEvaluator(trace as ShotTrace, geometry);
  const normal = tl.segments.find((s) => s.id === "normal")!;
  for (let k = 0; k < normal.f1 - normal.f0; k++) assert.equal(sourceAtFrame(tl, normal.f0 + k).t, ev23(k, 30, W0).t, `normal frame ${k}`);
});

test("iteration 24: every frame shows a source time inside the trace window; play never runs backwards", () => {
  let prev: { seg: string; t: number } | null = null;
  for (let f = 0; f < tl.durationInFrames; f++) {
    const { t, segment } = sourceAtFrame(tl, f);
    assert.ok(t >= W0 - 1e-12 && t <= W1 + 1e-12, `frame ${f}: ${t}`);
    if (prev && prev.seg === segment.id) assert.ok(segment.kind === "hold" ? t === prev.t : t > prev.t, `frame ${f}`);
    prev = { seg: segment.id, t };
  }
});

test("iteration 24: the pause is at exactly the trace's key contact; no invented events", () => {
  const pause = tl.segments.find((s) => s.kind === "hold" && s.t === tContact);
  assert.ok(pause && pause.f1 - pause.f0 >= 30, "a pause of at least 1 s at contact.W-C_reception");
  for (let f = Math.ceil(pause.f0); f < pause.f1; f++) assert.equal(sourceAtFrame(tl, f).t, tContact);
  // the presentation names only events that exist in the trace and carries no mechanics of its own
  const refs = JSON.stringify(spec.segments).match(/"event":"([^"]+)"/g) ?? [];
  for (const r of refs) assert.ok(trace.events.some((e: { id: string }) => r.includes(`"${e.id}"`)), r);
  for (const banned of ["velocity", "speed_mm", "direction_deg", "arc_mm", "theta", "x_mm"]) assert.ok(!JSON.stringify(spec).includes(banned), banned);
});

test("iteration 24: the same source time gives the same physical state in the normal pass and the replay", () => {
  for (let k = 33; k <= 40; k++) {
    const fn = 30 + k, fr = 95 + 4 * (k - 33);
    const a = sourceAtFrame(tl, fn), b = sourceAtFrame(tl, fr);
    assert.equal(a.segment.id, "normal");
    assert.equal(b.segment.id, "replay_in");
    assert.equal(a.t, b.t, `k ${k}: source times must be bit-identical`);
    const sa = stateAt(a.t, 0), sb = stateAt(b.t, 0);
    assert.deepEqual(sa, sb);
  }
});

test("iteration 24: captions and the marker are presentation data on existing segments, restrained", () => {
  const ids = new Set(tl.segments.map((s) => s.id));
  for (const c of [...spec.captions, ...spec.markers]) for (const s of c.segments) assert.ok(ids.has(s), `${c.id}: ${s}`);
  assert.equal(spec.captions.filter((c) => c.role === "title").length, 1, "one short technique title");
  assert.ok(spec.captions.find((c) => c.role === "title")!.text.length <= 24);
  const contact = spec.captions.filter((c) => c.role === "contact");
  assert.equal(contact.length, 1, "one key-contact explanation");
  assert.ok(contact[0]!.segments.every((s) => tl.segments.find((x) => x.id === s)!.kind === "hold"), "explanation shown while paused");
  assert.equal(spec.markers.length, 1, "one restrained marker");
});

test("iteration 24: the composition reads the trace only through the pure evaluator; no clocks, no blur or depth of field", () => {
  for (const file of ["remotion/ShotPresentation.tsx", "remotion/ShotScene.tsx"]) {
    const src = readFileSync(file, "utf8").replace(/\/\/.*$/gm, "");
    for (const bad of ["useFrame(", "Date.now", "performance.now", "new THREE.Clock", "getDelta", "requestAnimationFrame", "setInterval", "blur(", "DepthOfField", "Bokeh", "motionBlur"]) assert.ok(!src.includes(bad), `${file}: ${bad}`);
  }
  const src = readFileSync("remotion/ShotPresentation.tsx", "utf8");
  assert.match(src, /stateAt\(sourceAtFrame\(timeline, frame\)\.t, frame\)/);
  assert.match(src, /shotTimeEvaluator\(SHOT_TRACE/);
  assert.equal(spec.camera, "oblique", "one camera from the static benchmarks (remotion/cameras.ts)");
});
