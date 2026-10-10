// Iteration 23: plays the accepted shot trace with a fixed overhead camera on a plain background.
// Physical time comes only from the frame: t = startS + useCurrentFrame() / fps. Each frame sets every
// trace-driven node to an absolute pose computed by the pure evaluator (src/model/shot-pose.ts); nothing is
// accumulated between frames, no useFrame() and no wall clock, so frames can render in any order.
import { ThreeCanvas } from "@remotion/three";
import { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import geometry from "../data/geometry.json" with { type: "json" };
import traceJson from "../data/traces/shovel-17.trace.json" with { type: "json" };
import contactChecks from "../shots/22-shovel/checks.json" with { type: "json" };
import { checkTraceCompatibility, shotFrameEvaluator, type AssetManifest } from "../src/model/shot-pose.ts";
import type { ShotTrace } from "../src/model/trace.ts";
import manifest from "./asset-manifest.json" with { type: "json" };
import { SHOT_CAMERA, toThree } from "./cameras.ts";
import { ShotScene } from "./ShotScene.tsx";

export const SHOT_TRACE = traceJson as unknown as ShotTrace & { time_base: { window_s: [number, number] }; asset_refs: Record<string, unknown>; trace_id: string };

/** Rejects mismatched geometry/asset versions and unaccepted traces (throws; the render fails). */
export function assertShotRenderable(): string[] {
  const compared = checkTraceCompatibility(SHOT_TRACE, geometry.geometry_version, manifest as AssetManifest);
  if (SHOT_TRACE.status !== "accepted") throw new Error(`trace ${SHOT_TRACE.trace_id} is ${SHOT_TRACE.status}, not accepted`);
  // CLAUDE.md "Contact physics": only a trace whose finite-puck contact check passed is played
  if (contactChecks.trace_id !== SHOT_TRACE.trace_id) throw new Error(`contact checks are for ${contactChecks.trace_id}, not ${SHOT_TRACE.trace_id}`);
  if (contactChecks.unexpected_penetrations.length > 0) throw new Error(`trace ${SHOT_TRACE.trace_id} overlaps geometry: ${JSON.stringify(contactChecks.unexpected_penetrations)}`);
  return [...compared, "contact_checks"];
}

const evaluate = shotFrameEvaluator(SHOT_TRACE, geometry as Parameters<typeof shotFrameEvaluator>[1]);

export type ShotProps = {
  /** Source time (s) shown at frame 0. Default: the trace window start. */
  startS: number;
};

export const ShotPlayback: React.FC<ShotProps> = ({ startS }) => {
  const { width, height, fps } = useVideoConfig();
  const frame = useCurrentFrame();
  // physical time from the frame only; absolute state for this frame
  const state = useMemo(() => evaluate(frame, fps, startS), [frame, fps, startS]);
  useMemo(() => console.log(`[shot23-check] PASS versions: ${assertShotRenderable().join(", ")}`), []);
  const cam = useMemo(() => {
    const halfW = SHOT_CAMERA.fovDegOrWidthMm / 2000;
    const aspect = height / width;
    const c = new THREE.OrthographicCamera(-halfW, halfW, halfW * aspect, -halfW * aspect, 0.01, 20);
    c.position.set(...toThree(SHOT_CAMERA.positionMm));
    c.up.set(0, 0, -1);
    c.lookAt(...toThree(SHOT_CAMERA.targetMm));
    c.updateProjectionMatrix();
    return c;
  }, [width, height]);
  return (
    <AbsoluteFill style={{ backgroundColor: "#a6a6a6" }}>
      <ThreeCanvas width={width} height={height} camera={Object.assign(cam, { manual: true })} orthographic linear={false} flat={false} gl={{ antialias: true, preserveDrawingBuffer: true }}>
        <ShotScene state={state} logTag="shot23" />
      </ThreeCanvas>
    </AbsoluteFill>
  );
};
