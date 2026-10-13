// Render targets: every analysis composition on the shared renderer (remotion/analysis-videos.ts), by a short name.
// A shot-encyclopedia move is "move:<id>" (or just "<id>" when no hand-made video has that name); new moves need no
// entry here: building them (scripts/build-move.py <id> --video-spec) registers their composition move-<id>.
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync } from "node:fs";

export interface Target {
  name: string;
  composition: string;
  spec: string;
  trace: string;
  checks: string;
  /** console tag of the composition's [<tag>-state] / [<tag>-camera] / [<tag>-cached] logs */
  tag: string;
  /** a proposed trace may be rendered (the composition says so too; its own gate decides in the browser) */
  allowProposed: boolean;
  /** shot-encyclopedia move id (its trace and presentation must pass scripts/build-move.py --check) */
  move: string | null;
  /** files that define the composition (fingerprinted in the export report) */
  files: string[];
  final: { out: string; report: string; title: string };
}

// shared by every analysis composition: the renderer, its scene layer, the scene and the overlay theme
const SHARED = ["remotion/AnalysisVideo.tsx", "remotion/SceneLayer.tsx", "remotion/ShotScene.tsx", "remotion/theme.ts"];

const HAND_MADE: Target[] = [
  { name: "shovel-17", composition: "analysis-shovel-17", spec: "data/presentations/shovel-17.analysis.json", trace: "data/traces/shovel-17.trace.json", checks: "shots/22-shovel/checks.json",
    tag: "analysis", allowProposed: false, move: null, files: ["remotion/ShotAnalysis.tsx", ...SHARED],
    final: { out: "validation/analysis-shovel-17.mp4", report: "validation/analysis-shovel-17-report.json", title: "#17 The Shovel - sports-analysis video" } },
  { name: "spjass", composition: "analysis-spjass", spec: "data/presentations/spjass.analysis.json", trace: "data/traces/spjass.trace.json", checks: "shots/spjass/checks.json",
    tag: "spjass", allowProposed: true, move: null, files: ["remotion/SpjassAnalysis.tsx", ...SHARED],
    final: { out: "validation/analysis-spjass.mp4", report: "validation/analysis-spjass-report.json", title: "The spjass - sports-analysis video" } },
  { name: "ikv", composition: "analysis-ikv", spec: "data/presentations/invers-kryssar-velodrom.analysis.json", trace: "data/traces/invers-kryssar-velodrom.trace.json", checks: "shots/invers-kryssar-velodrom/checks.json",
    tag: "ikv", allowProposed: true, move: null, files: ["remotion/IkvAnalysis.tsx", ...SHARED],
    final: { out: "validation/analysis-ikv.mp4", report: "validation/analysis-ikv-report.json", title: "Invers Kryssar med Velodrom - sports-analysis video" } },
  { name: "defence-lw", composition: "analysis-defence-lw", spec: "data/presentations/defence-left-wing.analysis.json", trace: "data/traces/defence-left-wing.trace.json", checks: "shots/defence-left-wing/checks.json",
    tag: "defence", allowProposed: true, move: null, files: ["remotion/DefenceAnalysis.tsx", ...SHARED],
    final: { out: "validation/analysis-defence-lw.mp4", report: "validation/analysis-defence-lw-report.json", title: "Defending the left wing - concept video" } },
  { name: "nacka", composition: "analysis-nacka", spec: "data/presentations/nacka.analysis.json", trace: "data/traces/nacka.trace.json", checks: "shots/nacka/checks.json",
    tag: "nacka", allowProposed: true, move: null, files: ["remotion/NackaAnalysis.tsx", ...SHARED],
    final: { out: "validation/analysis-nacka.mp4", report: "validation/analysis-nacka-report.json", title: "Näcka - sports-analysis video" } },
];

function moveTarget(id: string): Target {
  return {
    name: `move:${id}`, composition: `move-${id}`, spec: `data/presentations/${id}.analysis.json`, trace: `data/traces/${id}.trace.json`, checks: `shots/${id}/checks.json`,
    tag: `move-${id}`, allowProposed: true, move: id, files: ["remotion/EncyclopediaAnalysis.tsx", "remotion/encyclopedia-registry.ts", ...SHARED],
    final: { out: `validation/moves/${id}.mp4`, report: `validation/moves/${id}-video-report.json`, title: `${id} - shot encyclopedia video` },
  };
}

/** Moves with a generated video (registered in remotion/encyclopedia-registry.ts). */
export function registeredMoves(): string[] {
  const reg = readFileSync("remotion/encyclopedia-registry.ts", "utf8");
  return [...reg.matchAll(/\{ id: "([^"]+)", spec:/g)].map((m) => m[1]!);
}

export function allTargets(): Target[] {
  return [...HAND_MADE, ...registeredMoves().map(moveTarget)];
}

export function resolveTarget(name: string): Target {
  const all = allTargets();
  const t = all.find((x) => x.name === name || x.composition === name) ?? (existsSync(`moves/${name}/move.json`) ? all.find((x) => x.move === name) : undefined);
  if (t) return t;
  if (name.startsWith("move:") || existsSync(`moves/${name}/move.json`)) {
    const id = name.replace(/^move:/, "");
    throw new Error(`move ${id} has no generated video: python3 scripts/build-move.py ${id} --video-spec (moves with a video: ${registeredMoves().join(", ") || "none"})`);
  }
  throw new Error(`unknown target ${name}; one of ${all.map((x) => x.name).join(", ")}`);
}

export const sha = (p: string): string => createHash("sha256").update(readFileSync(p)).digest("hex");
/** Fingerprint of the files that define a composition (each file's path and SHA-256, in order). */
export const compositionSha = (files: readonly string[]): string => createHash("sha256").update(files.map((f) => `${f}:${sha(f)}`).join("\n")).digest("hex");

export const moveIds = (): string[] => readdirSync("moves").filter((d) => existsSync(`moves/${d}/move.json`));
