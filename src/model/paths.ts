// Builds pose-path samplers from the canonical geometry (visible slot centrelines, ASSUMED preview scale).
import type { GeometryFile } from "./geometry.ts";
import { pathSampler, type PathSampler, type Team, type Vec2 } from "./pose.ts";

export interface FigurePath {
  playerId: string;
  team: Team;
  sampler: PathSampler;
}

export function loadFigurePaths(g: GeometryFile): FigurePath[] {
  return g.players.map((pl) => {
    const f = g.fixture_paths.find((x) => x.id === pl.fixture_path_id);
    if (!f?.centreline) throw new Error(`${pl.id}: no centreline in data/geometry.json`);
    const kind = pl.position === "G" ? "goalie" : "skater";
    return { playerId: pl.id, team: pl.team_id, sampler: pathSampler(f.id, kind, f.centreline.points_mm as Vec2[]) };
  });
}
