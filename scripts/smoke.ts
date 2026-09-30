// Smoke test for the data-to-artifact route: JSON fixture in, static SVG out.
// Checks the toolchain only; the points are not hockey geometry.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

interface Point {
  id: string;
  x: number;
  y: number;
}

interface SmokeFixture {
  description: string;
  units: string;
  points: Point[];
}

const FIXTURE = "data/fixtures/smoke.json";
const OUTPUT = "validation/03-smoke.svg";

function readFixture(path: string): SmokeFixture {
  const raw: unknown = JSON.parse(readFileSync(path, "utf8"));
  if (typeof raw !== "object" || raw === null || !Array.isArray((raw as SmokeFixture).points)) {
    throw new Error(`${path}: expected an object with a points array`);
  }
  const fixture = raw as SmokeFixture;
  for (const p of fixture.points) {
    if (typeof p.id !== "string" || !Number.isFinite(p.x) || !Number.isFinite(p.y)) {
      throw new Error(`${path}: invalid point ${JSON.stringify(p)}`);
    }
  }
  return fixture;
}

const escapeXml = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// World convention used throughout the project: +x right, +y up. SVG is y-down, so y is negated.
function renderSvg(fixture: SmokeFixture): string {
  const half = 100;
  const size = 2 * half;
  const sx = (x: number): number => x;
  const sy = (y: number): number => -y;
  const parts: string[] = [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${-half} ${-half} ${size} ${size}" width="480" height="480" font-family="sans-serif">`,
    `<title>Smoke diagnostic: ${escapeXml(FIXTURE)}</title>`,
    `<rect x="${-half}" y="${-half}" width="${size}" height="${size}" fill="#ffffff"/>`,
    `<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#333"/></marker></defs>`,
    `<line x1="0" y1="0" x2="${half - 10}" y2="0" stroke="#333" stroke-width="1" marker-end="url(#arrow)"/>`,
    `<line x1="0" y1="0" x2="0" y2="${-(half - 10)}" stroke="#333" stroke-width="1" marker-end="url(#arrow)"/>`,
    `<text x="${half - 14}" y="10" font-size="8" fill="#333">+x</text>`,
    `<text x="4" y="${-(half - 14)}" font-size="8" fill="#333">+y</text>`,
    `<circle cx="0" cy="0" r="2.5" fill="#c00"/>`,
    `<text x="4" y="10" font-size="7" fill="#c00">origin (0, 0)</text>`,
  ];
  for (const p of fixture.points) {
    parts.push(
      `<circle cx="${sx(p.x)}" cy="${sy(p.y)}" r="2" fill="#0057b8"/>`,
      `<text x="${sx(p.x) + 3}" y="${sy(p.y) - 3}" font-size="6" fill="#0057b8">${escapeXml(p.id)} (${p.x}, ${p.y})</text>`,
    );
  }
  parts.push(
    `<text x="${-half + 4}" y="${half - 4}" font-size="5" fill="#666">${escapeXml(fixture.units)} units; +y up (SVG y negated)</text>`,
    `</svg>`,
  );
  return parts.join("\n") + "\n";
}

const fixture = readFixture(FIXTURE);
mkdirSync(dirname(OUTPUT), { recursive: true });
writeFileSync(OUTPUT, renderSvg(fixture));
console.log(`smoke: ${fixture.points.length} points from ${FIXTURE} -> ${OUTPUT}`);
