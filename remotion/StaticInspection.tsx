// Static 3D inspection of the Blender-exported scene (iteration 19). No animation: the frame number is not
// used, so every frame renders the same fixed pose. The GLB is local (public/) and loaded with useLoader,
// which suspends; ThreeCanvas holds the render (delayRender) until the Suspense boundary resolves, and the
// scene holds it again until the post-import checks have run.
import { useLoader } from "@react-three/fiber";
import { ThreeCanvas } from "@remotion/three";
import { useEffect, useMemo, useState } from "react";
import { AbsoluteFill, staticFile, useDelayRender, useVideoConfig } from "remotion";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { CAMERAS, toThree } from "./cameras.ts";
import { runImportChecks, type ImportCheck } from "./checks.ts";

// A type alias (not an interface) so it satisfies Remotion's Record<string, unknown> props constraint.
export type InspectionProps = {
  camera: "overhead" | "side" | "oblique";
  showChecks?: boolean;
};

function makeCamera(name: InspectionProps["camera"], width: number, height: number): THREE.OrthographicCamera | THREE.PerspectiveCamera {
  const cam = CAMERAS[name];
  const aspect = height / width;
  const halfW = cam.fovDegOrWidthMm / 2000;
  const c =
    cam.kind === "orthographic"
      ? new THREE.OrthographicCamera(-halfW, halfW, halfW * aspect, -halfW * aspect, 0.01, 20)
      : new THREE.PerspectiveCamera(cam.fovDegOrWidthMm, width / height, 0.01, 20);
  c.position.set(...toThree(cam.positionMm));
  // Overhead: world +y (the reference image's up) stays up on screen; world +y is three -Z.
  if (cam.kind === "orthographic") c.up.set(0, 0, -1);
  else c.up.set(0, 1, 0);
  c.lookAt(...toThree(cam.targetMm));
  c.updateProjectionMatrix();
  return c;
}

const Scene: React.FC<{ onChecks: (c: ImportCheck[]) => void }> = ({ onChecks }) => {
  const gltf = useLoader(GLTFLoader, staticFile("full_static_appearance.glb"));
  const { delayRender, continueRender } = useDelayRender();
  const [handle] = useState(() => delayRender("post-import checks"));
  useEffect(() => {
    onChecks(runImportChecks(gltf.scene));
    continueRender(handle);
  }, [gltf, onChecks, continueRender, handle]);
  return (
    <>
      <hemisphereLight args={["#ffffff", "#8c8c8c", 1.1]} />
      <directionalLight position={toThree([600, -350, 900])} intensity={2.2} />
      <primitive object={gltf.scene} />
    </>
  );
};

export const StaticInspection: React.FC<InspectionProps> = ({ camera, showChecks }) => {
  const { width, height } = useVideoConfig();
  const cam = useMemo(() => makeCamera(camera, width, height), [camera, width, height]);
  const [checks, setChecks] = useState<ImportCheck[]>([]);
  const onChecks = useMemo(
    () => (c: ImportCheck[]) => {
      for (const x of c) console.log(`[import-check] ${x.pass ? "PASS" : "FAIL"} ${x.name}: ${x.detail}`);
      setChecks(c);
    },
    [],
  );
  return (
    <AbsoluteFill style={{ backgroundColor: "#a6a6a6" }}>
      <ThreeCanvas width={width} height={height} camera={Object.assign(cam, { manual: true })} orthographic={CAMERAS[camera].kind === "orthographic"} linear={false} flat={false} gl={{ antialias: true, preserveDrawingBuffer: true }}>
        <Scene onChecks={onChecks} />
      </ThreeCanvas>
      {showChecks ? (
        <div style={{ position: "absolute", left: 24, top: 24, padding: 16, background: "rgba(255,255,255,0.9)", font: "22px monospace", lineHeight: 1.5, maxWidth: width - 48 }}>
          {checks.length === 0 ? "checks not run" : checks.map((c) => <div key={c.name} style={{ color: c.pass ? "#006400" : "#b00000" }}>{`${c.pass ? "PASS" : "FAIL"} ${c.name}: ${c.detail}`}</div>)}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
