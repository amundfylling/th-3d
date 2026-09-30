// Renders validation/10-skater-contacts.svg: the evidence crop for the representative skater and its
// PROVISIONAL debug contacts at several orientations for both teams (via the pose functions), with a
// finite-radius puck (nominal diameter) beside the blade and a side view with the unknown puck thickness.
import { readFileSync, writeFileSync } from "node:fs";
import type { GeometryFile } from "../src/model/geometry.ts";
import { pathSampler, skaterPose, toWorld, type Pose, type Vec3 } from "../src/model/pose.ts";

const OUT = "validation/10-skater-contacts.svg";
const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const rep = JSON.parse(readFileSync("validation/10-contacts-report.json", "utf8")) as { pivot_px: [number, number]; pivot_along_slot_uncertainty_mm: number; mm_per_px_assumed: number };
const asset = g.figure_assets.find((a) => a.id === "fig.W-RD")!;
const shape = (kind: string, side?: string) => asset.contact_shapes.find((c) => c.kind === kind && (!side || c.id.endsWith(side)))!.geometry!.points_mm as Vec3[];
const blade = shape("blade"), shaft = shape("stick_shaft"), skL = shape("skate", "left"), skR = shape("skate", "right");
const puckD = g.puck.diameter.value!; // catalog_nominal
const esc = (s: string): string => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const f1 = (v: number): string => v.toFixed(1);

// Puck placed beside the blade's outer face, at the blade midpoint (pivot-local, debug placement only).
const b0 = blade[0]!, b1 = blade[1]!;
const bm: Vec3 = [(b0[0] + b1[0]) / 2, (b0[1] + b1[1]) / 2, 0];
const bd = [b1[0] - b0[0], b1[1] - b0[1]];
const bl = Math.hypot(bd[0]!, bd[1]!);
const outward: [number, number] = [bd[1]! / bl, -bd[0]! / bl]; // right-hand normal of the blade direction
const sideSign = outward[0] * bm[0] + outward[1] * bm[1] > 0 ? 1 : -1; // point away from the pivot
const puckC: Vec3 = [bm[0] + sideSign * outward[0] * (puckD / 2 + 0.5), bm[1] + sideSign * outward[1] * (puckD / 2 + 0.5), 0];

// Panels: one synthetic straight path per panel so the SAME pose functions produce every drawing.
const S = 6; // svg units per mm in panels
const PANEL = 110; // mm per panel side
const thetas = [0, 60, 135, -90];
const panels: string[] = [];
const results: string[] = [];
(["W", "E"] as const).forEach((team, row) => {
  thetas.forEach((th, col) => {
    const cx = 60 + col * (PANEL * S + 40) + (PANEL * S) / 2, cy = 1300 + row * (PANEL * S + 120) + (PANEL * S) / 2;
    const path = pathSampler(`panel.${team}.${th}`, "skater", [[-10, 0], [10, 0]]);
    const r = skaterPose(path, team, { u_preview: 0.5, thetaDeg: th });
    if (!r.ok) throw new Error(r.reason);
    const p: Pose = r;
    const P = (q: Vec3): string => `${f1(cx + q[0] * S)},${f1(cy - q[1] * S)}`;
    const poly = (pts: Vec3[], stroke: string, w: number, extra = ""): string => `<polyline points="${toWorld(p, pts).map(P).join(" ")}" fill="none" stroke="${stroke}" stroke-width="${w}" stroke-linecap="round" ${extra}/>`;
    const [pc] = toWorld(p, [puckC]);
    const [pv] = toWorld(p, [[0, 0, 0]]);
    panels.push(`<rect x="${f1(cx - (PANEL * S) / 2)}" y="${f1(cy - (PANEL * S) / 2)}" width="${PANEL * S}" height="${PANEL * S}" fill="#f6f8fb" stroke="#999" stroke-width="2"/>`);
    panels.push(`<text x="${f1(cx - (PANEL * S) / 2 + 10)}" y="${f1(cy - (PANEL * S) / 2 + 40)}" font-size="34" fill="#111">team ${team}, theta ${th} deg (heading ${p.headingDeg})</text>`);
    panels.push(poly([[0, 0, 0], [30, 0, 0]], "#d00000", 5), poly([[0, 0, 0], [0, 14, 0]], "#009900", 5));
    panels.push(poly(shaft, "#888", 4), poly(skL, "#555", 7), poly(skR, "#555", 7), poly(blade.slice(0, 2), team === "W" ? "#0b4fb3" : "#c79a00", 10));
    panels.push(`<circle cx="${f1(cx + pc![0] * S)}" cy="${f1(cy - pc![1] * S)}" r="${f1((puckD / 2) * S)}" fill="#222" fill-opacity="0.85" stroke="#000" stroke-width="2"/>`);
    panels.push(`<path d="M${f1(cx + pv![0] * S - 14)},${f1(cy - pv![1] * S)} h28 M${f1(cx + pv![0] * S)},${f1(cy - pv![1] * S - 14)} v28" stroke="#000" stroke-width="4"/>`);
    // Fixed-in-body check printed per panel: blade tip distance from the axis.
    const [tipW] = toWorld(p, [blade[1]!]);
    results.push(`${team} ${th}: blade tip ${f1(Math.hypot(tipW![0] - pv![0], tipW![1] - pv![1]))} mm from the axis`);
  });
});

