// Browser and GL backend for every Remotion render in this repository (Node APIs and the remotion CLI alike).
//
// Browser, first match wins:
//   1. --browser <path>, or the environment variable REMOTION_BROWSER_EXECUTABLE;
//   2. Remotion's own browser (ensureBrowser of the installed @remotion/renderer: a chrome-headless-shell it downloads once
//      into node_modules/.remotion and then reuses);
//   3. if that download is impossible (offline, blocked network), a chrome-headless-shell already installed by Playwright
//      under $PLAYWRIGHT_BROWSERS_PATH (or ~/.cache/ms-playwright) - found by search, never a fixed path.
// GL backend: --gl <name>, or REMOTION_GL; default "swangle" (SwiftShader through ANGLE: CPU, the same on every machine,
// the backend every committed export was made with). On a desktop with a GPU, "angle" (macOS/Windows) or "angle-egl" /
// "egl" / "vulkan" (Linux) can use it - but only the WebGL renderer string the page reports (logged by
// remotion/ShotScene.tsx as [gl-renderer], or probed with probeRenderer) says what actually drew the frames.
//
// The same { browserExecutable, chromiumOptions } go to openBrowser, selectComposition, renderStill, renderFrames and
// renderMedia (the Node APIs read no remotion.config / CLI flags).
//
//   node scripts/video/render-env.ts            prints the browser path (for `remotion still --browser-executable=...`)
import type { ChromiumOptions } from "@remotion/renderer";
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, readdirSync, rmSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const GL_BACKENDS = ["swangle", "angle", "egl", "swiftshader", "vulkan", "angle-egl"] as const;
export type GlBackend = (typeof GL_BACKENDS)[number];

export interface RenderEnv {
  browserExecutable: string;
  browserSource: "argument" | "environment" | "remotion" | "playwright";
  browserVersion: string;
  gl: GlBackend;
  chromiumOptions: ChromiumOptions;
}

function playwrightHeadlessShell(): string | null {
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, path.join(homedir(), ".cache/ms-playwright"), path.join(homedir(), "Library/Caches/ms-playwright")].filter((r): r is string => !!r && existsSync(r));
  for (const root of roots) {
    const dirs = readdirSync(root).filter((d) => d.startsWith("chromium_headless_shell-")).sort().reverse();
    for (const d of dirs) {
      for (const rel of ["chrome-linux/headless_shell", "chrome-headless-shell-linux64/chrome-headless-shell", "chrome-mac/headless_shell", "chrome-headless-shell-mac-arm64/chrome-headless-shell", "chrome-headless-shell-mac-x64/chrome-headless-shell", "chrome-win/headless_shell.exe"]) {
        const p = path.join(root, d, rel);
        if (existsSync(p)) return p;
      }
    }
  }
  return null;
}

function version(exe: string): string {
  try {
    return execFileSync(exe, ["--version"], { encoding: "utf8", timeout: 20000 }).trim();
  } catch {
    return "unknown";
  }
}

export async function resolveRenderEnv(opts: { browser?: string | null; gl?: string | null; quiet?: boolean } = {}): Promise<RenderEnv> {
  const gl = (opts.gl ?? process.env.REMOTION_GL ?? "swangle") as GlBackend;
  if (!GL_BACKENDS.includes(gl)) throw new Error(`--gl ${gl}: one of ${GL_BACKENDS.join(", ")}`);
  const log = (s: string) => { if (!opts.quiet) console.error(s); };
  let exe: string | null = null;
  let source: RenderEnv["browserSource"] = "argument";
  if (opts.browser) exe = opts.browser;
  else if (process.env.REMOTION_BROWSER_EXECUTABLE) [exe, source] = [process.env.REMOTION_BROWSER_EXECUTABLE, "environment"];
  if (exe) {
    if (!existsSync(exe)) throw new Error(`browser ${exe} (${source}) does not exist`);
  } else {
    // the download runs in a child process: a failed download (offline, blocked host) surfaces as an uncaught socket
    // error inside @remotion/renderer, which must not take this process down
    const dl = spawnSync(process.execPath, ["--input-type=module", "-e", "import { ensureBrowser } from '@remotion/renderer'; const s = await ensureBrowser({ logLevel: 'warn' }); console.log(JSON.stringify(s));"], { encoding: "utf8", timeout: 600000 });
    const st = dl.status === 0 ? (JSON.parse(dl.stdout.trim().split("\n").pop()!) as { type: string; path?: string }) : null;
    if (st?.path && existsSync(st.path)) [exe, source] = [st.path, "remotion"];
    else {
      const why = (dl.stderr || dl.stdout || "").split("\n").find((l) => /Error|error/.test(l)) ?? `exit ${dl.status}`;
      const lock = path.resolve("node_modules/.remotion/chrome-headless-shell/download.lock");
      if (existsSync(lock) && readdirSync(path.dirname(lock)).length === 1) rmSync(lock);  // stale lock of the failed download
      const fallback = playwrightHeadlessShell();
      if (!fallback) throw new Error(`Remotion could not download its browser (${why.trim()}); pass --browser <chrome-headless-shell> or set REMOTION_BROWSER_EXECUTABLE`);
      log(`browser: Remotion's browser download failed (${why.trim()}); using the Playwright headless shell found at ${fallback}`);
      [exe, source] = [fallback, "playwright"];
    }
  }
  if (!exe) throw new Error("no browser: pass --browser <path>");
  return { browserExecutable: exe, browserSource: source, browserVersion: version(exe), gl, chromiumOptions: { gl } };
}

/** Human-readable backend label for reports: the requested flag plus what the page reported, never one without the other. */
export function backendLabel(env: RenderEnv, observed: string[]): string {
  return `--gl=${env.gl}; WebGL renderer reported: ${observed.length ? observed.join(" | ") : "not observed (no WebGL frame rendered)"}`;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const env = await resolveRenderEnv({ browser: process.argv[2] ?? null, quiet: false });
  console.log(env.browserExecutable);
}
