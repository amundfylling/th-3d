// Figure molds (2026-09-30): rigid skater and goalie assets fitted to the user's photos/videos and the
// official overhead; contacts derived from the molds; handedness and rigidity under the pose functions.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import type { GeometryFile } from "../src/model/geometry.ts";
import { linearDeterminant, pathSampler, skaterPose, toWorld, type Pose, type Vec3 } from "../src/model/pose.ts";
import { readGlbJson } from "./rink-asset.test.ts";

const g = JSON.parse(readFileSync("data/geometry.json", "utf8")) as GeometryFile;
const rep = JSON.parse(readFileSync("validation/players/figures-report.json", "utf8"));
const over = JSON.parse(readFileSync("validation/players/overhead-fit.json", "utf8"));
const molds = JSON.parse(readFileSync("data/figure-molds.json", "utf8"));
const KITS = ["SWE", "FIN"] as const;

const posBounds = (gltf: any, node: any) => {
  const accs = gltf.meshes[node.mesh].primitives.map((p: any) => gltf.accessors[p.attributes.POSITION]);
  return [0, 1, 2].map((i) => [Math.min(...accs.map((a: any) => a.min[i])), Math.max(...accs.map((a: any) => a.max[i]))]);
};

test("four rigid assets: one mesh node each on the fixture axis, a back-print child, no rig or animation", () => {
  for (const kind of ["skater", "goalie"]) for (const kit of KITS) {
    const gltf = readGlbJson(`assets/figures/${kind}_${kit}.glb`);
    const root = gltf.nodes.find((n: any) => n.name === `${kind === "skater" ? "Skater" : "Goalie"}.${kit}`);
    assert.ok(root, `${kind}_${kit} root node`);
    assert.equal(root.translation, undefined, "origin = fixture axis (no node offset)");
    assert.equal(root.rotation, undefined);
    assert.equal(gltf.skins, undefined);
    assert.equal(gltf.animations, undefined);
    assert.equal(root.children.length, 1, "one decal child");
    assert.match(gltf.nodes[root.children[0]].name, /^Print\./);
    const [x, y] = posBounds(gltf, root);
    assert.ok(Math.abs(y![0]!) < 1e-6, `${kind}_${kit}: lowest point on the ice (glTF +Y up), got ${y![0]}`);
    assert.ok(x![0]! < 0 && x![1]! > 0, "the axis lies inside the footprint");
  }
});

test("Sweden and Finland kits share one mold: identical geometry bounds, only the kit material differs", () => {
  for (const kind of ["skater", "goalie"]) {
    const [a, b] = KITS.map((k) => readGlbJson(`assets/figures/${kind}_${k}.glb`));
    const na = a!.nodes.find((n: any) => n.name.endsWith(".SWE")), nb = b!.nodes.find((n: any) => n.name.endsWith(".FIN"));
    assert.deepEqual(posBounds(a, na), posBounds(b, nb));
    const mats = (gl: any) => gl.materials.map((m: any) => m.name).filter((n: string) => !n.startsWith("print_")).sort();
    assert.deepEqual(mats(a).map((n: string) => n.replace("SWE", "KIT")), mats(b).map((n: string) => n.replace("FIN", "KIT")));
    assert.ok(mats(a).includes("fig_blue") && mats(b).includes("fig_blue"), "one shared blue");
  }
  assert.equal(rep.assets.skater_SWE.height_mm, rep.assets.skater_FIN.height_mm);
});

test("mount socket, stick and blade: on the ice, blade on the figure's LEFT, overhead-consistent skater stick", () => {
  for (const [name, r] of Object.entries(rep.assets) as [string, any][]) {
    assert.equal(r.zmin_mm, 0, `${name} rests on the ice`);
    assert.equal(r.stick_zmin_mm, 0, `${name} blade on the ice`);
    assert.equal(r.stick_side, "left (+y)");
    assert.ok(r.socket_bottom_diameter_mm > 8 && r.socket_bottom_diameter_mm < 16);
  }
  const s = rep.assets.skater_SWE;
  // Official overhead, four figures read on the ice (validation/players/overhead-fit.json stick_check).
  const sc = over.stick_check;
  assert.ok(Math.abs(s.blade_heel_mm[1] - sc.mean_heel_lateral_mm) < 1.5, `heel lateral ${s.blade_heel_mm[1]} vs ${sc.mean_heel_lateral_mm}`);
  assert.ok(Math.abs(s.blade_length_mm - sc.mean_blade_length_mm) < 1.5, `blade ${s.blade_length_mm} vs ${sc.mean_blade_length_mm}`);
});

