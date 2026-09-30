// Renders validation/05-board-overlay.svg from the canonical data: the unchanged overhead photograph
// (embedded byte-for-byte), the traced inner board boundary, landmarks and review notes.
// The photograph is never resampled or stretched: it is placed at its native pixel size.
import { readFileSync, writeFileSync } from "node:fs";
import type { GeometryFile } from "../src/model/geometry.ts";

const GEOMETRY = "data/geometry.json";
const REPORT = "validation/05-board-report.json";
const OUTPUT = "validation/05-board-overlay.svg";
const TRACE_ID = "trace.board_inner.overhead";
const MAP_ID = "map.overhead.preview";

const g = JSON.parse(readFileSync(GEOMETRY, "utf8")) as GeometryFile;
const report = JSON.parse(readFileSync(REPORT, "utf8")) as Record<string, any>;
const trace = g.image_traces.find((t) => t.id === TRACE_ID);
if (!trace) throw new Error(`${TRACE_ID} not found; run scripts/trace-board.ts first`);
const img = g.source_images.find((s) => s.source_id === trace.source_image_id)!;
const mapping = g.image_to_world.find((m) => m.id === MAP_ID);
const landmarks = g.landmarks.filter((l) => trace.landmark_ids.includes(l.id));
const photo = readFileSync(img.local_path).toString("base64");

const W = img.width_px;
const H = img.height_px;
const esc = (s: string): string => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const f1 = (v: number): string => v.toFixed(1);

const filled = new Set<number>();
for (const s of trace.inferred_segments) for (let i = s.from; i <= s.to; i++) filled.add(i);
const pts = trace.points_px;
const polyline = (idx: number[]): string => idx.map((i) => `${f1(pts[i]![0])},${f1(pts[i]![1])}`).join(" ");
// Detected runs as solid lines, filled runs (plus their neighbours) as dashed lines.
const runs: { filled: boolean; idx: number[] }[] = [];
for (let i = 0; i <= pts.length; i++) {
  const k = i % pts.length;
  const isFilled = filled.has(k);
  const last = runs[runs.length - 1];
  if (last && last.filled === isFilled) last.idx.push(k);
  else {
    if (last) last.idx.push(k);
    runs.push({ filled: isFilled, idx: last ? [last.idx[last.idx.length - 2]!, k] : [k] });
  }
}

function traceLayer(dashScale: number): string {
  // Strokes are in screen pixels (non-scaling) so the line stays visible and thin at any zoom.
  const parts: string[] = [];
  for (const r of runs) {
    parts.push(
      r.filled
        ? `<polyline points="${polyline(r.idx)}" fill="none" stroke="#ff8c00" stroke-width="3" vector-effect="non-scaling-stroke" stroke-dasharray="${12 * dashScale} ${8 * dashScale}"/>`
        : `<polyline points="${polyline(r.idx)}" fill="none" stroke="#e6007e" stroke-width="2" vector-effect="non-scaling-stroke"/>`,
    );
  }
  return parts.join("\n");
}

function landmarkLayer(scale: number, withLabels: boolean): string {
  return landmarks
    .map((l) => {
      const [u, v] = l.px;
      const below = v > H / 2;
      const ty = below ? v + 60 * scale : v - 70 * scale;
      const label = withLabels
        ? `<text x="${f1(u)}" y="${f1(ty)}" font-size="${26 * scale}" text-anchor="middle" fill="#003f8a" stroke="#fff" stroke-width="${5 * scale}" paint-order="stroke">${esc(l.id.replace("lm.board.", ""))}</text>` +
          `<text x="${f1(u)}" y="${f1(ty + 30 * scale)}" font-size="${24 * scale}" text-anchor="middle" fill="#003f8a" stroke="#fff" stroke-width="${5 * scale}" paint-order="stroke">(${f1(u)}, ${f1(v)}) px</text>`
        : "";
      return `<circle cx="${f1(u)}" cy="${f1(v)}" r="${7 * scale}" fill="none" stroke="#003f8a" stroke-width="${2.5 * scale}"/>` +
        `<line x1="${f1(u)}" y1="${f1(v - 14 * scale)}" x2="${f1(u)}" y2="${f1(v + 14 * scale)}" stroke="#003f8a" stroke-width="${1.5 * scale}"/>${label}`;
    })
    .join("\n");
}

