// Iteration 10: provisional contact geometry behaves as a rigid part of the figure.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import type { GeometryFile } from "../src/model/geometry.ts";
import { linearDeterminant, pathSampler, skaterPose, toWorld, type Pose, type Vec3 } from "../src/model/pose.ts";

const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const asset = g.figure_assets.find((a) => a.id === "fig.W-RD")!;
const pts = (id: string): Vec3[] => asset.contact_shapes.find((c) => c.id === id)!.geometry!.points_mm as Vec3[];
const blade = pts("contact.W-RD.blade");
const all: Vec3[] = asset.contact_shapes.flatMap((c) => c.geometry!.points_mm as Vec3[]);
const path = pathSampler("t", "skater", [[-50, 10], [80, -20], [150, 40]]);
const pose = (team: "W" | "E", u: number, th: number): Pose => {
  const r = skaterPose(path, team, { u_preview: u, thetaDeg: th });
  assert.ok(r.ok);
  return r as Pose;
};

test("provisional contacts are labelled and real contact quantities stay unknown", () => {
  assert.ok(asset.contact_shapes.length >= 3);
  for (const c of asset.contact_shapes) {
    assert.equal(c.status, "assumed");
    assert.equal(c.provisional, true);
    assert.equal(c.assumption_id, "assume.debug_contacts.W-RD");
    assert.equal(c.frame, "pivot_local");
  }
  assert.equal(asset.blade_offset_from_pivot.value, null);
  assert.equal(asset.ice_clearance.value, null);
  assert.ok(asset.inventory!.some((i) => i.item.startsWith("mounting") && i.status === "unknown"));
  assert.equal(g.puck.thickness.value, null, "puck thickness not established");
});

test("contact points stay fixed relative to the figure for any pose (pairwise distances invariant)", () => {
  const ref = toWorld(pose("W", 0.1, 0), all);
  for (const [team, u, th] of [["W", 0.7, 33], ["E", 0.4, -120], ["E", 1, 725]] as const) {
    const w = toWorld(pose(team, u, th), all);
    for (let i = 0; i < all.length; i++) for (let j = i + 1; j < all.length; j++) {
      const d0 = Math.hypot(ref[i]![0] - ref[j]![0], ref[i]![1] - ref[j]![1], ref[i]![2] - ref[j]![2]);
      const d1 = Math.hypot(w[i]![0] - w[j]![0], w[i]![1] - w[j]![1], w[i]![2] - w[j]![2]);
      assert.ok(Math.abs(d0 - d1) < 1e-9, `distance ${i}-${j} changed`);
    }
  }
});

test("contacts rotate about the fixture axis: radius from the axis and height are preserved", () => {
  for (let th = -360; th <= 360; th += 45) {
    const p = pose("W", 0.5, th);
    const w = toWorld(p, all);
    all.forEach((q, i) => {
      assert.ok(Math.abs(Math.hypot(w[i]![0] - p.pivot[0], w[i]![1] - p.pivot[1]) - Math.hypot(q[0], q[1])) < 1e-9);
      assert.ok(Math.abs(w[i]![2] - q[2]) < 1e-12);
    });
  }
});

test("handedness preserved: the blade stays on the figure's left for both teams, det +1", () => {
  assert.equal(g.players.find((p) => p.id === "W-RD")!.stick_handedness, "left");
  const mid: Vec3 = [(blade[0]![0] + blade[1]![0]) / 2, (blade[0]![1] + blade[1]![1]) / 2, 0];
  for (const team of ["W", "E"] as const) for (const th of [0, 90, 181, -45, 400]) {
    const p = pose(team, 0.5, th);
    assert.ok(Math.abs(linearDeterminant(p.matrix) - 1) < 1e-12);
    const [o, f, b] = toWorld(p, [[0, 0, 0], [10, 0, 0], mid]);
    const cross = (f![0] - o![0]) * (b![1] - o![1]) - (f![1] - o![1]) * (b![0] - o![0]);
    assert.ok(cross > 0, `${team} ${th}: blade on the left`);
  }
});
