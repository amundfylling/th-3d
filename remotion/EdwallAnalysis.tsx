// Edwall hat-trick analysis videos (compositions analysis-edwall-g2-goal2..4): the shared analysis video
// (remotion/AnalysisVideo.tsx) with the PROPOSED rebuilds of Nygård's three long Edwall shovels in the NM26 semi-final,
// game 2 (data/traces/edwall-<goal>.trace.json, docs/rebuild-g2-edwall-v2.md). The pass is fitted to puck readings from the
// broadcast; the shot is hidden there and DESIGNED. Registered by its own entry (remotion/edwall-index.ts) so the shared
// Root stays untouched; rendered by scripts/edwall-render.ts. The contact check gate applies.
import { Composition } from "remotion";
import a2 from "../data/presentations/edwall-g2-goal2.analysis.json" with { type: "json" };
import a3 from "../data/presentations/edwall-g2-goal3.analysis.json" with { type: "json" };
import a4 from "../data/presentations/edwall-g2-goal4.analysis.json" with { type: "json" };
import t2 from "../data/traces/edwall-g2-goal2.trace.json" with { type: "json" };
import t3 from "../data/traces/edwall-g2-goal3.trace.json" with { type: "json" };
import t4 from "../data/traces/edwall-g2-goal4.trace.json" with { type: "json" };
import c2 from "../shots/edwall/g2-goal2.checks.json" with { type: "json" };
import c3 from "../shots/edwall/g2-goal3.checks.json" with { type: "json" };
import c4 from "../shots/edwall/g2-goal4.checks.json" with { type: "json" };
import type { AnalysisSpec } from "../src/model/analysis.ts";
import { createAnalysisVideo, type AnalysisTrace } from "./AnalysisVideo.tsx";

const GOALS = [
  { id: "g2-goal2", n: "1", spec: a2, trace: t2, checks: c2 },
  { id: "g2-goal3", n: "2", spec: a3, trace: t3, checks: c3 },
  { id: "g2-goal4", n: "3", spec: a4, trace: t4, checks: c4 },
] as const;

export const EDWALL = GOALS.map((g) => {
  const video = createAnalysisVideo({
    spec: g.spec as unknown as AnalysisSpec,
    trace: g.trace as unknown as AnalysisTrace,
    checks: g.checks,
    logTag: `edwall${g.n}`,
    allowProposed: true,
    text: {
      kicker: `NM 2026 · SEMI-FINAL GAME 2 · GOAL ${g.n} OF 3`,
      title: "EDWALL",
      subtitle: "Nygård's long shovel · rebuilt from the broadcast (proposed)",
      bug: `EDWALL HAT-TRICK · GOAL ${g.n}`,
      endTitle: `EDWALL · GOAL ${g.n} OF 3`,
      endSteps: ["HEEL-GROOVE DRAG BY THE RIGHT WING", "PASS ACROSS TO THE CENTRE", "LONG SHOVEL INTO THE FAR CORNER"],
    },
  });
  return { id: `analysis-edwall-${g.id}`, ANALYSIS: video.ANALYSIS, Component: video.Component };
});

export const EdwallRoot: React.FC = () => (
  <>
    {EDWALL.map((v) => (
      <Composition key={v.id} id={v.id} component={v.Component} durationInFrames={v.ANALYSIS.durationInFrames} fps={v.ANALYSIS.spec.fps}
        width={v.ANALYSIS.spec.width} height={v.ANALYSIS.spec.height} defaultProps={{ graphics: true }} />
    ))}
  </>
);
