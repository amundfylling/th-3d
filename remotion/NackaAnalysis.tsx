// Näcka analysis video (composition analysis-nacka): the shared analysis video (remotion/AnalysisVideo.tsx) with the
// designed Näcka trace (NTHF description and illustration), its contact checks and data/presentations/nacka.analysis.json.
// The trace is PROPOSED and DESIGNED (no recording of Näcka exists); the user asked for the animation directly, so this composition
// is allowed to render a proposed trace. The contact check gate still applies.
import analysisJson from "../data/presentations/nacka.analysis.json" with { type: "json" };
import traceJson from "../data/traces/nacka.trace.json" with { type: "json" };
import contactChecks from "../shots/nacka/checks.json" with { type: "json" };
import type { AnalysisSpec } from "../src/model/analysis.ts";
import { createAnalysisVideo, type AnalysisTrace } from "./AnalysisVideo.tsx";

export const NACKA_TRACE = traceJson as unknown as AnalysisTrace;

const video = createAnalysisVideo({
  spec: analysisJson as unknown as AnalysisSpec,
  trace: NACKA_TRACE,
  checks: contactChecks,
  logTag: "nacka",
  allowProposed: true,
  text: {
    kicker: "SHOT ANALYSIS",
    title: "NÄCKA",
    subtitle: "Table hockey · centre move · animated from the NTHF description",
    bug: "NÄCKA",
    endTitle: "NÄCKA",
    endSteps: ["PUCK BEHIND THE HEEL", "HEEL PASS TO THE RIGHT", "BLADE SHOT, RIGHT CORNER"],
  },
});

export const NACKA_ANALYSIS = video.ANALYSIS;
export const NackaAnalysis = video.Component;
