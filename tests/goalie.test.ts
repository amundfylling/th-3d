// Iteration 15: goalie asset agrees with the goalie pose adapter; nothing declared measured.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import type { GeometryFile } from "../src/model/geometry.ts";
import { loadFigurePaths } from "../src/model/paths.ts";
import { goaliePose, toWorld, type Pose, type Vec3 } from "../src/model/pose.ts";
import { readGlbJson } from "./rink-asset.test.ts";

const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const rep = JSON.parse(readFileSync("validation/15-goalie-report.json", "utf8"));
const asset = g.figure_assets.find((a) => a.id === "fig.W-G")!;
const path = loadFigurePaths(g).find((p) => p.playerId === "W-G")!.sampler;

test("goalie asset: own rigid node at its fixture axis, own contacts, thresholds met", () => {
  const gltf = readGlbJson("assets/figures/goalie_W-G.glb");
  assert.equal(gltf.nodes.length, 1);
  assert.equal(gltf.nodes[0].name, "Goalie.W-G");
  assert.equal(gltf.nodes[0].translation, undefined);
  assert.equal(gltf.skins, undefined);
  assert.ok(rep.top_silhouette_iou >= 0.75);
  assert.equal(rep.pass, true);
  const kinds = asset.contact_shapes.map((c) => c.kind).sort();
  assert.deepEqual(kinds, ["blade", "pad", "pad", "stick_shaft"]);
  for (const c of asset.contact_shapes) assert.equal(c.provisional, true);
});

test("no goalie clearance or dimension is declared measured", () => {
  for (const q of [asset.figure_height, asset.blade_offset_from_pivot, asset.ice_clearance]) assert.notEqual(q.status, "measured");
  assert.equal(asset.ice_clearance.value, null);
  assert.equal(g.preview_parameters!.goalie_height!.status, "assumed");
  for (const i of asset.inventory!) assert.notEqual(i.status, "measured");
});

test("contacts placed by goaliePose match the asset placed in the render scene", () => {
  // The debug pivot lies on the W-G path: find its arc-length parameter.
  const pv = rep.pivot_world_mm as [number, number];
  let best = { u: 0, d: Infinity };
  for (let k = 0; k <= 4000; k++) {
    const u = k / 4000;
    const q = path.at(u * path.length).point;
    const d = Math.hypot(q[0] - pv[0], q[1] - pv[1]);
    if (d < best.d) best = { u, d };
  }
  assert.ok(best.d < 1.5, `pivot ${best.d.toFixed(2)} mm from the W-G path`);
  const r = goaliePose(path, "W", { u_preview: best.u, thetaDeg: 0 });
  assert.ok(r.ok);
  const p = r as Pose;
  for (const c of asset.contact_shapes) {
    const world = toWorld(p, c.geometry!.points_mm as Vec3[]);
    const placed = rep.world_contacts_mm[c.id] as Vec3[];
    world.forEach((w, i) => {
      const e = Math.hypot(w[0] - placed[i]![0], w[1] - placed[i]![1], w[2] - placed[i]![2]);
      assert.ok(e < 1.5, `${c.id}[${i}] differs by ${e.toFixed(2)} mm`);
    });
  }
});
