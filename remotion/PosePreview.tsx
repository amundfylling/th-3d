// Diagnostic still: the rink with chosen figures at fixed poses (slot arc + rotation) and the puck at a point, seen
// straight from above (orthographic). Used for interpretation sketches before a trace exists (scripts/ikv-sketch-render.ts).
// The pose goes through the same pure pose code as every trace (shotTimeEvaluator on a one-keyframe in-memory trace).
import { ThreeCanvas } from "@remotion/three";
import { useThree } from "@react-three/fiber";
import { useLayoutEffect, useMemo, useState } from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import * as THREE from "three";
import geometry from "../data/geometry.json" with { type: "json" };
import { shotTimeEvaluator } from "../src/model/shot-pose.ts";
import type { ShotTrace } from "../src/model/trace.ts";
import { toThree } from "./cameras.ts";
import { ShotScene } from "./ShotScene.tsx";

export type PosePreviewProps = {
  poses: Record<string, { arc_mm: number; theta_deg: number }>;
  puckMm: [number, number];
  /** Orthographic straight down ({cx, cy, widthMm}) or perspective ({positionMm, targetMm, upMm, fovDeg}, move pictures). */
  camera: { cx: number; cy: number; widthMm: number } | { positionMm: [number, number, number]; targetMm: [number, number, number]; upMm: [number, number, number]; fovDeg: number };
  background?: string;
  /** Figures left out of the still (player ids). */
  hidden?: string[];
};

/** Leaves figures out of the still (move pictures: puck.no draws no figure where an arrow runs through its place).
 * A sibling of ShotScene inside the canvas, so it commits with the loaded scene; this composition is a single still. */
const HideFigures: React.FC<{ ids: string[] }> = ({ ids }) => {
  const { scene } = useThree();
  useLayoutEffect(() => {
    for (const pid of ids) {
      const node = scene.getObjectByName(THREE.PropertyBinding.sanitizeNodeName(`Figure.${pid}`));
      if (!node) throw new Error(`figure ${pid} not in the scene`);
      node.visible = false;
    }
  }, [ids, scene]);
  return null;
};

export const PosePreview: React.FC<PosePreviewProps> = ({ poses, puckMm, camera, background, hidden }) => {
  const { width, height } = useVideoConfig();
  const state = useMemo(() => {
    const figures: ShotTrace["figures"] = {};
    for (const [pid, p] of Object.entries(poses)) {
      figures[pid] = { player_id: pid, team: pid.startsWith("W") ? "W" : "E", fixture_path_id: `path.${pid}`, status: "preview pose",
        arc_keyframes: [{ t: 0, arc_mm: p.arc_mm, sigma_mm: null, source: "preview" }], theta_keyframes: [{ t: 0, theta_deg: p.theta_deg, sigma_deg: null, source: "preview" }] };
    }
    const trace: ShotTrace = { schema: "shot-trace/1", trace_id: "preview", status: "proposed", geometry_version: geometry.geometry_version, figures,
      puck: { radius_mm: 12.7, nodes: [{ t: 0, x_mm: puckMm[0], y_mm: puckMm[1], phase: "preview" }], phases: [] } };
    return shotTimeEvaluator(trace, geometry as Parameters<typeof shotTimeEvaluator>[1])(0, 0);
  }, [poses, puckMm]);
  const [cam] = useState(() => {
    if ("positionMm" in camera) {
      const c = new THREE.PerspectiveCamera(camera.fovDeg, width / height, 0.004, 10);
      const o = new THREE.Vector3(...toThree([0, 0, 0]));
      c.position.set(...toThree(camera.positionMm));
      c.up.copy(new THREE.Vector3(...toThree(camera.upMm)).sub(o).normalize());
      c.lookAt(...toThree(camera.targetMm));
      c.updateProjectionMatrix();
      return Object.assign(c, { manual: true });
    }
    const halfW = camera.widthMm / 2000, aspect = height / width;
    const c = new THREE.OrthographicCamera(-halfW, halfW, halfW * aspect, -halfW * aspect, 0.01, 20);
    c.position.set(...toThree([camera.cx, camera.cy, 1000]));
    c.up.set(0, 0, -1);
    c.lookAt(...toThree([camera.cx, camera.cy, 0]));
    c.updateProjectionMatrix();
    return Object.assign(c, { manual: true });
  });
  return (
    <AbsoluteFill style={{ backgroundColor: background ?? "#1b212b" }}>
      <ThreeCanvas width={width} height={height} camera={cam} orthographic={!("positionMm" in camera)} linear={false} flat={false} gl={{ antialias: true, preserveDrawingBuffer: true }}>
        <ShotScene state={state} logTag="pose-preview" />
        <HideFigures ids={hidden ?? []} />
      </ThreeCanvas>
    </AbsoluteFill>
  );
};
