// Iteration 05: provisional trace of the installed inner board boundary (ice contact edge) in the
// official overhead photograph. Detection is automatic from a documented seed and thresholds; the
// photograph is only read. Writes the trace, landmarks, checks and an assumed preview mapping into
// data/geometry.json and the numeric evidence into validation/05-board-report.json.
import { readFileSync, writeFileSync } from "node:fs";
import {
  angleBetweenLinesDeg,
  distanceToCircle,
  fitCircle,
  fitLine,
  intersectLines,
  robustFit,
  signedDistanceToLine,
  type Circle,
  type Line,
  type Vec2,
} from "../src/model/fit.ts";
import type { Assumption, GeometryFile, ImageToWorldMapping, Landmark, PixelPoint } from "../src/model/geometry.ts";
import { floodFill, loadPinnedJpeg, maxChannelBilinear, rgbAt, type Raster } from "../src/model/raster.ts";

// ---- Operator parameters (documented in docs/board-trace.md) ----------------------------------
const SOURCE_ID = "stiga_se_fi_overhead";
/** A centre-ice pixel (on the red centre line) from which the ice region is flood-filled. */
const SEED: [number, number] = [2818, 1650];
/** Pixels whose max(R,G,B) is below this are treated as the near-black board-base strip / slots. */
const BARRIER_MAX_CHANNEL = 90;
/** Minimum max-channel level just inside the edge, and minimum inside-minus-strip contrast. */
const MIN_INSIDE_LEVEL = 130;
const MIN_EDGE_CONTRAST = 80;
/** Local-consistency test: neighbour window (rays), tolerance (px), and longest gap filled by interpolation. */
const LOCAL_WINDOW = 8;
const LOCAL_OUTLIER_PX = 2;
const MAX_FILL_GAP_RAYS = 40;
/** Number of rays cast from the ice-region centre (0.25 deg spacing). */
const RAYS = 1440;
/** Every Nth ray is stored in the canonical trace (0.5 deg spacing). */
const STORE_EVERY = 2;
/** Initial corner-region size used only to seed the straight/corner split. */
const CORNER_SEED_PX = 650;
/** Approximate image x of the markings that meet the long boards (from inspection). */
const MARKING_SEEDS: { id: string; kind: "red" | "blue"; x: number; what: string }[] = [
  { id: "goal_line.W", kind: "red", x: 1208, what: "W goal line" },
  { id: "blue_line.W", kind: "blue", x: 2267, what: "W blue line" },
  { id: "centre_line", kind: "red", x: 2806, what: "centre red line" },
  { id: "blue_line.E", kind: "blue", x: 3342, what: "E blue line" },
  { id: "goal_line.E", kind: "red", x: 4420, what: "E goal line" },
];
const CATALOG_PLAYING_LENGTH_MM = 845;
const CATALOG_PLAYING_WIDTH_MM = 457;
const GEOMETRY_VERSION = "0.2.0";
// ------------------------------------------------------------------------------------------------

const GEOMETRY = "data/geometry.json";
const REPORT = "validation/05-board-report.json";
const round = (v: number, d = 2): number => Math.round(v * 10 ** d) / 10 ** d;

const geometry = JSON.parse(readFileSync(GEOMETRY, "utf8")) as GeometryFile;
const image = geometry.source_images.find((s) => s.source_id === SOURCE_ID);
if (!image) throw new Error(`${SOURCE_ID} missing from source_images`);
console.log(`decoding ${image.local_path} ...`);
const raster = loadPinnedJpeg(image.local_path, image.sha256);