// Evidence panel: overhead crop around the figure with the covered slot stretch and assumed pivot.
const over = g.source_images.find((s) => s.source_id === "stiga_se_fi_overhead")!;
const ev = { x: 2240, y: 3000, w: 360, h: 460 };
const evScale = 2.4;
const trace = g.image_traces.find((t) => t.id === "trace.slot.W-RD.overhead")!;
const unc = rep.pivot_along_slot_uncertainty_mm / rep.mm_per_px_assumed;
const evidence = `<svg x="40" y="60" width="${ev.w * evScale}" height="${ev.h * evScale}" viewBox="${ev.x} ${ev.y} ${ev.w} ${ev.h}"><use href="#overhead"/>
<polyline points="${trace.points_px.map((q) => `${q[0]},${q[1]}`).join(" ")}" fill="none" stroke="#e6194b" stroke-width="2" vector-effect="non-scaling-stroke"/>
<line x1="${rep.pivot_px[0] - unc}" y1="${rep.pivot_px[1]}" x2="${rep.pivot_px[0] + unc}" y2="${rep.pivot_px[1]}" stroke="#ff8c00" stroke-width="6" vector-effect="non-scaling-stroke"/>
<path d="M${rep.pivot_px[0] - 8},${rep.pivot_px[1]} h16 M${rep.pivot_px[0]},${rep.pivot_px[1] - 8} v16" stroke="#000" stroke-width="3" vector-effect="non-scaling-stroke"/>
<circle cx="2400" cy="3250" r="6" fill="none" stroke="#009900" stroke-width="3" vector-effect="non-scaling-stroke"/>
<circle cx="2393" cy="3050" r="6" fill="none" stroke="#0b4fb3" stroke-width="3" vector-effect="non-scaling-stroke"/>
<line x1="2330" y1="3330" x2="2440" y2="3330" stroke="#d00000" stroke-width="3" vector-effect="non-scaling-stroke" stroke-dasharray="6 4"/>
</svg>
<rect x="40" y="60" width="${ev.w * evScale}" height="${ev.h * evScale}" fill="none" stroke="#444" stroke-width="3"/>`;

