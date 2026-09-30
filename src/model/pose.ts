// Pure, renderer-independent fixture-pose mathematics (iteration 09). World frame: docs/geometry.md
// (mm, +z up, angles counter-clockwise about +z seen from above). Conventions: docs/pose.md.
//
// A figure's state is (u_preview, thetaDeg):
//  - u_preview in [0, 1] is a NORMALISED ARC-LENGTH parameter along the path's preview travel range.
//    It is NOT rod displacement; the rod-to-path mapping and the physical stops are unknown.
//  - thetaDeg is a continuous (unwrapped) rotation about the fixture axis, relative to the team's home
//    heading. It is independent of the path tangent: no coupling is applied without a measurement.

export type Vec2 = [number, number];
export type Vec3 = [number, number, number];

/** 4x4 rigid transform, row-major, acting on column vectors [x, y, z, 1]. */
export type Mat4 = [
  number, number, number, number,
  number, number, number, number,
  number, number, number, number,
  number, number, number, number,
];

export interface PathSampler {
  readonly id: string;
  readonly kind: "skater" | "goalie";
  /** Total arc length of the path polyline (mm). */
  readonly length: number;
  /** Point and unit tangent at arc length s in [0, length]. */
  at(s: number): { point: Vec2; tangent: Vec2 };
}

/** Builds an arc-length sampler over a world polyline (mm). Throws on degenerate input. */
export function pathSampler(id: string, kind: PathSampler["kind"], points: Vec2[]): PathSampler {
  if (points.length < 2) throw new Error(`${id}: path needs at least 2 points`);
  const cum: number[] = [0];
  for (let i = 1; i < points.length; i++) {
    const d = Math.hypot(points[i]![0] - points[i - 1]![0], points[i]![1] - points[i - 1]![1]);
    cum.push(cum[i - 1]! + d);
  }
  const length = cum[cum.length - 1]!;
  if (!(length > 0) || points.some((p) => !Number.isFinite(p[0]) || !Number.isFinite(p[1]))) throw new Error(`${id}: degenerate path`);
  return {
    id,
    kind,
    length,
    at(s: number) {
      // Binary search for the segment containing s (s is validated by the caller).
      let lo = 0, hi = cum.length - 1;
      while (hi - lo > 1) {
        const mid = (lo + hi) >> 1;
        if (cum[mid]! <= s) lo = mid;
        else hi = mid;
      }
      // Skip zero-length segments.
      while (hi < cum.length - 1 && cum[hi]! - cum[lo]! === 0) hi++;
      const a = points[lo]!, b = points[hi]!;
      const segLen = cum[hi]! - cum[lo]!;
      const f = segLen > 0 ? (s - cum[lo]!) / segLen : 0;
      const t: Vec2 = segLen > 0 ? [(b[0] - a[0]) / segLen, (b[1] - a[1]) / segLen] : [1, 0];
      return { point: [a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])], tangent: t };
    },
  };
}

export type Team = "W" | "E";
/** Team home heading (deg): each team's figures face the goal they attack. A proper rotation, not a mirror. */
export const HOME_HEADING_DEG: Record<Team, number> = { W: 0, E: 180 };

export interface FigureState {
  /** Normalised preview arc-length parameter in [0, 1]. NOT rod displacement. */
  u_preview: number;
  /** Continuous rotation about the fixture axis relative to the team home heading (deg, unwrapped). */
  thetaDeg: number;
}

export interface PoseOptions {
  /**
   * Fixture-axis offset from the slot centreline in the path frame [along tangent, left normal] (mm).
   * UNKNOWN physically; the preview default is [0, 0] and is reported as an assumption.
   */
  fixtureOffsetMm?: Vec2;
  /** Height of the fixture-local origin above the ice top surface (mm); preview default 0. */
  originHeightMm?: number;
}

export interface Pose {
  ok: true;
  pathId: string;
  kind: PathSampler["kind"];
  team: Team;
  state: FigureState;
  /** Fixture axis position on the ice plane (mm). */
  pivot: Vec3;
  /** World heading of the figure's local +x axis (deg, unwrapped: home heading + thetaDeg). */
  headingDeg: number;
  /** Local (pivot frame) -> world rigid transform. */
  matrix: Mat4;
  /** Slot tangent at the pivot (for reference only; rotation does NOT follow it). */
  pathTangent: Vec2;
  assumptions: string[];
}

export interface InvalidPose {
  ok: false;
  pathId: string;
  reason: string;
}

