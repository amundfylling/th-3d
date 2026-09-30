// Structural + evidence-policy validation of data/geometry.json (policy in docs/geometry.md).
import type { GeometryFile, ImageToWorldMapping, Quantity, WorldPolyline } from "./geometry.ts";
import { geometrySchema } from "./geometry-schema.ts";

export interface ReferenceIndexEntry {
  id: string;
  local_path: string;
  sha256: string;
  native_width_px: number;
  native_height_px: number;
}

export interface ValidationContext {
  /** Entries of references/index.json `sources`. */
  referenceIndex: ReferenceIndexEntry[];
  /** Returns the SHA-256 of a repository file, or null if missing. Omit to skip file checks. */
  fileSha256?: (path: string) => string | null;
}

export interface ValidationResult {
  ok: boolean;
  errors: string[];
}

const EVIDENCED = new Set(["measured", "catalog_nominal", "traced"]);
const STATUS_RANK: Record<string, number> = { unknown: 0, assumed: 1, traced: 2, catalog_nominal: 2, measured: 3 };

function isQuantity(v: unknown): v is Quantity {
  return typeof v === "object" && v !== null && "value" in v && "unit" in v && "status" in v && "uncertainty" in v;
}

function isWorldPolyline(v: unknown): v is WorldPolyline {
  return typeof v === "object" && v !== null && "points_mm" in v && "mapping_id" in v;
}

/** Visits every object in the tree with its JSON path. */
function walk(node: unknown, path: string, visit: (value: object, path: string) => void): void {
  if (Array.isArray(node)) {
    node.forEach((child, i) => walk(child, `${path}[${i}]`, visit));
  } else if (typeof node === "object" && node !== null) {
    visit(node, path);
    for (const [key, child] of Object.entries(node)) walk(child, `${path}.${key}`, visit);
  }
}

/** True when the 2x2 linear part is a uniform scale times a rotation or reflection. */
export function isUniformSimilarity(m: ImageToWorldMapping["matrix"]): boolean {
  const [a, b, , c, d, , g, h, k] = m;
  const n1 = Math.hypot(a, c);
  const n2 = Math.hypot(b, d);
  const tol = 1e-9 * Math.max(n1, n2, 1);
  return n1 > 0 && Math.abs(n1 - n2) <= tol && Math.abs(a * b + c * d) <= tol * Math.max(n1, n2) && g === 0 && h === 0 && k === 1;
}

