// The one place that decides which Python runs a project script.
//
//   node scripts/py.ts scripts/ikv-trace.py [args...]     run a script with the chosen interpreter
//   node scripts/py.ts --which                            print the choice and where it came from
//
// Order, first match:
//   1. $PYTHON                           (the variable the tests and scripts/video.ts already read)
//   2. $NM26_PY                          (the older name of scripts/pipeline/nm26_rebuild.py; still honoured)
//   3. /root/venvs/blender/bin/python    if it exists: the pinned venv of docs/pipeline.md section 0 (bpy 4.5, NumPy 1.26,
//                                        OpenCV 4.10). Committed outputs were made with it.
//   4. python3
//
// Before this, 34 npm scripts named the venv path outright and failed with "not found" in any container without it,
// also for scripts that need only numpy; the rebuild runner had its own rule and the tests a third. The runner follows
// the same order (step_python in nm26_rebuild.py); tests/py-launcher.test.ts holds the two together.
//
// The launcher adds nothing else: same arguments, same working directory, same exit code. A script that needs a module
// the chosen Python lacks fails with Python's own ModuleNotFoundError.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const BLENDER_VENV_PYTHON = "/root/venvs/blender/bin/python";

export interface PythonChoice {
  command: string;
  source: "PYTHON" | "NM26_PY" | "blender-venv" | "python3";
}

type Env = Record<string, string | undefined>;

/** The interpreter for pipeline scripts (order above). Empty variables count as unset. */
export function resolvePython(env: Env = process.env, exists: (p: string) => boolean = existsSync): PythonChoice {
  if (env.PYTHON) return { command: env.PYTHON, source: "PYTHON" };
  if (env.NM26_PY) return { command: env.NM26_PY, source: "NM26_PY" };
  if (exists(BLENDER_VENV_PYTHON)) return { command: BLENDER_VENV_PYTHON, source: "blender-venv" };
  return { command: "python3", source: "python3" };
}

/**
 * The interpreter for the test suite and other light helpers: $PYTHON, else python3. Never the Blender venv by
 * itself, so `npm test` gives the same result whether or not that venv is installed.
 */
export function testPython(env: Env = process.env): string {
  return env.PYTHON || "python3";
}

function main(argv: string[]): number {
  const choice = resolvePython();
  if (argv[0] === "--which") {
    console.log(`${choice.command}  (${choice.source})`);
    return 0;
  }
  if (argv.length === 0) {
    console.error("usage: node scripts/py.ts <script.py> [args...] | --which");
    return 2;
  }
  const r = spawnSync(choice.command, argv, { stdio: "inherit" });
  if (r.error) {
    const from =
      choice.source === "python3" ? "the default" : choice.source === "blender-venv" ? "the Blender venv" : `$${choice.source}`;
    console.error(
      `py.ts: cannot run ${choice.command} (${from}): ${r.error.message}\n` +
        "  set PYTHON to a Python with the modules this script needs (docs/pipeline.md section 0).",
    );
    return 127;
  }
  if (r.signal) {
    console.error(`py.ts: ${choice.command} ${argv[0]} was stopped by ${r.signal}`);
    return 1;
  }
  return r.status ?? 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exit(main(process.argv.slice(2)));
}
