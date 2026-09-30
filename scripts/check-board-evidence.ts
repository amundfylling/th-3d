// Evidence for the delegated iteration-05 review decisions (docs/decisions.md D2, D3):
//  1. Does the dark strip at the board base widen with distance from the image centre (a vertical
//     board face seen in perspective) or not (a flat shadow / trim on the ice)?
//  2. Do the printed marking lines bow like the board sides (lens barrel distortion) or stay straight
//     (the boards themselves bow)?
// Reads the pinned overhead and data/geometry.json; writes validation/05-evidence-check.json only.
import { readFileSync, writeFileSync } from "node:fs";
import type { GeometryFile } from "../src/model/geometry.ts";
import { loadPinnedJpeg, maxChannelAt, rgbAt } from "../src/model/raster.ts";

const OUTPUT = "validation/05-evidence-check.json";
const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const report = JSON.parse(readFileSync("validation/05-board-report.json", "utf8")) as {
  ice_region: { centre_px: [number, number] };
  side_bow_px: Record<string, { sagitta_px: number }>;
};
const trace = g.image_traces.find((t) => t.id === "trace.board_inner.overhead")!;
const img = g.source_images.find((s) => s.source_id === trace.source_image_id)!;
const raster = loadPinnedJpeg(img.local_path, img.sha256);
const imageCentre: [number, number] = [img.width_px / 2, img.height_px / 2];
const iceCentre = report.ice_region.centre_px;
const round = (v: number, d = 2): number => Math.round(v * 10 ** d) / 10 ** d;
const median = (a: number[]): number => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)]!;

// 1. Dark-strip width (max channel < 110) outward from each trace point, vs distance from image centre.
const widths: { r: number; w: number }[] = [];
for (const [u, v] of trace.points_px) {
  const d = [u - iceCentre[0], v - iceCentre[1]];
  const n = Math.hypot(d[0]!, d[1]!);
  const dir = [d[0]! / n, d[1]! / n];
  const dark = (t: number): boolean => maxChannelAt(raster, Math.round(u + t * dir[0]! - 0.5), Math.round(v + t * dir[1]! - 0.5)) < 110;
  let t0 = -1;
  for (let t = 0; t < 5; t += 0.5) if (dark(t)) { t0 = t; break; }
  if (t0 < 0) continue;
  let t1 = t0;
  while (t1 < 60 && dark(t1)) t1 += 0.5;
  widths.push({ r: Math.hypot(u - imageCentre[0], v - imageCentre[1]), w: t1 - t0 });
}
const mean = (a: number[]): number => a.reduce((s, x) => s + x, 0) / a.length;
const mr = mean(widths.map((x) => x.r)), mw = mean(widths.map((x) => x.w));
const cov = mean(widths.map((x) => (x.r - mr) * (x.w - mw)));
const corr = cov / Math.sqrt(mean(widths.map((x) => (x.r - mr) ** 2)) * mean(widths.map((x) => (x.w - mw) ** 2)));
const bins = [[1200, 1500], [1500, 2000], [2000, 2500]].map(([lo, hi]) => {
  const sel = widths.filter((x) => x.r >= lo! && x.r < hi!);
  return { radius_px: `${lo}-${hi}`, n: sel.length, median_width_px: round(median(sel.map((x) => x.w)), 1), median_width_per_1000px_radius: round((1000 * median(sel.map((x) => x.w))) / median(sel.map((x) => x.r)), 2) };
});

