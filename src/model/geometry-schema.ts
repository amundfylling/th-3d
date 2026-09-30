// Runtime schema for data/geometry.json. The `Check<GeometryFile>` annotation makes tsc verify that
// this schema and the interfaces in geometry.ts describe the same structure.
import { arr, bool, lit, nonEmptyStr, nullable, num, obj, opt, rec, str, tuple, union, type Check } from "./check.ts";
import {
  EVIDENCE_STATUSES,
  GOAL_CONFIGURATIONS,
  UNITS,
  type GeometryFile,
  type ImageToWorldMapping,
  type Quantity,
  type WorldPolyline,
} from "./geometry.ts";

const status = lit(...EVIDENCE_STATUSES);
const ids = arr(nonEmptyStr);

export const quantity: Check<Quantity> = obj({
  value: nullable(num),
  unit: lit(...UNITS),
  status,
  uncertainty: nullable(num),
  source_ids: ids,
  assumption_id: opt(nonEmptyStr),
  qualifier: opt(str),
  note: opt(str),
});

const worldPoint = tuple(num, num);
const pixelPoint = tuple(num, num);

const worldPolyline: Check<WorldPolyline> = obj({
  points_mm: arr(worldPoint),
  closed: bool,
  status,
  source_ids: ids,
  mapping_id: nullable(nonEmptyStr),
  uncertainty_mm: nullable(num),
  note: opt(str),
});

const matrix3 = tuple(num, num, num, num, num, num, num, num, num);

const mapping: Check<ImageToWorldMapping> = obj({
  id: nonEmptyStr,
  source_image_id: nonEmptyStr,
  model: lit("similarity", "homography"),
  matrix: matrix3,
  plane: lit("ice_top_z0"),
  status: lit("assumed", "traced", "measured"),
  assumption_ids: ids,
  landmark_residuals: opt(arr(obj({ landmark_id: nonEmptyStr, residual_px: num }))),
  note: str,
});

const evidenceNote = obj({ status, source_ids: ids, description: str });
const team = lit("W", "E");
const range = obj({ start: quantity, end: quantity });

