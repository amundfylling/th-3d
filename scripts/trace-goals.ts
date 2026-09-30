// Iteration 08: goal regions. Traces the ice-sheet cut-out behind each goal line in the bare sheet,
// maps it into the overhead with the slot homography, traces the (elevated) cage outline and post tops
// in the overhead, and measures the behind-goal space. Photographs are only read.
import { readFileSync, writeFileSync } from "node:fs";
import type { Vec2 } from "../src/model/fit.ts";
import type { GeometryFile, ImageTrace, Landmark, PixelPoint } from "../src/model/geometry.ts";
import { applyH, type H } from "../src/model/homography.ts";
import { bilinear, loadPinnedJpeg, type Raster } from "../src/model/raster.ts";
import { simplifyClosed } from "../src/model/slot-trace.ts";

// ---- Operator parameters (from gridded zooms, docs/tracks.md) -----------------------------------
const GOALS = {
  W: {
    cutoutSeedBare: [380, 820] as Vec2,
    cageBox: [880, 2470, 1212, 3110] as const, // overhead px; x limited to the goal-line side of the cage
    postSeeds: { pos_y: [1203, 2522] as Vec2, neg_y: [1203, 3052] as Vec2 },
  },
  E: {
    cutoutSeedBare: [2150, 820] as Vec2,
    cageBox: [4425, 2470, 4800, 3110] as const,
    postSeeds: { pos_y: [4478, 2530] as Vec2, neg_y: [4478, 3062] as Vec2 },
  },
};
const WHITE_MIN = 235; // bare-sheet cut-out: min(R,G,B) >= this
const POST_DARK_MAX = 80; // overhead post-top knob: max(R,G,B) < this
// --------------------------------------------------------------------------------------------------

const round = (v: number, d = 2): number => Math.round(v * 10 ** d) / 10 ** d;
const rp = (p: Vec2): PixelPoint => [round(p[0]), round(p[1])];
const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const slotsReport = JSON.parse(readFileSync("validation/slots-report.json", "utf8")) as { homography_bare_to_overhead: { matrix: H; curve_rms_px: number } };
const H_BO = slotsReport.homography_bare_to_overhead.matrix;
const img = (id: string) => g.source_images.find((s) => s.source_id === id)!;
const OVER = "stiga_se_fi_overhead", BARE = "stiga_ca_bare_ice_sheet";
const over = loadPinnedJpeg(img(OVER).local_path, img(OVER).sha256);
const bare = loadPinnedJpeg(img(BARE).local_path, img(BARE).sha256);
const px = (r: Raster, x: number, y: number): [number, number, number] => {
  const i = (y * r.width + x) * 4;
  return [r.data[i]!, r.data[i + 1]!, r.data[i + 2]!];
};

/** Region grown from a seed over pixels passing `ok`, limited to a box; returns mask and bbox. */
function grow(r: Raster, seed: Vec2, ok: (c: [number, number, number]) => boolean, limit: number): Set<number> {
  const seen = new Set<number>();
  const q = [Math.round(seed[1]) * r.width + Math.round(seed[0])];
  seen.add(q[0]!);
  while (q.length) {
    const p = q.pop()!;
    const x = p % r.width, y = (p - x) / r.width;
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]] as const) {
      const nx = x + dx, ny = y + dy;
      const n = ny * r.width + nx;
      if (nx < 0 || ny < 0 || nx >= r.width || ny >= r.height || seen.has(n) || !ok(px(r, nx, ny))) continue;
      seen.add(n);
      q.push(n);
      if (seen.size > limit) throw new Error("region grew beyond limit (leak)");
    }
  }
  return seen;
}

/** Star-shaped outline of a region: sub-pixel crossing along 360 rays from its centroid. */
function outline(r: Raster, region: Set<number>, f: (c: [number, number, number]) => number, thr: number): { poly: Vec2[]; centroid: Vec2 } {
  let cx = 0, cy = 0;
  for (const p of region) { cx += (p % r.width) + 0.5; cy += Math.floor(p / r.width) + 0.5; }
  cx /= region.size; cy /= region.size;
  const poly: Vec2[] = [];
  for (let k = 0; k < 360; k++) {
    const a = (k * Math.PI) / 180;
    const d: Vec2 = [Math.cos(a), Math.sin(a)];
    let tOut = 0;
    for (let t = 0; t < 400; t += 0.5) if (region.has(Math.floor(cy + t * d[1]) * r.width + Math.floor(cx + t * d[0]))) tOut = t;
    let prev = bilinear(r, cx + (tOut - 3) * d[0], cy + (tOut - 3) * d[1], (a1, b1, c1) => f([a1, b1, c1]));
    let tEdge = tOut;
    for (let t = tOut - 3 + 0.25; t <= tOut + 4; t += 0.25) {
      const v = bilinear(r, cx + t * d[0], cy + t * d[1], (a1, b1, c1) => f([a1, b1, c1]));
      if (v < thr && prev >= thr) { tEdge = t - 0.25 + (0.25 * (prev - thr)) / (prev - v); break; }
      prev = v;
    }
    poly.push([cx + tEdge * d[0], cy + tEdge * d[1]]);
  }
  return { poly, centroid: [cx, cy] };
}

