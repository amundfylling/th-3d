import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { traceEvaluator, type ShotTrace } from "../src/model/trace.ts";

const trace = JSON.parse(readFileSync("data/traces/shovel-17.trace.json", "utf8"));
const obs = JSON.parse(readFileSync("shots/21-shovel/observations.json", "utf8"));
const geo = JSON.parse(readFileSync("data/geometry.json", "utf8"));
const checks = JSON.parse(readFileSync("shots/22-shovel/checks.json", "utf8"));

test("iteration 22: trace status comes from the recorded user review, never silently accepted", () => {
  const inputs = JSON.parse(readFileSync("shots/22-shovel/inputs.json", "utf8"));
  assert.equal(trace.schema, "shot-trace/1");
  if (!inputs.user_review) {
    assert.equal(trace.status, "proposed");
    return;
  }
  assert.equal(trace.status, inputs.user_review.status_after_review);
  assert.equal(trace.review.date, inputs.user_review.date);
  assert.equal(trace.review.contacts_confirmed, true);
});

test("iteration 22: trace references the current geometry, assets and the pinned recording", () => {
  assert.equal(trace.geometry_version, geo.geometry_version);
  assert.equal(trace.source.recording_sha256, obs.source.sha256);
  for (const k of ["figure_molds_sha256", "skater_glb_sha256", "goalie_glb_sha256"]) assert.match(trace.asset_refs[k], /^[0-9a-f]{64}$/, k);
  const paths = new Set(geo.fixture_paths.map((p: any) => p.id));
  for (const [pid, f] of Object.entries(trace.figures) as [string, any][]) {
    if (typeof f !== "object") continue;
    assert.ok(paths.has(f.fixture_path_id), pid);
    for (const k of f.arc_keyframes) assert.ok(k.sigma_mm === null || k.sigma_mm > 0, `${pid} sigma ${k.sigma_mm}: unknown is null, never zero`);
    for (const k of f.theta_keyframes) assert.ok(k.sigma_deg === null || k.sigma_deg > 0, `${pid} theta sigma`);
  }
});

test("iteration 22: contact events carry observed intervals; replay conflict is explicit", () => {
  const ev = Object.fromEntries(trace.events.map((e: any) => [e.id, e]));
  for (const id of ["pass.release", "contact.W-C_reception", "shot.separation", "goal_entry"]) assert.ok(ev[id], id);
  for (const id of ["pass.release", "contact.W-C_reception", "goal_entry"]) {
    const [a, b] = ev[id].observed_interval;
    assert.equal(ev[id].inside_observed_interval, ev[id].t_estimate >= a && ev[id].t_estimate <= b, id);
  }
  assert.ok(ev["pass.release"].t_estimate < ev["contact.W-C_reception"].t_estimate);
  assert.ok(ev["contact.W-C_reception"].t_estimate < ev["shot.separation"].t_estimate);
  assert.ok(ev["shot.separation"].t_estimate < ev["goal_entry"].t_estimate);
  const run = ev["contact.W-C_reception"].w_c_run_timing;
  assert.equal(typeof run.rule_reaches_far_corner, "boolean");
  const sep = ev["shot.separation"];
  if (/^assumed/.test(sep.status)) {
    // an assumed direction is labelled as such, stated as a limitation, and lands inside the far-corner window
    assert.equal(run.rule_reaches_far_corner, false);
    assert.ok(trace.limitations.some((l: string) => l.startsWith("ASSUMED SHOT DIRECTION")));
    const [lo, hi] = checks.shot_direction_diagnostic.clear_plus_y_directions_deg;
    assert.ok(sep.direction_deg >= lo && sep.direction_deg <= hi, `${sep.direction_deg} outside ${lo}-${hi}`);
  }
  const g = ev["goal_entry"];
  assert.ok(g.goal_line_y_mm > 0.53 && g.goal_line_y_mm <= g.mouth_centre_window_y_mm[1], "far corner (+y side) inside the mouth");
});

