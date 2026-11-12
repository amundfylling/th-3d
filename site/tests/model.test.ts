// Combo editor model checks (run with `npm test` in site/): the editor poses figures exactly as the repo's pose code,
// reads every library move cleanly, repairs what it can in hand-written or AI-written JSON, and round-trips share links.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import geometry from "../../data/geometry.json" with { type: "json" };
import { pathSampler, skaterPose, goaliePose, type Vec2 as RepoVec2 } from "../../src/model/pose.ts";
import { parseAnswer, promptForClipboard } from "../src/ai.ts";
import { PIDS, RINK, SLOTS, arrowDrawnLine, arrowRibbon, clampInsideBoards, comboFromLibrary, decodeShare, emptyCombo, encodeShare, figureToWorld, headingDeg, normalizeCombo, pivotOf, polylineLength, slicePolyline, teamOf } from "../src/model.ts";

const library = JSON.parse(readFileSync(new URL("../public/library.json", import.meta.url), "utf8")) as { geometry_version: string; default_figures: Record<string, { arc_mm: number; theta_deg: number }>; moves: Record<string, unknown>[] };
const base = emptyCombo(library.default_figures);

test("the rink data and the library come from the current geometry", () => {
  assert.equal(RINK.geometry_version, geometry.geometry_version);
  assert.equal(library.geometry_version, geometry.geometry_version);
  assert.equal(PIDS.length, 12);
});

test("figure poses equal the repo's pose code (pivot and heading)", () => {
  for (const fp of geometry.fixture_paths) {
    const pid = fp.player_id, kind = pid.endsWith("-G") ? "goalie" : "skater";
    const path = pathSampler(fp.id, kind, fp.centreline.points_mm.map((p) => [p[0]!, p[1]!] as RepoVec2));
    assert.ok(Math.abs(path.length - SLOTS[pid]!.length) < 0.05, `${pid} slot length`);
    for (const f of [0.01, 0.2, 0.5, 0.77, 0.99]) {
      const arc = f * path.length, theta = 360 * f - 180;
      const ref = (kind === "goalie" ? goaliePose : skaterPose)(path, teamOf(pid), { u_preview: arc / path.length, thetaDeg: theta });
      assert.ok(ref.ok);
      const mine = pivotOf(pid, { arc_mm: arc, theta_deg: theta });
      assert.ok(Math.hypot(mine[0] - ref.pivot[0], mine[1] - ref.pivot[1]) < 0.02, `${pid} pivot at ${arc}`);
      assert.equal(headingDeg(pid, theta), ref.headingDeg);
      // a point of the figure frame goes where the repo's rigid matrix puts it
      const m = ref.matrix, w = figureToWorld(pid, { arc_mm: arc, theta_deg: theta }, [2.8, 33.1]);
      assert.ok(Math.hypot(w[0] - (m[0] * 2.8 + m[1] * 33.1 + m[3]), w[1] - (m[4] * 2.8 + m[5] * 33.1 + m[7])) < 0.02, `${pid} blade point`);
    }
    const n = SLOTS[pid]!.nearest(SLOTS[pid]!.at(path.length * 0.4).point);
    assert.ok(Math.abs(n.arc - path.length * 0.4) < 0.01 && n.dist < 1e-6);
  }
});

test("every library move reads without a repair and survives a second read unchanged", () => {
  assert.equal(library.moves.length, 121);
  for (const move of library.moves) {
    const { combo, notes } = normalizeCombo({ ...move, schema: "th-combo/1" }, base);
    assert.deepEqual(notes, [], `${String(move.id)}: ${notes.join("; ")}`);
    assert.equal(Object.keys(combo.figures).length, 12);
    assert.ok(combo.arrows.length >= 1, `${String(move.id)} has arrows`);
    assert.deepEqual(normalizeCombo(JSON.parse(JSON.stringify(combo)), base).combo, combo);
    for (const a of combo.arrows) {
      const rib = arrowRibbon(arrowDrawnLine(a, combo.markers), a.width_mm, { dashed: false, head: true });
      assert.ok(rib.indices.length >= 3 && rib.positions.every(Number.isFinite), `${String(move.id)} arrow geometry`);
    }
  }
  assert.equal(comboFromLibrary(library.moves[0]!, base).schema, "th-combo/1");
});

