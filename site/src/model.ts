// Combo editor model (docs/combo-editor.md): the combo document, its validation, the slot and board mathematics and
// the arrow geometry. Pure TypeScript with no DOM or three.js, so it is tested in Node (site/tests).
//
// World frame as everywhere in the repo (docs/geometry.md): millimetres, +x toward the E goal (the goal the white/blue
// W team attacks; the yellow E team defends it), +y to the attackers' left, +z up, angles counter-clockwise seen from above. A figure's state is
// (arc_mm, theta_deg): arc length along its slot centreline and rotation about the fixture axis relative to the team's
// home heading (W 0 deg, E 180 deg), exactly as in the traces and the pose-preview composition.
import rinkJson from "./generated/rink.json" with { type: "json" };

export type Vec2 = [number, number];
export type Team = "W" | "E";

export interface Rink {
  geometry_version: string;
  puck_radius_mm: number;
  slots: Record<string, number[][]>;
  board_mm: number[][];
  goals: { W: { at_mm: number[]; mouth_mm: number }; E: { at_mm: number[]; mouth_mm: number }; depth_mm: number };
}
export const RINK = rinkJson as unknown as Rink;
export const PIDS = Object.keys(RINK.slots);
export const HOME_HEADING_DEG: Record<Team, number> = { W: 0, E: 180 };
export const teamOf = (pid: string): Team => (pid.startsWith("W") ? "W" : "E");
/** Middle of a skater's blade in the figure frame (mm; +x = facing, +y = the figure's left), as in the move pictures. */
export const BLADE_MID_MM: Vec2 = [2.8, 33.1];
export const SCHEMA_ID = "th-combo/1";

export const ROLE_NAMES: Record<string, string> = { G: "Goalie", LD: "Left defender", RD: "Right defender", C: "Centre", LW: "Left wing", RW: "Right wing" };
export const figureName = (pid: string): string => `${teamOf(pid) === "W" ? "White" : "Yellow"} ${ROLE_NAMES[pid.slice(2)]!.toLowerCase()}`;

export interface FigurePose { arc_mm: number; theta_deg: number; hidden?: boolean }
export type ArrowStyle = "solid" | "dashed";
export interface Arrow { id: string; points_mm: Vec2[]; style: ArrowStyle; curved: boolean; color: string; width_mm: number; head: boolean }
export interface Marker { id: string; label: string; x_mm: number; y_mm: number; color: string }
export interface CameraPose { position_mm: [number, number, number]; target_mm: [number, number, number]; fov_deg: number }
export interface Combo {
  schema: typeof SCHEMA_ID;
  name: string;
  description: string;
  figures: Record<string, FigurePose>;
  puck: { x_mm: number; y_mm: number; hidden?: boolean };
  arrows: Arrow[];
  markers: Marker[];
  camera?: CameraPose;
}

export const COLORS = { pass: "#16be34", move: "#8b95a5", red: "#c8102e", blue: "#1f5fbf", yellow: "#ffcc1a", white: "#ffffff", navy: "#0e2a57" } as const;
export const ARROW_DEFAULTS = { style: "solid" as ArrowStyle, curved: false, color: COLORS.pass as string, width_mm: 4.2, head: true };
export const MARKER_RADIUS_MM = 11;

// ---------------------------------------------------------------- slots

export interface Slot {
  pid: string;
  length: number;
  at(arc: number): { point: Vec2; tangent: Vec2 };
  nearest(q: Vec2): { arc: number; dist: number };
}

