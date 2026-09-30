// Canonical geometry contract for data/geometry.json.
// These types plus the runtime checks in validate.ts are the schema. Coordinate conventions and
// the evidence policy are documented in docs/geometry.md.

export const EVIDENCE_STATUSES = ["measured", "catalog_nominal", "traced", "assumed", "unknown"] as const;
export type EvidenceStatus = (typeof EVIDENCE_STATUSES)[number];

export const UNITS = ["mm", "deg", "g", "px", "mm_per_px"] as const;
export type Unit = (typeof UNITS)[number];

/**
 * One value with its evidence. `uncertainty` is a symmetric half-width in `unit`;
 * null means "not stated", never zero. `status: "unknown"` if and only if `value` is null.
 */
export interface Quantity {
  value: number | null;
  unit: Unit;
  status: EvidenceStatus;
  uncertainty: number | null;
  source_ids: string[];
  /** Required when status is "assumed"; must name an entry in `assumptions`. */
  assumption_id?: string;
  /** Wording carried from the source, e.g. "approx.". */
  qualifier?: string;
  note?: string;
}

/** World-space 2D point on the ice plane (z = 0), millimetres. */
export type WorldPoint2 = [x: number, y: number];
/** Source-image pixel coordinate: u right, v down, origin at the top-left corner of the image. */
export type PixelPoint = [u: number, v: number];

export interface WorldPolyline {
  points_mm: WorldPoint2[];
  closed: boolean;
  status: EvidenceStatus;
  source_ids: string[];
  /** Mapping that produced these points from image traces, if any. */
  mapping_id: string | null;
  uncertainty_mm: number | null;
  note?: string;
}

/** user_statement: a setup choice or convention stated by the user (not a measurement). */
export type SourceKind = "reference_image" | "catalog_statement" | "document" | "user_measurement" | "user_statement";

export interface Source {
  id: string;
  kind: SourceKind;
  title: string;
  /** For reference_image: the id in references/index.json. */
  index_id?: string;
  url?: string | null;
  /** Where the statement is read in the repository's reference PDF, if it is second-hand. */
  via?: { path: string; page: number };
  note?: string;
}

export interface SourceImage {
  /** Same id as the source (kind reference_image). */
  source_id: string;
  local_path: string;
  sha256: string;
  width_px: number;
  height_px: number;
}

export interface Landmark {
  id: string;
  source_image_id: string;
  px: PixelPoint;
  uncertainty_px: number | null;
  description: string;
  /** Visible, partly hidden by an object, or inferred (e.g. by symmetry). */
  visibility: "visible" | "partly_occluded" | "inferred";
  note?: string;
}

export interface ImageTrace {
  id: string;
  source_image_id: string;
  /** What the trace represents, e.g. "board_inner_boundary". */
  feature: string;
  closed: boolean;
  points_px: PixelPoint[];
  landmark_ids: string[];
  status: "traced" | "assumed";
  uncertainty_px: number | null;
  method: string;
  /** Index ranges of points that are occluded or inferred rather than seen. */
  inferred_segments: { from: number; to: number; reason: string; assumption_id?: string }[];
  /** Numeric summary of the trace (widths, fit errors, lengths), in the units named by each key. */
  stats?: Record<string, number>;
  note?: string;
}

/**
 * Pixel -> world (ice plane, mm) mapping. A 3x3 row-major matrix acting on [u, v, 1].
 * "similarity" must have a uniform scale (no separate x/y stretch). Applies to the ice plane only:
 * never to elevated objects such as figures, boards tops or screens.
 */
export interface ImageToWorldMapping {
  id: string;
  source_image_id: string;
  model: "similarity" | "homography";
  matrix: [number, number, number, number, number, number, number, number, number];
  plane: "ice_top_z0";
  status: "assumed" | "traced" | "measured";
  assumption_ids: string[];
  landmark_residuals?: { landmark_id: string; residual_px: number }[];
  note: string;
}

export interface Assumption {
  id: string;
  statement: string;
  reason: string;
  affects: string[];
  replace_with: string;
}

export interface DimensionClaim {
  id: string;
  source_ids: string[];
  length: Quantity;
  width: Quantity;
  height?: Quantity;
  scope_note: string;
}

export interface Conflict {
  id: string;
  subject: string;
  claim_ids: string[];
  description: string;
  resolution: "unresolved" | { resolved_by_source_ids: string[]; note: string };
}

export interface Marking {
  id: string;
  kind:
    | "centre_line"
    | "blue_line"
    | "goal_line"
    | "centre_circle"
    | "faceoff_circle"
    | "faceoff_spot"
    | "goal_crease";
  world: WorldPolyline | null;
  image_trace_ids: string[];
}

export type Position = "G" | "LD" | "RD" | "C" | "LW" | "RW";

export interface Team {
  id: "W" | "E";
  /** Display label: W is team A, E is team B. */
  label?: "A" | "B";
  defends_goal_id: string;
  attacks_toward: "+x" | "-x";
  /** Which reference-variant team occupies this side in a named image; the user's setup may differ. */
  reference_variant?: { team: string; source_ids: string[]; status: EvidenceStatus; note?: string };
}