// 1. Ice region: flood fill bounded by near-black pixels.
const mask = floodFill(raster, SEED, BARRIER_MAX_CHANNEL);
let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, area = 0;
for (let y = 0; y < raster.height; y++) {
  for (let x = 0; x < raster.width; x++) {
    if (mask[y * raster.width + x]) {
      area++;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
  }
}
if (area > 0.6 * raster.width * raster.height) throw new Error("flood fill leaked outside the boards");
const centre: Vec2 = [(minX + maxX + 1) / 2, (minY + maxY + 1) / 2];
console.log(`ice region: ${area} px, bbox x ${minX}..${maxX}, y ${minY}..${maxY}`);

// 2. One edge sample per ray: outermost ice pixel, then sub-pixel threshold crossing.
interface Sample {
  ray: number;
  dir: Vec2;
  p: Vec2;
  iceLevel: number;
  darkLevel: number;
  darkWidth: number;
  quality: "ok" | "not_ice_inside" | "no_dark_strip";
}
const inMask = (u: number, v: number): boolean => {
  const x = Math.floor(u), y = Math.floor(v);
  return x >= 0 && y >= 0 && x < raster.width && y < raster.height && mask[y * raster.width + x] === 1;
};
const median = (a: number[]): number => {
  const s = [...a].sort((x, y) => x - y);
  return s[Math.floor(s.length / 2)]!;
};
const samples: Sample[] = [];
const tMax = Math.hypot(maxX - minX, maxY - minY) / 2 + 10;
/** Sub-pixel ice/strip crossing along a ray, searched around `tOut` (the expected edge distance). */
function detectAlongRay(k: number, dir: Vec2, tOut: number): Sample {
  const at = (t: number): Vec2 => [centre[0] + t * dir[0], centre[1] + t * dir[1]];
  const f = (t: number): number => maxChannelBilinear(raster, ...at(t));
  const inside: number[] = [];
  for (let t = tOut - 25; t <= tOut - 8; t += 0.5) inside.push(f(t));
  const iceLevel = median(inside);
  let darkLevel = 255;
  for (let t = tOut - 2; t <= tOut + 15; t += 0.25) darkLevel = Math.min(darkLevel, f(t));
  const thr = (iceLevel + darkLevel) / 2;
  let tEdge = tOut;
  for (let t = tOut - 8; t <= tOut + 15; t += 0.25) {
    if (f(t) < thr) {
      const f0 = f(t - 0.25), f1 = f(t);
      tEdge = t - 0.25 + (0.25 * (f0 - thr)) / (f0 - f1);
      break;
    }
  }
  let tBack = tEdge;
  for (let t = tEdge + 0.25; t <= tEdge + 40; t += 0.25) {
    tBack = t;
    if (f(t) >= thr) break;
  }
  // Ice next to the boards is often in shadow (max channel ~160), so require contrast, not white.
  const quality = iceLevel < MIN_INSIDE_LEVEL ? "not_ice_inside" : darkLevel > 100 || iceLevel - darkLevel < MIN_EDGE_CONTRAST ? "no_dark_strip" : "ok";
  return { ray: k, dir, p: at(tEdge), iceLevel, darkLevel, darkWidth: tBack - tEdge, quality };
}
for (let k = 0; k < RAYS; k++) {
  const a = (2 * Math.PI * k) / RAYS;
  const dir: Vec2 = [Math.cos(a), Math.sin(a)];
  let tOut = 0;
  for (let t = 0; t <= tMax; t += 0.5) if (inMask(centre[0] + t * dir[0], centre[1] + t * dir[1])) tOut = t;
  samples.push(detectAlongRay(k, dir, tOut));
}

// 3. Straight sides and corners: seed split, robust fits, then reassign by fitted geometry.
type SideKey = "top" | "bottom" | "left" | "right";
type CornerKey = "top_left" | "top_right" | "bottom_right" | "bottom_left";
const sideOf = (p: Vec2, r: number): SideKey | CornerKey => {
  const nearL = p[0] < minX + r, nearR = p[0] > maxX - r, nearT = p[1] < minY + r, nearB = p[1] > maxY - r;
  if (nearT && nearL) return "top_left";
  if (nearT && nearR) return "top_right";
  if (nearB && nearR) return "bottom_right";
  if (nearB && nearL) return "bottom_left";
  const dists: [SideKey, number][] = [["top", p[1] - minY], ["bottom", maxY - p[1]], ["left", p[0] - minX], ["right", maxX - p[0]]];
  return dists.sort((a, b) => a[1] - b[1])[0]![0];
};
const good = samples.filter((s) => s.quality === "ok");
const pts = (keys: string, list: Sample[]): Vec2[] => list.filter((s) => sideOf(s.p, CORNER_SEED_PX) === keys).map((s) => s.p);
const sides = {} as Record<SideKey, Line>;
for (const k of ["top", "bottom", "left", "right"] as SideKey[]) sides[k] = robustFit(pts(k, good), fitLine, signedDistanceToLine, 3, 1.5).model;
const cornerSides: Record<CornerKey, [SideKey, SideKey]> = {
  top_left: ["top", "left"],
  top_right: ["top", "right"],
  bottom_right: ["bottom", "right"],
  bottom_left: ["bottom", "left"],
};
const corners = {} as Record<CornerKey, Circle>;
for (const k of Object.keys(cornerSides) as CornerKey[]) {
  const [s1, s2] = cornerSides[k];
  const cornerPts = pts(k, good).filter(
    (p) => Math.abs(signedDistanceToLine(sides[s1], p)) > 2 && Math.abs(signedDistanceToLine(sides[s2], p)) > 2,
  );
  corners[k] = robustFit(cornerPts, fitCircle, distanceToCircle, 3, 1.5).model;
}

// Assign each sample to the component it belongs to: an arc if it lies beyond both tangent points.
const foot = (l: Line, p: Vec2): Vec2 => {
  const d = signedDistanceToLine(l, p);
  return [p[0] - d * l.normal[0], p[1] - d * l.normal[1]];
};
function componentOf(p: Vec2): SideKey | CornerKey {
  for (const k of Object.keys(cornerSides) as CornerKey[]) {
    const c = corners[k].centre;
    const [s1, s2] = cornerSides[k];
    const beyond = (s: SideKey, other: SideKey): boolean => {
      // p is on the far side (toward the corner) of the perpendicular through the tangent point.
      const t = foot(sides[s], c);
      const along = sides[s].dir;
      const towardCorner = Math.sign((intersectLines(sides[s], sides[other])[0] - t[0]) * along[0] + (intersectLines(sides[s], sides[other])[1] - t[1]) * along[1]);
      return ((p[0] - t[0]) * along[0] + (p[1] - t[1]) * along[1]) * towardCorner > 0;
    };
    if (beyond(s1, s2) && beyond(s2, s1)) return k;
  }
  const dists = (["top", "bottom", "left", "right"] as SideKey[]).map((s) => [s, Math.abs(signedDistanceToLine(sides[s], p))] as const);
  return [...dists].sort((a, b) => a[1] - b[1])[0]![0];
}
const residualTo = (comp: SideKey | CornerKey, p: Vec2): number =>
  comp in sides ? signedDistanceToLine(sides[comp as SideKey], p) : distanceToCircle(corners[comp as CornerKey], p);

// Refit once with the geometric assignment, then classify outliers.
const fits: Record<string, { rms: number; maxAbs: number; n: number; outliers: number }> = {};
for (let pass = 0; pass < 2; pass++) {
  for (const k of ["top", "bottom", "left", "right"] as SideKey[]) {
    const p = good.filter((s) => componentOf(s.p) === k).map((s) => s.p);
    const r = robustFit(p, fitLine, signedDistanceToLine, 3, 1.5);
    sides[k] = r.model;
    fits[k] = { rms: r.rms, maxAbs: r.maxAbs, n: r.inliers.length, outliers: r.outliers.length };
  }
  for (const k of Object.keys(cornerSides) as CornerKey[]) {
    const p = good.filter((s) => componentOf(s.p) === k).map((s) => s.p);
    const r = robustFit(p, fitCircle, distanceToCircle, 3, 1.5);
    corners[k] = r.model;
    fits[k] = { rms: r.rms, maxAbs: r.maxAbs, n: r.inliers.length, outliers: r.outliers.length };
  }
}
// Model-guided re-detection: where the outermost-ice search failed (e.g. the flood slipped through a
// gap in the strip into the sponsor band), search again around the fitted model's edge distance.
let redetected = 0;
for (let i = 0; i < samples.length; i++) {
  const s0 = samples[i]!;
  if (s0.quality === "ok") continue;
  const guess = rayHit(componentOf(s0.p), s0.dir);
  const retry = detectAlongRay(s0.ray, s0.dir, Math.hypot(guess[0] - centre[0], guess[1] - centre[1]));
  if (retry.quality === "ok") {
    samples[i] = retry;
    redetected++;
  }
}
good.splice(0, good.length, ...samples.filter((s) => s.quality === "ok"));
for (const k of ["top", "bottom", "left", "right"] as SideKey[]) {
  const r = robustFit(good.filter((s) => componentOf(s.p) === k).map((s) => s.p), fitLine, signedDistanceToLine, 3, 1.5);
  sides[k] = r.model;
  fits[k] = { rms: r.rms, maxAbs: r.maxAbs, n: r.inliers.length, outliers: r.outliers.length };
}
for (const k of Object.keys(cornerSides) as CornerKey[]) {
  const r = robustFit(good.filter((s) => componentOf(s.p) === k).map((s) => s.p), fitCircle, distanceToCircle, 3, 1.5);
  corners[k] = r.model;
  fits[k] = { rms: r.rms, maxAbs: r.maxAbs, n: r.inliers.length, outliers: r.outliers.length };
}
const OUTLIER_PX = (comp: string): number => Math.max(3 * fits[comp]!.rms, 2);

// 4. Trace points: detected where good and consistent, otherwise filled from the fitted model.
function rayHit(comp: SideKey | CornerKey, dir: Vec2): Vec2 {
  if (comp in sides) {
    const l = sides[comp as SideKey];
    const t = ((l.point[0] - centre[0]) * l.normal[0] + (l.point[1] - centre[1]) * l.normal[1]) / (dir[0] * l.normal[0] + dir[1] * l.normal[1]);
    return [centre[0] + t * dir[0], centre[1] + t * dir[1]];
  }
  const c = corners[comp as CornerKey];
  const ox = centre[0] - c.centre[0], oy = centre[1] - c.centre[1];
  const b = ox * dir[0] + oy * dir[1];
  const t = -b + Math.sqrt(b * b - (ox * ox + oy * oy - c.radius * c.radius));
  return [centre[0] + t * dir[0], centre[1] + t * dir[1]];
}
interface TracePoint { p: Vec2; comp: string; status: "detected" | "filled"; reason?: string }
const tOf = (p: Vec2): number => Math.hypot(p[0] - centre[0], p[1] - centre[1]);
// Local consistency: compare each ray's edge distance with a quadratic fitted to its neighbours
// (+-LOCAL_WINDOW rays, excluding itself). Unbiased at corners, unlike a plain median.
function localPrediction(k: number, usable: boolean[]): number | null {
  const xs: number[] = [];
  const ys: number[] = [];
  for (let d = -LOCAL_WINDOW; d <= LOCAL_WINDOW; d++) {
    const j = (k + d + RAYS) % RAYS;
    if (d === 0 || !usable[j]) continue;
    xs.push(d);
    ys.push(tOf(samples[j]!.p));
  }
  if (xs.length < LOCAL_WINDOW) return null;
  const n = xs.length;
  const S = (f: (x: number, y: number) => number): number => xs.reduce((acc, x, i) => acc + f(x, ys[i]!), 0);
  const m = [S((x) => x ** 4), S((x) => x ** 3), S((x) => x ** 2), S((x) => x ** 3), S((x) => x ** 2), S((x) => x), S((x) => x ** 2), S((x) => x), n];
  const rhs = [S((x, y) => x * x * y), S((x, y) => x * y), S((_, y) => y)];
  const det3 = (q: number[]): number => q[0]! * (q[4]! * q[8]! - q[5]! * q[7]!) - q[1]! * (q[3]! * q[8]! - q[5]! * q[6]!) + q[2]! * (q[3]! * q[7]! - q[4]! * q[6]!);
  const D = det3(m);
  return det3(m.map((v, j) => (j % 3 === 2 ? rhs[Math.floor(j / 3)]! : v))) / D; // value at d = 0
}
const reason: (string | null)[] = samples.map((s) => {
  if (s.quality !== "ok") return s.quality;
  const comp = componentOf(s.p);
  const res = residualTo(comp, s.p);
  return Math.abs(res) > OUTLIER_PX(comp) ? `model residual ${round(res, 1)} px` : null;
});
for (let pass = 0; pass < 2; pass++) {
  const usable = reason.map((r) => r === null);
  samples.forEach((s, k) => {
    if (reason[k] !== null) return;
    const pred = localPrediction(k, usable);
    if (pred !== null && Math.abs(tOf(s.p) - pred) > LOCAL_OUTLIER_PX) reason[k] = `local deviation ${round(tOf(s.p) - pred, 1)} px`;
  });
}
// Fill flagged rays by interpolating the edge distance between the nearest accepted rays on each side.
const trace: TracePoint[] = samples.map((s, k) => {
  const comp = componentOf(s.p);
  if (reason[k] === null) return { p: s.p, comp, status: "detected" };
  let a = k, b = k;
  do a = (a - 1 + RAYS) % RAYS; while (reason[a] !== null && a !== k);
  do b = (b + 1) % RAYS; while (reason[b] !== null && b !== k);
  const da = (k - a + RAYS) % RAYS, db = (b - k + RAYS) % RAYS;
  if (da + db > MAX_FILL_GAP_RAYS) return { p: rayHit(comp, s.dir), comp, status: "filled", reason: `${reason[k]}; gap too long, fitted ${comp} model used` };
  const t = (tOf(samples[a]!.p) * db + tOf(samples[b]!.p) * da) / (da + db);
  return { p: [centre[0] + t * s.dir[0], centre[1] + t * s.dir[1]], comp, status: "filled", reason: reason[k]! };
});

// 5. Landmarks where markings meet the long boards.
const isColour = (kind: "red" | "blue", [r, g, b]: [number, number, number]): boolean =>
  kind === "red" ? r > 150 && r - g > 70 && r - b > 70 : b > 110 && b - r > 50 && b - g > 15;
interface LandmarkFit { id: string; side: "top" | "bottom"; px: Vec2; offsets: number; spreadPx: number; widthPx: number }
const landmarkFits: LandmarkFit[] = [];
for (const m of MARKING_SEEDS) {
  for (const side of ["top", "bottom"] as const) {
    const line = sides[side];
    const inward: Vec2 = signedDistanceToLine(line, centre) > 0 ? line.normal : [-line.normal[0], -line.normal[1]];
    const xs: [number, number][] = [];
    const widths: number[] = [];
    for (let o = 15; o <= 60; o += 5) {
      const hits: number[] = [];
      for (let x = m.x - 150; x <= m.x + 150; x += 0.5) {
        const base = foot(line, [x, line.point[1] + ((x - line.point[0]) * line.dir[1]) / line.dir[0]]);
        const q: Vec2 = [base[0] + o * inward[0], base[1] + o * inward[1]];
        if (isColour(m.kind, rgbAt(raster, q[0] - 0.5, q[1] - 0.5))) hits.push(x);
      }
      if (hits.length >= 6) {
        xs.push([o, hits.reduce((s, v) => s + v, 0) / hits.length]);
        widths.push((hits.length * 0.5));
      }
    }
    if (xs.length < 5) {
      console.warn(`landmark ${m.id}/${side}: marking not found (${xs.length} offsets)`);
      continue;
    }
    // Linear extrapolation of the marking centre to offset 0 (the boundary).
    const n = xs.length;
    const mo = xs.reduce((s, [o]) => s + o, 0) / n;
    const mx = xs.reduce((s, [, x]) => s + x, 0) / n;
    const slope = xs.reduce((s, [o, x]) => s + (o - mo) * (x - mx), 0) / xs.reduce((s, [o]) => s + (o - mo) ** 2, 0);
    const x0 = mx - slope * mo;
    const spread = Math.sqrt(xs.reduce((s, [o, x]) => s + (x - (x0 + slope * o)) ** 2, 0) / n);
    const onLine = foot(line, [x0, line.point[1] + ((x0 - line.point[0]) * line.dir[1]) / line.dir[0]]);
    landmarkFits.push({ id: `lm.board.${m.id}.${side}`, side, px: onLine, offsets: n, spreadPx: spread, widthPx: median(widths) });
  }
}
const lm = (id: string): Vec2 | undefined => landmarkFits.find((l) => l.id === id)?.px;

// 6. Checks.
const lineDist = (a: Line, b: Line, at: Vec2): number => Math.abs(signedDistanceToLine(b, foot(a, at)));
const xsAt = [minX + 700, (minX + maxX) / 2, maxX - 700];
const ysAt = [minY + 500, (minY + maxY) / 2, maxY - 500];
const widthPx = xsAt.map((x) => lineDist(sides.top, sides.bottom, [x, minY]));
const lengthPx = ysAt.map((y) => lineDist(sides.left, sides.right, [minX, y]));
const axisDir: Vec2 = (() => {
  const d1 = sides.top.dir[0] >= 0 ? sides.top.dir : ([-sides.top.dir[0], -sides.top.dir[1]] as Vec2);
  const d2 = sides.bottom.dir[0] >= 0 ? sides.bottom.dir : ([-sides.bottom.dir[0], -sides.bottom.dir[1]] as Vec2);
  const s: Vec2 = [d1[0] + d2[0], d1[1] + d2[1]];
  const n = Math.hypot(...s);
  return [s[0] / n, s[1] / n];
})();
const midLong: Line = (() => {
  const a = foot(sides.top, centre), b = foot(sides.bottom, centre);
  return { point: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], dir: axisDir, normal: [-axisDir[1], axisDir[0]] };
})();
const midShort: Line = (() => {
  const a = foot(sides.left, centre), b = foot(sides.right, centre);
  const d: Vec2 = [-axisDir[1], axisDir[0]];
  return { point: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], dir: d, normal: [-d[1], d[0]] };
})();
const origin = intersectLines(midLong, midShort);
const along = (p: Vec2): number => (p[0] - origin[0]) * axisDir[0] + (p[1] - origin[1]) * axisDir[1];
const Lpx = lengthPx[1]!;
const Wpx = widthPx[1]!;
const cornerRadii = Object.fromEntries((Object.keys(corners) as CornerKey[]).map((k) => [k, round(corners[k].radius, 1)]));
const tangency = Object.fromEntries(
  (Object.keys(cornerSides) as CornerKey[]).map((k) => [
    k,
    cornerSides[k].map((s) => round(Math.abs(signedDistanceToLine(sides[s], corners[k].centre)) - corners[k].radius, 2)),
  ]),
);
const markingChecks: Record<string, number | null> = {};
{
  const ct = lm("lm.board.centre_line.top"), cb = lm("lm.board.centre_line.bottom");
  if (ct && cb) {
    const d: Vec2 = [cb[0] - ct[0], cb[1] - ct[1]];
    const ang = (Math.acos(Math.abs(d[0] * axisDir[0] + d[1] * axisDir[1]) / Math.hypot(...d)) * 180) / Math.PI;
    markingChecks.centre_line_angle_to_long_axis_deg = round(ang, 3);
    markingChecks.centre_line_offset_from_boundary_centre_px = round((along(ct) + along(cb)) / 2, 2);
  }
  for (const [west, east] of [["blue_line.W", "blue_line.E"], ["goal_line.W", "goal_line.E"]] as const) {
    for (const side of ["top", "bottom"]) {
      const w = lm(`lm.board.${west}.${side}`), e = lm(`lm.board.${east}.${side}`), c = lm(`lm.board.centre_line.${side}`);
      if (w && e && c) markingChecks[`${west.split(".")[0]}_asymmetry_about_centre_line_${side}_px`] = round(Math.abs(along(e) - along(c)) - Math.abs(along(c) - along(w)), 2);
    }
    for (const id of [west, east]) {
      const t = lm(`lm.board.${id}.top`), b = lm(`lm.board.${id}.bottom`);
      if (t && b) markingChecks[`${id}_top_minus_bottom_along_axis_px`] = round(along(t) - along(b), 2);
    }
  }
}
// Straightness: quadratic fit of each side's detected points (normal offset vs along-side position).
const bow: Record<string, { sagitta_px: number; linear_rms_px: number; quadratic_rms_px: number }> = {};
for (const k of ["top", "bottom", "left", "right"] as SideKey[]) {
  const l = sides[k];
  const pts2 = trace.filter((t) => t.status === "detected" && t.comp === k).map((t) => [
    (t.p[0] - l.point[0]) * l.dir[0] + (t.p[1] - l.point[1]) * l.dir[1],
    signedDistanceToLine(l, t.p) * Math.sign(signedDistanceToLine(l, centre)),
  ] as Vec2);
  const n = pts2.length;
  // Least squares d = a s^2 + b s + c via normal equations.
  const S = (f: (s: number, d: number) => number): number => pts2.reduce((acc, [x, d]) => acc + f(x, d), 0);
  const m = [S((x) => x ** 4), S((x) => x ** 3), S((x) => x ** 2), S((x) => x ** 3), S((x) => x ** 2), S((x) => x), S((x) => x ** 2), S((x) => x), n];
  const rhs = [S((x, d) => x * x * d), S((x, d) => x * d), S((_, d) => d)];
  const det3 = (q: number[]): number => q[0]! * (q[4]! * q[8]! - q[5]! * q[7]!) - q[1]! * (q[3]! * q[8]! - q[5]! * q[6]!) + q[2]! * (q[3]! * q[7]! - q[4]! * q[6]!);
  const D = det3(m);
  const col = (i: number): number[] => m.map((v, j) => (j % 3 === i ? rhs[Math.floor(j / 3)]! : v));
  const [qa, qb, qc] = [det3(col(0)) / D, det3(col(1)) / D, det3(col(2)) / D];
  const xsK = pts2.map(([x]) => x);
  const half = (Math.max(...xsK) - Math.min(...xsK)) / 2;
  const rmsOf = (f: (x: number) => number): number => Math.sqrt(pts2.reduce((acc, [x, d]) => acc + (d - f(x)) ** 2, 0) / n);
  // Positive sagitta: the middle of the side lies inward (toward the ice centre) of its ends.
  bow[k] = { sagitta_px: round(-qa * half * half, 2), linear_rms_px: round(rmsOf(() => 0), 3), quadratic_rms_px: round(rmsOf((x) => qa * x * x + qb * x + qc), 3) };
}
const stripWidths = samples.filter((s) => s.quality === "ok").map((s) => s.darkWidth);
const detected = trace.filter((t) => t.status === "detected").length;
const straightRms = Math.max(...(["top", "bottom", "left", "right"] as const).map((k) => fits[k]!.rms));
const stripMedian = median(stripWidths);
const uncertaintyPx = Math.ceil(stripMedian + 2 * straightRms);

