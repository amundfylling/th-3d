// Scene cache (pilot): lossless PNGs of the 3D scene layer (remotion/SceneLayer.tsx: background, rink, posed figures and
// puck, seen from the frame's camera), reused for every output frame whose scene is identical. Captions and graphics are
// never in a cached image: the composite render draws them live above it, so a wording or styling change re-renders no
// scene. See docs/video-workflow.md "Scene cache".
//
// Identity of a cached image = namespace + scene state:
//   namespace: the scene renderer's code (SceneLayer, ShotScene, cameras, coordinate adapter), the served scene GLB and
//     its manifest, the geometry file, the three / r3f / remotion / react versions, the browser build, the --gl flag AND
//     the WebGL renderer the page reports, the output size and scale, the image format and the background behind the
//     canvas (the theme's). Changing any of them starts a new namespace (nothing old is reused).
//   scene state: every figure's pose matrix and the puck position (full double precision, from the pure evaluator) and the
//     complete camera (position, target, field of view). A frozen trace under a moving camera is a new state per frame.
// Not in the identity: overlay text, graphics, chapter timing, badges - anything above the scene layer.
//
// An entry is written only after its scene render was verified: the state and camera the page logged equal the pure
// evaluation for the frame it was rendered for (scripts/video.ts). The entry keeps that verification record; reused
// frames point at it and are reported as reused, with no per-frame WebGL readback of their own.
import { createHash } from "node:crypto";
import { createReadStream, existsSync, mkdirSync, readdirSync, readFileSync, renameSync, statSync, writeFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import path from "node:path";
import type { ShotFrameState } from "../../src/model/shot-pose.ts";
import type { CameraView } from "../../src/model/camera-track.ts";
import { sha } from "./targets.ts";

export const CACHE_ROOT = "out/scene-cache";
export const SCHEMA = "scene-cache/1";
export const RENDERER_FILES = ["remotion/SceneLayer.tsx", "remotion/ShotScene.tsx", "remotion/cameras.ts", "src/model/coordinates.ts", "remotion/asset-manifest.json", "public/full_static_appearance.glb", "data/geometry.json"];
const PACKAGES = ["three", "@react-three/fiber", "@remotion/three", "remotion", "react", "react-dom"];

export interface NamespaceInputs {
  files: Record<string, string>;
  packages: Record<string, string>;
  browser: string;
  gl: string;
  webgl_renderer: string;
  width: number;
  height: number;
  scale: number;
  image_format: "png";
  background: string;
}

export function namespaceInputs(o: { browserVersion: string; gl: string; webglRenderer: string; width: number; height: number; scale: number; background: string }): NamespaceInputs {
  const lock = JSON.parse(readFileSync("package-lock.json", "utf8"));
  return {
    files: Object.fromEntries(RENDERER_FILES.map((f) => [f, sha(f)])),
    packages: Object.fromEntries(PACKAGES.map((p) => [p, lock.packages[`node_modules/${p}`]?.version ?? "missing"])),
    browser: o.browserVersion, gl: o.gl, webgl_renderer: o.webglRenderer,
    width: o.width, height: o.height, scale: o.scale, image_format: "png", background: o.background,
  };
}

const h = (s: string): string => createHash("sha256").update(s).digest("hex");
export const namespaceId = (ns: NamespaceInputs): string => h(JSON.stringify({ schema: SCHEMA, ...ns })).slice(0, 24);

/** The scene state of a frame: what the scene layer draws, nothing else (full precision; JSON keeps doubles exact). */
export function sceneState(s: ShotFrameState, cam: CameraView): { figures: Record<string, number[]>; puck: number[]; camera: CameraView } {
  const figures: Record<string, number[]> = {};
  for (const pid of Object.keys(s.figures).sort()) figures[pid] = [...s.figures[pid]!.matrix];
  return { figures, puck: [...s.puckMm], camera: { positionMm: [...cam.positionMm], targetMm: [...cam.targetMm], fovDeg: cam.fovDeg } };
}

export const stateKey = (ns: string, state: ReturnType<typeof sceneState>): string => h(ns + "\n" + JSON.stringify(state));

export interface Entry {
  schema: string;
  key: string;
  namespace: string;
  png_sha256: string;
  bytes: number;
  rendered: { target: string; composition: string; frame: number; at: string; render_seconds_batch: number };
  /** the scene render's own checks: logged state and camera equal to the pure evaluation of that frame */
  verification: { state_equal_to_pure: boolean; readback_max_diff: number; camera_max_diff_mm: number; webgl_renderer: string };
  state: ReturnType<typeof sceneState>;
}

export class SceneCache {
  readonly dir: string;
  readonly ns: string;
  constructor(ns: string, inputs: NamespaceInputs, root = CACHE_ROOT) {
    this.ns = ns;
    this.dir = path.join(root, ns);
    mkdirSync(this.dir, { recursive: true });
    const nsFile = path.join(this.dir, "namespace.json");
    if (!existsSync(nsFile)) writeFileSync(nsFile, JSON.stringify({ schema: SCHEMA, namespace: ns, inputs }, null, 1) + "\n");
  }
  png(key: string): string {
    return path.join(this.dir, `${key}.png`);
  }
  entry(key: string): Entry | null {
    const p = path.join(this.dir, `${key}.json`);
    if (!existsSync(p) || !existsSync(this.png(key))) return null;
    const e = JSON.parse(readFileSync(p, "utf8")) as Entry;
    // an entry is only usable if it was verified and its image is the one verified
    if (e.key !== key || e.namespace !== this.ns || !e.verification.state_equal_to_pure) return null;
    if (statSync(this.png(key)).size !== e.bytes || sha(this.png(key)) !== e.png_sha256) return null;
    return e;
  }
  /** Moves a verified scene render into the cache (the PNG first, then its record: a record never points at nothing). */
  put(key: string, pngFile: string, rec: Omit<Entry, "schema" | "key" | "namespace" | "png_sha256" | "bytes">): Entry {
    const e: Entry = { schema: SCHEMA, key, namespace: this.ns, png_sha256: sha(pngFile), bytes: statSync(pngFile).size, ...rec };
    renameSync(pngFile, this.png(key));
    writeFileSync(path.join(this.dir, `${key}.json`), JSON.stringify(e) + "\n");
    return e;
  }
  size(): number {
    return readdirSync(this.dir).filter((f) => f.endsWith(".png")).length;
  }
}

/** Serves the cache over http on 127.0.0.1 (the browser loads the PNGs from there; nothing is copied into the bundle). */
export async function serveCache(root = CACHE_ROOT): Promise<{ base: string; close: () => Promise<void> }> {
  const abs = path.resolve(root);
  const server: Server = createServer((req, res) => {
    const rel = decodeURIComponent((req.url ?? "/").split("?")[0]!).replace(/^\/+/, "");
    const file = path.resolve(abs, rel);
    if (!file.startsWith(abs + path.sep) || !file.endsWith(".png") || !existsSync(file)) {
      res.writeHead(404).end();
      return;
    }
    res.writeHead(200, { "content-type": "image/png", "cache-control": "no-store", "access-control-allow-origin": "*" });
    createReadStream(file).pipe(res);
  });
  await new Promise<void>((ok) => server.listen(0, "127.0.0.1", ok));
  const port = (server.address() as { port: number }).port;
  return { base: `http://127.0.0.1:${port}`, close: () => new Promise<void>((ok) => server.close(() => ok())) };
}
