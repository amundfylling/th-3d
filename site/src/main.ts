// Combo editor (docs/combo-editor.md): application wiring. State, undo, pointer tools, inspector, dialogs, export.
import "./style.css";
import { AI_MODELS, askClaude, parseAnswer, promptForClipboard } from "./ai.ts";
import {
  type Arrow, type Combo, type FigurePose, type Marker, type Vec2, ARROW_DEFAULTS, BLADE_MID_MM, COLORS, MARKER_RADIUS_MM, PIDS, RINK, SLOTS,
  arrowCentreline, arrowDrawnLine, clampArc, clampInsideBoards, comboFromLibrary, decodeShare, emptyCombo, encodeShare, figureName, figureToWorld,
  formatGuide, headingDeg, newId, normalizeCombo, pivotOf, pointAt, polylineLength, wrapDeg,
} from "./model.ts";
import { type Selection, RING_MM, Stage, VIEWS, knobOf, midOf } from "./stage.ts";

type Tool = "select" | "arrow" | "move" | "marker";
interface LibraryMove { id: string; name: string; level: number | null; player: string | null; description: string; view: string; [k: string]: unknown }
interface Library { default_figures: Record<string, FigurePose>; moves: LibraryMove[] }

const $ = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;
const esc = (s: string): string => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
const store = {
  get(key: string): string | null { try { return localStorage.getItem(`th-combo.${key}`); } catch { return null; } },
  set(key: string, value: string | null): void { try { if (value === null) localStorage.removeItem(`th-combo.${key}`); else localStorage.setItem(`th-combo.${key}`, value); } catch { /* private window */ } },
};

const viewport = $("viewport"), stage = new Stage($<HTMLCanvasElement>("stage"));
let library: Library = { default_figures: {}, moves: [] };
let base: Combo = emptyCombo({});
let combo: Combo = base;
let sel: Selection = null;
let tool: Tool = "select";
let draft: { points: Vec2[]; cursor: Vec2 | null } | null = null;
let undoStack: string[] = [], historyAt = -1;
/** A tall phone screen shows the whole rink; a wide screen the attacking half, as the move pictures do. */
const portrait = (): boolean => viewport.clientWidth < viewport.clientHeight * 0.8;
let viewId: string | null = "half";
let snapPuck = store.get("snap") !== "0";
let playing: { stop: () => void } | null = null;

// ------------------------------------------------------------------ state

function redraw(): void {
  stage.applyFigures(combo);
  stage.drawOverlay(combo);
  drawHandles();
}
function drawHandles(): void {
  const dashed = tool === "move";
  stage.drawHandles(combo, sel, draft ? { ...draft, color: dashed ? COLORS.move : COLORS.pass, dashed } : null);
}
function commit(): void {
  const s = JSON.stringify(combo);
  if (undoStack[historyAt] !== s) {
    undoStack = undoStack.slice(0, historyAt + 1);
    undoStack.push(s);
    if (undoStack.length > 200) undoStack.shift();
    historyAt = undoStack.length - 1;
  }
  store.set("current", s);
  syncChrome();
}
function replaceCombo(next: Combo, opts: { keepSelection?: boolean } = {}): void {
  combo = next;
  if (!opts.keepSelection) sel = null;
  draft = null;
  commit();
  redraw();
  renderInspector();
}
function travel(delta: number): void {
  const at = historyAt + delta;
  if (at < 0 || at >= undoStack.length) return;
  historyAt = at;
  combo = JSON.parse(undoStack[at]!) as Combo;
  store.set("current", undoStack[at]!);
  if (sel && !selectionExists(sel)) sel = null;
  draft = null;
  redraw();
  renderInspector();
  syncChrome();
}
function selectionExists(s: NonNullable<Selection>): boolean {
  if (s.kind === "arrow") return combo.arrows.some((a) => a.id === s.id);
  if (s.kind === "marker") return combo.markers.some((m) => m.id === s.id);
  return true;
}
function select(next: Selection): void {
  const same = JSON.stringify(next) === JSON.stringify(sel);
  sel = next;
  drawHandles();
  if (!same) renderInspector();
  syncChrome();
}
function syncChrome(): void {
  $<HTMLButtonElement>("btn-undo").disabled = historyAt <= 0;
  $<HTMLButtonElement>("btn-redo").disabled = historyAt >= undoStack.length - 1;
  $<HTMLButtonElement>("btn-delete").disabled = !(sel && (sel.kind === "arrow" || sel.kind === "marker"));
  const name = $<HTMLInputElement>("name");
  if (document.activeElement !== name) name.value = combo.name;
  document.title = `${combo.name} · Combo Editor`;
  for (const b of document.querySelectorAll<HTMLButtonElement>(".tools [data-tool]")) b.classList.toggle("on", b.dataset.tool === tool);
  for (const b of document.querySelectorAll<HTMLButtonElement>("#views [data-view]")) b.classList.toggle("on", b.dataset.view === viewId);
  $("draftbar").hidden = !draft;
  document.body.classList.toggle("drafting", !!draft);
  if (draft) {
    $("draft-text").textContent = draft.points.length === 0 ? "Tap where the arrow starts" : draft.points.length === 1 ? "Tap where it goes" : "Tap more points, or finish";
    $<HTMLButtonElement>("draft-done").disabled = draft.points.length < 2;
    $<HTMLButtonElement>("draft-undo").disabled = draft.points.length === 0;
  }
  $("hint").textContent = playing ? "" : HINTS[tool];
}
const HINTS: Record<Tool, string> = {
  select: "Drag a player to slide it along its slot. Drag its stick to turn it. Drag empty ice to look around.",
  arrow: "Pass or shot: tap the ice for each point of the arrow, then Done.",
  move: "Player run (dashed): tap the ice for each point of the arrow, then Done.",
  marker: "Tap the ice to put the next number.",
};
function toast(text: string, error = false): void {
  const t = $("toast");
  t.textContent = text;
  t.classList.toggle("error", error);
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => { t.hidden = true; }, error ? 5200 : 2400);
}
let toastTimer = 0;
function setTool(next: Tool): void {
  if (playing) return;
  tool = next;
  draft = next === "arrow" || next === "move" ? { points: [], cursor: null } : null;
  if (next !== "select") sel = null;
  drawHandles();
  renderInspector();
  syncChrome();
  viewport.style.cursor = next === "select" ? "" : "crosshair";
}

// ------------------------------------------------------------------ geometry helpers

