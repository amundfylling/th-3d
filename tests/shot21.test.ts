import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const obs = JSON.parse(readFileSync("shots/21-shovel/observations.json", "utf8"));
const geo = JSON.parse(readFileSync("data/geometry.json", "utf8"));

test("iteration 21: observation record references the pinned source and the current geometry", () => {
  assert.equal(obs.source.sha256, "65eca3cd30a39eb7a90f559936fbb0ffffdad64f5a22165eca4734928e557886");
  assert.equal(obs.geometry_version, geo.geometry_version);
  assert.match(obs.status, /not reviewed by the user/);
  assert.match(obs.not_done, /no motion fitting/);
});

test("iteration 21: content frame rate measured, not taken from the container", () => {
  const seg = obs.timing.segments[1];
  assert.ok(seg.content_rate_fps > 20 && seg.content_rate_fps < 30, `content ${seg.content_rate_fps} fps`);
  assert.ok(obs.source.decoder_container_fps > 50, "container rate is the screen recording");
});

test("iteration 21: observed figures map to stable IDs on existing fixture paths", () => {
  const paths = new Set(geo.fixture_paths.map((p: any) => p.id));
  for (const [pid, f] of Object.entries(obs.figures) as [string, any][]) {
    assert.ok(paths.has(f.fixture_path_id), pid);
    for (const o of f.observations) assert.ok(o.arc_mm >= 0 && o.arc_mm <= o.slot_length_mm + 1e-6, `${pid} frame ${o.recording_frame}`);
  }
  assert.ok(obs.figures["W-C"] && obs.figures["W-RW"], "shooter and passer");
});

test("iteration 21: camera mapping consistent; contacts are intervals, never exact", () => {
  assert.ok(obs.camera_seg1.fit.rms_px < 10 && obs.camera_seg1.fit.leave_one_out_rms_px < 20, JSON.stringify(obs.camera_seg1.fit));
  for (const e of obs.events) {
    assert.ok(e.interval_s[0] <= e.interval_s[1], e.id);
    if ("exact_time" in e) assert.equal(e.exact_time, null, `${e.id} must not claim an exact contact time`);
  }
  const hidden = obs.puck.observations.filter((p: any) => p.image_px === null);
  assert.ok(hidden.length >= 3, "occluded puck samples recorded as not visible, not interpolated");
});
