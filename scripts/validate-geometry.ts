// Validates data/geometry.json against its schema, evidence policy and the reference index.
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { validateGeometry, type ReferenceIndexEntry } from "../src/model/validate.ts";

const GEOMETRY = process.argv[2] ?? "data/geometry.json";
const INDEX = "references/index.json";

const index = JSON.parse(readFileSync(INDEX, "utf8")) as { sources: ReferenceIndexEntry[] };
const data: unknown = JSON.parse(readFileSync(GEOMETRY, "utf8"));
const result = validateGeometry(data, {
  referenceIndex: index.sources,
  fileSha256: (path) => (existsSync(path) ? createHash("sha256").update(readFileSync(path)).digest("hex") : null),
});

if (!result.ok) {
  console.error(`${GEOMETRY}: ${result.errors.length} error(s)`);
  for (const e of result.errors) console.error(`  ${e}`);
  process.exit(1);
}
const g = data as { geometry_version: string };
console.log(`${GEOMETRY}: valid (geometry_version ${g.geometry_version})`);
