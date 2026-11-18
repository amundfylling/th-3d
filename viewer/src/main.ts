// Interactive 3D move viewer (docs/viewer.md). Plays the saved traces live: the scene GLB is the same rink the videos use
// (meshopt + WebP compressed copy), figure and puck poses come from viewer-data/1 samples written by the same pure
// evaluator as the videos (scripts/viewer-export.ts). The page only interpolates between samples and draws (rule 7).
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const t0Load = performance.now();
const perf: Record<string, any> = { frames: [] as number[] };
(window as any).__viewer = { perf };

const mm = (x: number, y: number, z: number) => new THREE.Vector3(x / 1000, z / 1000, -y / 1000); // world mm (z up) -> glTF m (Y up)

interface ViewerData {
  move: string; trace_id: string; status: string; window_s: [number, number]; step_s: number; figures: string[];
  samples: { t: number; fig: number[][]; puck: number[] }[] | null;
  stride?: number; fig_flat?: number[]; puck_flat?: number[];
  phases: { id: string; t0: number; t1: number }[];
  events: { id: string; t: number; part: string | null; peak_impact_mm_s: number | null; touches: number | null; speed_after_mm_s: number | null; goal_line_y_mm: number | null }[];
  story: { title?: string; setup?: { title: string; text: string; highlight?: Record<string, string> }; beats?: { title: string; text: string; event?: string; contact?: string }[]; end_steps?: string[] };
  checks: { passed?: boolean; overlaps?: number; slide_passed?: boolean | null; robustness?: unknown };
}
const MOVES: { id: string; title: string; file: string }[] = [
  { id: "hjerpefinte", title: "Hjerpefinte", file: "moves/hjerpefinte.json" },
  { id: "nacka", title: "Näcka", file: "moves/nacka.json" },
  { id: "spjass", title: "Spjass", file: "moves/spjass.json" },
  { id: "invers-kryssar-velodrom", title: "Invers Kryssar med Velodrom", file: "moves/invers-kryssar-velodrom.json" },
];

// ---- renderer / scene -------------------------------------------------------------------------------------------
const canvas = $<HTMLCanvasElement>("c");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
renderer.toneMapping = THREE.ACESFilmicToneMapping;
const q = new URLSearchParams(location.search);
const maxDpr = Number(q.get("dpr") ?? 2);
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, maxDpr));
const camera = new THREE.PerspectiveCamera(36, 1, 0.01, 5);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.dampingFactor = 0.12; controls.minDistance = 0.08; controls.maxDistance = 1.6; controls.maxPolarAngle = Math.PI * 0.495;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0e1116);
scene.add(new THREE.HemisphereLight(0xffffff, 0x8c8c8c, 1.1));
const sun = new THREE.DirectionalLight(0xffffff, 2.2); sun.position.copy(mm(600, -350, 900)); scene.add(sun);

const VIEWS: Record<string, { label: string; pos: [number, number, number]; tgt: [number, number, number] }> = {
  oblique: { label: "Oblique", pos: [40, -690, 450], tgt: [0, 10, 0] },
  overhead: { label: "Overhead", pos: [0, -1, 900], tgt: [0, 0, 0] },
  side: { label: "Side", pos: [0, -900, 120], tgt: [0, 0, 20] },
  goalE: { label: "Behind W", pos: [-520, 0, 230], tgt: [120, 0, 0] },
  follow: { label: "Follow puck", pos: [0, 0, 0], tgt: [0, 0, 0] },
};
let viewKey = "oblique", follow = false;
let camAnim: { t: number; p0: THREE.Vector3; g0: THREE.Vector3; p1: THREE.Vector3; g1: THREE.Vector3 } | null = null;
function setView(k: string) {
  viewKey = k; follow = k === "follow";
  document.querySelectorAll<HTMLButtonElement>("#views [data-v]").forEach((b) => b.classList.toggle("on", b.dataset.v === k));
  if (follow) { dirty = true; return; }
  const v = VIEWS[k]!;
  camAnim = { t: 0, p0: camera.position.clone(), g0: controls.target.clone(), p1: mm(...v.pos), g1: mm(...v.tgt) };
  dirty = true;
}

