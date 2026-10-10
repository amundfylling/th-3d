// Shared shot scene (iterations 23-24): the Blender-exported rink with the trace-driven nodes posed from a pure state.
import { useLoader, useThree } from "@react-three/fiber";
import { useLayoutEffect, useMemo, useState } from "react";
import { cancelRender, staticFile, useDelayRender } from "remotion";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { gltfMToWorldMm, worldMatrixToGltf } from "../src/model/coordinates.ts";
import type { ShotFrameState } from "../src/model/shot-pose.ts";
import manifest from "./asset-manifest.json" with { type: "json" };
import { toThree } from "./cameras.ts";

const find = (root: THREE.Object3D, name: string): THREE.Object3D => {
  const o = root.getObjectByName(THREE.PropertyBinding.sanitizeNodeName(name));
  if (!o) throw new Error(`node ${name} not in the scene`);
  return o;
};

export const r4 = (v: number): number => Math.round(v * 1e4) / 1e4;

/**
 * The rink scene with every trace-driven node (W-C, W-RW, E-G, E-RD, E-LD, puck) set to the given physical state.
 * The state is computed by the caller from the frame alone (pure evaluator); this component only applies it, reads it
 * back and logs it (`[<logTag>-state]`). No useFrame, clock or state carried between frames.
 */
export const ShotScene: React.FC<{ state: ShotFrameState; logTag: string }> = ({ state, logTag }) => {
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
        console.log(`[${logTag}-check] PASS scene GLB sha256 ${hex.slice(0, 12)}...`);
        continueRender(hashHandle);
      })
      .catch((e: unknown) => cancelRender(e instanceof Error ? e : new Error(String(e))));
  }, [continueRender, hashHandle, logTag]);

  const pids = Object.keys(state.figures).join(",");
  const nodes = useMemo(() => {
    const figs = Object.fromEntries(pids.split(",").map((pid) => [pid, find(gltf.scene, `Figure.${pid}`)]));
    return { figs, puck: find(gltf.scene, "Puck") };
  }, [gltf, pids]);

  // Absolute pose for this frame, applied before R3F draws it (ThreeCanvas advances in a later effect).
  useLayoutEffect(() => {
    const s = state;
    const frame = s.frame;
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
    console.log(`[${logTag}-state] ${JSON.stringify({ frame, t: r4(s.t), figures: readback, puck: [r4(s.puckMm[0]), r4(s.puckMm[1])], phase: s.puckPhase, readback_max_diff: Number(worst.toExponential(2)) })}`);
    if (worst > 1e-3) cancelRender(new Error(`frame ${frame}: scene readback differs from the pure state by ${worst}`));
  }, [state, logTag, nodes, gltf]);

  return (
    <>
      <hemisphereLight args={["#ffffff", "#8c8c8c", 1.1]} />
      <directionalLight position={toThree([600, -350, 900])} intensity={2.2} />
      <primitive object={gltf.scene} />
    </>
  );
};

