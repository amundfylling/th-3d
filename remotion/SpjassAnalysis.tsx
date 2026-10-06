// Spjass analysis video (composition analysis-spjass): the shared analysis video (remotion/AnalysisVideo.tsx) with the
// spjass trace reconstructed from the user's TikTok, its contact checks and data/presentations/spjass.analysis.json.
// The trace is PROPOSED (not yet reviewed by the user); the user asked for the animation directly, so this composition
// is allowed to render a proposed trace. The contact check gate still applies.
import analysisJson from "../data/presentations/spjass.analysis.json" with { type: "json" };
import traceJson from "../data/traces/spjass.trace.json" with { type: "json" };
import contactChecks from "../shots/spjass/checks.json" with { type: "json" };
import type { AnalysisSpec } from "../src/model/analysis.ts";
import { createAnalysisVideo, type AnalysisTrace } from "./AnalysisVideo.tsx";

export const SPJASS_TRACE = traceJson as unknown as AnalysisTrace;

const video = createAnalysisVideo({
  spec: analysisJson as unknown as AnalysisSpec,
  trace: SPJASS_TRACE,
  checks: contactChecks,
  logTag: "spjass",
  allowProposed: true,
  text: {
    kicker: "SHOT ANALYSIS",
    title: "THE SPJASS",
    subtitle: "Table hockey · centre move · reconstructed from video",
    bug: "THE SPJASS",
    endTitle: "THE SPJASS",
    endSteps: ["PUCK BEHIND THE HEEL", "BACKHAND FLICK TO THE SIDE", "SPIN AND FOREHAND SHOT"],
  },
});

export const SPJASS_ANALYSIS = video.ANALYSIS;
export const SpjassAnalysis = video.Component;
