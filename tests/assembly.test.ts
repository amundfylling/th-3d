// Iteration 16: full static assembly driven by the pose functions and canonical IDs.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { readGlbJson } from "./rink-asset.test.ts";

const poses = JSON.parse(readFileSync("validation/16-assembly-poses.json", "utf8")).figures as any[];
const rep = JSON.parse(readFileSync("validation/16-assembly-report.json", "utf8"));

test("12 figures: 10 skaters + 2 goalies, each on its own path with its own asset id", () => {
  assert.equal(poses.length, 12);
  assert.equal(poses.filter((p) => p.position === "G").length, 2);
  for (const p of poses) {
    assert.equal(p.path_id, `path.${p.player_id}`);
    assert.equal(p.asset_id, `fig.${p.player_id}`);
    assert.ok(p.reference_to_path_mm < 1, `${p.player_id} reference point ${p.reference_to_path_mm} mm from its path`);
    assert.ok(Math.abs(p.det - 1) < 1e-9, "proper rotation");
    const home = p.team === "W" ? 0 : 180;
    const d = (((p.heading_deg - home - p.state.thetaDeg) % 360) + 540) % 360 - 180;
    assert.ok(Math.abs(d) < 1e-6, `${p.player_id}: heading = home + theta`);
  }
});

test("every figure uses the shared mold of its kind in its team's kit; no placeholders remain", () => {
  assert.equal(rep.modelled.length, 12);
  assert.deepEqual(rep.placeholders, []);
  for (const p of poses) {
    const kind = p.position === "G" ? "goalie" : "skater";
    const kit = p.team === "W" ? "FIN" : "SWE";
    assert.equal(p.asset, `assets/figures/${kind}_${kit}.blend#${kind === "goalie" ? "Goalie" : "Skater"}.${kit}`);
  }
  const fitted = poses.filter((p) => /mold fit on the official overhead/.test(p.reference_rule)).map((p) => p.player_id).sort();
  assert.deepEqual(fitted, ["E-C", "E-LD", "E-LW", "E-RD", "W-G", "W-RD"]);
  const gltf = readGlbJson("assets/scene/full_static.glb");
  const prints = gltf.nodes.filter((n: any) => /^Print\./.test(n.name));
  assert.equal(prints.length, 12, "one back print per figure");
});

test("assembly checks: no intersections, nothing below the ice, vertical axes, metres in GLB", () => {
  assert.equal(rep.pass, true);
  assert.deepEqual(rep.intersections, []);
  assert.equal(rep.mounting_axes_vertical, true);
  const gltf = readGlbJson("assets/scene/full_static.glb");
  const figs = gltf.nodes.filter((n: any) => /^Figure\./.test(n.name));
  assert.equal(figs.length, 12);
  const ice = gltf.nodes.find((n: any) => n.name === "Ice");
  const acc = gltf.accessors[gltf.meshes[ice.mesh].primitives[0].attributes.POSITION];
  assert.ok(Math.abs(acc.max[0] - acc.min[0] - 0.8454) < 0.001, "ice length in metres");
});

test("iteration 20 reprojection: pipeline consistent to ~2 output px (slots) and ~1 px (ice edge median)", () => {
  const r = JSON.parse(readFileSync("validation/20-reprojection.json", "utf8"));
  assert.ok(r.slot_summary.worst_mean_offset_px <= 2, JSON.stringify(r.slot_summary));
  assert.ok(r.ice_edge.median_abs_offset_px <= 1, JSON.stringify(r.ice_edge));
  assert.match(r.scope, /not measured/);
});