/** Puck positions that sit against a skater's blade (front and back face), for snapping. */
function bladeSpots(): Vec2[] {
  const out: Vec2[] = [], off = RINK.puck_radius_mm + 1.6;
  for (const pid of PIDS) {
    const pose = combo.figures[pid]!;
    if (pid.endsWith("-G") || pose.hidden) continue;
    out.push(figureToWorld(pid, pose, [BLADE_MID_MM[0] + off, BLADE_MID_MM[1]]), figureToWorld(pid, pose, [BLADE_MID_MM[0] - off, BLADE_MID_MM[1]]));
  }
  return out;
}
/** Snaps a drawn point to the puck, a marker or an arrow end when it is close. */
function snapPoint(p: Vec2, skipArrow?: string): Vec2 {
  const targets: Vec2[] = [[combo.puck.x_mm, combo.puck.y_mm], ...combo.markers.map((m): Vec2 => [m.x_mm, m.y_mm])];
  for (const a of combo.arrows) if (a.id !== skipArrow) targets.push(a.points_mm[0]!, a.points_mm[a.points_mm.length - 1]!);
  let best: Vec2 = p, bd = 7;
  for (const t of targets) { const d = Math.hypot(t[0] - p[0], t[1] - p[1]); if (d < bd) { bd = d; best = [t[0], t[1]]; } }
  return best;
}
const r1 = (v: number): number => Math.round(v * 10) / 10;
function distToPolyline(p: Vec2, pts: Vec2[]): number {
  let best = Infinity;
  for (let i = 0; i + 1 < pts.length; i++) {
    const a = pts[i]!, b = pts[i + 1]!, dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy;
    const t = l2 > 0 ? Math.min(1, Math.max(0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2)) : 0;
    best = Math.min(best, Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy));
  }
  return best;
}

// ------------------------------------------------------------------ pointer tools

type Drag =
  | { kind: "figure"; pid: string; zMm: number; offset: Vec2 }
  | { kind: "turn"; pid: string; zMm: number; lastAngle: number; theta: number }
  | { kind: "puck"; zMm: number; offset: Vec2 }
  | { kind: "marker"; id: string; offset: Vec2 }
  | { kind: "arrowPoint"; id: string; index: number }
  | { kind: "arrow"; id: string; start: Vec2; original: Vec2[] };
let drag: (Drag & { pointerId: number; moved: boolean }) | null = null;
let press: { x: number; y: number; id: number; t: number } | null = null;
const activePointers = new Set<number>();

function hit(x: number, y: number, touch: boolean): Drag | null {
  const tol = touch ? 24 : 13;
  const near = (p: Vec2, z = 0): number => { const s = stage.screenOf(p, z); return Math.hypot(s[0] - x, s[1] - y); };
  const ice = stage.planePoint(x, y);
  if (sel?.kind === "arrow") {
    const selId = sel.id, a = combo.arrows.find((q) => q.id === selId);
    if (a) {
      for (let i = 0; i < a.points_mm.length; i++) if (near(a.points_mm[i]!) < tol) return { kind: "arrowPoint", id: a.id, index: i };
      for (let i = 0; i + 1 < a.points_mm.length; i++) {
        if (near(midOf(a, i)) < tol * 0.8) {
          a.points_mm.splice(i + 1, 0, midOf(a, i).map(r1) as Vec2);
          return { kind: "arrowPoint", id: a.id, index: i + 1 };
        }
      }
    }
  }
  const body = stage.pickBody(x, y, touch ? 12 : 5);
  if (sel?.kind === "figure" && !(body?.kind === "figure" && body.pid === sel.pid)) {
    const pose = combo.figures[sel.pid]!, p = pivotOf(sel.pid, pose);
    const onRing = ice && Math.abs(Math.hypot(ice[0] - p[0], ice[1] - p[1]) - RING_MM) < (touch ? 9 : 5);
    if (near(knobOf(sel.pid, pose.arc_mm, pose.theta_deg)) < tol * 1.2 || onRing) return { kind: "turn", pid: sel.pid, zMm: 0, lastAngle: Math.atan2(ice![1] - p[1], ice![0] - p[0]), theta: pose.theta_deg };
  }
  for (const m of [...combo.markers].reverse()) {
    const c = stage.screenOf([m.x_mm, m.y_mm], 1.5), edge = stage.screenOf([m.x_mm, m.y_mm + MARKER_RADIUS_MM], 1.5);
    if (Math.hypot(c[0] - x, c[1] - y) < Math.max(Math.hypot(edge[0] - c[0], edge[1] - c[1]), touch ? 16 : 0) && ice) return { kind: "marker", id: m.id, offset: [m.x_mm - ice[0], m.y_mm - ice[1]] };
  }
  if (body?.kind === "puck") {
    const q = stage.planePoint(x, y, body.zMm)!;
    return { kind: "puck", zMm: body.zMm, offset: [combo.puck.x_mm - q[0], combo.puck.y_mm - q[1]] };
  }
  if (body?.kind === "figure") {
    const pose = combo.figures[body.pid]!, p = pivotOf(body.pid, pose), q = stage.planePoint(x, y, body.zMm)!;
    // the stick (left of the body, low) turns the figure; the body slides it. The goalie only slides here.
    const onStick = !body.pid.endsWith("-G") && body.local[1] > 15 && body.zMm < 26;
    if (onStick) return { kind: "turn", pid: body.pid, zMm: body.zMm, lastAngle: Math.atan2(q[1] - p[1], q[0] - p[0]), theta: pose.theta_deg };
    return { kind: "figure", pid: body.pid, zMm: body.zMm, offset: [p[0] - q[0], p[1] - q[1]] };
  }
  if (ice) {
    for (const a of [...combo.arrows].reverse()) {
      const line = arrowCentreline(a);
      const s0 = stage.screenOf(ice), s1 = stage.screenOf([ice[0] + 1, ice[1]]), px = Math.hypot(s1[0] - s0[0], s1[1] - s0[1]) || 1;
      if (distToPolyline(ice, line) < a.width_mm / 2 + (touch ? 14 : 6) / px) return { kind: "arrow", id: a.id, start: ice, original: a.points_mm.map((p): Vec2 => [p[0], p[1]]) };
    }
  }
  return null;
}

function selectionOf(d: Drag): Selection {
  if (d.kind === "figure" || d.kind === "turn") return { kind: "figure", pid: d.pid };
  if (d.kind === "puck") return { kind: "puck" };
  if (d.kind === "marker") return { kind: "marker", id: d.id };
  return { kind: "arrow", id: d.id };
}

