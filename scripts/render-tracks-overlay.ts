// Renders a slot-trace review overlay from the canonical data:
//   node scripts/render-tracks-overlay.ts <output.svg> <title> <player,player,...> [--samples]
// Both photographs are embedded unchanged and drawn at a uniform scale (no stretching).
import { readFileSync, writeFileSync } from "node:fs";
import type { GeometryFile, ImageTrace } from "../src/model/geometry.ts";

const [out, title, playerList, ...flags] = process.argv.slice(2);
if (!out || !title || !playerList) throw new Error("usage: render-tracks-overlay.ts <out.svg> <title> <players> [--samples]");
const players = playerList.split(",");
const withSamples = flags.includes("--samples");
const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const report = JSON.parse(readFileSync("validation/slots-report.json", "utf8")) as {
  homography_bare_to_overhead: { curve_rms_px: number };
  end_checks: { pid: string; end: string; observed: [number, number]; predicted: [number, number]; extension_px: number; lateral_px: number; occluder: string | null }[];
};

const COLOURS = ["#e6194b", "#f58231", "#911eb4", "#3cb44b", "#4363d8", "#008080", "#9a6324", "#f032e6", "#000075", "#808000", "#000000", "#800000"];
const colour = (i: number): string => COLOURS[i % COLOURS.length]!;
const esc = (s: string): string => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const f1 = (v: number): string => v.toFixed(1);
const img = (id: string) => g.source_images.find((s) => s.source_id === id)!;
const overhead = img("stiga_se_fi_overhead");
const bare = img("stiga_ca_bare_ice_sheet");
const b64 = (path: string): string => readFileSync(path).toString("base64");
const trace = (player: string, k: "overhead" | "bare"): ImageTrace => g.image_traces.find((t) => t.id === `trace.slot.${player}.${k}`)!;
const lm = (id: string) => g.landmarks.find((l) => l.id === id);
const team = (p: string) => g.teams.find((t) => t.id === p.split("-")[0])!;

/** Trace drawing in image-pixel units; stroke widths are screen pixels (non-scaling). */
function traceLayer(k: "overhead" | "bare", dash: number): string {
  return players
    .map((p, i) => {
      const t = trace(p, k);
      const c = colour(i);
      const inferred = new Set<number>();
      for (const s of t.inferred_segments) for (let j = s.from; j <= s.to; j++) inferred.add(j);
      const segs: string[] = [];
      let run: number[] = [];
      let runInf = inferred.has(0);
      const flush = (): void => {
        if (run.length > 1)
          segs.push(`<polyline points="${run.map((j) => `${f1(t.points_px[j]![0])},${f1(t.points_px[j]![1])}`).join(" ")}" fill="none" stroke="${c}" stroke-width="${runInf ? 2.5 : 2}" vector-effect="non-scaling-stroke"${runInf ? ` stroke-dasharray="${dash} ${dash}"` : ""}/>`);
      };
      t.points_px.forEach((_, j) => {
        const inf = inferred.has(j);
        if (inf !== runInf) {
          run.push(j);
          flush();
          run = [j];
          runInf = inf;
        } else run.push(j);
      });
      flush();
      const ends = ["start", "end"].map((e) => lm(`lm.slot.${p}.${k}.${e}`)!).map((l) => {
        const [u, v] = l.px;
        return l.visibility === "visible"
          ? `<circle cx="${f1(u)}" cy="${f1(v)}" r="${dash * 0.9}" fill="${c}" stroke="#fff" stroke-width="1.5" vector-effect="non-scaling-stroke"/>`
          : `<circle cx="${f1(u)}" cy="${f1(v)}" r="${dash * 1.3}" fill="none" stroke="${c}" stroke-width="2.5" vector-effect="non-scaling-stroke"/>`;
      });
      const preds =
        k === "overhead"
          ? report.end_checks
              .filter((e) => e.pid === `path.${p}` && e.occluder)
              .map((e) => {
                const [u, v] = e.predicted;
                const s = dash * 1.2;
                return `<line x1="${f1(e.observed[0])}" y1="${f1(e.observed[1])}" x2="${f1(u)}" y2="${f1(v)}" stroke="${c}" stroke-width="2" stroke-dasharray="${dash / 2} ${dash / 2}" vector-effect="non-scaling-stroke"/>` +
                  `<path d="M${f1(u - s)},${f1(v - s)} L${f1(u + s)},${f1(v + s)} M${f1(u - s)},${f1(v + s)} L${f1(u + s)},${f1(v - s)}" stroke="${c}" stroke-width="2.5" vector-effect="non-scaling-stroke"/>`;
              })
          : [];
      const samples =
        withSamples && k === "overhead"
          ? t.points_px
              .filter((_, j) => j % 25 === 0)
              .map((q, j) => `<rect x="${f1(q[0] - dash / 2)}" y="${f1(q[1] - dash / 2)}" width="${dash}" height="${dash}" fill="#fff" stroke="${c}" stroke-width="1.5" vector-effect="non-scaling-stroke"/><text x="${f1(q[0] + dash)}" y="${f1(q[1] - dash)}" font-size="${dash * 1.6}" fill="${c}">${j * 25}</text>`)
          : [];
      return [...segs, ...ends, ...preds, ...samples].join("\n");
    })
    .join("\n");
}