test("fits meet their thresholds (set before fitting): photo silhouettes >= 0.78 mean, overhead >= 0.65", () => {
  for (const kind of ["skater", "goalie"]) {
    const f = JSON.parse(readFileSync(`validation/players/${kind}-fit.json`, "utf8"));
    assert.ok(f.mean_iou >= 0.78, `${kind} mean IoU ${f.mean_iou}`);
    for (const [v, r] of Object.entries(f.views) as [string, any][]) assert.ok(r.iou >= 0.65, `${v} ${r.iou}`);
  }
  for (const pid of ["E-LD", "E-RD", "E-C", "E-LW"]) assert.ok(over.figures[pid].iou >= 0.65, `${pid} ${over.figures[pid].iou}`);
  assert.ok(over.scale_k_mm_per_mold_unit > 0.9 && over.scale_k_mm_per_mold_unit < 1.3);
});

test("all 12 assets use the shared molds; contacts identical per mold; statuses honest", () => {
  const byKind = (k: string) => g.figure_assets.filter((a) => a.kind === k);
  assert.equal(byKind("skater").length, 10);
  assert.equal(byKind("goalie").length, 2);
  for (const k of ["skater", "goalie"]) {
    const ref = JSON.stringify(byKind(k)[0]!.contact_shapes.map((c) => [c.kind, c.geometry]));
    for (const a of byKind(k)) {
      assert.equal(a.mold_group, `mold.${k}`);
      assert.equal(JSON.stringify(a.contact_shapes.map((c) => [c.kind, c.geometry])), ref, `${a.id} contacts equal the mold's`);
      for (const c of a.contact_shapes) assert.equal(c.provisional, undefined);
      assert.equal(a.ice_clearance.value, null);
      assert.notEqual(a.figure_height.status, "measured");
    }
  }
  for (const a of byKind("goalie")) assert.equal(a.figure_height.assumption_id, "assume.figure_mold_scale");
  assert.ok(!g.assumptions.some((a) => a.id.startsWith("assume.debug_contacts.")), "debug contacts retired");
  for (const pl of g.players) assert.equal(pl.stick_handedness, "left");
  assert.ok(g.sources.some((s) => s.id === "user_statement_2026_09_30_players" && s.kind === "user_statement"));
  assert.equal(Object.keys(molds.prints).length, 12);
});

// Rigidity and handedness of the mold contacts under the pose functions (formerly iteration-10 tests).
const asset = g.figure_assets.find((a) => a.id === "fig.W-RD")!;
const all: Vec3[] = asset.contact_shapes.flatMap((c) => c.geometry!.points_mm as Vec3[]);
const blade = asset.contact_shapes.find((c) => c.kind === "blade")!.geometry!.points_mm as Vec3[];
const path = pathSampler("t", "skater", [[-50, 10], [80, -20], [150, 40]]);
const pose = (team: "W" | "E", u: number, th: number): Pose => {
  const r = skaterPose(path, team, { u_preview: u, thetaDeg: th });
  assert.ok(r.ok);
  return r as Pose;
};

test("contacts are rigid: pairwise distances, radius from the axis and heights preserved for any pose", () => {
  const ref = toWorld(pose("W", 0.1, 0), all);
  for (const [team, u, th] of [["W", 0.7, 33], ["E", 0.4, -120], ["E", 1, 725]] as const) {
    const p = pose(team, u, th);
    const w = toWorld(p, all);
    for (let i = 0; i < all.length; i += 3) for (let j = i + 1; j < all.length; j += 5) {
      const d0 = Math.hypot(ref[i]![0] - ref[j]![0], ref[i]![1] - ref[j]![1], ref[i]![2] - ref[j]![2]);
      const d1 = Math.hypot(w[i]![0] - w[j]![0], w[i]![1] - w[j]![1], w[i]![2] - w[j]![2]);
      assert.ok(Math.abs(d0 - d1) < 1e-9);
    }
    all.forEach((q, i) => {
      assert.ok(Math.abs(Math.hypot(w[i]![0] - p.pivot[0], w[i]![1] - p.pivot[1]) - Math.hypot(q[0], q[1])) < 1e-9);
      assert.ok(Math.abs(w[i]![2] - q[2]) < 1e-12);
    });
  }
});

test("handedness preserved for both teams (proper rotation, blade on the figure's left)", () => {
  const mid: Vec3 = [(blade[0]![0] + blade[1]![0]) / 2, (blade[0]![1] + blade[1]![1]) / 2, 0];
  for (const team of ["W", "E"] as const) for (const th of [0, 90, 181, -45, 400]) {
    const p = pose(team, 0.5, th);
    assert.ok(Math.abs(linearDeterminant(p.matrix) - 1) < 1e-12);
    const [o, f, b] = toWorld(p, [[0, 0, 0], [10, 0, 0], mid]);
    assert.ok((f![0] - o![0]) * (b![1] - o![1]) - (f![1] - o![1]) * (b![0] - o![0]) > 0, `${team} ${th}`);
  }
});