export const geometrySchema: Check<GeometryFile> = obj({
  schema: lit("stiga-play-off-21-geometry"),
  geometry_version: nonEmptyStr,
  updated: nonEmptyStr,
  coordinate_system: obj({
    world: str,
    units: lit("mm"),
    origin: str,
    x_axis: str,
    y_axis: str,
    z_axis: str,
    angles: str,
    image_pixels: str,
  }),
  sources: arr(
    obj({
      id: nonEmptyStr,
      kind: lit("reference_image", "catalog_statement", "document", "user_measurement", "user_statement"),
      title: nonEmptyStr,
      index_id: opt(nonEmptyStr),
      url: opt(nullable(str)),
      via: opt(obj({ path: nonEmptyStr, page: num })),
      note: opt(str),
    }),
  ),
  source_images: arr(
    obj({ source_id: nonEmptyStr, local_path: nonEmptyStr, sha256: nonEmptyStr, width_px: num, height_px: num }),
  ),
  assumptions: arr(
    obj({ id: nonEmptyStr, statement: nonEmptyStr, reason: nonEmptyStr, affects: ids, replace_with: nonEmptyStr }),
  ),
  landmarks: arr(
    obj({
      id: nonEmptyStr,
      source_image_id: nonEmptyStr,
      px: pixelPoint,
      uncertainty_px: nullable(num),
      description: nonEmptyStr,
      visibility: lit("visible", "partly_occluded", "inferred"),
      note: opt(str),
    }),
  ),
  image_traces: arr(
    obj({
      id: nonEmptyStr,
      source_image_id: nonEmptyStr,
      feature: nonEmptyStr,
      closed: bool,
      points_px: arr(pixelPoint),
      landmark_ids: ids,
      status: lit("traced", "assumed"),
      uncertainty_px: nullable(num),
      method: nonEmptyStr,
      inferred_segments: arr(
        obj({ from: num, to: num, reason: nonEmptyStr, assumption_id: opt(nonEmptyStr) }),
      ),
      stats: opt(rec(num)),
      note: opt(str),
    }),
  ),
  image_to_world: arr(mapping),
  board: obj({
    inner_boundary: obj({
      world: nullable(worldPolyline),
      image_trace_ids: ids,
      corner_radius: quantity,
      board_height: quantity,
      note: str,
    }),
    playing_area_nominal: obj({ length: quantity, width: quantity, note: str }),
    outer_housing: obj({
      world: nullable(worldPolyline),
      image_trace_ids: ids,
      dimension_claim_ids: ids,
      note: str,
    }),
    loose_sheet: obj({ world: nullable(worldPolyline), image_trace_ids: ids, thickness: quantity, note: str }),
  }),
  dimension_claims: arr(
    obj({
      id: nonEmptyStr,
      source_ids: ids,
      length: quantity,
      width: quantity,
      height: opt(quantity),
      scope_note: str,
    }),
  ),
  conflicts: arr(
    obj({
      id: nonEmptyStr,
      subject: nonEmptyStr,
      claim_ids: ids,
      description: nonEmptyStr,
      resolution: union(lit("unresolved"), obj({ resolved_by_source_ids: ids, note: nonEmptyStr })),
    }),
  ),
  markings: arr(
    obj({
      id: nonEmptyStr,
      kind: lit("centre_line", "blue_line", "goal_line", "centre_circle", "faceoff_circle", "faceoff_spot", "goal_crease"),
      world: nullable(worldPolyline),
      image_trace_ids: ids,
    }),
  ),
  teams: arr(
    obj({
      id: team,
      label: opt(lit("A", "B")),
      defends_goal_id: nonEmptyStr,
      attacks_toward: lit("+x", "-x"),
      reference_variant: opt(obj({ team: nonEmptyStr, source_ids: ids, status, note: opt(str) })),
    }),
  ),
  players: arr(
    obj({
      id: nonEmptyStr,
      team_id: team,
      position: lit("G", "LD", "RD", "C", "LW", "RW"),
      asset_id: nonEmptyStr,
      fixture_path_id: nonEmptyStr,
      stick_handedness: lit("left", "right", "unknown"),
      handedness_source_ids: ids,
    }),
  ),
  fixture_paths: arr(
    obj({
      id: nonEmptyStr,
      player_id: nonEmptyStr,
      control_rod: obj({ part_number: nullable(nonEmptyStr), has_link: bool, source_ids: ids }),
      centreline: nullable(worldPolyline),
      fixture_axis_path: nullable(worldPolyline),
      identity_evidence: opt(obj({ source_ids: ids, description: nonEmptyStr })),
      image_trace_ids: ids,
      visible_slot_limits: range,
      usable_stops: range,
      rotation_range: obj({ min: quantity, max: quantity }),
      transfer: nullable(evidenceNote),
      note: opt(str),
    }),
  ),
  figure_assets: arr(
    obj({
      id: nonEmptyStr,
      kind: lit("skater", "goalie"),
      mold_group: nullable(nonEmptyStr),
      figure_height: quantity,
      blade_offset_from_pivot: quantity,
      ice_clearance: quantity,
      contact_shapes: arr(
        obj({
          id: nonEmptyStr,
          kind: lit("blade", "skate", "base", "stick_shaft", "pad"),
          frame: lit("pivot_local"),
          geometry: nullable(
            obj({ type: lit("polyline", "points"), points_mm: arr(tuple(num, num, num)) }),
          ),
          status,
          source_ids: ids,
          uncertainty_mm: nullable(num),
          provisional: opt(bool),
          assumption_id: opt(nonEmptyStr),
          note: opt(str),
        }),
      ),
      inventory: opt(arr(obj({ item: nonEmptyStr, status, evidence: nonEmptyStr }))),
      note: opt(str),
    }),
  ),
  goal_setup: obj({
    configuration: union(lit(...GOAL_CONFIGURATIONS), lit("unknown")),
    candidates: arr(lit(...GOAL_CONFIGURATIONS)),
    source_ids: ids,
    note: str,
  }),
  goals: arr(
    obj({
      id: nonEmptyStr,
      team_id: team,
      part_number: nullable(nonEmptyStr),
      width: quantity,
      height: quantity,
      depth: quantity,
      source_ids: ids,
      image_trace_ids: opt(ids),
      landmark_ids: opt(ids),
      note: opt(str),
    }),
  ),
  end_screens: arr(
    obj({
      id: nonEmptyStr,
      team_id: team,
      part_number: nullable(nonEmptyStr),
      height: quantity,
      length: quantity,
      thickness: quantity,
      source_ids: ids,
    }),
  ),
  puck: obj({
    part_number: nullable(nonEmptyStr),
    diameter: quantity,
    thickness: quantity,
    mass: quantity,
    rim_profile: nullable(evidenceNote),
  }),
});