// 2. Straightness of printed marking lines between their top and bottom landmarks.
const isRed = ([r, gg, b]: [number, number, number]): boolean => r > 150 && r - gg > 70 && r - b > 70;
const isBlue = ([r, gg, b]: [number, number, number]): boolean => b > 110 && b - r > 50 && b - gg > 15;
const lm = (id: string): [number, number] => g.landmarks.find((l) => l.id === id)!.px;
const topBow = Math.abs(report.side_bow_px.top!.sagitta_px);
const topHalfSpan = 1700; // half-length of the top straight section in px (report fits_px / inspection)
const topOffset = Math.abs(lm("lm.board.centre_line.top")[1] - imageCentre[1]);
const k = topBow / (topHalfSpan ** 2 * topOffset); // radial model r_d = r (1 - k r^2), fitted to the top side only
const lines = (["goal_line.W", "blue_line.W", "centre_line", "blue_line.E", "goal_line.E"] as const).map((name) => {
  const colour = name.startsWith("blue") ? isBlue : isRed;
  const t = lm(`lm.board.${name}.top`), b = lm(`lm.board.${name}.bottom`);
  const ys: number[] = [], xs: number[] = [];
  for (let y = Math.ceil(t[1]) + 30; y < b[1] - 30; y += 10) {
    const x0 = t[0] + ((b[0] - t[0]) * (y - t[1])) / (b[1] - t[1]);
    const hits: number[] = [];
    for (let x = Math.floor(x0) - 40; x < Math.floor(x0) + 40; x++) if (colour(rgbAt(raster, x, y))) hits.push(x);
    if (hits.length >= 8 && hits.length <= 45 && hits[hits.length - 1]! - hits[0]! < 50) {
      ys.push(y);
      xs.push(mean(hits) + 0.5);
    }
  }
  // Quadratic x(y) by least squares (centred), sagitta = middle minus chord.
  const yc = mean(ys);
  const Y = ys.map((y) => (y - yc) / 1000);
  const S = (f: (y: number, x: number) => number): number => Y.reduce((s, y, i) => s + f(y, xs[i]!), 0);
  const m = [S((y) => y ** 4), S((y) => y ** 3), S((y) => y ** 2), S((y) => y ** 3), S((y) => y ** 2), S((y) => y), S((y) => y ** 2), S((y) => y), Y.length];
  const rhs = [S((y, x) => y * y * x), S((y, x) => y * x), S((_, x) => x)];
  const det3 = (q: number[]): number => q[0]! * (q[4]! * q[8]! - q[5]! * q[7]!) - q[1]! * (q[3]! * q[8]! - q[5]! * q[6]!) + q[2]! * (q[3]! * q[7]! - q[4]! * q[6]!);
  const D = det3(m);
  const [qa, qb, qc] = [0, 1, 2].map((i) => det3(m.map((v, j) => (j % 3 === i ? rhs[Math.floor(j / 3)]! : v))) / D) as [number, number, number];
  const q = (y: number): number => qa * y * y + qb * y + qc;
  const y0 = Math.min(...Y), y1 = Math.max(...Y), ym = (y0 + y1) / 2;
  const sagitta = q(ym) - (q(y0) + q(y1)) / 2;
  const x0 = mean(xs) - imageCentre[0];
  const half = ((y1 - y0) * 1000) / 2;
  const rms = Math.sqrt(mean(xs.map((x, i) => (x - q(Y[i]!)) ** 2)));
  return { line: name, mean_x_offset_from_image_centre_px: round(x0, 0), samples: ys.length, measured_sagitta_px: round(sagitta), quadratic_rms_px: round(rms), barrel_predicted_sagitta_px: round(k * half * half * x0) };
});

const goalRatios = lines.filter((l) => l.line.startsWith("goal")).map((l) => round(l.measured_sagitta_px / l.barrel_predicted_sagitta_px));
const result = {
  iteration: "05 (delegated review evidence)",
  source_image_id: img.source_id,
  dark_strip_vs_radius: {
    samples: widths.length,
    correlation_width_vs_radius: round(corr, 3),
    bins,
    reading: corr > 0.3 && Math.abs(bins[2]!.median_width_per_1000px_radius - bins[0]!.median_width_per_1000px_radius) < 0.25 * bins[0]!.median_width_per_1000px_radius
      ? "Width grows in proportion to distance from the image centre (constant width per 1000 px radius), as a vertical board face does under a central camera. A flat shadow or trim on the ice would not scale this way. So the strip is the lower board face and its ice-side edge is the board base."
      : "Width does not scale with radius as a vertical face would; the strip may be a shadow or flat trim and the contact line could lie on its outer side.",
  },
  marking_straightness: {
    radial_model: "r_d = r (1 - k r^2) about the image centre, k fitted so the model reproduces the top board sagitta alone",
    k_per_px2: k,
    lines,
    sign: "Sagitta = middle minus chord along x; negative = middle toward -x.",
    goal_line_measured_over_predicted: goalRatios,
    reading:
      goalRatios.every((r) => r > 0.8)
        ? "Marking lines bow as much as the lens model predicts: the board-side bow is explained by lens distortion."
        : goalRatios.every((r) => r > 0 && r < 0.8)
          ? "Marking lines bow with the lens-model sign but clearly less than predicted: lens distortion explains only part of the board-side bow; the rest is attributed to the boards themselves (not separable without a calibrated photo)."
          : "Marking lines do not bow consistently with the lens model: the board-side bow is attributed to the boards themselves (not separable without a calibrated photo).",
  },
};
writeFileSync(OUTPUT, JSON.stringify(result, null, 2) + "\n");
console.log(JSON.stringify(result, null, 1));
