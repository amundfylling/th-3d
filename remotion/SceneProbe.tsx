// Scene-state isolation check (scripts/video/scene-probe.ts): composition frame i draws the scene layer of
// items[i] = { video, frame } (any analysis composition, any output frame), all in one browser tab. Rendered with one tab
// in two different orders, every item must give the same pixels as rendered alone: no figure or puck pose may leak from
// the composition drawn before it.
import { useLayoutEffect } from "react";
import { useCurrentFrame } from "remotion";
import { ANALYSIS_VIDEOS } from "./analysis-videos.ts";

export type SceneProbeProps = { items: { video: string; frame: number }[] };

export const sceneProbeMetadata = ({ props }: { props: SceneProbeProps }) => ({ durationInFrames: Math.max(1, props.items.length) });

export const SceneProbe: React.FC<SceneProbeProps> = ({ items }) => {
  const item = items[useCurrentFrame()]!;
  const v = ANALYSIS_VIDEOS.find((x) => x.id === item.video);
  if (!v) throw new Error(`scene probe: unknown composition ${item.video}`);
  // frameMap with one entry per probe frame, all pointing at the item's output frame (the component reads frameMap[i])
  return <v.Component graphics={false} frameMap={items.map(() => item.frame)} />;
};

/** Logs the WebGL renderer the browser gives a page with the render's flags ([gl-renderer]), without loading the scene. */
export const GlProbe: React.FC = () => {
  useLayoutEffect(() => {
    const c = document.createElement("canvas");
    const ctx = (c.getContext("webgl2") ?? c.getContext("webgl")) as WebGLRenderingContext | null;
    if (!ctx) {
      console.log(`[gl-renderer] ${JSON.stringify({ vendor: "none", renderer: "no WebGL context", version: "none" })}`);
      return;
    }
    const dbg = ctx.getExtension("WEBGL_debug_renderer_info");
    console.log(`[gl-renderer] ${JSON.stringify({
      vendor: String(dbg ? ctx.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : ctx.getParameter(ctx.VENDOR)),
      renderer: String(dbg ? ctx.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : ctx.getParameter(ctx.RENDERER)),
      version: String(ctx.getParameter(ctx.VERSION)),
    })}`);
  }, []);
  return null;
};
