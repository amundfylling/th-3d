// Analysis video spec (sports-analysis presentation of an accepted trace): resolves the shot timeline (which source
// time each frame shows), the camera keys and the time windows of captions and graphics. Everything is a pure function
// of the presentation frame; nothing here changes the trace.
import { cameraAt, type CameraKey, type CameraState, type CameraView } from "./camera-track.ts";
import { resolveTimeline, sourceAtFrame, type PresentationSpec, type ResolvedSegment, type SegmentSpec, type Timeline } from "./presentation.ts";

/** A presentation time: seconds, or "segment.start" / "segment.end" with an optional "+0.3" / "-0.2" offset (s). */
export type TimeRef = number | string;

export interface Window {
  from: TimeRef;
  to: TimeRef;
}

export interface GraphicSpec extends Window {
  id: string;
  type:
    | "title_card"
    | "end_card"
    | "highlight"
    | "pass_arrow"
    | "puck_arrow"
    | "contact_marker"
    | "puck_marker"
    | "slot_arrow"
    | "rotation_arrow"
    | "puck_trail"
    | "goal_banner";
  /** figure id for highlights / slot and rotation arrows / contact markers */
  target?: string;
  label?: string;
  accent?: "amber" | "cyan";
  /** trace event the graphic is anchored to (the pose or puck at that source time) */
  event?: string;
  /** arrows: start offset, length and sideways offset on the ice (mm) */
  start_mm?: number;
  length_mm?: number;
  ahead_mm?: number;
  offset_mm?: number;
  /** rotation arrow: direction seen from above, arc radius (mm), start angle relative to the figure heading and sweep (deg) */
  direction?: "cw" | "ccw";
  radius_mm?: number;
  start_deg?: number;
  sweep_deg?: number;
  /** contact marker: point in the figure frame (mm); default: the event's contact_point_local_mm */
  local_mm?: [number, number];
  /** label placement: world offset of a puck-arrow label (mm), screen offset of a marker label (px) */
  label_offset_mm?: [number, number];
  /** puck arrow: distance of its label along the arrow (mm) */
  label_at_mm?: number;
  label_offset_px?: [number, number];
  /** puck trail: samples are not drawn earlier than this many seconds before the event */
  back_s?: number;
}

export interface ChapterSpec extends Window {
  id: string;
  number: string;
  title: string;
  text: string;
}

export interface AnalysisSpec {
  schema: "shot-analysis/1";
  analysis_id: string;
  trace_id: string;
  fps: number;
  width: number;
  height: number;
  segments: SegmentSpec[];
  /** segment ids whose holds are not labelled FREEZE (intro/outro holds) */
  unlabelled_holds: string[];
  /** replay segments labelled REPLAY instead of SLOW MOTION */
  replay_segments: string[];
  views: Record<string, CameraView>;
  camera: { at: TimeRef; view: string; lift?: number }[];
  chapters: ChapterSpec[];
  graphics: GraphicSpec[];
}

export interface ResolvedWindow<T> {
  item: T;
  t0: number;
  t1: number;
}

export interface Analysis {
  spec: AnalysisSpec;
  timeline: Timeline;
  durationInFrames: number;
  cameraKeys: CameraKey[];
  chapters: ResolvedWindow<ChapterSpec>[];
  graphics: ResolvedWindow<GraphicSpec>[];
}

type TraceLike = Parameters<typeof resolveTimeline>[1];

export function resolveTime(ref: TimeRef, tl: Timeline): number {
  if (typeof ref === "number") return ref;
  const m = /^([\w-]+)\.(start|end)([+-]\d+(?:\.\d+)?)?$/.exec(ref);
  if (!m) throw new Error(`bad time reference ${ref}`);
  const seg = tl.segments.find((s) => s.id === m[1]);
  if (!seg) throw new Error(`time reference to unknown segment ${m[1]}`);
  return (m[2] === "start" ? seg.f0 : seg.f1) / tl.outFps + (m[3] ? Number(m[3]) : 0);
}

export function resolveAnalysis(spec: AnalysisSpec, trace: TraceLike): Analysis {
  const pres: PresentationSpec = { schema: "shot-presentation/1", presentation_id: spec.analysis_id, trace_id: spec.trace_id, fps: spec.fps, camera: "animated", segments: spec.segments, captions: [], markers: [] };
  const timeline = resolveTimeline(pres, trace);
  const win = <T extends Window>(x: T): ResolvedWindow<T> => {
    const t0 = resolveTime(x.from, timeline), t1 = resolveTime(x.to, timeline);
    if (!(t1 > t0)) throw new Error(`window ${JSON.stringify(x)} is empty`);
    return { item: x, t0, t1 };
  };
  const cameraKeys = spec.camera.map((k) => ({ t: resolveTime(k.at, timeline), view: k.view, ...(k.lift ? { lift: k.lift } : {}) }));
  for (const k of cameraKeys) if (!spec.views[k.view]) throw new Error(`camera key uses unknown view ${k.view}`);
  return { spec, timeline, durationInFrames: timeline.durationInFrames, cameraKeys, chapters: spec.chapters.map(win), graphics: spec.graphics.map(win) };
}

/** Fade-in/out opacity of a window at time t (fade seconds at each end). */
export function windowOpacity(w: { t0: number; t1: number }, t: number, fade = 0.25): number {
  if (t < w.t0 || t > w.t1) return 0;
  return Math.min(1, (t - w.t0) / fade, (w.t1 - t) / fade);
}

/** Speed badge derived from the shot timeline only (never from the mechanics). */
export function badgeFor(seg: ResolvedSegment, spec: AnalysisSpec, outFps: number): string | null {
  if (seg.kind === "hold") return spec.unlabelled_holds.includes(seg.id) ? null : "FREEZE";
  if (seg.kind === "rewind") return "REWIND";
  const speed = (seg.rate * outFps) / spec.fps;
  if (spec.replay_segments.includes(seg.id)) return speed === 1 ? "REPLAY" : `REPLAY  ×${fmt(speed)}`;
  return speed === 1 ? "FULL SPEED" : `SLOW MOTION  ×${fmt(speed)}`;
}

const fmt = (x: number): string => (Math.round(x * 100) / 100).toString();

export interface AnalysisFrame {
  frame: number;
  /** presentation time (s) */
  time: number;
  /** source time of the trace shown */
  t: number;
  segment: ResolvedSegment;
  camera: CameraState;
  badge: string | null;
}

export function analysisFrame(a: Analysis, frame: number): AnalysisFrame {
  const { t, segment } = sourceAtFrame(a.timeline, frame);
  const time = frame / a.timeline.outFps;
  return { frame, time, t, segment, camera: cameraAt(a.spec.views, a.cameraKeys, time), badge: badgeFor(segment, a.spec, a.timeline.outFps) };
}
