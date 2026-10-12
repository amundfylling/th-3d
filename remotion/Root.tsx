import { Composition } from "remotion";
import { framesForWindow } from "../src/model/shot-pose.ts";
import { SHOT_TRACE, ShotPlayback } from "./ShotPlayback.tsx";
import { ShotPresentation, TIMELINE, timelineFor } from "./ShotPresentation.tsx";
import { PosePreview } from "./PosePreview.tsx";
import { analysisMetadata } from "./AnalysisVideo.tsx";
import { ANALYSIS_VIDEOS } from "./analysis-videos.ts";
import { GlProbe, SceneProbe, sceneProbeMetadata } from "./SceneProbe.tsx";

// Iteration 25: final export settings (presentation choice, not geometry precision): 1920 x 1080 at 60 fps.
export const FINAL_FPS = 60;
import { StaticInspection, type InspectionProps } from "./StaticInspection.tsx";

// Iteration 23: the accepted trace at real speed (source time = window start + frame / fps).
export const SHOT_FPS = 30;
const [W0, W1] = SHOT_TRACE.time_base.window_s;

// One static inspection composition per camera choice. Every frame shows the same fixed pose.
const CAMERAS: InspectionProps["camera"][] = ["overhead", "side", "oblique"];

export const RemotionRoot: React.FC = () => (
  <>
    {CAMERAS.map((camera) => (
      <Composition
        key={camera}
        id={`static-${camera}`}
        component={StaticInspection}
        durationInFrames={30}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{ camera }}
      />
    ))}
    <Composition id="shot23-shovel-17" component={ShotPlayback} durationInFrames={framesForWindow([W0, W1], SHOT_FPS)} fps={SHOT_FPS} width={1920} height={1080} defaultProps={{ startS: W0 }} />
    {/* Diagnostic still at an arbitrary source time: render frame 0 with --props='{"startS": t}'. */}
    <Composition id="shot23-at-time" component={ShotPlayback} durationInFrames={1} fps={SHOT_FPS} width={1920} height={1080} defaultProps={{ startS: W0 }} />
    {/* Iteration 24: normal speed + 1/4-speed replay with a pause at the key contact (oblique benchmark camera). */}
    <Composition id="shot24-shovel-17" component={ShotPresentation} durationInFrames={TIMELINE.durationInFrames} fps={TIMELINE.fps} width={1920} height={1080} defaultProps={{ overlays: true }} />
    {/* Iteration 25: the same presentation exported at 60 fps (approved iteration-24 timeline, laid out at 2 output frames per presentation frame). */}
    <Composition id="shot25-shovel-17-final" component={ShotPresentation} durationInFrames={timelineFor(FINAL_FPS).durationInFrames} fps={FINAL_FPS} width={1920} height={1080} defaultProps={{ overlays: true }} />
    {/* Sports-analysis videos (VAR-style breakdowns) on the shared renderer: analysis-shovel-17 (accepted Shovel trace),
        analysis-spjass, analysis-nacka, analysis-ikv, analysis-defence-lw, and one move-<id> per shot-encyclopedia move
        (remotion/encyclopedia-registry.ts). Props: graphics, frameMap (render selected frames), sceneSrc (cached scene layer). */}
    {ANALYSIS_VIDEOS.map((v) => (
      <Composition key={v.id} id={v.id} component={v.Component} durationInFrames={v.ANALYSIS.durationInFrames} fps={v.ANALYSIS.spec.fps} width={v.ANALYSIS.spec.width} height={v.ANALYSIS.spec.height} defaultProps={{ graphics: true }} calculateMetadata={analysisMetadata} />
    ))}
    {/* Scene-state isolation check: scenes of several compositions drawn in one tab (scripts/video/scene-probe.ts). */}
    <Composition id="scene-probe" component={SceneProbe} durationInFrames={1} fps={30} width={1920} height={1080} defaultProps={{ items: [{ video: "analysis-shovel-17", frame: 0 }] }} calculateMetadata={sceneProbeMetadata} />
    {/* Which WebGL implementation a render's browser flags give (scripts/video/render-env.ts probeRenderer). */}
    <Composition id="gl-probe" component={GlProbe} durationInFrames={1} fps={30} width={64} height={64} />
    <Composition id="pose-preview" component={PosePreview} durationInFrames={1} fps={30} width={1600} height={1300} defaultProps={{ poses: {}, puckMm: [0, 0] as [number, number], camera: { cx: 150, cy: 0, widthMm: 640 } }} />
    <Composition id="static-checks" component={StaticInspection} durationInFrames={30} fps={30} width={1920} height={1080} defaultProps={{ camera: "oblique", showChecks: true }} />
  </>
);
