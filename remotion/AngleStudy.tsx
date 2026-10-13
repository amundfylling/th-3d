// Camera-angle study for the move pictures (docs/move-pictures.md): the Näcka trace played in slow motion from one of
// four cameras, with the puck path drawn on the ice as the picture's green arrows and numbered contacts. Presentation
// only: time comes from the frame alone (t = timeAt(frame)), the trace is evaluated by the pure pose code, and the
// trace must pass the same gate as every analysis video (versions, contact checks, proposed allowed by the user's ask).
import { ThreeCanvas } from "@remotion/three";
import { useLayoutEffect, useMemo, useState } from "react";
import { AbsoluteFill, cancelRender, staticFile, useCurrentFrame, useDelayRender, useVideoConfig } from "remotion";
import * as THREE from "three";
import geometry from "../data/geometry.json" with { type: "json" };
import traceJson from "../data/traces/nacka.trace.json" with { type: "json" };
import contactChecks from "../shots/nacka/checks.json" with { type: "json" };
import type { Vec3 } from "../src/model/pose.ts";
import { checkTraceCompatibility, shotTimeEvaluator, type AssetManifest } from "../src/model/shot-pose.ts";
import type { ShotTrace } from "../src/model/trace.ts";
import manifest from "./asset-manifest.json" with { type: "json" };
import { toThree } from "./cameras.ts";
import { ShotScene } from "./ShotScene.tsx";

const TRACE = traceJson as unknown as ShotTrace & { trace_id: string; asset_refs: Record<string, unknown>; events: { id: string; t_estimate: number }[] };
const evalAt = shotTimeEvaluator(TRACE, geometry as Parameters<typeof shotTimeEvaluator>[1]);

function assertRenderable(): string[] {
  const compared = checkTraceCompatibility(TRACE, geometry.geometry_version, manifest as AssetManifest);
  if (TRACE.status !== "accepted" && TRACE.status !== "proposed") throw new Error(`trace ${TRACE.trace_id} is ${TRACE.status}`);
  if (contactChecks.trace_id !== TRACE.trace_id) throw new Error(`contact checks are for ${contactChecks.trace_id}, not ${TRACE.trace_id}`);
  if (contactChecks.unexpected_penetrations.length > 0) throw new Error(`trace ${TRACE.trace_id} overlaps geometry`);
  return [...compared, "contact_checks", "status_proposed_allowed"];
}

// ---------------------------------------------------------------- timing (source seconds from the frame)
export const ANGLE_FPS = 30;
const T0 = 3.95, T1 = 4.56, SLOW = 4, HOLD_IN = 0.6, HOLD_OUT = 1.4;
export const ANGLE_FRAMES = Math.round((HOLD_IN + (T1 - T0) * SLOW + HOLD_OUT) * ANGLE_FPS);
const timeAt = (frame: number): number => Math.min(T1, T0 + Math.max(0, frame / ANGLE_FPS - HOLD_IN) / SLOW);

// ---------------------------------------------------------------- the move's contacts and arrows (from the trace)
const ev = (id: string): number => TRACE.events.find((e) => e.id === id)!.t_estimate;
const STOPS = [ev("contact.heel_pass"), ev("contact.shot"), ev("goal_net")];
const puckAt = (t: number): Vec3 => { const p = evalAt(t, 0).puckMm; return [p[0], p[1], 1]; };
const ARROWS = STOPS.slice(0, -1).map((t0, i) => {
  const t1 = STOPS[i + 1]!, n = 40;
  return { t0, t1, pts: Array.from({ length: n + 1 }, (_, k) => puckAt(t0 + ((t1 - t0) * k) / n)) };
});

// ---------------------------------------------------------------- the four cameras (world mm, z up)
export type Angle = "overhead" | "tilted" | "oblique" | "goalie";
type Cam = { kind: "ortho"; target: Vec3; heightMm: number; up: Vec3 } | { kind: "persp"; position: Vec3; target: Vec3; fovDeg: number; up: Vec3 };
const tilt = 20 * (Math.PI / 180), D = 1050, TGT: Vec3 = [245, 0, 0];
export const ANGLES: Record<Angle, Cam> = {
  // 1. straight overhead, goal up (like the pictures)
  overhead: { kind: "ortho", target: [245, 0, 0], heightMm: 300, up: [1, 0, 0] },
  // 2. overhead tilted 20 deg toward the attackers' end, goal up
  tilted: { kind: "persp", position: [TGT[0] - D * Math.sin(tilt), 0, D * Math.cos(tilt)], target: TGT, fovDeg: 17.5, up: [1, 0, 0] },
  // 3. the analysis videos' replay view (data/presentations/nacka.analysis.json "replay")
  oblique: { kind: "persp", position: [40, -330, 330], target: [220, 0, 0], fovDeg: 32, up: [0, 0, 1] },
  // 4. from behind the goal, above the boards (the goalie's view)
  goalie: { kind: "persp", position: [580, 0, 290], target: [200, 0, 0], fovDeg: 32, up: [0, 0, 1] },
};

function makeCamera(c: Cam, width: number, height: number): THREE.OrthographicCamera | THREE.PerspectiveCamera {
  const up = new THREE.Vector3(...toThree(c.up)).sub(new THREE.Vector3(...toThree([0, 0, 0]))).normalize();
  let cam: THREE.OrthographicCamera | THREE.PerspectiveCamera;
  if (c.kind === "ortho") {
    const halfH = c.heightMm / 2000, halfW = halfH * (width / height);
    cam = new THREE.OrthographicCamera(-halfW, halfW, halfH, -halfH, 0.01, 20);
    cam.position.set(...toThree([c.target[0], c.target[1], 1000]));
  } else {
    cam = new THREE.PerspectiveCamera(c.fovDeg, width / height, 0.004, 10);
    cam.position.set(...toThree(c.position));
  }
  cam.up.copy(up);
  cam.lookAt(...toThree(c.target));
  cam.updateProjectionMatrix();
  cam.updateMatrixWorld(true);
  return cam;
}