function labels(k: "overhead" | "bare", size: number): string {
  return players
    .map((p, i) => {
      const t = trace(p, k);
      const q = t.points_px[Math.floor(t.points_px.length / 2)]!;
      const tm = team(p);
      return `<text x="${f1(q[0])}" y="${f1(q[1] - size * 0.8)}" font-size="${size}" font-weight="bold" text-anchor="middle" fill="${colour(i)}" stroke="#fff" stroke-width="${size / 5}" paint-order="stroke">${esc(p)} (team ${tm.label} ${tm.reference_variant?.team ?? ""})</text>`;
    })
    .join("\n");
}

// Layout: overhead rink region at 1:1, bare sheet at 2x, then end insets, then notes.
const W = 5100;
const oView = { x: 300, y: 1300, w: 5100, h: 3000 };
const bScale = 2;
const bTop = oView.h + 160;
const bH = bare.height_px * bScale;
const insetTop = bTop + bH + 160;
const COLS = 6;
const CELL = Math.floor(W / COLS);
const insetDefs = players.flatMap((p) =>
  ["start", "end"].map((e) => ({ p, e, l: lm(`lm.slot.${p}.overhead.${e}`)! })),
);
const insetRows = Math.ceil(insetDefs.length / COLS);
const notesTop = insetTop + insetRows * (CELL + 70) + 60;

const insets = insetDefs
  .map(({ p, e, l }, i) => {
    const cx = (i % COLS) * CELL + 15;
    const cy = insetTop + Math.floor(i / COLS) * (CELL + 70);
    const size = CELL - 30;
    const R = 180;
    const [u, v] = l.px;
    return `<text x="${cx}" y="${cy + 36}" font-size="30" fill="#222">${esc(p)} ${e}: ${l.visibility === "visible" ? "visible" : "hidden under figure"} (${f1(u)}, ${f1(v)})</text>
<svg x="${cx}" y="${cy + 50}" width="${size}" height="${size}" viewBox="${u - R} ${v - R} ${2 * R} ${2 * R}"><use href="#overhead"/>${traceLayer("overhead", 5)}</svg>
<rect x="${cx}" y="${cy + 50}" width="${size}" height="${size}" fill="none" stroke="#444" stroke-width="3"/>`;
  })
  .join("\n");

