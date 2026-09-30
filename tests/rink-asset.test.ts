// Iteration 11: the GLB is in metres, +Y up, converted exactly once, and matches the canonical data.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { worldMmToGltfM } from "../src/model/coordinates.ts";
import type { GeometryFile } from "../src/model/geometry.ts";

export function readGlbJson(path: string): any {
  const b = readFileSync(path);
  assert.equal(b.toString("ascii", 0, 4), "glTF");
  const len = b.readUInt32LE(12);
  assert.equal(b.toString("ascii", 16, 20), "JSON");
  return JSON.parse(b.toString("utf8", 20, 20 + len));
}

const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const gltf = readGlbJson("assets/rink/rink.glb");
const bounds = (name: string): { min: number[]; max: number[] } => {
  const mesh = gltf.meshes.find((m: any) => m.name === name) ?? gltf.meshes[gltf.nodes.find((n: any) => n.name === name).mesh];
  const acc = gltf.accessors[mesh.primitives[0].attributes.POSITION];
  return { min: acc.min, max: acc.max };
};
const near = (a: number, b: number, tol: number, msg: string): void => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} vs ${b}`);

test("rink GLB contains exactly the static rink parts, no animation", () => {
  const names = gltf.nodes.map((n: any) => n.name).sort();
  assert.deepEqual(names, ["HousingBase", "HousingRim", "Ice", "InnerBoards"]);
  assert.equal(gltf.animations, undefined);
  for (const n of gltf.nodes) {
    assert.equal(n.rotation, undefined, `${n.name}: no node rotation (axis conversion lives in the vertex data)`);
    assert.equal(n.scale, undefined, `${n.name}: no node scale (mm->m done once in the build)`);
  }
});

test("ice extent in the GLB equals the canonical boundary converted once (m, +Y up)", () => {
  const pts = g.board.inner_boundary.world!.points_mm;
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const lo = worldMmToGltfM([Math.min(...xs), Math.max(...ys), 0]);
  const hi = worldMmToGltfM([Math.max(...xs), Math.min(...ys), 0]);
  const ice = bounds("Ice");
  near(ice.min[0]!, lo[0], 1e-4, "ice x min"); near(ice.max[0]!, hi[0], 1e-4, "ice x max");
  near(ice.min[2]!, lo[2], 1e-4, "ice z min (= -y max)"); near(ice.max[2]!, hi[2], 1e-4, "ice z max (= -y min)");
  const iceT = g.preview_parameters!.ice_sheet_thickness!.value! / 1000;
  near(ice.max[1]!, 0, 1e-6, "ice top at Y = 0"); near(ice.min[1]!, -iceT, 1e-6, "ice bottom");
  near(bounds("InnerBoards").max[1]!, g.preview_parameters!.board_height_above_ice!.value! / 1000, 1e-6, "board top");
});

test("render-based scale check passed", () => {
  const v = JSON.parse(readFileSync("validation/11-rink-verify.json", "utf8"));
  assert.equal(v.pass, true, JSON.stringify(v));
});
