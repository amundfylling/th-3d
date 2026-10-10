// Shot encyclopedia: one analysis video per move built by the move engine (moves/<id>/move.json, scripts/build-move.py).
// The shared analysis video (remotion/AnalysisVideo.tsx) with the move's trace, contact checks and generated presentation
// (remotion/encyclopedia-registry.ts, written by scripts/shotlib/presentation.py). Composition ids: move-<id>.
// Moves are designed and PROPOSED until the user reviews them; the contact check gate still applies.
import { createAnalysisVideo } from "./AnalysisVideo.tsx";
import { ENCYCLOPEDIA } from "./encyclopedia-registry.ts";

export const ENCYCLOPEDIA_VIDEOS = ENCYCLOPEDIA.map((m) => {
  const video = createAnalysisVideo({ spec: m.spec, trace: m.trace, checks: m.checks, logTag: `move-${m.id}`, allowProposed: true, text: m.text });
  return { id: `move-${m.id}`, ANALYSIS: video.ANALYSIS, Component: video.Component };
});
