// Evidence-policy tests: the canonical file passes, and each mutation that would smuggle in
// invented or silently resolved geometry is rejected.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { isUniformSimilarity, validateGeometry, type ReferenceIndexEntry } from "../src/model/validate.ts";

const index = (JSON.parse(readFileSync("references/index.json", "utf8")) as { sources: ReferenceIndexEntry[] }).sources;
const load = (): any => JSON.parse(readFileSync("data/geometry.json", "utf8"));
const check = (data: unknown) => validateGeometry(data, { referenceIndex: index });

function rejects(name: string, mutate: (g: any) => void, expected: RegExp): void {
  test(`rejects: ${name}`, () => {
    const g = load();
    mutate(g);
    const r = check(g);
    assert.equal(r.ok, false, "expected validation to fail");
    assert.ok(r.errors.some((e) => expected.test(e)), `no error matched ${expected}:\n${r.errors.join("\n")}`);
  });
}

test("canonical data/geometry.json is valid", () => {
  const r = check(load());
  assert.deepEqual(r.errors, []);
});

test("unknown physical values stay null", () => {
  const g = load();
  for (const f of g.fixture_paths) {
    assert.equal(f.usable_stops.start.value, null);
    assert.equal(f.usable_stops.end.value, null);
  }
  for (const a of g.figure_assets) assert.equal(a.blade_offset_from_pivot.value, null);
  assert.equal(g.puck.thickness.value, null);
  assert.equal(g.conflicts[0].resolution, "unresolved");
});

rejects("unknown status with a value", (g) => (g.puck.thickness.value = 3), /if and only if value is null/);
rejects("zero uncertainty", (g) => (g.puck.diameter.uncertainty = 0), /uncertainty must be null/);
rejects("catalog value without source", (g) => (g.puck.diameter.source_ids = []), /requires source_ids/);
rejects("assumed value without assumption", (g) => {
  g.puck.thickness = { value: 4, unit: "mm", status: "assumed", uncertainty: null, source_ids: [] };
}, /requires assumption_id/);
rejects("measured value without a user measurement", (g) => {
  g.puck.diameter.status = "measured";
}, /requires a user_measurement source/);
rejects("unknown source id", (g) => g.puck.diameter.source_ids.push("nowhere"), /unknown source "nowhere"/);
rejects("conflict resolved from catalog values", (g) => {
  g.conflicts[0].resolution = { resolved_by_source_ids: ["stiga_sports_catalog"], note: "pick 960" };
}, /only be resolved by a user_measurement/);
rejects("modified reference hash", (g) => (g.source_images[0].sha256 = "0".repeat(64)), /sha256 differs/);
rejects("anisotropic preview scale", (g) => {
  g.assumptions.push({ id: "a", statement: "s", reason: "r", affects: [], replace_with: "m" });
  g.image_to_world.push({
    id: "m", source_image_id: "stiga_se_fi_overhead", model: "similarity",
    matrix: [0.2, 0, -500, 0, -0.25, 600, 0, 0, 1], plane: "ice_top_z0", status: "assumed", assumption_ids: ["a"], note: "",
  });
}, /uniform scale/);
rejects("landmark outside image", (g) => {
  g.landmarks.push({ id: "L", source_image_id: "stiga_se_fi_overhead", px: [6000, 10], uncertainty_px: 2, description: "d", visibility: "visible" });
}, /outside the source image/);
rejects("missing player position", (g) => g.players.splice(1, 1), /expected exactly one each/);
rejects("typo key", (g) => (g.puck.diameterr = 1), /unknown key/);

test("isUniformSimilarity accepts rotation+reflection with one scale", () => {
  const s = 0.15, t = 0.3;
  assert.ok(isUniformSimilarity([s * Math.cos(t), s * Math.sin(t), 1, s * Math.sin(t), -s * Math.cos(t), 2, 0, 0, 1]));
  assert.ok(!isUniformSimilarity([s, 0, 0, 0, -1.01 * s, 0, 0, 0, 1]));
});

test("board trace stays provisional: pixel trace traced, world outline and mapping assumed", () => {
  const g = load();
  const trace = g.image_traces.find((t: any) => t.id === "trace.board_inner.overhead");
  assert.ok(trace, "board trace present");
  assert.equal(trace.status, "traced");
  assert.ok(trace.uncertainty_px > 0);
  const map = g.image_to_world.find((m: any) => m.id === "map.overhead.preview");
  assert.equal(map.status, "assumed");
  assert.equal(map.model, "similarity");
  assert.ok(isUniformSimilarity(map.matrix));
  assert.equal(g.board.inner_boundary.world.status, "assumed");
  assert.equal(g.board.inner_boundary.corner_radius.value, null);
});

rejects("board outline promoted to measured without measurement", (g) => {
  g.board.inner_boundary.world.status = "measured";
}, /stronger than its mapping|requires a user_measurement/);
