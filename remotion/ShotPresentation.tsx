// Iteration 24: presentation around the accepted shot - once at normal speed, then a 1/4-speed replay that pauses at
// the key contact. The frame maps to a source time through the explicit timeline (src/model/presentation.ts,
// data/presentations/shovel-17.presentation.json); the physical state comes from the same trace evaluator as
// iteration 23. Captions and the marker are a separate overlay layer that only reads the state; they never feed back
// into the mechanics. No blur or depth of field is used anywhere.
import { ThreeCanvas } from "@remotion/three";
import { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import geometry from "../data/geometry.json" with { type: "json" };
import presentationJson from "../data/presentations/shovel-17.presentation.json" with { type: "json" };
import { activeAt, resolveTimeline, sourceAtFrame, type PresentationSpec } from "../src/model/presentation.ts";
import { shotTimeEvaluator } from "../src/model/shot-pose.ts";
import { CAMERAS, toThree } from "./cameras.ts";
import { ShotScene } from "./ShotScene.tsx";
import { SHOT_TRACE, assertShotRenderable } from "./ShotPlayback.tsx";

export const PRESENTATION = presentationJson as unknown as PresentationSpec;
const TIMELINES = new Map<number, ReturnType<typeof resolveTimeline>>();
/** The presentation timeline laid out at an output frame rate (a whole multiple of the presentation fps). */
export function timelineFor(fps: number): ReturnType<typeof resolveTimeline> {
  if (!TIMELINES.has(fps)) TIMELINES.set(fps, resolveTimeline(PRESENTATION, SHOT_TRACE as unknown as Parameters<typeof resolveTimeline>[1], fps));
  return TIMELINES.get(fps)!;
}
export const TIMELINE = timelineFor(PRESENTATION.fps);
const stateAt = shotTimeEvaluator(SHOT_TRACE, geometry as Parameters<typeof shotTimeEvaluator>[1]);

export type PresentationProps = {
  /** false: render the mechanics only (used to compare normal and replay frames pixel for pixel). */
  overlays: boolean;
};

function benchmarkCamera(name: keyof typeof CAMERAS, width: number, height: number): THREE.PerspectiveCamera | THREE.OrthographicCamera {
  const cam = CAMERAS[name];
  const aspect = height / width;
  const halfW = cam.fovDegOrWidthMm / 2000;
  const c =
    cam.kind === "orthographic"
      ? new THREE.OrthographicCamera(-halfW, halfW, halfW * aspect, -halfW * aspect, 0.01, 20)
      : new THREE.PerspectiveCamera(cam.fovDegOrWidthMm, width / height, 0.01, 20);
  c.position.set(...toThree(cam.positionMm));
  if (cam.kind === "orthographic") c.up.set(0, 0, -1);
  else c.up.set(0, 1, 0);
  c.lookAt(...toThree(cam.targetMm));
  c.updateProjectionMatrix();
  c.updateMatrixWorld(true);
  return c;
}

const CAPTION: React.CSSProperties = { position: "absolute", color: "#ffffff", fontFamily: "DejaVu Sans, Arial, sans-serif", textShadow: "0 1px 3px rgba(0,0,0,0.6)" };

const Overlay: React.FC<{ frame: number; timeline: ReturnType<typeof resolveTimeline>; puckMm: [number, number, number]; cam: THREE.Camera; width: number; height: number }> = ({ frame, timeline, puckMm, cam, width, height }) => {
  const { segment } = sourceAtFrame(timeline, frame);
  const caps = activeAt(PRESENTATION.captions, segment);
  const marks = activeAt(PRESENTATION.markers, segment);
  const toPx = (p: [number, number, number]): [number, number] => {
    const v = new THREE.Vector3(...toThree(p)).project(cam);
    return [((v.x + 1) / 2) * width, ((1 - v.y) / 2) * height];
  };
  const centre = toPx([puckMm[0], puckMm[1], 6]);
  const edge = toPx([puckMm[0] + 12.7, puckMm[1], 6]);
  const r = Math.hypot(edge[0] - centre[0], edge[1] - centre[1]) * 1.9;
  const title = caps.find((c) => c.role === "title");
  const speed = caps.find((c) => c.role === "speed");
  const contact = caps.find((c) => c.role === "contact");
  return (
    <AbsoluteFill>
      {marks.length ? (
        <svg width={width} height={height} style={{ position: "absolute", left: 0, top: 0 }}>
          <circle cx={centre[0]} cy={centre[1]} r={r} fill="none" stroke="#ffd23f" strokeWidth={4} opacity={0.95} />
        </svg>
      ) : null}
      {title ? <div style={{ ...CAPTION, left: 48, top: 36, fontSize: 56, fontWeight: 700 }}>{title.text}</div> : null}
      {speed ? <div style={{ ...CAPTION, right: 48, top: 48, fontSize: 34 }}>{speed.text}</div> : null}
      {contact ? (
        <div style={{ ...CAPTION, left: 48, right: 48, bottom: 40, fontSize: 34, lineHeight: 1.35, padding: "18px 26px", background: "rgba(20,24,32,0.72)", borderRadius: 10 }}>{contact.text}</div>
      ) : null}
    </AbsoluteFill>
  );
};

export const ShotPresentation: React.FC<PresentationProps> = ({ overlays }) => {
  const { width, height, fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const timeline = timelineFor(fps); // throws unless fps is a whole multiple of the presentation fps
  useMemo(() => console.log(`[shot24-check] PASS versions: ${assertShotRenderable().join(", ")}`), []);
  // presentation frame -> source time (explicit timeline) -> physical state (pure evaluator of the same trace)
  const state = useMemo(() => stateAt(sourceAtFrame(timeline, frame).t, frame), [timeline, frame]);
  const cam = useMemo(() => benchmarkCamera(PRESENTATION.camera as keyof typeof CAMERAS, width, height), [width, height]);
  return (
    <AbsoluteFill style={{ backgroundColor: "#a6a6a6" }}>
      <ThreeCanvas width={width} height={height} camera={Object.assign(cam, { manual: true })} orthographic={CAMERAS[PRESENTATION.camera as keyof typeof CAMERAS].kind === "orthographic"} linear={false} flat={false} gl={{ antialias: true, preserveDrawingBuffer: true }}>
        <ShotScene state={state} logTag="shot24" />
      </ThreeCanvas>
      {overlays ? <Overlay frame={frame} timeline={timeline} puckMm={state.puckMm} cam={cam} width={width} height={height} /> : null}
    </AbsoluteFill>
  );
};