// ---- state -------------------------------------------------------------------------------------------------------
let rink: THREE.Object3D, puckNode: THREE.Object3D;
const figNodes: Record<string, THREE.Object3D> = {};
const rest = new Map<THREE.Object3D, { p: THREE.Vector3; q: THREE.Quaternion }>();
let data: ViewerData, nF = 0, nS = 0, fig: Float32Array, puckA: Float32Array, tRel = 0, dur = 1;
let playing = false, speed = 0.25, loop = true, dirty = true, trailOn = true, ghostOn = true;
let trailLine: THREE.Mesh | null = null, trailGhost: THREE.Mesh | null = null, trailN = 0;
const marks: THREE.Object3D[] = [];
const highlight = new Set<string>();

const rings = new Map<string, THREE.Mesh>();
function applyHighlight() {
  for (const pid of Object.keys(figNodes)) {
    let ring = rings.get(pid);
    if (!ring) { ring = new THREE.Mesh(new THREE.RingGeometry(0.019, 0.024, 40).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0xffa000, side: THREE.DoubleSide, depthWrite: false, transparent: true, opacity: 0.95 })); ring.position.y = 0.0008; ring.renderOrder = 6; rings.set(pid, ring); }
    figNodes[pid]!.add(ring); ring.visible = highlight.has(pid);
  }
  dirty = true;
}

const tmpQ = new THREE.Quaternion(), tmpQ2 = new THREE.Quaternion();
function pose(t: number) {
  const k = Math.min(Math.max(t / data.step_s, 0), nS - 1 - 1e-9), i = Math.floor(k), f = k - i;
  for (const r of rest) { r[0].position.copy(r[1].p); r[0].quaternion.copy(r[1].q); }
  const w = 7 * nF, a = i * w, b = a + w;
  data.figures.forEach((pid, j) => {
    const n = figNodes[pid]; if (!n) return;
    const o = j * 7;
    n.position.set(fig[a + o]! + (fig[b + o]! - fig[a + o]!) * f, fig[a + o + 1]! + (fig[b + o + 1]! - fig[a + o + 1]!) * f, fig[a + o + 2]! + (fig[b + o + 2]! - fig[a + o + 2]!) * f);
    tmpQ.fromArray(fig as unknown as number[], a + o + 3); tmpQ2.fromArray(fig as unknown as number[], b + o + 3);
    n.quaternion.slerpQuaternions(tmpQ, tmpQ2, f);
  });
  const p = 3 * i, p1 = p + 3;
  puckNode.position.set(puckA[p]! + (puckA[p1]! - puckA[p]!) * f, puckA[p + 1]! + (puckA[p1 + 1]! - puckA[p + 1]!) * f, puckA[p + 2]! + (puckA[p1 + 2]! - puckA[p + 2]!) * f);
  if (trailLine) (trailLine.geometry as THREE.BufferGeometry).setDrawRange(0, Math.max(0, Math.floor(k / trailStride)) * 6);
}
let trailStride = 2;
function ribbon(color: number, opacity: number) {
  const n = Math.ceil(nS / trailStride), pos = new Float32Array(n * 2 * 3), idx: number[] = [];
  const hw = 0.0022, y = 0.0006;
  for (let j = 0; j < n; j++) {
    const s = Math.min(j * trailStride, nS - 1), sp = Math.min(s + trailStride, nS - 1), sm = Math.max(s - trailStride, 0);
    const x = puckA[3 * s]!, z = puckA[3 * s + 2]!;
    let dx = puckA[3 * sp]! - puckA[3 * sm]!, dz = puckA[3 * sp + 2]! - puckA[3 * sm + 2]!;
    const L = Math.hypot(dx, dz) || 1; dx /= L; dz /= L;
    pos.set([x - dz * hw, y, z + dx * hw, x + dz * hw, y, z - dx * hw], j * 6);
    if (j < n - 1) idx.push(2 * j, 2 * j + 1, 2 * j + 2, 2 * j + 1, 2 * j + 3, 2 * j + 2);
  }
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(pos, 3)); g.setIndex(idx);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color, transparent: opacity < 1, opacity, side: THREE.DoubleSide, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
  m.renderOrder = 5; m.frustumCulled = false; return { m, n };
}

