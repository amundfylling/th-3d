// Guided tracing of a slot (the cut in the ice sheet that a figure's fixture runs in) in one photograph.
// An operator seed polyline fixes the slot's identity and rough route; the centreline, width and ends
// are measured from the image. Occluded stretches (figures, puck) become explicit gaps.
import type { Vec2 } from "./fit.ts";

/** Slot signal at a pixel-centre coordinate: high inside the slot, low on the surrounding surface. */
export type Signal = (u: number, v: number) => number;

export interface SlotTraceParams {
  /** Spacing of cross-sections along the slot (px). */
  step: number;
  /** Half-length of each cross-section profile (px). */
  halfWindow: number;
  /** Max offset of the slot centre from the current guide curve (px). */
  searchRadius: number;
  expectedWidth: number;
  /** Accepted width range as fractions of expectedWidth. */
  widthRange: [number, number];
  /** Minimum core-minus-surroundings signal contrast. */
  minContrast: number;
  /** How far the guide is extended beyond each seed end to look for the real slot end (px). */
  extend: number;
  /** Guide refinement passes. */
  passes: number;
  /** Max sideways jump (px) of a section centre from the median of its neighbours: [first pass, later passes]. */
  lateralTol: [number, number];
}

export interface Section {
  /** Position of the section on the guide curve. */
  guide: Vec2;
  normal: Vec2;
  tangent: Vec2;
  ok: boolean;
  centre?: Vec2;
  width?: number;
  contrast?: number;
  reject?: string;
}

export interface SlotEnd {
  point: Vec2;
  /** Sub-pixel crossing found along the tangent (true) or only the last good section (false). */
  refined: boolean;
}

export interface SlotTrace {
  sections: Section[];
  /** Index range [first, last] of accepted sections forming the slot. */
  span: [number, number];
  start: SlotEnd;
  end: SlotEnd;
  /** Smoothed centreline from start to end (gaps interpolated), densely sampled at `step`. */
  centreline: Vec2[];
  /** For each centreline point: detected (true) or interpolated across a gap (false). */
  detected: boolean[];
  widthMedian: number;
}

const sub = (a: Vec2, b: Vec2): Vec2 => [a[0] - b[0], a[1] - b[1]];
const add = (a: Vec2, b: Vec2): Vec2 => [a[0] + b[0], a[1] + b[1]];
const mul = (a: Vec2, k: number): Vec2 => [a[0] * k, a[1] * k];
const len = (a: Vec2): number => Math.hypot(a[0], a[1]);
const unit = (a: Vec2): Vec2 => {
  const l = len(a);
  if (!(l > 0)) throw new Error("zero-length direction in slot trace");
  return mul(a, 1 / l);
};
const median = (a: number[]): number => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)]!;

/** Resamples a polyline at a fixed arc-length spacing (first and last points kept). */
export function resample(poly: Vec2[], step: number): Vec2[] {
  const out: Vec2[] = [poly[0]!];
  let carry = 0;
  for (let i = 1; i < poly.length; i++) {
    const a = poly[i - 1]!, b = poly[i]!;
    const d = len(sub(b, a));
    let t = step - carry;
    while (t <= d) {
      out.push(add(a, mul(sub(b, a), t / d)));
      t += step;
    }
    carry = d - (t - step);
  }
  const last = poly[poly.length - 1]!;
  if (len(sub(last, out[out.length - 1]!)) > step * 0.25) out.push(last);
  return out;
}

export const polylineLength = (poly: Vec2[]): number => poly.slice(1).reduce((s, p, i) => s + len(sub(p, poly[i]!)), 0);

function tangents(poly: Vec2[]): Vec2[] {
  return poly.map((_, i) => {
    const a = poly[Math.max(0, i - 2)]!, b = poly[Math.min(poly.length - 1, i + 2)]!;
    return unit(sub(b, a));
  });
}

