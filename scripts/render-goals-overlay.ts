// Renders validation/08-goals-and-goalies.svg: the 12-route inventory on the unchanged overhead, both goal
// regions zoomed in the overhead and the bare sheet, and the unresolved dimensions.
import { readFileSync, writeFileSync } from "node:fs";
import type { GeometryFile, ImageTrace } from "../src/model/geometry.ts";

const OUT = "validation/08-goals-and-goalies.svg";
const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const goals = JSON.parse(readFileSync("validation/goals-report.json", "utf8")) as Record<string, any>;
const slots = JSON.parse(readFileSync("validation/slots-report.json", "utf8")) as any;
const img = (id: string) => g.source_images.find((s) => s.source_id === id)!;
const over = img("stiga_se_fi_overhead"), bare = img("stiga_ca_bare_ice_sheet");
const esc = (s: string): string => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const f1 = (v: number): string => v.toFixed(1);
const trace = (id: string): ImageTrace => g.image_traces.find((t) => t.id === id)!;
const PLAYERS = g.players.map((p) => p.id);
const COLOURS: Record<string, string> = { G: "#000000", LD: "#e6194b", RD: "#f58231", C: "#911eb4", LW: "#3cb44b", RW: "#4363d8" };
const col = (p: string): string => (p.startsWith("E") && !p.endsWith("G") ? shade(COLOURS[p.split("-")[1]!]!) : COLOURS[p.split("-")[1]!]!);
function shade(hex: string): string {
  const n = parseInt(hex.slice(1), 16);
  const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.round(v * 0.55));
  return `#${c.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}
const pts = (t: ImageTrace): string => t.points_px.map((q) => `${f1(q[0])},${f1(q[1])}`).join(" ");

function layer(k: "overhead" | "bare", dash: number, labels: number): string {
  const out: string[] = [];
  for (const p of PLAYERS) {
    const t = trace(`trace.slot.${p}.${k}`);
    const c = p.endsWith("G") ? "#00d0ff" : col(p);
    out.push(`<polyline points="${pts(t)}" fill="none" stroke="${c}" stroke-width="${p.endsWith("G") ? 3 : 2}" vector-effect="non-scaling-stroke"/>`);
    for (const e of ["start", "end"]) {
      const l = g.landmarks.find((x) => x.id === `lm.slot.${p}.${k}.${e}`)!;
      out.push(l.visibility === "visible"
        ? `<circle cx="${f1(l.px[0])}" cy="${f1(l.px[1])}" r="${dash}" fill="${c}" stroke="#fff" stroke-width="1.5" vector-effect="non-scaling-stroke"/>`
        : `<circle cx="${f1(l.px[0])}" cy="${f1(l.px[1])}" r="${dash * 1.4}" fill="none" stroke="${c}" stroke-width="2.5" vector-effect="non-scaling-stroke"/>`);
    }
    if (labels) {
      const q = t.points_px[Math.floor(t.points_px.length / 2)]!;
      out.push(`<text x="${f1(q[0] + (p.endsWith("G") ? labels : 0))}" y="${f1(q[1] - labels * 0.6)}" font-size="${labels}" font-weight="bold" fill="${c}" stroke="#fff" stroke-width="${labels / 5}" paint-order="stroke">${p}</text>`);
    }
  }
  if (k === "overhead") {
    for (const e of slots.end_checks.filter((x: any) => x.occluder && x.pid.endsWith("G"))) {
      const [u, v] = e.predicted, s = dash * 1.3;
      out.push(`<path d="M${f1(u - s)},${f1(v - s)} L${f1(u + s)},${f1(v + s)} M${f1(u - s)},${f1(v + s)} L${f1(u + s)},${f1(v - s)}" stroke="#00d0ff" stroke-width="2.5" vector-effect="non-scaling-stroke"/>`);
    }
  }
  for (const team of ["W", "E"]) {
    if (k === "overhead") {
      out.push(`<polygon points="${pts(trace(`trace.goal.${team}.cutout.overhead`))}" fill="#ffff00" fill-opacity="0.25" stroke="#ffd000" stroke-width="2.5" stroke-dasharray="${dash} ${dash}" vector-effect="non-scaling-stroke"/>`);
      out.push(`<polygon points="${pts(trace(`trace.goal.${team}.cage.overhead`))}" fill="none" stroke="#ff00ff" stroke-width="2" stroke-dasharray="${dash / 2} ${dash / 2}" vector-effect="non-scaling-stroke"/>`);
      for (const side of ["pos_y", "neg_y"]) {
        const l = g.landmarks.find((x) => x.id === `lm.goal.${team}.post_top.${side}`)!;
        out.push(`<rect x="${f1(l.px[0] - dash)}" y="${f1(l.px[1] - dash)}" width="${dash * 2}" height="${dash * 2}" fill="none" stroke="#ff00ff" stroke-width="2.5" vector-effect="non-scaling-stroke"/>`);
      }
      for (const s of ["top", "bottom"]) {
        const l = g.landmarks.find((x) => x.id === `lm.board.goal_line.${team}.${s}`)!;
        out.push(`<circle cx="${f1(l.px[0])}" cy="${f1(l.px[1])}" r="${dash}" fill="none" stroke="#003f8a" stroke-width="2.5" vector-effect="non-scaling-stroke"/>`);
      }
    } else {
      out.push(`<polygon points="${pts(trace(`trace.goal.${team}.cutout.bare`))}" fill="none" stroke="#ffb000" stroke-width="2.5" vector-effect="non-scaling-stroke"/>`);
    }
  }
  return out.join("\n");
}

const b64 = (p: string): string => readFileSync(p).toString("base64");
const W = 5100;
const main = { x: 300, y: 1300, w: 5100, h: 3000 };
const zoomO = { W: { x: 650, y: 2380, w: 1000, h: 800 }, E: { x: 3900, y: 2380, w: 1000, h: 800 } };
const zoomB = { W: { x: 270, y: 640, w: 350, h: 300 }, E: { x: 1840, y: 640, w: 350, h: 300 } };
const half = W / 2 - 30;
const row2 = main.h + 120;
const h2 = (half * 800) / 1000;
const row3 = row2 + h2 + 110;
const h3 = (half * 300) / 350;
const notesTop = row3 + h3 + 90;
const panel = (x: number, y: number, v: { x: number; y: number; w: number; h: number }, id: string, k: "overhead" | "bare", title: string): string => {
  const w = half, h = (half * v.h) / v.w;
  return `<text x="${x}" y="${y - 14}" font-size="34" fill="#111">${esc(title)} (uniform ${f1(w / v.w)}x; source px x ${v.x}..${v.x + v.w}, y ${v.y}..${v.y + v.h})</text>
