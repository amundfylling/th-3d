// Iteration 15: evidence inventory, traced top silhouette and PROVISIONAL debug contacts for the goalie
// W-G (Finland). Its own geometry: nothing is derived from the skater. Real values stay unknown.
import { readFileSync, writeFileSync } from "node:fs";
import type { ContactShape, GeometryFile, ImageTrace, InventoryItem, PixelPoint } from "../src/model/geometry.ts";

const PLAYER = "W-G";
const ASSET = `fig.${PLAYER}`;
const OVER = "stiga_se_fi_overhead";
const ASSUMPTION = `assume.debug_contacts.${PLAYER}`;
const round = (v: number, d = 2): number => Math.round(v * 10 ** d) / 10 ** d;

// ---- Operator traces (3x contrast-enhanced crop, 10 px grid; docs/figures.md) --------------------
const BODY_PX: PixelPoint[] = [[1340, 2842], [1348, 2825], [1360, 2815], [1378, 2812], [1390, 2818], [1392, 2835], [1388, 2852], [1400, 2862], [1415, 2870], [1417, 2900], [1416, 2950], [1430, 2952], [1432, 2975], [1420, 2995], [1410, 3020], [1408, 3040], [1400, 3045], [1395, 3030], [1380, 3020], [1365, 3025], [1345, 3025], [1320, 3018], [1302, 3000], [1293, 2975], [1291, 2940], [1293, 2905], [1300, 2875], [1318, 2855]];
const STICK_PX: PixelPoint[] = [[1421, 2763], [1438, 2763], [1438, 2950], [1421, 2950]];
const DEBUG = { stickBladeHeight: 5, gloveHeight: 18, padHalfLength: 6 };
/** Pad ice-contact centres (pivot-local mm), read from the traced pad lobes of the top silhouette. */
const PAD_CENTRES: Record<"left" | "right", [number, number]> = { left: [-8, -2], right: [-1, -24] };
/** Stick glove (blocker hand) position (pivot-local mm): the blue arm lobe beside the paddle at px (1402, 2905). */
const STICK_HAND: [number, number, number] = [-0.5, -7.5, DEBUG.stickBladeHeight + 13];
// --------------------------------------------------------------------------------------------------

const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const map = g.image_to_world.find((m) => m.id === "map.overhead.preview")!;
const toW = ([u, v]: [number, number]): [number, number] => [map.matrix[0] * u + map.matrix[1] * v + map.matrix[2], map.matrix[3] * u + map.matrix[4] * v + map.matrix[5]];
const mmPerPx = Math.hypot(map.matrix[0], map.matrix[3]);
// Pivot: same rule as W-RD - midpoint of the covered slot stretch (last visible section -> bare-predicted end).
const slots = JSON.parse(readFileSync("validation/slots-report.json", "utf8")) as { end_checks: { pid: string; end: string; observed: [number, number]; predicted: [number, number] }[] };
const ec = slots.end_checks.find((e) => e.pid === "path.W-G" && e.end === "end")!;
const pivotPx: [number, number] = [(ec.observed[0] + ec.predicted[0]) / 2, (ec.observed[1] + ec.predicted[1]) / 2];
const halfPx = Math.hypot(ec.predicted[0] - ec.observed[0], ec.predicted[1] - ec.observed[1]) / 2;
const pv = toW(pivotPx);
const local = (p: [number, number], z: number): [number, number, number] => { const w = toW(p); return [round(w[0] - pv[0]), round(w[1] - pv[1]), z]; }; // heading 0 (faces +x)
const stickMidX = (STICK_PX[0]![0] + STICK_PX[1]![0]) / 2;
const bladeA = local([stickMidX, STICK_PX[0]![1]], 0), bladeB = local([stickMidX, STICK_PX[2]![1]], 0);
const unc = round((halfPx + 5) * mmPerPx, 1);
const src = [OVER, "stiga_se_fi_side_a"];
const shape = (id: string, kind: ContactShape["kind"], pts: [number, number, number][], note: string): ContactShape =>
  ({ id, kind, frame: "pivot_local", geometry: { type: "polyline", points_mm: pts }, status: "assumed", source_ids: src, uncertainty_mm: unc, provisional: true, assumption_id: ASSUMPTION, note });
