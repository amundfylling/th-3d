// Iteration 12: goal, screen and puck assets have the documented origins and dimensions, and the
// assembled scene keeps the accepted rink geometry unchanged.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import type { GeometryFile } from "../src/model/geometry.ts";
import { readGlbJson } from "./rink-asset.test.ts";

const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const rep = JSON.parse(readFileSync("validation/12-hardware-report.json", "utf8"));
const meshBounds = (gltf: any, name: string) => {
  const node = gltf.nodes.find((n: any) => n.name === name);
  const acc = gltf.accessors[gltf.meshes[node.mesh].primitives[0].attributes.POSITION];
  return { min: acc.min as number[], max: acc.max as number[], node };
};
const near = (a: number, b: number, tol: number, msg: string): void => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} vs ${b}`);

test("puck asset: origin at bottom centre, nominal diameter, preview thickness", () => {
  const b = meshBounds(readGlbJson("assets/puck/puck.glb"), "Puck");
  near(b.min[1]!, 0, 1e-6, "bottom on Y=0");
  near(b.max[1]!, g.preview_parameters!.puck_thickness!.value! / 1000, 1e-6, "thickness");
  near(b.max[0]! - b.min[0]!, g.puck.diameter.value! / 1000, 1e-4, "diameter");
  assert.equal(g.puck.thickness.value, null, "physical puck thickness still unknown");
});

test("goal asset: origin at mouth centre on the ice, opens toward +x, no insert", () => {
  const b = meshBounds(readGlbJson("assets/goal/goal.glb"), "Goal");
  near(b.min[1]!, 0, 1e-6, "on the ice");
  near(b.max[1]!, (g.preview_parameters!.goal_height!.value! + g.preview_parameters!.goal_post_radius!.value!) / 1000, 1e-4, "height + post radius");
  assert.ok(b.max[0]! <= (g.preview_parameters!.goal_post_radius!.value! + 1e-3) / 1000, "nothing in front of the goal line");
  near(-b.min[0]!, (rep.goal.depth_mm + g.preview_parameters!.goal_bar_radius!.value!) / 1000, 1e-4, "depth");
  assert.equal(rep.goal.configuration, "ithf_no_insert_no_cup");
  for (const q of ["width", "height", "depth"] as const) assert.equal(g.goals[0]![q].value, null, `physical goal ${q} unknown`);
});

test("assembled scene: rink meshes unchanged, two goals, two screens, one puck", () => {
  assert.equal(rep.rink_meshes_unchanged, true);
  const scene = readGlbJson("assets/scene/static_hardware.glb");
  const rink = readGlbJson("assets/rink/rink.glb");
  for (const name of ["Ice", "InnerBoards", "HousingBase", "HousingRim"]) {
    const a = meshBounds(scene, name), b = meshBounds(rink, name);
    a.min.forEach((v, i) => near(v, b.min[i]!, 1e-9, `${name} min`));
    a.max.forEach((v, i) => near(v, b.max[i]!, 1e-9, `${name} max`));
  }
  const names = scene.nodes.map((n: any) => n.name).sort();
  assert.deepEqual(names, ["EndScreen.E", "EndScreen.W", "Goal.E", "Goal.W", "HousingBase", "HousingRim", "Ice", "InnerBoards", "Puck"]);
  assert.ok(rep.screen.E_end_max_gap_to_board_face_mm < 5, "E screen placed by rotation sits on the E end boards");
});
