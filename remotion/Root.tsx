import { Composition } from "remotion";
import { StaticInspection, type InspectionProps } from "./StaticInspection.tsx";

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
    <Composition id="static-checks" component={StaticInspection} durationInFrames={30} fps={30} width={1920} height={1080} defaultProps={{ camera: "oblique", showChecks: true }} />
  </>
);
