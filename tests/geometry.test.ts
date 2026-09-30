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

rejects("goal setup chosen without the user's statement", (g) => {
  g.goal_setup.source_ids = g.goal_setup.source_ids.filter((id: string) => id !== "user_statement_2026_09_30");
}, /must cite the user's statement/);

// ---- Iteration 06+: slot traces --------------------------------------------------------------
const TRACED_BY_ITERATION: Record<string, string[]> = {
  "06": ["W-LD", "W-RD", "W-C", "E-LD", "E-RD", "E-C"],
  "07": ["W-LW", "W-RW", "E-LW", "E-RW"],
};

test("slot paths: expected set traced in both photographs, with identity evidence", () => {
  const g = load();
  const expected = Object.values(TRACED_BY_ITERATION).flat();
  for (const p of expected) {
    const f = g.fixture_paths.find((x: any) => x.id === `path.${p}`);
    assert.ok(f, `path.${p} exists`);
    assert.deepEqual([...f.image_trace_ids].sort(), [`trace.slot.${p}.bare`, `trace.slot.${p}.overhead`]);
    assert.ok(f.identity_evidence?.description, `${p} identity evidence`);
    // The figure named in the evidence belongs to the team that owns the path in the reference variant.
    const team = g.teams.find((t: any) => t.id === p.split("-")[0]);
    assert.ok(f.identity_evidence.description.includes(team.reference_variant.team), `${p} evidence names ${team.reference_variant.team}`);
    assert.equal(f.fixture_axis_path, null, "fixture axis stays unknown");
    assert.equal(f.usable_stops.start.status, "unknown");
    assert.equal(f.usable_stops.end.status, "unknown");
    assert.equal(f.centreline.status, "assumed", "mm centreline only via the assumed preview scale");
  }
  const traced = g.fixture_paths.filter((f: any) => f.image_trace_ids.length > 0).map((f: any) => f.id.replace("path.", "")).sort();
  assert.deepEqual(traced, [...expected].sort(), "no other paths traced yet");
});

test("slot paths: each team traced independently (no mirrored copies)", () => {
  const g = load();
  const pts = (p: string) => g.image_traces.find((t: any) => t.id === `trace.slot.${p}.overhead`).points_px;
  for (const [a, b] of [["W-LD", "E-LD"], ["W-RD", "E-RD"], ["W-C", "E-C"], ["W-LW", "E-LW"], ["W-RW", "E-RW"]] as const) {
    const pa = pts(a), pb = pts(b);
    assert.notEqual(pa.length === pb.length && pa.every((q: number[], i: number) => q[0] === pb[i]?.[0]), true);
    // A point-mirror about the image of the rink centre would map one onto the other exactly; require independent data.
    const c: [number, number] = [2822.5, 2798];
    const mirrored = pa.map((q: [number, number]) => [2 * c[0] - q[0], 2 * c[1] - q[1]] as [number, number]);
    const exact = mirrored.every((q: [number, number]) => pb.some((r: [number, number]) => Math.hypot(r[0] - q[0], r[1] - q[1]) < 1e-6));
    assert.equal(exact, false, `${b} is not a mirror copy of ${a}`);
  }
});

test("slot paths: notes state no tangent-facing and no rod-travel = arc-length assumption", () => {
  const g = load();
  for (const f of g.fixture_paths.filter((x: any) => x.image_trace_ids.length > 0)) {
    assert.match(f.note, /NOT assumed to follow the slot tangent/);
    assert.match(f.note, /NOT assumed equal to arc length/);
  }
});
