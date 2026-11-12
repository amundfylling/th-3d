// Interactive 3D viewer data (docs/viewer.md): samples a saved trace with the same pure evaluator the videos use
// (src/model/shot-pose.ts) and writes, per sample, every trace figure's glTF node pose and the puck position, plus the
// events, puck phases and the move's story text. The viewer only interpolates between these samples (rule 7).
//
//   node scripts/viewer-export.ts <move-id> <out.json> [step_ms=1]
import { readFileSync, writeFileSync } from "node:fs";
import * as THREE from "three";
import { shotTimeEvaluator } from "../src/model/shot-pose.ts";
import { worldMatrixToGltf, worldMmToGltfM } from "../src/model/coordinates.ts";
import type { ShotTrace } from "../src/model/trace.ts";

const [id, out, stepArg] = process.argv.slice(2);
if (!id || !out) throw new Error("usage: node scripts/viewer-export.ts <move-id> <out.json> [step_ms]");
const json = (p: string) => JSON.parse(readFileSync(p, "utf8"));
const trace = json(`data/traces/${id}.trace.json`) as ShotTrace & Record<string, any>;
const geometry = json("data/geometry.json");
const checks = json(`shots/${id}/checks.json`);
const story = json(`moves/${id}/story.json`);
const at = shotTimeEvaluator(trace, geometry);
const nodes = trace.puck.nodes as { t: number; phase: string }[];
const [t0, t1] = [nodes[0]!.t, nodes[nodes.length - 1]!.t];
const step = Number(stepArg ?? 1) / 1000;
const r = (v: number, n = 6) => Math.round(v * 10 ** n) / 10 ** n;
const m = new THREE.Matrix4(), p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
const pids = Object.keys(at(t0, 0).figures);
const samples: { t: number; fig: number[][]; puck: number[] }[] = [];
for (let k = 0; t0 + k * step <= t1 + 1e-9; k++) {
  const t = r(t0 + k * step, 5);
  const st = at(t, k);
  const fig = pids.map((pid) => {
    m.set(...(worldMatrixToGltf(st.figures[pid]!.matrix) as [number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number]));
    m.decompose(p, q, s);
    return [r(p.x), r(p.y), r(p.z), r(q.x), r(q.y), r(q.z), r(q.w)];
  });
  samples.push({ t, fig, puck: worldMmToGltfM(st.puckMm).map((v) => r(v)) });
}
const phases: { id: string; t0: number; t1: number }[] = [];
for (const n of nodes) {
  const last = phases[phases.length - 1];
  if (!last || last.id !== n.phase) phases.push({ id: n.phase, t0: n.t, t1: n.t });
  else last.t1 = n.t;
}
const events = (trace.events as any[]).map((e) => ({ id: e.id, t: e.t_estimate, part: e.part ?? null, peak_impact_mm_s: e.peak_impact_mm_s ?? null, touches: e.touches ?? null, speed_after_mm_s: e.speed_after_mm_s ?? null, goal_line_y_mm: e.goal_line_y_mm ?? null }));
writeFileSync(out, JSON.stringify({
  schema: "viewer-data/1", move: id, trace_id: trace.trace_id, status: trace.status,
  window_s: [t0, t1], step_s: step, figures: pids, samples, phases, events,
  story: { title: story.title, setup: story.setup, beats: story.beats, end_steps: story.end_steps },
  checks: { passed: checks.passed, overlaps: (checks.unexpected_penetrations ?? []).length, slide_passed: checks.slide_check?.passed ?? null,
    robustness: (() => { try { return json(`validation/moves/${id}-robustness.json`).variants_passed ?? null; } catch { return null; } })() },
}));
console.log(`${out}: ${samples.length} samples, ${pids.length} figures (${pids.join(", ")})`);