function smooth(poly: Vec2[], half: number): Vec2[] {
  return poly.map((_, i) => {
    let sx = 0, sy = 0, n = 0;
    for (let j = Math.max(0, i - half); j <= Math.min(poly.length - 1, i + half); j++) {
      sx += poly[j]![0];
      sy += poly[j]![1];
      n++;
    }
    // Keep the ends anchored so smoothing does not shorten the slot.
    return i === 0 || i === poly.length - 1 ? poly[i]! : ([sx / n, sy / n] as Vec2);
  });
}

/** Measures one cross-section: the slot run nearest the guide, with sub-pixel edges. */
function measure(signal: Signal, guide: Vec2, normal: Vec2, tangent: Vec2, p: SlotTraceParams): Section {
  const ds = 0.5;
  const n = Math.round((2 * p.halfWindow) / ds) + 1;
  const offs: number[] = [];
  const vals: number[] = [];
  for (let i = 0; i < n; i++) {
    const o = -p.halfWindow + i * ds;
    offs.push(o);
    vals.push(signal(guide[0] + o * normal[0], guide[1] + o * normal[1]));
  }
  const outer = Math.max(4, Math.round(n * 0.12));
  const sideL = median(vals.slice(0, outer));
  const sideR = median(vals.slice(n - outer));
  // Core: maximum within the search radius of the guide.
  let iCore = -1;
  for (let i = 0; i < n; i++) if (Math.abs(offs[i]!) <= p.searchRadius && (iCore < 0 || vals[i]! > vals[iCore]!)) iCore = i;
  const core = vals[iCore]!;
  const base: Section = { guide, normal, tangent, ok: false };
  const contrast = core - Math.max(sideL, sideR);
  if (contrast < p.minContrast) return { ...base, contrast, reject: "low contrast" };
  const thrL = (core + sideL) / 2;
  const thrR = (core + sideR) / 2;
  // Edges: scan outward from the core to the first drop below the mid level. A short light interruption
  // (a reflection streak inside the dark slot, < 0.35 slot widths) is bridged only if the signal
  // returns above the mid level and the run stays within 1.3 expected widths; a neighbouring dark
  // object separated by a light gap is therefore not merged into the slot.
  const bridge = Math.round((0.35 * p.expectedWidth) / ds);
  const maxRun = (1.3 * p.expectedWidth) / ds;
  const scan = (dir: 1 | -1, thr: number): number => {
    let i = iCore;
    for (;;) {
      const j = i + dir;
      if (j < 0 || j >= n) return -1;
      if (vals[j]! < thr) {
        let k = j;
        let back = -1;
        for (let m = 1; m <= bridge; m++) {
          k = j + dir * m;
          if (k < 0 || k >= n) break;
          if (vals[k]! >= thr) { back = k; break; }
        }
        if (back >= 0 && Math.abs(back - iCore) < maxRun) { i = back; continue; }
        return j;
      }
      i = j;
    }
  };
  const l = scan(-1, thrL);
  const r = scan(1, thrR);
  if (l < 0 || r < 0) return { ...base, contrast, reject: "run touches window edge" };
  const eL = offs[l]! + (ds * (thrL - vals[l]!)) / (vals[l + 1]! - vals[l]!);
  const eR = offs[r - 1]! + (ds * (vals[r - 1]! - thrR)) / (vals[r - 1]! - vals[r]!);
  const width = eR - eL;
  if (width < p.expectedWidth * p.widthRange[0] || width > p.expectedWidth * p.widthRange[1])
    return { ...base, contrast, width, reject: `width ${width.toFixed(1)} px` };
  const mid = (eL + eR) / 2;
  return { ...base, ok: true, centre: add(guide, mul(normal, mid)), width, contrast };
}

/**
 * Centre for a rejected section: the guide point shifted sideways by the offset interpolated between
 * the nearest accepted sections. Unlike a straight chord between centres, this keeps the guide's
 * curvature across a gap on a curve.
 */
