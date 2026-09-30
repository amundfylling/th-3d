// Iteration 17: materials and artwork do not change geometry; the ice texture has calibrated scale.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { readGlbJson } from "./rink-asset.test.ts";

const rep = JSON.parse(readFileSync("validation/17-materials-report.json", "utf8"));
const tex = JSON.parse(readFileSync("validation/17-ice-texture-report.json", "utf8"));

test("geometry unchanged by the material pass (Blender vertex check and GLB bounds)", () => {
  assert.equal(rep.geometry_unchanged, true);
  const a = readGlbJson("assets/scene/full_static.glb"), b = readGlbJson("assets/scene/full_static_materials.glb");
  for (const name of ["Ice", "InnerBoards", "HousingBase", "HousingRim", "Goal.W", "Goal.E"]) {
    const bounds = (g: any) => { const n = g.nodes.find((x: any) => x.name === name); const acc = g.accessors[g.meshes[n.mesh].primitives[0].attributes.POSITION]; return [...acc.min, ...acc.max]; };
    bounds(a).forEach((v: number, i: number) => assert.ok(Math.abs(v - bounds(b)[i]) < 1e-9, `${name} bound ${i}`));
  }
});

test("ice texture: selected variant, calibrated texel size covering the ice bounds, reconstruction reported", () => {
  assert.equal(tex.source_image_id, "stiga_se_fi_overhead");
  assert.match(tex.variant, /bare-sheet print NOT used/);
  const [x0, y0, x1, y1] = tex.bounds_mm;
  assert.ok(Math.abs(tex.size_px[0] * tex.texel_mm - (x1 - x0)) < tex.texel_mm, "width");
  assert.ok(Math.abs(tex.size_px[1] * tex.texel_mm - (y1 - y0)) < tex.texel_mm, "height");
  assert.ok(tex.masked_fraction_of_ice > 0 && tex.masked_fraction_of_ice < 0.4);
  assert.match(tex.reconstruction, /RECONSTRUCTED/);
  assert.ok(tex.known_gaps.length >= 3);
  assert.equal(tex.redrawn_lines.centre_line.absent_samples > 0, true, "centre line absent under the disc is respected");
});

test("gaps and mismatches are recorded", () => {
  assert.ok(rep.gaps_and_mismatches.some((s: string) => /board sponsor/.test(s)));
  assert.match(rep.boards, /PLACEHOLDER/);
});