<svg x="${x}" y="${y}" width="${w}" height="${h}" viewBox="${v.x} ${v.y} ${v.w} ${v.h}"><use href="#${id}"/>${layer(k, k === "overhead" ? 6 : 2.5, k === "overhead" ? 26 : 10)}</svg>
<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="none" stroke="#444" stroke-width="3"/>`;
};
const gW = goals["goal.W"], gE = goals["goal.E"];
const res = (p: string) => slots.paths[`path.${p}`].homography_curve_residual_px;
const notes = [
  `08 - Goalie routes and goal regions - PROVISIONAL, AI review only (no personal user approval). Geometry ${g.geometry_version}.`,
  `Route inventory complete in pixels: 10 outfield routes (W/E x LD, RD, C, LW, RW) + 2 goalie routes (W-G, E-G, cyan). This does NOT establish measured usable travel: all 12 usable_stops, the fixture-axis paths and rotation limits remain UNKNOWN (rod recordings needed).`,
  `Goalie routes: own short slots in the creases, about 3 deg off the image vertical in both photographs; not skater paths. W-G lower end and E-G upper end hidden under the goalies (open circle = observed end, X = bare-sheet prediction). Bare vs overhead: the goalie slots sit ${res("W-G").rms} / ${res("E-G").rms} px RMS apart after the fit, a symmetric ~7 px shift toward the rink centre (unresolved; excluded from the homography fit, docs/tracks.md).`,
  `Goal regions: yellow dashed = ice-sheet cut-out behind the goal line, traced in the bare sheet and mapped into the overhead (front edge vs goal line: W ${gW.cutout_front_edge_minus_goal_line_px} px, E ${gE.cutout_front_edge_minus_goal_line_px} px). Magenta dotted = red cage outline, ELEVATED. Magenta squares = post-top knobs, ELEVATED. Blue circles = goal-line landmarks.`,
  `Measured in overhead pixels only: mouth between post tops W ${gW.mouth_between_post_tops_px} px, E ${gE.mouth_between_post_tops_px} px; post tops vs goal line W ${gW.post_tops_minus_goal_line_px.pos_y}/${gW.post_tops_minus_goal_line_px.neg_y} px, E ${gE.post_tops_minus_goal_line_px.pos_y}/${gE.post_tops_minus_goal_line_px.neg_y} px (perspective displacement of elevated tops; asymmetric W/E, unexplained); behind-goal space board to cut-out back W ${gW.behind_goal_px.board_to_cutout_back} px, E ${gE.behind_goal_px.board_to_cutout_back} px.`,
  `UNRESOLVED dimensions (unknown in mm): goal opening width and height, post and crossbar size, cage depth, goal position relative to the goal line at ice level, cut-out size, goalie pivot position and offset, goalie travel stops, goalie rotation limits.`,
  `Goal configuration (data): retail supplied white insert/deflector vs the user's setup = WITHOUT inserts or goal cups, screens kept (user statement, docs/decisions.md D5). Reference photos: no white insert visible; the dark area inside each cage is the ice cut-out.`,
];
const wrap = (t: string, width = 200): string[] => {
  const out: string[] = [];
  let line = "";
  for (const w of t.split(" ")) { if (line && line.length + w.length + 1 > width) { out.push(line); line = "      " + w; } else line = line ? `${line} ${w}` : w; }
  return [...out, line];
};
const lines = notes.flatMap((n) => wrap(n));
const H = notesTop + lines.length * 44 + 60;
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W / 4}" height="${Math.round(H / 4)}" font-family="DejaVu Sans, Arial, sans-serif">
<title>08 goals and goalie routes (provisional)</title>
<defs>
<image id="overhead" x="0" y="0" width="${over.width_px}" height="${over.height_px}" href="data:image/jpeg;base64,${b64(over.local_path)}"/>
<image id="bare" x="0" y="0" width="${bare.width_px}" height="${bare.height_px}" href="data:image/jpeg;base64,${b64(bare.local_path)}"/>
</defs>
<rect width="${W}" height="${H}" fill="#fff"/>
<svg x="0" y="0" width="${main.w}" height="${main.h}" viewBox="${main.x} ${main.y} ${main.w} ${main.h}"><use href="#overhead"/>${layer("overhead", 8, 40)}</svg>
${panel(20, row2, zoomO.W, "overhead", "overhead", "goal.W and W-G (overhead)")}
${panel(W / 2 + 10, row2, zoomO.E, "overhead", "overhead", "goal.E and E-G (overhead)")}
${panel(20, row3, zoomB.W, "bare", "bare", "W goal area (bare sheet, older artwork)")}
${panel(W / 2 + 10, row3, zoomB.E, "bare", "bare", "E goal area (bare sheet, older artwork)")}
${lines.map((t, i) => `<text x="20" y="${notesTop + i * 44}" font-size="32" fill="#111">${esc(t)}</text>`).join("\n")}
</svg>
`;
writeFileSync(OUT, svg);
console.log(`wrote ${OUT} (${(svg.length / 1e6).toFixed(2)} MB)`);
