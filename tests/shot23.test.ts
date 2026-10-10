import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { checkTraceCompatibility, framesForWindow, shotFrameEvaluator, sourceTimeForFrame, type AssetManifest } from "../src/model/shot-pose.ts";
import { rigid } from "../src/model/pose.ts";
import type { ShotTrace } from "../src/model/trace.ts";

const trace = JSON.parse(readFileSync("data/traces/shovel-17.trace.json", "utf8"));
const geometry = JSON.parse(readFileSync("data/geometry.json", "utf8"));
const manifest = JSON.parse(readFileSync("remotion/asset-manifest.json", "utf8")) as AssetManifest & { asset_files: Record<string, string>; scene_glb: { path: string; source: string; sha256: string } };
const FPS = 30;
const [W0, W1] = trace.time_base.window_s as [number, number];
const ev = shotFrameEvaluator(trace as ShotTrace, geometry);
const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");

test("iteration 23: physical time comes only from frame / fps", () => {
  assert.equal(sourceTimeForFrame(0, FPS, W0), W0);
  assert.ok(Math.abs(sourceTimeForFrame(40, FPS, W0) - (W0 + 40 / 30)) < 1e-12);
  assert.throws(() => sourceTimeForFrame(1.5, FPS, W0));
  assert.throws(() => sourceTimeForFrame(-1, FPS, W0));
  const n = framesForWindow([W0, W1], FPS);
  assert.ok(sourceTimeForFrame(n - 1, FPS, W0) <= W1 + 1e-9 && sourceTimeForFrame(n, FPS, W0) > W1, `${n} frames`);
});

test("iteration 23: shuffled and repeated frame evaluation gives identical poses", () => {
  const n = framesForWindow([W0, W1], FPS);
  const frames = Array.from({ length: n }, (_, i) => i);
  const forward = frames.map((f) => JSON.stringify(ev(f, FPS, W0)));
  const order = [...frames].sort((a, b) => ((a * 7919) % 101) - ((b * 7919) % 101)); // fixed permutation
  for (let rep = 0; rep < 3; rep++) for (const f of order) assert.equal(JSON.stringify(ev(f, FPS, W0)), forward[f], `frame ${f} rep ${rep}`);
  // a fresh evaluator (no shared state) agrees too
  const ev2 = shotFrameEvaluator(trace as ShotTrace, geometry);
  for (const f of [...order].reverse()) assert.equal(JSON.stringify(ev2(f, FPS, W0)), forward[f]);
});

test("iteration 23: contact timing in frames is unchanged and inside the shot", () => {
  for (const id of ["pass.release", "contact.W-C_reception", "shot.separation", "goal_entry"]) {
    const t = trace.events.find((e: { id: string }) => e.id === id).t_estimate;
    // the diagnostic composition places frame 0 exactly at the event time
    assert.equal(ev(0, FPS, t).t, t, id);
    assert.ok(t > W0 && t < W1, id);
  }
  // puck phase at the release frame boundary matches the trace phases
  const rel = trace.events.find((e: { id: string }) => e.id === "pass.release").t_estimate;
  assert.equal(ev(0, FPS, rel + 1e-3).puckPhase, "pass_free");
});

test("iteration 23: continuous angles - no reversal through zero, W-RW turns counter-clockwise", () => {
  for (const pid of Object.keys(ev(0, FPS, W0).figures)) {
    let prev: number | null = null, prevMat: number | null = null;
    for (let t = W0; t <= W1; t += 0.001) {
      const f = ev(0, FPS, t).figures[pid]!;
      // heading recovered from the pose matrix, unwrapped against the previous sample, equals headingDeg
      const m = f.matrix;
      let h = (Math.atan2(m[4], m[0]) * 180) / Math.PI;
      if (prevMat !== null) h = prevMat + ((((h - prevMat) % 360) + 540) % 360) - 180;
      assert.ok(Math.abs(h - f.headingDeg - 360 * Math.round((h - f.headingDeg) / 360)) < 1e-9, `${pid} matrix heading`);
      if (prev !== null) assert.ok(Math.abs(f.headingDeg - prev) < 5, `${pid} jumps ${f.headingDeg - prev} deg at ${t}`);
      prev = f.headingDeg;
      prevMat = h;
    }
  }
  // W-RW passes with a counter-clockwise rotation: heading never decreases from the frame-102 blade key to the
  // visual key after the pass (the prep turns before it go both ways, observed in the recording)
  const k = trace.figures["W-RW"].theta_keyframes;
  const i102 = k.findIndex((x: { source: string }) => x.source.startsWith("blade frame 102"));
  const iEnd = k.findIndex((x: { source: string }) => x.source.startsWith("visual: back to the camera in frame 107"));
  assert.ok(i102 >= 0 && iEnd > i102, "pass rotation keys present");
  let last = -Infinity;
  for (let t = k[i102].t; t <= k[iEnd].t; t += 0.001) {
    const h = ev(0, FPS, t).figures["W-RW"]!.headingDeg;
    assert.ok(h >= last - 1e-9, `W-RW reverses at ${t}`);
    last = h;
  }
  assert.deepEqual(rigid(370, [0, 0, 0]).map((x) => Math.round(x * 1e12)), rigid(10, [0, 0, 0]).map((x) => Math.round(x * 1e12)));
});

test("iteration 23: mismatched geometry or asset versions are rejected", () => {
  assert.deepEqual(checkTraceCompatibility(trace, geometry.geometry_version, manifest), ["geometry_version", "figure_molds_sha256", "skater_glb_sha256", "goalie_glb_sha256"]);
  assert.throws(() => checkTraceCompatibility({ ...trace, geometry_version: "0.5.0" }, geometry.geometry_version, manifest), /geometry_version/);
  const bad = { ...manifest, asset_sha256: { ...manifest.asset_sha256, skater_glb_sha256: "0".repeat(64) } };
  assert.throws(() => checkTraceCompatibility(trace, geometry.geometry_version, bad), /skater_glb_sha256/);
  assert.throws(() => checkTraceCompatibility({ ...trace, asset_refs: {} }, geometry.geometry_version, manifest), /no asset hashes/);
});

test("iteration 23: the asset manifest matches the files on disk", () => {
  assert.equal(manifest.geometry_version, geometry.geometry_version);
  for (const [k, p] of Object.entries(manifest.asset_files)) assert.equal(manifest.asset_sha256[k], sha(p), p);
  assert.equal(manifest.scene_glb.sha256, sha(manifest.scene_glb.source));
});

test("iteration 23: the composition advances only by frame (no useFrame, clocks or accumulated state)", () => {
  const src = readFileSync("remotion/ShotPlayback.tsx", "utf8").replace(/\/\/.*$/gm, "");
  for (const bad of ["useFrame(", "Date.now", "performance.now", "new THREE.Clock", "getDelta", "requestAnimationFrame", "setInterval"]) assert.ok(!src.includes(bad), bad);
  assert.match(src, /useCurrentFrame\(\)/);
  assert.match(src, /evaluate\(frame, fps, startS\)/);
});
