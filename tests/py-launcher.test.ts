// scripts/py.ts: the one rule for which Python runs a project script (docs/tools.md, "Which Python runs a script").
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { BLENDER_VENV_PYTHON, resolvePython, testPython } from "../scripts/py.ts";

const yes = (): boolean => true;
const no = (): boolean => false;
const launch = (args: string[], env: Record<string, string | undefined> = {}) =>
  spawnSync(process.execPath, ["scripts/py.ts", ...args], { encoding: "utf8", env: { ...process.env, ...env } });

// every combination of the three inputs: [PYTHON, NM26_PY, venv exists] -> [command, source]
const CASES: [string | undefined, string | undefined, boolean, string, string][] = [
  ["/a/py", "/b/py", true, "/a/py", "PYTHON"],
  ["/a/py", "/b/py", false, "/a/py", "PYTHON"],
  ["/a/py", undefined, true, "/a/py", "PYTHON"],
  ["/a/py", undefined, false, "/a/py", "PYTHON"],
  [undefined, "/b/py", true, "/b/py", "NM26_PY"],
  [undefined, "/b/py", false, "/b/py", "NM26_PY"],
  [undefined, undefined, true, BLENDER_VENV_PYTHON, "blender-venv"],
  [undefined, undefined, false, "python3", "python3"],
  ["", "", true, BLENDER_VENV_PYTHON, "blender-venv"], // empty counts as unset
  ["", "/b/py", false, "/b/py", "NM26_PY"],
];

test("py launcher: PYTHON, then NM26_PY, then the Blender venv if it exists, then python3", () => {
  for (const [PYTHON, NM26_PY, venv, command, source] of CASES) {
    assert.deepEqual(resolvePython({ PYTHON, NM26_PY }, venv ? yes : no), { command, source }, JSON.stringify([PYTHON, NM26_PY, venv]));
  }
});

test("py launcher: the tests use PYTHON or python3 and never pick the venv by themselves", () => {
  assert.equal(testPython({}), "python3");
  assert.equal(testPython({ PYTHON: "" }), "python3");
  assert.equal(testPython({ PYTHON: "/a/py", NM26_PY: "/b/py" }), "/a/py");
  assert.equal(testPython({ NM26_PY: "/b/py" }), "python3");
});

test("py launcher: runs the script with its arguments, working directory and exit code", () => {
  const tmp = mkdtempSync(path.join(tmpdir(), "py-"));
  try {
    const script = path.join(tmp, "probe.py");
    writeFileSync(script, 'import json, os, sys\nprint(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd()}))\nsys.exit(int(sys.argv[1]))\n');
    for (const code of [0, 3]) {
      const r = launch([script, String(code), "--flag", "two words"], { PYTHON: testPython(), NM26_PY: undefined });
      assert.equal(r.status, code, r.stderr);
      assert.deepEqual(JSON.parse(r.stdout), { argv: [String(code), "--flag", "two words"], cwd: process.cwd() });
    }
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("py launcher: a missing interpreter is named, with what to set", () => {
  const r = launch(["scripts/build-move.py"], { PYTHON: "/no/such/python" });
  assert.equal(r.status, 127);
  assert.match(r.stderr, /cannot run \/no\/such\/python \(\$PYTHON\)/);
  assert.match(r.stderr, /set PYTHON/);
});

test("py launcher: --which prints the choice, no arguments prints the usage", () => {
  const which = launch(["--which"], { PYTHON: "/a/py" });
  assert.equal(which.status, 0);
  assert.equal(which.stdout.trim(), "/a/py  (PYTHON)");
  const none = launch([]);
  assert.equal(none.status, 2);
  assert.match(none.stderr, /usage/);
});

test("py launcher: package.json names no interpreter path, and every script it launches exists", () => {
  const scripts = JSON.parse(readFileSync("package.json", "utf8")).scripts as Record<string, string>;
  let launched = 0;
  for (const [name, cmd] of Object.entries(scripts)) {
    assert.doesNotMatch(cmd, /\/(venvs?|bin)\/[^ ]*python/, `${name}: use node scripts/py.ts`);
    for (const m of cmd.matchAll(/node scripts\/py\.ts (\S+\.py)/g)) {
      launched += 1;
      assert.doesNotThrow(() => readFileSync(m[1]!), `${name}: ${m[1]}`);
    }
  }
  assert.ok(launched >= 60, `${launched} launcher calls`);
});

test("py launcher: the rebuild runner picks the same interpreter", () => {
  const code = [
    "import importlib.util, json, sys",
    'spec = importlib.util.spec_from_file_location("nm26_rebuild", "scripts/pipeline/nm26_rebuild.py")',
    "m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m)",
    "cases = json.loads(sys.argv[1])",
    "print(json.dumps([[m.step_python({k: v for k, v in (('PYTHON', a), ('NM26_PY', b)) if v is not None}, lambda p, e=e: e), m.BLENDER_PY, sys.executable] for a, b, e in cases]))",
  ].join("\n");
  const r = spawnSync(testPython(), ["-c", code, JSON.stringify(CASES.map(([a, b, e]) => [a ?? null, b ?? null, e]))], { encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr);
  const out = JSON.parse(r.stdout) as [string, string, string][];
  CASES.forEach(([a, b, e, command, source], i) => {
    const [got, venv, self] = out[i]!;
    assert.equal(venv, BLENDER_VENV_PYTHON);
    // the runner's last fallback is its own interpreter where the launcher's is python3
    assert.equal(got, source === "python3" ? self : command, JSON.stringify([a, b, e]));
  });
});
