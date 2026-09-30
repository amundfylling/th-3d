// Focused numerical checks for the fixture-pose mathematics (iteration 09).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { gltfMToWorldMm, worldMatrixToGltf, worldMmToGltfM } from "../src/model/coordinates.ts";
import type { GeometryFile } from "../src/model/geometry.ts";
import { loadFigurePaths } from "../src/model/paths.ts";
import { goaliePose, linearDeterminant, pathSampler, skaterPose, toWorld, transformPoint, unwrapDeg, type Pose, type Vec3 } from "../src/model/pose.ts";

const close = (a: number, b: number, tol = 1e-9, msg = ""): void => assert.ok(Math.abs(a - b) <= tol, `${msg} ${a} vs ${b}`);
const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const paths = loadFigurePaths(g);
const path = (id: string) => paths.find((p) => p.playerId === id)!;
const ok = (p: ReturnType<typeof skaterPose>): Pose => {
  assert.equal(p.ok, true, !p.ok ? p.reason : "");
  return p as Pose;
};

test("all 12 canonical paths load; goalies get goalie samplers", () => {
  assert.equal(paths.length, 12);
  assert.deepEqual(paths.filter((p) => p.sampler.kind === "goalie").map((p) => p.playerId).sort(), ["E-G", "W-G"]);
  for (const p of paths) assert.ok(p.sampler.length > 0);
});

test("path sampling is continuous along every canonical path (1 mm steps)", () => {
  for (const p of paths) {
    let prev = p.sampler.at(0).point;
    for (let s = 1; s <= p.sampler.length; s += 1) {
      const q = p.sampler.at(s).point;
      assert.ok(Math.hypot(q[0] - prev[0], q[1] - prev[1]) <= 1 + 1e-9, `${p.playerId} jump at s=${s}`);
      prev = q;
    }
    const end = p.sampler.at(p.sampler.length).point;
    assert.ok(Math.hypot(end[0] - prev[0], end[1] - prev[1]) <= 1 + 1e-9);
  }
});

test("boundary inputs: u = 0 and 1 hit the path ends; outside [0, 1] and NaN are flagged, not clamped", () => {
  const s = pathSampler("t", "skater", [[0, 0], [100, 0], [100, 50]]);
  const a = ok(skaterPose(s, "W", { u_preview: 0, thetaDeg: 0 }));
  const b = ok(skaterPose(s, "W", { u_preview: 1, thetaDeg: 0 }));
  assert.deepEqual(a.pivot, [0, 0, 0]);
  close(b.pivot[0], 100); close(b.pivot[1], 50);
  for (const u of [-0.001, 1.001, Number.NaN, Infinity]) {
    const r = skaterPose(s, "W", { u_preview: u, thetaDeg: 0 });
    assert.equal(r.ok, false, `u=${u} must be invalid`);
  }
  assert.equal(skaterPose(s, "W", { u_preview: 0.5, thetaDeg: Number.NaN }).ok, false);
  assert.throws(() => pathSampler("bad", "skater", [[1, 1], [1, 1]]));
});

test("rotation passes continuously through 360 deg and the state keeps unwrapped angles", () => {
  const s = pathSampler("t", "skater", [[0, 0], [100, 0]]);
  const local: Vec3 = [30, 5, 0];
  let prev: Vec3 | null = null;
  for (let th = 355; th <= 365; th += 0.5) {
    const p = ok(skaterPose(s, "W", { u_preview: 0.5, thetaDeg: th }));
    assert.equal(p.state.thetaDeg, th, "no wrapping of the state");
    const w = transformPoint(p.matrix, local);
    if (prev) assert.ok(Math.hypot(w[0] - prev[0], w[1] - prev[1]) < 0.3, `jump at ${th}`);
    prev = w;
  }
  const at1 = transformPoint(ok(skaterPose(s, "W", { u_preview: 0.5, thetaDeg: 1 })).matrix, local);
  const at361 = transformPoint(ok(skaterPose(s, "W", { u_preview: 0.5, thetaDeg: 361 })).matrix, local);
  close(at1[0], at361[0], 1e-9); close(at1[1], at361[1], 1e-9);
  assert.deepEqual(unwrapDeg([350, 10, 30, 190, -170]), [350, 370, 390, 550, 550]);
});

test("one known pivot-local point maps exactly", () => {
  const s = pathSampler("t", "skater", [[10, 20], [110, 20]]);
  const p = ok(skaterPose(s, "W", { u_preview: 0.25, thetaDeg: 90 }));
  // pivot at (35, 20); local (+10 forward, +2 left, 3 up) rotated by 90 deg -> (-2, +10, 3)
  const [w] = toWorld(p, [[10, 2, 3]]);
  close(w![0], 33, 1e-9); close(w![1], 30, 1e-9); close(w![2], 3, 1e-9);
  // E team: home heading 180 deg, theta 0 -> local +x points to world -x
  const e = ok(skaterPose(s, "E", { u_preview: 0.25, thetaDeg: 0 }));
  const [we] = toWorld(e, [[10, 2, 0]]);
  close(we![0], 25, 1e-9); close(we![1], 18, 1e-9);
});

