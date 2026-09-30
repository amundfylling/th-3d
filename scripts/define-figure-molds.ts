// Figure molds (2026-09-30, before iteration 21): records the user's figure photos/videos and statements as
// sources, and replaces the provisional debug contacts of iterations 10/15 with contact geometry of the fitted
// rigid molds (data/figure-molds.json x the overhead-fitted scale). All 12 figure assets get their mold group.
// Inputs: data/figure-molds.json, validation/players/{figures-report,overhead-fit,skater-fit,goalie-fit}.json,
// references/index.json. Writes data/geometry.json. Evidence chain: docs/players.md.
import { readFileSync, writeFileSync } from "node:fs";
import type { Assumption, ContactShape, GeometryFile, InventoryItem, Quantity } from "../src/model/geometry.ts";

type V3 = [number, number, number];
const round = (v: number, d = 2): number => Math.round(v * 10 ** d) / 10 ** d;
const read = <T>(p: string): T => JSON.parse(readFileSync(p, "utf8")) as T;
const g = read<GeometryFile>("data/geometry.json");
const molds = read<Record<string, any>>("data/figure-molds.json");
const rep = read<{ scale_k_mm_per_mold_unit: number; assets: Record<string, any> }>("validation/players/figures-report.json");
const over = read<{ scale_k_mm_per_mold_unit: number; goalie_only_best_scale_k: number; figures: Record<string, { iou: number }> }>("validation/players/overhead-fit.json");
const fits = { skater: read<{ mean_iou: number; views: Record<string, { iou: number }> }>("validation/players/skater-fit.json"), goalie: read<{ mean_iou: number; views: Record<string, { iou: number }> }>("validation/players/goalie-fit.json") };
const index = read<{ sources: { id: string; local_path: string; sha256: string; native_width_px: number; native_height_px: number; title: string }[] }>("references/index.json");
const K = rep.scale_k_mm_per_mold_unit;
if (K !== over.scale_k_mm_per_mold_unit) throw new Error("figures-report and overhead-fit disagree on k: rebuild the figures");

// ---- Sources ----------------------------------------------------------------------------------------
const MEDIA = index.sources.filter((s) => s.id.startsWith("user_") && (s.id.includes("_photo_") || s.id.includes("_video_")));
const STATEMENT = "user_statement_2026_09_30_players";
const PACK = "stiga_ca_team_pack_finland";
const OVER = "stiga_se_fi_overhead";
g.sources = g.sources.filter((s) => !s.id.startsWith("user_goalie_") && !s.id.startsWith("user_skater_") && s.id !== STATEMENT && s.id !== PACK);
g.source_images = g.source_images.filter((s) => !s.source_id.startsWith("user_goalie_") && !s.source_id.startsWith("user_skater_") && s.source_id !== PACK);
for (const m of MEDIA) {
  g.sources.push({ id: m.id, kind: "reference_image", title: m.title, index_id: m.id, url: null, note: "User upload (references/players_images); unscaled close-up of the loose figure. Stills: references/derived/players." });
  g.source_images.push({ source_id: m.id, local_path: m.local_path, sha256: m.sha256, width_px: m.native_width_px, height_px: m.native_height_px });
}
const pack = index.sources.find((s) => s.id === PACK)!;
g.sources.push({ id: PACK, kind: "reference_image", title: pack.title, index_id: PACK, url: null, note: "Blister card, all six Finland figures side by side at one depth: five identical skaters and the goalie, equally tall." });
g.source_images.push({ source_id: PACK, local_path: pack.local_path, sha256: pack.sha256, width_px: pack.native_width_px, height_px: pack.native_height_px });
g.sources.push({ id: STATEMENT, kind: "user_statement", title: "User statement of 2026-09-30 on the figures",
  note: "'Every player is identical, except the goalkeeper. The only difference between sweden and finland is the kit color and the country name on the back.' Photos/videos of the Sweden goalie and skater uploaded to references/players_images." });
const photoIds = MEDIA.map((m) => m.id);
const skaterMedia = photoIds.filter((i) => i.startsWith("user_skater_"));
const goalieMedia = photoIds.filter((i) => i.startsWith("user_goalie_"));

