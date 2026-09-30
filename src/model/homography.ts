// Planar homography (3x3, row-major, h[8] = 1) between two photographs of the same plane.
import type { Vec2 } from "./fit.ts";
import { closestOnPolyline } from "./slot-trace.ts";

export type H = [number, number, number, number, number, number, number, number, number];

export function applyH(h: H, [x, y]: Vec2): Vec2 {
  const w = h[6] * x + h[7] * y + h[8];
  return [(h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w];
}

/** Solves A x = b for a small dense system by Gaussian elimination with partial pivoting. */
function solve(A: number[][], b: number[]): number[] {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i]!]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r]![c]!) > Math.abs(M[p]![c]!)) p = r;
    [M[c], M[p]] = [M[p]!, M[c]!];
    for (let r = c + 1; r < n; r++) {
      const f = M[r]![c]! / M[c]![c]!;
      for (let k = c; k <= n; k++) M[r]![k]! -= f * M[c]![k]!;
    }
  }
  const x = new Array<number>(n).fill(0);
  for (let r = n - 1; r >= 0; r--) {
    let s = M[r]![n]!;
    for (let k = r + 1; k < n; k++) s -= M[r]![k]! * x[k]!;
    x[r] = s / M[r]![r]!;
  }
  return x;
}

/** Normalising similarity (centroid to origin, mean distance sqrt 2) for numerical conditioning. */
function normaliser(pts: Vec2[]): { T: H; Tinv: H } {
  const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
  const cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  const d = pts.reduce((s, p) => s + Math.hypot(p[0] - cx, p[1] - cy), 0) / pts.length;
  const k = Math.SQRT2 / d;
  return { T: [k, 0, -k * cx, 0, k, -k * cy, 0, 0, 1], Tinv: [1 / k, 0, cx, 0, 1 / k, cy, 0, 0, 1] };
}

const mul3 = (a: H, b: H): H => {
  const r = new Array<number>(9).fill(0);
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) for (let k = 0; k < 3; k++) r[i * 3 + j]! += a[i * 3 + k]! * b[k * 3 + j]!;
  return r as H;
};

/** Least-squares homography mapping src[i] -> dst[i] (at least 4 pairs). */
export function fitHomography(src: Vec2[], dst: Vec2[]): H {
  if (src.length < 4) throw new Error("need at least 4 correspondences");
  const ns = normaliser(src), nd = normaliser(dst);
  const s = src.map((p) => applyH(ns.T, p));
  const d = dst.map((p) => applyH(nd.T, p));
  const AtA = Array.from({ length: 8 }, () => new Array<number>(8).fill(0));
  const Atb = new Array<number>(8).fill(0);
  s.forEach(([x, y], i) => {
    const [u, v] = d[i]!;
    const rows: [number[], number][] = [
      [[x, y, 1, 0, 0, 0, -u * x, -u * y], u],
      [[0, 0, 0, x, y, 1, -v * x, -v * y], v],
    ];
    for (const [r, b] of rows) for (let a = 0; a < 8; a++) {
      Atb[a]! += r[a]! * b;
      for (let c = 0; c < 8; c++) AtA[a]![c]! += r[a]! * r[c]!;
    }
  });
  const h = [...solve(AtA, Atb), 1] as H;
  const full = mul3(nd.Tinv, mul3(h, ns.T));
  return full.map((v) => v / full[8]) as H;
}

export interface CurvePair {
  id: string;
  src: Vec2[];
  dst: Vec2[];
}

/**
 * Refines a homography so every source curve lands on its destination curve (closest-point iterations).
 * Returns the homography and per-curve RMS / max point-to-curve residuals in destination pixels.
 */
export function fitHomographyToCurves(initial: H, pairs: CurvePair[], iterations = 30): { h: H; residuals: Record<string, { rms: number; max: number; n: number }> } {
  let h = initial;
  for (let it = 0; it < iterations; it++) {
    const src: Vec2[] = [];
    const dst: Vec2[] = [];
    for (const p of pairs) {
      const L = p.dst.slice(1).reduce((s, q, i) => s + Math.hypot(q[0] - p.dst[i]![0], q[1] - p.dst[i]![1]), 0);
      for (const q of p.src) {
        const c = closestOnPolyline(p.dst, applyH(h, q));
        // Points that map beyond a destination curve's ends (e.g. an occluded end) carry no information.
        if (c.s < 1 || c.s > L - 1) continue;
        src.push(q);
        dst.push(c.point);
      }
    }
    h = fitHomography(src, dst);
  }
  const residuals: Record<string, { rms: number; max: number; n: number }> = {};
  for (const p of pairs) {
    const L = p.dst.slice(1).reduce((s, q, i) => s + Math.hypot(q[0] - p.dst[i]![0], q[1] - p.dst[i]![1]), 0);
    const d = p.src
      .map((q) => closestOnPolyline(p.dst, applyH(h, q)))
      .filter((c) => c.s >= 1 && c.s <= L - 1)
      .map((c) => c.dist);
    residuals[p.id] = { rms: Math.sqrt(d.reduce((s, x) => s + x * x, 0) / d.length), max: Math.max(...d), n: d.length };
  }
  return { h, residuals };
}
