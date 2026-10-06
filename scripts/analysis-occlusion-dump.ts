// Dumps, per frame of an analysis video, the camera position and the posed figures and puck (pure evaluation),
// for scripts/analysis-occlusion.py (ray casts against the real figure meshes).
//   node scripts/analysis-occlusion-dump.ts <analysis.json> <trace.json> <out.json>
import { readFileSync, writeFileSync } from "node:fs";
import { analysisFrame, resolveAnalysis } from "../src/model/analysis.ts";
import { shotTimeEvaluator } from "../src/model/shot-pose.ts";

const [specPath, tracePath, outPath] = process.argv.slice(2) as [string, string, string];
const spec = JSON.parse(readFileSync(specPath, "utf8"));
if (process.env.VIEWS) Object.assign(spec.views, JSON.parse(process.env.VIEWS));
const trace = JSON.parse(readFileSync(tracePath, "utf8"));
const A = resolveAnalysis(spec, trace);
const stateAt = shotTimeEvaluator(trace, JSON.parse(readFileSync("data/geometry.json", "utf8")));
const asm = JSON.parse(readFileSync("validation/16-assembly-poses.json", "utf8")).figures as { player_id: string; pivot_mm: number[]; heading_deg: number }[];
const frames = [];
for (let f = 0; f < A.durationInFrames; f++) {
  const af = analysisFrame(A, f), s = stateAt(af.t, f);
  frames.push({
    frame: f, segment: af.segment.id, t: af.t, camera: af.camera.positionMm, puck: s.puckMm,
    figures: asm.map((a) => {
      const tf = s.figures[a.player_id];
      return { id: a.player_id, kind: a.player_id.endsWith("G") ? "goalie" : "skater", pivot: tf ? tf.pivotMm.slice(0, 2) : a.pivot_mm.slice(0, 2), heading: tf ? tf.headingDeg : a.heading_deg };
    }),
  });
}
writeFileSync(outPath, JSON.stringify({ spec: specPath, trace: tracePath, frames }));