// ---- Assumptions --------------------------------------------------------------------------------------
const SCALE = "assume.figure_mold_scale";
const HIDDEN = "assume.figure_mold_hidden_details";
g.assumptions = g.assumptions.filter((a) => !a.id.startsWith("assume.debug_contacts.") && a.id !== SCALE && a.id !== HIDDEN);
const assumptions: Assumption[] = [
  { id: SCALE, statement: `One scale k = ${K} mm per mold unit for BOTH molds: fitted to four Sweden skaters on the official overhead (validation/players/overhead-fit.json) at the preview scale. The goalie alone fits best at k = ${over.goalie_only_best_scale_k} (hand-traced white goalie on white ice); the Finland team pack shows goalie and skaters equally tall, so the skater k is used.`,
    reason: "The user's photos have no scale object near the figure; the overhead is the only scaled view (itself at the ASSUMED preview scale).",
    affects: g.figure_assets.map((a) => `figure_assets.${a.id}`), replace_with: "Ruler measurements of one skater and the goalie: height (ice to helmet top), socket base diameter, blade length and heel offset from the socket axis." },
  { id: HIDDEN, statement: "Hidden or unresolved mold details are assumed: socket bore (3 x 2 x 3 mold units), blade and runner thickness (0.9 mold units skater, 2.4 goalie blade), stick wire radius (0.75), print fonts.",
    reason: "Not visible or not resolvable in the user's photos/videos.", affects: ["data/figure-molds.json"], replace_with: "Close-up measurements or scaled macro photos of the socket bore, blade and stick." },
];
g.assumptions.push(...assumptions);

// ---- Contacts from the molds ---------------------------------------------------------------------------
const s3 = (p: number[], z?: number): V3 => [round(p[0]! * K), round(p[1]! * K), round((z ?? p[2] ?? 0) * K)];
const ring = (r: number, n = 16): V3[] => Array.from({ length: n + 1 }, (_, i) => [round(r * K * Math.cos((2 * Math.PI * i) / n)), round(r * K * Math.sin((2 * Math.PI * i) / n)), 0]);
function contacts(pid: string, kind: "skater" | "goalie"): ContactShape[] {
  const m = molds[kind];
  const src = kind === "skater" ? [...skaterMedia, OVER] : [...goalieMedia, OVER, PACK];
  const c = (id: string, k: ContactShape["kind"], pts: V3[], unc: number, note: string): ContactShape =>
    ({ id: `contact.${pid}.${id}`, kind: k, frame: "pivot_local", geometry: { type: "polyline", points_mm: pts }, status: "traced", source_ids: src, uncertainty_mm: unc, note });
  const [h, t] = m.stick.blade as [number[], number[]];
  const bh = m.stick.blade_h as number;
  const blade = c("blade", "blade", [s3(h, 0), s3(t, 0), s3(t, bh), s3(h, bh), s3(h, 0)], 2.5,
    `Blade: upright plate on the ice from heel to toe (${kind === "skater" ? "flattened metal wire" : "tan plastic"}), outline of the fitted mold x k. Overhead check (skaters): heel ~21.9 mm left of the axis, blade ~20.2 mm long (4 figures).`);
  const base = c("base", "base", ring(m.socket.r_bottom), 1.5, "Mount socket: flared base ring on the ice, centred on the fixture axis (bore opens downward, rectangular key).");
  if (kind === "skater") {
    return [blade, c("stick_shaft", "stick_shaft", (m.stick.shaft as number[][]).map((p) => s3(p)), 2.5, "Round wire shaft through both gloves to the heel."), base,
      c("skate.right", "skate", [s3(m.runner.a, 0), s3(m.runner.b, 0)], 3, "Right (pushing) skate runner on the ice, behind and right of the axis. The left skate stands on the mount socket.")];
  }
  const pad = (n: string) => { const b = m.boxes[n]; const [cx, cy] = b.centre; const [hx, hy] = b.half_size; return [s3([cx - hx, cy - hy], 0), s3([cx + hx, cy - hy], 0), s3([cx + hx, cy + hy], 0), s3([cx - hx, cy + hy], 0), s3([cx - hx, cy - hy], 0)]; };
  return [blade, c("stick_shaft", "stick_shaft", (m.stick.paddle as number[][]).map((p) => s3(p)), 2.5, "Flat tan paddle from the blocker down to the heel."), base,
    c("pad.left", "pad", pad("pad_l"), 3, "Left leg-pad bottom on the ice."), c("pad.right", "pad", pad("pad_r"), 3, "Right leg-pad bottom (over the socket side).")];
}

// ---- Figure assets ----------------------------------------------------------------------------------------
const q = (value: number | null, status: Quantity["status"], unc: number | null, src: string[], note: string, assumption_id?: string): Quantity =>
  ({ value, unit: "mm", status, uncertainty: value === null ? null : unc, source_ids: value === null ? [] : src, ...(assumption_id ? { assumption_id } : {}), note });
