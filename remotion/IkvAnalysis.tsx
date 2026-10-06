// Invers Kryssar med Velodrom analysis video (composition analysis-ikv): the shared analysis video (remotion/AnalysisVideo.tsx) with the
// designed trace of the NTHF description (reading approved as a sketch), its contact checks and data/presentations/invers-kryssar-velodrom.analysis.json.
// The trace is PROPOSED and DESIGNED (no recording exists); the user asked for the animation directly, so this composition
// is allowed to render a proposed trace. The contact check gate still applies.
import analysisJson from "../data/presentations/invers-kryssar-velodrom.analysis.json" with { type: "json" };
import traceJson from "../data/traces/invers-kryssar-velodrom.trace.json" with { type: "json" };
import contactChecks from "../shots/invers-kryssar-velodrom/checks.json" with { type: "json" };
import type { AnalysisSpec } from "../src/model/analysis.ts";
import { createAnalysisVideo, type AnalysisTrace } from "./AnalysisVideo.tsx";

export const IKV_TRACE = traceJson as unknown as AnalysisTrace;

const video = createAnalysisVideo({
  spec: analysisJson as unknown as AnalysisSpec,
  trace: IKV_TRACE,
  checks: contactChecks,
  logTag: "ikv",
  allowProposed: true,
  text: {
    kicker: "SHOT ANALYSIS",
    title: "VELODROM",
    subtitle: "Invers Kryssar med Velodrom · right wing · animated from the NTHF description",
    bug: "INVERS KRYSSAR MED VELODROM",
    endTitle: "INVERS KRYSSAR MED VELODROM",
    endSteps: ["CROSS PASS TO THE LEFT WING", "ALONG THE BOARDS BEHIND THE GOAL", "FIRST-TIME SHOT"],
  },
});

export const IKV_ANALYSIS = video.ANALYSIS;
export const IkvAnalysis = video.Component;