async function loadMove(id: string) {
  const mv = MOVES.find((m) => m.id === id) ?? MOVES[0]!;
  const tl = performance.now();
  const d = (await (await fetch(mv.file)).json()) as ViewerData;
  perf[`move_${mv.id}_fetch_parse_ms`] = Math.round(performance.now() - tl);
  data = d; nF = d.figures.length;
  // unpack packed arrays
  fig = Float32Array.from(d.fig_flat!); puckA = Float32Array.from(d.puck_flat!);
  nS = puckA.length / 3; dur = (nS - 1) * d.step_s; tRel = 0;
  for (const o of [trailLine, trailGhost, ...marks]) if (o) { scene.remove(o); }
  marks.length = 0;
  highlight.clear(); for (const pid of Object.keys(figNodes)) { rings.get(pid)?.removeFromParent(); delete figNodes[pid]; }
  for (const pid of d.figures) { const n = rink.getObjectByName(THREE.PropertyBinding.sanitizeNodeName(`Figure.${pid}`)); if (n) figNodes[pid] = n; }
  applyHighlight();
  { const g = ribbon(0x4fb3ff, 0.35); trailGhost = g.m; scene.add(g.m); const h = ribbon(0xffd23f, 1); trailLine = h.m; scene.add(h.m); trailN = h.n; trailGhost.visible = ghostOn; trailLine.visible = trailOn; }
  for (const e of d.events) {
    const k = Math.round((e.t - d.window_s[0]) / d.step_s); if (k < 0 || k >= nS) continue;
    const s = new THREE.Mesh(new THREE.SphereGeometry(0.0016, 12, 8), new THREE.MeshBasicMaterial({ color: e.id.startsWith("contact") ? 0xff5050 : 0xffffff }));
    s.position.set(puckA[3 * k]!, 0.0016, puckA[3 * k + 2]!); scene.add(s); marks.push(s);
  }
  renderSide(mv); buildTimeline(); location.hash = mv.id; ($("scrub") as HTMLInputElement).value = "0";
  $("hud").textContent = `${mv.title} · ${d.status.toUpperCase()} trace · ${d.trace_id}`;
  pose(0); dirty = true; syncUI();
}

function renderSide(mv: (typeof MOVES)[number]) {
  const s = data.story, c = data.checks, el = $("side");
  const parts: string[] = [`<h1>${s.title ?? mv.title}</h1><p><span class="tag">${data.status}</span> <span class="tag">${data.figures.join(" · ")}</span> <span class="tag">${dur.toFixed(2)} s</span></p>`];
  if (s.setup) parts.push(`<h2>${s.setup.title}</h2><p>${s.setup.text}</p>`);
  parts.push(`<h2>Highlight figure</h2><div class="row">${data.figures.map((p) => `<button data-hl="${p}">${p}${s.setup?.highlight?.[p] ? " · " + s.setup.highlight[p].toLowerCase() : ""}</button>`).join("")}</div>`);
  parts.push(`<h2>Events (tap to jump)</h2>`);
  for (const e of data.events) parts.push(`<button class="ev" data-t="${(e.t - data.window_s[0]).toFixed(5)}">${e.id} <small>${(e.t - data.window_s[0]).toFixed(3)} s${e.part ? " · " + e.part : ""}${e.peak_impact_mm_s != null ? " · impact " + e.peak_impact_mm_s + " mm/s" : ""}${e.speed_after_mm_s != null ? " · after " + e.speed_after_mm_s + " mm/s" : ""}</small></button>`);
  if (s.beats?.length) { parts.push(`<h2>Story</h2>`); for (const b of s.beats) parts.push(`<p><b>${b.title}</b><br>${b.text}</p>`); }
  parts.push(`<h2>Checks</h2><p>contact check ${c.passed ? '<span class="ok">passed</span>' : "n/a"} · overlaps ${c.overlaps ?? "n/a"} · slide check ${c.slide_passed == null ? "n/a" : c.slide_passed ? '<span class="ok">passed</span>' : "FAILED"}</p>`);
  parts.push(`<p style="color:var(--mute);font-size:12px">Poses are the saved trace sampled every ${(data.step_s * 1000).toFixed(0)} ms by the same evaluator as the videos; the viewer only interpolates.</p>`);
  el.innerHTML = parts.join("");
  el.querySelectorAll<HTMLButtonElement>("[data-hl]").forEach((b) => b.addEventListener("click", () => { const p = b.dataset.hl!; highlight.has(p) ? highlight.delete(p) : highlight.add(p); b.classList.toggle("on"); b.classList.add("hot"); applyHighlight(); }));
  el.querySelectorAll<HTMLButtonElement>("[data-t]").forEach((b) => b.addEventListener("click", () => seek(Number(b.dataset.t))));
}
const COLORS = ["#4fb3ff", "#ffb020", "#7bd88f", "#d98cff", "#ff7b7b", "#6fe0d6", "#c0c06a"];
function buildTimeline() {
  const tl = $("tl"); tl.innerHTML = "";
  data.phases.forEach((p, i) => { const e = document.createElement("i"); e.style.left = ((p.t0 - data.window_s[0]) / dur) * 100 + "%"; e.style.width = ((p.t1 - p.t0) / dur) * 100 + "%"; e.style.background = COLORS[i % COLORS.length]!; e.title = p.id; tl.appendChild(e); });
}
function phaseAt(t: number) { const a = t + data.window_s[0]; let cur = data.phases[0]; for (const p of data.phases) if (a >= p.t0) cur = p; return cur?.id ?? ""; }
function seek(t: number) { tRel = Math.min(Math.max(t, 0), dur); playing = false; syncUI(); dirty = true; }
function syncUI() {
  ($("scrub") as HTMLInputElement).value = String(Math.round((tRel / dur) * 1000));
  $("time").textContent = `${tRel.toFixed(3)} / ${dur.toFixed(2)} s`;
  $("phase").textContent = phaseAt(tRel).replace(/_/g, " ");
  $("play").textContent = playing ? "⏸ Pause" : "▶ Play";
}

