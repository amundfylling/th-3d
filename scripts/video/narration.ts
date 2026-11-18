// Norwegian voice-over for an analysis video, timed from the saved trace (experiment, PROPOSED).
//
//   node scripts/video/narration.ts plan  <move>                 anchors -> output times (no audio)
//   node scripts/video/narration.ts build <move> [--video f.mp4] [--out dir]   synthesise, fit, mix, mux, measure
//
// Each line in moves/<id>/narration.json is anchored to a trace event ({event}) or a presentation segment edge
// ({segment, edge}). An event anchor is resolved like the review stills do: the output frame at which the slowest play
// segment passing the event reaches it. Nothing is hand-timed: change a slow-motion rate or the trace and the plan moves.
import { execFileSync, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync, statSync } from "node:fs";
import path from "node:path";
import { resolveAnalysis, type AnalysisSpec } from "../../src/model/analysis.ts";
import { sourceAtFrame } from "../../src/model/presentation.ts";

const VOICE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/no/no_NO/talesyntese/medium/no_NO-talesyntese-medium";
const VOICE_DIR = "out/voices";
const SR = 48000;
const GAP_S = 0.15; // minimum silence before the next line
const MIN_LENGTH_SCALE = 0.75; // fastest speech allowed to fit a line

interface Anchor { event?: string; segment?: string; edge?: "start" | "end"; offset_s?: number }
interface Line { id: string; text: string; anchor: Anchor; beat?: string }
export interface Planned { id: string; text: string; start_s: number; frame: number; source: string; event_t?: number; shown_t?: number; shown_err_ms?: number }

const read = (p: string) => JSON.parse(readFileSync(p, "utf8"));

export function loadMove(move: string, specOverride?: (s: AnalysisSpec) => void) {
  const spec: AnalysisSpec = read(`data/presentations/${move}.analysis.json`);
  specOverride?.(spec);
  const trace = read(`data/traces/${move}.trace.json`);
  const a = resolveAnalysis(spec, trace);
  const narr = read(`moves/${move}/narration.json`) as { lines: Line[]; voice: string };
  return { a, trace, narr };
}

export function plan(move: string, specOverride?: (s: AnalysisSpec) => void): { planned: Planned[]; duration_s: number; fps: number } {
  const { a, trace, narr } = loadMove(move, specOverride);
  const tl = a.timeline, fps = tl.outFps;
  const planned: Planned[] = narr.lines.map((l) => {
    const off = l.anchor.offset_s ?? 0;
    if (l.anchor.segment) {
      const s = tl.segments.find((x) => x.id === l.anchor.segment);
      if (!s) throw new Error(`${l.id}: unknown segment ${l.anchor.segment}`);
      const f = l.anchor.edge === "end" ? s.f1 : s.f0;
      return { id: l.id, text: l.text, start_s: f / fps + off, frame: f, source: `${l.anchor.segment}.${l.anchor.edge ?? "start"}` };
    }
    const ev = (trace.events as { id: string; t_estimate: number | null }[]).find((e) => e.id === l.anchor.event);
    if (!ev || ev.t_estimate === null) throw new Error(`${l.id}: trace has no event ${l.anchor.event}`);
    const u = (ev.t_estimate - tl.windowStartS) * tl.fps;
    // an explanation freeze on exactly this event wins: speak when the freeze starts
    const hold = tl.segments.find((s) => s.kind === "hold" && Math.abs(s.t - ev.t_estimate!) < 1e-9 && s.id.endsWith("_freeze"));
    if (hold) {
      const fh = hold.f0;
      const shownH = sourceAtFrame(tl, Math.min(Math.ceil(fh - 1e-9), a.durationInFrames - 1)).t;
      return { id: l.id, text: l.text, start_s: fh / fps + off, frame: fh, source: `${l.anchor.event} (${hold.id}.start)`, event_t: ev.t_estimate, shown_t: shownH, shown_err_ms: (shownH - ev.t_estimate) * 1000 };
    }
    const plays = tl.segments.filter((s) => s.kind === "play" && s.rate > 0 && u >= s.u0 - 1e-9 && u <= s.u0 + (s.f1 - s.f0) * s.rate + 1e-9);
    const slow = plays.sort((x, y) => x.rate - y.rate)[0];
    if (!slow) throw new Error(`${l.id}: no play segment shows ${l.anchor.event}`);
    const f = slow.f0 + (u - slow.u0) / slow.rate;
    // video side: the source time the first whole output frame at/after f really shows
    const fi = Math.ceil(f - 1e-9);
    const shown = sourceAtFrame(tl, Math.min(fi, a.durationInFrames - 1)).t;
    return { id: l.id, text: l.text, start_s: f / fps + off, frame: f, source: `${l.anchor.event} (${slow.id})`, event_t: ev.t_estimate, shown_t: shown, shown_err_ms: (shown - ev.t_estimate) * 1000 };
  });
  planned.sort((x, y) => x.start_s - y.start_s);
  return { planned, duration_s: a.durationInFrames / fps, fps };
}

function ensureVoice(): string {
  const model = `${VOICE_DIR}/no_NO-talesyntese-medium.onnx`;
  mkdirSync(VOICE_DIR, { recursive: true });
  for (const ext of ["onnx", "onnx.json"]) {
    const f = `${VOICE_DIR}/no_NO-talesyntese-medium.${ext}`;
    if (!existsSync(f) || statSync(f).size < 1000) execFileSync("curl", ["-sSL", "--fail", "-o", f, `${VOICE_URL}.${ext}`]);
  }
  return model;
}

