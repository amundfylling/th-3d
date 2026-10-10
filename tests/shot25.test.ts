import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { resolveTimeline, sourceAtFrame, type PresentationSpec } from "../src/model/presentation.ts";

const trace = JSON.parse(readFileSync("data/traces/shovel-17.trace.json", "utf8"));
const spec = JSON.parse(readFileSync("data/presentations/shovel-17.presentation.json", "utf8")) as PresentationSpec;
const t30 = resolveTimeline(spec, trace);
const t60 = resolveTimeline(spec, trace, 60);
const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");

test("iteration 25: the 60 fps export shows the approved 30 fps presentation, every source time bit for bit", () => {
  assert.equal(t60.outFps, 60);
  assert.equal(t60.durationInFrames, 2 * t30.durationInFrames);
  for (let k = 0; k < t30.durationInFrames; k++) {
    const a = sourceAtFrame(t30, k), b = sourceAtFrame(t60, 2 * k);
    assert.equal(b.t, a.t, `frame ${k}`);
    assert.equal(b.segment.id, a.segment.id);
  }
  // the in-between 60 fps frames lie between their neighbours (or on a pause)
  for (let k = 0; k + 1 < t30.durationInFrames; k++) {
    const lo = sourceAtFrame(t60, 2 * k).t, mid = sourceAtFrame(t60, 2 * k + 1).t, hi = sourceAtFrame(t60, 2 * k + 2).t;
    if (sourceAtFrame(t60, 2 * k).segment.id === sourceAtFrame(t60, 2 * k + 2).segment.id) assert.ok(mid >= Math.min(lo, hi) && mid <= Math.max(lo, hi), `frame ${2 * k + 1}`);
  }
  assert.throws(() => resolveTimeline(spec, trace, 45), /whole multiple/);
});

test("iteration 25: the final composition is registered at the recorded output settings", () => {
  const root = readFileSync("remotion/Root.tsx", "utf8");
  assert.match(root, /FINAL_FPS = 60/);
  assert.match(root, /id="shot25-shovel-17-final"[^>]*fps=\{FINAL_FPS\} width=\{1920\} height=\{1080\}/);
});

test("iteration 25: export report matches the committed trace, presentation, assets and final video", (t) => {
  if (!existsSync("validation/25-export-report.json")) return t.skip("no export yet (npm run video:shovel-17)");
  const r = JSON.parse(readFileSync("validation/25-export-report.json", "utf8"));
  const lock = JSON.parse(readFileSync("package-lock.json", "utf8"));
  assert.equal(r.trace.trace_id, trace.trace_id);
  assert.equal(r.trace.sha256, sha("data/traces/shovel-17.trace.json"), "trace changed since the export: re-render");
  assert.equal(r.presentation.sha256, sha("data/presentations/shovel-17.presentation.json"), "presentation changed since the export: re-render");
  const manifest = JSON.parse(readFileSync("remotion/asset-manifest.json", "utf8"));
  assert.equal(r.model.scene_glb_sha256, manifest.scene_glb.sha256);
  assert.equal(r.versions.remotion, lock.packages["node_modules/remotion"].version);
  assert.equal(r.versions.three, lock.packages["node_modules/three"].version);
  for (const k of ["draft", "final"]) {
    assert.ok(r[k], `${k} render recorded`);
    assert.deepEqual(r[k].frames_differing_from_pure, [], `${k}: every frame equals the pure evaluation`);
    assert.equal(r[k].frames_logged, r[k].frames);
    assert.equal(r[k].fps, 60);
  }
  assert.equal(r.final.width, 1920);
  assert.equal(r.final.height, 1080);
  if (existsSync(r.final.path)) assert.equal(sha(r.final.path), r.final.sha256);
});
