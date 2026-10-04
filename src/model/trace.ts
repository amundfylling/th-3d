// Evaluation of a saved shot trace (data/traces/*.trace.json, schema "shot-trace/1") at source time t.
// Pure and frame-order independent: every call interpolates the stored keyframes and nodes, nothing is
// integrated or cached. Mirrors scripts/shot22-trace.py, which writes evaluation_samples for cross-checking.
// Figure pose from (arc_mm, theta_deg) follows docs/pose.md (src/model/pose.ts).

export interface ArcKeyframe {
  t: number;
  arc_mm: number;
  sigma_mm: number | null;
  source: string;
}

export interface ThetaKeyframe {
  t: number;
  theta_deg: number;
  sigma_deg: number | null;
  source: string;
}

export interface TraceFigure {
  player_id: string;
  team: "W" | "E";
  fixture_path_id: string;
  status: string;
  arc_keyframes: ArcKeyframe[];
  theta_keyframes: ThetaKeyframe[];
}

export interface PuckNode {
  t: number;
  x_mm: number;
  y_mm: number;
  phase: string;
}

export interface ShotTrace {
  schema: "shot-trace/1";
  trace_id: string;
  status: "proposed" | "accepted";
  geometry_version: string;
  figures: Record<string, TraceFigure | string>;
  puck: { radius_mm: number; nodes: PuckNode[]; phases: { id: string; t: [number, number | null] }[] };
}

export interface TraceState {
  t: number;
  figures: Record<string, { arc_mm: number; theta_deg: number }>;
  puck: { x_mm: number; y_mm: number; phase: string | null };
}

function endSlope(h0: number, h1: number, d0: number, d1: number): number {
  const m = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1);
  if (m * d0 <= 0) return 0;
  if (d0 * d1 <= 0 && Math.abs(m) > Math.abs(3 * d0)) return 3 * d0;
  return m;
}

/** Fritsch-Carlson slopes of the monotone piecewise cubic Hermite interpolant (as scipy PCHIP). */
export function pchipSlopes(x: number[], y: number[]): number[] {
  const n = x.length;
  const h = x.slice(1).map((v, i) => v - x[i]!);
  const d = h.map((hi, i) => (y[i + 1]! - y[i]!) / hi);
  if (n === 2) return [d[0]!, d[0]!];
  const m = new Array<number>(n).fill(0);
  for (let i = 1; i < n - 1; i++) {
    const dl = d[i - 1]!;
    const dr = d[i]!;
    if (dl * dr <= 0) continue;
    const w1 = 2 * h[i]! + h[i - 1]!;
    const w2 = h[i]! + 2 * h[i - 1]!;
    m[i] = (w1 + w2) / (w1 / dl + w2 / dr);
  }
  m[0] = endSlope(h[0]!, h[1]!, d[0]!, d[1]!);
  m[n - 1] = endSlope(h[n - 2]!, h[n - 3]!, d[n - 2]!, d[n - 3]!);
  return m;
}

/** Index i with x[i] < t <= x[i+1] (x strictly increasing, x[0] < t < x[n-1]). */
function segment(x: number[], t: number): number {
  let lo = 0;
  let hi = x.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (x[mid]! < t) lo = mid;
    else hi = mid;
  }
  return lo;
}

export function pchipEval(x: number[], y: number[], m: number[], t: number): number {
  if (x.length === 1 || t <= x[0]!) return y[0]!;
  if (t >= x[x.length - 1]!) return y[y.length - 1]!;
  const i = segment(x, t);
  const x0 = x[i]!;
  const h = x[i + 1]! - x0;
  const s = (t - x0) / h;
  const s2 = s * s;
  const s3 = s2 * s;
  return (2 * s3 - 3 * s2 + 1) * y[i]! + (s3 - 2 * s2 + s) * h * m[i]! + (-2 * s3 + 3 * s2) * y[i + 1]! + (s3 - s2) * h * m[i + 1]!;
}

/** Piecewise linear, held constant outside the nodes. */
export function linEval(x: number[], y: number[], t: number): number {
  if (x.length === 1 || t <= x[0]!) return y[0]!;
  if (t >= x[x.length - 1]!) return y[y.length - 1]!;
  const i = segment(x, t);
  const y0 = y[i]!;
  return y0 + ((y[i + 1]! - y0) * (t - x[i]!)) / (x[i + 1]! - x[i]!);
}

/** Precomputes the arc slopes once; the returned evaluator is a pure function of t. */
export function traceEvaluator(trace: ShotTrace): (t: number) => TraceState {
  if (trace.schema !== "shot-trace/1") throw new Error(`unsupported trace schema ${trace.schema}`);
  const figs = Object.entries(trace.figures)
    .filter((e): e is [string, TraceFigure] => typeof e[1] === "object")
    .map(([pid, f]) => {
      const ax = f.arc_keyframes.map((k) => k.t);
      const ay = f.arc_keyframes.map((k) => k.arc_mm);
      for (let i = 1; i < ax.length; i++) if (!(ax[i]! > ax[i - 1]!)) throw new Error(`${pid}: arc keyframe times not increasing`);
      return { pid, ax, ay, am: ax.length > 1 ? pchipSlopes(ax, ay) : [0], tx: f.theta_keyframes.map((k) => k.t), ty: f.theta_keyframes.map((k) => k.theta_deg) };
    });
  const px = trace.puck.nodes.map((n) => n.t);
  const pxv = trace.puck.nodes.map((n) => n.x_mm);
  const pyv = trace.puck.nodes.map((n) => n.y_mm);
  const phases = trace.puck.phases;
  return (t: number) => {
    const figures: TraceState["figures"] = {};
    for (const f of figs) figures[f.pid] = { arc_mm: pchipEval(f.ax, f.ay, f.am, t), theta_deg: linEval(f.tx, f.ty, t) };
    const ph = phases.find((p) => t >= p.t[0] && (p.t[1] === null || t < p.t[1])) ?? null;
    return { t, figures, puck: { x_mm: linEval(px, pxv, t), y_mm: linEval(px, pyv, t), phase: ph ? ph.id : null } };
  };
}