// Inset regions: the four corners plus two places where the edge was filled.
const bbox = report.ice_region.bbox_px as [number, number, number, number];
const R = 800;
const insets: { title: string; x: number; y: number; w: number; h: number }[] = [
  { title: "Top-left corner", x: bbox[0] - 120, y: bbox[1] - 120, w: R, h: R },
  { title: "Top-right corner", x: bbox[2] - R + 120, y: bbox[1] - 120, w: R, h: R },
  { title: "Bottom-left corner", x: bbox[0] - 120, y: bbox[3] - R + 120, w: R, h: R },
  { title: "Bottom-right corner", x: bbox[2] - R + 120, y: bbox[3] - R + 120, w: R, h: R },
  { title: "Top board at centre line (landmark)", x: 2806 - 200, y: bbox[1] - 150, w: 400, h: 400 },
  { title: "Right end beside figure 26 (edge detected in its shadow)", x: bbox[2] - 300, y: 2700, w: 400, h: 400 },
  { title: "Left end, mid-length", x: bbox[0] - 200, y: 2600, w: 400, h: 400 },
  { title: "Top board at W blue line (interpolated gap, dashed)", x: 2267 - 200, y: bbox[1] - 150, w: 400, h: 400 },
  { title: "Bottom board near W corner", x: 1060 - 200, y: bbox[3] - 250, w: 400, h: 400 },
];
const COLS = 3;
const CELL = Math.floor(W / COLS);
const PAD = 40;
const insetTop = H + 80;
const insetRows = Math.ceil(insets.length / COLS);
const notesTop = insetTop + insetRows * (CELL + 60) + 40;

const insetSvg = insets
  .map((r, i) => {
    const cx = (i % COLS) * CELL + PAD / 2;
    const cy = insetTop + Math.floor(i / COLS) * (CELL + 60);
    const size = CELL - PAD;
    const scale = r.w / size; // image units per output unit inside the inset
    return `<g>
<text x="${cx}" y="${cy + 40}" font-size="36" fill="#222">${esc(r.title)} - source px x ${r.x}..${r.x + r.w}, y ${r.y}..${r.y + r.h} (uniform ${f1(size / r.w)}x)</text>
<svg x="${cx}" y="${cy + 55}" width="${size}" height="${size}" viewBox="${r.x} ${r.y} ${r.w} ${r.h}" preserveAspectRatio="xMidYMid meet">
<use href="#photo"/>
${traceLayer(scale)}
${landmarkLayer(scale, false)}
</svg>
<rect x="${cx}" y="${cy + 55}" width="${size}" height="${size}" fill="none" stroke="#444" stroke-width="3"/>
</g>`;
  })
  .join("\n");

