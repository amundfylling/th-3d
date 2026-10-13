// Which output frames a command renders: frame ranges, named presentation segments and the automatic review stills.
// Everything here is read from the resolved presentation (src/model/analysis.ts) and the trace events; it never changes
// what a frame shows, only which frames are rendered.
import { analysisFrame, type Analysis } from "../../src/model/analysis.ts";

export interface Range {
  from: number;
  to: number; // inclusive
}

/** Output frames of a segment: the integer frames f with f0 <= f < f1 (segments cover [f0, f1); adjacent ones partition). */
export function segmentRange(a: Analysis, id: string): Range {
  const s = a.timeline.segments.find((x) => x.id === id);
  if (!s) throw new Error(`no segment ${id}; segments: ${a.timeline.segments.map((x) => x.id).join(", ")}`);
  return { from: Math.ceil(s.f0 - 1e-9), to: Math.min(a.durationInFrames - 1, Math.ceil(s.f1 - 1e-9) - 1) };
}

/** "--frames 100-160,200-220" and/or "--segment shot_in,shot_freeze" -> sorted ranges; adjacent segments merge. */
export function selectRanges(a: Analysis, frames: string | null, segments: string | null): Range[] {
  const out: Range[] = [];
  for (const part of (frames ?? "").split(",").filter(Boolean)) {
    const m = /^(\d+)(?:-(\d+))?$/.exec(part.trim());
    if (!m) throw new Error(`--frames ${part}: use a, a-b or a list a-b,c-d`);
    const r = { from: Number(m[1]), to: Number(m[2] ?? m[1]) };
    if (r.to < r.from || r.to >= a.durationInFrames) throw new Error(`--frames ${part}: outside 0-${a.durationInFrames - 1}`);
    out.push(r);
  }
  for (const id of (segments ?? "").split(",").filter(Boolean)) out.push(segmentRange(a, id.trim()));
  if (!out.length) return [{ from: 0, to: a.durationInFrames - 1 }];
  out.sort((x, y) => x.from - y.from);
  const merged: Range[] = [];
  for (const r of out) {
    const last = merged[merged.length - 1];
    if (last && r.from <= last.to + 1) last.to = Math.max(last.to, r.to);
    else merged.push({ ...r });
  }
  return merged;
}

export const framesOf = (rs: Range[]): number[] => rs.flatMap((r) => Array.from({ length: r.to - r.from + 1 }, (_, i) => r.from + i));

export interface Still {
  frame: number;
  reasons: string[];
}

interface EventLike {
  id: string;
  t_estimate: number | null;
}

/**
 * Review stills derived from the trace events and the presentation: the title, the set-up, every contact just before /
 * at / after it (in the slowest play segment that shows it), every explanation freeze once the camera has arrived, the
 * middle of every camera move, the goal and the end card. Frames closer than 3 apart are merged (reasons kept).
 */
export function reviewStills(a: Analysis, events: EventLike[], gap = 8): Still[] {
  const n = a.durationInFrames;
  const fps = a.timeline.outFps;
  const clamp = (f: number) => Math.max(0, Math.min(n - 1, Math.round(f)));
  const raw: Still[] = [];
  const add = (f: number, why: string) => raw.push({ frame: clamp(f), reasons: [why] });
  const segs = a.timeline.segments;
  const w0 = a.timeline.windowStartS;
  const srcFps = a.timeline.fps;

  const title = a.graphics.find((g) => g.item.type === "title_card");
  if (title) add(title.t0 * fps + 0.7 * fps, "title card");
  // contacts and beat events: before / at / after, in the slowest play segment that passes the event
  const named = events.filter((e) => e.t_estimate !== null && (e.id.startsWith("contact.") || segs.some((s) => s.id.endsWith("_freeze") && s.kind === "hold" && Math.abs(s.t - e.t_estimate!) < 1e-9)));
  for (const e of named) {
    const u = (e.t_estimate! - w0) * srcFps;
    const plays = segs.filter((s) => s.kind === "play" && s.rate > 0 && u >= s.u0 - 1e-9 && u <= s.u0 + (s.f1 - s.f0) * s.rate + 1e-9);
    const slow = plays.sort((x, y) => x.rate - y.rate)[0];
    if (!slow) continue;
    const f = slow.f0 + (u - slow.u0) / slow.rate;
    const label = e.id.replace(/^contact\./, "");
    add(Math.max(slow.f0, f - gap), `just before ${label} (${slow.id})`);
    add(Math.min(f, slow.f1 - 1), `at ${label} (${slow.id})`);
    const after = segs.find((s) => s.f0 >= slow.f1 - 1e-9 && s.kind === "play");
    if (f + gap < slow.f1) add(f + gap, `just after ${label} (${slow.id})`);
    else if (after) add(after.f0 + gap, `just after ${label} (${after.id})`);
  }
  // explanation freezes: late in each labelled hold, when the camera has arrived and the text has faded in
  for (const s of segs) {
    if (s.kind !== "hold" || a.spec.unlabelled_holds.includes(s.id) || s.f1 - s.f0 < 12) continue;
    const f = s.f1 - Math.min(15, (s.f1 - s.f0) / 3);
    const ch = a.chapters.find((c) => f / fps >= c.t0 && f / fps <= c.t1);
    add(f, ch ? `freeze ${s.id}: "${ch.item.title}"` : `freeze ${s.id}`);
  }
  // camera moves: the middle of each transition between two different views
  for (let i = 1; i < a.cameraKeys.length; i++) {
    const k0 = a.cameraKeys[i - 1]!, k1 = a.cameraKeys[i]!;
    if (k0.view !== k1.view && k1.t > k0.t) add(((k0.t + k1.t) / 2) * fps, `camera move ${k0.view} -> ${k1.view}`);
  }
  const goal = segs.find((s) => s.id === "goal_hold");
  if (goal) add(goal.f0 + 5, "goal at full speed");
  const end = a.graphics.find((g) => g.item.type === "end_card");
  if (end) add(Math.min(n - 1, end.t1 * fps - 10), "end card");

  raw.sort((x, y) => x.frame - y.frame);
  const out: Still[] = [];
  for (const s of raw) {
    const last = out[out.length - 1];
    if (last && s.frame - last.frame < 3) last.reasons.push(...s.reasons);
    else out.push({ frame: s.frame, reasons: [...s.reasons] });
  }
  for (const s of out) {
    const af = analysisFrame(a, s.frame);
    s.reasons = [...new Set(s.reasons)];
    (s as Still & { t: number; segment: string; camera: string }).t = Math.round(af.t * 1e5) / 1e5;
    (s as Still & { segment: string }).segment = af.segment.id;
    (s as Still & { camera: string }).camera = af.camera.mode;
  }
  return out;
}
