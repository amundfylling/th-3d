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
      if (k === "skater") assert.notEqual(a.figure_height.status, "measured", "skater not measured yet");
    }
  }
  for (const a of byKind("goalie")) {
    assert.equal(a.figure_height.status, "measured");
    assert.equal(a.figure_height.value, 54);
    assert.deepEqual(a.figure_height.source_ids, ["user_measurement_2026_10_01_goalie"]);
  }
  for (const a of byKind("skater")) assert.equal(a.figure_height.status, "traced");
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

test("refinement round 2: held-out views fitted after the shape, close-up sheets and block lettering present", () => {
  for (const kind of ["skater", "goalie"]) {
    const h = JSON.parse(readFileSync(`validation/players/${kind}-heldout-fit.json`, "utf8"));
    assert.equal(h.held_out, true);
    const fitted = Object.keys(JSON.parse(readFileSync(`validation/players/${kind}-fit.json`, "utf8")).views);
    for (const [v, r] of Object.entries(h.views) as [string, any][]) {
      assert.ok(!fitted.includes(v), `${v} must not be a fitting view`);
      assert.ok(r.iou >= 0.65, `held-out ${v} IoU ${r.iou}`);
    }
    assert.ok(readFileSync(`validation/players/closeups-${kind}.png`).length > 100000);
  }
  for (const k of ["blue", "kit_SWE", "kit_FIN", "skin"]) assert.equal(molds.albedo_srgb[k].length, 3);
  const glyphs = readFileSync("assets/blender/print_glyphs.py", "utf8");
  assert.match(glyphs, /BLOCK digits/);
  for (const kind of ["skater", "goalie"]) assert.ok(molds.print_layout[kind].digit_h > 4);
});

test("goalie matches the user's ruler measurements; the skater keeps its own (overhead) scale", () => {
  const m = molds.measurements.goalie;
  assert.deepEqual([m.height_mm, m.blade_length_mm, m.blade_height_mm], [54, 26, 5.5]);
  assert.equal(m.uncertainty_mm, null, "unstated uncertainty stays null");
  for (const kit of KITS) {
    const r = rep.assets[`goalie_${kit}`];
    assert.ok(Math.abs(r.height_mm - 54) <= 0.1, `goalie height ${r.height_mm}`);
    assert.ok(Math.abs(r.blade_length_mm - 26) <= 0.05, `blade ${r.blade_length_mm}`);
    assert.ok(Math.abs(r.blade_height_mm - 5.5) <= 0.05, `blade height ${r.blade_height_mm}`);
  }
  assert.equal(rep.scales.skater, over.scale_k_mm_per_mold_unit, "skater scale from the overhead fit");
  assert.ok(Math.abs(rep.scales.goalie - molds.goalie.scale.k_mm_per_mold_unit) < 1e-4);
  assert.notEqual(rep.scales.goalie, rep.scales.skater);
  const src = g.sources.find((s) => s.id === "user_measurement_2026_10_01_goalie")!;
  assert.equal(src.kind, "user_measurement");
  const idx = JSON.parse(readFileSync("references/index.json", "utf8")).sources.find((s: any) => s.id === "user_goalie_measurement_sketch");
  assert.ok(idx && idx.sha256.length === 64);
});