function applyDrag(d: Drag, x: number, y: number, shift: boolean): void {
  if (d.kind === "figure") {
    const q = stage.planePoint(x, y, d.zMm);
    if (!q) return;
    const pose = combo.figures[d.pid]!;
    pose.arc_mm = r1(clampArc(d.pid, SLOTS[d.pid]!.nearest([q[0] + d.offset[0], q[1] + d.offset[1]]).arc));
    stage.applyFigures(combo);
  } else if (d.kind === "turn") {
    const q = stage.planePoint(x, y, d.zMm);
    if (!q) return;
    const pose = combo.figures[d.pid]!, p = pivotOf(d.pid, pose);
    if (Math.hypot(q[0] - p[0], q[1] - p[1]) < 4) return;
    const a = Math.atan2(q[1] - p[1], q[0] - p[0]);
    let da = a - d.lastAngle;
    da -= 2 * Math.PI * Math.round(da / (2 * Math.PI));
    d.lastAngle = a;
    d.theta += (da * 180) / Math.PI;
    pose.theta_deg = shift ? wrapDeg(Math.round(d.theta / 5) * 5) : r1(wrapDeg(d.theta));
    stage.applyFigures(combo);
  } else if (d.kind === "puck") {
    const q = stage.planePoint(x, y, d.zMm);
    if (!q) return;
    let p = clampInsideBoards([q[0] + d.offset[0], q[1] + d.offset[1]], RINK.puck_radius_mm);
    if (snapPuck && !shift) {
      let bd = 7;
      for (const s of bladeSpots()) { const dist = Math.hypot(s[0] - p[0], s[1] - p[1]); if (dist < bd) { bd = dist; p = s; } }
    }
    combo.puck.x_mm = r1(p[0]);
    combo.puck.y_mm = r1(p[1]);
    stage.setPuck(p);
  } else {
    const q = stage.planePoint(x, y);
    if (!q) return;
    if (d.kind === "marker") {
      const m = combo.markers.find((k) => k.id === d.id)!;
      const p = shift ? [q[0] + d.offset[0], q[1] + d.offset[1]] : snapPoint([q[0] + d.offset[0], q[1] + d.offset[1]]);
      m.x_mm = r1(p[0]!);
      m.y_mm = r1(p[1]!);
    } else if (d.kind === "arrowPoint") {
      const a = combo.arrows.find((k) => k.id === d.id)!;
      const ends = d.index === 0 || d.index === a.points_mm.length - 1;
      a.points_mm[d.index] = (ends && !shift ? snapPoint(q, a.id) : q).map(r1) as Vec2;
    } else {
      const a = combo.arrows.find((k) => k.id === d.id)!;
      a.points_mm = d.original.map((p): Vec2 => [r1(p[0] + q[0] - d.start[0]), r1(p[1] + q[1] - d.start[1])]);
    }
    stage.drawOverlay(combo);
  }
  drawHandles();
  liveInspector();
}

viewport.addEventListener("pointerdown", (e) => {
  if (playing || (e.target as HTMLElement).closest(".tools, .views, #inspector, .draftbar, .toast")) return;
  activePointers.add(e.pointerId);
  if (e.button !== 0 || activePointers.size > 1) { press = null; return; }
  press = { x: e.clientX, y: e.clientY, id: e.pointerId, t: performance.now() };
  if (tool !== "select") return;
  const d = hit(e.clientX, e.clientY, e.pointerType !== "mouse");
  if (!d) return;
  // an object is grabbed: the camera must not move with it
  stage.controls.enabled = false;
  drag = { ...d, pointerId: e.pointerId, moved: false };
  select(selectionOf(d));
  viewport.setPointerCapture(e.pointerId);
  viewport.style.cursor = d.kind === "turn" ? "ew-resize" : "grabbing";
}, { capture: true });

viewport.addEventListener("pointermove", (e) => {
  if (drag && e.pointerId === drag.pointerId) {
    if (!drag.moved && press && Math.hypot(e.clientX - press.x, e.clientY - press.y) < 3) return;
    drag.moved = true;
    applyDrag(drag, e.clientX, e.clientY, e.shiftKey);
    return;
  }
  if (e.pointerType !== "mouse" || e.buttons !== 0 || playing) return;
  hover = { x: e.clientX, y: e.clientY };
});
let hover: { x: number; y: number } | null = null;
stage.onFrame(() => {
  if (!hover) return;
  const h = hover;
  hover = null;
  if ((document.elementFromPoint(h.x, h.y) as HTMLElement | null)?.id !== "stage") { return; }
  if (draft) {
    const q = stage.planePoint(h.x, h.y);
    draft.cursor = q && draft.points.length ? snapPoint(q) : null;
    drawHandles();
  } else if (tool === "select") {
    const d = hit2(h.x, h.y);
    viewport.style.cursor = !d ? "" : d === "turn" ? "ew-resize" : "grab";
  }
});
/** Hover test without side effects (the real hit test may insert an arrow point). */
function hit2(x: number, y: number): string | null {
  const before = sel?.kind === "arrow" ? combo.arrows.find((a) => a.id === (sel as { id: string }).id)?.points_mm.slice() : null;
  const d = hit(x, y, false);
  if (before && sel?.kind === "arrow") combo.arrows.find((a) => a.id === (sel as { id: string }).id)!.points_mm = before;
  return d ? d.kind : null;
}

function endPointer(e: PointerEvent): void {
  activePointers.delete(e.pointerId);
  if (drag && e.pointerId === drag.pointerId) {
    const d = drag;
    drag = null;
    stage.controls.enabled = true;
    viewport.style.cursor = "";
    if (viewport.hasPointerCapture(e.pointerId)) viewport.releasePointerCapture(e.pointerId);
    if (d.moved) commit();
    else if (d.kind === "arrowPoint") { redraw(); commit(); }
    renderInspector();
    press = null;
    return;
  }
  if (!press || press.id !== e.pointerId || e.type === "pointercancel") { press = null; return; }
  const still = Math.hypot(e.clientX - press.x, e.clientY - press.y) < (e.pointerType === "mouse" ? 4 : 9) && performance.now() - press.t < 600;
  press = null;
  if (!still) return;
  const q = stage.planePoint(e.clientX, e.clientY);
  if (tool === "select") { select(null); return; }
  if (!q) return;
  if (tool === "marker") {
    const p = snapPoint(clampInsideBoards(q, 2));
    const used = combo.markers.map((m) => Number(m.label)).filter((n) => Number.isInteger(n));
    const m: Marker = { id: newId("m"), label: String(used.length ? Math.max(...used) + 1 : 1), x_mm: r1(p[0]), y_mm: r1(p[1]), color: COLORS.navy };
    combo.markers.push(m);
    commit();
    stage.drawOverlay(combo);
    return;
  }
  if (draft) {
    const last = draft.points[draft.points.length - 1];
    if (last && draft.points.length >= 2) {
      const s = stage.screenOf(last);
      if (Math.hypot(s[0] - e.clientX, s[1] - e.clientY) < (e.pointerType === "mouse" ? 12 : 22)) { finishDraft(); return; }
    }
    draft.points.push(snapPoint(q).map(r1) as Vec2);
    draft.cursor = null;
    drawHandles();
    syncChrome();
  }
}
viewport.addEventListener("pointerup", endPointer);
viewport.addEventListener("pointercancel", endPointer);
viewport.addEventListener("contextmenu", (e) => e.preventDefault());
viewport.addEventListener("wheel", (e) => {
  // the wheel over the selected player turns it; anywhere else it zooms
  if (sel?.kind !== "figure" || playing) return;
  const body = stage.pickBody(e.clientX, e.clientY);
  if (body?.kind !== "figure" || body.pid !== sel.pid) return;
  e.preventDefault();
  e.stopPropagation();
  nudgeTheta(sel.pid, (e.deltaY > 0 ? -1 : 1) * (e.shiftKey ? 1 : 5));
}, { capture: true, passive: false });

