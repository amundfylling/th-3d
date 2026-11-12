// Combo editor stage: the three.js scene. Loads the table (public/table.glb, a web-sized copy of the repo's scene
// GLB), poses the twelve figures and the puck from a combo, and draws the arrows, the numbered markers and the
// editing handles. Draws only when something changed (requestRender), so an idle page uses no GPU.
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { type Arrow, type CameraPose, type Combo, type Marker, type Vec2, MARKER_RADIUS_MM, PIDS, RINK, SLOTS, arrowDrawnLine, arrowRibbon, headingDeg, pivotOf, polylineLength, slicePolyline } from "./model.ts";

export const toThree = (x: number, y: number, z = 0): THREE.Vector3 => new THREE.Vector3(x / 1000, z / 1000, -y / 1000);
export const toWorld = (v: THREE.Vector3): Vec2 => [v.x * 1000, -v.z * 1000];

export type Selection = { kind: "figure"; pid: string } | { kind: "puck" } | { kind: "arrow"; id: string } | { kind: "marker"; id: string } | null;
export interface ViewPreset { id: string; label: string; x: [number, number]; y: [number, number]; tiltDeg: number; azimuthDeg?: number }
export const VIEWS: ViewPreset[] = [
  { id: "half", label: "Attack", x: [68, 446], y: [-254, 254], tiltDeg: 20 },
  { id: "mid", label: "Attack +", x: [-95, 446], y: [-254, 254], tiltDeg: 20 },
  { id: "full", label: "Full rink", x: [-446, 446], y: [-254, 254], tiltDeg: 20 },
  { id: "top", label: "Top", x: [-446, 446], y: [-254, 254], tiltDeg: 0.6 },
  { id: "side", label: "Side", x: [-446, 446], y: [-254, 254], tiltDeg: 58, azimuthDeg: 90 },
  { id: "goal", label: "Behind goal", x: [-120, 446], y: [-254, 254], tiltDeg: 62 },
];
const FOV = 24;

function markerTexture(label: string, color: string): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 192;
  const g = c.getContext("2d")!;
  g.beginPath(); g.arc(96, 96, 94, 0, Math.PI * 2); g.fillStyle = "#ffffff"; g.fill();
  g.beginPath(); g.arc(96, 96, 82, 0, Math.PI * 2); g.fillStyle = color; g.fill();
  g.fillStyle = "#ffffff"; g.textAlign = "center"; g.textBaseline = "middle";
  g.font = `${label.length > 2 ? 78 : label.length > 1 ? 100 : 122}px "Barlow Condensed", "Arial Narrow", sans-serif`;
  g.fillText(label, 96, 104);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}

