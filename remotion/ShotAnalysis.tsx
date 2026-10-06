// "#17 The Shovel" analysis video (composition analysis-shovel-17): the shared analysis video (remotion/AnalysisVideo.tsx)
// with the accepted Shovel trace, its contact checks and data/presentations/shovel-17.analysis.json.
import analysisJson from "../data/presentations/shovel-17.analysis.json" with { type: "json" };
import contactChecks from "../shots/22-shovel/checks.json" with { type: "json" };
import type { AnalysisSpec } from "../src/model/analysis.ts";
import { createAnalysisVideo, type AnalysisTrace } from "./AnalysisVideo.tsx";
import { SHOT_TRACE, assertShotRenderable } from "./ShotPlayback.tsx";

export type { AnalysisProps } from "./AnalysisVideo.tsx";

const video = createAnalysisVideo({
  spec: analysisJson as unknown as AnalysisSpec,
  trace: SHOT_TRACE as unknown as AnalysisTrace,
  checks: contactChecks,
  logTag: "analysis",
  gate: assertShotRenderable,
  text: {
    kicker: "SHOT ANALYSIS",
    title: "THE SHOVEL",
    subtitle: "Table hockey · STIGA Play Off 21 · reconstructed from video",
    bug: "#17 THE SHOVEL",
    endTitle: "THE SHOVEL",
    endSteps: ["BACKHAND PASS", "RECEIVED ON THE BACK", "SHOVELLED TO THE FAR CORNER"],
  },
  defaults: {
    pass_arrow: { event: "pass.release", label: "PASS" },
    contact_marker: { event: "contact.W-C_reception", target: "W-C", label: "CONTACT · AT THE SKATES" },
    slot_arrow: { event: "contact.W-C_reception" },
    puck_trail: { event: "pass.release" },
  },
});

export const ANALYSIS = video.ANALYSIS;
export const ShotAnalysis = video.Component;
