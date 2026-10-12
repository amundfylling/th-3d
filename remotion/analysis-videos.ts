// Every analysis composition built on the shared renderer (remotion/AnalysisVideo.tsx), by composition id. Root.tsx
// registers them; the scene-probe composition (remotion/SceneProbe.tsx) draws their scenes in one tab in any order.
import type { Analysis } from "../src/model/analysis.ts";
import type { AnalysisProps } from "./AnalysisVideo.tsx";
import { DEFENCE_ANALYSIS, DefenceAnalysis } from "./DefenceAnalysis.tsx";
import { ENCYCLOPEDIA_VIDEOS } from "./EncyclopediaAnalysis.tsx";
import { IKV_ANALYSIS, IkvAnalysis } from "./IkvAnalysis.tsx";
import { NACKA_ANALYSIS, NackaAnalysis } from "./NackaAnalysis.tsx";
import { ANALYSIS, ShotAnalysis } from "./ShotAnalysis.tsx";
import { SPJASS_ANALYSIS, SpjassAnalysis } from "./SpjassAnalysis.tsx";

export interface AnalysisVideoEntry {
  id: string;
  ANALYSIS: Analysis;
  Component: React.FC<AnalysisProps>;
}

export const ANALYSIS_VIDEOS: AnalysisVideoEntry[] = [
  { id: "analysis-shovel-17", ANALYSIS, Component: ShotAnalysis },
  { id: "analysis-spjass", ANALYSIS: SPJASS_ANALYSIS, Component: SpjassAnalysis },
  { id: "analysis-nacka", ANALYSIS: NACKA_ANALYSIS, Component: NackaAnalysis },
  { id: "analysis-ikv", ANALYSIS: IKV_ANALYSIS, Component: IkvAnalysis },
  { id: "analysis-defence-lw", ANALYSIS: DEFENCE_ANALYSIS, Component: DefenceAnalysis },
  ...ENCYCLOPEDIA_VIDEOS,
];
