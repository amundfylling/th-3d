// Publishes site/dist to Cloudflare Pages (docs/combo-editor.md) with nothing but an API token.
//
//   npm run build && node scripts/deploy-cloudflare.mjs            (or: npm run deploy)
//   env: CLOUDFLARE_API_TOKEN (Pages: Edit), optional CLOUDFLARE_ACCOUNT_ID, CF_PAGES_PROJECT (default table-hockey-combo),
//        CF_PAGES_BRANCH (default main = the public address; any other name gives a preview address)
//
// Why not `wrangler pages deploy`: that uploads the files with a short-lived upload token in the Authorization header,
// and the cloud sessions this repo is worked on in reach Cloudflare through a proxy that sets that header itself, so
// the upload is refused there. This script instead sends the whole site inside the deployment request: the files travel
// as data modules of a small Pages worker that serves them (the site is about 3 MB, under the worker size limit). From a
// machine with a normal token, `npx wrangler pages deploy dist --project-name <project>` works just as well.
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const DIST = path.resolve(here, "../dist");
const PROJECT = process.env.CF_PAGES_PROJECT ?? "table-hockey-combo";
const BRANCH = process.env.CF_PAGES_BRANCH ?? "main";
const TOKEN = process.env.CLOUDFLARE_API_TOKEN;
if (!TOKEN) throw new Error("set CLOUDFLARE_API_TOKEN (a token with the Cloudflare Pages: Edit permission)");
const API = "https://api.cloudflare.com/client/v4";
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".glb": "model/gltf-binary", ".woff2": "font/woff2", ".ttf": "font/ttf", ".txt": "text/plain; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml" };

const curl = (args) => JSON.parse(execFileSync("curl", ["-sS", "--max-time", "180", "-H", `Authorization: Bearer ${TOKEN}`, ...args], { encoding: "utf8", maxBuffer: 1 << 26 }));
const ok = (res, what) => { if (!res.success) throw new Error(`${what}: ${JSON.stringify(res.errors)}`); return res.result; };

let account = process.env.CLOUDFLARE_ACCOUNT_ID;
if (!account) {
  const accounts = ok(curl([`${API}/accounts`]), "list accounts");
  if (accounts.length !== 1) throw new Error(`the token sees ${accounts.length} accounts; set CLOUDFLARE_ACCOUNT_ID`);
  account = accounts[0].id;
}
const project = curl([`${API}/accounts/${account}/pages/projects/${PROJECT}`]);
if (!project.success) ok(curl(["-X", "POST", "-H", "Content-Type: application/json", "-d", JSON.stringify({ name: PROJECT, production_branch: "main" }), `${API}/accounts/${account}/pages/projects`]), "create project");

const files = [];
const walk = (dir) => { for (const name of readdirSync(dir).sort()) { const p = path.join(dir, name); if (statSync(p).isDirectory()) walk(p); else files.push(p); } };
walk(DIST);
if (!files.some((f) => f.endsWith("index.html"))) throw new Error(`${DIST} has no index.html: run npm run build first`);

// the worker: one data module per file, served with its type, an ETag and a cache rule (hashed assets never change)
const bundle = new FormData();
const table = [];
let total = 0;
files.forEach((file, i) => {
  const rel = "/" + path.relative(DIST, file).split(path.sep).join("/"), body = readFileSync(file);
  total += body.length;
  bundle.append(`f${i}.bin`, new File([body], `f${i}.bin`, { type: "application/octet-stream" }));
  table.push({ i, rel, type: TYPES[path.extname(file)] ?? "application/octet-stream", etag: `"${createHash("sha256").update(body).digest("hex").slice(0, 20)}"`, immutable: rel.startsWith("/assets/") });
});
const worker = `${table.map((f) => `import f${f.i} from "./f${f.i}.bin";`).join("\n")}
const FILES = {${table.map((f) => `${JSON.stringify(f.rel)}: { body: f${f.i}, type: ${JSON.stringify(f.type)}, etag: ${JSON.stringify(f.etag)}, cache: ${JSON.stringify(f.immutable ? "public, max-age=31536000, immutable" : "public, max-age=300, must-revalidate")} }`).join(",\n")}};
export default {
  fetch(request) {
    const url = new URL(request.url);
    if (request.method !== "GET" && request.method !== "HEAD") return new Response("Method not allowed", { status: 405 });
    const f = FILES[url.pathname === "/" ? "/index.html" : url.pathname];
    if (!f) return new Response("Not found", { status: 404, headers: { "content-type": "text/plain; charset=utf-8" } });
    const headers = { "content-type": f.type, etag: f.etag, "cache-control": f.cache, "x-content-type-options": "nosniff", "referrer-policy": "no-referrer" };
    if (request.headers.get("if-none-match") === f.etag) return new Response(null, { status: 304, headers });
    return new Response(request.method === "HEAD" ? null : f.body, { headers });
  },
};
`;
bundle.append("_worker.js", new File([worker], "_worker.js", { type: "application/javascript+module" }));
bundle.set("metadata", JSON.stringify({ main_module: "_worker.js", compatibility_date: "2026-10-01" }));

const tmp = mkdtempSync(path.join(tmpdir(), "combo-deploy-"));
try {
  const bundlePath = path.join(tmp, "_worker.bundle");
  writeFileSync(bundlePath, Buffer.from(await new Response(bundle).arrayBuffer()));
  let commit = "";
  try { commit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: here, encoding: "utf8" }).trim(); } catch { /* not a git checkout */ }
  const res = ok(curl(["-X", "POST", "-F", "manifest={}", "-F", `branch=${BRANCH}`, "-F", "commit_message=Combo editor", ...(commit ? ["-F", `commit_hash=${commit}`] : []), "-F", "commit_dirty=false",
    "-F", `_worker.bundle=@${bundlePath};filename=_worker.bundle`, `${API}/accounts/${account}/pages/projects/${PROJECT}/deployments`]), "create deployment");
  console.log(`deployed ${files.length} files (${(total / 1e6).toFixed(2)} MB) to ${res.url}${BRANCH === "main" ? ` and https://${PROJECT}.pages.dev` : ""}`);
} finally {
  rmSync(tmp, { recursive: true, force: true });
}
