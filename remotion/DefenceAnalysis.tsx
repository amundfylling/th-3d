// Defending against the left wing (composition analysis-defence-lw): the shared analysis video (remotion/AnalysisVideo.tsx)
// with the designed set-ups of data/traces/defence-left-wing.trace.json (passive / active / mix, from the user's TikTok),
// its contact checks and data/presentations/defence-left-wing.analysis.json. The trace is PROPOSED and DESIGNED (a concept
// illustration); the user asked for the video directly. The puck stays on the left wing's blade; shots and passes are
// lanes recorded on the trace events, drawn as graphics.
import analysisJson from "../data/presentations/defence-left-wing.analysis.json" with { type: "json" };
import traceJson from "../data/traces/defence-left-wing.trace.json" with { type: "json" };
import contactChecks from "../shots/defence-left-wing/checks.json" with { type: "json" };
import type { AnalysisSpec } from "../src/model/analysis.ts";
import { createAnalysisVideo, type AnalysisTrace } from "./AnalysisVideo.tsx";

export const DEFENCE_TRACE = traceJson as unknown as AnalysisTrace;

const video = createAnalysisVideo({
  spec: analysisJson as unknown as AnalysisSpec,
  trace: DEFENCE_TRACE,
  checks: contactChecks,
  logTag: "defence",
  allowProposed: true,
  text: {
    kicker: "DEFENCE ANALYSIS",
    title: "3 DEFENCES",
    subtitle: "When the opponent's left wing has the puck · passive · active · mix",
    bug: "DEFENDING THE LEFT WING",
    endTitle: "3 WAYS TO DEFEND THE LEFT WING",
    endSteps: ["PASSIVE · THE BOX", "ACTIVE", "THE MIX"],
  },
});

export const DEFENCE_ANALYSIS = video.ANALYSIS;
export const DefenceAnalysis = video.Component;
