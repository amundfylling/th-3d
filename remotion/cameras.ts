// Inspection cameras defined in canonical world millimetres (z up) and converted ONCE with the project
// adapter (src/model/coordinates.ts). Matches the Blender benchmark cameras of iterations 16-18.
import { worldMmToGltfM } from "../src/model/coordinates.ts";
import type { Vec3 } from "../src/model/pose.ts";

export interface InspectionCamera {
  kind: "orthographic" | "perspective";
  positionMm: Vec3;
  targetMm: Vec3;
  /** Perspective: vertical field of view (deg). Orthographic: visible width (mm). */
  fovDegOrWidthMm: number;
}

// Blender AsmOblique: 35 mm lens on a 36 mm sensor width, 16:9 -> vertical FOV 2 atan(18 * 9/16 / 35).
const obliqueVFov = (2 * Math.atan((18 * 9) / 16 / 35) * 180) / Math.PI;

export const CAMERAS: Record<"overhead" | "side" | "oblique", InspectionCamera> = {
  overhead: { kind: "orthographic", positionMm: [0, 0, 1000], targetMm: [0, 0, 0], fovDegOrWidthMm: 931.2 },
  side: { kind: "perspective", positionMm: [0, -900, 120], targetMm: [0, 0, 20], fovDegOrWidthMm: 28 },
  oblique: { kind: "perspective", positionMm: [120, -700, 430], targetMm: [0, -20, 0], fovDegOrWidthMm: obliqueVFov },
};

export const toThree = (p: Vec3): [number, number, number] => worldMmToGltfM(p);
