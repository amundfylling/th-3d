import { Composition } from "remotion";
import { framesForWindow } from "../src/model/shot-pose.ts";
import { SHOT_TRACE, ShotPlayback } from "./ShotPlayback.tsx";
import { ShotPresentation, TIMELINE, timelineFor } from "./ShotPresentation.tsx";

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
    <Composition id="static-checks" component={StaticInspection} durationInFrames={30} fps={30} width={1920} height={1080} defaultProps={{ camera: "oblique", showChecks: true }} />
  </>
);