const shapes: ContactShape[] = [
  shape(`contact.${PLAYER}.stick_blade`, "blade", [bladeA, bladeB, [bladeB[0], bladeB[1], DEBUG.stickBladeHeight], [bladeA[0], bladeA[1], DEBUG.stickBladeHeight], bladeA],
    `DEBUG goalie stick blade: vertical plate standing on edge across the front (overhead: narrow tan strip along y), ice to ${DEBUG.stickBladeHeight} mm (side A: wide paddle; height assumed).`),
  shape(`contact.${PLAYER}.stick_shaft`, "stick_shaft", [[bladeA[0], STICK_HAND[1], DEBUG.stickBladeHeight], STICK_HAND],
    `DEBUG shaft from the blade top up to the blocker hand at ${STICK_HAND[2]} mm (assumed).`),
  ...(["left", "right"] as const).map((side) => {
    const [cx, cy] = PAD_CENTRES[side];
    return shape(`contact.${PLAYER}.pad.${side}`, "pad", [[cx - DEBUG.padHalfLength, cy, 0], [cx + DEBUG.padHalfLength, cy, 0]],
      `DEBUG ${side} leg-pad ice contact, under the traced pad lobe of the top silhouette. Real contact unknown.`);
  }),
];
const trace: ImageTrace = {
  id: `trace.figure.${PLAYER}.overhead.top_silhouette`, source_image_id: OVER, feature: "figure_top_silhouette_elevated", closed: true, points_px: BODY_PX,
  landmark_ids: [], status: "traced", uncertainty_px: 5,
  method: "Operator trace on a 3x contrast-enhanced crop with a 10 px grid (white jersey vs yellow print). Body only; the stick is traced separately.",
  inferred_segments: [], note: "Top-view silhouette of the Finland goalie (W-G). ELEVATED body, near-orthographic view. 'FINLAND' on the back faces -x: the goalie faces +x.",
};
const stickTrace: ImageTrace = { ...trace, id: `trace.figure.${PLAYER}.overhead.stick`, feature: "goalie_stick_top_elevated", points_px: STICK_PX, method: "Operator trace of the tan stick strip (same crop).", note: "Goalie stick seen from above: a narrow strip along y in front of the body = a paddle/blade standing on edge across the front." };
g.image_traces = [...g.image_traces.filter((t) => !t.id.startsWith(`trace.figure.${PLAYER}.`)), trace, stickTrace].sort((a, b) => a.id.localeCompare(b.id));

const inventory: InventoryItem[] = [
  { item: "identity", status: "traced", evidence: "Only one Finland goalie exists, so the overhead (top), side A (profile, crop at px 1150-1450) and oblique A (crop at px 3520-3870) all show W-G." },
  { item: "mounting (fixture) axis position", status: "unknown", evidence: `Hidden under the goalie; confined to the covered W-G slot stretch (+-${round(halfPx * mmPerPx, 1)} mm at the preview scale). Debug pivot at its midpoint.` },
  { item: "stick side", status: "traced", evidence: `Overhead: the stick stands across the front, from local y ${bladeB[1]} to ${bladeA[1]} mm, i.e. mostly toward the goalie's LEFT (+y).` },
  { item: "stick blade outline and height", status: "unknown", evidence: "Side A shows a wide tan L-shaped stick with the blade on the ice; unscaled." },
  { item: "pads / skates ice contact", status: "unknown", evidence: "Pads reach the ice in side A; exact contact unknown." },
  { item: "goalie height", status: "assumed", evidence: "Side A: goalie about 243 px vs about 260 px for a skater in the same photo (depths differ) -> about 0.93 x 57 mm = 53 mm; see preview_parameters.goalie_height." },
  { item: "body shape", status: "assumed", evidence: "Iteration 15 proxy matched to the traced top silhouette; profile from side A (crouched, large pads, blocker and catcher)." },
];
g.assumptions = g.assumptions.filter((a) => a.id !== ASSUMPTION);
g.assumptions.push({
  id: ASSUMPTION,
  statement: `Debug goalie contacts for ${PLAYER}: pivot at the midpoint of the covered W-G slot stretch, heading 0 deg; stick blade = vertical plate along the traced tan strip, ice to ${DEBUG.stickBladeHeight} mm; shaft to the blocker hand at ${STICK_HAND.join(", ")} mm; pad contacts under the traced pad lobes at ${JSON.stringify(PAD_CENTRES)}; preview scale.`,
  reason: "No loose-goalie views or measurements; a labelled stand-in is needed to exercise the goalie pose adapter and build the asset.",
  affects: [`figure_assets.${ASSET}.contact_shapes`],
  replace_with: "Scaled photographs or measurements of the loose and installed goalie (fixture axis, stick outline, pad contacts, ice clearance).",
});
g.preview_parameters!.goalie_height = { value: 53, unit: "mm", status: "assumed", uncertainty: null, source_ids: ["stiga_se_fi_side_a", "stiga_canada_catalog"], assumption_id: ASSUMPTION, note: "Side A: goalie about 243 px vs a skater about 260 px (different depths, perspective uncorrected) x catalog approx. 57 mm. The catalog figure height is NOT stated to apply to the goalie." };
const asset = g.figure_assets.find((a) => a.id === ASSET)!;
asset.contact_shapes = shapes;
asset.inventory = inventory;
asset.note = `Goalie asset (iteration 15): its own body, stick and origin; not a resized skater. Contacts are PROVISIONAL DEBUG GEOMETRY (${ASSUMPTION}); figure_height, blade offset and ice clearance remain unknown.`;
const player = g.players.find((p) => p.id === PLAYER)!;
player.stick_handedness = "left";
player.handedness_source_ids = [OVER];
writeFileSync("data/geometry.json", JSON.stringify(g, null, 2) + "\n");
const report = { player: PLAYER, pivot_px: pivotPx.map((v) => round(v)), pivot_along_slot_uncertainty_mm: round(halfPx * mmPerPx, 2), heading_deg: 0, mm_per_px_assumed: round(mmPerPx, 6), stick_blade_local_mm: [bladeA, bladeB], contact_uncertainty_mm: unc };
writeFileSync("validation/15-goalie-contacts-report.json", JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report));
