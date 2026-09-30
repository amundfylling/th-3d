// The single world -> glTF / Three.js adapter (docs/geometry.md): world is mm, +z up, right-handed;
// glTF/Three is metres, +Y up, right-handed. Applied once at the export/render boundary.
import type { Mat4, Vec3 } from "./pose.ts";

export const MM_PER_M = 1000;

/** World point (mm, z up) -> glTF/Three point (m, Y up): (x, z, -y) / 1000. */
export function worldMmToGltfM([x, y, z]: Vec3): Vec3 {
  return [x / MM_PER_M, z / MM_PER_M, -y / MM_PER_M];
}

/** Inverse of worldMmToGltfM. */
export function gltfMToWorldMm([X, Y, Z]: Vec3): Vec3 {
  return [X * MM_PER_M, -Z * MM_PER_M, Y * MM_PER_M];
}

/** World rotation about +z by `deg` equals a glTF/Three rotation about +Y by the same angle. */
export const worldYawDegToGltfYawDeg = (deg: number): number => deg;

/**
 * Converts a world rigid transform (mm) to glTF/Three (m): M_gltf = C * M_world * C^-1 with the
 * basis change C (a proper rotation plus unit scale, never a mirror).
 */
export function worldMatrixToGltf(m: Mat4): Mat4 {
  // C maps world axes to glTF: x->X, y->-Z, z->Y.
  const C = [1, 0, 0, 0, 0, 1, 0, -1, 0]; // row-major 3x3
  const Ci = [1, 0, 0, 0, 0, -1, 0, 1, 0];
  const R = [m[0], m[1], m[2], m[4], m[5], m[6], m[8], m[9], m[10]];
  const mul = (a: number[], b: number[]): number[] =>
    [0, 1, 2].flatMap((i) => [0, 1, 2].map((j) => a[i * 3]! * b[j]! + a[i * 3 + 1]! * b[3 + j]! + a[i * 3 + 2]! * b[6 + j]!));
  const Rg = mul(mul(C, R), Ci);
  const t = worldMmToGltfM([m[3], m[7], m[11]]);
  return [Rg[0]!, Rg[1]!, Rg[2]!, t[0], Rg[3]!, Rg[4]!, Rg[5]!, t[1], Rg[6]!, Rg[7]!, Rg[8]!, t[2], 0, 0, 0, 1];
}
