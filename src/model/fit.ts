// Small robust 2D fitting helpers for image traces (pixel units in, pixel units out).

export type Vec2 = [number, number];

export interface Line {
  /** A point on the line (centroid of inliers). */
  point: Vec2;
  /** Unit direction. */
  dir: Vec2;
  /** Unit normal (dir rotated +90 deg). */
  normal: Vec2;
}

export interface Circle {
  centre: Vec2;
  radius: number;
}

export interface RobustFit<M> {
  model: M;
  inliers: number[];
  outliers: number[];
  rms: number;
  maxAbs: number;
}

export const signedDistanceToLine = (l: Line, p: Vec2): number =>
  (p[0] - l.point[0]) * l.normal[0] + (p[1] - l.point[1]) * l.normal[1];

export const distanceToCircle = (c: Circle, p: Vec2): number => Math.hypot(p[0] - c.centre[0], p[1] - c.centre[1]) - c.radius;

/** Total-least-squares line through the points. */
export function fitLine(points: Vec2[]): Line {
  const n = points.length;
  if (n < 2) throw new Error("fitLine needs at least 2 points");
  let mx = 0;
  let my = 0;
  for (const [x, y] of points) {
    mx += x / n;
    my += y / n;
  }
  let sxx = 0;
  let sxy = 0;
  let syy = 0;
  for (const [x, y] of points) {
    sxx += (x - mx) ** 2;
    sxy += (x - mx) * (y - my);
    syy += (y - my) ** 2;
  }
  const angle = 0.5 * Math.atan2(2 * sxy, sxx - syy);
  const dir: Vec2 = [Math.cos(angle), Math.sin(angle)];
  return { point: [mx, my], dir, normal: [-dir[1], dir[0]] };
}

/** Algebraic (Kasa) circle fit followed by Gauss-Newton refinement of the geometric error. */
export function fitCircle(points: Vec2[]): Circle {
  const n = points.length;
  if (n < 3) throw new Error("fitCircle needs at least 3 points");
  let mx = 0;
  let my = 0;
  for (const [x, y] of points) {
    mx += x / n;
    my += y / n;
  }
  // Solve [suu suv; suv svv][a b]' = 0.5 [suuu+suvv; svvv+svuu] in centred coordinates.
  let suu = 0, suv = 0, svv = 0, suuu = 0, svvv = 0, suvv = 0, svuu = 0;
  for (const [x, y] of points) {
    const u = x - mx;
    const v = y - my;
    suu += u * u; suv += u * v; svv += v * v;
    suuu += u * u * u; svvv += v * v * v; suvv += u * v * v; svuu += v * u * u;
  }
  const det = suu * svv - suv * suv;
  const r1 = 0.5 * (suuu + suvv);
  const r2 = 0.5 * (svvv + svuu);
  const a = (r1 * svv - r2 * suv) / det;
  const b = (suu * r2 - suv * r1) / det;
  let cx = a + mx;
  let cy = b + my;
  let r = Math.sqrt(a * a + b * b + (suu + svv) / n);
  for (let iter = 0; iter < 50; iter++) {
    // Normal equations for residual d_i = |p_i - c| - r.
    let j11 = 0, j12 = 0, j13 = 0, j22 = 0, j23 = 0, j33 = 0, g1 = 0, g2 = 0, g3 = 0;
    for (const [x, y] of points) {
      const dx = cx - x;
      const dy = cy - y;
      const d = Math.hypot(dx, dy);
      const res = d - r;
      const jx = dx / d;
      const jy = dy / d;
      const jr = -1;
      j11 += jx * jx; j12 += jx * jy; j13 += jx * jr; j22 += jy * jy; j23 += jy * jr; j33 += jr * jr;
      g1 += jx * res; g2 += jy * res; g3 += jr * res;
    }
    const step = solve3([j11, j12, j13, j12, j22, j23, j13, j23, j33], [-g1, -g2, -g3]);
    cx += step[0];
    cy += step[1];
    r += step[2];
    if (Math.hypot(step[0], step[1], step[2]) < 1e-9) break;
  }
  return { centre: [cx, cy], radius: r };
}

function solve3(m: number[], v: number[]): [number, number, number] {
  const [a, b, c, d, e, f, g, h, i] = m as [number, number, number, number, number, number, number, number, number];
  const det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
  const [x, y, z] = v as [number, number, number];
  return [
    (x * (e * i - f * h) - b * (y * i - f * z) + c * (y * h - e * z)) / det,
    (a * (y * i - f * z) - x * (d * i - f * g) + c * (d * z - y * g)) / det,
    (a * (e * z - y * h) - b * (d * z - y * g) + x * (d * h - e * g)) / det,
  ];
}

/**
 * Iteratively refits after rejecting points whose |residual| exceeds max(k * rms, floor).
 * Returns indices into `points`.
 */
export function robustFit<M>(
  points: Vec2[],
  fit: (pts: Vec2[]) => M,
  residual: (m: M, p: Vec2) => number,
  k = 3,
  floor = 1.5,
): RobustFit<M> {
  let inliers = points.map((_, i) => i);
  let model = fit(points);
  for (let iter = 0; iter < 20; iter++) {
    const res = inliers.map((i) => residual(model, points[i]!));
    const rms = Math.sqrt(res.reduce((s, r) => s + r * r, 0) / res.length);
    const limit = Math.max(k * rms, floor);
    const next = points.map((_, i) => i).filter((i) => Math.abs(residual(model, points[i]!)) <= limit);
    if (next.length === inliers.length && next.every((v, j) => v === inliers[j])) break;
    if (next.length < 3) break;
    inliers = next;
    model = fit(inliers.map((i) => points[i]!));
  }
  const res = inliers.map((i) => residual(model, points[i]!));
  const inlierSet = new Set(inliers);
  return {
    model,
    inliers,
    outliers: points.map((_, i) => i).filter((i) => !inlierSet.has(i)),
    rms: Math.sqrt(res.reduce((s, r) => s + r * r, 0) / res.length),
    maxAbs: res.reduce((m, r) => Math.max(m, Math.abs(r)), 0),
  };
}

export function intersectLines(a: Line, b: Line): Vec2 {
  // a.point + s a.dir = b.point + t b.dir
  const det = a.dir[0] * -b.dir[1] - a.dir[1] * -b.dir[0];
  const dx = b.point[0] - a.point[0];
  const dy = b.point[1] - a.point[1];
  const s = (dx * -b.dir[1] - dy * -b.dir[0]) / det;
  return [a.point[0] + s * a.dir[0], a.point[1] + s * a.dir[1]];
}

export const angleBetweenLinesDeg = (a: Line, b: Line): number => {
  const c = Math.abs(a.dir[0] * b.dir[0] + a.dir[1] * b.dir[1]);
  return (Math.acos(Math.min(1, c)) * 180) / Math.PI;
};