let nudgeTimer = 0;
function nudgeTheta(pid: string, deg: number): void {
  const pose = combo.figures[pid]!;
  pose.theta_deg = r1(wrapDeg(pose.theta_deg + deg));
  stage.applyFigures(combo);
  drawHandles();
  liveInspector();
  clearTimeout(nudgeTimer);
  nudgeTimer = window.setTimeout(commit, 350);
}
function nudgeArc(pid: string, mm: number): void {
  const pose = combo.figures[pid]!;
  pose.arc_mm = r1(clampArc(pid, pose.arc_mm + mm));
  stage.applyFigures(combo);
  drawHandles();
  liveInspector();
  clearTimeout(nudgeTimer);
  nudgeTimer = window.setTimeout(commit, 350);
}

function finishDraft(): void {
  if (!draft || draft.points.length < 2) return;
  const dashed = tool === "move";
  const a: Arrow = { id: newId("a"), points_mm: draft.points, ...ARROW_DEFAULTS, style: dashed ? "dashed" : "solid", color: dashed ? COLORS.move : COLORS.pass };
  combo.arrows.push(a);
  draft = { points: [], cursor: null };
  commit();
  redraw();
}
function deleteSelection(): void {
  if (sel?.kind === "arrow") combo.arrows = combo.arrows.filter((a) => a.id !== (sel as { id: string }).id);
  else if (sel?.kind === "marker") combo.markers = combo.markers.filter((m) => m.id !== (sel as { id: string }).id);
  else return;
  sel = null;
  commit();
  redraw();
  renderInspector();
}

$("draft-done").onclick = finishDraft;
$("draft-cancel").onclick = () => setTool("select");
$("draft-undo").onclick = () => { draft?.points.pop(); drawHandles(); syncChrome(); };
for (const b of document.querySelectorAll<HTMLButtonElement>(".tools [data-tool]")) b.onclick = () => setTool(b.dataset.tool as Tool);
$("btn-delete").onclick = deleteSelection;
$("btn-undo").onclick = () => travel(-1);
$("btn-redo").onclick = () => travel(1);
$<HTMLInputElement>("name").oninput = (e) => { combo.name = (e.target as HTMLInputElement).value; };
$<HTMLInputElement>("name").onchange = () => { combo.name = combo.name.trim() || "Untitled"; commit(); };

window.addEventListener("keydown", (e) => {
  const el = e.target as HTMLElement;
  if (el.matches("input, textarea, select") || document.querySelector("dialog[open]")) return;
  const mod = e.ctrlKey || e.metaKey, k = e.key.toLowerCase();
  if (mod && k === "z") { e.preventDefault(); travel(e.shiftKey ? 1 : -1); return; }
  if (mod && k === "y") { e.preventDefault(); travel(1); return; }
  if (mod || e.altKey) return;
  if (k === " ") { e.preventDefault(); togglePlay(); return; }
  if (playing) return;
  if (k === "v" || (k === "escape" && tool !== "select")) setTool("select");
  else if (k === "escape") select(null);
  else if (k === "a") setTool("arrow");
  else if (k === "d") setTool("move");
  else if (k === "n") setTool("marker");
  else if (k === "enter") finishDraft();
  else if (k === "backspace" && draft) { draft.points.pop(); drawHandles(); syncChrome(); }
  else if (k === "delete" || k === "backspace") deleteSelection();
  else if (sel?.kind === "figure" && (k === "arrowleft" || k === "arrowright")) { e.preventDefault(); nudgeTheta(sel.pid, (k === "arrowleft" ? 1 : -1) * (e.shiftKey ? 1 : 5)); }
  else if (sel?.kind === "figure" && (k === "arrowup" || k === "arrowdown")) { e.preventDefault(); nudgeArc(sel.pid, (k === "arrowup" ? 1 : -1) * (e.shiftKey ? 1 : 5)); }
});

// ------------------------------------------------------------------ inspector

