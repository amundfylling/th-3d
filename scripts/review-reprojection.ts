// Iteration 20: end-to-end geometric reprojection check. Projects the canonical geometry (world mm) into the
// Remotion orthographic overhead still (validation/19/19-overhead.png) with the camera definition of
// remotion/cameras.ts, and measures how well it lands on the rendered features. Tests the pipeline
// (data -> Blender -> GLB -> Remotion) only; absolute physical accuracy is NOT tested (no calibration).
import { readFileSync, writeFileSync } from "node:fs";
import { PNG } from "./png-read.ts";
import { CAMERAS } from "../remotion/cameras.ts";
import type { GeometryFile } from "../src/model/geometry.ts";

const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const img = PNG.read("validation/19/19-overhead.png");
const cam = CAMERAS.overhead;
const mmPerPx = cam.fovDegOrWidthMm / img.width;
const toPx = (x: number, y: number): [number, number] => [img.width / 2 + (x - cam.positionMm[0]) / mmPerPx, img.height / 2 - (y - cam.positionMm[1]) / mmPerPx];
const lum = (u: number, v: number): number => {
  const i = (Math.round(v) * img.width + Math.round(u)) * 4;
  return (img.data[i]! + img.data[i + 1]! + img.data[i + 2]!) / 3;
};
const round = (v: number, d = 3): number => Math.round(v * 10 ** d) / 10 ** d;

// 1. Slot centrelines: sample every centreline point; find the dark slot's centre across the local normal.
const slotStats: Record<string, { n: number; onDark: number; meanOffsetPx: number; maxOffsetPx: number }> = {};
for (const f of g.fixture_paths) {
  const P = f.centreline!.points_mm;
  const offs: number[] = [];
  let onDark = 0, n = 0;
  for (let i = 2; i < P.length - 2; i++) {
    const [u, v] = toPx(P[i]![0], P[i]![1]);
    const [u1, v1] = toPx(P[i + 1]![0], P[i + 1]![1]);
    const [u0, v0] = toPx(P[i - 1]![0], P[i - 1]![1]);
    const tx = u1 - u0, ty = v1 - v0, tl = Math.hypot(tx, ty);
    const nx = -ty / tl, ny = tx / tl;
    n++;
    if (lum(u, v) < 90) onDark++;
    const dark: number[] = [];
    for (let k = -12; k <= 12; k += 0.5) if (lum(u + k * nx, v + k * ny) < 90) dark.push(k);
    if (dark.length >= 4 && dark[dark.length - 1]! - dark[0]! < 20) offs.push((dark[0]! + dark[dark.length - 1]!) / 2);
  }
  slotStats[f.player_id] = { n, onDark: round(onDark / n), meanOffsetPx: round(offs.reduce((s, x) => s + Math.abs(x), 0) / offs.length), maxOffsetPx: round(Math.max(...offs.map(Math.abs))) };
}
// 2. Ice edge: along the canonical boundary, the transition from ice (bright) to board must be within a few px.
const B = g.board.inner_boundary.world!.points_mm;
const edgeOffsets: number[] = [];
for (let i = 0; i < B.length; i += 6) {
  const [x, y] = B[i]!;
  const r = Math.hypot(x, y);
  const [u, v] = toPx(x, y);
  const [ui, vi] = toPx(x * (1 - 30 / r), y * (1 - 30 / r));
  const dx = (u - ui) / Math.hypot(u - ui, v - vi), dy = (v - vi) / Math.hypot(u - ui, v - vi);
  let prev = lum(u - 12 * dx, v - 12 * dy), found: number | null = null;
  for (let k = -12; k <= 12; k += 0.25) {
    const l = lum(u + k * dx, v + k * dy);
    if (Math.abs(l - prev) > 25 && found === null) found = k;
    prev = l;
  }
  if (found !== null) edgeOffsets.push(found);
}
const med = (a: number[]): number => [...a].sort((p, q) => p - q)[Math.floor(a.length / 2)]!;
const report = {
  image: "validation/19/19-overhead.png",
  output_mm_per_px: round(mmPerPx, 4),
  slots: slotStats,
  slot_summary: { min_on_dark: Math.min(...Object.values(slotStats).map((s) => s.onDark)), worst_mean_offset_px: Math.max(...Object.values(slotStats).map((s) => s.meanOffsetPx)) },
  ice_edge: { samples: edgeOffsets.length, median_abs_offset_px: round(med(edgeOffsets.map(Math.abs))), p90_abs_offset_px: round([...edgeOffsets.map(Math.abs)].sort((p, q) => p - q)[Math.floor(edgeOffsets.length * 0.9)]!) },
  scope: "Pipeline reprojection only (canonical data -> Blender -> GLB -> Remotion). Physical accuracy is limited by the ASSUMED preview scale and the 21 px (~3.8 mm) trace uncertainty; it is not measured.",
};
writeFileSync("validation/20-reprojection.json", JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify({ ...report, slots: undefined }, null, 1));
