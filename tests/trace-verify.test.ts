// Contact check of every saved trace from its file alone (scripts/shotlib/verify.py, CLAUDE.md "Contact physics").
// The other trace tests read the checks file each generator wrote about itself; this one measures the saved puck
// against all twelve figures, the boards and the goals again. Python tests in tests/traces/ (numpy and shapely; set
// PYTHON to use another interpreter).
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

const py = process.env.PYTHON ?? "python3";

test("saved traces: no overlap anywhere, measured from the trace files (python unittest)", (t) => {
  const probe = spawnSync(py, ["-c", "import numpy, shapely"], { encoding: "utf8" });
  if (probe.error || probe.status !== 0) return t.skip(`${py} has no numpy + shapely: the saved traces were NOT re-checked here`);
  const r = spawnSync(py, ["-m", "unittest", "discover", "-s", "tests/traces", "-p", "test_*.py"], { encoding: "utf8", timeout: 600_000 });
  assert.equal(r.status, 0, `trace checks failed:\n${r.stderr}${r.stdout}`);
  assert.match(r.stderr, /\nOK/, r.stderr);
});