const synth = (model: string, jobs: { id: string; text: string; length_scale: number; out: string }[]) =>
  JSON.parse(execFileSync("python3", ["-I", "scripts/video/tts_piper.py", model], { input: JSON.stringify(jobs), encoding: "utf8", maxBuffer: 1 << 26 })) as Record<string, { duration_s: number; trim_lead_s: number }>;

/** Speech onsets (s) of a mono/stereo file: the first sample above the threshold after each expected start - 0.1 s. */
function onsets(file: string, expect: number[]): number[] {
  const raw = execFileSync("ffmpeg", ["-v", "error", "-i", file, "-ac", "1", "-ar", String(SR), "-f", "s16le", "-"], { maxBuffer: 1 << 29 });
  const a = new Int16Array(raw.buffer, raw.byteOffset, Math.floor(raw.length / 2));
  return expect.map((t) => {
    for (let i = Math.max(0, Math.floor((t - 0.1) * SR)); i < a.length; i++) if (Math.abs(a[i]!) > 600) return i / SR;
    return NaN;
  });
}

export function build(move: string, video: string, outDir: string) {
  const t0 = Date.now();
  mkdirSync(outDir, { recursive: true });
  const { planned, duration_s } = plan(move);
  const model = ensureVoice();
  const wavs = (scale: Record<string, number>, only?: string[]) => synth(model, planned.filter((p) => !only || only.includes(p.id)).map((p) => ({ id: p.id, text: p.text, length_scale: scale[p.id] ?? 1, out: `${outDir}/${p.id}.wav` })));
  const scale: Record<string, number> = {};
  let info = wavs(scale);
  // fit: every line must end GAP_S before the next line (or the end of the video)
  const refit: string[] = [];
  planned.forEach((p, i) => {
    const room = (planned[i + 1]?.start_s ?? duration_s) - p.start_s - GAP_S;
    if (info[p.id]!.duration_s > room) { scale[p.id] = Math.max(MIN_LENGTH_SCALE, (room / info[p.id]!.duration_s) * 0.97); refit.push(p.id); }
  });
  if (refit.length) info = { ...info, ...wavs(scale, refit) };
  const rows = planned.map((p, i) => {
    const room = (planned[i + 1]?.start_s ?? duration_s) - p.start_s - GAP_S;
    return { ...p, speech_s: info[p.id]!.duration_s, length_scale: scale[p.id] ?? 1, room_s: room, fits: info[p.id]!.duration_s <= room + 1e-6 };
  });
  const tts_s = (Date.now() - t0) / 1000;

  // mix: each trimmed wav delayed to its start time
  const t1 = Date.now();
  const mix = `${outDir}/narration.wav`;
  const inputs = rows.flatMap((r) => ["-i", `${outDir}/${r.id}.wav`]);
  const filt = rows.map((r, i) => `[${i}:a]aresample=${SR},adelay=${Math.round(r.start_s * 1000)}:all=1[a${i}]`).join(";") + ";" + rows.map((_, i) => `[a${i}]`).join("") + `amix=inputs=${rows.length}:normalize=0:duration=longest,apad=whole_dur=${duration_s},atrim=0:${duration_s}[m]`;
  execFileSync("ffmpeg", ["-y", "-v", "error", ...inputs, "-filter_complex", filt, "-map", "[m]", "-ar", String(SR), mix]);
  const out = `${outDir}/${move}-narrated.mp4`;
  execFileSync("ffmpeg", ["-y", "-v", "error", "-i", video, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out]);
  const mux_s = (Date.now() - t1) / 1000;

  // measure: speech onsets in the muxed file against the frame time of each anchor
  const on = onsets(out, rows.map((r) => r.start_s));
  const measured = rows.map((r, i) => ({ id: r.id, source: r.source, expected_s: Number(r.start_s.toFixed(4)), audio_onset_s: Number(on[i]!.toFixed(4)), err_ms: Math.round((on[i]! - r.start_s) * 1000), frame_event_err_ms: r.shown_err_ms === undefined ? null : Number(r.shown_err_ms.toFixed(1)), speech_s: Number(r.speech_s.toFixed(2)), length_scale: Number(r.length_scale.toFixed(3)), fits: r.fits }));
  const report = { move, voice: "no_NO-talesyntese-medium (Piper)", video_duration_s: duration_s, tts_seconds: tts_s, mix_mux_seconds: mux_s, added_seconds: tts_s + mux_s, lines: measured, max_abs_err_ms: Math.max(...measured.map((m) => Math.abs(m.err_ms))), all_fit: rows.every((r) => r.fits) };
  writeFileSync(`${outDir}/narration-report.json`, JSON.stringify(report, null, 1));
  return report;
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(import.meta.filename)) {
  const [cmd, move] = process.argv.slice(2);
  const opt = (k: string, d: string) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1]! : d; };
  if (cmd === "plan") console.log(JSON.stringify(plan(move!), null, 1));
  else if (cmd === "build") console.log(JSON.stringify(build(move!, opt("--video", `validation/moves/${move}.mp4`), opt("--out", `out/narration/${move}`)), null, 1));
  else { console.error("usage: narration.ts plan|build <move>"); process.exit(2); }
}