test("hand-written JSON is repaired where possible and refused where not", () => {
  const { combo, notes } = normalizeCombo({
    figures: { "W-C": { at_mm: [100, 40], theta_deg: 540 }, "W-LW": { arc_mm: 9999 }, "X-1": { arc_mm: 1 } },
    puck: { x_mm: 5000, y_mm: 0 }, arrows: [{ points_mm: [[0, 0]] }, { points_mm: [[0, 0], [50, 10]], style: "dashed" }], markers: [{ n: 1, at_mm: [0, 0] }],
  }, base);
  assert.ok(SLOTS["W-C"]!.nearest(pivotOf("W-C", combo.figures["W-C"]!)).dist < 0.1);
  assert.equal(combo.figures["W-C"]!.theta_deg, -180);
  assert.ok(combo.figures["W-LW"]!.arc_mm <= SLOTS["W-LW"]!.length);
  assert.deepEqual(combo.figures["E-G"], base.figures["E-G"]);
  assert.ok(combo.puck.x_mm < 450);
  assert.equal(combo.arrows.length, 1);
  assert.equal(combo.arrows[0]!.style, "dashed");
  assert.equal(combo.markers[0]!.label, "1");
  assert.equal(notes.length, 5, notes.join(" | "));
  assert.throws(() => normalizeCombo({ schema: "other/9" }, base), /Unknown schema/);
  assert.throws(() => normalizeCombo({ figures: { "W-C": { arc_mm: "far" } } }, base), /arc_mm must be a number/);
  assert.throws(() => normalizeCombo([], base), /JSON object/);
});

test("the puck stays inside the boards", () => {
  const r = RINK.puck_radius_mm;
  for (const q of [[0, 0], [600, 0], [-600, 300], [430, 225], [0, -400]] as [number, number][]) {
    const p = clampInsideBoards(q, r);
    const dmin = Math.min(...RINK.board_mm.map((b) => Math.hypot(b[0]! - p[0], b[1]! - p[1])));
    assert.ok(dmin >= r - 0.6, `${q}: ${dmin}`);
  }
  assert.deepEqual(clampInsideBoards([10, 20], r), [10, 20]);
});

test("polylines are cut by arc length", () => {
  const line: [number, number][] = [[0, 0], [10, 0], [10, 10]];
  assert.equal(polylineLength(line), 20);
  assert.deepEqual(slicePolyline(line, 5, 15), [[5, 0], [10, 0], [10, 5]]);
  assert.equal(polylineLength(slicePolyline(line, 2, 19)), 17);
});

test("share links round-trip", async () => {
  const combo = comboFromLibrary(library.moves.find((m) => m.id === "senter-velodrom")!, base);
  const s = await encodeShare(combo);
  assert.match(s, /^[A-Za-z0-9_-]+$/);
  assert.ok(s.length < 2000, `share value is ${s.length} characters`);
  assert.deepEqual(normalizeCombo(await decodeShare(s), base).combo, combo);
});

test("AI answers are read from a fenced block or bare braces; the prompt carries the format and the table", () => {
  assert.deepEqual(parseAnswer('Moved it.\n```json\n{"puck": {"x_mm": 1, "y_mm": 2}}\n```\nDone.'), { json: { puck: { x_mm: 1, y_mm: 2 } }, said: "Moved it." });
  assert.deepEqual(parseAnswer('Here: {"name": "x"}').json, { name: "x" });
  assert.throws(() => parseAnswer("I cannot do that."), /No JSON/);
  const prompt = promptForClipboard(base, "pass to the left wing");
  for (const needle of ["th-combo/1", "W-LW", "arc_mm", "pass to the left wing", "blade"]) assert.ok(prompt.includes(needle), needle);
});