const inspector = $("inspector");
const SWATCHES: string[] = [COLORS.pass, COLORS.red, COLORS.blue, COLORS.yellow, COLORS.white, COLORS.move, COLORS.navy];
function swatches(current: string, list: string[] = SWATCHES): string {
  return `<div class="swatches">${list.map((c) => `<button data-color="${c}" class="${c.toLowerCase() === current.toLowerCase() ? "on" : ""}" style="background:${c}" aria-label="Colour ${c}"></button>`).join("")}</div>`;
}
function renderInspector(): void {
  inspector.classList.toggle("idle", !sel);
  if (sel?.kind === "figure") {
    const pid = sel.pid, pose = combo.figures[pid]!, len = SLOTS[pid]!.length;
    inspector.innerHTML = `<h3>${esc(figureName(pid))}</h3><p class="kicker">${pid} · slides along its slot, turns about its peg</p>
      <label>Position along the slot <span class="val" id="i-arc-v"></span></label><input id="i-arc" type="range" min="0.5" max="${(len - 0.5).toFixed(1)}" step="0.5" value="${pose.arc_mm}">
      <label>Turn <span class="val" id="i-theta-v"></span></label><input id="i-theta" type="range" min="-180" max="180" step="1" value="${pose.theta_deg}">
      <div class="row"><button id="i-face">Face the goal</button><button id="i-flip">Turn 180°</button><button id="i-hide">${pose.hidden ? "Show" : "Hide"}</button></div>`;
    const arc = $<HTMLInputElement>("i-arc"), theta = $<HTMLInputElement>("i-theta");
    arc.oninput = () => { pose.arc_mm = Number(arc.value); stage.applyFigures(combo); drawHandles(); liveInspector(); };
    theta.oninput = () => { pose.theta_deg = Number(theta.value); stage.applyFigures(combo); drawHandles(); liveInspector(); };
    arc.onchange = theta.onchange = commit;
    $("i-face").onclick = () => { pose.theta_deg = 0; commit(); redraw(); renderInspector(); };
    $("i-flip").onclick = () => { pose.theta_deg = r1(wrapDeg(pose.theta_deg + 180)); commit(); redraw(); renderInspector(); };
    $("i-hide").onclick = () => { if (pose.hidden) delete pose.hidden; else pose.hidden = true; commit(); redraw(); renderInspector(); };
  } else if (sel?.kind === "puck") {
    inspector.innerHTML = `<h3>Puck</h3><p class="kicker">Drag it on the ice. Near a stick it snaps to the blade.</p>
      <label class="toggle"><input id="i-snap" type="checkbox" ${snapPuck ? "checked" : ""}> Snap to sticks</label>
      <div class="row"><button id="i-centre">To the centre spot</button><button id="i-hide">${combo.puck.hidden ? "Show" : "Hide"}</button></div>`;
    $<HTMLInputElement>("i-snap").onchange = (e) => { snapPuck = (e.target as HTMLInputElement).checked; store.set("snap", snapPuck ? "1" : "0"); };
    $("i-centre").onclick = () => { combo.puck.x_mm = 0; combo.puck.y_mm = 0; commit(); redraw(); };
    $("i-hide").onclick = () => { if (combo.puck.hidden) delete combo.puck.hidden; else combo.puck.hidden = true; commit(); redraw(); renderInspector(); };
  } else if (sel?.kind === "arrow") {
    const a = combo.arrows.find((q) => q.id === (sel as { id: string }).id);
    if (!a) { sel = null; renderInspector(); return; }
    const n = combo.arrows.indexOf(a) + 1;
    inspector.innerHTML = `<h3>Arrow ${n} of ${combo.arrows.length}</h3><p class="kicker">Drag the white dots. Drag a small dot to add a bend.</p>
      <label>Kind</label><div class="seg"><button data-style="solid" class="${a.style === "solid" ? "on" : ""}">Pass / shot</button><button data-style="dashed" class="${a.style === "dashed" ? "on" : ""}">Run (dashed)</button></div>
      <label>Line</label><div class="seg"><button data-curved="0" class="${a.curved ? "" : "on"}">Straight</button><button data-curved="1" class="${a.curved ? "on" : ""}">Curved</button></div>
      <label>Colour</label>${swatches(a.color)}
      <label>Width <span class="val" id="i-width-v">${a.width_mm.toFixed(1)} mm</span></label><input id="i-width" type="range" min="2" max="9" step="0.2" value="${a.width_mm}">
      <label class="toggle"><input id="i-head" type="checkbox" ${a.head ? "checked" : ""}> Arrow head</label>
      <div class="row"><button id="i-reverse">Reverse</button><button id="i-earlier" ${n === 1 ? "disabled" : ""}>Play earlier</button><button id="i-later" ${n === combo.arrows.length ? "disabled" : ""}>Play later</button><button id="i-del">Delete</button></div>`;
    const done = (): void => { commit(); redraw(); renderInspector(); };
    for (const b of inspector.querySelectorAll<HTMLButtonElement>("[data-style]")) b.onclick = () => { a.style = b.dataset.style as Arrow["style"]; if (a.color === COLORS.pass && a.style === "dashed") a.color = COLORS.move; else if (a.color === COLORS.move && a.style === "solid") a.color = COLORS.pass; done(); };
    for (const b of inspector.querySelectorAll<HTMLButtonElement>("[data-curved]")) b.onclick = () => { a.curved = b.dataset.curved === "1"; done(); };
    for (const b of inspector.querySelectorAll<HTMLButtonElement>("[data-color]")) b.onclick = () => { a.color = b.dataset.color!; done(); };
    const w = $<HTMLInputElement>("i-width");
    w.oninput = () => { a.width_mm = Number(w.value); $("i-width-v").textContent = `${a.width_mm.toFixed(1)} mm`; stage.drawOverlay(combo); };
    w.onchange = commit;
    $<HTMLInputElement>("i-head").onchange = (e) => { a.head = (e.target as HTMLInputElement).checked; done(); };
    $("i-reverse").onclick = () => { a.points_mm.reverse(); done(); };
    const shift = (by: number): void => { const i = combo.arrows.indexOf(a); combo.arrows.splice(i, 1); combo.arrows.splice(i + by, 0, a); done(); };
    $("i-earlier").onclick = () => shift(-1);
    $("i-later").onclick = () => shift(1);
    $("i-del").onclick = deleteSelection;
  } else if (sel?.kind === "marker") {
    const m = combo.markers.find((q) => q.id === (sel as { id: string }).id);
    if (!m) { sel = null; renderInspector(); return; }
    inspector.innerHTML = `<h3>Number</h3><p class="kicker">Drag it on the ice.</p>
      <label>Text (up to 3 characters)</label><input id="i-label" type="text" maxlength="3" value="${esc(m.label)}">
      <label>Colour</label>${swatches(m.color, [COLORS.navy, COLORS.red, COLORS.blue, "#111827", "#0f7a2a"])}
      <div class="row"><button id="i-del">Delete</button></div>`;
    const l = $<HTMLInputElement>("i-label");
    l.oninput = () => { m.label = l.value || "?"; stage.drawOverlay(combo); };
    l.onchange = commit;
    for (const b of inspector.querySelectorAll<HTMLButtonElement>("[data-color]")) b.onclick = () => { m.color = b.dataset.color!; commit(); redraw(); renderInspector(); };
    $("i-del").onclick = deleteSelection;
  } else {
    inspector.innerHTML = `<button class="collapse" id="i-collapse">Table ▾</button><div class="body"><h3>Table</h3><p class="kicker">Tap a player on the table, or pick one here.</p>
      <div class="figgrid">${PIDS.map((pid) => `<button data-pid="${pid}" class="${pid.startsWith("W") ? "w" : "e"} ${combo.figures[pid]!.hidden ? "off" : ""}" title="${esc(figureName(pid))}">${pid.slice(2)}</button>`).join("")}</div>
      <label>Notes</label><textarea id="i-desc" maxlength="600" placeholder="What happens in this combination?">${esc(combo.description)}</textarea>
      <label class="toggle"><input id="i-ontop" type="checkbox" ${stage.arrowsOnTop ? "checked" : ""}> Arrows in front of the players</label>
      <label class="toggle"><input id="i-snap" type="checkbox" ${snapPuck ? "checked" : ""}> Puck snaps to sticks</label>
      <label>Background</label>${swatches(stage.background, ["#0e2a57", "#071632", "#1b212b", "#2f6f4f", "#ffffff"])}
      <div class="row"><button id="i-reset">Reset players</button><button id="i-clear">Remove arrows</button></div></div>`;
    $("i-collapse").onclick = () => inspector.classList.toggle("open");
    for (const b of inspector.querySelectorAll<HTMLButtonElement>("[data-pid]")) b.onclick = () => { setTool("select"); select({ kind: "figure", pid: b.dataset.pid! }); };
    const d = $<HTMLTextAreaElement>("i-desc");
    d.oninput = () => { combo.description = d.value; };
    d.onchange = commit;
    $<HTMLInputElement>("i-ontop").onchange = (e) => { stage.arrowsOnTop = (e.target as HTMLInputElement).checked; store.set("ontop", stage.arrowsOnTop ? "1" : "0"); stage.drawOverlay(combo); };
    $<HTMLInputElement>("i-snap").onchange = (e) => { snapPuck = (e.target as HTMLInputElement).checked; store.set("snap", snapPuck ? "1" : "0"); };
    for (const b of inspector.querySelectorAll<HTMLButtonElement>("[data-color]")) b.onclick = () => { stage.setBackground(b.dataset.color!); store.set("bg", b.dataset.color!); renderInspector(); };
    $("i-reset").onclick = () => { combo.figures = structuredClone(base.figures); commit(); redraw(); toast("Players back to the start formation"); };
    $("i-clear").onclick = () => { combo.arrows = []; combo.markers = []; commit(); redraw(); toast("Arrows and numbers removed"); };
  }
  liveInspector();
}
/** Updates the numbers in the open inspector while something is dragged (no rebuild, so sliders keep the pointer). */
function liveInspector(): void {
  if (sel?.kind !== "figure") return;
  const pose = combo.figures[sel.pid]!, arc = document.getElementById("i-arc") as HTMLInputElement | null, theta = document.getElementById("i-theta") as HTMLInputElement | null;
  if (!arc || !theta) return;
  if (document.activeElement !== arc) arc.value = String(pose.arc_mm);
  if (document.activeElement !== theta) theta.value = String(pose.theta_deg);
  $("i-arc-v").textContent = `${pose.arc_mm.toFixed(0)} mm`;
  $("i-theta-v").textContent = `${pose.theta_deg.toFixed(0)}° (heading ${wrapDeg(headingDeg(sel.pid, pose.theta_deg)).toFixed(0)}°)`;
}

