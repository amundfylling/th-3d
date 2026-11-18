// Static server for viewer/dist with on-the-fly brotli/gzip (what any static host does), used for the page-weight and
// fps measurements. Reports bytes actually sent. node scripts/viewer-serve.ts [port=8123]
import { createServer } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { brotliCompressSync, gzipSync, constants } from "node:zlib";
import { extname, join, normalize } from "node:path";

const root = "viewer/dist", port = Number(process.argv[2] ?? 8123);
const types: Record<string, string> = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".glb": "model/gltf-binary" };
const cache = new Map<string, Uint8Array>();
createServer((req, res) => {
  let p = normalize(decodeURIComponent((req.url ?? "/").split("?")[0]!)); if (p.endsWith("/")) p += "index.html";
  const f = join(root, p); if (p.includes("..") || !existsSync(f)) { res.writeHead(404).end(); return; }
  const raw = readFileSync(f), ae = String(req.headers["accept-encoding"] ?? ""), text = [".html", ".js", ".json"].includes(extname(f));
  const enc = text && ae.includes("br") ? "br" : text && ae.includes("gzip") ? "gzip" : "";
  let body: Uint8Array = raw;
  if (enc) { const k = enc + f; if (!cache.has(k)) cache.set(k, enc === "br" ? brotliCompressSync(raw, { params: { [constants.BROTLI_PARAM_QUALITY]: 9 } }) : gzipSync(raw)); body = cache.get(k)!; }
  res.writeHead(200, { "content-type": types[extname(f)] ?? "application/octet-stream", "content-length": body.length, ...(enc ? { "content-encoding": enc } : {}), "cache-control": "public, max-age=3600" });
  res.end(body);
}).listen(port, () => console.log(`http://localhost:${port}/`));