function makeSlot(pid: string, pts: number[][]): Slot {
  const cum = [0];
  for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1]! + Math.hypot(pts[i]![0]! - pts[i - 1]![0]!, pts[i]![1]! - pts[i - 1]![1]!));
  const length = cum[cum.length - 1]!;
  return {
    pid,
    length,
    at(arc) {
      const s = Math.min(Math.max(arc, 0), length);
      let lo = 0, hi = cum.length - 1;
      while (hi - lo > 1) {
        const mid = (lo + hi) >> 1;
        if (cum[mid]! <= s) lo = mid;
        else hi = mid;
      }
      const a = pts[lo]!, b = pts[hi]!, seg = cum[hi]! - cum[lo]!;
      const f = seg > 0 ? (s - cum[lo]!) / seg : 0;
      return { point: [a[0]! + f * (b[0]! - a[0]!), a[1]! + f * (b[1]! - a[1]!)], tangent: seg > 0 ? [(b[0]! - a[0]!) / seg, (b[1]! - a[1]!) / seg] : [1, 0] };
    },
    nearest(q) {
      let best = { arc: 0, dist: Infinity };
      for (let i = 0; i + 1 < pts.length; i++) {
        const a = pts[i]!, b = pts[i + 1]!;
        const dx = b[0]! - a[0]!, dy = b[1]! - a[1]!, l2 = dx * dx + dy * dy;
        const t = l2 > 0 ? Math.min(1, Math.max(0, ((q[0] - a[0]!) * dx + (q[1] - a[1]!) * dy) / l2)) : 0;
        const d = Math.hypot(q[0] - (a[0]! + t * dx), q[1] - (a[1]! + t * dy));
        if (d < best.dist) best = { arc: cum[i]! + t * Math.sqrt(l2), dist: d };
      }
      return best;
    },
  };
}

export const SLOTS: Record<string, Slot> = Object.fromEntries(PIDS.map((pid) => [pid, makeSlot(pid, RINK.slots[pid]!)]));
/** The pose code of the repo rejects the very ends of a slot; the editor keeps the same half millimetre away. */
export const clampArc = (pid: string, arc: number): number => Math.min(Math.max(arc, 0.5), SLOTS[pid]!.length - 0.5);
export const headingDeg = (pid: string, thetaDeg: number): number => HOME_HEADING_DEG[teamOf(pid)] + thetaDeg;
export const wrapDeg = (d: number): number => ((((d + 180) % 360) + 360) % 360) - 180;

/** Fixture axis position (mm) of a figure. */
export const pivotOf = (pid: string, pose: FigurePose): Vec2 => SLOTS[pid]!.at(pose.arc_mm).point;
/** A point of the figure frame (mm) in the world. */
export function figureToWorld(pid: string, pose: FigurePose, local: Vec2): Vec2 {
  const p = pivotOf(pid, pose), h = (headingDeg(pid, pose.theta_deg) * Math.PI) / 180;
  return [p[0] + Math.cos(h) * local[0] - Math.sin(h) * local[1], p[1] + Math.sin(h) * local[0] + Math.cos(h) * local[1]];
}

// ---------------------------------------------------------------- boards