export const PREVIEW_ASSUMPTIONS = {
  axis: "assume.fixture_axis_on_slot_centreline",
  travel: "u_preview spans the visible slot centreline (not measured stops)",
} as const;

function invalid(pathId: string, reason: string): InvalidPose {
  return { ok: false, pathId, reason };
}

/** Rotation about +z by `deg` combined with translation, as a 4x4 matrix. */
export function rigid(deg: number, t: Vec3): Mat4 {
  const r = (deg * Math.PI) / 180;
  const c = Math.cos(r), s = Math.sin(r);
  return [c, -s, 0, t[0], s, c, 0, t[1], 0, 0, 1, t[2], 0, 0, 0, 1];
}

export function transformPoint(m: Mat4, p: Vec3): Vec3 {
  return [
    m[0] * p[0] + m[1] * p[1] + m[2] * p[2] + m[3],
    m[4] * p[0] + m[5] * p[1] + m[6] * p[2] + m[7],
    m[8] * p[0] + m[9] * p[1] + m[10] * p[2] + m[11],
  ];
}

/** Determinant of the 3x3 linear part (+1 for a proper rotation; -1 would be a mirror). */
export function linearDeterminant(m: Mat4): number {
  return m[0] * (m[5] * m[10] - m[6] * m[9]) - m[1] * (m[4] * m[10] - m[6] * m[8]) + m[2] * (m[4] * m[9] - m[5] * m[8]);
}

function pose(path: PathSampler, team: Team, state: FigureState, opts: PoseOptions): Pose | InvalidPose {
  if (!Number.isFinite(state.u_preview)) return invalid(path.id, "u_preview is not a finite number");
  if (state.u_preview < 0 || state.u_preview > 1) return invalid(path.id, `u_preview ${state.u_preview} outside [0, 1]; not clamped`);
  if (!Number.isFinite(state.thetaDeg)) return invalid(path.id, "thetaDeg is not a finite number");
  const off = opts.fixtureOffsetMm ?? [0, 0];
  const h = opts.originHeightMm ?? 0;
  if (!off.every(Number.isFinite) || !Number.isFinite(h)) return invalid(path.id, "non-finite fixture offset or origin height");
  const { point, tangent } = path.at(state.u_preview * path.length);
  const left: Vec2 = [-tangent[1], tangent[0]];
  const pivot: Vec3 = [point[0] + off[0] * tangent[0] + off[1] * left[0], point[1] + off[0] * tangent[1] + off[1] * left[1], h];
  const headingDeg = HOME_HEADING_DEG[team] + state.thetaDeg;
  const assumptions: string[] = [PREVIEW_ASSUMPTIONS.travel];
  if (opts.fixtureOffsetMm === undefined) assumptions.push(PREVIEW_ASSUMPTIONS.axis);
  return { ok: true, pathId: path.id, kind: path.kind, team, state: { ...state }, pivot, headingDeg, matrix: rigid(headingDeg, pivot), pathTangent: tangent, assumptions };
}

/** Pose of an outfield skater. Rejects goalie paths. */
export function skaterPose(path: PathSampler, team: Team, state: FigureState, opts: PoseOptions = {}): Pose | InvalidPose {
  if (path.kind !== "skater") return invalid(path.id, "skaterPose called with a goalie path");
  return pose(path, team, state, opts);
}

/**
 * Pose of a goalie: its own adapter. Uses the goalie's own path and asset frame; rejects skater paths.
 * Goalie rotation limits and its fixture offset are unknown (same flags as skaters, kept separate so
 * goalie-specific constraints can be added without touching skaters).
 */
export function goaliePose(path: PathSampler, team: Team, state: FigureState, opts: PoseOptions = {}): Pose | InvalidPose {
  if (path.kind !== "goalie") return invalid(path.id, "goaliePose called with a skater path");
  return pose(path, team, state, opts);
}

/** Maps pivot-local points (mm) to world (mm) for a valid pose. */
export function toWorld(p: Pose, local: Vec3[]): Vec3[] {
  return local.map((q) => transformPoint(p.matrix, q));
}

/**
 * Unwraps a sequence of angles (deg) so consecutive values never jump by more than 180 deg.
 * Keeps rotation continuous through 360 deg (e.g. 350, 10 -> 350, 370).
 */
export function unwrapDeg(seq: number[]): number[] {
  const out: number[] = [];
  for (const a of seq) {
    if (out.length === 0) { out.push(a); continue; }
    const prev = out[out.length - 1]!;
    let d = a - prev;
    d -= 360 * Math.round(d / 360);
    out.push(prev + d);
  }
  return out;
}