// ---- UI wiring ----------------------------------------------------------------------------------------------------
const mk = (parent: HTMLElement, label: string, on: () => void, extra?: (b: HTMLButtonElement) => void) => { const b = document.createElement("button"); b.textContent = label; b.addEventListener("click", on); extra?.(b); parent.appendChild(b); return b; };
{
  const sp = $("speeds"); sp.append(Object.assign(document.createElement("span"), { textContent: "Speed", style: "color:var(--mute);font-size:12px" }));
  for (const s of [0.02, 0.1, 0.25, 0.5, 1]) mk(sp, `${s}×`, () => { speed = s; sp.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.textContent === `${s}×`)); }, (b) => b.classList.toggle("on", s === speed));
  const vw = $("views"); for (const [k, v] of Object.entries(VIEWS)) mk(vw, v.label, () => setView(k), (b) => { b.dataset.v = k; b.classList.toggle("on", k === viewKey); });
  const op = $("opts");
  mk(op, "Loop", () => { loop = !loop; }, (b) => { b.classList.add("on"); b.addEventListener("click", () => b.classList.toggle("on", loop)); });
  mk(op, "Trail", () => { trailOn = !trailOn; if (trailLine) trailLine.visible = trailOn; dirty = true; }, (b) => { b.classList.add("on"); b.addEventListener("click", () => b.classList.toggle("on", trailOn)); });
  mk(op, "Path", () => { ghostOn = !ghostOn; if (trailGhost) trailGhost.visible = ghostOn; dirty = true; }, (b) => { b.classList.add("on"); b.addEventListener("click", () => b.classList.toggle("on", ghostOn)); });
  mk(op, "−5 ms", () => seek(tRel - 0.005)); mk(op, "+5 ms", () => seek(tRel + 0.005));
  const sel = document.createElement("select"); sel.setAttribute("aria-label", "Move");
  for (const m of MOVES) sel.add(new Option(m.title, m.id));
  sel.addEventListener("change", () => loadMove(sel.value)); op.appendChild(sel); (window as any).__sel = sel;
}
$("play").addEventListener("click", () => { if (!playing && tRel >= dur - 1e-6) tRel = 0; playing = !playing; syncUI(); });
($("scrub") as HTMLInputElement).addEventListener("input", (e) => { tRel = (Number((e.target as HTMLInputElement).value) / 1000) * dur; playing = false; syncUI(); dirty = true; });
addEventListener("keydown", (e) => { if (e.code === "Space") { e.preventDefault(); $("play").click(); } else if (e.code === "ArrowLeft") seek(tRel - (e.shiftKey ? 0.05 : 0.005)); else if (e.code === "ArrowRight") seek(tRel + (e.shiftKey ? 0.05 : 0.005)); });
controls.addEventListener("change", () => { dirty = true; }); controls.addEventListener("start", () => { camAnim = null; });

function resize() {
  const st = $("stage"), w = st.clientWidth, h = st.clientHeight; if (!w || !h) return;
  renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); dirty = true;
}
new ResizeObserver(resize).observe($("stage"));

