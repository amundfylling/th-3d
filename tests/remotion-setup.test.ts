// Iteration 19: Remotion dependencies pinned and aligned; static composition uses the single adapter.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pkg = JSON.parse(readFileSync("package.json", "utf8"));
const lock = JSON.parse(readFileSync("package-lock.json", "utf8"));

test("remotion and every @remotion/* package share one exact version (package.json and lockfile)", () => {
  const deps = { ...pkg.dependencies, ...pkg.devDependencies } as Record<string, string>;
  const direct = Object.entries(deps).filter(([k]) => k === "remotion" || k.startsWith("@remotion/"));
  assert.ok(direct.length >= 3);
  for (const [, v] of direct) assert.match(v, /^\d+\.\d+\.\d+$/, "exact pin, no range");
  const version = deps.remotion!;
  const installed = Object.entries(lock.packages as Record<string, { version?: string }>)
    .filter(([k]) => /node_modules\/(remotion|@remotion\/[^/]+)$/.test(k))
    .map(([k, v]) => [k, v.version]);
  assert.ok(installed.length >= 5);
  for (const [k, v] of installed) assert.equal(v, version, `${k} is ${v}, expected ${version}`);
});

test("static composition: no frame-dependent code; cameras converted by the project adapter", () => {
  const src = readFileSync("remotion/StaticInspection.tsx", "utf8");
  assert.doesNotMatch(src, /useCurrentFrame|interpolate\(/, "no animation");
  const cams = readFileSync("remotion/cameras.ts", "utf8");
  assert.match(cams, /worldMmToGltfM/);
  const checks = readFileSync("remotion/checks.ts", "utf8");
  assert.match(checks, /worldMmToGltfM/);
});