test("refinement round 4: independent fresh frames scored at frozen cameras; lofted cuffs, moulded pads, smooth skin edges", () => {
  for (const kind of ["skater", "goalie"]) {
    const ind = JSON.parse(readFileSync(`validation/players/${kind}-independent-fit.json`, "utf8"));
    assert.equal(ind.role, "regression_reference", "formerly independent frames, inspected since");
    const used = [
      ...Object.keys(JSON.parse(readFileSync(`validation/players/${kind}-fit.json`, "utf8")).views),
      ...Object.keys(JSON.parse(readFileSync(`validation/players/${kind}-heldout-fit.json`, "utf8")).views),
    ];
    assert.ok(Object.keys(ind.views).length >= 4);
    for (const [v, r] of Object.entries(ind.views) as [string, any][]) {
      assert.ok(!used.includes(v), `${v} must not be a fitting or inspected view`);
      assert.ok(r.iou >= 0.65, `independent ${v} IoU ${r.iou}`);
    }
  }
  const sk = molds.skater.parts;
  assert.ok(sk.sleeves.lofts.gauntlet_r && sk.sleeves.lofts.gauntlet_l, "both gauntlets are lofted cuffs");
  assert.ok(Object.keys(sk.gloves.mboxes).length === 2, "one moulded hand block per glove");
  const go = molds.goalie;
  assert.deepEqual(Object.keys(go.boxes), [], "pads are moulded parts, not boxes");
  for (const n of ["pad_l", "pad_r"]) {
    const mb = go.parts[n].mboxes;
    const lows = Object.keys(mb).filter((k) => /^lo\d+$/.test(k)).sort((a, b) => Number(a.slice(2)) - Number(b.slice(2)));
    assert.ok(mb.upper && mb.knee && lows.length >= 2);
    assert.ok(mb[lows.at(-1)!].half_size[1] < mb.upper.half_size[1], "lower pad tapers toward the boot");
    assert.ok(go.pad_footprint[n].half_size.length === 3);
  }
  assert.ok(go.paint[0].refine >= 2, "skin borders refined");
});

test("refinement round 5: blocker board faces front-right and covers the pad; stick heel moved; finish data; skater scale frozen", () => {
  const go = molds.goalie;
  const board = go.parts.blocker.rboxes.board;
  const [, hw, hh] = board.half_size;
  assert.ok(hw >= 3.5 && hh >= 5.0, `board ${2 * hw} x ${2 * hh} mold units (photos ~8 x 12)`);
  const rz = board.rot_deg[2];
  assert.ok(rz <= -10 && rz >= -40, `board face azimuth ${rz} deg (front-right)`);
  assert.ok(Math.abs(board.centre[1] - -3.5) < 2, "board in front of the right pad");
  const [top, bottom] = go.stick.paddle;
  const hand = go.parts.blocker.rboxes.hand.centre;
  assert.ok(Math.hypot(top[0] - hand[0], top[1] - hand[1], top[2] - hand[2]) < 2.5, "paddle top held in the blocker hand");
  assert.ok(bottom[2] < top[2]);
  const [heel, toe] = go.stick.blade;
  assert.ok(Math.abs(toe[1] - heel[1] - 26 / go.scale.k_mm_per_mold_unit) < 0.05, "measured blade length kept");
  for (const k of ["plastic_roughness", "coat_weight", "coat_roughness", "metal_roughness"]) assert.equal(typeof molds.finish[k], "number");
  assert.equal(molds.finish.status, "assumed");
  assert.equal(over.scale_k_mm_per_mold_unit, 1.0814, "skater scale frozen for round 5");
  const cuff = molds.skater.parts.sleeves.lofts.gauntlet_r;
  assert.ok(cuff.subsurf >= 1 && cuff.lip >= 0.75, "softened upper cuff rim");
});

test("refinement round 6 (skater): boxy helmet without side knobs, forward face, collar band, flat gauntlet over the hand", () => {
  const P = molds.skater.parts;
  assert.ok(P.helmet.mboxes.dome, "helmet dome is one rounded box");
  assert.equal(P.helmet.ellipsoids.brim, undefined, "no brim roll (it formed side knobs)");
  const env = P.face.face_sections.envelope; // round 12: front measured in the helmet's frame (nose x ~13.4)
  const front = env.pivot[0] + Math.max(...env.levels.map((q: any) => q.front)) * Math.cos((env.yaw_deg * Math.PI) / 180);
  assert.ok(front > 13 && front < 14.6, `face front under the helmet front edge (${front.toFixed(2)})`);
  const band = Object.keys(P.collar.ellipsoids).filter((k) => k.startsWith("band"));
  assert.ok(band.length >= 20, "collar is a continuous band");
  const cuff = P.sleeves.lofts.gauntlet_r;
  assert.ok(cuff.mouth_r[1] <= 2.2 && cuff.mouth_r[0] >= 6, "flattened gauntlet: long rim, thin across");
  assert.equal(Object.keys(P.gloves.capsules).filter((k) => k.startsWith("u_")).length, 0, "upper hand hidden in the gauntlet");
  const sk = rep.assets.skater_SWE, fi = rep.assets.skater_FIN;
  assert.deepEqual([sk.height_mm, sk.blade_length_mm], [fi.height_mm, fi.blade_length_mm], "one shared mold");
});