// ------------------------------------------------------------------ views and play-back

function buildViews(): void {
  $("views").innerHTML = `<button class="play" id="btn-play" title="Play the arrows in order (Space)"><svg viewBox="0 0 24 24"><path d="M7 4l13 8-13 8z"/></svg><span>Play</span></button><span class="sep"></span>` +
    VIEWS.map((v) => `<button data-view="${v.id}">${v.label}</button>`).join("");
  for (const b of document.querySelectorAll<HTMLButtonElement>("#views [data-view]")) b.onclick = () => setView(b.dataset.view!, 550);
  $("btn-play").onclick = togglePlay;
}
function setView(id: string, ms: number): void {
  const v = VIEWS.find((q) => q.id === id) ?? VIEWS[0]!;
  viewId = v.id;
  stage.setCamera(stage.presetPose(v), ms);
  delete combo.camera;
  syncChrome();
}
stage.onUserCamera = () => { viewId = null; combo.camera = stage.cameraPose(); store.set("current", JSON.stringify(combo)); syncChrome(); };

interface Step { arrow: Arrow; line: Vec2[]; length: number; t0: number; t1: number }
/** The play-back plan: each arrow is drawn in order; the puck rides the solid ones. */
function timeline(): { steps: Step[]; total: number } {
  const steps: Step[] = [];
  let t = 0.7;
  for (const arrow of combo.arrows) {
    const line = arrowDrawnLine(arrow, combo.markers), length = polylineLength(line);
    if (length < 1) continue;
    const dur = arrow.style === "dashed" ? Math.min(0.9, Math.max(0.35, length / 500)) : Math.min(1.5, Math.max(0.4, length / 520));
    steps.push({ arrow, line, length, t0: t, t1: t + dur });
    t += dur + 0.28;
  }
  return { steps, total: t + 1.1 };
}
function drawPlayFrame(tl: { steps: Step[] }, t: number): void {
  const arrows = new Map<string, number>(), markers = new Set<string>();
  let puck: Vec2 = [combo.puck.x_mm, combo.puck.y_mm];
  const first = tl.steps.find((s) => s.arrow.style === "solid");
  if (first) puck = arrowCentreline(first.arrow)[0]!;
  const reached: Vec2[] = [puck];
  for (const s of tl.steps) {
    const u = Math.min(1, Math.max(0, (t - s.t0) / (s.t1 - s.t0))), e = u * u * (3 - 2 * u);
    arrows.set(s.arrow.id, e * s.length);
    if (u <= 0) continue;
    const centre = arrowCentreline(s.arrow);
    reached.push(centre[0]!);
    if (u >= 1) reached.push(centre[centre.length - 1]!);
    if (s.arrow.style === "solid") puck = pointAt(centre, e * polylineLength(centre)).point;
  }
  const ends = tl.steps.flatMap((s) => { const c = arrowCentreline(s.arrow); return [c[0]!, c[c.length - 1]!]; });
  for (const m of combo.markers) {
    const atEnd = ends.some((p) => Math.hypot(p[0] - m.x_mm, p[1] - m.y_mm) < 8);
    if (!atEnd || reached.some((p) => Math.hypot(p[0] - m.x_mm, p[1] - m.y_mm) < 8)) markers.add(m.id);
  }
  stage.setPuck(puck);
  stage.drawOverlay(combo, { arrows, markers });
}
function startPlay(onDone?: () => void): { stop: () => void; total: number } | null {
  const tl = timeline();
  if (!tl.steps.length) { toast("Draw an arrow first: the puck follows the arrows"); return null; }
  setTool("select");
  select(null);
  document.body.classList.add("playing");
  stage.setHandlesVisible(false);
  const t0 = performance.now();
  let ended = false;
  const off = stage.onFrame((now) => {
    const t = (now - t0) / 1000;
    drawPlayFrame(tl, t);
    if (t >= tl.total) stop();
  });
  const stop = (): void => {
    if (ended) return;
    ended = true;
    off();
    playing = null;
    document.body.classList.remove("playing");
    stage.setHandlesVisible(true);
    redraw();
    setPlayLabel(false);
    syncChrome();
    onDone?.();
  };
  playing = { stop };
  setPlayLabel(true);
  syncChrome();
  return { stop, total: tl.total };
}
function setPlayLabel(on: boolean): void {
  const b = document.getElementById("btn-play");
  if (b) b.innerHTML = on ? `<svg viewBox="0 0 24 24"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg><span>Stop</span>` : `<svg viewBox="0 0 24 24"><path d="M7 4l13 8-13 8z"/></svg><span>Play</span>`;
}
function togglePlay(): void {
  if (playing) playing.stop();
  else startPlay();
}

// ------------------------------------------------------------------ export

