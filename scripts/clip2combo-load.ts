// Opens th-combo/1 files with the combo editor's own reader (site/src/model.ts, PR #23) and reports what it repaired.
//   SITE_DIR=<repo>/site node scripts/clip2combo-load.ts file.json [...]   (SITE_DIR defaults to ./site)
// Needs site/src/generated/rink.json (node site/scripts/build-assets.mjs). One JSON line per file.
import { readFileSync } from "node:fs";
import path from "node:path";
const site = path.resolve(process.env.SITE_DIR ?? "site");
const M = await import(path.join(site, "src/model.ts"));
const base = M.emptyCombo({});
const strip = (c: any) => JSON.stringify({ ...c, arrows: c.arrows.map((a: any) => ({ ...a, id: 0 })), markers: c.markers.map((m: any) => ({ ...m, id: 0 })) });
for (const f of process.argv.slice(2)) {
  const out: Record<string, unknown> = { file: path.basename(f) };
  try {
    const raw = JSON.parse(readFileSync(f, "utf8"));
    const a = M.normalizeCombo(raw, base);
    const b = M.normalizeCombo(JSON.parse(JSON.stringify(a.combo)), base);
    out.loads = true;
    out.notes = a.notes;
    out.stable = strip(a.combo) === strip(b.combo);
    out.arrows = a.combo.arrows.length;
    out.markers = a.combo.markers.length;
    // does every figure keep the pose we wrote (no clamping)?
    out.pose_changed = Object.keys(raw.figures).filter((k) => Math.abs(raw.figures[k].arc_mm - a.combo.figures[k].arc_mm) > 0.15).length;
    out.arrows_dropped = (raw.arrows ?? []).length - a.combo.arrows.length;
    out.puck_moved = Math.hypot(raw.puck.x_mm - a.combo.puck.x_mm, raw.puck.y_mm - a.combo.puck.y_mm) > 0.15;
  } catch (e) {
    out.loads = false;
    out.error = String(e);
  }
  console.log(JSON.stringify(out));
}