// ---- main loop ----------------------------------------------------------------------------------------------------
let last = performance.now();
const bench = q.has("bench");
function frame(now: number) {
  requestAnimationFrame(frame);
  const dt = Math.min((now - last) / 1000, 0.1); last = now;
  if (!data) return;
  if (playing) { tRel += dt * speed; if (tRel >= dur) { if (loop) tRel -= dur; else { tRel = dur; playing = false; } } syncUI(); dirty = true; }
  if (camAnim) { camAnim.t = Math.min(camAnim.t + dt / 0.45, 1); const e = camAnim.t * camAnim.t * (3 - 2 * camAnim.t); camera.position.lerpVectors(camAnim.p0, camAnim.p1, e); controls.target.lerpVectors(camAnim.g0, camAnim.g1, e); if (camAnim.t >= 1) camAnim = null; dirty = true; }
  if (follow) { const p = puckNode.position; controls.target.lerp(p, 0.2); if (camera.position.distanceTo(controls.target) > 0.3) camera.position.lerp(p.clone().add(new THREE.Vector3(0.05, 0.09, 0.16)), 0.05); dirty = true; }
  controls.update();
  if (dirty || bench) {
    dirty = false; const t1 = performance.now();
    pose(tRel); renderer.render(scene, camera);
    if (perf.frames.length < 4000) perf.frames.push(now);
    perf.cpuMs = (perf.cpuMs ?? []); if (perf.cpuMs.length < 4000) perf.cpuMs.push(performance.now() - t1);
    if (!perf.firstFrame) { perf.firstFrame = Math.round(performance.now() - t0Load); }
  }
}

(async () => {
  const loader = new GLTFLoader(); loader.setMeshoptDecoder(MeshoptDecoder);
  const tg = performance.now();
  const gltf = await loader.loadAsync(q.get("scene") ?? "scene.glb");
  perf.scene_load_ms = Math.round(performance.now() - tg);
  rink = gltf.scene; scene.add(rink);
  const pm = new THREE.PMREMGenerator(renderer), env = pm.fromScene(new RoomEnvironment(), 0.04).texture; pm.dispose();
  rink.traverse((o) => { const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined; if (m && m.name?.startsWith("fig_")) { m.envMap = env; m.envMapIntensity = m.metalness > 0.5 ? 1 : 0.12; m.needsUpdate = true; } });
  // Clear plastic (goal screens): KHR transmission makes three.js render the whole scene twice per frame. A plain
  // translucent material looks the same from above and halves the work; ?transmission=1 keeps the real thing.
  if (!q.has("transmission")) rink.traverse((o) => { const m = (o as THREE.Mesh).material as THREE.MeshPhysicalMaterial | undefined; if (m && m.transmission > 0) { m.transmission = 0; m.transparent = true; m.opacity = 0.1; m.depthWrite = false; m.needsUpdate = true; } });
  puckNode = rink.getObjectByName("Puck")!;
  rink.traverse((o) => { if (o.name === "Puck" || o.name.startsWith("Figure.")) rest.set(o, { p: o.position.clone(), q: o.quaternion.clone() }); });
  const start = location.hash.slice(1) || MOVES[0]!.id;

  (window as any).__sel.value = MOVES.find((m) => m.id === start)?.id ?? MOVES[0]!.id;
  const v = VIEWS.oblique!; camera.position.copy(mm(...v.pos)); controls.target.copy(mm(...v.tgt));
  resize();
  await loadMove((window as any).__sel.value);
  $("loading").remove();
  perf.ready_ms = Math.round(performance.now() - t0Load);
  requestAnimationFrame(frame);
  if (q.has("play")) { playing = true; speed = Number(q.get("speed") ?? 1); syncUI(); }
  if (q.has("view")) setView(q.get("view")!);
  addEventListener("hashchange", () => { const id = location.hash.slice(1); if (id && id !== data.move) { (window as any).__sel.value = id; loadMove(id); } });
})();
// exposed for the benchmark script
Object.assign((window as any).__viewer, { renderer, scene, camera, setView, loadMove, seek, get dur() { return dur; }, setSpeed: (s: number) => { speed = s; }, play: () => { playing = true; syncUI(); }, setT: (t: number) => { tRel = t; syncUI(); dirty = true; } });