const fileStem = (): string => (combo.name.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "combination");
function download(blob: Blob, name: string): void {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
function exportedCombo(): Combo {
  const c = structuredClone(combo);
  c.camera = stage.cameraPose();
  return c;
}
async function renderPng(): Promise<Blob> {
  const size = $<HTMLSelectElement>("ex-size").value, bg = $<HTMLSelectElement>("ex-bg").value;
  let w: number, h: number;
  if (size === "view") {
    const r = stage.canvas.getBoundingClientRect(), k = Math.min(2, 4096 / Math.max(r.width, r.height));
    w = Math.round(r.width * k); h = Math.round(r.height * k);
  } else [w, h] = size.split("x").map(Number) as [number, number];
  const before = stage.background;
  if (bg !== "current" && bg !== "transparent") stage.setBackground(bg);
  try {
    return await stage.withExportFrame(w, h, bg === "transparent", (canvas) => new Promise<Blob>((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new Error("The picture could not be made."))), "image/png")));
  } finally {
    if (stage.background !== before) stage.setBackground(before);
  }
}
$("ex-png").onclick = async () => {
  try { download(await renderPng(), `${fileStem()}.png`); toast("Picture saved"); } catch (e) { toast((e as Error).message, true); }
};
$("ex-copy-png").onclick = async () => {
  try {
    await navigator.clipboard.write([new ClipboardItem({ "image/png": renderPng() })]);
    toast("Picture copied");
  } catch { toast("This browser cannot copy pictures. Use Download instead.", true); }
};
$("ex-json").onclick = () => { download(new Blob([JSON.stringify(exportedCombo(), null, 1) + "\n"], { type: "application/json" }), `${fileStem()}.json`); toast("JSON saved"); };
$("ex-copy-json").onclick = async () => { await copyText(JSON.stringify(exportedCombo(), null, 1)); toast("JSON copied"); };
$("ex-link").onclick = async () => {
  const url = `${location.origin}${location.pathname}#c=${await encodeShare(exportedCombo())}`;
  await copyText(url);
  toast("Share link copied");
};
async function copyText(text: string): Promise<void> {
  try { await navigator.clipboard.writeText(text); } catch {
    const t = document.createElement("textarea");
    t.value = text;
    document.body.append(t);
    t.select();
    document.execCommand("copy");
    t.remove();
  }
}
$("ex-video").onclick = () => {
  if (typeof MediaRecorder === "undefined") { toast("This browser cannot record video.", true); return; }
  const mime = ["video/mp4;codecs=avc1.640028", "video/mp4", "video/webm;codecs=vp9", "video/webm"].find((m) => MediaRecorder.isTypeSupported(m));
  if (!mime) { toast("This browser cannot record video.", true); return; }
  if (!timeline().steps.length) { toast("Draw an arrow first: the puck follows the arrows", true); return; }
  $<HTMLDialogElement>("dlg-export").close();
  const unlock = stage.lockSize(1920, 1080);
  document.body.classList.add("busy");
  viewport.dataset.busy = "Recording the video…";
  const rec = new MediaRecorder(stage.canvas.captureStream(60), { mimeType: mime, videoBitsPerSecond: 12_000_000 });
  const chunks: Blob[] = [];
  rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  rec.onstop = () => {
    unlock();
    document.body.classList.remove("busy");
    download(new Blob(chunks, { type: mime.split(";")[0]! }), `${fileStem()}.${mime.startsWith("video/mp4") ? "mp4" : "webm"}`);
    toast("Video saved");
  };
  rec.start();
  // the stream only carries frames that are drawn: keep drawing for the whole recording
  const keep = stage.onFrame(() => stage.requestRender());
  const run = startPlay(() => { keep(); setTimeout(() => rec.stop(), 150); });
  if (!run) { keep(); rec.stop(); }
};

// ------------------------------------------------------------------ open, library, AI

function openCombo(input: unknown, what: string): string[] {
  const { combo: next, notes } = normalizeCombo(input, base);
  replaceCombo(next);
  if (next.camera) { viewId = null; stage.setCamera(next.camera, 500); }
  syncChrome();
  toast(`${what}: ${next.name}`);
  return notes;
}
function showNotes(el: HTMLElement, notes: string[], error = false): void {
  el.classList.toggle("error", error);
  el.textContent = notes.join("\n");
}
async function openFile(file: File): Promise<void> {
  const notesEl = $("open-notes");
  try {
    const notes = openCombo(JSON.parse(await file.text()), "Opened");
    showNotes(notesEl, notes);
    if (!notes.length) $<HTMLDialogElement>("dlg-open").close();
  } catch (e) {
    showNotes(notesEl, [`Could not open ${file.name}: ${(e as Error).message}`], true);
    if (!$<HTMLDialogElement>("dlg-open").open) toast(`Could not open ${file.name}: ${(e as Error).message}`, true);
  }
}
$("btn-open").onclick = () => { showNotes($("open-notes"), []); $<HTMLDialogElement>("dlg-open").showModal(); };
$("open-file").onclick = () => $<HTMLInputElement>("open-input").click();
$<HTMLInputElement>("open-input").onchange = (e) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) void openFile(f); (e.target as HTMLInputElement).value = ""; };
$("open-new").onclick = () => { replaceCombo(structuredClone(base)); setView(portrait() ? "full" : "half", 500); $<HTMLDialogElement>("dlg-open").close(); toast("New, empty table"); };
$("open-apply").onclick = () => {
  try {
    const notes = openCombo(parseAnswer($<HTMLTextAreaElement>("open-text").value).json, "Opened");
    showNotes($("open-notes"), notes);
    if (!notes.length) $<HTMLDialogElement>("dlg-open").close();
  } catch (e) { showNotes($("open-notes"), [(e as Error).message], true); }
};
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => { e.preventDefault(); const f = e.dataTransfer?.files[0]; if (f) void openFile(f); });

