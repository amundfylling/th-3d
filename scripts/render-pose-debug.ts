// Renders validation/09-pose-debug.svg: static sample states from the pure pose functions, drawn in
// world millimetres (preview scale ASSUMED). The glyph is a debug marker, not contact geometry.
import { readFileSync, writeFileSync } from "node:fs";
import type { GeometryFile } from "../src/model/geometry.ts";
import { loadFigurePaths } from "../src/model/paths.ts";
import { goaliePose, skaterPose, toWorld, type FigureState, type Pose, type Vec3 } from "../src/model/pose.ts";

const OUT = "validation/09-pose-debug.svg";
const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const paths = loadFigurePaths(g);
const S = 5; // SVG units per mm
const esc = (s: string): string => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const X = (x: number): number => x * S;
const Y = (y: number): number => -y * S;
const f1 = (v: number): string => v.toFixed(1);

const SAMPLES: { player: string; state: FigureState; label?: string }[] = [
  { player: "W-LD", state: { u_preview: 0, thetaDeg: 0 } },
  { player: "W-LD", state: { u_preview: 0.5, thetaDeg: 0 } },
  { player: "W-LD", state: { u_preview: 1, thetaDeg: 0 } },
  { player: "E-LD", state: { u_preview: 0.3, thetaDeg: 90 } },
  { player: "W-C", state: { u_preview: 0.5, thetaDeg: 45 } },
  { player: "E-C", state: { u_preview: 0.5, thetaDeg: -45 } },
  { player: "E-RW", state: { u_preview: 0.8, thetaDeg: 350 }, label: "350" },
  { player: "E-RW", state: { u_preview: 0.9, thetaDeg: 370 }, label: "370 (continuous through 360)" },
  { player: "W-LW", state: { u_preview: 0.95, thetaDeg: 90 }, label: "behind E goal" },
  { player: "E-LW", state: { u_preview: 0.05, thetaDeg: 0 } },
  { player: "W-RW", state: { u_preview: 0.7, thetaDeg: -30 } },
  { player: "E-RD", state: { u_preview: 0.6, thetaDeg: 0 } },
  { player: "W-RD", state: { u_preview: 1.2, thetaDeg: 0 }, label: "INVALID on purpose" },
  { player: "W-G", state: { u_preview: 0.5, thetaDeg: 0 } },
  { player: "E-G", state: { u_preview: 0.5, thetaDeg: 20 } },
];
// Debug glyph in the pivot-local frame (mm): heading, left marker and an asymmetric left-side "blade".
const GLYPH = { heading: [[0, 0, 0], [28, 0, 0]] as Vec3[], left: [[0, 0, 0], [0, 12, 0]] as Vec3[], blade: [[4, 4, 0], [20, 9, 0], [30, 9, 0]] as Vec3[] };