const BOARD = RINK.board_mm as Vec2[];
function insideBoard(q: Vec2): boolean {
  let inside = false;
  for (let i = 0, j = BOARD.length - 1; i < BOARD.length; j = i++) {
    const a = BOARD[i]!, b = BOARD[j]!;
    if (a[1] > q[1] !== b[1] > q[1] && q[0] < ((b[0] - a[0]) * (q[1] - a[1])) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}
function nearestOnBoard(q: Vec2): { point: Vec2; dist: number } {
  let best = { point: BOARD[0]!, dist: Infinity };
  for (let i = 0; i < BOARD.length; i++) {
    const a = BOARD[i]!, b = BOARD[(i + 1) % BOARD.length]!;
    const dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy;
    const t = l2 > 0 ? Math.min(1, Math.max(0, ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / l2)) : 0;
    const p: Vec2 = [a[0] + t * dx, a[1] + t * dy], d = Math.hypot(q[0] - p[0], q[1] - p[1]);
    if (d < best.dist) best = { point: p, dist: d };
  }
  return best;
}
/** Keeps a disk of the given radius inside the inner boards (the puck may touch them, not cross them). */
export function clampInsideBoards(q: Vec2, radius: number): Vec2 {
  const n = nearestOnBoard(q), inside = insideBoard(q);
  if (inside && n.dist >= radius) return q;
  // direction from the board point into the rink
  let ux = q[0] - n.point[0], uy = q[1] - n.point[1];
  if (!inside) { ux = -ux; uy = -uy; }
  let l = Math.hypot(ux, uy);
  if (l < 1e-6) { ux = -n.point[0]; uy = -n.point[1]; l = Math.hypot(ux, uy) || 1; }
  return [n.point[0] + (ux / l) * radius, n.point[1] + (uy / l) * radius];
}

// ---------------------------------------------------------------- combos

let idCounter = 0;
export const newId = (prefix: string): string => `${prefix}${Date.now().toString(36)}${(idCounter++).toString(36)}`;

export function emptyCombo(defaults: Record<string, FigurePose>): Combo {
  return {
    schema: SCHEMA_ID, name: "New combination", description: "",
    figures: Object.fromEntries(PIDS.map((pid) => [pid, { arc_mm: clampArc(pid, defaults[pid]?.arc_mm ?? SLOTS[pid]!.length / 2), theta_deg: defaults[pid]?.theta_deg ?? 0 }])),
    puck: { x_mm: 0, y_mm: 0 }, arrows: [], markers: [],
  };
}

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isPt = (v: unknown): v is [number, number] => Array.isArray(v) && v.length >= 2 && isNum(v[0]) && isNum(v[1]);
const isColor = (v: unknown): v is string => typeof v === "string" && /^#[0-9a-fA-F]{6}$/.test(v);
const r1 = (v: number): number => Math.round(v * 10) / 10;

/**
 * Reads a combo written by a person or an AI. Lenient on what can be repaired (missing figures keep the base pose,
 * arcs are held inside the slot, `at_mm` is moved to the nearest slot point), strict on what cannot (wrong schema,
 * non-numbers). Returns the clean combo and a note for everything that was changed.
 */
export function normalizeCombo(input: unknown, base: Combo): { combo: Combo; notes: string[] } {
  const notes: string[] = [];
  if (typeof input !== "object" || input === null || Array.isArray(input)) throw new Error("The combination must be a JSON object.");
  const o = input as Record<string, unknown>;
  if (o.schema !== undefined && o.schema !== SCHEMA_ID) throw new Error(`Unknown schema "${String(o.schema)}"; this editor reads "${SCHEMA_ID}".`);
  const figures: Record<string, FigurePose> = {};
  const fin = (typeof o.figures === "object" && o.figures !== null ? o.figures : {}) as Record<string, unknown>;
  for (const key of Object.keys(fin)) if (!PIDS.includes(key)) notes.push(`Unknown figure "${key}" ignored (figures are ${PIDS.join(", ")}).`);
  for (const pid of PIDS) {
    const b = base.figures[pid]!, f = fin[pid] as Record<string, unknown> | undefined;
    if (f === undefined || f === null || typeof f !== "object") { figures[pid] = { ...b }; continue; }
    let arc = b.arc_mm;
    if (isPt(f.at_mm)) {
      const n = SLOTS[pid]!.nearest([f.at_mm[0], f.at_mm[1]]);
      arc = n.arc;
      if (n.dist > 5) notes.push(`${pid}: at_mm was ${r1(n.dist)} mm from its slot; moved onto the slot.`);
    } else if (isNum(f.arc_mm)) arc = f.arc_mm;
    else if (f.arc_mm !== undefined || f.at_mm !== undefined) throw new Error(`${pid}: arc_mm must be a number (or at_mm a [x, y] point).`);
    const clamped = clampArc(pid, arc);
    if (Math.abs(clamped - arc) > 0.6) notes.push(`${pid}: arc_mm ${r1(arc)} is outside the slot (0 to ${r1(SLOTS[pid]!.length)}); set to ${r1(clamped)}.`);
    if (f.theta_deg !== undefined && !isNum(f.theta_deg)) throw new Error(`${pid}: theta_deg must be a number.`);
    figures[pid] = { arc_mm: r1(clamped), theta_deg: r1(wrapDeg(isNum(f.theta_deg) ? f.theta_deg : b.theta_deg)), ...(f.hidden === true ? { hidden: true } : {}) };
  }
  const pin = (o.puck ?? {}) as Record<string, unknown>;
  let puckPt: Vec2 = isNum(pin.x_mm) && isNum(pin.y_mm) ? [pin.x_mm, pin.y_mm] : [base.puck.x_mm, base.puck.y_mm];
  const cl = clampInsideBoards(puckPt, RINK.puck_radius_mm);
  if (Math.hypot(cl[0] - puckPt[0], cl[1] - puckPt[1]) > 0.5) notes.push("The puck was outside the boards; moved inside.");
  puckPt = cl;
  const arrows: Arrow[] = [];
  for (const [i, raw] of (Array.isArray(o.arrows) ? o.arrows : []).entries()) {
    const a = raw as Record<string, unknown>;
    const pts = (Array.isArray(a?.points_mm) ? a.points_mm : []).filter(isPt).map((p): Vec2 => [r1(p[0]), r1(p[1])]);
    if (pts.length < 2) { notes.push(`Arrow ${i + 1} has fewer than two points; ignored.`); continue; }
    arrows.push({
      id: typeof a.id === "string" && a.id ? a.id : newId("a"), points_mm: pts,
      style: a.style === "dashed" ? "dashed" : "solid", curved: a.curved === true,
      color: isColor(a.color) ? a.color : a.style === "dashed" ? COLORS.move : ARROW_DEFAULTS.color,
      width_mm: isNum(a.width_mm) ? Math.min(12, Math.max(1.5, a.width_mm)) : ARROW_DEFAULTS.width_mm, head: a.head !== false,
    });
  }
  const markers: Marker[] = [];
  for (const [i, raw] of (Array.isArray(o.markers) ? o.markers : []).entries()) {
    const m = raw as Record<string, unknown>;
    const pt = isPt(m?.at_mm) ? m.at_mm : isNum(m?.x_mm) && isNum(m?.y_mm) ? [m.x_mm, m.y_mm] : null;
    if (!pt) { notes.push(`Marker ${i + 1} has no position; ignored.`); continue; }
    markers.push({ id: typeof m.id === "string" && m.id ? m.id : newId("m"), label: String(m.label ?? m.n ?? i + 1).slice(0, 3), x_mm: r1(pt[0]!), y_mm: r1(pt[1]!), color: isColor(m.color) ? m.color : COLORS.navy });
  }
  const ids = new Set<string>();
  for (const it of [...arrows, ...markers]) { if (ids.has(it.id)) it.id = newId("x"); ids.add(it.id); }
  const combo: Combo = {
    schema: SCHEMA_ID, name: typeof o.name === "string" ? o.name.slice(0, 80) : base.name, description: typeof o.description === "string" ? o.description.slice(0, 600) : "",
    figures, puck: { x_mm: r1(puckPt[0]), y_mm: r1(puckPt[1]), ...(pin.hidden === true ? { hidden: true } : {}) }, arrows, markers,
  };
  const c = o.camera as Record<string, unknown> | undefined;
  if (c && Array.isArray(c.position_mm) && c.position_mm.length === 3 && c.position_mm.every(isNum) && Array.isArray(c.target_mm) && c.target_mm.length === 3 && c.target_mm.every(isNum)) {
    combo.camera = { position_mm: c.position_mm as [number, number, number], target_mm: c.target_mm as [number, number, number], fov_deg: isNum(c.fov_deg) ? Math.min(80, Math.max(5, c.fov_deg)) : 24 };
  }
  return { combo, notes };
}

/** A library move (site/public/library.json) as a combo. */
export function comboFromLibrary(move: Record<string, unknown>, base: Combo): Combo {
  return normalizeCombo({ ...move, schema: SCHEMA_ID }, base).combo;
}

// ---------------------------------------------------------------- arrow geometry

function catmullRom(pts: Vec2[], perSeg = 16): Vec2[] {
  if (pts.length < 3) return pts.slice();
  const out: Vec2[] = [];
  const P = (i: number): Vec2 => pts[Math.min(pts.length - 1, Math.max(0, i))]!;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = P(i - 1), p1 = P(i), p2 = P(i + 1), p3 = P(i + 2);
    // centripetal parameterisation: no loops or overshoot at uneven spacing
    const t0 = 0, t1 = t0 + Math.sqrt(Math.hypot(p1[0] - p0[0], p1[1] - p0[1])) || 1e-3;
    const t2 = t1 + (Math.sqrt(Math.hypot(p2[0] - p1[0], p2[1] - p1[1])) || 1e-3), t3 = t2 + (Math.sqrt(Math.hypot(p3[0] - p2[0], p3[1] - p2[1])) || 1e-3);
    for (let k = 0; k < perSeg; k++) {
      const t = t1 + ((t2 - t1) * k) / perSeg;
      const lerp = (a: Vec2, b: Vec2, ta: number, tb: number): Vec2 => (tb - ta < 1e-9 ? a : [a[0] + ((b[0] - a[0]) * (t - ta)) / (tb - ta), a[1] + ((b[1] - a[1]) * (t - ta)) / (tb - ta)]);
      const a1 = lerp(p0, p1, t0, t1), a2 = lerp(p1, p2, t1, t2), a3 = lerp(p2, p3, t2, t3);
      const b1 = lerp(a1, a2, t0, t2), b2 = lerp(a2, a3, t1, t3);
      out.push(lerp(b1, b2, t1, t2));
    }
  }
  out.push(pts[pts.length - 1]!);
  return out;
}

export const polylineLength = (pts: Vec2[]): number => pts.slice(1).reduce((s, p, i) => s + Math.hypot(p[0] - pts[i]![0], p[1] - pts[i]![1]), 0);

/** The part of a polyline between arc lengths a and b. */
export function slicePolyline(pts: Vec2[], a: number, b: number): Vec2[] {
  const out: Vec2[] = [];
  let s = 0;
  for (let i = 0; i + 1 < pts.length; i++) {
    const p = pts[i]!, q = pts[i + 1]!, l = Math.hypot(q[0] - p[0], q[1] - p[1]);
    if (l < 1e-9) continue;
    const s0 = Math.max(a, s), s1 = Math.min(b, s + l);
    if (s1 > s0 || (out.length === 0 && s1 === s0 && s0 === a && a === b)) {
      const at = (x: number): Vec2 => [p[0] + ((q[0] - p[0]) * (x - s)) / l, p[1] + ((q[1] - p[1]) * (x - s)) / l];
      if (out.length === 0) out.push(at(s0));
      if (s1 > s0) out.push(at(s1));
    }
    s += l;
  }
  return out;
}

export function pointAt(pts: Vec2[], s: number): { point: Vec2; dir: Vec2 } {
  let acc = 0;
  for (let i = 0; i + 1 < pts.length; i++) {
    const p = pts[i]!, q = pts[i + 1]!, l = Math.hypot(q[0] - p[0], q[1] - p[1]);
    if (l < 1e-9) continue;
    if (s <= acc + l || i + 2 === pts.length) {
      const f = Math.min(1, Math.max(0, (s - acc) / l));
      return { point: [p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f], dir: [(q[0] - p[0]) / l, (q[1] - p[1]) / l] };
    }
    acc += l;
  }
  return { point: pts[0] ?? [0, 0], dir: [1, 0] };
}

/** The line an arrow follows: through its points, straight or as a smooth curve. */
export const arrowCentreline = (a: Pick<Arrow, "points_mm" | "curved">): Vec2[] => (a.curved ? catmullRom(a.points_mm) : a.points_mm.slice());

/**
 * The drawn line of an arrow: the centreline, shortened where an end sits under a numbered marker so that the
 * arrow head stays visible beside the circle (as in the move pictures).
 */
export function arrowDrawnLine(a: Arrow, markers: Marker[]): Vec2[] {
  const line = arrowCentreline(a);
  const len = polylineLength(line);
  const near = (p: Vec2): boolean => markers.some((m) => Math.hypot(m.x_mm - p[0], m.y_mm - p[1]) < 6);
  let s0 = near(line[0]!) ? MARKER_RADIUS_MM + 2 : 0;
  let s1 = near(line[line.length - 1]!) ? MARKER_RADIUS_MM + 2.5 : 0;
  if (len - s0 - s1 < 14) { s0 = Math.min(s0, len * 0.2); s1 = Math.min(s1, len * 0.2); }
  return slicePolyline(line, s0, len - s1);
}

export interface Ribbon { positions: number[]; indices: number[] }

/** Flat triangles (x, y pairs) of an arrow: a ribbon of the given width, optionally dashed, with a triangular head. */
export function arrowRibbon(line: Vec2[], width: number, opts: { dashed: boolean; head: boolean }): Ribbon {
  const positions: number[] = [], indices: number[] = [];
  const len = polylineLength(line);
  if (len < 0.5 || line.length < 2) return { positions, indices };
  const headLen = opts.head ? Math.min(width * 3.6, len * 0.55) : 0, headHalf = width * 1.9;
  const strip = (pts: Vec2[]): void => {
    if (pts.length < 2) return;
    const base = positions.length / 2;
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i]!, a = pts[Math.max(0, i - 1)]!, b = pts[Math.min(pts.length - 1, i + 1)]!;
      let tx = b[0] - a[0], ty = b[1] - a[1];
      const l = Math.hypot(tx, ty) || 1;
      tx /= l; ty /= l;
      // mitre: widen at corners so the ribbon keeps its width (limited at sharp turns)
      let k = 1;
      if (i > 0 && i < pts.length - 1) {
        const l1 = Math.hypot(p[0] - a[0], p[1] - a[1]) || 1, cos = ((p[0] - a[0]) / l1) * tx + ((p[1] - a[1]) / l1) * ty;
        k = Math.min(2.2, 1 / Math.max(0.3, cos));
      }
      const nx = -ty * (width / 2) * k, ny = tx * (width / 2) * k;
      positions.push(p[0] + nx, p[1] + ny, p[0] - nx, p[1] - ny);
      if (i > 0) indices.push(base + 2 * i - 2, base + 2 * i - 1, base + 2 * i, base + 2 * i - 1, base + 2 * i + 1, base + 2 * i);
    }
  };
  const cap = (c: Vec2): void => {
    const base = positions.length / 2, n = 10;
    positions.push(c[0], c[1]);
    for (let i = 0; i < n; i++) positions.push(c[0] + (Math.cos((i / n) * 2 * Math.PI) * width) / 2, c[1] + (Math.sin((i / n) * 2 * Math.PI) * width) / 2);
    for (let i = 0; i < n; i++) indices.push(base, base + 1 + i, base + 1 + ((i + 1) % n));
  };
  const shaftEnd = len - headLen * 0.75;
  if (opts.dashed) {
    const dash = width * 2.6, gap = width * 1.7;
    for (let s = 0; s < shaftEnd; s += dash + gap) strip(slicePolyline(line, s, Math.min(s + dash, shaftEnd)));
  } else {
    const shaft = slicePolyline(line, 0, shaftEnd);
    strip(shaft);
    if (shaft.length) cap(shaft[0]!);
  }
  if (opts.head && headLen > 0) {
    const tip = line[line.length - 1]!, back = pointAt(line, len - headLen).point;
    let ux = tip[0] - back[0], uy = tip[1] - back[1];
    const l = Math.hypot(ux, uy) || 1;
    ux /= l; uy /= l;
    const bx = tip[0] - ux * headLen, by = tip[1] - uy * headLen, base = positions.length / 2;
    positions.push(tip[0], tip[1], bx - uy * headHalf, by + ux * headHalf, bx + uy * headHalf, by - ux * headHalf);
    indices.push(base, base + 1, base + 2);
  }
  return { positions, indices };
}

