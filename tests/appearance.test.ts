// Iteration 18: appearance pass keeps geometry, uses recorded colour samples, lists unresolved decals.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { readGlbJson } from "./rink-asset.test.ts";

const rep = JSON.parse(readFileSync("validation/18-appearance-report.json", "utf8"));
const samples = JSON.parse(readFileSync("validation/18-colour-samples.json", "utf8"));

test("geometry unchanged: assets and scene", () => {
  assert.equal(rep.geometry_unchanged.scene, true);
  const a = readGlbJson("assets/scene/full_static_materials.glb"), b = readGlbJson("assets/scene/full_static_appearance.glb");
  for (const name of ["Figure.W-RD", "Figure.W-G", "Puck", "Figure.E-LD"]) {
    const bounds = (g: any) => {
      const n = g.nodes.find((x: any) => x.name === name);
      const accs = g.meshes[n.mesh].primitives.map((p: any) => g.accessors[p.attributes.POSITION]);
      return [0, 1, 2].flatMap((i) => [Math.min(...accs.map((x: any) => x.min[i])), Math.max(...accs.map((x: any) => x.max[i]))]);
    };
    const bb = bounds(b);
    bounds(a).forEach((v: number, i: number) => assert.ok(Math.abs(v - bb[i]!) < 1e-9, `${name} bound ${i}`));
  }
});

test("colours come from recorded photo samples; figures carry their own kit materials and prints", () => {
  for (const s of Object.values(samples) as any[]) assert.match(s.source, /stiga_se_fi_overhead px/);
  assert.deepEqual(rep.colours_srgb.fin_blue, samples.finland_blue.srgb);
  assert.match(rep.figures, /own materials and per-player back prints/);
  const gltf = readGlbJson("assets/figures/skater_FIN.glb");
  const names = gltf.materials.map((m: any) => m.name).filter((n: string) => !n.startsWith("print_")).sort();
  assert.deepEqual(names, ["fig_blue", "fig_kit_FIN", "fig_recess", "fig_skin", "fig_stick_metal", "fig_stick_tan"].filter((n) => gltf.materials.some((m: any) => m.name === n)));
  assert.ok(names.includes("fig_kit_FIN") && names.includes("fig_blue") && names.includes("fig_stick_metal"));
});
