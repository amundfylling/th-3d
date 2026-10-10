// Sports-analysis video of a contact-checked shot trace (VAR-style breakdown), shared by every analysis composition.
// Three independent tracks, all pure functions of the frame (src/model/analysis.ts, data/presentations/*.analysis.json):
//   1. shot timeline: frame -> source time of the trace (play, slow motion, rewind, freeze);
//   2. camera track: frame -> camera (eased moves between named views, stationary while text is read);
//   3. graphics: captions and object-anchored graphics, drawn in an SVG/HTML layer above the canvas.
// The physical state comes only from the trace evaluator; graphics read it and never feed back. No useFrame, no clock.
// Per-shot wording and graphic defaults come from an AnalysisConfig (remotion/ShotAnalysis.tsx, remotion/SpjassAnalysis.tsx).
import { useThree } from "@react-three/fiber";
import { ThreeCanvas } from "@remotion/three";
import { useLayoutEffect, useMemo, useState } from "react";
import { AbsoluteFill, cancelRender, staticFile, useCurrentFrame, useDelayRender, useVideoConfig } from "remotion";
import * as THREE from "three";
import geometry from "../data/geometry.json" with { type: "json" };
import { analysisFrame, resolveAnalysis, windowOpacity, type Analysis, type AnalysisSpec, type GraphicSpec, type ResolvedWindow } from "../src/model/analysis.ts";
import type { CameraView } from "../src/model/camera-track.ts";
import { pathSampler, transformPoint, type Vec2, type Vec3 } from "../src/model/pose.ts";
import { checkTraceCompatibility, shotTimeEvaluator, type AssetManifest, type ShotFrameState } from "../src/model/shot-pose.ts";
import type { ShotTrace } from "../src/model/trace.ts";
import manifest from "./asset-manifest.json" with { type: "json" };
import { toThree } from "./cameras.ts";
import { ShotScene } from "./ShotScene.tsx";

type Lane = { from_mm: [number, number]; to_mm: [number, number]; end_mm: [number, number]; blocked_by: string | null };
type TraceEvent = { id: string; t_estimate: number; contact_point_local_mm?: [number, number]; lanes?: Record<string, Lane> };
export type AnalysisTrace = ShotTrace & { trace_id: string; time_base: { window_s: [number, number] }; asset_refs: Record<string, unknown>; events: TraceEvent[] };

export interface ContactChecks {
  trace_id: string;
  unexpected_penetrations: unknown[];
}

export interface AnalysisConfig {
  spec: AnalysisSpec;
  trace: AnalysisTrace;
  checks: ContactChecks;
  /** console tag of the per-frame state/camera logs ([<tag>-state], [<tag>-camera], [<tag>-check]) */
  logTag: string;
  /** render a trace with status "proposed" (the user asked for the video before reviewing the trace); default: accepted only */
  allowProposed?: boolean;
  /** extra render gate run before the trace checks (returns the names of the checks passed) */
  gate?: () => string[];
  text: { kicker: string; title: string; subtitle: string; bug: string; endTitle: string; endSteps: string[] };
  /** per graphic type defaults merged under each graphic spec */
  defaults?: Partial<Record<GraphicSpec["type"], Partial<GraphicSpec>>>;
}

export type AnalysisProps = { graphics: boolean };

const ACCENT = { amber: "#FFB21E", cyan: "#2FD6FF", red: "#FF4D4D", green: "#3BE07A" } as const;
const INK = "#F4F6FA";
const PANEL = "rgba(9, 14, 24, 0.84)";
const COND = "'Barlow Condensed', 'DejaVu Sans', sans-serif";
const SANS = "'Barlow', 'DejaVu Sans', sans-serif";