const e = report.error_estimate_px;
const pc = report.projection_checks;
const pm = report.preview_mapping_assumed;
const notes = [
  `Iteration 05 - PROVISIONAL inner board boundary (ice-contact edge). Geometry version ${g.geometry_version}. AI review under the user's delegation accepted it (docs/decisions.md D1-D3); no personal user approval is claimed.`,
  `Source: ${img.source_id} = ${img.local_path}, ${W} x ${H} px, SHA-256 ${img.sha256}. Embedded unchanged; drawn at native size (1 unit = 1 source pixel, u right, v down).`,
  `Magenta solid: detected edge (${report.samples.detected_and_consistent}/${report.samples.total} rays). Orange dashed: interpolated between neighbouring detected points where the edge is disturbed (${trace.inferred_segments.length} segments; assumption assume.board_occlusion_fill).`,
  `Blue circles: landmarks where markings meet the long boards; labels give ID and source-pixel coordinates.`,
  `The line is the ice-side edge of the near-black strip at the board base (assume.board_edge_is_ice_contact; strip median ${report.dark_strip_width_px.median} px). NOT the board top rail, NOT the outer housing, NOT the loose sheet perimeter (hidden under the boards).`,
  `Error estimate: trace uncertainty ${e.trace_uncertainty_px} px (${e.rule}). Straight-side fit RMS worst ${e.edge_localisation_rms_worst_straight} px; corner radii ${Object.values(report.corner_radius_px).join(" / ")} px.`,
  `Projection: opposite sides parallel within ${pc.top_vs_bottom_angle_deg} deg (top/bottom) and ${pc.left_vs_right_angle_deg} deg (left/right); width ${pc.width_px_at_left_mid_right.join(" / ")} px at left/mid/right; outward bow up to ${Math.max(...Object.values(report.side_bow_px as Record<string, { sagitta_px: number }>).map((b) => Math.abs(b.sagitta_px)))} px (lens distortion or real board bow). Similarity-mapping bound ${e.similarity_mapping_bound_px} px.`,
  `Markings: centre line ${report.marking_checks_px.centre_line_offset_from_boundary_centre_px} px from the traced boundary centre along the long axis; every marking line leans ${Object.entries(report.marking_checks_px).filter(([k]) => k.endsWith("top_minus_bottom_along_axis_px")).map(([, v]) => v).join(" / ")} px (top minus bottom, along the long axis) relative to the board normal: the printed sheet may sit slightly rotated in the boards.`,
  mapping
    ? `PREVIEW SCALE (ASSUMED, not calibrated): ${pm.mm_per_px} mm/px uniform from catalog length approx. 845 mm = traced length ${report.extents_px.length} px. Implied width ${pm.implied_width_mm} mm vs catalog approx. ${pm.catalog_width_mm} mm (discrepancy ${pm.width_discrepancy_mm} mm; aspect ${report.extents_px.aspect} vs ${report.extents_px.catalog_aspect_845_457}). No millimetre accuracy is claimed.`
    : "No preview scale.",
  `No plane rectification applied. Elevated objects (board tops, screens, figures, goals) are not mapped. Numbers: ${REPORT}.`,
];
const wrap = (t: string, width = 170): string[] => {
  const lines: string[] = [];
  let line = "";
  for (const word of t.split(" ")) {
    if (line && line.length + word.length + 1 > width) {
      lines.push(line);
      line = "   " + word;
    } else line = line ? `${line} ${word}` : word;
  }
  return [...lines, line];
};
const noteLines = notes.flatMap((t) => wrap(t));
const notesSvg = noteLines
  .map((t, i) => `<text x="40" y="${notesTop + 60 + i * 58}" font-size="40" fill="#111">${esc(t)}</text>`)
  .join("\n");
const totalH = notesTop + 60 + noteLines.length * 58 + 60;

const svg = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 ${W} ${totalH}" width="${W / 4}" height="${Math.round(totalH / 4)}" font-family="DejaVu Sans, Arial, sans-serif">
<title>05 board overlay (provisional) - ${esc(img.source_id)}</title>
<defs><image id="photo" x="0" y="0" width="${W}" height="${H}" href="data:image/jpeg;base64,${photo}"/></defs>
<rect x="0" y="0" width="${W}" height="${totalH}" fill="#ffffff"/>
<use href="#photo"/>
<rect x="0" y="0" width="${W}" height="${H}" fill="none" stroke="#999" stroke-width="4"/>
${traceLayer(1.6)}
${landmarkLayer(1.6, true)}
${insets.map((r) => `<rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" fill="none" stroke="#444" stroke-width="3" stroke-dasharray="12 8"/>`).join("\n")}
<text x="40" y="80" font-size="56" fill="#111">05 - Provisional inner board boundary on ${esc(img.source_id)} (unchanged, native ${W} x ${H} px)</text>
${insetSvg}
${notesSvg}
</svg>
`;
writeFileSync(OUTPUT, svg);
console.log(`wrote ${OUTPUT} (${(svg.length / 1e6).toFixed(2)} MB)`);