test("contact physics: the puck never overlaps a figure, the boards or the goal (CLAUDE.md), except user-approved exceptions", () => {
  const inputs = JSON.parse(readFileSync("shots/22-shovel/inputs.json", "utf8"));
  assert.ok(checks.penetration_tolerance_mm <= 0.1);
  assert.deepEqual(checks.unexpected_penetrations, [], JSON.stringify(checks.unexpected_penetrations));
  // the clearance scan covers the whole trace window, every phase
  const phases = new Set(checks.min_clearance_by_obstacle_and_phase.map((r: any) => r.phase));
  for (const ph of trace.puck.phases) if (ph.t[1] === null || ph.t[1] > ph.t[0]) assert.ok(phases.has(ph.id), `phase ${ph.id} not checked`);
  for (const r of checks.min_clearance_by_obstacle_and_phase) {
    const ex = (inputs.approved_overlap_exceptions ?? []).find((x: any) => x.obstacle === r.obstacle && x.phase === r.phase);
    assert.ok(r.min_clearance_mm >= -checks.penetration_tolerance_mm || (ex && r.min_clearance_mm >= -ex.max_overlap_mm), `${r.obstacle} ${r.phase} ${r.min_clearance_mm}`);
  }
  for (const [id, a] of Object.entries(checks.approved_exceptions) as [string, any][]) {
    const ex = inputs.approved_overlap_exceptions.find((x: any) => x.id === id);
    assert.ok(ex && /user/.test(ex.approved_by), `${id} needs the user's approval`);
    assert.ok(a.worst_mm >= -ex.max_overlap_mm, id);
  }
  assert.ok(checks.max_puck_step_mm < 2, "no puck jumps between samples");
});

test("prep foot drag (user 2026-10-05): at every observation the puck touches W-RW's foot, within the reading uncertainty", () => {
  assert.ok(checks.prep_foot_contacts.length >= 8);
  for (const c of checks.prep_foot_contacts) assert.ok(c.push_from_observed_mm <= c.observed_sigma_mm, `frame ${c.frame}: ${c.push_from_observed_mm} mm`);
  // slight turns at the board end (sharp frames 30, 68): within 30 deg of facing up the ice
  for (const fr of [30, 68]) {
    const c = checks.prep_foot_contacts.find((x: any) => x.frame === fr);
    assert.ok(Math.abs(((c.heading_deg - c.visual_heading_deg + 540) % 360) - 180) <= 30, `frame ${fr} heading ${c.heading_deg}`);
  }
});

test("iteration 22: fast motion is checked between samples (puck step < 2 mm)", () => {
  assert.ok(checks.max_puck_step_mm < 2, `${checks.max_puck_step_mm}`);
  assert.ok(checks.sampling_s <= 0.0005);
});

test("iteration 22: TypeScript evaluator reproduces the script's evaluation samples", () => {
  const ev = traceEvaluator(trace as ShotTrace);
  let worst = 0;
  for (const s of trace.evaluation_samples) {
    const st = ev(s.t);
    for (const [pid, v] of Object.entries(s) as [string, any][]) {
      if (pid === "t") continue;
      if (pid === "puck") {
        worst = Math.max(worst, Math.abs(st.puck.x_mm - v[0]), Math.abs(st.puck.y_mm - v[1]));
        continue;
      }
      const f = st.figures[pid];
      assert.ok(f, pid);
      worst = Math.max(worst, Math.abs(f.arc_mm - v.arc_mm), Math.abs(f.theta_deg - v.theta_deg));
    }
  }
  assert.ok(worst < 1e-3, `worst difference ${worst}`);
});

test("iteration 22: evaluation does not depend on call order", () => {
  const ev = traceEvaluator(trace as ShotTrace);
  const ts = trace.evaluation_samples.map((s: any) => s.t);
  const fwd = ts.map((t: number) => ev(t));
  const rev = [...ts].reverse().map((t: number) => ev(t)).reverse();
  assert.deepEqual(fwd, rev);
});