/** Rejects mismatched geometry/asset versions, unreviewed traces (unless allowed) and traces that failed the contact check. */
export function assertTraceRenderable(cfg: AnalysisConfig): string[] {
  const extra = cfg.gate ? cfg.gate() : null;
  if (extra) return extra;
  const t = cfg.trace;
  const compared = checkTraceCompatibility(t, geometry.geometry_version, manifest as AssetManifest);
  if (t.status !== "accepted" && !(cfg.allowProposed && t.status === "proposed")) throw new Error(`trace ${t.trace_id} is ${t.status}, not accepted`);
  // CLAUDE.md "Contact physics": only a trace whose finite-puck contact check passed is played
  if (cfg.checks.trace_id !== t.trace_id) throw new Error(`contact checks are for ${cfg.checks.trace_id}, not ${t.trace_id}`);
  if (cfg.checks.unexpected_penetrations.length > 0) throw new Error(`trace ${t.trace_id} overlaps geometry: ${JSON.stringify(cfg.checks.unexpected_penetrations)}`);
  return [...compared, "contact_checks", ...(t.status === "proposed" ? ["status_proposed_allowed"] : [])];
}

// ---------------------------------------------------------------- camera
function makeCamera(v: CameraView, width: number, height: number, cam = new THREE.PerspectiveCamera()): THREE.PerspectiveCamera {
  cam.fov = v.fovDeg;
  cam.aspect = width / height;
  cam.near = 0.004;
  cam.far = 10;
  cam.up.set(0, 1, 0);
  cam.position.set(...toThree(v.positionMm));
  cam.lookAt(...toThree(v.targetMm));
  cam.updateProjectionMatrix();
  cam.updateMatrixWorld(true);
  return cam;
}

/** Sets the canvas camera for this frame (absolute, from the camera track). */
const CameraRig: React.FC<{ view: CameraView; frame: number; tag: string }> = ({ view, frame, tag }) => {
  const { camera, size } = useThree();
  useLayoutEffect(() => {
    const c = makeCamera(view, size.width, size.height, camera as THREE.PerspectiveCamera);
    // read back the canvas camera (glTF metres -> world mm) so the export can compare it with the pure camera track
    const mm = (x: number, y: number, z: number): number[] => [x * 1000, -z * 1000, y * 1000].map((v) => Math.round(v * 100) / 100);
    console.log(`[${tag}-camera] ${JSON.stringify({ frame, position: mm(c.position.x, c.position.y, c.position.z), fov: Math.round(c.fov * 1e4) / 1e4 })}`);
  }, [view, camera, size, frame, tag]);
  return null;
};

// ---------------------------------------------------------------- fonts
const FONTS: [string, string, string][] = [
  ["Barlow Condensed", "BarlowCondensed-ExtraBold.ttf", "800"],
  ["Barlow Condensed", "BarlowCondensed-SemiBold.ttf", "600"],
  ["Barlow", "Barlow-SemiBold.ttf", "600"],
  ["Barlow", "Barlow-Medium.ttf", "500"],
];
function useFonts(): void {
  const { delayRender, continueRender } = useDelayRender();
  const [handle] = useState(() => delayRender("fonts"));
  useLayoutEffect(() => {
    Promise.all(FONTS.map(([family, file, weight]) => new FontFace(family, `url(${staticFile(`fonts/${file}`)})`, { weight }).load().then((f) => document.fonts.add(f))))
      .then(() => continueRender(handle))
      .catch((e: unknown) => cancelRender(e instanceof Error ? e : new Error(String(e))));
  }, [continueRender, handle]);
}

// ---------------------------------------------------------------- graphics helpers
type Proj = (p: Vec3) => [number, number] | null;

function projector(cam: THREE.PerspectiveCamera, width: number, height: number): Proj {
  return (p) => {
    const v = new THREE.Vector3(...toThree(p)).project(cam);
    if (v.z > 1 || v.z < -1) return null;
    return [((v.x + 1) / 2) * width, ((1 - v.y) / 2) * height];
  };
}

const pathD = (pts: ([number, number] | null)[]): string => {
  const ok = pts.filter((p): p is [number, number] => p !== null);
  return ok.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
};

