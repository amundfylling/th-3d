// Iteration 25: output frames that show the trace's contact events, in the normal pass and in the replay, at a given
// output fps (JSON on stdout). Used by scripts/shot25-review.py.
//
//   node scripts/shot25-keyframes.ts 60
import { readFileSync } from "node:fs";
import { resolveTimeline, sourceAtFrame, type PresentationSpec } from "../src/model/presentation.ts";

const fps = Number(process.argv[2] ?? 60);
const trace = JSON.parse(readFileSync("data/traces/shovel-17.trace.json", "utf8"));
const spec = JSON.parse(readFileSync("data/presentations/shovel-17.presentation.json", "utf8")) as PresentationSpec;
const tl = resolveTimeline(spec, trace, fps);
const out: Record<string, { t: number; normal: number; replay: number }> = {};
for (const id of ["pass.release", "contact.W-C_reception", "shot.separation", "goal_entry"]) {
  const t = trace.events.find((e: { id: string }) => e.id === id).t_estimate as number;
  let best = { normal: -1, replay: -1, dn: Infinity, dr: Infinity };
  for (let f = 0; f < tl.durationInFrames; f++) {
    const s = sourceAtFrame(tl, f);
    const d = Math.abs(s.t - t);
    if (s.segment.id === "normal" && d < best.dn) best = { ...best, normal: f, dn: d };
    if (s.segment.id.startsWith("replay") || s.segment.id === "contact_pause") if (d < best.dr) best = { ...best, replay: f, dr: d };
  }
  out[id] = { t, normal: best.normal, replay: best.replay };
}
console.log(JSON.stringify({ fps, frames: tl.durationInFrames, events: out }));