function convexHull(points: Vec2[]): Vec2[] {
  const pts = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o: Vec2, a: Vec2, b: Vec2): number => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower: Vec2[] = [], upper: Vec2[] = [];
  for (const p of pts) { while (lower.length >= 2 && cross(lower[lower.length - 2]!, lower[lower.length - 1]!, p) <= 0) lower.pop(); lower.push(p); }
  for (const p of [...pts].reverse()) { while (upper.length >= 2 && cross(upper[upper.length - 2]!, upper[upper.length - 1]!, p) <= 0) upper.pop(); upper.push(p); }
  return [...lower.slice(0, -1), ...upper.slice(0, -1)];
}

const boundary = g.image_traces.find((t) => t.id === "trace.board_inner.overhead")!.points_px;
const report: Record<string, unknown> = { homography_curve_rms_px: slotsReport.homography_bare_to_overhead.curve_rms_px };
g.image_traces = g.image_traces.filter((t) => !t.id.startsWith("trace.goal."));
g.landmarks = g.landmarks.filter((l) => !l.id.startsWith("lm.goal."));

for (const [team, cfg] of Object.entries(GOALS) as ["W" | "E", (typeof GOALS)["W"]][]) {
  // Ice cut-out in the bare sheet (white: the background shows through the hole).
  const region = grow(bare, cfg.cutoutSeedBare, (c) => Math.min(...c) >= WHITE_MIN, 80000);
  const { poly: cutBare } = outline(bare, region, (c) => Math.min(...c), (252 + 212) / 2);
  const cutBareS = simplifyClosed(cutBare, 0.75);
  const cutOver = cutBareS.map((p) => applyH(H_BO, p));
  // Cage outline in the overhead: red cage pixels, excluding the goal-line columns.
  const [x0, y0, x1, y1] = cfg.cageBox;
  const red: Vec2[] = [];
  const colCount = new Map<number, number>();
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
    const [r, gg, b] = px(over, x, y);
    if (r > 140 && r - gg > 60 && r - b > 60) { red.push([x + 0.5, y + 0.5]); colCount.set(x, (colCount.get(x) ?? 0) + 1); }
  }
  const lineCols = new Set([...colCount].filter(([, n]) => n > 0.9 * (y1 - y0)).map(([x]) => x));
  const cage = convexHull(red.filter((p) => !lineCols.has(Math.floor(p[0]))));
  // Post-top knobs: centroid of near-black pixels within 30 px of each seed.
  const posts: Record<string, Vec2> = {};
  for (const [side, s] of Object.entries(cfg.postSeeds)) {
    let sx = 0, sy = 0, n = 0;
    for (let y = s[1] - 30; y <= s[1] + 30; y++) for (let x = s[0] - 30; x <= s[0] + 30; x++) {
      if (Math.max(...px(over, x, y)) < POST_DARK_MAX) { sx += x + 0.5; sy += y + 0.5; n++; }
    }
    if (n < 30) throw new Error(`post ${team} ${side}: knob not found`);
    posts[side] = [sx / n, sy / n];
  }
  // Behind-goal space along the goal's centre row: cut-out back edge / cage back to the board boundary.
  const cy = (posts.pos_y![1] + posts.neg_y![1]) / 2;
  const sign = team === "W" ? -1 : 1;
  const edgeX = (poly: Vec2[]): number => {
    const xs: number[] = [];
    poly.forEach((p, i) => {
      const q = poly[(i + 1) % poly.length]!;
      if ((p[1] - cy) * (q[1] - cy) <= 0 && p[1] !== q[1]) xs.push(p[0] + ((cy - p[1]) * (q[0] - p[0])) / (q[1] - p[1]));
    });
    return sign < 0 ? Math.min(...xs) : Math.max(...xs);
  };
  const boardX = edgeX(boundary as Vec2[]);
  const cutBack = edgeX(cutOver);
  const cageBack = edgeX(cage);
  const goalLine = ["top", "bottom"].map((s) => g.landmarks.find((l) => l.id === `lm.board.goal_line.${team}.${s}`)!.px);
  const lineXAt = (y: number): number => goalLine[0]![0] + ((y - goalLine[0]![1]) * (goalLine[1]![0] - goalLine[0]![0])) / (goalLine[1]![1] - goalLine[0]![1]);
  const cutFront = sign < 0 ? Math.max(...cutOver.map((p) => p[0])) : Math.min(...cutOver.map((p) => p[0]));

  const tr = (id: string, sid: string, feature: string, pts: Vec2[], status: ImageTrace["status"], note: string, method: string, stats: Record<string, number>): void => {
    g.image_traces.push({ id, source_image_id: sid, feature, closed: true, points_px: pts.map(rp), landmark_ids: [], status, uncertainty_px: status === "traced" ? 2 : Math.ceil(2 * slotsReport.homography_bare_to_overhead.curve_rms_px + 2), method, inferred_segments: [], stats, note });
  };
  tr(`trace.goal.${team}.cutout.bare`, BARE, "goal_ice_cutout", cutBareS, "traced",
    "Hole in the loose ice sheet behind the goal line (white where the background shows through). Ice-plane feature.",
    `scripts/trace-goals.ts: region grown from seed ${cfg.cutoutSeedBare.join(",")} over min(R,G,B) >= ${WHITE_MIN}; sub-pixel outline on 360 rays; Douglas-Peucker 0.75 px.`,
    { area_px: region.size, vertices: cutBareS.length });
  tr(`trace.goal.${team}.cutout.overhead`, OVER, "goal_ice_cutout", cutOver, "assumed",
    "The bare-sheet cut-out mapped into the overhead with the slot homography (assume.bare_sheet_same_slot_layout). In the overhead the hole shows as the dark area inside the cage.",
    "Bare-sheet cut-out outline mapped by the bare->overhead homography of validation/slots-report.json.",
    { front_edge_x_px: round(cutFront, 1), goal_line_x_px_at_centre_row: round(lineXAt(cy), 1), front_edge_minus_goal_line_px: round(cutFront - lineXAt(cy), 1) });
  tr(`trace.goal.${team}.cage.overhead`, OVER, "goal_cage_outline_elevated", cage, "traced",
    "Top-view outline of the red goal cage. ELEVATED: perspective shifts it outward from its footprint; not an ice-level outline.",
    `scripts/trace-goals.ts: convex hull of red pixels (R>140, R-G>60, R-B>60) in box ${cfg.cageBox.join(",")}, goal-line columns removed.`,
    { red_pixels: red.length });
  const lmIds: string[] = [];
  for (const [side, p] of Object.entries(posts)) {
    const id = `lm.goal.${team}.post_top.${side}`;
    lmIds.push(id);
    g.landmarks.push({ id, source_image_id: OVER, px: rp(p), uncertainty_px: 5, description: `Top knob of the ${side === "pos_y" ? "+y" : "-y"} front post of goal.${team} (centroid of near-black knob pixels). ELEVATED: not the post base on the ice.`, visibility: "visible" } satisfies Landmark);
  }
  const goal = g.goals.find((x) => x.id === `goal.${team}`)!;
  goal.image_trace_ids = [`trace.goal.${team}.cutout.bare`, `trace.goal.${team}.cutout.overhead`, `trace.goal.${team}.cage.overhead`];
  goal.landmark_ids = lmIds;
  goal.note = `Goal region traced in pixels (docs/goals.md). Mouth between post tops ${round(Math.hypot(posts.pos_y![0] - posts.neg_y![0], posts.pos_y![1] - posts.neg_y![1]), 1)} px in the overhead (elevated; opening width, height, post size and depth stay unknown in mm). The white insert is not visible in the reference photos; the dark area inside the cage is the ice cut-out.`;
  report[`goal.${team}`] = {
    cutout_bare_area_px: region.size,
    cutout_vertices: cutBareS.length,
    cutout_front_edge_minus_goal_line_px: round(cutFront - lineXAt(cy), 1),
    post_tops_px: Object.fromEntries(Object.entries(posts).map(([k, v]) => [k, rp(v)])),
    mouth_between_post_tops_px: round(Math.hypot(posts.pos_y![0] - posts.neg_y![0], posts.pos_y![1] - posts.neg_y![1]), 1),
    post_tops_minus_goal_line_px: Object.fromEntries(Object.entries(posts).map(([k, v]) => [k, round(v[0] - lineXAt(v[1]), 1)])),
    behind_goal_px: { board_to_cutout_back: round(Math.abs(cutBack - boardX), 1), board_to_cage_back_elevated: round(Math.abs(cageBack - boardX), 1) },
  };
}
g.goal_setup.note = `${g.goal_setup.note.split(" Reference photos:")[0]} Reference photos: no white insert is visible in either goal of the official overhead; the dark area inside each cage is the ice-sheet cut-out behind the goal line (docs/goals.md).`;
writeFileSync("data/geometry.json", JSON.stringify(g, null, 2) + "\n");
writeFileSync("validation/goals-report.json", JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report, null, 1));