function iceCircle(proj: Proj, c: Vec3, r: number, n = 48): string {
  return pathD(Array.from({ length: n + 1 }, (_, i) => proj([c[0] + r * Math.cos((2 * Math.PI * i) / n), c[1] + r * Math.sin((2 * Math.PI * i) / n), 1]))) + " Z";
}

/** Arrow on the ice along world points, drawn on up to `progress` of its length; head at the end. */
function IceArrow({ proj, pts, color, progress, width = 7 }: { proj: Proj; pts: Vec3[]; color: string; progress: number; width?: number }) {
  const lens = pts.slice(1).map((p, i) => Math.hypot(p[0] - pts[i]![0], p[1] - pts[i]![1]));
  const total = lens.reduce((a, b) => a + b, 0);
  let left = total * Math.min(1, Math.max(0, progress));
  const drawn: Vec3[] = [pts[0]!];
  for (let i = 0; i < lens.length && left > 0; i++) {
    const f = Math.min(1, left / lens[i]!);
    const a = pts[i]!, b = pts[i + 1]!;
    drawn.push([a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])]);
    left -= lens[i]!;
  }
  if (drawn.length < 2) return null;
  const tip = drawn[drawn.length - 1]!, prev = drawn[drawn.length - 2]!;
  const dx = tip[0] - prev[0], dy = tip[1] - prev[1], L = Math.hypot(dx, dy) || 1;
  const ux = dx / L, uy = dy / L, hl = 22, hw = 13;
  const head = [proj([tip[0] + ux * hl * 0.35, tip[1] + uy * hl * 0.35, 1]), proj([tip[0] - ux * hl + -uy * hw, tip[1] - uy * hl + ux * hw, 1]), proj([tip[0] - ux * hl - -uy * hw, tip[1] - uy * hl - ux * hw, 1])];
  const shaft = drawn.slice(0, -1).concat([[tip[0] - ux * hl * 0.6, tip[1] - uy * hl * 0.6, 1]]);
  return (
    <g>
      <path d={pathD(shaft.map(proj))} fill="none" stroke="rgba(0,0,0,0.45)" strokeWidth={width + 5} strokeLinecap="round" strokeLinejoin="round" />
      <path d={pathD(shaft.map(proj))} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" />
      {head.every(Boolean) ? <path d={pathD(head) + " Z"} fill={color} stroke="rgba(0,0,0,0.45)" strokeWidth={2} /> : null}
    </g>
  );
}

function Tag({ x, y, text, color, opacity }: { x: number; y: number; text: string; color: string; opacity: number }) {
  return (
    <div style={{ position: "absolute", left: x, top: y, transform: "translate(-50%, -100%)", opacity, display: "flex", alignItems: "stretch", fontFamily: COND, fontWeight: 600, fontSize: 30, letterSpacing: 1.5, color: INK, whiteSpace: "nowrap", boxShadow: "0 6px 18px rgba(0,0,0,0.35)" }}>
      <div style={{ width: 7, background: color }} />
      <div style={{ background: PANEL, padding: "5px 14px 4px 12px" }}>{text}</div>
    </div>
  );
}