export function validateGeometry(data: unknown, ctx: ValidationContext): ValidationResult {
  const errors: string[] = [];
  if (!geometrySchema(data, "$", errors)) return { ok: false, errors };
  const g: GeometryFile = data;
  const err = (path: string, message: string): void => void errors.push(`${path}: ${message}`);

  // Unique ids per collection and globally among referenceable things.
  const sources = new Map(g.sources.map((s) => [s.id, s]));
  const assumptions = new Set(g.assumptions.map((a) => a.id));
  const landmarks = new Map(g.landmarks.map((l) => [l.id, l]));
  const traces = new Map(g.image_traces.map((t) => [t.id, t]));
  const mappings = new Map(g.image_to_world.map((m) => [m.id, m]));
  const images = new Map(g.source_images.map((i) => [i.source_id, i]));
  const claims = new Set(g.dimension_claims.map((c) => c.id));
  const collections: [string, { id: string }[]][] = [
    ["sources", g.sources],
    ["assumptions", g.assumptions],
    ["landmarks", g.landmarks],
    ["image_traces", g.image_traces],
    ["image_to_world", g.image_to_world],
    ["dimension_claims", g.dimension_claims],
    ["conflicts", g.conflicts],
    ["markings", g.markings],
    ["players", g.players],
    ["fixture_paths", g.fixture_paths],
    ["figure_assets", g.figure_assets],
    ["goals", g.goals],
    ["end_screens", g.end_screens],
  ];
  const seen = new Map<string, string>();
  for (const [name, items] of collections) {
    for (const item of items) {
      const prior = seen.get(item.id);
      if (prior) err(`$.${name}`, `duplicate id "${item.id}" (also in ${prior})`);
      seen.set(item.id, name);
    }
  }

  // Sources and source images agree with references/index.json.
  const index = new Map(ctx.referenceIndex.map((e) => [e.id, e]));
  g.sources.forEach((s, i) => {
    const p = `$.sources[${i}]`;
    if (s.index_id !== undefined && !index.has(s.index_id)) err(p, `index_id "${s.index_id}" is not in references/index.json`);
    if (s.kind === "reference_image") {
      if (!s.index_id) err(p, `reference_image must name an index_id`);
      if (!images.has(s.id)) err(p, `reference_image source has no source_images entry`);
    }
    if (s.kind === "user_measurement" && s.via) err(p, "a user measurement cannot be second-hand (via)");
  });
  g.source_images.forEach((img, i) => {
    const p = `$.source_images[${i}]`;
    const src = sources.get(img.source_id);
    if (!src || src.kind !== "reference_image") return err(p, `source_id must name a reference_image source`);
    const entry = src.index_id ? index.get(src.index_id) : undefined;
    if (!entry) return;
    if (entry.local_path !== img.local_path) err(p, `local_path differs from references/index.json`);
    if (entry.sha256 !== img.sha256) err(p, `sha256 differs from references/index.json`);
    if (entry.native_width_px !== img.width_px || entry.native_height_px !== img.height_px)
      err(p, `dimensions differ from references/index.json`);
    if (ctx.fileSha256) {
      const actual = ctx.fileSha256(img.local_path);
      if (actual === null) err(p, `file missing: ${img.local_path}`);
      else if (actual !== img.sha256) err(p, `file hash mismatch for ${img.local_path}; the reference was modified`);
    }
  });

  // Generic referential integrity and quantity policy over the whole tree.
  walk(g, "$", (node, path) => {
    const rec = node as Record<string, unknown>;
    const refList = (key: string, known: { has(id: string): boolean }, what: string): void => {
      const v = rec[key];
      if (Array.isArray(v)) for (const id of v) if (typeof id === "string" && !known.has(id)) err(`${path}.${key}`, `unknown ${what} "${id}"`);
    };
    refList("source_ids", sources, "source");
    refList("handedness_source_ids", sources, "source");
    refList("resolved_by_source_ids", sources, "source");
    refList("assumption_ids", assumptions, "assumption");
    refList("landmark_ids", landmarks, "landmark");
    refList("image_trace_ids", traces, "image trace");
    refList("claim_ids", claims, "dimension claim");
    refList("dimension_claim_ids", claims, "dimension claim");
    if (typeof rec.assumption_id === "string" && !assumptions.has(rec.assumption_id))
      err(`${path}.assumption_id`, `unknown assumption "${rec.assumption_id}"`);
    if (typeof rec.source_image_id === "string" && !images.has(rec.source_image_id))
      err(`${path}.source_image_id`, `unknown source image "${rec.source_image_id}"`);

    if (isQuantity(node)) checkQuantity(node, path);
    if (isWorldPolyline(node)) checkPolyline(node, path);
  });

  function checkQuantity(q: Quantity, path: string): void {
    if ((q.status === "unknown") !== (q.value === null))
      err(path, `status "unknown" if and only if value is null (status=${q.status}, value=${q.value})`);
    if (q.uncertainty !== null && !(q.uncertainty > 0))
      err(path, `uncertainty must be null (not stated) or > 0; zero or negative is not allowed`);
    if (EVIDENCED.has(q.status) && q.source_ids.length === 0) err(path, `status "${q.status}" requires source_ids`);
    if (q.status === "assumed" && !q.assumption_id) err(path, `status "assumed" requires assumption_id`);
    if (q.status !== "assumed" && q.assumption_id) err(path, `assumption_id is only allowed with status "assumed"`);
    const kinds = q.source_ids.map((id) => sources.get(id)?.kind);
    if (q.status === "measured" && !kinds.includes("user_measurement"))
      err(path, `status "measured" requires a user_measurement source`);
    if (q.status === "catalog_nominal" && !kinds.some((k) => k === "catalog_statement" || k === "document"))
      err(path, `status "catalog_nominal" requires a catalog_statement or document source`);
  }

  function checkPolyline(pl: WorldPolyline, path: string): void {
    if (pl.points_mm.length < 2) err(path, "a polyline needs at least 2 points");
    if (EVIDENCED.has(pl.status) && pl.source_ids.length === 0) err(path, `status "${pl.status}" requires source_ids`);
    if (pl.uncertainty_mm !== null && !(pl.uncertainty_mm > 0)) err(path, "uncertainty_mm must be null or > 0");
    if (pl.mapping_id !== null) {
      const m = mappings.get(pl.mapping_id);
      if (!m) return err(path, `unknown mapping "${pl.mapping_id}"`);
      if (STATUS_RANK[pl.status]! > STATUS_RANK[m.status]!)
        err(path, `status "${pl.status}" is stronger than its mapping "${m.id}" (${m.status})`);
    } else if (pl.status === "traced") {
      err(path, `a traced world polyline must name the mapping that produced it`);
    }
    if (pl.status === "measured" && !pl.source_ids.some((id) => sources.get(id)?.kind === "user_measurement"))
      err(path, `status "measured" requires a user_measurement source`);
  }

  // Image-space data lies inside its image.
  const inImage = (id: string, [u, v]: [number, number]): boolean => {
    const img = images.get(id);
    return !img || (u >= 0 && v >= 0 && u <= img.width_px && v <= img.height_px);
  };
  g.landmarks.forEach((l, i) => {
    if (!inImage(l.source_image_id, l.px)) err(`$.landmarks[${i}].px`, "outside the source image");
    if (l.uncertainty_px !== null && !(l.uncertainty_px > 0)) err(`$.landmarks[${i}]`, "uncertainty_px must be null or > 0");
  });
  g.image_traces.forEach((t, i) => {
    const p = `$.image_traces[${i}]`;
    t.points_px.forEach((pt, j) => {
      if (!inImage(t.source_image_id, pt)) err(`${p}.points_px[${j}]`, "outside the source image");
    });
    if (t.uncertainty_px !== null && !(t.uncertainty_px > 0)) err(p, "uncertainty_px must be null or > 0");
    for (const lid of t.landmark_ids) {
      const l = landmarks.get(lid);
      if (l && l.source_image_id !== t.source_image_id) err(p, `landmark "${lid}" belongs to another image`);
    }
    t.inferred_segments.forEach((s, j) => {
      if (!(s.from >= 0 && s.to >= s.from && s.to < t.points_px.length)) err(`${p}.inferred_segments[${j}]`, "index range outside points_px");
    });
  });

  // Mappings: uniform similarity only (no separate x/y stretch); assumptions must be named.
  g.image_to_world.forEach((m, i) => {
    const p = `$.image_to_world[${i}]`;
    if (m.model === "similarity" && !isUniformSimilarity(m.matrix))
      err(p, "similarity mapping must have one uniform scale (no separate x/y stretch) and last row [0,0,1]");
    if (m.model === "homography" && m.matrix[8] === 0) err(p, "homography matrix[8] must be non-zero");
    if (m.status === "assumed" && m.assumption_ids.length === 0) err(p, `status "assumed" requires assumption_ids`);
    for (const r of m.landmark_residuals ?? []) {
      const l = landmarks.get(r.landmark_id);
      if (!l) err(p, `unknown landmark "${r.landmark_id}" in residuals`);
      else if (l.source_image_id !== m.source_image_id) err(p, `residual landmark "${r.landmark_id}" belongs to another image`);
    }
  });

  // Conflicts stay unresolved unless a direct measurement settles them.
  g.conflicts.forEach((c, i) => {
    if (c.claim_ids.length < 2) err(`$.conflicts[${i}]`, "a conflict needs at least two claims");
    if (c.resolution !== "unresolved" && !c.resolution.resolved_by_source_ids.some((id) => sources.get(id)?.kind === "user_measurement"))
      err(`$.conflicts[${i}].resolution`, "a conflict may only be resolved by a user_measurement source");
  });

  // Teams, players, fixtures and assets form a consistent roster.
  const players = new Map(g.players.map((pl) => [pl.id, pl]));
  const paths = new Map(g.fixture_paths.map((f) => [f.id, f]));
  const assets = new Set(g.figure_assets.map((a) => a.id));
  const goals = new Map(g.goals.map((x) => [x.id, x]));
  for (const t of g.teams) {
    const goal = goals.get(t.defends_goal_id);
    if (!goal || goal.team_id !== t.id) err(`$.teams.${t.id}`, `defends_goal_id must name this team's goal`);
    const positions = g.players.filter((pl) => pl.team_id === t.id).map((pl) => pl.position).sort();
    if (positions.join(",") !== ["C", "G", "LD", "LW", "RD", "RW"].join(","))
      err(`$.teams.${t.id}`, `expected exactly one each of G, LD, RD, C, LW, RW; got ${positions.join(",")}`);
  }
  if (g.teams.length !== 2) err("$.teams", "expected two teams");
  g.players.forEach((pl, i) => {
    const p = `$.players[${i}]`;
    if (!assets.has(pl.asset_id)) err(p, `unknown asset "${pl.asset_id}"`);
    const f = paths.get(pl.fixture_path_id);
    if (!f) err(p, `unknown fixture path "${pl.fixture_path_id}"`);
    else if (f.player_id !== pl.id) err(p, `fixture path "${f.id}" belongs to "${f.player_id}"`);
    if (pl.stick_handedness !== "unknown" && pl.handedness_source_ids.length === 0) err(p, "stick handedness needs a source");
  });
  g.fixture_paths.forEach((f, i) => {
    if (!players.has(f.player_id)) err(`$.fixture_paths[${i}]`, `unknown player "${f.player_id}"`);
  });

  // Goal setup: a chosen configuration must be one of the candidates.
  if (g.goal_setup.configuration !== "unknown" && !g.goal_setup.candidates.includes(g.goal_setup.configuration))
    err("$.goal_setup", "configuration must be one of the candidates");

  return { ok: errors.length === 0, errors };
}