export interface Player {
  id: string;
  team_id: Team["id"];
  position: Position;
  asset_id: string;
  fixture_path_id: string;
  stick_handedness: "left" | "right" | "unknown";
  handedness_source_ids: string[];
}

export interface FixturePath {
  id: string;
  player_id: string;
  control_rod: { part_number: string | null; has_link: boolean; source_ids: string[] };
  /** Visible slot centreline on the ice plane (from image traces); null until traced. */
  centreline: WorldPolyline | null;
  /** Path of the fixture rotation axis. Only a measurement can supply it; it may differ from the slot centreline. */
  fixture_axis_path: WorldPolyline | null;
  /** Why this slot belongs to this player (e.g. the figure standing on it in a named image). */
  identity_evidence?: { source_ids: string[]; description: string };
  image_trace_ids: string[];
  /** Arc-length positions along the centreline of the visible slot ends (unit as stated: image px or mm). */
  visible_slot_limits: { start: Quantity; end: Quantity };
  /** Arc-length positions (mm) of the physical travel stops; only measurement can fill these. */
  usable_stops: { start: Quantity; end: Quantity };
  /** Fixture axis rotation limits relative to the path frame; unknown until measured. */
  rotation_range: { min: Quantity; max: Quantity };
  /** Rod-to-figure transfer (push/pull and twist); null until evidenced. */
  transfer: null | { status: EvidenceStatus; source_ids: string[]; description: string };
  note?: string;
}

export interface ContactShape {
  id: string;
  kind: "blade" | "skate" | "base" | "stick_shaft" | "pad";
  /** Geometry in the asset's pivot-local frame (docs/geometry.md). */
  frame: "pivot_local";
  geometry: null | { type: "polyline" | "points"; points_mm: [number, number, number][] };
  status: EvidenceStatus;
  source_ids: string[];
  uncertainty_mm: number | null;
  /** True for debug geometry that stands in for unmeasured contacts; never physical evidence. */
  provisional?: boolean;
  assumption_id?: string;
  note?: string;
}

/** One line of a figure's contact-evidence inventory. */
export interface InventoryItem {
  item: string;
  status: EvidenceStatus;
  evidence: string;
}

export interface FigureAsset {
  id: string;
  kind: "skater" | "goalie";
  /** Group of assets known to share one mold; null while unknown. */
  mold_group: string | null;
  figure_height: Quantity;
  blade_offset_from_pivot: Quantity;
  ice_clearance: Quantity;
  contact_shapes: ContactShape[];
  inventory?: InventoryItem[];
  note?: string;
}

export interface Goal {
  id: string;
  team_id: Team["id"];
  part_number: string | null;
  width: Quantity;
  height: Quantity;
  depth: Quantity;
  source_ids: string[];
  /** Image traces of the goal region (ice cut-out, elevated cage outline). */
  image_trace_ids?: string[];
  /** Landmarks of the goal (post tops, which are elevated). */
  landmark_ids?: string[];
  note?: string;
}

export const GOAL_CONFIGURATIONS = ["retail_with_deflector_insert", "ithf_no_insert_no_cup"] as const;

export interface GoalSetup {
  configuration: (typeof GOAL_CONFIGURATIONS)[number] | "unknown";
  candidates: (typeof GOAL_CONFIGURATIONS)[number][];
  source_ids: string[];
  note: string;
}

export interface EndScreen {
  id: string;
  team_id: Team["id"];
  part_number: string | null;
  height: Quantity;
  length: Quantity;
  thickness: Quantity;
  source_ids: string[];
}

export interface Puck {
  part_number: string | null;
  diameter: Quantity;
  thickness: Quantity;
  mass: Quantity;
  rim_profile: null | { status: EvidenceStatus; source_ids: string[]; description: string };
}

export interface GeometryFile {
  schema: "stiga-play-off-21-geometry";
  geometry_version: string;
  updated: string;
  coordinate_system: {
    world: string;
    units: "mm";
    origin: string;
    x_axis: string;
    y_axis: string;
    z_axis: string;
    angles: string;
    image_pixels: string;
  };
  sources: Source[];
  source_images: SourceImage[];
  assumptions: Assumption[];
  landmarks: Landmark[];
  image_traces: ImageTrace[];
  image_to_world: ImageToWorldMapping[];
  board: {
    inner_boundary: {
      world: WorldPolyline | null;
      image_trace_ids: string[];
      corner_radius: Quantity;
      board_height: Quantity;
      note: string;
    };
    playing_area_nominal: { length: Quantity; width: Quantity; note: string };
    outer_housing: { world: WorldPolyline | null; image_trace_ids: string[]; dimension_claim_ids: string[]; note: string };
    loose_sheet: { world: WorldPolyline | null; image_trace_ids: string[]; thickness: Quantity; note: string };
  };
  dimension_claims: DimensionClaim[];
  conflicts: Conflict[];
  markings: Marking[];
  teams: Team[];
  players: Player[];
  fixture_paths: FixturePath[];
  figure_assets: FigureAsset[];
  goal_setup: GoalSetup;
  goals: Goal[];
  end_screens: EndScreen[];
  puck: Puck;
}