function dotTexture(fill: string, stroke: string): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  g.beginPath(); g.arc(32, 32, 24, 0, Math.PI * 2); g.fillStyle = fill; g.fill(); g.lineWidth = 8; g.strokeStyle = stroke; g.stroke();
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export class Stage {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(FOV, 1, 0.02, 20);
  readonly controls: OrbitControls;
  readonly figures: Record<string, THREE.Object3D> = {};
  puck!: THREE.Object3D;
  arrowsOnTop = true;
  background = "#0e2a57";
  /** Called after every camera move by the user (not by a preset animation). */
  onUserCamera: (() => void) | null = null;

  private readonly overlay = new THREE.Group();
  private readonly handles = new THREE.Group();
  private readonly arrowMeshes = new Map<string, THREE.Mesh>();
  private readonly markerSprites = new Map<string, THREE.Sprite>();
  private readonly markerTextures = new Map<string, THREE.CanvasTexture>();
  private readonly raycaster = new THREE.Raycaster();
  private readonly handleTex = { point: dotTexture("#ffffff", "#1f5fbf"), mid: dotTexture("#cfe0ff", "#ffffff"), knob: dotTexture("#ffcc1a", "#0e2a57") };
  private needsRender = true;
  private animating: { from: CameraPose; to: CameraPose; t0: number; ms: number } | null = null;
  private frameCallbacks = new Set<(now: number) => void>();

  readonly canvas: HTMLCanvasElement;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.scene.background = new THREE.Color(this.background);
    // the lights of the repo's video scene (remotion/ShotScene.tsx), plus a soft shadow under the figures
    this.scene.add(new THREE.HemisphereLight("#ffffff", "#8c8c8c", 1.1));
    const sun = new THREE.DirectionalLight("#ffffff", 2.2);
    sun.position.copy(toThree(600, -350, 900));
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    const sc = sun.shadow.camera;
    sc.left = -0.55; sc.right = 0.55; sc.top = 0.42; sc.bottom = -0.42; sc.near = 0.3; sc.far = 2.2;
    sun.shadow.bias = -0.0004;
    sun.shadow.normalBias = 0.0006;
    sun.shadow.radius = 5;
    sun.shadow.intensity = 0.55;
    this.scene.add(sun, this.overlay, this.handles);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.12;
    this.controls.minDistance = 0.15;
    this.controls.maxDistance = 4;
    this.controls.minPolarAngle = 0.01;
    this.controls.maxPolarAngle = Math.PI / 2 - 0.03;
    this.controls.zoomToCursor = true;
    this.controls.addEventListener("change", () => { this.needsRender = true; });
    this.controls.addEventListener("end", () => this.onUserCamera?.());
    new ResizeObserver(() => this.resize()).observe(canvas.parentElement!);
    this.resize();
    const loop = (now: number): void => {
      requestAnimationFrame(loop);
      for (const cb of this.frameCallbacks) cb(now);
      if (this.animating) this.stepCameraAnimation(now);
      else if (this.controls.enabled) this.controls.update();
      if (this.needsRender) { this.needsRender = false; this.renderer.render(this.scene, this.camera); }
    };
    requestAnimationFrame(loop);
  }

  requestRender(): void { this.needsRender = true; }
  onFrame(cb: (now: number) => void): () => void { this.frameCallbacks.add(cb); return () => this.frameCallbacks.delete(cb); }

  async load(url: string, onProgress: (fraction: number) => void): Promise<void> {
    const loader = new GLTFLoader();
    loader.setMeshoptDecoder(MeshoptDecoder);
    const gltf = await loader.loadAsync(url, (e) => onProgress(e.total ? e.loaded / e.total : 0.5));
    const pm = new THREE.PMREMGenerator(this.renderer);
    const env = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    pm.dispose();
    const maxAniso = this.renderer.capabilities.getMaxAnisotropy();
    gltf.scene.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      const m = mesh.material as THREE.MeshPhysicalMaterial;
      if (m.name.startsWith("fig_")) { m.envMap = env; m.envMapIntensity = m.metalness > 0.5 ? 1.0 : 0.12; }
      if (m.transmission > 0) {
        // the clear end screens: plain transparency instead of three's transmission pass, which would draw the whole
        // scene a second time on every frame
        m.transmission = 0; m.transparent = true; m.opacity = 0.3; m.depthWrite = false; m.roughness = 0.08;
        m.envMap = env; m.envMapIntensity = 0.6;
        mesh.renderOrder = 2;
      }
      if (m.map) m.map.anisotropy = maxAniso;
      m.needsUpdate = true;
    });
    for (const pid of PIDS) {
      const node = gltf.scene.getObjectByName(THREE.PropertyBinding.sanitizeNodeName(`Figure.${pid}`));
      if (!node) throw new Error(`figure ${pid} is not in the table model`);
      node.traverse((o) => { o.castShadow = true; o.userData.pid = pid; });
      this.figures[pid] = node;
    }
    const puck = gltf.scene.getObjectByName("Puck");
    if (!puck) throw new Error("the puck is not in the table model");
    puck.traverse((o) => { o.castShadow = true; o.userData.puck = true; });
    this.puck = puck;
    for (const name of ["Ice", "InnerBoards", "HousingRim", "HousingBase"]) gltf.scene.getObjectByName(name)?.traverse((o) => { o.receiveShadow = true; });
    for (const name of ["Goal.W", "Goal.E", "InnerBoards"]) gltf.scene.getObjectByName(THREE.PropertyBinding.sanitizeNodeName(name))?.traverse((o) => { o.castShadow = true; });
    this.scene.add(gltf.scene);
    await document.fonts.load('100px "Barlow Condensed"').catch(() => undefined);
    this.needsRender = true;
  }

  private resize(): void {
    const el = this.canvas.parentElement!;
    const w = Math.max(1, el.clientWidth), h = Math.max(1, el.clientHeight);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.needsRender = true;
  }

  // ------------------------------------------------------------ posing

  applyFigures(combo: Combo): void {
    for (const pid of PIDS) {
      const node = this.figures[pid], pose = combo.figures[pid];
      if (!node || !pose) continue;
      const p = pivotOf(pid, pose);
      node.position.x = p[0] / 1000;
      node.position.z = -p[1] / 1000;
      node.quaternion.setFromAxisAngle(THREE.Object3D.DEFAULT_UP, (headingDeg(pid, pose.theta_deg) * Math.PI) / 180);
      node.visible = !pose.hidden;
    }
    this.setPuck([combo.puck.x_mm, combo.puck.y_mm]);
    this.puck.visible = !combo.puck.hidden;
    this.needsRender = true;
  }

  setPuck(p: Vec2): void {
    this.puck.position.x = p[0] / 1000;
    this.puck.position.z = -p[1] / 1000;
    this.needsRender = true;
  }

  // ------------------------------------------------------------ arrows and markers

  /** Rebuilds the arrows and markers. `reveal` (play-back) limits how much of each arrow is drawn (mm; absent = all). */
  drawOverlay(combo: Combo, reveal?: { arrows: Map<string, number>; markers: Set<string> }): void {
    const seenA = new Set<string>();
    for (const a of combo.arrows) {
      seenA.add(a.id);
      let line = arrowDrawnLine(a, combo.markers);
      const shown = reveal?.arrows.get(a.id);
      if (reveal) line = shown === undefined || shown <= 0.5 ? [] : slicePolyline(line, 0, Math.min(shown, polylineLength(line)));
      const rib = arrowRibbon(line, a.width_mm, { dashed: a.style === "dashed", head: a.head });
      let mesh = this.arrowMeshes.get(a.id);
      if (!mesh) {
        mesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({ toneMapped: false, side: THREE.DoubleSide, transparent: true }));
        mesh.frustumCulled = false;
        this.arrowMeshes.set(a.id, mesh);
        this.overlay.add(mesh);
      }
      const pos = new Float32Array((rib.positions.length / 2) * 3);
      for (let i = 0; i < rib.positions.length / 2; i++) { pos[3 * i] = rib.positions[2 * i]! / 1000; pos[3 * i + 1] = 0.0011; pos[3 * i + 2] = -rib.positions[2 * i + 1]! / 1000; }
      mesh.geometry.dispose();
      mesh.geometry = new THREE.BufferGeometry();
      mesh.geometry.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      mesh.geometry.setIndex(rib.indices);
      const mat = mesh.material as THREE.MeshBasicMaterial;
      mat.color.set(a.color);
      mat.depthTest = !this.arrowsOnTop;
      mat.depthWrite = false;
      mesh.renderOrder = this.arrowsOnTop ? 10 + combo.arrows.indexOf(a) * 0.01 : 1;
    }
    for (const [id, mesh] of this.arrowMeshes) if (!seenA.has(id)) { this.overlay.remove(mesh); mesh.geometry.dispose(); (mesh.material as THREE.Material).dispose(); this.arrowMeshes.delete(id); }
    const seenM = new Set<string>();
    for (const m of combo.markers) {
      seenM.add(m.id);
      let sp = this.markerSprites.get(m.id);
      if (!sp) {
        sp = new THREE.Sprite(new THREE.SpriteMaterial({ toneMapped: false, depthTest: false, depthWrite: false, transparent: true }));
        sp.renderOrder = 20;
        this.markerSprites.set(m.id, sp);
        this.overlay.add(sp);
      }
      const key = `${m.label}|${m.color}`;
      let tex = this.markerTextures.get(key);
      if (!tex) { tex = markerTexture(m.label, m.color); this.markerTextures.set(key, tex); }
      (sp.material as THREE.SpriteMaterial).map = tex;
      sp.position.copy(toThree(m.x_mm, m.y_mm, 1.5));
      const d = (MARKER_RADIUS_MM * 2 * (94 / 82)) / 1000;
      sp.scale.set(d, d, 1);
      sp.visible = !reveal || reveal.markers.has(m.id);
    }
    for (const [id, sp] of this.markerSprites) if (!seenM.has(id)) { this.overlay.remove(sp); (sp.material as THREE.Material).dispose(); this.markerSprites.delete(id); }
    this.needsRender = true;
  }

  // ------------------------------------------------------------ handles

  /** Editing handles for the selection and the arrow being drawn. Never part of an export. */
  drawHandles(combo: Combo, sel: Selection, draft: { points: Vec2[]; cursor: Vec2 | null; color: string; dashed: boolean } | null): void {
    for (const c of [...this.handles.children]) {
      this.handles.remove(c);
      const mesh = c as THREE.Mesh;
      if (mesh.geometry && !(c instanceof THREE.Sprite)) mesh.geometry.dispose();
      const mat = (mesh.material ?? null) as THREE.Material | null;
      mat?.dispose();
    }
    // handle dots keep their size on screen; a little smaller on a tall phone screen, where the height sets the scale
    const k = this.camera.aspect < 0.8 ? 0.8 : 1;
    const dot = (p: Vec2, tex: THREE.Texture, base: number): void => {
      const size = base * k;
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, depthWrite: false, sizeAttenuation: false, toneMapped: false, transparent: true }));
      s.position.copy(toThree(p[0], p[1], 1.5));
      s.scale.set(size, size, 1);
      s.renderOrder = 30;
      this.handles.add(s);
    };
    const flat = (positions: number[], indices: number[], color: string, opacity: number): void => {
      const g = new THREE.BufferGeometry();
      const pos = new Float32Array((positions.length / 2) * 3);
      for (let i = 0; i < positions.length / 2; i++) { pos[3 * i] = positions[2 * i]! / 1000; pos[3 * i + 1] = 0.0009; pos[3 * i + 2] = -positions[2 * i + 1]! / 1000; }
      g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      g.setIndex(indices);
      const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color, opacity, transparent: true, depthTest: false, depthWrite: false, toneMapped: false, side: THREE.DoubleSide }));
      m.renderOrder = 5;
      m.frustumCulled = false;
      this.handles.add(m);
    };
    if (sel?.kind === "figure" && combo.figures[sel.pid]) {
      const pose = combo.figures[sel.pid]!, p = pivotOf(sel.pid, pose);
      const slot = RINK.slots[sel.pid]!.map((q): Vec2 => [q[0]!, q[1]!]);
      const track = arrowRibbon(slot, 5, { dashed: false, head: false });
      flat(track.positions, track.indices, "#ffcc1a", 0.55);
      const ring: Vec2[] = Array.from({ length: 73 }, (_, i): Vec2 => [p[0] + RING_MM * Math.cos((i / 72) * 2 * Math.PI), p[1] + RING_MM * Math.sin((i / 72) * 2 * Math.PI)]);
      const rr = arrowRibbon(ring, 2.6, { dashed: false, head: false });
      flat(rr.positions, rr.indices, "#ffcc1a", 0.95);
      dot(knobOf(sel.pid, pose.arc_mm, pose.theta_deg), this.handleTex.knob, 0.025);
    }
    if (sel?.kind === "puck") {
      const ring: Vec2[] = Array.from({ length: 49 }, (_, i): Vec2 => [combo.puck.x_mm + 17 * Math.cos((i / 48) * 2 * Math.PI), combo.puck.y_mm + 17 * Math.sin((i / 48) * 2 * Math.PI)]);
      const rr = arrowRibbon(ring, 2.2, { dashed: false, head: false });
      flat(rr.positions, rr.indices, "#ffcc1a", 0.95);
    }
    if (sel?.kind === "arrow") {
      const a = combo.arrows.find((x) => x.id === sel.id);
      if (a) {
        for (let i = 0; i + 1 < a.points_mm.length; i++) dot(midOf(a, i), this.handleTex.mid, 0.012);
        for (const q of a.points_mm) dot(q, this.handleTex.point, 0.019);
      }
    }
    if (sel?.kind === "marker") {
      const m = combo.markers.find((x) => x.id === sel.id);
      if (m) {
        const ring: Vec2[] = Array.from({ length: 49 }, (_, i): Vec2 => [m.x_mm + 15.5 * Math.cos((i / 48) * 2 * Math.PI), m.y_mm + 15.5 * Math.sin((i / 48) * 2 * Math.PI)]);
        const rr = arrowRibbon(ring, 2.2, { dashed: false, head: false });
        flat(rr.positions, rr.indices, "#ffcc1a", 0.95);
      }
    }
    if (draft && draft.points.length) {
      const pts = draft.cursor ? [...draft.points, draft.cursor] : draft.points;
      if (pts.length > 1) {
        const rib = arrowRibbon(pts, 4.2, { dashed: draft.dashed, head: true });
        flat(rib.positions, rib.indices, draft.color, 0.8);
      }
      for (const q of draft.points) dot(q, this.handleTex.point, 0.017);
    }
    this.needsRender = true;
  }

  setHandlesVisible(v: boolean): void { this.handles.visible = v; this.needsRender = true; }

  // ------------------------------------------------------------ picking

  private ray(clientX: number, clientY: number): THREE.Raycaster {
    const r = this.canvas.getBoundingClientRect();
    this.raycaster.setFromCamera(new THREE.Vector2(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1), this.camera);
    return this.raycaster;
  }

  /** The point of the horizontal plane at height `zMm` under the pointer (world mm), or null above the horizon. */
  planePoint(clientX: number, clientY: number, zMm = 0): Vec2 | null {
    const hit = new THREE.Vector3();
    if (!this.ray(clientX, clientY).ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -zMm / 1000), hit)) return null;
    return toWorld(hit);
  }

  /** The figure or the puck under the pointer, with the hit point (world mm and height). */
  pickBody(clientX: number, clientY: number, slopPx = 0): { kind: "figure"; pid: string; at: Vec2; zMm: number; local: Vec2 } | { kind: "puck"; at: Vec2; zMm: number } | null {
    const targets = [...Object.values(this.figures).filter((f) => f.visible), ...(this.puck.visible ? [this.puck] : [])];
    let hit = this.ray(clientX, clientY).intersectObjects(targets, true)[0];
    // the sticks are thin: a near miss still grabs (the closest hit on a small circle round the pointer)
    for (let i = 0; !hit && slopPx > 0 && i < 8; i++) {
      const a = (i / 8) * 2 * Math.PI;
      hit = this.ray(clientX + slopPx * Math.cos(a), clientY + slopPx * Math.sin(a)).intersectObjects(targets, true)[0];
    }
    if (!hit) return null;
    const at = toWorld(hit.point), zMm = hit.point.y * 1000;
    if (hit.object.userData.puck) return { kind: "puck", at, zMm };
    const pid = hit.object.userData.pid as string;
    const l = this.figures[pid]!.worldToLocal(hit.point.clone());
    return { kind: "figure", pid, at, zMm, local: [l.x * 1000, -l.z * 1000] };
  }

  /** Screen position (CSS px, relative to the viewport) of a point on the ice. */
  screenOf(p: Vec2, zMm = 0): Vec2 {
    const v = toThree(p[0], p[1], zMm).project(this.camera), r = this.canvas.getBoundingClientRect();
    return [r.left + ((v.x + 1) / 2) * r.width, r.top + ((1 - v.y) / 2) * r.height];
  }

  // ------------------------------------------------------------ camera

  cameraPose(): CameraPose {
    const p = this.camera.position, t = this.controls.target, r = (v: number): number => Math.round(v * 1e4) / 10;
    return { position_mm: [r(p.x), r(-p.z), r(p.y)], target_mm: [r(t.x), r(-t.z), r(t.y)], fov_deg: this.camera.fov };
  }

  /** The camera of a preset: the given ice rectangle fills the picture, seen tilted from the vertical. */
  presetPose(v: ViewPreset): CameraPose {
    const tx = (v.x[0] + v.x[1]) / 2, ty = (v.y[0] + v.y[1]) / 2;
    const tilt = (v.tiltDeg * Math.PI) / 180, az = ((v.azimuthDeg ?? 0) * Math.PI) / 180;
    const dir = new THREE.Vector3(-Math.sin(tilt) * Math.cos(az), -Math.sin(tilt) * Math.sin(az), Math.cos(tilt));
    const cam = new THREE.PerspectiveCamera(FOV, this.camera.aspect, 0.02, 20);
    const corners = [v.x[0], v.x[1]].flatMap((x) => [v.y[0], v.y[1]].map((y) => toThree(x, y)));
    let lo = 100, hi = 6000;
    for (let i = 0; i < 28; i++) {
      const d = (lo + hi) / 2;
      cam.position.copy(toThree(tx + dir.x * d, ty + dir.y * d, dir.z * d));
      cam.lookAt(toThree(tx, ty));
      cam.updateMatrixWorld(true);
      const fits = corners.every((c) => { const q = c.clone().project(cam); return Math.abs(q.x) <= 0.97 && Math.abs(q.y) <= 0.97; });
      if (fits) hi = d; else lo = d;
    }
    return { position_mm: [tx + dir.x * hi, ty + dir.y * hi, dir.z * hi], target_mm: [tx, ty, 0], fov_deg: FOV };
  }

  setCamera(pose: CameraPose, animateMs = 0): void {
    if (animateMs > 0) { this.animating = { from: this.cameraPose(), to: pose, t0: performance.now(), ms: animateMs }; return; }
    this.animating = null;
    this.camera.position.copy(toThree(...pose.position_mm));
    this.controls.target.copy(toThree(...pose.target_mm));
    this.camera.fov = pose.fov_deg;
    this.camera.updateProjectionMatrix();
    this.controls.update();
    this.needsRender = true;
  }

  private stepCameraAnimation(now: number): void {
    const a = this.animating!;
    const u = Math.min(1, (now - a.t0) / a.ms), e = u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
    const mix = (p: number[], q: number[]): [number, number, number] => [p[0]! + (q[0]! - p[0]!) * e, p[1]! + (q[1]! - p[1]!) * e, p[2]! + (q[2]! - p[2]!) * e];
    const to = a.to;
    this.setCamera({ position_mm: mix(a.from.position_mm, to.position_mm), target_mm: mix(a.from.target_mm, to.target_mm), fov_deg: a.from.fov_deg + (to.fov_deg - a.from.fov_deg) * e });
    if (u < 1) this.animating = a;
  }

  // ------------------------------------------------------------ export

  /** Draws one clean frame (no handles) at the given pixel size and hands the canvas to `use`; then restores the view. */
  async withExportFrame<T>(width: number, height: number, transparent: boolean, use: (canvas: HTMLCanvasElement) => Promise<T>): Promise<T> {
    const size = this.renderer.getSize(new THREE.Vector2()), ratio = this.renderer.getPixelRatio(), aspect = this.camera.aspect, bg = this.scene.background;
    try {
      this.handles.visible = false;
      this.renderer.setPixelRatio(1);
      this.renderer.setSize(width, height, false);
      this.camera.aspect = width / height;
      this.camera.updateProjectionMatrix();
      if (transparent) { this.scene.background = null; this.renderer.setClearColor(0x000000, 0); }
      this.renderer.render(this.scene, this.camera);
      return await use(this.canvas);
    } finally {
      this.scene.background = bg;
      this.handles.visible = true;
      this.renderer.setPixelRatio(ratio);
      this.renderer.setSize(size.x, size.y, false);
      this.camera.aspect = aspect;
      this.camera.updateProjectionMatrix();
      this.needsRender = true;
    }
  }

  /** Holds the drawing buffer at a fixed size (video recording); returns the function that restores it. */
  lockSize(width: number, height: number): () => void {
    const size = this.renderer.getSize(new THREE.Vector2()), ratio = this.renderer.getPixelRatio(), aspect = this.camera.aspect;
    this.handles.visible = false;
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.needsRender = true;
    return () => {
      this.handles.visible = true;
      this.renderer.setPixelRatio(ratio);
      this.renderer.setSize(size.x, size.y, false);
      this.camera.aspect = aspect;
      this.camera.updateProjectionMatrix();
      this.resize();
    };
  }

  setBackground(color: string): void {
    this.background = color;
    this.scene.background = new THREE.Color(color);
    this.needsRender = true;
  }
}

/** Radius of the turn ring round a selected figure (mm). */
export const RING_MM = 46;
/** Where the turn knob sits: on the ring, on the stick side of the figure. */
export function knobOf(pid: string, arcMm: number, thetaDeg: number): Vec2 {
  const p = SLOTS[pid]!.at(arcMm).point, h = ((headingDeg(pid, thetaDeg) + 90) * Math.PI) / 180;
  return [p[0] + RING_MM * Math.cos(h), p[1] + RING_MM * Math.sin(h)];
}
export const midOf = (a: Arrow, i: number): Vec2 => [(a.points_mm[i]![0] + a.points_mm[i + 1]![0]) / 2, (a.points_mm[i]![1] + a.points_mm[i + 1]![1]) / 2];
export type { Marker };
