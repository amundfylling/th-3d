// Iterations 06-08: traces every seeded slot (data/slot-seeds.json) in the installed overhead and the
// bare sheet, relates the two photographs by a homography fitted to the curves, and writes slot traces,
// end landmarks and fixture-path updates into data/geometry.json plus validation/slots-report.json.
// Reference photographs are only read.
import { readFileSync, writeFileSync } from "node:fs";
import type { Vec2 } from "../src/model/fit.ts";
import type { FixturePath, GeometryFile, ImageTrace, Landmark, PixelPoint, Quantity, WorldPolyline } from "../src/model/geometry.ts";
import { applyH, fitHomography, fitHomographyToCurves, type H } from "../src/model/homography.ts";
import { bilinear, loadPinnedJpeg } from "../src/model/raster.ts";
import { closestOnPolyline, polylineLength, traceSlot, type SlotTrace, type SlotTraceParams } from "../src/model/slot-trace.ts";

type ImageKey = "overhead" | "bare";
interface Seed {
  iteration: string;
  identity: string;
  occluded: { start?: string; end?: string; middle?: string };
  occluded_bare?: { start?: string; end?: string };
  overhead: Vec2[];
  bare: Vec2[];
}
const seeds = JSON.parse(readFileSync("data/slot-seeds.json", "utf8")) as { images: Record<ImageKey, string>; paths: Record<string, Seed> };

// ---- Operator parameters ------------------------------------------------------------------------
const PARAMS: Record<ImageKey, SlotTraceParams> = {
  // Overhead: dark slots (~37 px) on light ice/print. Signal = 255 - max(R,G,B).
  overhead: { step: 8, halfWindow: 60, searchRadius: 40, expectedWidth: 37, widthRange: [0.7, 1.35], minContrast: 50, extend: 120, passes: 3, lateralTol: [8, 4] },
  // Bare sheet: white cut-outs (~17 px) on a light grey sheet. Signal = min(R,G,B).
  bare: { step: 4, halfWindow: 30, searchRadius: 20, expectedWidth: 17, widthRange: [0.6, 1.5], minContrast: 10, extend: 30, passes: 3, lateralTol: [4, 2] },
};
const SIGNAL: Record<ImageKey, (r: number, g: number, b: number) => number> = {
  overhead: (r, g, b) => 255 - Math.max(r, g, b),
  bare: (r, g, b) => Math.min(r, g, b),
};
/** Stored world outline keeps every Nth centreline point. */
const WORLD_EVERY = 2;
const PREVIEW_MAP = "map.overhead.preview";
const BARE_ASSUMPTION = "assume.bare_sheet_same_slot_layout";
// --------------------------------------------------------------------------------------------------

const round = (v: number, d = 2): number => Math.round(v * 10 ** d) / 10 ** d;
const rp = (p: Vec2): PixelPoint => [round(p[0]), round(p[1])];
const GEOMETRY = "data/geometry.json";
const REPORT = "validation/slots-report.json";
const g = JSON.parse(readFileSync(GEOMETRY, "utf8")) as GeometryFile;
const imageOf = (k: ImageKey) => g.source_images.find((s) => s.source_id === seeds.images[k])!;
const rasters = Object.fromEntries(
  (["overhead", "bare"] as ImageKey[]).map((k) => {
    const img = imageOf(k);
    console.log(`decoding ${img.local_path} ...`);
    return [k, loadPinnedJpeg(img.local_path, img.sha256)];
  }),
) as Record<ImageKey, ReturnType<typeof loadPinnedJpeg>>;

// 1. Trace every path in both images.
const traces: Record<string, Record<ImageKey, SlotTrace>> = {};
const fitErr: Record<string, Record<ImageKey, { rms: number; max: number; detectedFraction: number }>> = {};
for (const [pid, seed] of Object.entries(seeds.paths)) {
  traces[pid] = {} as Record<ImageKey, SlotTrace>;
  fitErr[pid] = {} as Record<ImageKey, { rms: number; max: number; detectedFraction: number }>;
  for (const k of ["overhead", "bare"] as ImageKey[]) {
    const r = rasters[k];
    const t = traceSlot((u, v) => bilinear(r, u, v, SIGNAL[k]), seed[k], PARAMS[k]);
    traces[pid][k] = t;
    const raw = t.sections.slice(t.span[0], t.span[1] + 1).filter((s) => s.ok).map((s) => s.centre!);
    const d = raw.map((p) => closestOnPolyline(t.centreline, p).dist);
    fitErr[pid][k] = {
      rms: Math.sqrt(d.reduce((s, x) => s + x * x, 0) / d.length),
      max: Math.max(...d),
      detectedFraction: t.detected.filter(Boolean).length / t.detected.length,
    };
    console.log(`${pid} ${k}: ${t.centreline.length} pts, length ${round(polylineLength(t.centreline), 1)} px, width ${round(t.widthMedian, 1)} px, fit rms ${round(fitErr[pid][k].rms, 2)} px`);
  }
}