test("rotation is independent of the path tangent", () => {
  const s = pathSampler("t", "skater", [[0, 0], [100, 0], [100, 100]]);
  const a = ok(skaterPose(s, "W", { u_preview: 0.25, thetaDeg: 30 }));
  const b = ok(skaterPose(s, "W", { u_preview: 0.75, thetaDeg: 30 }));
  assert.notDeepEqual(a.pathTangent, b.pathTangent);
  assert.equal(a.headingDeg, b.headingDeg);
});

test("handedness preserved for both teams: proper rotations only (det +1), left stays left", () => {
  const s = pathSampler("t", "skater", [[0, 0], [100, 0]]);
  // A left-handed stick: blade on the figure's left (+y local).
  const forward: Vec3 = [10, 0, 0], leftBlade: Vec3 = [5, 8, 0];
  for (const team of ["W", "E"] as const) {
    for (const th of [0, 37, -120, 400]) {
      const p = ok(skaterPose(s, team, { u_preview: 0.5, thetaDeg: th }));
      close(linearDeterminant(p.matrix), 1, 1e-12, `det ${team} ${th}`);
      const [o, f, l] = toWorld(p, [[0, 0, 0], forward, leftBlade]);
      const cross = (f![0] - o![0]) * (l![1] - o![1]) - (f![1] - o![1]) * (l![0] - o![0]);
      assert.ok(cross > 0, `${team} theta ${th}: blade must stay on the figure's left`);
    }
  }
});

test("goalie adapter is separate: rejects skater paths and vice versa", () => {
  const gp = path("W-G").sampler, sp = path("W-LD").sampler;
  assert.equal(goaliePose(sp, "W", { u_preview: 0.5, thetaDeg: 0 }).ok, false);
  assert.equal(skaterPose(gp, "W", { u_preview: 0.5, thetaDeg: 0 }).ok, false);
  const p = goaliePose(gp, "W", { u_preview: 0.5, thetaDeg: 0 });
  assert.equal(p.ok, true);
});

test("preview assumptions are reported unless a fixture offset is supplied", () => {
  const s = pathSampler("t", "skater", [[0, 0], [100, 0]]);
  assert.ok(ok(skaterPose(s, "W", { u_preview: 0.5, thetaDeg: 0 })).assumptions.includes("assume.fixture_axis_on_slot_centreline"));
  const q = ok(skaterPose(s, "W", { u_preview: 0.5, thetaDeg: 0 }, { fixtureOffsetMm: [0, 3] }));
  assert.ok(!q.assumptions.includes("assume.fixture_axis_on_slot_centreline"));
  close(q.pivot[1], 3);
  assert.ok(g.assumptions.some((a) => a.id === "assume.fixture_axis_on_slot_centreline"), "assumption recorded in data");
});

test("world -> glTF adapter: basis vectors, units, round trip, same-sign yaw, det +1", () => {
  assert.deepEqual(worldMmToGltfM([1000, 0, 0]), [1, 0, -0]);
  assert.deepEqual(worldMmToGltfM([0, 1000, 0]), [0, 0, -1]);
  assert.deepEqual(worldMmToGltfM([0, 0, 1000]), [0, 1, -0]);
  const p: Vec3 = [123, -45, 6];
  const back = gltfMToWorldMm(worldMmToGltfM(p));
  p.forEach((v, i) => close(back[i]!, v, 1e-9));
  const s = pathSampler("t", "skater", [[0, 0], [100, 0]]);
  const pose = ok(skaterPose(s, "W", { u_preview: 0.3, thetaDeg: 30 }));
  const mg = worldMatrixToGltf(pose.matrix);
  close(linearDeterminant(mg), 1, 1e-12);
  // Local point transformed in world then converted == converted local point transformed in glTF.
  const local: Vec3 = [20, 7, 4];
  const viaWorld = worldMmToGltfM(transformPoint(pose.matrix, local));
  const viaGltf = transformPoint(mg, worldMmToGltfM(local));
  viaWorld.forEach((v, i) => close(viaGltf[i]!, v, 1e-12));
  // Yaw +30 about world +z == +30 about glTF +Y: glTF rotation about Y maps +X to (cos, 0, -sin).
  close(mg[0], Math.cos(Math.PI / 6), 1e-12); close(mg[8], -Math.sin(Math.PI / 6), 1e-12);
});
