// Iteration 10: contact inventory and PROVISIONAL debug contact geometry for one representative skater
// (W-RD, Finland no. 4). Real contact quantities stay unknown; the provisional shapes are derived from
// operator-read pixel evidence in the overhead through the ASSUMED preview scale (docs/contacts.md).
import { readFileSync, writeFileSync } from "node:fs";
import type { ContactShape, GeometryFile, InventoryItem } from "../src/model/geometry.ts";

const PLAYER = "W-RD";
const ASSET = `fig.${PLAYER}`;
const OVER = "stiga_se_fi_overhead";
const ASSUMPTION = `assume.debug_contacts.${PLAYER}`;

// ---- Operator-read evidence (overhead px; zoomed crops in docs/contacts.md) ----------------------
const EVIDENCE = {
  /** Body axis from the back of the shoulders to the helmet (figure faces +x). */
  back: [2330, 3330] as [number, number],
  helmet: [2440, 3330] as [number, number],
  /** Stick shaft seen from above: from the hands to the tip. */
  hands: [2400, 3250] as [number, number],
  tip: [2393, 3050] as [number, number],
  readUncertaintyPx: 5,
};
// Debug-only dimensions (mm): no measurement exists for any of them.
const DEBUG = { bladeFraction: 0.3, bladeHeight: 4, handsHeight: 20, skateHalfLength: 6, skateGauge: 5, skateHeight: 3 };
// --------------------------------------------------------------------------------------------------

const round = (v: number, d = 2): number => Math.round(v * 10 ** d) / 10 ** d;
const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const map = g.image_to_world.find((m) => m.id === "map.overhead.preview")!;
const toWorld = ([u, v]: [number, number]): [number, number] => [map.matrix[0] * u + map.matrix[1] * v + map.matrix[2], map.matrix[3] * u + map.matrix[4] * v + map.matrix[5]];
const mmPerPx = Math.hypot(map.matrix[0], map.matrix[3]);

// Pivot: the fixture axis lies somewhere on the covered stretch of the W-RD slot (hidden under the
// figure, between the last visible cross-section and the visible end cap). Debug choice: its midpoint.
const trace = g.image_traces.find((t) => t.id === `trace.slot.${PLAYER}.overhead`)!;
const covered = trace.inferred_segments.filter((s) => s.to < trace.points_px.length - 1).sort((a, b) => b.to - b.from - (a.to - a.from))[0]!;
const cStart = trace.points_px[Math.max(0, covered.from - 1)]!;
const cEnd = trace.points_px[trace.points_px.length - 1]!; // visible end cap beyond the figure
const pivotPx: [number, number] = [(cStart[0] + cEnd[0]) / 2, (cStart[1] + cEnd[1]) / 2];
const halfStretchPx = Math.hypot(cEnd[0] - cStart[0], cEnd[1] - cStart[1]) / 2;
const pivotW = toWorld(pivotPx);
const hb = toWorld(EVIDENCE.back), hh = toWorld(EVIDENCE.helmet);
const headingDeg = (Math.atan2(hh[1] - hb[1], hh[0] - hb[0]) * 180) / Math.PI;
const toLocal = (px: [number, number], z: number): [number, number, number] => {
  const w = toWorld(px);
  const dx = w[0] - pivotW[0], dy = w[1] - pivotW[1];
  const r = (-headingDeg * Math.PI) / 180;
  return [round(dx * Math.cos(r) - dy * Math.sin(r)), round(dx * Math.sin(r) + dy * Math.cos(r)), z];
};
const hands = toLocal(EVIDENCE.hands, DEBUG.handsHeight);
const tip = toLocal(EVIDENCE.tip, 0);
const bladeStart: [number, number, number] = [
  round(hands[0] + (1 - DEBUG.bladeFraction) * (tip[0] - hands[0])),
  round(hands[1] + (1 - DEBUG.bladeFraction) * (tip[1] - hands[1])),
  0,
];
const unc = round(halfStretchPx * mmPerPx + EVIDENCE.readUncertaintyPx * mmPerPx, 1);
const src = [OVER, "stiga_canada_catalog"];
const shape = (id: string, kind: ContactShape["kind"], pts: [number, number, number][], note: string, u: number | null = unc): ContactShape =>
  ({ id, kind, frame: "pivot_local", geometry: { type: "polyline", points_mm: pts }, status: "assumed", source_ids: src, uncertainty_mm: u, provisional: true, assumption_id: ASSUMPTION, note });
const shapes: ContactShape[] = [
  shape(`contact.${PLAYER}.blade`, "blade", [
    [bladeStart[0], bladeStart[1], 0], [tip[0], tip[1], 0], [tip[0], tip[1], DEBUG.bladeHeight], [bladeStart[0], bladeStart[1], DEBUG.bladeHeight], [bladeStart[0], bladeStart[1], 0],
  ], `DEBUG blade: vertical strip along the last ${DEBUG.bladeFraction * 100}% of the stick's top-view projection, from the ice (z 0) to ${DEBUG.bladeHeight} mm (assumed). Real outline, offset, lie and height unknown.`),
  shape(`contact.${PLAYER}.stick_shaft`, "stick_shaft", [[bladeStart[0], bladeStart[1], 0], hands],
    `DEBUG shaft: top-view projection from the hands to the blade; rises linearly to ${DEBUG.handsHeight} mm at the hands (assumed).`),
  ...([1, -1] as const).map((side) => shape(`contact.${PLAYER}.skate.${side > 0 ? "left" : "right"}`, "skate", [
    [-DEBUG.skateHalfLength, side * DEBUG.skateGauge, 0], [DEBUG.skateHalfLength, side * DEBUG.skateGauge, 0],
  ], `DEBUG placeholder: skates are hidden under the body in the top view and unscaled in the side views; placed ${DEBUG.skateGauge} mm either side of the axis at ice level. Real position and ice clearance unknown.`, 10)),
];

