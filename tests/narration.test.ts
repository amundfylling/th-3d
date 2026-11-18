// Narration timing (scripts/video/narration.ts): anchors resolve from the trace + presentation and follow retuning. Pure.
import { test } from "node:test";
import assert from "node:assert/strict";
import { plan } from "../scripts/video/narration.ts";

test("hjerpefinte narration anchors land on the event frames", () => {
  const p = plan("hjerpefinte");
  const by = Object.fromEntries(p.planned.map((x) => [x.id, x]));
  assert.ok(Math.abs(by.shot!.shown_err_ms!) < 1);
  assert.ok(Math.abs(by.feint!.shown_err_ms!) < 1);
  assert.ok(by.feint!.start_s < by.shot!.start_s);
});

test("narration follows a re-tuned slow-motion rate", () => {
  const a = plan("hjerpefinte");
  const b = plan("hjerpefinte", (s) => { for (const x of s.segments) if (x.id === "shot_in") x.rate = 0.1; });
  const t = (p: typeof a, id: string) => p.planned.find((x) => x.id === id)!.start_s;
  assert.ok(t(b, "shot") < t(a, "shot"), "shot line moves earlier when shot_in plays faster");
  assert.ok(Math.abs(b.planned.find((x) => x.id === "shot")!.shown_err_ms!) < 1, "and still lands on the contact frame");
});