function fillFromGuide(sections: Section[], i: number): Vec2 {
  const off = (s: Section): number => (s.centre![0] - s.guide[0]) * s.normal[0] + (s.centre![1] - s.guide[1]) * s.normal[1];
  let j0 = i - 1; while (!sections[j0]!.ok) j0--;
  let j1 = i + 1; while (!sections[j1]!.ok) j1++;
  const f = (i - j0) / (j1 - j0);
  const o = off(sections[j0]!) * (1 - f) + off(sections[j1]!) * f;
  const s = sections[i]!;
  return add(s.guide, mul(s.normal, o));
}

/** Least-squares quadratic through (x, y), evaluated at x = 0 (robust to smooth curvature). */
function quadraticAtZero(xs: number[], ys: number[]): number {
  const S = (f: (x: number, y: number) => number): number => xs.reduce((acc, x, i) => acc + f(x, ys[i]!), 0);
  const m = [S((x) => x ** 4), S((x) => x ** 3), S((x) => x ** 2), S((x) => x ** 3), S((x) => x ** 2), S((x) => x), S((x) => x ** 2), S((x) => x), xs.length];
  const rhs = [S((x, y) => x * x * y), S((x, y) => x * y), S((_, y) => y)];
  const det3 = (q: number[]): number => q[0]! * (q[4]! * q[8]! - q[5]! * q[7]!) - q[1]! * (q[3]! * q[8]! - q[5]! * q[6]!) + q[2]! * (q[3]! * q[7]! - q[4]! * q[6]!);
  const D = det3(m);
  if (Math.abs(D) < 1e-9) return ys.reduce((a, b) => a + b, 0) / ys.length;
  return det3(m.map((v, j) => (j % 3 === 2 ? rhs[Math.floor(j / 3)]! : v))) / D;
}

/**
 * Rejects accepted sections whose centre jumps sideways (e.g. onto a dark part of a figure standing
 * over the slot): compared with the median offset of accepted neighbours within +-6 sections, and,
 * after the first pass, against a cap on the offset from the guide itself.
 */
function rejectLateralOutliers(sections: Section[], tol: number, cap: number): void {
  const off = (s: Section): number => (s.centre![0] - s.guide[0]) * s.normal[0] + (s.centre![1] - s.guide[1]) * s.normal[1];
  for (let round = 0; round < 2; round++) {
    const offsets = sections.map((s) => (s.ok ? off(s) : NaN));
    sections.forEach((s, i) => {
      if (!s.ok) return;
      if (Math.abs(offsets[i]!) > cap) {
        s.ok = false;
        s.reject = `offset ${offsets[i]!.toFixed(1)} px from guide`;
        return;
      }
      const xs: number[] = [];
      const ys: number[] = [];
      for (let j = Math.max(0, i - 6); j <= Math.min(sections.length - 1, i + 6); j++)
        if (j !== i && !Number.isNaN(offsets[j]!)) { xs.push(j - i); ys.push(offsets[j]!); }
      if (xs.length < 6) return;
      const pred = quadraticAtZero(xs, ys);
      if (Math.abs(offsets[i]! - pred) > tol) {
        s.ok = false;
        s.reject = `lateral jump ${(offsets[i]! - pred).toFixed(1)} px`;
      }
    });
  }
}

/** Finds where the slot stops along `dir` from `from` (sub-pixel), using the centreline signal. */
function findEnd(signal: Signal, from: Vec2, dir: Vec2, width: number, maxDist: number): SlotEnd {
  const ds = 0.5;
  const core = median([0, 1, 2, 3, 4].map((k) => signal(from[0] - k * dir[0], from[1] - k * dir[1])));
  const beyond: number[] = [];
  for (let t = maxDist - 10; t <= maxDist; t += 1) beyond.push(signal(from[0] + t * dir[0], from[1] + t * dir[1]));
  const outside = median(beyond);
  const thr = (core + outside) / 2;
  let prev = core;
  for (let t = ds; t <= maxDist; t += ds) {
    const v = signal(from[0] + t * dir[0], from[1] + t * dir[1]);
    if (v < thr) {
      const tt = t - ds + (ds * (prev - thr)) / (prev - v);
      if (!Number.isFinite(tt)) break;
      return { point: add(from, mul(dir, tt)), refined: core - outside > 0 && tt < maxDist - width };
    }
    prev = v;
  }
  return { point: from, refined: false };
}