let libPlayer = "All";
function renderLibrary(): void {
  const q = $<HTMLInputElement>("lib-search").value.trim().toLowerCase();
  const players = ["All", ...new Set(library.moves.map((m) => m.player ?? "Other"))];
  $("lib-players").innerHTML = players.map((p) => `<button data-player="${esc(p)}" class="${p === libPlayer ? "on" : ""}">${esc(p)}</button>`).join("");
  for (const b of document.querySelectorAll<HTMLButtonElement>("#lib-players button")) b.onclick = () => { libPlayer = b.dataset.player!; renderLibrary(); };
  const list = library.moves.filter((m) => (libPlayer === "All" || (m.player ?? "Other") === libPlayer) && (!q || `${m.name} ${m.description}`.toLowerCase().includes(q)))
    .sort((a, b) => (a.level ?? 99) - (b.level ?? 99) || a.name.localeCompare(b.name));
  $("lib-list").innerHTML = list.map((m) => `<button data-move="${esc(m.id)}"><b>${esc(m.name)}${m.level === null ? "" : `<i>Level ${m.level}</i>`}</b><small>${esc(m.description)}</small></button>`).join("") || `<p class="sub">No move matches.</p>`;
  for (const b of document.querySelectorAll<HTMLButtonElement>("#lib-list button")) b.onclick = () => { loadMove(b.dataset.move!); $<HTMLDialogElement>("dlg-library").close(); };
}
function loadMove(id: string): boolean {
  const m = library.moves.find((q) => q.id === id);
  if (!m) return false;
  replaceCombo(comboFromLibrary(m, base));
  setView(m.view === "full" || portrait() ? "full" : m.view === "mid" || m.view === "deep" ? "mid" : "half", 500);
  toast(m.name);
  return true;
}
$("btn-library").onclick = () => { renderLibrary(); $<HTMLDialogElement>("dlg-library").showModal(); };
$<HTMLInputElement>("lib-search").oninput = renderLibrary;
$("btn-export").onclick = () => $<HTMLDialogElement>("dlg-export").showModal();
$("btn-help").onclick = () => { $("help-format").textContent = formatGuide(); $<HTMLDialogElement>("dlg-help").showModal(); };
for (const d of document.querySelectorAll<HTMLDialogElement>("dialog")) d.addEventListener("click", (e) => { if (e.target === d) d.close(); });

let aiAbort: AbortController | null = null;
function applyAnswer(text: string): void {
  const status = $("ai-status");
  try {
    const { json, said } = parseAnswer(text);
    const { combo: next, notes } = normalizeCombo(json, combo);
    delete next.camera;
    if (combo.camera) next.camera = combo.camera;
    replaceCombo(next);
    showNotes(status, [said || "Applied.", ...notes, "Not what you wanted? Undo brings the old table back."]);
  } catch (e) { showNotes(status, [(e as Error).message], true); }
}
$("btn-ai").onclick = () => {
  const m = $<HTMLSelectElement>("ai-model");
  if (!m.options.length) m.innerHTML = AI_MODELS.map((x) => `<option value="${x.id}">${x.label}</option>`).join("");
  m.value = store.get("model") ?? AI_MODELS[0].id;
  $<HTMLInputElement>("ai-key").value = store.get("key") ?? "";
  $<HTMLDialogElement>("dlg-ai").showModal();
};
$("ai-copy").onclick = async () => { await copyText(promptForClipboard(combo, $<HTMLTextAreaElement>("ai-request").value)); showNotes($("ai-status"), ["Prompt copied. Paste it into your AI, then paste its answer in the box."]); };
$("ai-apply").onclick = () => applyAnswer($<HTMLTextAreaElement>("ai-answer").value);
$("ai-forget").onclick = () => { store.set("key", null); $<HTMLInputElement>("ai-key").value = ""; showNotes($("ai-status"), ["The key was removed from this browser."]); };
$("ai-stop").onclick = () => aiAbort?.abort();
$("ai-ask").onclick = async () => {
  const key = $<HTMLInputElement>("ai-key").value.trim(), request = $<HTMLTextAreaElement>("ai-request").value.trim(), status = $("ai-status");
  const model = $<HTMLSelectElement>("ai-model").value;
  if (!request) { showNotes(status, ["Write what should change first."], true); return; }
  if (!key) { showNotes(status, ["Paste your Anthropic API key first (console.anthropic.com, API keys). Or use the free way on the right."], true); return; }
  store.set("key", key);
  store.set("model", model);
  aiAbort = new AbortController();
  $<HTMLButtonElement>("ai-ask").disabled = true;
  $("ai-stop").hidden = false;
  showNotes(status, ["Claude is thinking…"]);
  try {
    const text = await askClaude({ apiKey: key, model, combo, request, signal: aiAbort.signal, onText: (t) => showNotes(status, [`Claude is writing… ${t.length} characters`]) });
    applyAnswer(text);
  } catch (e) {
    showNotes(status, [aiAbort.signal.aborted ? "Stopped." : (e as Error).message], !aiAbort.signal.aborted);
  } finally {
    $<HTMLButtonElement>("ai-ask").disabled = false;
    $("ai-stop").hidden = true;
  }
};

// ------------------------------------------------------------------ start

async function start(): Promise<void> {
  const bar = $("load-bar");
  buildViews();
  stage.arrowsOnTop = store.get("ontop") !== "0";
  const bg = store.get("bg");
  if (bg && /^#[0-9a-f]{6}$/i.test(bg)) stage.setBackground(bg);
  const [lib] = await Promise.all([
    fetch("./library.json").then((r) => { if (!r.ok) throw new Error(`library.json: ${r.status}`); return r.json() as Promise<Library>; }),
    stage.load("./table.glb", (f) => { bar.style.width = `${Math.round(4 + f * 92)}%`; }),
  ]);
  library = lib;
  base = emptyCombo(library.default_figures);
  base.puck = { x_mm: 0, y_mm: 0 };
  combo = structuredClone(base);
  let initialNote = "";
  const hash = new URLSearchParams(location.hash.slice(1));
  const saved = store.get("current");
  try {
    if (hash.get("c")) { combo = normalizeCombo(await decodeShare(hash.get("c")!), base).combo; window.history.replaceState(null, "", location.pathname + location.search); }
    else if (hash.get("move") && library.moves.some((m) => m.id === hash.get("move"))) combo = comboFromLibrary(library.moves.find((m) => m.id === hash.get("move"))!, base);
    else if (saved) combo = normalizeCombo(JSON.parse(saved), base).combo;
    else combo = comboFromLibrary(library.moves.find((m) => m.id === "agdur") ?? {}, base);
  } catch (e) {
    initialNote = `That link or saved table could not be read (${(e as Error).message}). Showing an empty table.`;
    combo = structuredClone(base);
  }
  undoStack = [];
  historyAt = -1;
  commit();
  if (combo.camera) { viewId = null; stage.setCamera(combo.camera); } else setView(portrait() ? "full" : "half", 0);
  redraw();
  renderInspector();
  syncChrome();
  bar.style.width = "100%";
  $("loading").classList.add("done");
  if (initialNote) toast(initialNote, true);
}
// A small handle for scripts, browser tests and AI agents that drive the page.
Object.assign(window, { comboEditor: { getCombo: () => exportedCombo(), setCombo: (json: unknown) => openCombo(json, "Opened"), screenOf: (p: Vec2, z = 0) => stage.screenOf(p, z), figurePoint: (pid: string, local: Vec2) => figureToWorld(pid, combo.figures[pid]!, local), formatGuide } });

start().catch((e: unknown) => {
  console.error(e);
  $("load-text").textContent = `Could not load the table: ${(e as Error).message}. Reload the page to try again.`;
});