const rows = players.map((p, i) => {
  const o = trace(p, "overhead"), b = trace(p, "bare");
  const fp = g.fixture_paths.find((f) => f.id === `path.${p}`)!;
  const ends = report.end_checks.filter((e) => e.pid === `path.${p}`).map((e) => `${e.end} ${e.occluder ? "hidden" : "visible"}: bare-predicted ${e.extension_px >= 0 ? "+" : ""}${e.extension_px} px along, ${e.lateral_px} px across`).join("; ");
  return [
    `${p} [${colour(i)}] team ${team(p).label} (${team(p).reference_variant?.team}), rod ${fp.control_rod.part_number}${fp.control_rod.has_link ? " + link 7A" : ""}. Evidence: ${fp.identity_evidence?.description ?? ""}`,
    `   overhead: length ${o.stats!.length_px} px, width ${o.stats!.width_median_px} px, fit RMS ${o.stats!.fit_rms_px} px (max ${o.stats!.fit_max_px}), detected ${Math.round(o.stats!.detected_fraction! * 100)}%. bare: length ${b.stats!.length_px} px, width ${b.stats!.width_median_px} px, homography residual RMS ${b.stats!.homography_curve_rms_px_in_overhead} px (max ${b.stats!.homography_curve_max_px_in_overhead}). ${ends}`,
  ];
});
const notes = [
  `${title} - PROVISIONAL. Geometry ${g.geometry_version}. AI review only; no personal user approval is claimed.`,
  `Top: ${overhead.source_id} (unchanged, 1:1, view x ${oView.x}..${oView.x + oView.w}, y ${oView.y}..${oView.y + oView.h}). Middle: ${bare.source_id} (unchanged, older artwork, uniform ${bScale}x). Insets: overhead at each slot end.`,
  `Solid line: detected visible slot centreline. Dashed: interpolated where hidden (figure, puck, print). Filled dot: visible slot end. Open circle: observed end where a figure hides the slot. X + dashed: end predicted from the bare sheet (assume.bare_sheet_same_slot_layout).`,
  `Bare->overhead homography fitted to all traced curves: RMS ${report.homography_bare_to_overhead.curve_rms_px} px. Visible slot centreline only: the fixture-axis path and usable travel stops are UNKNOWN (need rod recordings); no mm claimed.`,
  ...rows.flat(),
];
const wrap = (t: string, width = 200): string[] => {
  const out: string[] = [];
  let line = "";
  for (const w of t.split(" ")) {
    if (line && line.length + w.length + 1 > width) { out.push(line); line = "      " + w; } else line = line ? `${line} ${w}` : w;
  }
  return [...out, line];
};
const noteLines = notes.flatMap((n) => wrap(n));
const totalH = notesTop + noteLines.length * 44 + 80;

const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${totalH}" width="${W / 4}" height="${Math.round(totalH / 4)}" font-family="DejaVu Sans, Arial, sans-serif">
<title>${esc(title)}</title>
<defs>
<image id="overhead" x="0" y="0" width="${overhead.width_px}" height="${overhead.height_px}" href="data:image/jpeg;base64,${b64(overhead.local_path)}"/>
<image id="bare" x="0" y="0" width="${bare.width_px}" height="${bare.height_px}" href="data:image/jpeg;base64,${b64(bare.local_path)}"/>
</defs>
<rect width="${W}" height="${totalH}" fill="#fff"/>
<svg x="0" y="0" width="${oView.w}" height="${oView.h}" viewBox="${oView.x} ${oView.y} ${oView.w} ${oView.h}"><use href="#overhead"/>${traceLayer("overhead", 8)}${labels("overhead", 44)}</svg>
<text x="20" y="${oView.h + 60}" font-size="48" fill="#111">${esc(title)} - installed overhead (above) and bare sheet (below)</text>
<svg x="0" y="${bTop}" width="${bare.width_px * bScale}" height="${bH}" viewBox="0 0 ${bare.width_px} ${bare.height_px}"><use href="#bare"/>${traceLayer("bare", 4)}${labels("bare", 22)}</svg>
${insets}
${noteLines.map((t, i) => `<text x="20" y="${notesTop + i * 44}" font-size="32" fill="#111">${esc(t)}</text>`).join("\n")}
</svg>
`;
writeFileSync(out, svg);
console.log(`wrote ${out} (${(svg.length / 1e6).toFixed(2)} MB, ${Math.round(totalH / 4)} px tall at 1/4)`);
