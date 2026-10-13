// The 3D layer of the analysis videos: background, canvas, camera and the posed rink scene (remotion/ShotScene.tsx),
// and nothing of the captions or graphics drawn above it. Two ways to fill the layer, chosen per render:
//   - SceneLayer:       rendered live in WebGL for this frame (the direct renderer, the reference);
//   - CachedSceneLayer: a lossless PNG of the same layer rendered earlier for an identical scene state
//                       (scripts/video/scene-cache.ts). The PNG was made by SceneLayer itself, so the two are the same pixels.
// The scene-cache key hashes this file: any change here invalidates every cached scene image.
import { useThree } from "@react-three/fiber";
import { ThreeCanvas } from "@remotion/three";
import { useLayoutEffect, useState } from "react";
import { AbsoluteFill, Img } from "remotion";
import * as THREE from "three";
import type { CameraView } from "../src/model/camera-track.ts";
import type { ShotFrameState } from "../src/model/shot-pose.ts";
import { toThree } from "./cameras.ts";
import { ShotScene } from "./ShotScene.tsx";

export function makeCamera(v: CameraView, width: number, height: number, cam = new THREE.PerspectiveCamera()): THREE.PerspectiveCamera {
  cam.fov = v.fovDeg;
  cam.aspect = width / height;
  cam.near = 0.004;
  cam.far = 10;
  cam.up.set(0, 1, 0);
  cam.position.set(...toThree(v.positionMm));
  cam.lookAt(...toThree(v.targetMm));
  cam.updateProjectionMatrix();
  cam.updateMatrixWorld(true);
  return cam;
}

/** Sets the canvas camera for this frame (absolute, from the camera track). */
const CameraRig: React.FC<{ view: CameraView; frame: number; tag: string }> = ({ view, frame, tag }) => {
  const { camera, size } = useThree();
  useLayoutEffect(() => {
    const c = makeCamera(view, size.width, size.height, camera as THREE.PerspectiveCamera);
    // read back the canvas camera (glTF metres -> world mm) so the export can compare it with the pure camera track
    const mm = (x: number, y: number, z: number): number[] => [x * 1000, -z * 1000, y * 1000].map((v) => Math.round(v * 100) / 100);
    console.log(`[${tag}-camera] ${JSON.stringify({ frame, position: mm(c.position.x, c.position.y, c.position.z), fov: Math.round(c.fov * 1e4) / 1e4 })}`);
  }, [view, camera, size, frame, tag]);
  return null;
};

/** Live WebGL scene layer: the background and the rink posed from the pure state, seen from the pure camera. */
export const SceneLayer: React.FC<{ state: ShotFrameState; view: CameraView; frame: number; tag: string; background: string; width: number; height: number }> = ({ state, view, frame, tag, background, width, height }) => {
  // one canvas camera for the life of the tab (a new camera object per frame makes the canvas reconfigure and leak)
  const [canvasCamera] = useState(() => Object.assign(new THREE.PerspectiveCamera(), { manual: true }));
  return (
    <AbsoluteFill style={{ background }}>
      <ThreeCanvas width={width} height={height} camera={canvasCamera} linear={false} flat={false} gl={{ antialias: true, preserveDrawingBuffer: true, alpha: true }}>
        <CameraRig view={view} frame={frame} tag={tag} />
        <ShotScene state={state} logTag={tag} />
      </ThreeCanvas>
    </AbsoluteFill>
  );
};

/** Cached scene layer: the PNG SceneLayer rendered for this frame's scene state, shown 1:1 (logged as [<tag>-cached]). */
export const CachedSceneLayer: React.FC<{ src: string; frame: number; tag: string; width: number; height: number }> = ({ src, frame, tag, width, height }) => {
  useLayoutEffect(() => console.log(`[${tag}-cached] ${JSON.stringify({ frame, src })}`), [src, frame, tag]);
  return (
    <AbsoluteFill>
      <Img src={src} style={{ position: "absolute", left: 0, top: 0, width, height }} />
    </AbsoluteFill>
  );
};
