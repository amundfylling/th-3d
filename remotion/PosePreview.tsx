// Diagnostic still: the rink with chosen figures at fixed poses (slot arc + rotation) and the puck at a point, seen
// straight from above (orthographic). Used for interpretation sketches before a trace exists (scripts/ikv-sketch-render.ts).
// The pose goes through the same pure pose code as every trace (shotTimeEvaluator on a one-keyframe in-memory trace).
import { ThreeCanvas } from "@remotion/three";
import { useMemo, useState } from "react";
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
  camera: { cx: number; cy: number; widthMm: number };
};

export const PosePreview: React.FC<PosePreviewProps> = ({ poses, puckMm, camera }) => {
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
    const halfW = camera.widthMm / 2000, aspect = height / width;
    const c = new THREE.OrthographicCamera(-halfW, halfW, halfW * aspect, -halfW * aspect, 0.01, 20);
    c.position.set(...toThree([camera.cx, camera.cy, 1000]));
    c.up.set(0, 0, -1);
    c.lookAt(...toThree([camera.cx, camera.cy, 0]));
    c.updateProjectionMatrix();
    return Object.assign(c, { manual: true });
  });
  return (
    <AbsoluteFill style={{ backgroundColor: "#1b212b" }}>
      <ThreeCanvas width={width} height={height} camera={cam} orthographic linear={false} flat={false} gl={{ antialias: true, preserveDrawingBuffer: true }}>
        <ShotScene state={state} logTag="pose-preview" />
      </ThreeCanvas>
    </AbsoluteFill>
  );
};