// ---------------------------------------------------------------- composition factory
export function createAnalysisVideo(cfg: AnalysisConfig): { ANALYSIS: Analysis; Component: React.FC<AnalysisProps> } {
  const ANALYSIS = resolveAnalysis(cfg.spec, cfg.trace as unknown as Parameters<typeof resolveAnalysis>[1]);
  const stateAt = shotTimeEvaluator(cfg.trace, geometry as Parameters<typeof shotTimeEvaluator>[1]);
  const event = (id: string): TraceEvent => {
    const e = cfg.trace.events.find((x) => x.id === id);
    if (!e) throw new Error(`trace ${cfg.trace.trace_id} has no event ${id}`);
    return e;
  };
  const param = (spec: GraphicSpec): GraphicSpec => ({ ...(cfg.defaults?.[spec.type] ?? {}), ...spec });
  const markerLabel = (svg: React.ReactNode[], html: React.ReactNode[], id: string, cc: [number, number], off: [number, number], text: string, color: string, o: number) => {
    // label beside the marked point (screen space), never on top of it
    const lx = cc[0] + off[0], ly = cc[1] + off[1];
    const sx = Math.sign(off[0]) || 1, sy = Math.sign(off[1]) || 1;
    svg.push(<polyline key={id + "l"} points={`${cc[0] + 8 * sx},${cc[1] + 8 * sy} ${lx - 20 * sx},${ly - 20 * sy} ${lx},${ly - 20 * sy}`} fill="none" stroke={color} strokeWidth={2.5} opacity={o} />);
    html.push(<Tag key={id + "t"} x={lx + 170 * sx} y={ly + (sy < 0 ? -40 : 0)} text={text} color={color} opacity={o} />);
  };

  const Graphics: React.FC<{ frame: number; state: ShotFrameState; cam: THREE.PerspectiveCamera; width: number; height: number }> = ({ frame, state, cam, width, height }) => {
    const af = analysisFrame(ANALYSIS, frame);
    const time = af.time;
    const proj = projector(cam, width, height);
    const active = ANALYSIS.graphics.map((g) => ({ g, o: windowOpacity(g, time) })).filter((x) => x.o > 0);
    const svg: React.ReactNode[] = [];
    const html: React.ReactNode[] = [];
    const since = (g: ResolvedWindow<GraphicSpec>): number => time - g.t0;
    for (const { g, o } of active) {
      const spec = param(g.item);
      const color = ACCENT[spec.accent ?? "amber"];
      if (spec.type === "highlight") {
        const f = state.figures[spec.target!]!;
        const c: Vec3 = [f.pivotMm[0], f.pivotMm[1], 1];
        svg.push(<path key={spec.id + "g"} d={iceCircle(proj, c, 34)} fill={color} fillOpacity={0.16 * o} stroke="none" />);
        svg.push(<path key={spec.id} d={iceCircle(proj, c, 34)} fill="none" stroke={color} strokeWidth={4} opacity={o} />);
        // tag beside the figure (screen space, to the left so it never covers the puck side), with a short leader
        const mid = proj([f.pivotMm[0], f.pivotMm[1], 40]);
        if (mid) {
          const [ox, oy] = spec.label_offset_px ?? [-150, -60];
          const tx = mid[0] + ox, ty = mid[1] + oy;
          const sx = Math.sign(ox) || -1;
          svg.push(<polyline key={spec.id + "l"} points={`${mid[0] + 22 * sx},${mid[1]} ${tx - 40 * sx},${ty} ${tx},${ty}`} fill="none" stroke={color} strokeWidth={2.5} opacity={o} />);
          html.push(<Tag key={spec.id + "t"} x={tx + 70 * sx} y={ty + 20} text={spec.label ?? spec.target!} color={color} opacity={o} />);
        }
      } else if (spec.type === "pass_arrow" || spec.type === "puck_arrow") {
        const te = event(spec.event!).t_estimate;
        const p0 = stateAt(te, 0).puckMm, p1 = stateAt(te + 0.012, 0).puckMm;
        const d = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]);
        const u: Vec2 = [(p1[0] - p0[0]) / d, (p1[1] - p0[1]) / d];
        const s0 = spec.start_mm ?? 22, len = spec.length_mm ?? 175;
        const start: Vec3 = [p0[0] + u[0] * s0, p0[1] + u[1] * s0, 1];
        const end: Vec3 = [p0[0] + u[0] * len, p0[1] + u[1] * len, 1];
        svg.push(<g key={spec.id} opacity={o}><IceArrow proj={proj} pts={[start, end]} color={color} progress={since(g) / 0.6} /></g>);
        const lo = spec.label_offset_mm ?? [30, 0];
        const la = spec.label_at_mm ?? 120;
        const lab = proj([p0[0] + u[0] * la + lo[0], p0[1] + u[1] * la + lo[1], 1]);
        if (lab && spec.label && since(g) > 0.5) html.push(<Tag key={spec.id + "t"} x={lab[0] + 70} y={lab[1]} text={spec.label} color={color} opacity={o * Math.min(1, (since(g) - 0.5) / 0.25)} />);
      } else if (spec.type === "contact_marker") {
        const ev = event(spec.event!);
        const local = spec.local_mm ?? ev.contact_point_local_mm!;
        const fig = stateAt(ev.t_estimate, 0).figures[spec.target!]!;
        const cp = transformPoint(fig.matrix, [local[0], local[1], 0]);
        const c: Vec3 = [cp[0], cp[1], 2];
        const pulse = 1 + 0.18 * Math.max(0, 1 - since(g) / 0.5);
        svg.push(<path key={spec.id} d={iceCircle(proj, c, 10 * pulse)} fill="none" stroke={color} strokeWidth={4} opacity={o} />);
        const cc = proj(c);
        if (cc) markerLabel(svg, html, spec.id, cc, spec.label_offset_px ?? [150, 120], spec.label ?? "CONTACT", color, o);
      } else if (spec.type === "puck_marker") {
        const p = state.puckMm;
        const c: Vec3 = [p[0], p[1], 1];
        const pulse = 1 + 0.18 * Math.max(0, 1 - since(g) / 0.5);
        svg.push(<path key={spec.id} d={iceCircle(proj, c, (spec.radius_mm ?? 17) * pulse)} fill="none" stroke={color} strokeWidth={4} opacity={o} />);
        const cc = proj(c);
        if (cc && spec.label) markerLabel(svg, html, spec.id, cc, spec.label_offset_px ?? [150, 120], spec.label, color, o);
      } else if (spec.type === "slot_arrow") {
        const fp = geometry.fixture_paths.find((p) => p.player_id === spec.target)!;
        const path = pathSampler(fp.id, "skater", fp.centreline.points_mm.map((p) => [p[0]!, p[1]!] as Vec2));
        const a0 = stateAt(event(spec.event!).t_estimate, 0).figures[spec.target!]!.arcMm + (spec.ahead_mm ?? 25), a1 = Math.min(path.length, a0 + (spec.length_mm ?? 125));
        const off = spec.offset_mm ?? -40;
        const pts: Vec3[] = [];
        for (let k = 0; k <= 12; k++) {
          const s = a0 + ((a1 - a0) * k) / 12, q = path.at(s);
          pts.push([q.point[0] - q.tangent[1] * off, q.point[1] + q.tangent[0] * off, 1]);
        }
        svg.push(<g key={spec.id} opacity={o}><IceArrow proj={proj} pts={pts} color={color} progress={since(g) / 0.7} /></g>);
      } else if (spec.type === "rotation_arrow") {
        // arc around the figure's pivot at its pose at the event, seen from above: counter-clockwise = increasing angle
        const fig = stateAt(event(spec.event!).t_estimate, 0).figures[spec.target!]!;
        const r = spec.radius_mm ?? 30, sgn = spec.direction === "cw" ? -1 : 1;
        const a0 = ((fig.headingDeg + (spec.start_deg ?? 0)) * Math.PI) / 180, sw = ((spec.sweep_deg ?? 120) * Math.PI) / 180;
        const pts: Vec3[] = [];
        for (let k = 0; k <= 24; k++) {
          const a = a0 + (sgn * sw * k) / 24;
          pts.push([fig.pivotMm[0] + r * Math.cos(a), fig.pivotMm[1] + r * Math.sin(a), 1]);
        }
        svg.push(<g key={spec.id} opacity={o}><IceArrow proj={proj} pts={pts} color={color} progress={since(g) / 0.7} width={6} /></g>);
        const mid = proj(pts[12]!);
        if (mid && spec.label && since(g) > 0.5) {
          const [ox, oy] = spec.label_offset_px ?? [0, -40];
          html.push(<Tag key={spec.id + "t"} x={mid[0] + ox} y={mid[1] + oy} text={spec.label} color={color} opacity={o * Math.min(1, (since(g) - 0.5) / 0.25)} />);
        }
      } else if (spec.type === "puck_trail") {
        const n = 16, dt = 0.0035;
        const earliest = event(spec.event!).t_estimate - (spec.back_s ?? 0.15);
        const pts = Array.from({ length: n }, (_, k) => {
          const tk = Math.max(af.t - k * dt, earliest);
          return proj([...(stateAt(tk, 0).puckMm.slice(0, 2) as [number, number]), 6] as Vec3);
        });
        for (let k = 0; k + 1 < n; k++) {
          const a = pts[k], b = pts[k + 1];
          // amber streak with a thin dark edge so it reads on the white ice
          if (a && b && Math.hypot(a[0] - b[0], a[1] - b[1]) > 0.5) {
            const fall = 1 - k / n;
            svg.push(
              <line key={spec.id + "e" + k} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="rgba(9,14,24,0.55)" strokeWidth={9 * fall + 3} strokeLinecap="round" opacity={0.6 * o * fall} />,
              <line key={spec.id + k} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={ACCENT.amber} strokeWidth={9 * fall} strokeLinecap="round" opacity={0.9 * o * fall} />,
            );
          }
        }
      } else if (spec.type === "lane") {
        // an attacking option drawn on the ice: from the puck (or the receiver) to its target, or to where the swept
        // finite puck would first touch a defending figure (a cross); never part of the physical state
        const ln = event(spec.event!).lanes?.[spec.lane!];
        if (!ln) throw new Error(`event ${spec.event} has no lane ${spec.lane}`);
        const blocked = !spec.option && ln.blocked_by !== null;
        const end = spec.option ? ln.to_mm : ln.end_mm;
        const col = spec.accent ? color : blocked ? ACCENT.red : ACCENT.green;
        const a: Vec3 = [ln.from_mm[0], ln.from_mm[1], 1], b: Vec3 = [end[0], end[1], 1];
        const prog = since(g) / (spec.ghost_s ?? 0.6);
        svg.push(<g key={spec.id} opacity={o}><IceArrow proj={proj} pts={[a, b]} color={col} progress={blocked ? Math.min(prog, 0.999) : prog} width={6} /></g>);
        if (spec.ghost_s) {
          const f = Math.min(1, Math.max(0, prog));
          const c: Vec3 = [a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), 1];
          svg.push(<path key={spec.id + "g"} d={iceCircle(proj, c, 12.7)} fill="#10141c" fillOpacity={0.55 * o} stroke={col} strokeWidth={2} opacity={o} />);
        }
        if (blocked && prog >= 1) {
          const k = 13, c0 = proj([b[0] - k, b[1] - k, 2]), c1 = proj([b[0] + k, b[1] + k, 2]), c2 = proj([b[0] - k, b[1] + k, 2]), c3 = proj([b[0] + k, b[1] - k, 2]);
          if (c0 && c1 && c2 && c3) {
            for (const [u, v, w] of [[c0, c1, 10], [c2, c3, 10], [c0, c1, 6], [c2, c3, 6]] as const) {
              svg.push(<line key={spec.id + "x" + u[0] + w} x1={u[0]} y1={u[1]} x2={v[0]} y2={v[1]} stroke={w === 10 ? "rgba(0,0,0,0.5)" : ACCENT.red} strokeWidth={w} strokeLinecap="round" opacity={o} />);
            }
          }
        }
        const tip = proj(b);
        if (tip && spec.label && prog >= 1) markerLabel(svg, html, spec.id, tip, spec.label_offset_px ?? [150, 120], spec.label, col, o * Math.min(1, (prog - 1) * 4 + 0.001));
      } else if (spec.type === "goal_banner") {
        const s = Math.min(1, since(g) / 0.25);
        html.push(
          <div key={spec.id} style={{ position: "absolute", left: 56, top: 132, display: "flex", opacity: o }}>
            <div style={{ display: "flex", alignItems: "center", gap: 22, background: PANEL, padding: "10px 46px 8px 36px", transform: `scale(${0.9 + 0.1 * s})`, boxShadow: "0 10px 30px rgba(0,0,0,0.35)" }}>
              <div style={{ width: 12, height: 64, background: color }} />
              <div style={{ fontFamily: COND, fontWeight: 800, fontSize: 92, color: INK, letterSpacing: 6, lineHeight: 1 }}>{spec.label ?? "GOAL"}</div>
            </div>
          </div>,
        );
      } else if (spec.type === "title_card") {
        const s = Math.min(1, since(g) / 0.6);
        html.push(
          <div key={spec.id + "v"} style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 1250, opacity: o, background: "linear-gradient(90deg, rgba(8,12,20,0.78) 0%, rgba(8,12,20,0.55) 55%, rgba(8,12,20,0) 100%)" }} />,
          <div key={spec.id} style={{ position: "absolute", left: 120, bottom: 150, opacity: o }}>
            <div style={{ fontFamily: COND, fontWeight: 600, fontSize: 34, letterSpacing: 8, color: ACCENT.amber }}>{cfg.text.kicker}</div>
            <div style={{ fontFamily: COND, fontWeight: 800, fontSize: 150, lineHeight: 0.95, color: INK, letterSpacing: 2 + 6 * (1 - s), textShadow: "0 6px 30px rgba(0,0,0,0.45)" }}>{cfg.text.title}</div>
            <div style={{ height: 8, width: 460 * s, background: ACCENT.amber, marginTop: 14 }} />
            <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 32, color: INK, marginTop: 18, textShadow: "0 2px 10px rgba(0,0,0,0.6)" }}>{cfg.text.subtitle}</div>
          </div>,
        );
      } else if (spec.type === "end_card") {
        const steps = cfg.text.endSteps;
        html.push(
          <div key={spec.id} style={{ position: "absolute", left: 0, right: 0, bottom: 96, display: "flex", justifyContent: "center", opacity: o }}>
            <div style={{ background: PANEL, padding: "26px 44px 24px", boxShadow: "0 10px 30px rgba(0,0,0,0.35)" }}>
              <div style={{ fontFamily: COND, fontWeight: 800, fontSize: 64, color: INK, letterSpacing: 3, lineHeight: 1 }}>{cfg.text.endTitle}</div>
              <div style={{ display: "flex", gap: 34, marginTop: 18 }}>
                {steps.map((s, i) => (
                  <div key={s} style={{ display: "flex", alignItems: "center", gap: 12, fontFamily: COND, fontWeight: 600, fontSize: 34, color: INK, letterSpacing: 1 }}>
                    <div style={{ width: 40, height: 40, background: i === 1 ? ACCENT.amber : ACCENT.cyan, color: "#0A0F18", fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center" }}>{i + 1}</div>
                    {s}
                  </div>
                ))}
              </div>
            </div>
          </div>,
        );
      }
    }
    const chapter = ANALYSIS.chapters.map((c) => ({ c, o: windowOpacity(c, time) })).find((x) => x.o > 0);
    const inCard = active.some((x) => x.g.item.type === "title_card" || x.g.item.type === "end_card");
    return (
      <AbsoluteFill>
        <svg width={width} height={height} style={{ position: "absolute", left: 0, top: 0 }}>{svg}</svg>
        {html}
        {!inCard ? (
          <div style={{ position: "absolute", left: 56, top: 44, display: "flex", alignItems: "stretch", fontFamily: COND, fontWeight: 600, fontSize: 30, letterSpacing: 2, color: INK }}>
            <div style={{ width: 8, background: ACCENT.amber }} />
            <div style={{ background: PANEL, padding: "6px 16px 5px 14px" }}>{cfg.text.kicker}</div>
            <div style={{ background: "rgba(255,255,255,0.92)", color: "#0A0F18", padding: "6px 16px 5px", fontWeight: 800 }}>{cfg.text.bug}</div>
          </div>
        ) : null}
        {af.badge && !inCard ? (
          <div style={{ position: "absolute", right: 56, top: 44, display: "flex", alignItems: "center", gap: 12, background: PANEL, padding: "6px 18px 5px 16px", fontFamily: COND, fontWeight: 800, fontSize: 30, letterSpacing: 3, color: INK }}>
            <div style={{ width: 14, height: 14, borderRadius: 7, background: af.badge === "FREEZE" ? ACCENT.cyan : af.badge.startsWith("FULL") ? "#3BE07A" : af.badge === "REWIND" ? "#FF5A5A" : ACCENT.amber }} />
            {af.badge}
          </div>
        ) : null}
        {chapter ? (
          <div style={{ position: "absolute", left: 56, bottom: 56, maxWidth: 1180, display: "flex", alignItems: "stretch", opacity: chapter.o, transform: `translateY(${(1 - chapter.o) * 18}px)`, boxShadow: "0 10px 30px rgba(0,0,0,0.35)" }}>
            <div style={{ width: 92, background: ACCENT.amber, color: "#0A0F18", fontFamily: COND, fontWeight: 800, fontSize: 72, display: "flex", alignItems: "center", justifyContent: "center" }}>{chapter.c.item.number}</div>
            <div style={{ background: PANEL, padding: "16px 30px 18px 26px" }}>
              <div style={{ fontFamily: COND, fontWeight: 800, fontSize: 52, letterSpacing: 2, color: INK, lineHeight: 1 }}>{chapter.c.item.title}</div>
              <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 32, color: INK, marginTop: 10, lineHeight: 1.3 }}>{chapter.c.item.text}</div>
            </div>
          </div>
        ) : null}
      </AbsoluteFill>
    );
  };

  const Component: React.FC<AnalysisProps> = ({ graphics }) => {
    const { width, height } = useVideoConfig();
    const frame = useCurrentFrame();
    useFonts();
    useMemo(() => console.log(`[${cfg.logTag}-check] PASS versions: ${assertTraceRenderable(cfg).join(", ")}`), []);
    const af = useMemo(() => analysisFrame(ANALYSIS, frame), [frame]);
    // shot timeline -> physical state (same pure evaluator as every other composition)
    const state = useMemo(() => stateAt(af.t, frame), [af.t, frame]);
    const view = useMemo<CameraView>(() => ({ positionMm: af.camera.positionMm, targetMm: af.camera.targetMm, fovDeg: af.camera.fovDeg }), [af]);
    const cam = useMemo(() => makeCamera(view, width, height), [view, width, height]);
    // one canvas camera for the life of the tab (a new camera object per frame makes the canvas reconfigure and leak)
    const [canvasCamera] = useState(() => Object.assign(new THREE.PerspectiveCamera(), { manual: true }));
    return (
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 40%, #3a4250 0%, #161b24 75%)" }}>
        <ThreeCanvas width={width} height={height} camera={canvasCamera} linear={false} flat={false} gl={{ antialias: true, preserveDrawingBuffer: true, alpha: true }}>
          <CameraRig view={view} frame={frame} tag={cfg.logTag} />
          <ShotScene state={state} logTag={cfg.logTag} />
        </ThreeCanvas>
        {graphics ? <Graphics frame={frame} state={state} cam={cam} width={width} height={height} /> : null}
      </AbsoluteFill>
    );
  };
  return { ANALYSIS, Component };
}