// 2. Homography bare -> overhead: start from the ends visible in both, refine on all curves.
const src: Vec2[] = [];
const dst: Vec2[] = [];
for (const [pid, seed] of Object.entries(seeds.paths)) {
  if (!seed.occluded.start && !seed.occluded_bare?.start) { src.push(traces[pid]!.bare.start.point); dst.push(traces[pid]!.overhead.start.point); }
  if (!seed.occluded.end && !seed.occluded_bare?.end) { src.push(traces[pid]!.bare.end.point); dst.push(traces[pid]!.overhead.end.point); }
}
const h0: H = fitHomography(src, dst);
const { h, residuals } = fitHomographyToCurves(
  h0,
  Object.keys(seeds.paths).map((pid) => ({ id: pid, src: traces[pid]!.bare.centreline, dst: traces[pid]!.overhead.centreline })),
);
const allRes = Object.values(residuals);
const hRms = Math.sqrt(allRes.reduce((s, r) => s + r.rms ** 2 * r.n, 0) / allRes.reduce((s, r) => s + r.n, 0));
console.log(`homography bare->overhead: curve RMS ${round(hRms, 2)} px`);

// 3. Occluded overhead ends predicted from the bare sheet.
interface EndCheck { pid: string; end: "start" | "end"; observed: Vec2; predicted: Vec2; extension_px: number; lateral_px: number; occluder: string | null }
const endChecks: EndCheck[] = [];
for (const [pid, seed] of Object.entries(seeds.paths)) {
  const o = traces[pid]!.overhead, b = traces[pid]!.bare;
  for (const end of ["start", "end"] as const) {
    if (seed.occluded_bare?.[end]) continue;
    const cl = o.centreline;
    const obs = end === "start" ? cl[0]! : cl[cl.length - 1]!;
    const prev = end === "start" ? cl[Math.min(4, cl.length - 1)]! : cl[Math.max(0, cl.length - 5)]!;
    const dir: Vec2 = [obs[0] - prev[0], obs[1] - prev[1]];
    const n = Math.hypot(...dir);
    const tdir: Vec2 = [dir[0] / n, dir[1] / n];
    const pred = applyH(h, end === "start" ? b.start.point : b.end.point);
    const d: Vec2 = [pred[0] - obs[0], pred[1] - obs[1]];
    endChecks.push({
      pid, end, observed: obs, predicted: pred,
      extension_px: d[0] * tdir[0] + d[1] * tdir[1],
      lateral_px: -d[0] * tdir[1] + d[1] * tdir[0],
      occluder: seed.occluded[end] ?? null,
    });
  }
}

// 4. Write canonical data (idempotent: replaces only entries owned by this script).
const map = g.image_to_world.find((m) => m.id === PREVIEW_MAP)!;
const toWorld = ([u, v]: Vec2): [number, number] => [round(map.matrix[0] * u + map.matrix[1] * v + map.matrix[2]), round(map.matrix[3] * u + map.matrix[4] * v + map.matrix[5])];
const q = (value: number | null, unit: Quantity["unit"], status: Quantity["status"], sourceIds: string[], extra: Partial<Quantity> = {}): Quantity =>
  ({ value, unit, status, uncertainty: null, source_ids: sourceIds, ...extra });

if (!g.assumptions.some((a) => a.id === BARE_ASSUMPTION)) {
  g.assumptions.push({
    id: BARE_ASSUMPTION,
    statement: "The loose sheet in stiga_ca_bare_ice_sheet (older artwork) has the same slot layout as the installed sheet in stiga_se_fi_overhead; the two photographs are related by one planar homography.",
    reason: `Used only to locate slot ends hidden under figures in the overhead. Curve residuals after the fit are reported in ${REPORT}.`,
    affects: ["fixture_paths.*.visible_slot_limits", "fixture_paths.*.centreline"],
    replace_with: "Overhead of the user's empty installed rink with scale markers.",
  });
}
const ownedTrace = (id: string): boolean => id.startsWith("trace.slot.");
const ownedLandmark = (id: string): boolean => id.startsWith("lm.slot.");
g.image_traces = g.image_traces.filter((t) => !ownedTrace(t.id));
g.landmarks = g.landmarks.filter((l) => !ownedLandmark(l.id));

