// Iteration 23: plays the accepted shot trace with a fixed overhead camera on a plain background.
// Physical time comes only from the frame: t = startS + useCurrentFrame() / fps. Each frame sets every
// trace-driven node to an absolute pose computed by the pure evaluator (src/model/shot-pose.ts); nothing is
// accumulated between frames, no useFrame() and no wall clock, so frames can render in any order.
import { useLoader, useThree } from "@react-three/fiber";
import { ThreeCanvas } from "@remotion/three";
import { useLayoutEffect, useMemo, useState } from "react";
import { AbsoluteFill, cancelRender, staticFile, useCurrentFrame, useDelayRender, useVideoConfig } from "remotion";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import geometry from "../data/geometry.json" with { type: "json" };
import traceJson from "../data/traces/shovel-17.trace.json" with { type: "json" };
import contactChecks from "../shots/22-shovel/checks.json" with { type: "json" };
import { gltfMToWorldMm, worldMatrixToGltf } from "../src/model/coordinates.ts";
import { checkTraceCompatibility, shotFrameEvaluator, type AssetManifest } from "../src/model/shot-pose.ts";
import type { ShotTrace } from "../src/model/trace.ts";
import manifest from "./asset-manifest.json" with { type: "json" };
import { SHOT_CAMERA, toThree } from "./cameras.ts";

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

const find = (root: THREE.Object3D, name: string): THREE.Object3D => {
  const o = root.getObjectByName(THREE.PropertyBinding.sanitizeNodeName(name));
  if (!o) throw new Error(`node ${name} not in the scene`);
  return o;
};

const r4 = (v: number): number => Math.round(v * 1e4) / 1e4;

const Scene: React.FC<{ startS: number }> = ({ startS }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const gltf = useLoader(GLTFLoader, staticFile("full_static_appearance.glb"));
  const { gl } = useThree();
  useMemo(() => {
    const pm = new THREE.PMREMGenerator(gl);
    const env = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    pm.dispose();
    gltf.scene.traverse((o) => {
      const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
      if (m && "envMap" in m && m.name.startsWith("fig_")) {
        m.envMap = env;
        m.envMapIntensity = m.metalness > 0.5 ? 1.0 : 0.12;
        m.needsUpdate = true;
      }
    });
  }, [gl, gltf]);

  // The loaded GLB must be the one in the manifest (hash of the bytes actually served).
  const { delayRender, continueRender } = useDelayRender();
  const [hashHandle] = useState(() => delayRender("scene GLB hash"));
  useLayoutEffect(() => {
    fetch(staticFile("full_static_appearance.glb"))
      .then((r) => r.arrayBuffer())
      .then((b) => crypto.subtle.digest("SHA-256", b))
      .then((d) => {
        const hex = [...new Uint8Array(d)].map((x) => x.toString(16).padStart(2, "0")).join("");
        if (hex !== manifest.scene_glb.sha256) throw new Error(`scene GLB ${hex.slice(0, 12)}... differs from the manifest ${manifest.scene_glb.sha256.slice(0, 12)}...`);
        console.log(`[shot23-check] PASS scene GLB sha256 ${hex.slice(0, 12)}...`);
        continueRender(hashHandle);
      })
      .catch((e: unknown) => cancelRender(e instanceof Error ? e : new Error(String(e))));
  }, [continueRender, hashHandle]);

  const nodes = useMemo(() => {
    const figs = Object.fromEntries(Object.keys(evaluate(0, fps, startS).figures).map((pid) => [pid, find(gltf.scene, `Figure.${pid}`)]));
    return { figs, puck: find(gltf.scene, "Puck") };
  }, [gltf, fps, startS]);

  // Absolute pose for this frame, applied before R3F draws it (ThreeCanvas advances in a later effect).
  useLayoutEffect(() => {
    const s = evaluate(frame, fps, startS);
    const m = new THREE.Matrix4();
    for (const [pid, f] of Object.entries(s.figures)) {
      const node = nodes.figs[pid]!;
      m.set(...worldMatrixToGltf(f.matrix));
      m.decompose(node.position, node.quaternion, node.scale);
    }
    nodes.puck.position.set(...toThree(s.puckMm));
    gltf.scene.updateMatrixWorld(true);
    // Read back what will be drawn and log it next to the pure state (checked by scripts/shot23-render.ts).
    const readback: Record<string, number[]> = {};
    let worst = 0;
    for (const [pid, f] of Object.entries(s.figures)) {
      const e = nodes.figs[pid]!.matrixWorld.elements;
      const p = gltfMToWorldMm([e[12]!, e[13]!, e[14]!]);
      // local +x (facing) in three = column 0; world heading = atan2(-Z, X)
      const heading = (Math.atan2(-e[2]!, e[0]!) * 180) / Math.PI;
      const dh = (((heading - f.headingDeg) % 360) + 540) % 360 - 180;
      worst = Math.max(worst, Math.hypot(p[0] - f.pivotMm[0], p[1] - f.pivotMm[1], p[2] - f.pivotMm[2]), Math.abs(dh));
      readback[pid] = [r4(f.arcMm), r4(f.thetaDeg), r4(f.pivotMm[0]), r4(f.pivotMm[1]), r4(f.headingDeg)];
    }
    const pe = nodes.puck.matrixWorld.elements;
    const pp = gltfMToWorldMm([pe[12]!, pe[13]!, pe[14]!]);
    worst = Math.max(worst, Math.hypot(pp[0] - s.puckMm[0], pp[1] - s.puckMm[1]));
    console.log(`[shot23-state] ${JSON.stringify({ frame, t: r4(s.t), figures: readback, puck: [r4(s.puckMm[0]), r4(s.puckMm[1])], phase: s.puckPhase, readback_max_diff: Number(worst.toExponential(2)) })}`);
    if (worst > 1e-3) cancelRender(new Error(`frame ${frame}: scene readback differs from the pure state by ${worst}`));
  }, [frame, fps, startS, nodes, gltf]);

  return (
    <>
      <hemisphereLight args={["#ffffff", "#8c8c8c", 1.1]} />
      <directionalLight position={toThree([600, -350, 900])} intensity={2.2} />
      <primitive object={gltf.scene} />
    </>
  );
};

export const ShotPlayback: React.FC<ShotProps> = ({ startS }) => {
  const { width, height } = useVideoConfig();
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
        <Scene startS={startS} />
      </ThreeCanvas>
    </AbsoluteFill>
  );
};
