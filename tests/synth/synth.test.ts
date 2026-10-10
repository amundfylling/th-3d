// Python unit tests of the synth / NM26 helpers (tests/synth/test_*.py), run by `npm test` through node --test.
// They need python3 with numpy only; set PYTHON to use another interpreter.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

test("synth helpers: python unittest (pivot_to_u, smoothing, blade contact)", () => {
  const py = process.env.PYTHON ?? "python3";
  const r = spawnSync(py, ["-m", "unittest", "discover", "-s", "tests/synth", "-p", "test_*.py"], {
    encoding: "utf8",
    timeout: 300_000,
  });
  assert.equal(r.error, undefined, `could not run ${py}: ${r.error?.message}`);
  assert.equal(r.status, 0, `python tests failed:\n${r.stderr}${r.stdout}`);
  assert.match(r.stderr, /\nOK/, r.stderr);
});
