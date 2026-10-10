// Camera choreography for analysis videos: a pure function of the presentation frame, separate from the shot
// timeline (which source time is shown). A freeze therefore holds the physical scene still while the camera may move,
// and the camera can stand still while the shot plays. Views are in world millimetres (z up).
import type { Vec3 } from "./pose.ts";

export interface CameraView {
  positionMm: Vec3;
  targetMm: Vec3;
  /** vertical field of view (deg) */
  fovDeg: number;
}

export interface CameraKey {
  /** presentation time (s) */
  t: number;
  view: string;
  /** extra height (mm) at the middle of the move that ENDS at this key (sin-shaped, zero at both ends) */
  lift?: number;
}

export interface CameraState extends CameraView {
  /** "hold" while the camera stands still, "move" during a transition */
  mode: "hold" | "move";
}

/** Smooth ease-in-out (quintic smootherstep): zero velocity and acceleration at both ends. */
export function ease(x: number): number {
  const u = Math.min(1, Math.max(0, x));
  return u * u * u * (u * (u * 6 - 15) + 10);
}

const lerp = (a: number, b: number, u: number): number => a + (b - a) * u;
const lerp3 = (a: Vec3, b: Vec3, u: number): Vec3 => [lerp(a[0], b[0], u), lerp(a[1], b[1], u), lerp(a[2], b[2], u)];

/**
 * Camera at presentation time t. Between two keys with the same view the camera holds; with different views it moves
 * with smootherstep easing. Position and target are blended in a cylindrical frame around the moving target, so a move
 * between two sides of the rink arcs around the action instead of cutting through it.
 */
export function cameraAt(views: Record<string, CameraView>, keys: CameraKey[], t: number): CameraState {
  if (!keys.length) throw new Error("camera track has no keys");
  for (let i = 1; i < keys.length; i++) if (!(keys[i]!.t >= keys[i - 1]!.t)) throw new Error("camera keys must be in time order");
  const view = (id: string): CameraView => {
    const v = views[id];
    if (!v) throw new Error(`unknown camera view ${id}`);
    return v;
  };
  if (t <= keys[0]!.t) return { ...view(keys[0]!.view), mode: "hold" };
  const last = keys[keys.length - 1]!;
  if (t >= last.t) return { ...view(last.view), mode: "hold" };
  let i = 0;
  while (!(t >= keys[i]!.t && t < keys[i + 1]!.t)) i++;
  const a = keys[i]!, b = keys[i + 1]!;
  const va = view(a.view), vb = view(b.view);
  if (a.view === b.view) return { ...va, mode: "hold" };
  const u = ease((t - a.t) / (b.t - a.t));
  const target = lerp3(va.targetMm, vb.targetMm, u);
  // cylindrical blend of the camera offset around the target: radius, azimuth (shorter way) and height
  const off = (v: CameraView): [number, number, number] => {
    const dx = v.positionMm[0] - v.targetMm[0], dy = v.positionMm[1] - v.targetMm[1];
    return [Math.hypot(dx, dy), Math.atan2(dy, dx), v.positionMm[2] - v.targetMm[2]];
  };
  const [ra, aa, ha] = off(va), [rb, ab, hb] = off(vb);
  let da = ab - aa;
  da -= 2 * Math.PI * Math.round(da / (2 * Math.PI));
  const r = lerp(ra, rb, u), az = aa + da * u, h = lerp(ha, hb, u) + (b.lift ?? 0) * Math.sin(Math.PI * u);
  const position: Vec3 = [target[0] + r * Math.cos(az), target[1] + r * Math.sin(az), target[2] + h];
  return { positionMm: position, targetMm: target, fovDeg: lerp(va.fovDeg, vb.fovDeg, u), mode: "move" };
}