const board = g.board.inner_boundary.world!.points_mm;
const xs = board.map((p) => p[0]), ys = board.map((p) => p[1]);
const pad = 40;
const minX = Math.min(...xs) - pad, maxX = Math.max(...xs) + pad, minY = Math.min(...ys) - pad, maxY = Math.max(...ys) + pad;
const vb = { x: X(minX), y: Y(maxY), w: (maxX - minX) * S, h: (maxY - minY) * S };
const parts: string[] = [];
parts.push(`<polygon points="${board.map((p) => `${f1(X(p[0]))},${f1(Y(p[1]))}`).join(" ")}" fill="#f4f7fb" stroke="#555" stroke-width="3"/>`);
for (const p of paths) {
  const f = g.fixture_paths.find((x) => x.id === p.sampler.id)!;
  parts.push(`<polyline points="${f.centreline!.points_mm.map((q) => `${f1(X(q[0]))},${f1(Y(q[1]))}`).join(" ")}" fill="none" stroke="${p.sampler.kind === "goalie" ? "#7fd8ff" : "#c8c8c8"}" stroke-width="${p.sampler.kind === "goalie" ? 10 : 7}" stroke-linecap="round"/>`);
}
const results: string[] = [];
let labelIndex = 0;
for (const s of SAMPLES) {
  const fp = paths.find((p) => p.playerId === s.player)!;
  const r = fp.sampler.kind === "goalie" ? goaliePose(fp.sampler, fp.team, s.state) : skaterPose(fp.sampler, fp.team, s.state);
  const tag = `${s.player} u=${s.state.u_preview} theta=${s.state.thetaDeg}`;
  if (!r.ok) {
    results.push(`${tag}: FLAGGED INVALID - ${r.reason}`);
    continue;
  }
  const p: Pose = r;
  const line = (pts: Vec3[], stroke: string, w: number): string =>
    `<polyline points="${toWorld(p, pts).map((q) => `${f1(X(q[0]))},${f1(Y(q[1]))}`).join(" ")}" fill="none" stroke="${stroke}" stroke-width="${w}" stroke-linecap="round"/>`;
  const [px, py] = p.pivot;
  const tan = p.pathTangent;
  const colour = fp.team === "W" ? "#0b4fb3" : "#c79a00";
  parts.push(`<line x1="${f1(X(px))}" y1="${f1(Y(py))}" x2="${f1(X(px + 22 * tan[0]))}" y2="${f1(Y(py + 22 * tan[1]))}" stroke="#999" stroke-width="3" stroke-dasharray="6 5"/>`);
  parts.push(line(GLYPH.heading, "#d00000", 6), line(GLYPH.left, "#009900", 6), line(GLYPH.blade, colour, 8));
  parts.push(`<circle cx="${f1(X(px))}" cy="${f1(Y(py))}" r="${4 * S}" fill="none" stroke="#111" stroke-width="4"/>`);
  // Alternate labels above/below and anchor them inward near the right edge so none overlap or clip.
  const below = labelIndex++ % 2 === 1;
  const nearRight = X(px) > vb.x + vb.w * 0.7;
  parts.push(`<text x="${f1(X(px) + (nearRight ? -30 : 30))}" y="${f1(Y(py) + (below ? 70 : -30))}" text-anchor="${nearRight ? "end" : "start"}" font-size="44" fill="#111" stroke="#fff" stroke-width="8" paint-order="stroke">${esc(`${s.player} u=${s.state.u_preview} th=${s.state.thetaDeg}${s.label ? ` (${s.label})` : ""}`)}</text>`);
  results.push(`${tag}: pivot (${f1(px)}, ${f1(py)}) mm, heading ${f1(p.headingDeg)} deg, det +1; assumptions: ${p.assumptions.join("; ")}`);
}
const notes = [
  "09 - Pose debug (static). Pure functions in src/model/pose.ts; world mm, +x right (toward goal.E), +y up; PREVIEW SCALE ASSUMED (not calibrated). AI review only.",
  "State = (u_preview in [0,1], thetaDeg). u_preview is a NORMALISED ARC-LENGTH preview parameter along the visible slot centreline - NOT rod displacement; rod mapping and stops are unknown.",
  "Glyph (DEBUG ONLY, not contact geometry): black circle = fixture axis (assumed on the slot centreline); red = local +x (heading); green = local +y (figure's left); team-coloured L = asymmetric left-side marker used to show handedness; grey dashed = slot tangent (rotation is NOT coupled to it).",
  "Team W (blue) home heading 0 deg, team E (gold) 180 deg: a proper rotation (det +1), never a mirror, so the left-side marker stays on each figure's left. Goalies (cyan paths) use goaliePose.",
  ...results,
];
const wrap = (t: string, width = 150): string[] => {
  const out: string[] = [];
  let line = "";
  for (const w of t.split(" ")) { if (line && line.length + w.length + 1 > width) { out.push(line); line = "    " + w; } else line = line ? `${line} ${w}` : w; }
  return [...out, line];
};
const noteLines = notes.flatMap((n) => wrap(n));
const noteTop = vb.y + vb.h + 80;
const noteSvg = noteLines.map((t, i) => `<text x="${f1(vb.x + 20)}" y="${f1(noteTop + i * 56)}" font-size="40" fill="#111">${esc(t)}</text>`).join("\n");
const totalH = vb.h + 120 + noteLines.length * 56;
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${f1(vb.x)} ${f1(vb.y)} ${f1(vb.w)} ${f1(totalH)}" width="${Math.round(vb.w / 4)}" height="${Math.round(totalH / 4)}" font-family="DejaVu Sans, Arial, sans-serif">
<title>09 pose debug</title>
<rect x="${f1(vb.x)}" y="${f1(vb.y)}" width="${f1(vb.w)}" height="${f1(totalH)}" fill="#fff"/>
${parts.join("\n")}
${noteSvg}
</svg>
`;
writeFileSync(OUT, svg);
console.log(`wrote ${OUT}`);
console.log(results.join("\n"));