// 7. Assumed preview mapping: uniform scale from the catalog playing length, rotation to the long axis.
const s = CATALOG_PLAYING_LENGTH_MM / Lpx;
const ex = axisDir;
const ey: Vec2 = [ex[1], -ex[0]]; // image-up
const matrix: ImageToWorldMapping["matrix"] = [
  s * ex[0], s * ex[1], -s * (ex[0] * origin[0] + ex[1] * origin[1]),
  s * ey[0], s * ey[1], -s * (ey[0] * origin[0] + ey[1] * origin[1]),
  0, 0, 1,
];
const toWorld = ([u, v]: Vec2): [number, number] => [
  round(matrix[0] * u + matrix[1] * v + matrix[2], 2),
  round(matrix[3] * u + matrix[4] * v + matrix[5], 2),
];

// 8. Write canonical data (idempotent: replaces only the entries this script owns).
const TRACE_ID = "trace.board_inner.overhead";
const MAP_ID = "map.overhead.preview";
const stored = trace.filter((_, i) => i % STORE_EVERY === 0);
const inferred: GeometryFile["image_traces"][number]["inferred_segments"] = [];
stored.forEach((t, i) => {
  if (t.status !== "filled") return;
  const last = inferred[inferred.length - 1];
  if (last && last.to === i - 1) last.to = i;
  else inferred.push({ from: i, to: i, reason: "", assumption_id: "assume.board_occlusion_fill" });
});
for (const seg of inferred) {
  const reasons = new Set(stored.slice(seg.from, seg.to + 1).map((t) => t.reason));
  seg.reason = `Interpolated between the nearest detected edge points (${stored[seg.from]!.comp}): ${[...reasons].join("; ")}.`;
}
const assumptions: Assumption[] = [
  {
    id: "assume.board_edge_is_ice_contact",
    statement: "The ice-side edge of the near-black strip at the base of the boards is the ice contact boundary.",
    reason: `The strip (median ${round(stripMedian, 1)} px wide) could be a base trim, a gap over the loose sheet or a shadow; the photograph does not show which.`,
    affects: [TRACE_ID, "board.inner_boundary"],
    replace_with: "Close-up or measurement of the installed board base on the user's game.",
  },
  {
    id: "assume.board_occlusion_fill",
    statement: "Where the edge is hidden or disturbed, the boundary is interpolated (along the rays) between the nearest detected edge points on either side.",
    reason: "A few short stretches are disturbed by painted markings meeting the boards or fail the local consistency test; the neighbouring edge is continuous.",
    affects: [TRACE_ID],
    replace_with: "Empty installed-rink overhead without figures.",
  },
  {
    id: "assume.overhead_near_orthographic",
    statement: "The official overhead views the ice plane nearly perpendicularly, so a similarity (no perspective) maps ice-plane pixels to the world.",
    reason: `Opposite traced sides are parallel within ${round(Math.max(angleBetweenLinesDeg(sides.top, sides.bottom), angleBetweenLinesDeg(sides.left, sides.right)), 3)} deg; see ${REPORT}. Elevated parts (board tops, screens, figures) do show perspective and are excluded.`,
    affects: [MAP_ID],
    replace_with: "Homography from a perpendicular overhead with scale markers in both directions.",
  },
  {
    id: "assume.preview_scale_catalog_length",
    statement: `The catalog playing length (approx. ${CATALOG_PLAYING_LENGTH_MM} mm) equals the traced inner boundary's long extent; one uniform scale is applied to both axes.`,
    reason: "Only a preview scale is needed before calibration; the catalog does not say what the 845 mm spans.",
    affects: [MAP_ID, "board.inner_boundary.world"],
    replace_with: "Measured inner board length and width of the user's game.",
  },
];
const landmarks: Landmark[] = landmarkFits.map((l) => ({
  id: l.id,
  source_image_id: SOURCE_ID,
  px: [round(l.px[0]), round(l.px[1])] as PixelPoint,
  uncertainty_px: round(Math.max(1, l.widthPx / 2), 1),
  description: `Where the ${MARKING_SEEDS.find((m) => l.id.includes(m.id))!.what} meets the ${l.side} long board (ice-contact edge); line centre extrapolated from ${l.offsets} offsets 15-60 px inside.`,
  visibility: "visible",
}));
geometry.geometry_version = GEOMETRY_VERSION;
geometry.assumptions = [...geometry.assumptions.filter((a) => !assumptions.some((b) => b.id === a.id)), ...assumptions];
geometry.landmarks = [...geometry.landmarks.filter((l) => !l.id.startsWith("lm.board.")), ...landmarks];
geometry.image_traces = [
  ...geometry.image_traces.filter((t) => t.id !== TRACE_ID),
  {
    id: TRACE_ID,
    source_image_id: SOURCE_ID,
    feature: "board_inner_boundary",
    closed: true,
    points_px: stored.map((t) => [round(t.p[0]), round(t.p[1])] as PixelPoint),
    landmark_ids: landmarks.map((l) => l.id),
    status: "traced",
    uncertainty_px: uncertaintyPx,
    method: `scripts/trace-board.ts: flood fill of the ice from seed ${SEED.join(",")} bounded by max(R,G,B) < ${BARRIER_MAX_CHANNEL}; ${RAYS} rays from the ice centre; sub-pixel crossing of the ice/strip mid-level; robust line (4 sides) and circle (4 corners) fits; every ${STORE_EVERY}nd ray stored.`,
    inferred_segments: inferred,
    note: "Ice-contact edge of the installed boards (inner base). Not the board top rail, not the outer housing, not the loose sheet perimeter (hidden under the boards).",
  },
];
geometry.image_to_world = [
  ...geometry.image_to_world.filter((m) => m.id !== MAP_ID),
  {
    id: MAP_ID,
    source_image_id: SOURCE_ID,
    model: "similarity",
    matrix,
    plane: "ice_top_z0",
    status: "assumed",
    assumption_ids: ["assume.overhead_near_orthographic", "assume.preview_scale_catalog_length"],
    note: `PREVIEW ONLY. ${round(s, 6)} mm/px uniform; origin at the traced boundary centre; +x along the fitted long axis toward image-right; +y toward image-top. Implied width ${round(Wpx * s, 1)} mm vs catalog approx. ${CATALOG_PLAYING_WIDTH_MM} mm. Ice plane only; never apply to elevated objects.`,
  },
];
geometry.board.inner_boundary.image_trace_ids = [TRACE_ID];
geometry.board.inner_boundary.world = {
  points_mm: stored.map((t) => toWorld(t.p)),
  closed: true,
  status: "assumed",
  source_ids: [SOURCE_ID, "stiga_canada_catalog"],
  mapping_id: MAP_ID,
  uncertainty_mm: null,
  note: "Shape traced from the overhead; size from an ASSUMED uniform preview scale. Not calibrated millimetres.",
};
geometry.board.inner_boundary.note =
  "Ice contact boundary of the installed boards, traced provisionally from stiga_se_fi_overhead (see docs/board-trace.md). Corner radius and length stay unknown in mm until measured; pixel values are in validation/05-board-report.json.";