test("refinement round 7 (skater): thin collar lying on the jersey, neck strip below the helmet, softened helmet", () => {
  const P = molds.skater.parts;
  const band = Object.entries(P.collar.ellipsoids).filter(([k]) => k.startsWith("band")).map(([, v]) => v as any);
  assert.ok(band.length >= 40, "continuous band");
  for (const e of band) assert.ok(e.semi_axes[2] <= 0.4, "thin band (flat across)");
  assert.ok(P.helmet.mboxes.dome.round >= 2.6, "rounded helmet corners");
  assert.ok(P.face.capsules.neck_back, "neck shows between the collar and the helmet at the back");
});

test("refinement round 8 (skater): broad thin collar footprint, level rear helmet edge, flatter crown", () => {
  const P = molds.skater.parts;
  const band = Object.values(P.collar.ellipsoids).filter((e: any) => e.semi_axes[2] <= 0.4) as any[];
  assert.equal(band.length, Object.keys(P.collar.ellipsoids).length, "every collar element is thin");
  const widest = Math.max(...band.map((e) => e.semi_axes[1]));
  assert.ok(widest >= 1.0, "broad strips at the back");
  assert.equal(P.helmet.ellipsoids.crown, undefined, "no crown fill (it raised the top above the profile)");
  assert.equal((P.helmet.negative_ellipsoids ?? {}).nape_cut, undefined, "no central notch in the rear helmet edge");
  const nb = P.face.capsules.neck_back;
  assert.ok(nb.b[2] <= 40.2, "back neck column stays below the helmet edge");
  assert.ok(Math.abs(rep.assets.skater_SWE.height_mm - 51.24) < 0.3, `helmet top near the profile reading (${rep.assets.skater_SWE.height_mm} mm)`);
});

test("refinement round 9 (skater face), carried into round 12: taper, small nose, turned with the head", () => {
  const env = molds.skater.parts.face.face_sections.envelope;
  const W = env.levels.map((q: any) => q.half_width);
  assert.ok(Math.max(...W) > Math.min(...W) * 2.5, "broad under the helmet, tapering to a narrow chin");
  assert.ok(env.relief.nose.h <= 0.5, "small moulded nose");
  // round 13: the face is turned WITH the head (rigid head_pose), not under a straight helmet
  assert.ok(molds.skater.head_pose.yaw_deg + env.yaw_deg > 10, "face turned toward the figure's left with the head");
});

test("refinement round 11/12 (skater face only): one face surface, no lobes, shallow central relief", () => {
  const F = molds.skater.parts.face;
  assert.equal(Object.keys(F.ellipsoids ?? {}).length, 0, "no face ellipsoid lobes (nose/chin/cheeks)");
  assert.equal(Object.keys(F.negative_ellipsoids ?? {}).length, 0, "no carved mouth ellipsoid");
  assert.equal(F.face_lofts, undefined, "round-11 side-profile extrusion removed (it spread the nose height across the face)");
  assert.ok(F.capsules.neck && F.capsules.neck_back, "neck capsules unchanged");
  const sk = rep.assets.skater_SWE, fi = rep.assets.skater_FIN;
  assert.deepEqual([sk.height_mm, sk.blade_length_mm], [fi.height_mm, fi.blade_length_mm], "one shared mold for both kits");
});

