// Iteration 14: W-RD body proxy is one rigid object that keeps the iteration-13 contact asset.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { readGlbJson } from "./rink-asset.test.ts";

const rep = JSON.parse(readFileSync("validation/14-skater-body-report.json", "utf8"));
const gltf = readGlbJson("assets/figures/skater_W-RD.glb");

test("body proxy meets the pre-set review thresholds", () => {
  assert.ok(rep.top_silhouette_iou >= 0.75, `IoU ${rep.top_silhouette_iou}`);
  assert.ok(rep.height_mm >= 51.3 && rep.height_mm <= 62.7, `height ${rep.height_mm}`);
  assert.ok(rep.body_zmin_mm >= 0, "no body part below the ice");
  assert.equal(rep.lower_asset_preserved, true);
  assert.equal(rep.pass, true);
});

test("one rigid node at the fixture axis, no skeleton or animation", () => {
  assert.equal(gltf.nodes.length, 1);
  assert.equal(gltf.nodes[0].name, "Skater.W-RD");
  assert.equal(gltf.nodes[0].translation, undefined);
  assert.equal(gltf.skins, undefined);
  assert.equal(gltf.animations, undefined);
});

test("only the overhead view is labelled as W-RD evidence", () => {
  const ev = rep.evidence_by_view as Record<string, string>;
  assert.match(ev.overhead!, /EVIDENCE/);
  for (const v of ["front", "back", "left", "right"]) assert.match(ev[v]!, /NO W-RD evidence/);
});