/**
 * `hidden` marks ends the operator saw covered by an object (a figure over the slot end). Those ends
 * are not searched beyond the seed and get no sub-pixel end: the observed end is the last accepted
 * cross-section, so dark parts of the covering object are never mistaken for slot.
 */
export function traceSlot(signal: Signal, seed: Vec2[], p: SlotTraceParams, hidden: { start?: boolean; end?: boolean } = {}): SlotTrace {
  const extStart = hidden.start ? 0 : p.extend;
  const extEnd = hidden.end ? 0 : p.extend;
  // Extend the seed along its end tangents so the real ends can be found beyond it.
  const t0 = unit(sub(seed[0]!, seed[1]!));
  const t1 = unit(sub(seed[seed.length - 1]!, seed[seed.length - 2]!));
  let guideLine = resample([add(seed[0]!, mul(t0, extStart)), ...seed, add(seed[seed.length - 1]!, mul(t1, extEnd))], p.step);
  let sections: Section[] = [];
  let span: [number, number] = [0, 0];
  let passParams = p;
  for (let pass = 0; pass < p.passes; pass++) {
    const tans = tangents(guideLine);
    const pp = passParams;
    sections = guideLine.map((g, i) => {
      const t = tans[i]!;
      return measure(signal, g, [-t[1], t[0]], t, pp);
    });
    // The first pass follows the coarse seed chords, so the lateral test starts once the guide follows the slot.
    if (pass > 0) rejectLateralOutliers(sections, p.lateralTol[1], 0.15 * p.expectedWidth);
    // The slot is the run of accepted sections that covers the seed's middle, allowing gaps.
    const okIdx = sections.map((s, i) => (s.ok ? i : -1)).filter((i) => i >= 0);
    if (okIdx.length < 3) throw new Error("slot not found near seed");
    const mid = Math.round(sections.length / 2);
    const maxGap = Math.round(400 / p.step);
    let a = okIdx.reduce((best, i) => (Math.abs(i - mid) < Math.abs(best - mid) ? i : best), okIdx[0]!);
    let b = a;
    // Walk outward from the middle, bridging gaps up to maxGap sections.
    let k = okIdx.indexOf(a);
    while (k > 0 && okIdx[k]! - okIdx[k - 1]! <= maxGap) k--;
    a = okIdx[k]!;
    k = okIdx.indexOf(b);
    while (k < okIdx.length - 1 && okIdx[k + 1]! - okIdx[k]! <= maxGap) k++;
    b = okIdx[k]!;
    span = [a, b];
    // New guide: detected centres in the span, gaps linearly interpolated, then smoothed.
    const pts: Vec2[] = [];
    for (let i = a; i <= b; i++) pts.push(sections[i]!.ok ? sections[i]!.centre! : fillFromGuide(sections, i));
    const smoothed = smooth(pts, 3);
    if (pass < p.passes - 1) {
      // Later passes: tight search around the refined guide and a width within +-25% of the median,
      // so the trace cannot wander onto printed features beside or beyond the slot.
      const w = median(sections.slice(a, b + 1).filter((x) => x.ok).map((x) => x.width!));
      passParams = { ...p, searchRadius: Math.max(4, 0.3 * p.expectedWidth), expectedWidth: w, widthRange: [0.75, 1.25] };
      // Restart the extensions from the seed ends (not from anything found beyond them).
      const sA = closestOnPolyline(smoothed, seed[0]!).s;
      const sB = closestOnPolyline(smoothed, seed[seed.length - 1]!).s;
      const kept = clip(smoothed, Math.min(sA, sB), Math.max(sA, sB));
      const e0 = unit(sub(kept[0]!, kept[Math.min(4, kept.length - 1)]!));
      const e1 = unit(sub(kept[kept.length - 1]!, kept[Math.max(0, kept.length - 5)]!));
      guideLine = resample([add(kept[0]!, mul(e0, extStart)), ...kept, add(kept[kept.length - 1]!, mul(e1, extEnd))], p.step);
    }
  }
  const [a, b] = span;
  const inSpan = sections.slice(a, b + 1);
  const pts: Vec2[] = [];
  const detected: boolean[] = [];
  inSpan.forEach((s, i) => {
    pts.push(s.ok ? s.centre! : fillFromGuide(inSpan, i));
    detected.push(s.ok);
  });
  const centre = smooth(pts, 2);
  const widthMedian = median(inSpan.filter((s) => s.ok).map((s) => s.width!));
  const dirStart = unit(sub(centre[0]!, centre[Math.min(3, centre.length - 1)]!));
  const dirEnd = unit(sub(centre[centre.length - 1]!, centre[Math.max(0, centre.length - 4)]!));
  const start = hidden.start ? { point: centre[0]!, refined: false } : findEnd(signal, centre[0]!, dirStart, widthMedian, p.step * 3 + widthMedian);
  const end = hidden.end ? { point: centre[centre.length - 1]!, refined: false } : findEnd(signal, centre[centre.length - 1]!, dirEnd, widthMedian, p.step * 3 + widthMedian);
  return {
    sections,
    span,
    start,
    end,
    centreline: [start.point, ...centre, end.point],
    detected: [start.refined, ...detected, end.refined],
    widthMedian,
  };
}

