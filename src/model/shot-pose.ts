// Frame -> physical state of a saved shot trace (iteration 23). Pure: the state at a frame depends only on
// (trace, geometry, frame, fps, start time). Nothing is integrated, cached across frames or read from a clock.
// Figure poses use the canonical pose functions (src/model/pose.ts): pivot on the slot centreline at the trace's
// arc length, heading = team home + continuous theta (a plain rotation matrix, never a quaternion blend, so
// there is no shortest-path reversal through zero).
import { traceEvaluator, type ShotTrace, type TraceFigure } from "./trace.ts";
import { goaliePose, pathSampler, skaterPose, type Mat4, type PathSampler, type Team, type Vec2, type Vec3 } from "./pose.ts";

export interface FigurePoseState {
  arcMm: number;
  thetaDeg: number;
  headingDeg: number;
  pivotMm: Vec3;
  matrix: Mat4;
}

export interface ShotFrameState {
  frame: number;
  /** Source time (s, recording presentation time) evaluated for this frame. */
  t: number;
  figures: Record<string, FigurePoseState>;
  /** Puck bottom centre on the ice (mm). */
  puckMm: Vec3;
  puckPhase: string | null;
}

interface GeometryLike {
  geometry_version: string;
  fixture_paths: { id: string; player_id: string; centreline: { points_mm: number[][] } }[];
}

/** Source time of a frame: start + frame / fps. The only time base of the shot. */
export function sourceTimeForFrame(frame: number, fps: number, startS: number): number {
  if (!Number.isInteger(frame) || frame < 0) throw new Error(`frame ${frame} must be a non-negative integer`);
  if (!(fps > 0)) throw new Error(`fps ${fps} must be positive`);
  return startS + frame / fps;
}

/** Number of frames that covers the trace window [start, end] at fps (both ends included). */
export function framesForWindow(window: [number, number], fps: number): number {
  return Math.floor((window[1] - window[0]) * fps + 1e-9) + 1;
}

export interface AssetManifest {
  geometry_version: string;
  /** SHA-256 of the files the trace's asset_refs name, by the same keys. */
  asset_sha256: Record<string, string>;
}

/**
 * Rejects a trace whose geometry or asset versions differ from the scene being rendered. Returns the list of
 * compared items; throws with every mismatch named.
 */
export function checkTraceCompatibility(trace: { geometry_version: string; asset_refs: Record<string, unknown> }, geometryVersion: string, manifest: AssetManifest): string[] {
  const errors: string[] = [];
  const compared: string[] = [];
  if (trace.geometry_version !== geometryVersion) errors.push(`geometry_version: trace ${trace.geometry_version}, scene ${geometryVersion}`);
  if (manifest.geometry_version !== geometryVersion) errors.push(`geometry_version: manifest ${manifest.geometry_version}, scene ${geometryVersion}`);
  compared.push("geometry_version");
  for (const [k, v] of Object.entries(trace.asset_refs)) {
    if (!k.endsWith("_sha256")) continue;
    const cur = manifest.asset_sha256[k];
    if (cur === undefined) errors.push(`${k}: not in the asset manifest`);
    else if (cur !== v) errors.push(`${k}: trace ${String(v).slice(0, 12)}..., current ${cur.slice(0, 12)}...`);
    compared.push(k);
  }
  if (compared.length < 2) errors.push("trace names no asset hashes");
  if (errors.length) throw new Error(`trace ${String((trace as { trace_id?: string }).trace_id)} does not match the scene: ${errors.join("; ")}`);
  return compared;
}

/** Builds a pure frame evaluator for a trace on the canonical geometry. */
export function shotFrameEvaluator(trace: ShotTrace, geometry: GeometryLike): (frame: number, fps: number, startS: number) => ShotFrameState {
  const evalAt = traceEvaluator(trace);
  const figs = Object.entries(trace.figures)
    .filter((e): e is [string, TraceFigure] => typeof e[1] === "object")
    .map(([pid, f]) => {
      const fp = geometry.fixture_paths.find((p) => p.id === f.fixture_path_id);
      if (!fp) throw new Error(`${pid}: fixture path ${f.fixture_path_id} not in the geometry`);
      const kind: PathSampler["kind"] = pid.endsWith("-G") ? "goalie" : "skater";
      return { pid, team: f.team as Team, path: pathSampler(fp.id, kind, fp.centreline.points_mm.map((p) => [p[0]!, p[1]!] as Vec2)) };
    });
  return (frame, fps, startS) => {
    const t = sourceTimeForFrame(frame, fps, startS);
    const st = evalAt(t);
    const figures: Record<string, FigurePoseState> = {};
    for (const f of figs) {
      const s = st.figures[f.pid];
      if (!s) throw new Error(`${f.pid}: no state at t = ${t}`);
      // The trace's arc is held inside the slot by construction; a value outside is an error, not clamped.
      const u = s.arc_mm / f.path.length;
      const state = { u_preview: Math.abs(u - 1) < 1e-9 ? 1 : Math.abs(u) < 1e-9 ? 0 : u, thetaDeg: s.theta_deg };
      const p = f.path.kind === "goalie" ? goaliePose(f.path, f.team, state) : skaterPose(f.path, f.team, state);
      if (!p.ok) throw new Error(`${f.pid} at t = ${t}: ${p.reason}`);
      figures[f.pid] = { arcMm: s.arc_mm, thetaDeg: s.theta_deg, headingDeg: p.headingDeg, pivotMm: p.pivot, matrix: p.matrix };
    }
    return { frame, t, figures, puckMm: [st.puck.x_mm, st.puck.y_mm, 0], puckPhase: st.puck.phase };
  };
}