const inventory: InventoryItem[] = [
  { item: "mounting (fixture) axis position", status: "unknown", evidence: `Hidden under the figure. Constrained to the covered stretch of the W-RD slot between px (${cStart.map((v) => round(v, 0)).join(", ")}) and the visible end cap (${cEnd.map((v) => round(v, 0)).join(", ")}): +-${round(halfStretchPx * mmPerPx, 1)} mm along the slot at the preview scale. Lateral offset from the slot centreline unknown.` },
  { item: "blade outline", status: "unknown", evidence: "The overhead shows only the stick's top-view projection; no loose-figure or scaled blade view exists." },
  { item: "blade offset from pivot", status: "unknown", evidence: `Debug estimate only: blade tip about ${round(Math.hypot(tip[0], tip[1]), 1)} mm from the assumed pivot, on the figure's left (preview scale, assumed pivot).` },
  { item: "stick side (handedness)", status: "traced", evidence: "Overhead: figure faces +x and the stick extends toward +y, i.e. the blade is on the figure's LEFT." },
  { item: "feet / skates", status: "unknown", evidence: "Hidden under the body in the top view; visible but unscaled and unidentifiable per figure in the side views." },
  { item: "contact heights (blade, skates, ice clearance)", status: "unknown", evidence: "No scaled side view of a loose or installed figure." },
  { item: "figure height", status: "catalog_nominal", evidence: "Approx. 57 mm (STIGA Canada), height datum unspecified." },
  { item: "mold shared with other skaters", status: "unknown", evidence: "Side and oblique photos show Finland skaters with clearly different molded poses (deep crouch, low stickhandling, skating stride); jersey numbers are not consistent across photos. W-RD's mold is NOT shown to be shared; other positions need their own variants." },
  { item: "body shape (torso, arms, legs, head)", status: "assumed", evidence: "Iteration 14 proxy (assets/figures/skater_W-RD.*): matched to the traced top silhouette (trace.figure.W-RD.overhead.top_silhouette, IoU 0.82) and catalog height; front, back and side views have no W-RD evidence." },
  { item: "skate position vs top silhouette", status: "unknown", evidence: "CONFLICT: the top silhouette shows a right-leg lobe reaching y about -24 mm (pivot-local), while the debug skate placeholders sit at +-5 mm. Contacts left unchanged pending measurement." },
];

g.assumptions = g.assumptions.filter((a) => a.id !== ASSUMPTION);
g.assumptions.push({
  id: ASSUMPTION,
  statement: `Debug contact geometry for ${PLAYER}: pivot at the midpoint of the covered slot stretch; heading ${round(headingDeg, 1)} deg from the body axis; blade = last ${DEBUG.bladeFraction * 100}% of the stick's top-view projection, ${DEBUG.bladeHeight} mm high from the ice; shaft rising to ${DEBUG.handsHeight} mm at the hands; skate placeholders ${DEBUG.skateGauge} mm either side of the axis; preview scale.`,
  reason: "No loose-figure views or measurements exist; a labelled stand-in is needed to exercise the pose and contact code.",
  affects: [`figure_assets.${ASSET}.contact_shapes`],
  replace_with: "Scaled photographs or measurements of the loose and installed figure: fixture axis, blade outline and offset, skate contacts, ice clearance (docs/contacts.md).",
});
const asset = g.figure_assets.find((a) => a.id === ASSET)!;
asset.contact_shapes = shapes;
asset.inventory = inventory;
asset.note = `Representative skater for iterations 10 and 13-14. Chosen because its slot is visible on BOTH sides of the figure in the overhead, which confines the hidden fixture axis to a short stretch (+-${round(halfStretchPx * mmPerPx, 1)} mm). Contact shapes are PROVISIONAL DEBUG GEOMETRY (${ASSUMPTION}); blade_offset_from_pivot and ice_clearance remain unknown.`;
asset.blade_offset_from_pivot = { value: null, unit: "mm", status: "unknown", uncertainty: null, source_ids: [], note: "Not measured. See the provisional debug blade in contact_shapes." };
asset.ice_clearance = { value: null, unit: "mm", status: "unknown", uncertainty: null, source_ids: [], note: "Not measured." };
const player = g.players.find((p) => p.id === PLAYER)!;
player.stick_handedness = "left";
player.handedness_source_ids = [OVER];
writeFileSync("data/geometry.json", JSON.stringify(g, null, 2) + "\n");
const report = { player: PLAYER, pivot_px: pivotPx.map((v) => round(v)), pivot_along_slot_uncertainty_mm: round(halfStretchPx * mmPerPx, 2), heading_deg: round(headingDeg, 2), mm_per_px_assumed: round(mmPerPx, 6), hands_local_mm: hands, tip_local_mm: tip, blade_start_local_mm: bladeStart, contact_uncertainty_mm: unc };
writeFileSync("validation/10-contacts-report.json", JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report));