/** Part of a polyline between arc-length positions s0 <= s1. */
function clip(poly: Vec2[], s0: number, s1: number): Vec2[] {
  const out: Vec2[] = [];
  let acc = 0;
  for (let i = 0; i < poly.length; i++) {
    if (i > 0) acc += len(sub(poly[i]!, poly[i - 1]!));
    if (acc >= s0 && acc <= s1) out.push(poly[i]!);
  }
  return out.length >= 5 ? out : poly;
}

/** Douglas-Peucker simplification; returns kept points. */
export function simplify(poly: Vec2[], tol: number): Vec2[] {
  if (poly.length <= 2) return poly;
  const [a, b] = [poly[0]!, poly[poly.length - 1]!];
  const ab = sub(b, a);
  const L = len(ab) || 1;
  let iMax = 0, dMax = 0;
  for (let i = 1; i < poly.length - 1; i++) {
    const d = Math.abs(ab[0] * (a[1] - poly[i]![1]) - ab[1] * (a[0] - poly[i]![0])) / L;
    if (d > dMax) { dMax = d; iMax = i; }
  }
  if (dMax <= tol) return [a, b];
  return [...simplify(poly.slice(0, iMax + 1), tol).slice(0, -1), ...simplify(poly.slice(iMax), tol)];
}

/** Douglas-Peucker for a closed outline: split at the point farthest from the first, simplify both halves. */
export function simplifyClosed(poly: Vec2[], tol: number): Vec2[] {
  if (poly.length <= 3) return poly;
  let iFar = 0, dFar = -1;
  poly.forEach((p, i) => {
    const d = len(sub(p, poly[0]!));
    if (d > dFar) { dFar = d; iFar = i; }
  });
  const a = simplify(poly.slice(0, iFar + 1), tol);
  const b = simplify([...poly.slice(iFar), poly[0]!], tol);
  return [...a.slice(0, -1), ...b.slice(0, -1)];
}

/** Distance from a point to a polyline, and the arc-length position of the closest point. */
export function closestOnPolyline(poly: Vec2[], p: Vec2): { dist: number; s: number; point: Vec2 } {
  let best = { dist: Infinity, s: 0, point: poly[0]! };
  let acc = 0;
  for (let i = 1; i < poly.length; i++) {
    const a = poly[i - 1]!, b = poly[i]!;
    const ab = sub(b, a);
    const L2 = ab[0] ** 2 + ab[1] ** 2;
    const t = L2 === 0 ? 0 : Math.max(0, Math.min(1, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / L2));
    const q = add(a, mul(ab, t));
    const d = len(sub(p, q));
    if (d < best.dist) best = { dist: d, s: acc + t * Math.sqrt(L2), point: q };
    acc += Math.sqrt(L2);
  }
  return best;
}