// ---------------------------------------------------------------- overlay (picture style)
const GREEN = "#16be34", NAVY = "#0e2a57";

function useFont(): void {
  const { delayRender, continueRender } = useDelayRender();
  const [handle] = useState(() => delayRender("font"));
  useLayoutEffect(() => {
    new FontFace("Barlow Condensed", `url(${staticFile("fonts/BarlowCondensed-ExtraBold.ttf")})`, { weight: "800" }).load()
      .then((f) => { document.fonts.add(f); continueRender(handle); })
      .catch((e: unknown) => cancelRender(e instanceof Error ? e : new Error(String(e))));
  }, [continueRender, handle]);
}

export const AngleStudy: React.FC<{ angle: Angle }> = ({ angle }) => {
  const { width, height } = useVideoConfig();
  const frame = useCurrentFrame();
  useFont();
  useMemo(() => console.log(`[angle-check] PASS ${assertRenderable().join(", ")}`), []);
  const t = timeAt(frame);
  const state = useMemo(() => evalAt(t, frame), [t, frame]);
  const cam = useMemo(() => makeCamera(ANGLES[angle], width, height), [angle, width, height]);
  const proj = (p: Vec3): [number, number] => {
    const v = new THREE.Vector3(...toThree(p)).project(cam);
    return [((v.x + 1) / 2) * width, ((1 - v.y) / 2) * height];
  };
  const s = width / 1280;
  const r = 26 * s, lw = 9 * s, head = 30 * s;
  const arrows = ARROWS.map((a, i) => {
    const prog = Math.min(1, Math.max(0, (t - a.t0) / (a.t1 - a.t0)));
    if (prog <= 0) return null;
    const P = a.pts.slice(0, Math.max(2, Math.ceil(prog * (a.pts.length - 1)) + 1)).map(proj);
    // trim the start out from under the circle
    let k = 0;
    while (k < P.length - 2 && Math.hypot(P[k]![0] - P[0]![0], P[k]![1] - P[0]![1]) < r + 4 * s) k++;
    const L = P.slice(k);
    const tip = L[L.length - 1]!, prev = L[Math.max(0, L.length - 4)]!;
    const len = Math.hypot(tip[0] - prev[0], tip[1] - prev[1]) || 1;
    const u = [(tip[0] - prev[0]) / len, (tip[1] - prev[1]) / len], n = [-u[1]!, u[0]!];
    const h = Math.min(head, 0.6 * Math.hypot(tip[0] - L[0]![0], tip[1] - L[0]![1]));
    const base = [tip[0] - u[0]! * h, tip[1] - u[1]! * h];
    const line = [...L.slice(0, -1), [tip[0] - u[0]! * h * 0.6, tip[1] - u[1]! * h * 0.6]];
    return (
      <g key={i}>
        <polyline points={line.map((p) => `${p[0]!.toFixed(1)},${p[1]!.toFixed(1)}`).join(" ")} fill="none" stroke={GREEN} strokeWidth={lw} strokeLinecap="round" strokeLinejoin="round" />
        <polygon points={`${tip[0]},${tip[1]} ${base[0]! + n[0]! * h * 0.55},${base[1]! + n[1]! * h * 0.55} ${base[0]! - n[0]! * h * 0.55},${base[1]! - n[1]! * h * 0.55}`} fill={GREEN} />
      </g>
    );
  });
  // numbered circles: 1 at the heel pass, 2 at the shot; 2 steps aside when the pass is too short to show (as in the pictures)
  const c1 = proj(puckAt(STOPS[0]!)), c2raw = proj(puckAt(STOPS[1]!));
  const d12 = Math.hypot(c2raw[0] - c1[0], c2raw[1] - c1[1]);
  let c2 = c2raw;
  if (d12 < 5 * r) {
    const u = [(c2raw[0] - c1[0]) / (d12 || 1), (c2raw[1] - c1[1]) / (d12 || 1)];
    c2 = [c2raw[0] - u[1]! * (r + 10 * s), c2raw[1] + u[0]! * (r + 10 * s)];
  }
  const badges: [number, [number, number], number][] = [[1, c1, STOPS[0]!], [2, c2, STOPS[1]!]];
  return (
    <AbsoluteFill style={{ backgroundColor: NAVY }}>
      <ThreeCanvas width={width} height={height} camera={Object.assign(cam, { manual: true })} orthographic={ANGLES[angle].kind === "ortho"} linear={false} flat={false} gl={{ antialias: true, preserveDrawingBuffer: true }}>
        <ShotScene state={state} logTag={`angle-${angle}`} />
      </ThreeCanvas>
      <svg width={width} height={height} style={{ position: "absolute", left: 0, top: 0 }}>
        {arrows}
        {badges.map(([k, p, tk]) => (t >= tk - 1e-9 ? (
          <g key={k}>
            <circle cx={p[0]} cy={p[1]} r={r + 3 * s} fill="#ffffff" />
            <circle cx={p[0]} cy={p[1]} r={r} fill={NAVY} />
            <text x={p[0]} y={p[1] + r * 0.36} textAnchor="middle" fontFamily="Barlow Condensed" fontWeight={800} fontSize={r * 1.15} fill="#ffffff">{k}</text>
          </g>
        ) : null))}
      </svg>
    </AbsoluteFill>
  );
};
