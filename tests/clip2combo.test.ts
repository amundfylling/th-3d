// Goal clip -> combo pipeline (scripts/clip2combo.py, docs/clip2combo.md). Python unittest, numpy only (set PYTHON to use another interpreter).
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

const py = process.env.PYTHON ?? "python3";

test("clip2combo: the pipeline gives well-formed th-combo/1 drafts for the 25 marked goals (python unittest)", (t) => {
  const probe = spawnSync(py, ["-c", "import numpy"], { encoding: "utf8" });
  if (probe.error || probe.status !== 0) return t.skip(`${py} has no numpy`);
  const r = spawnSync(py, ["-m", "unittest", "discover", "-s", "tests/clip2combo", "-p", "test_*.py"], { encoding: "utf8", timeout: 300_000 });
  assert.equal(r.status, 0, `clip2combo checks failed:\n${r.stderr}${r.stdout}`);
  assert.match(r.stderr, /\nOK/, r.stderr);
});
