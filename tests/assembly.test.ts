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
    assert.equal(p.heading_deg, p.team === "W" ? 0 : 180);
  }
});

test("mold reuse only where evidenced; everything else is a marked placeholder", () => {
  assert.deepEqual([...rep.modelled].sort(), ["W-G", "W-RD"]);
  assert.equal(rep.placeholders.length, 10);
  for (const p of poses.filter((x) => !["W-G", "W-RD"].includes(x.player_id))) assert.match(p.asset, /PLACEHOLDER/);
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
