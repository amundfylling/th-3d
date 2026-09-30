// Iteration 13: the W-RD lower asset is one rigid object at the fixture axis, built from the stored contacts.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { worldMmToGltfM } from "../src/model/coordinates.ts";
import type { GeometryFile } from "../src/model/geometry.ts";
import { readGlbJson } from "./rink-asset.test.ts";

const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const rep = JSON.parse(readFileSync("validation/13-skater-lower-report.json", "utf8"));
const gltf = readGlbJson("assets/figures/skater_W-RD_lower.glb");

test("single rigid node at the fixture axis, no skeleton or animation", () => {
  assert.equal(gltf.nodes.length, 1);
  const n = gltf.nodes[0];
  assert.equal(n.name, "SkaterLower.W-RD");
  assert.equal(n.translation, undefined, "origin = fixture axis");
  assert.equal(n.rotation, undefined);
  assert.equal(gltf.skins, undefined);
  assert.equal(gltf.animations, undefined);
});

test("stored contact shapes lie on the mesh surface; nothing below the ice", () => {
  assert.equal(rep.pass, true, JSON.stringify(rep.contact_on_surface_max_mm));
  for (const v of Object.values(rep.contact_on_surface_max_mm) as number[]) assert.ok(v <= 0.01);
  assert.ok(rep.nothing_below_ice);
});

test("GLB bounds = contact extents converted once (m, +Y up)", () => {
  const acc = gltf.meshes[0].primitives.map((p: any) => gltf.accessors[p.attributes.POSITION]);
  const min = [0, 1, 2].map((i) => Math.min(...acc.map((a: any) => a.min[i])));
  const max = [0, 1, 2].map((i) => Math.max(...acc.map((a: any) => a.max[i])));
  const [x0, y0, z0, x1, y1, z1] = rep.bounds_mm_xyz_min_max as number[];
  const lo = worldMmToGltfM([x0!, y1!, z0!]), hi = worldMmToGltfM([x1!, y0!, z1!]);
  for (let i = 0; i < 3; i++) {
    assert.ok(Math.abs(min[i]! - lo[i]!) < 1e-6, `min ${i}: ${min[i]} vs ${lo[i]}`);
    assert.ok(Math.abs(max[i]! - hi[i]!) < 1e-6, `max ${i}: ${max[i]} vs ${hi[i]}`);
  }
  // Blade tip (stored contact) is the extreme +y point: the blade is on the figure's left.
  const tip = g.figure_assets.find((a) => a.id === "fig.W-RD")!.contact_shapes.find((c) => c.kind === "blade")!.geometry!.points_mm[1]!;
  assert.ok(Math.abs(y1! - tip[1]) < 1e-3);
});