for (const [pid, seed] of Object.entries(seeds.paths)) {
  const player = pid.replace("path.", "");
  const traceIds: string[] = [];
  for (const k of ["overhead", "bare"] as ImageKey[]) {
    const t = traces[pid]![k];
    const sid = seeds.images[k];
    const tid = `trace.slot.${player}.${k}`;
    traceIds.push(tid);
    const lmIds = [`lm.slot.${player}.${k}.start`, `lm.slot.${player}.${k}.end`];
    for (const end of ["start", "end"] as const) {
      const occluder = k === "overhead" ? seed.occluded[end] : seed.occluded_bare?.[end];
      const e = t[end];
      g.landmarks.push({
        id: `lm.slot.${player}.${k}.${end}`,
        source_image_id: sid,
        px: rp(e.point),
        uncertainty_px: occluder ? null : e.refined ? round(Math.max(2, t.widthMedian / 6), 1) : round(PARAMS[k].step, 1),
        description: occluder
          ? `Observed ${end} of the ${player} slot where it disappears under the ${occluder}; the real slot end lies further on.`
          : `Visible ${end} of the ${player} slot (centreline end of the rounded cut), found along the end tangent.`,
        visibility: occluder ? "partly_occluded" : "visible",
      } satisfies Landmark);
    }
    // Gaps (interpolated stretches) as inferred segments.
    const inferred: ImageTrace["inferred_segments"] = [];
    t.detected.forEach((ok, i) => {
      if (ok) return;
      const last = inferred[inferred.length - 1];
      if (last && last.to === i - 1) last.to = i;
      else inferred.push({ from: i, to: i, reason: "" });
    });
    for (const s of inferred) {
      const atEnd = s.from === 0 || s.to === t.detected.length - 1;
      s.reason = atEnd
        ? "End point taken from the last accepted cross-section (sub-pixel end not found)."
        : `Slot hidden or disturbed (${k === "overhead" ? [seed.occluded.middle, seed.occluded.start, seed.occluded.end].filter(Boolean).join("; ") || "figure, stick or print" : "printed features or low contrast"}); centre interpolated linearly between accepted cross-sections.`;
    }
    const e = fitErr[pid]![k];
    g.image_traces.push({
      id: tid,
      source_image_id: sid,
      feature: "slot_centreline",
      closed: false,
      points_px: t.centreline.map(rp),
      landmark_ids: lmIds,
      status: "traced",
      uncertainty_px: Math.ceil(2 * e.rms + 1),
      method: `scripts/trace-slots.ts: guided cross-sections every ${PARAMS[k].step} px from the data/slot-seeds.json seed; sub-pixel edge pair per section (mid-level crossing); ${PARAMS[k].passes} guide passes; centreline = centres smoothed over 5 sections; ends by sub-pixel crossing along the end tangent. Curve representation: polyline through the smoothed centres at ${PARAMS[k].step} px spacing.`,
      inferred_segments: inferred,
      stats: {
        length_px: round(polylineLength(t.centreline), 1),
        width_median_px: round(t.widthMedian, 2),
        fit_rms_px: round(e.rms, 3),
        fit_max_px: round(e.max, 2),
        detected_fraction: round(e.detectedFraction, 3),
        ...(k === "bare" ? { homography_curve_rms_px_in_overhead: round(residuals[pid]!.rms, 2), homography_curve_max_px_in_overhead: round(residuals[pid]!.max, 2) } : {}),
      },
      note: k === "overhead" ? "Visible slot centreline in the installed overhead (primary alignment)." : "Slot centreline in the bare loose sheet (older artwork; topology reference, not scale).",
    } satisfies ImageTrace);
  }

  // Fixture path: world centreline from the overhead trace, extended to bare-predicted ends where occluded.
  const o = traces[pid]!.overhead;
  let pts: Vec2[] = [...o.centreline];
  const usedBare: string[] = [];
  const endStatus: Record<"start" | "end", "traced" | "assumed"> = { start: "traced", end: "traced" };
  for (const c of endChecks.filter((x) => x.pid === pid && x.occluder)) {
    if (c.extension_px > 0) {
      if (c.end === "start") pts = [c.predicted, ...pts];
      else pts = [...pts, c.predicted];
      usedBare.push(c.end);
      endStatus[c.end] = "assumed";
    }
  }
  const lengthPx = polylineLength(pts);
  const world: WorldPolyline = {
    points_mm: pts.filter((_, i) => i % WORLD_EVERY === 0 || i === pts.length - 1).map(toWorld),
    closed: false,
    status: "assumed",
    source_ids: [seeds.images.overhead, "stiga_canada_catalog", ...(usedBare.length ? [seeds.images.bare] : [])],
    mapping_id: PREVIEW_MAP,
    uncertainty_mm: null,
    note: `Visible slot centreline mapped with the ASSUMED preview scale.${usedBare.length ? ` ${usedBare.join(" and ")} end extended under the occluding figure to the bare-sheet prediction (${BARE_ASSUMPTION}).` : ""} Not the fixture-axis path.`,
  };
  const fp = g.fixture_paths.find((f) => f.id === pid)!;
  const limit = (end: "start" | "end", value: number): Quantity =>
    endStatus[end] === "traced"
      ? q(round(value, 1), "px", "traced", [seeds.images.overhead], { note: `Arc length along the overhead slot centreline (image px, not mm). ${end} end visible.` })
      : q(round(value, 1), "px", "assumed", [seeds.images.overhead, seeds.images.bare], { assumption_id: BARE_ASSUMPTION, note: `Arc length along the overhead centreline (image px). ${end} end hidden by ${seed.occluded[end]}; position predicted from the bare sheet.` });
  const updated: FixturePath = {
    ...fp,
    centreline: world,
    fixture_axis_path: null,
    identity_evidence: { source_ids: [seeds.images.overhead], description: seed.identity },
    image_trace_ids: traceIds,
    visible_slot_limits: { start: limit("start", 0), end: limit("end", lengthPx) },
    note: [
      fp.control_rod.has_link ? "Manual shows link 7A (7111-9073-01) on the left-wing rod; its effect on figure motion is unknown." : undefined,
      "Visible slot centreline only: the fixture axis may be offset from it and the usable travel stops (usable_stops) are unknown until the rods are recorded. The figure's rotation is NOT assumed to follow the slot tangent, and rod displacement is NOT assumed equal to arc length along the slot.",
    ].filter(Boolean).join(" "),
  };
  Object.assign(fp, updated);
}
g.image_traces.sort((a, b) => a.id.localeCompare(b.id));
writeFileSync(GEOMETRY, JSON.stringify(g, null, 2) + "\n");