// Side view (local x-z of the blade plane is approximated by the local y-z view: blade lies along +y).
const sv = { x: 1000, y: 70, s: 10 };
const SP = (y: number, z: number): string => `${f1(sv.x + y * sv.s)},${f1(sv.y + 700 - z * sv.s)}`;
const bladeYs = [blade[0]![1], blade[1]![1]];
const side = [
  `<text x="${sv.x}" y="${sv.y + 30}" font-size="34" fill="#111">Side view along the figure's +x (local y-z), mm - DEBUG heights</text>`,
  `<line x1="${f1(sv.x - 20)}" y1="${f1(sv.y + 700)}" x2="${f1(sv.x + 70 * sv.s)}" y2="${f1(sv.y + 700)}" stroke="#7aa7d6" stroke-width="4"/>`,
  `<text x="${f1(sv.x + 60 * sv.s)}" y="${f1(sv.y + 740)}" font-size="28" fill="#335">ice top, z = 0</text>`,
  `<polygon points="${[SP(bladeYs[0]!, 0), SP(bladeYs[1]!, 0), SP(bladeYs[1]!, 4), SP(bladeYs[0]!, 4)].join(" ")}" fill="#0b4fb3" opacity="0.8"/>`,
  `<polyline points="${[SP(shaft[0]![1], shaft[0]![2]), SP(shaft[1]![1], shaft[1]![2])].join(" ")}" stroke="#888" stroke-width="5" fill="none"/>`,
  `<line x1="${f1(sv.x)}" y1="${f1(sv.y + 700)}" x2="${f1(sv.x)}" y2="${f1(sv.y + 700 - 57 * sv.s)}" stroke="#000" stroke-width="3" stroke-dasharray="10 6"/>`,
  `<text x="${f1(sv.x + 10)}" y="${f1(sv.y + 700 - 57 * sv.s + 30)}" font-size="28">fixture axis (z up); figure approx. 57 mm, datum unknown</text>`,
  `<rect x="${f1(sv.x + (bladeYs[1]! + 1) * sv.s)}" y="${f1(sv.y + 700 - 8 * sv.s)}" width="${f1(puckD * sv.s)}" height="${f1(8 * sv.s)}" fill="none" stroke="#222" stroke-width="3" stroke-dasharray="8 6"/>`,
  `<text x="${f1(sv.x + (bladeYs[1]! + 1) * sv.s)}" y="${f1(sv.y + 700 - 9 * sv.s)}" font-size="28">puck: diameter approx. ${puckD} mm (nominal); THICKNESS UNKNOWN (box height arbitrary)</text>`,
].join("\n");

const notes = [
  "10 - Representative skater W-RD (Finland no. 4): contact inventory and PROVISIONAL DEBUG contact geometry. AI review only. CRITICAL CHECKPOINT: pivot and blade offset are UNMEASURED and drive shot accuracy.",
  `Evidence (top left, overhead unchanged at ${evScale}x): red = W-RD slot trace; orange bar = covered stretch where the hidden fixture axis must lie (+-${rep.pivot_along_slot_uncertainty_mm} mm along the slot, preview scale); black cross = assumed pivot (midpoint); green circle = hands; blue circle = stick tip; red dashed = body axis (figure faces +x). The stick is on the figure's LEFT.`,
  "Panels: the same pose functions (skaterPose + toWorld) place the debug contacts for team W (row 1) and team E (row 2) at theta 0/60/135/-90. Thick bar = debug blade; grey = shaft projection; dark grey = skate placeholders; black disc = puck at nominal diameter beside the blade (placement arbitrary, no velocity or collision). Red = heading, green = figure's left.",
  "Blade stays on each figure's left for both teams (proper rotation), and every contact point keeps its distance from the axis: " + results.join("; ") + ".",
  "Real values (inventory in data/geometry.json fig.W-RD): fixture axis position, blade outline/offset/height, skate contacts and ice clearance are UNKNOWN. Puck thickness is not established by any photograph.",
];
const wrap = (t: string, width = 140): string[] => {
  const out: string[] = [];
  let line = "";
  for (const w of t.split(" ")) { if (line && line.length + w.length + 1 > width) { out.push(line); line = "    " + w; } else line = line ? `${line} ${w}` : w; }
  return [...out, line];
};
const lines = notes.flatMap((n) => wrap(n));
const W = 60 + 4 * (PANEL * S + 40);
const notesTop = 1300 + 2 * (PANEL * S + 120) + 40;
const H = notesTop + lines.length * 46 + 60;
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${Math.round(W / 3)}" height="${Math.round(H / 3)}" font-family="DejaVu Sans, Arial, sans-serif">
<title>10 skater contacts (provisional)</title>
<defs><image id="overhead" x="0" y="0" width="${over.width_px}" height="${over.height_px}" href="data:image/jpeg;base64,${readFileSync(over.local_path).toString("base64")}"/></defs>
<rect width="${W}" height="${H}" fill="#fff"/>
${evidence}
${side}
${panels.join("\n")}
${lines.map((t, i) => `<text x="40" y="${notesTop + i * 46}" font-size="32" fill="#111">${esc(t)}</text>`).join("\n")}
</svg>
`;
writeFileSync(OUT, svg);
console.log(`wrote ${OUT}`);