test("refinement round 10 (skater upper cuff only): level opening, longer elbow tip, rim marks recorded", () => {
  const c = molds.skater.parts.sleeves.lofts.gauntlet_r;
  assert.ok(Math.abs(c.mouth_n[1]) < 0.1, "opening plane level across the figure (inner corner not raised)");
  assert.ok(c.mouth_c[1] - c.mouth_r[0] < -17, "elbow tip reaches the photographed outer point");
  assert.equal(c.warp, 0, "no saddle on the rim (front frame shows a rim that rises from the tip, then runs level)");
  const marks = JSON.parse(readFileSync("data/cuff-marks-r10.json", "utf8"));
  for (const v of ["skater-video-t00.00", "skater-video-t13.25", "skater-video-t14.50"]) assert.ok(marks.views[v].rim.length >= 1, v);
});

test("refinement round 12 (skater face only): horizontal cross-sections, depth falls off across the width", () => {
  const F = molds.skater.parts.face;
  const env = F.face_sections.envelope;
  assert.ok(env.levels.length >= 6, "stack of horizontal sections");
  assert.ok(env.n_front < 2, "pointed front section: a distinct centreline, cheeks recede from it");
  for (const q of env.levels) assert.ok(q.front > 0 && q.half_width > 0, `level z ${q.z}`);
  // nose relief stays on the centreline: its lateral falloff is narrower than the narrowest face section
  const minW = Math.min(...env.levels.map((q: any) => q.half_width));
  assert.ok(env.relief.nose.sigma < minW * 0.5, "nose projection vanishes before the cheeks");
  assert.ok(env.relief.nose.h <= 0.5 && env.relief.mouth.h <= 0.2, "restrained relief");
  assert.equal(env.jaw_slope, undefined, "no sheared jaw (it folded the cheek into a diagonal seam)");
  assert.ok(F.face_blend && F.face_blend.radius > 0, "face and neck blended into one skin surface");
  assert.equal(molds.skater.parts.helmet.mboxes.edge_r, undefined, "no strap-like helmet edge extension (tested and rejected in round 12)");
});

test("refinement round 13 (skater head): helmet and face are one rigid head, turned as a unit; face centred in the opening", () => {
  const sk = molds.skater;
  const hp = sk.head_pose;
  assert.deepEqual([...hp.parts].sort(), ["face", "helmet"], "helmet and face (with the neck capsules) posed together");
  // helmet-only orientation search at body-only cameras: best turn ~20 deg left, tipped forward; tilt weakly determined
  assert.ok(hp.yaw_deg >= 15 && hp.yaw_deg <= 25, `head turn ${hp.yaw_deg}`);
  assert.ok(hp.pitch_deg >= 0 && hp.pitch_deg <= 10, `head forward tip ${hp.pitch_deg}`);
  assert.ok(Math.abs(hp.roll_deg) <= 10, `head side tilt ${hp.roll_deg} (weakly determined; positive tilts made the face lean the wrong way in 13.25 s)`);
  const env = sk.parts.face.face_sections.envelope;
  assert.ok(Math.abs(env.yaw_deg) < 5, "face not turned relative to the helmet (round 12's 28 deg face under a straight helmet was the root cause)");
  assert.ok(Math.abs(env.pivot[1] + 1.7) < 0.5, "face centreline on the helmet's centreline");
  assert.ok(sk.parts.helmet.negative_ellipsoids.brow_arch.semi_axes[1] >= 3, "wider front opening (photographed edge rises toward the front)");
  assert.ok(sk.parts.torso.ellipsoids.traps.centre[2] > 36.5, "upper torso raised under the head");
  const neck = sk.parts.face.capsules.neck;
  assert.ok(neck.radius <= 1.6 && neck.b[0] <= 7.5, "front neck capsule stays inside the narrower face (no knob beside the chin)");
  const s = rep.assets.skater_SWE, f = rep.assets.skater_FIN;
  assert.deepEqual([s.height_mm, s.blade_length_mm], [f.height_mm, f.blade_length_mm], "one shared mold for both kits");
});