for (const a of g.figure_assets) {
  const pid = a.id.replace("fig.", "");
  const kind = a.kind;
  const team = pid.startsWith("W") ? "FIN" : "SWE";
  const r = rep.assets[`${kind}_${team}`];
  const src = kind === "skater" ? [...skaterMedia, OVER, STATEMENT] : [...goalieMedia, OVER, PACK, STATEMENT];
  const heel = r.blade_heel_mm as number[];
  a.mold_group = `mold.${kind}`;
  a.figure_height = kind === "skater"
    ? q(r.height_mm, "traced", 2.5, src, `Ice (socket underside) to helmet top of the fitted mold at k = ${K}. The catalog 'figure height approx. 57 mm' (datum unspecified) is ${round(57 - r.height_mm, 1)} mm higher; not resolved (preview scale is assumed).`)
    : q(r.height_mm, "assumed", 3, src, `Ice to mask top at the shared mold scale; the goalie-only overhead fit (k = ${over.goalie_only_best_scale_k}) would give ${round((r.height_mm * over.goalie_only_best_scale_k) / K, 1)} mm.`, SCALE);
  a.blade_offset_from_pivot = kind === "skater"
    ? q(round(Math.hypot(heel[0]!, heel[1]!)), "traced", 2, [OVER, ...skaterMedia], `Horizontal distance from the fixture axis to the blade heel (inner end); the blade runs ${r.blade_length_mm} mm further toward the figure's left. Overhead: heel 21.1-22.8 mm lateral on four figures.`)
    : q(round(Math.hypot(heel[0]!, heel[1]!)), "assumed", 3, [...goalieMedia, OVER], `Axis to blade heel at the shared mold scale; the goalie blade runs ${r.blade_length_mm} mm across the front toward the goalie's left.`, SCALE);
  a.ice_clearance = q(null, "unknown", null, [], "The socket base is drawn resting on the ice; whether the figure rides on the spindle above the ice is not visible in any view.");
  a.contact_shapes = contacts(pid, kind);
  const inv: InventoryItem[] = [
    { item: "mold identity", status: "traced", evidence: kind === "skater" ? "User statement: every skater is identical. Supported: all ten skaters in the official overhead show the same top-view pose; the Finland team pack shows five identical skaters." : "One goalie mold per team (user statement; Finland team pack; official overhead)." },
    { item: "mounting (fixture) axis position", status: "traced", evidence: kind === "skater" ? "User photos/videos: a flared cylindrical socket with a rectangular key bore under the LEFT skate (the stick side) is the mount; the figure turns about its axis." : "User photos: a flared socket with a rectangular key bore under the goalie's RIGHT skate; the left leg ends in a pad block." },
    { item: "stick and blade", status: "traced", evidence: kind === "skater" ? "Metal wire stick through both gloves (left shot), flattened blade on the ice toward the figure's left; overhead: heel ~21.9 mm left of the axis, blade ~20.2 mm (4 figures, preview scale)." : "Tan plastic stick: paddle from the blocker (right hand) to a heel between the pads; blade across the front toward the goalie's left, longer than the body is wide." },
    { item: "skates", status: "traced", evidence: kind === "skater" ? "Left boot on the mount socket; right boot pushed back and out with a metal runner on the ice." : "Blue boots under yellow/white socks; right boot on the socket." },
    { item: "uniform", status: "traced", evidence: `Kit colour (${team === "SWE" ? "Sweden yellow" : "Finland white"}) on jersey and socks; shared blue helmet, gloves, pants, boots${kind === "goalie" ? ", pads, blocker, catcher, mask" : ""}; skin face; back print country name + number (data/figure-molds.json prints).` },
    { item: "shape", status: "traced", evidence: `Camera-matched silhouette fit to the user's ${kind === "skater" ? "turntable video frames" : "photos and video frames"}: mean IoU ${fits[kind].mean_iou} (${Object.keys(fits[kind].views).length} views); overhead top-view IoU ${over.figures[kind === "skater" ? "E-LD" : "W-G"]?.iou ?? "n/a"}.` },
    { item: "absolute scale", status: kind === "skater" ? "traced" : "assumed", evidence: `k = ${K} mm per mold unit from the official overhead at the ASSUMED preview scale; ${kind === "goalie" ? "shared with the skater mold (goalie-only fit: " + over.goalie_only_best_scale_k + ")" : "no ruler measurement"}.` },
  ];
  a.inventory = inv;
  a.note = `Rigid ${kind} mold (data/figure-molds.json) in the ${team === "SWE" ? "Sweden" : "Finland"} kit: assets/figures/${kind}_${team}.glb. One rigid mesh, origin on the fixture axis at the socket underside, +x facing, +y the figure's left.`;
}
for (const pl of g.players) {
  pl.stick_handedness = "left";
  pl.handedness_source_ids = pl.position === "G" ? [...goalieMedia, OVER] : [...skaterMedia, OVER];
}
// Proxy-only build sizes of iterations 13-15, superseded by the mold data.
for (const k of ["blade_thickness", "stick_shaft_radius", "skate_width", "skate_height", "goalie_height"]) delete (g.preview_parameters as Record<string, unknown>)[k];
writeFileSync("data/geometry.json", JSON.stringify(g, null, 2) + "\n");
console.log(JSON.stringify({ k: K, assets: g.figure_assets.map((a) => [a.id, a.mold_group, a.figure_height.value, a.blade_offset_from_pivot.value]) }));
