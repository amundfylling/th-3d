// Track fix 2026-10-01: E-RW and W-RW are straight where a stick lies on the slot in the official overhead.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import type { GeometryFile } from "../src/model/geometry.ts";

const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const seeds = JSON.parse(readFileSync("data/slot-seeds.json", "utf8")).paths;

function straightness(pid: string, x0: number, x1: number): number {
  const P = g.fixture_paths.find((f) => f.player_id === pid)!.centreline!.points_mm.filter(([x]) => x > x0 && x < x1);
  const n = P.length, mx = P.reduce((s, p) => s + p[0], 0) / n, my = P.reduce((s, p) => s + p[1], 0) / n;
  const b = P.reduce((s, p) => s + (p[0] - mx) * (p[1] - my), 0) / P.reduce((s, p) => s + (p[0] - mx) ** 2, 0);
  return Math.max(...P.map(([x, y]) => Math.abs(y - (my + b * (x - mx)))));
}

test("stick-occluded stretches are straight (were 2.0 / 0.6 mm off)", () => {
  assert.ok(straightness("E-RW", -300, -100) < 0.3, `E-RW ${straightness("E-RW", -300, -100)}`);
  assert.ok(straightness("W-RW", 100, 300) < 0.3, `W-RW ${straightness("W-RW", 100, 300)}`);
});

test("the occlusion is operator-marked with a reason and reported as inferred, not measured", () => {
  for (const pid of ["E-RW", "W-RW"]) {
    const boxes = seeds[`path.${pid}`].occluded_boxes_overhead;
    assert.ok(boxes.length === 1 && boxes[0].reason.includes("stick"));
    const t = g.image_traces.find((x) => x.id === `trace.slot.${pid}.overhead`)!;
    assert.ok(t.inferred_segments.some((s) => s.reason.includes("stick")), `${pid} inferred segment`);
  }
});
