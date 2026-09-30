// Static poses for all 12 figures from the pure pose functions (iteration 16; figure molds 2026-09-30).
// Each figure stands where it stands in the official overhead: where the mold fit on the overhead exists
// (validation/players/overhead-fit.json: socket on the slot centreline, heading fitted) its pivot and
// heading are used; otherwise the iteration-16 rule (midpoint of the hidden slot stretch), theta 0.
import { readFileSync, writeFileSync } from "node:fs";
import type { GeometryFile } from "../src/model/geometry.ts";
import { loadFigurePaths } from "../src/model/paths.ts";
import { goaliePose, linearDeterminant, skaterPose, type Pose } from "../src/model/pose.ts";

type EndCheck = { pid: string; end: string; observed: [number, number]; predicted: [number, number]; occluder: string | null };
const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const slots = JSON.parse(readFileSync("validation/slots-report.json", "utf8")) as { end_checks: EndCheck[] };
const fit = JSON.parse(readFileSync("validation/players/overhead-fit.json", "utf8")) as { figures: Record<string, { pivot_mm: [number, number]; heading_deg: number }> };
const map = g.image_to_world.find((m) => m.id === "map.overhead.preview")!.matrix;
const toW = ([u, v]: [number, number]): [number, number] => [map[0] * u + map[1] * v + map[2], map[3] * u + map[4] * v + map[5]];
const det = map[0] * map[4] - map[1] * map[3];
const toPx = ([x, y]: [number, number]): [number, number] => {
  const dx = x - map[2], dy = y - map[5];
  return [(map[4] * dx - map[1] * dy) / det, (-map[3] * dx + map[0] * dy) / det];
};
/** Team kit of the reference variant (decision D4): W = Finland, E = Sweden. */
const KIT = { W: "FIN", E: "SWE" } as const;
const round = (v: number, d = 3): number => Math.round(v * 10 ** d) / 10 ** d;

/** Where the figure stands in the reference overhead (image px) and why. */
function referencePoint(pid: string): { px: [number, number]; rule: string; headingDeg?: number } {
  const f = fit.figures[pid];
  if (f) return { px: toPx(f.pivot_mm), rule: "figure-mold fit on the official overhead (socket on the slot centreline, heading fitted)", headingDeg: f.heading_deg };
  const e = slots.end_checks.find((x) => x.pid === `path.${pid}` && x.occluder);
  if (e) return { px: [(e.observed[0] + e.predicted[0]) / 2, (e.observed[1] + e.predicted[1]) / 2], rule: `midpoint of the ${e.end} stretch hidden by the ${e.occluder} (same rule)` };
  if (pid === "E-LW") return { px: [697.2, 2610], rule: "figure no. 92 stands beside the visible start end; point 20 px along the slot from it" };
  throw new Error(`no reference point for ${pid}`);
}

const paths = loadFigurePaths(g);
const out = paths.map((fp) => {
  const pl = g.players.find((p) => p.id === fp.playerId)!;
  const ref = referencePoint(fp.playerId);
  const w = toW(ref.px);
  let best = { u: 0, d: Infinity };
  for (let k = 0; k <= 20000; k++) {
    const u = k / 20000;
    const q = fp.sampler.at(u * fp.sampler.length).point;
    const d = Math.hypot(q[0] - w[0], q[1] - w[1]);
    if (d < best.d) best = { u, d };
  }
  const home = fp.team === "W" ? 0 : 180;
  const theta = ref.headingDeg === undefined ? 0 : ((((ref.headingDeg - home) % 360) + 540) % 360) - 180;
  const state = { u_preview: round(best.u, 5), thetaDeg: round(theta, 2) };
  const r = pl.position === "G" ? goaliePose(fp.sampler, fp.team, state) : skaterPose(fp.sampler, fp.team, state);
  if (!r.ok) throw new Error(`${fp.playerId}: ${r.reason}`);
  const p: Pose = r;
  const kind = pl.position === "G" ? "goalie" : "skater";
  const kit = KIT[pl.team_id];
  return {
    player_id: pl.id, team: pl.team_id, position: pl.position, path_id: fp.sampler.id, asset_id: pl.asset_id,
    asset: `assets/figures/${kind}_${kit}.blend#${kind === "goalie" ? "Goalie" : "Skater"}.${kit}`, kit,
    state, reference_px: ref.px.map((v) => round(v, 1)), reference_rule: ref.rule, reference_to_path_mm: round(best.d, 2),
    pivot_mm: p.pivot.map((v) => round(v)), heading_deg: p.headingDeg, det: round(linearDeterminant(p.matrix), 9), matrix: p.matrix.map((v) => round(v, 9)), assumptions: p.assumptions,
  };
});
writeFileSync("validation/16-assembly-poses.json", JSON.stringify({ note: "Static pose: each figure where it stands in the official overhead (mold fit where available, else the hidden-stretch rule at theta 0). Not a measured or control-derived pose.", figures: out }, null, 2) + "\n");
console.log(out.map((o) => `${o.player_id} u=${o.state.u_preview} d=${o.reference_to_path_mm}mm ${o.asset}`).join("\n"));