const report = {
  images: seeds.images,
  params: PARAMS,
  paths: Object.fromEntries(
    Object.entries(seeds.paths).map(([pid, seed]) => [
      pid,
      {
        iteration: seed.iteration,
        overhead: { length_px: round(polylineLength(traces[pid]!.overhead.centreline), 1), width_px: round(traces[pid]!.overhead.widthMedian, 2), ...Object.fromEntries(Object.entries(fitErr[pid]!.overhead).map(([k, v]) => [k, round(v, 3)])) },
        bare: { length_px: round(polylineLength(traces[pid]!.bare.centreline), 1), width_px: round(traces[pid]!.bare.widthMedian, 2), ...Object.fromEntries(Object.entries(fitErr[pid]!.bare).map(([k, v]) => [k, round(v, 3)])) },
        homography_curve_residual_px: { rms: round(residuals[pid]!.rms, 2), max: round(residuals[pid]!.max, 2), n: residuals[pid]!.n },
      },
    ]),
  ),
  homography_bare_to_overhead: { matrix: h.map((v) => Number(v.toPrecision(10))), initial_from_visible_ends: src.length, curve_rms_px: round(hRms, 3) },
  end_checks: endChecks.map((c) => ({ ...c, observed: rp(c.observed), predicted: rp(c.predicted), extension_px: round(c.extension_px, 1), lateral_px: round(c.lateral_px, 1) })),
  end_check_note: "extension_px > 0: the bare sheet places the slot end further on than the overhead shows (expected where a figure covers the end). For visible ends it measures the disagreement between the two photographs.",
};
writeFileSync(REPORT, JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report.end_checks.map((c) => [c.pid, c.end, c.occluder ? "occl" : "vis", c.extension_px, c.lateral_px])));