// ---------------------------------------------------------------- share links

const b64url = (bytes: Uint8Array): string => btoa(Array.from(bytes, (b) => String.fromCharCode(b)).join("")).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64url = (s: string): Uint8Array => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
async function pipe(bytes: Uint8Array, stream: CompressionStream | DecompressionStream): Promise<Uint8Array> {
  const out = new Response(new Blob([bytes as BlobPart]).stream().pipeThrough(stream as unknown as ReadableWritablePair<Uint8Array, Uint8Array>));
  return new Uint8Array(await out.arrayBuffer());
}
/** The combo as a compact URL fragment value (deflate + base64url). */
export async function encodeShare(combo: Combo): Promise<string> {
  return b64url(await pipe(new TextEncoder().encode(JSON.stringify(combo)), new CompressionStream("deflate-raw")));
}
export async function decodeShare(s: string): Promise<unknown> {
  return JSON.parse(new TextDecoder().decode(await pipe(unb64url(s), new DecompressionStream("deflate-raw"))));
}

// ---------------------------------------------------------------- text for people and AIs

/** A short, exact description of the format and the table, for the docs page and for AI prompts. */
export function formatGuide(): string {
  const slotLines = PIDS.map((pid) => {
    const s = SLOTS[pid]!, n = 6;
    const pts = Array.from({ length: n + 1 }, (_, i) => { const a = (s.length * i) / n, p = s.at(a).point; return `${Math.round(a)}:[${Math.round(p[0])},${Math.round(p[1])}]`; });
    return `  ${pid} (${figureName(pid)}), slot length ${r1(s.length)} mm, arc:[x,y] ${pts.join(" ")}`;
  }).join("\n");
  return `FORMAT "${SCHEMA_ID}": one JSON object describing a table hockey diagram on a STIGA Play Off 21 table.

{
  "schema": "${SCHEMA_ID}",
  "name": "short title",
  "description": "one or two sentences",
  "figures": { "<id>": { "arc_mm": number, "theta_deg": number, "hidden": false } },
  "puck": { "x_mm": number, "y_mm": number },
  "arrows": [ { "points_mm": [[x, y], [x, y]], "style": "solid" | "dashed", "curved": false, "color": "#16be34", "width_mm": 4.2, "head": true } ],
  "markers": [ { "label": "1", "x_mm": number, "y_mm": number } ]
}

COORDINATES (millimetres, seen from above): x runs along the table, y across it. The white team (ids W-*) attacks
toward +x; the goal it scores in is at x = ${Math.round(RINK.goals.E.at_mm[0]!)}, y = 0, about ${Math.round(RINK.goals.E.mouth_mm)} mm wide. The yellow team (ids E-*) attacks toward -x
(goal at x = ${Math.round(RINK.goals.W.at_mm[0]!)}). +y is the white team's LEFT side. The playing surface is roughly x -420..420, y -230..230 with
rounded corners. The puck radius is ${RINK.puck_radius_mm} mm.

FIGURES: six per team, each fixed to its own slot. "arc_mm" is the distance along the slot from its start (0) to its end
(the slot length). Instead of "arc_mm" you may give "at_mm": [x, y]; the figure is put at the nearest point of its slot.
"theta_deg" turns the figure about its peg, counter-clockwise seen from above; 0 means facing the goal it attacks
(white faces +x, yellow faces -x). Figures are rigid. A skater's stick blade is about 33 mm to the figure's LEFT of the
peg: for a figure at [px, py] with heading h (white: h = theta_deg, yellow: h = 180 + theta_deg) the blade middle is at
[px + 2.8 cos h - 33.1 sin h, py + 2.8 sin h + 33.1 cos h]. To let a figure play the puck, put the puck at its blade.
A figure you leave out keeps its current place. "hidden": true removes a figure from the picture.
Slots (arc in mm : position [x, y]):
${slotLines}

ARROWS: the puck's way (passes and shots) is a solid green arrow ("#16be34"); a figure's own movement is a dashed grey
arrow ("#8b95a5"). "points_mm" lists two or more points; "curved": true draws a smooth curve through them. A pass off
the boards is one arrow with a point at the board.
MARKERS: small numbered circles, one at each touch of the puck in order ("1" where the move starts).
An arrow that ends at a marker is shortened automatically so its head stays visible.`;
}
