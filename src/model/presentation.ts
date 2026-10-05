// Presentation timeline (iteration 24): an explicit, pure mapping from a presentation frame to the trace's source
// time. Normal speed, slow replay and pauses only change WHICH source time is shown; the physical state always comes
// from the same saved trace (src/model/shot-pose.ts). Captions and markers are separate data, never mechanics.

/** A source time: seconds, a trace event (its t_estimate) or a window frame (window start + k / fps). */
export type SourceRef = number | { event: string } | { window_frame: number };

export interface SegmentSpec {
  id: string;
  /** play: source time advances at `rate` x real time; hold: source time is frozen (a pause). */
  kind: "play" | "hold";
  from?: SourceRef;
  to?: SourceRef;
  rate?: number;
  at?: SourceRef;
  frames?: number;
}

export interface CaptionSpec {
  id: string;
  text: string;
  role: "title" | "speed" | "contact";
  segments: string[];
}

export interface MarkerSpec {
  id: string;
  target: "puck";
  segments: string[];
}

export interface PresentationSpec {
  schema: "shot-presentation/1";
  presentation_id: string;
  trace_id: string;
  fps: number;
  camera: string;
  segments: SegmentSpec[];
  captions: CaptionSpec[];
  markers: MarkerSpec[];
}

export interface ResolvedSegment {
  id: string;
  kind: "play" | "hold";
  /** Presentation frames [f0, f1) covered by the segment (may be fractional). */
  f0: number;
  f1: number;
  /** play: source time = window start + (u0 + (frame - f0) * rate) / fps, u0 in source frames. */
  u0: number;
  rate: number;
  /** hold: the frozen source time. */
  t: number;
}

export interface Timeline {
  fps: number;
  windowStartS: number;
  segments: ResolvedSegment[];
  durationInFrames: number;
}

interface TraceLike {
  trace_id: string;
  time_base: { window_s: [number, number] };
  events: { id: string; t_estimate: number | null }[];
}

/** Source frames (fractional) of a source time, snapped to an integer when it is one (exact replay frames). */
function toSourceFrames(t: number, w0: number, fps: number): number {
  const u = (t - w0) * fps;
  return Math.abs(u - Math.round(u)) < 1e-6 ? Math.round(u) : u;
}

export function resolveSource(ref: SourceRef, trace: TraceLike, fps: number): number {
  const w0 = trace.time_base.window_s[0];
  if (typeof ref === "number") return ref;
  if ("event" in ref) {
    const e = trace.events.find((x) => x.id === ref.event);
    if (!e || e.t_estimate === null) throw new Error(`presentation refers to unknown event ${ref.event}`);
    return e.t_estimate;
  }
  return w0 + ref.window_frame / fps;
}

/** Resolves a presentation spec against its trace. Throws on anything that would not evaluate the same trace. */
export function resolveTimeline(spec: PresentationSpec, trace: TraceLike): Timeline {
  if (spec.trace_id !== trace.trace_id) throw new Error(`presentation is for ${spec.trace_id}, trace is ${trace.trace_id}`);
  const fps = spec.fps;
  const [w0, w1] = trace.time_base.window_s;
  const out: ResolvedSegment[] = [];
  let f = 0;
  for (const s of spec.segments) {
    if (s.kind === "hold") {
      if (s.at === undefined || !(s.frames! > 0)) throw new Error(`${s.id}: hold needs at and frames > 0`);
      const t = resolveSource(s.at, trace, fps);
      out.push({ id: s.id, kind: "hold", f0: f, f1: f + s.frames!, u0: toSourceFrames(t, w0, fps), rate: 0, t });
      f += s.frames!;
    } else {
      if (s.from === undefined || s.to === undefined || !(s.rate! > 0)) throw new Error(`${s.id}: play needs from, to and rate > 0`);
      const a = resolveSource(s.from, trace, fps), b = resolveSource(s.to, trace, fps);
      if (!(b > a)) throw new Error(`${s.id}: play must move forward in source time`);
      const ua = toSourceFrames(a, w0, fps), ub = toSourceFrames(b, w0, fps);
      const n = (ub - ua) / s.rate!;
      out.push({ id: s.id, kind: "play", f0: f, f1: f + n, u0: ua, rate: s.rate!, t: Number.NaN });
      f += n;
    }
  }
  for (const s of out) {
    const lo = s.kind === "hold" ? s.t : w0 + s.u0 / fps;
    const hi = s.kind === "hold" ? s.t : w0 + (s.u0 + (s.f1 - s.f0) * s.rate) / fps;
    if (lo < w0 - 1e-9 || hi > w1 + 1e-9) throw new Error(`${s.id}: source time outside the trace window`);
  }
  return { fps, windowStartS: w0, segments: out, durationInFrames: Math.ceil(f - 1e-9) };
}

/** The segment shown at a presentation frame and the source time it maps to. Pure. */
export function sourceAtFrame(tl: Timeline, frame: number): { t: number; segment: ResolvedSegment } {
  if (!Number.isInteger(frame) || frame < 0) throw new Error(`frame ${frame} must be a non-negative integer`);
  const seg = tl.segments.find((s) => frame >= s.f0 && frame < s.f1) ?? tl.segments[tl.segments.length - 1]!;
  if (seg.kind === "hold") return { t: seg.t, segment: seg };
  // play beyond its last fractional frame (only the final segment) is held at its end
  const u = seg.u0 + Math.min(frame - seg.f0, seg.f1 - seg.f0) * seg.rate;
  return { t: tl.windowStartS + u / tl.fps, segment: seg };
}

/** Captions/markers active at a frame (presentation data only). */
export function activeAt<T extends { segments: string[] }>(items: T[], segment: ResolvedSegment): T[] {
  return items.filter((x) => x.segments.includes(segment.id));
}
