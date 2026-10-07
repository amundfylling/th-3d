import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const read = (p: string): string => readFileSync(p, "utf8");
const json = (p: string) => JSON.parse(read(p));
const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");
const D = "data/games/fylling-vs-moe-2022";

test("game tracking: the recording and the rules are indexed and unchanged", () => {
  const idx = json("references/index.json");
  for (const p of ["references/games/fylling-vs-moe-trondheim-open-2022-final.mov", "references/rules/ithf-game-rules.pdf"]) {
    const s = idx.sources.find((x: { local_path: string }) => x.local_path === p);
    assert.ok(s, p);
    assert.equal(sha(p), s.sha256, p);
  }
});

test("game tracking: stabilisation covers every frame; calibration fits the slots and lines", () => {
  const st = json(`${D}/stabilisation.json`);
  assert.equal(st.frames, 7756);
  assert.equal(st.H_video_to_ref.length, 7756);
  const c = json(`${D}/calibration.json`);
  assert.equal(c.status, "assumed");
  assert.ok(c.residuals.line_rms_crop_px < 1, "blue lines");
  assert.ok(c.residuals.slot_points_median_distance_crop_px < 1.5, "slot centrelines on the image slots");
});

test("game tracking: the puck track stays inside the rink and moves continuously", () => {
  const t = json(`${D}/puck-track.json`);
  const rows: number[][] = t.rows;
  assert.ok(rows.length > 1000);
  let prev: number[] | undefined;
  for (const r of rows) {
    assert.ok(Math.abs(r[2]!) < 440 && Math.abs(r[3]!) < 240, `frame ${r[0]}`);
    if (prev && r[0]! - prev[0]! === 1) assert.ok(Math.hypot(r[2]! - prev[2]!, r[3]! - prev[3]!) <= t.tracker.d_max_mm_per_frame + 1e-6, `jump at ${r[0]}`);
    prev = r;
  }
  assert.ok(t.match_frames_seen_fraction > 0.3);
});

test("game tracking: possession accounts for every match second, goalies not counted", () => {
  const p = json(`${D}/possession.json`);
  const per = p.per_skater as Record<string, { team: string; time_s: number; times: number }>;
  assert.equal(Object.keys(per).length, 10);
  assert.ok(Object.keys(per).every((k) => !k.endsWith("-G")));
  const on = Object.values(per).reduce((a, v) => a + v.time_s, 0);
  const nobody = Object.values(p.nobody_s as Record<string, number>).reduce((a, v) => a + v, 0);
  assert.ok(Math.abs(on + nobody - p.match_s) < 0.1, `${on} + ${nobody} vs ${p.match_s}`);
  assert.equal(p.match_s, 300);
  for (const t of ["W", "E"]) {
    const s = Object.values(per).filter((v) => v.team === t);
    assert.ok(Math.abs(s.reduce((a, v) => a + v.time_s, 0) - p.per_team[t].time_s) < 0.05);
    assert.equal(s.reduce((a, v) => a + v.times, 0), p.per_team[t].times);
  }
  // episodes are contiguous and cover the match
  let end = 0;
  for (const [, a, b] of p.episodes as [string, number, number][]) {
    assert.ok(Math.abs(a - end) < 1e-6 && b > a);
    end = b;
  }
  assert.ok(Math.abs(end - p.match_s) < 1e-6);
});

test("game tracking: passes follow the possession episodes; lines run between detected puck positions", () => {
  const p = json(`${D}/possession.json`);
  const ps = json(`${D}/passes.json`);
  const tr = json(`${D}/puck-track.json`);
  const at = new Map<number, number[]>((tr.rows as number[][]).map((r) => [Math.round((r[0]! / 25 - 7.5) * 100), r]));
  const sk = (p.episodes as [string, number, number][]).filter((e) => e[0] !== "nobody");
  let measured = 0;
  for (const e of ps.events) {
    const i = sk.findIndex((x) => x[0] === e.from && Math.abs(x[2] - e.t_poss_end) < 0.011);
    assert.ok(i >= 0 && sk[i + 1]![0] === e.to && Math.abs(sk[i + 1]![1] - e.t_poss_start) < 0.011, `${e.from}->${e.to} ${e.t_poss_end}`);
    assert.ok(e.transit_s <= ps.parameters.max_transit_s + 1e-9);
    if (!e.measured) continue;
    measured++;
    // both ends of the line are puck detections at the release and reception times
    for (const [t, q] of [[e.t_release, e.start_mm], [e.t_reception, e.end_mm]] as [number, number[]][]) {
      const r = at.get(Math.round(t * 100));
      assert.ok(r && Math.abs(r[2]! - q[0]!) < 0.11 && Math.abs(r[3]! - q[1]!) < 0.11, `${e.from}->${e.to} end at ${t}`);
    }
    assert.ok(e.t_release < e.t_reception && e.fit_residual_mm <= ps.parameters.tol_mm);
    assert.equal(e.line_mm.length, e.bounces + 2);
  }
  assert.equal(measured, ps.quality.measured_lines + ps.events.filter((e: { kind: string; measured: boolean }) => e.kind === "battle" && e.measured).length);
  for (const t of ["W", "E"]) assert.equal(ps.summary[t].passes, ps.events.filter((e: { kind: string; team: string }) => e.kind === "pass" && e.team === t).length);
});