writeFileSync(GEOMETRY, JSON.stringify(geometry, null, 2) + "\n");

const report = {
  iteration: "05",
  source_image_id: SOURCE_ID,
  source_sha256: image.sha256,
  parameters: { SEED, BARRIER_MAX_CHANNEL, MIN_INSIDE_LEVEL, MIN_EDGE_CONTRAST, LOCAL_WINDOW, LOCAL_OUTLIER_PX, MAX_FILL_GAP_RAYS, RAYS, STORE_EVERY, CORNER_SEED_PX, MARKING_SEEDS },
  ice_region: { area_px: area, bbox_px: [minX, minY, maxX, maxY], centre_px: centre.map((v) => round(v)) },
  samples: { total: RAYS, redetected_around_model: redetected, ok_quality: good.length, detected_and_consistent: detected, filled: RAYS - detected, stored: stored.length },
  fits_px: Object.fromEntries(Object.entries(fits).map(([k, v]) => [k, { rms: round(v.rms, 3), max_abs: round(v.maxAbs, 2), inliers: v.n, outliers: v.outliers }])),
  corner_radius_px: cornerRadii,
  corner_tangency_gap_px: tangency,
  dark_strip_width_px: { median: round(stripMedian, 2), min: round(Math.min(...stripWidths), 2), max: round(Math.max(...stripWidths), 2) },
  projection_checks: {
    top_vs_bottom_angle_deg: round(angleBetweenLinesDeg(sides.top, sides.bottom), 4),
    left_vs_right_angle_deg: round(angleBetweenLinesDeg(sides.left, sides.right), 4),
    top_vs_left_deviation_from_90_deg: round(90 - angleBetweenLinesDeg(sides.top, sides.left), 4),
    bottom_vs_right_deviation_from_90_deg: round(90 - angleBetweenLinesDeg(sides.bottom, sides.right), 4),
    width_px_at_left_mid_right: widthPx.map((v) => round(v)),
    length_px_at_top_mid_bottom: lengthPx.map((v) => round(v)),
    long_axis_angle_to_image_x_deg: round((Math.atan2(axisDir[1], axisDir[0]) * 180) / Math.PI, 4),
  },
  side_bow_px: bow,
  side_bow_note: "Positive sagitta: middle of the side lies inward of its ends; negative: bulges outward. A systematic outward bow on both long sides is consistent with lens barrel distortion or physically bowed boards; the photograph cannot separate them. The trace keeps detected points, so the bow is preserved.",
  marking_checks_px: markingChecks,
  landmarks: landmarkFits.map((l) => ({ id: l.id, px: l.px.map((v) => round(v)), offsets_used: l.offsets, line_fit_spread_px: round(l.spreadPx, 2), marking_width_px: l.widthPx })),
  extents_px: { length: round(Lpx), width: round(Wpx), aspect: round(Lpx / Wpx, 4), catalog_aspect_845_457: round(CATALOG_PLAYING_LENGTH_MM / CATALOG_PLAYING_WIDTH_MM, 4) },
  error_estimate_px: {
    edge_localisation_rms_worst_straight: round(straightRms, 3),
    boundary_definition_dark_strip_median: round(stripMedian, 2),
    trace_uncertainty_px: uncertaintyPx,
    rule: "ceil(median dark-strip width + 2 x worst straight-side RMS). The strip term dominates: the true contact line may lie anywhere across the strip.",
    similarity_mapping_bound_px: round(Math.max(...Object.values(bow).map((b) => Math.abs(b.sagitta_px))) + Math.abs(widthPx[2]! - widthPx[0]!) / 2, 2),
    similarity_mapping_bound_rule: "max |side sagitta| + half the width change from left to right (keystone). Bounds how far the uniform-scale mapping can misplace ice-plane points given the bow and keystone seen here; lens distortion and board shape are not separated.",
  },
  preview_mapping_assumed: {
    mapping_id: MAP_ID,
    mm_per_px: round(s, 6),
    implied_width_mm: round(Wpx * s, 2),
    catalog_width_mm: CATALOG_PLAYING_WIDTH_MM,
    width_discrepancy_mm: round(Wpx * s - CATALOG_PLAYING_WIDTH_MM, 2),
    trace_uncertainty_mm_under_assumed_scale: round(uncertaintyPx * s, 2),
    note: "All mm values here depend on assume.preview_scale_catalog_length and are NOT calibrated.",
  },
};
writeFileSync(REPORT, JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify({ bow, fits_px: report.fits_px, corner_radius_px: cornerRadii, tangency, checks: report.projection_checks, marking: markingChecks, extents: report.extents_px, err: report.error_estimate_px, preview: report.preview_mapping_assumed, samples: report.samples, inferred_segments: inferred.length }, null, 1));
