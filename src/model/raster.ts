// Read-only access to a decoded reference photograph. Never writes image files.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import jpeg from "jpeg-js";

export interface Raster {
  width: number;
  height: number;
  /** RGBA, row-major. */
  data: Uint8Array;
}

/** Decodes a JPEG after checking it is the pinned reference (SHA-256). */
export function loadPinnedJpeg(path: string, sha256: string): Raster {
  const bytes = readFileSync(path);
  const actual = createHash("sha256").update(bytes).digest("hex");
  if (actual !== sha256) throw new Error(`${path}: SHA-256 ${actual} does not match pinned ${sha256}`);
  const img = jpeg.decode(bytes, { useTArray: true, maxMemoryUsageInMB: 1024, maxResolutionInMP: 100 });
  return { width: img.width, height: img.height, data: img.data };
}

export function rgbAt(r: Raster, x: number, y: number): [number, number, number] {
  const xi = Math.min(r.width - 1, Math.max(0, Math.round(x)));
  const yi = Math.min(r.height - 1, Math.max(0, Math.round(y)));
  const i = (yi * r.width + xi) * 4;
  return [r.data[i]!, r.data[i + 1]!, r.data[i + 2]!];
}

/** Max of R, G, B at an integer pixel: high for ice and coloured paint, low only for near-black. */
export function maxChannelAt(r: Raster, x: number, y: number): number {
  const i = (y * r.width + x) * 4;
  return Math.max(r.data[i]!, r.data[i + 1]!, r.data[i + 2]!);
}

/** Bilinearly interpolated max-channel value at pixel-centre coordinates (u, v) = (x + 0.5, y + 0.5). */
export function maxChannelBilinear(r: Raster, u: number, v: number): number {
  const x = u - 0.5;
  const y = v - 0.5;
  const x0 = Math.max(0, Math.min(r.width - 2, Math.floor(x)));
  const y0 = Math.max(0, Math.min(r.height - 2, Math.floor(y)));
  const fx = x - x0;
  const fy = y - y0;
  const a = maxChannelAt(r, x0, y0);
  const b = maxChannelAt(r, x0 + 1, y0);
  const c = maxChannelAt(r, x0, y0 + 1);
  const d = maxChannelAt(r, x0 + 1, y0 + 1);
  return a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy;
}

/**
 * 4-connected flood fill from `seed` over pixels whose max channel is >= `minMaxChannel`.
 * Returns a mask (1 = filled).
 */
export function floodFill(r: Raster, seed: [number, number], minMaxChannel: number): Uint8Array {
  const { width, height } = r;
  const mask = new Uint8Array(width * height);
  const queue = new Int32Array(width * height);
  const start = seed[1] * width + seed[0];
  if (maxChannelAt(r, seed[0], seed[1]) < minMaxChannel) throw new Error(`flood seed ${seed} is on a barrier pixel`);
  let head = 0;
  let tail = 0;
  queue[tail++] = start;
  mask[start] = 1;
  while (head < tail) {
    const p = queue[head++]!;
    const x = p % width;
    const y = (p - x) / width;
    const tryPush = (q: number, qx: number, qy: number): void => {
      if (mask[q] === 0 && maxChannelAt(r, qx, qy) >= minMaxChannel) {
        mask[q] = 1;
        queue[tail++] = q;
      }
    };
    if (x > 0) tryPush(p - 1, x - 1, y);
    if (x < width - 1) tryPush(p + 1, x + 1, y);
    if (y > 0) tryPush(p - width, x, y - 1);
    if (y < height - 1) tryPush(p + width, x, y + 1);
  }
  return mask;
}

/** Bilinear interpolation of any per-pixel scalar at pixel-centre coordinates (u, v). */
export function bilinear(r: Raster, u: number, v: number, f: (rr: number, g: number, b: number) => number): number {
  const x = u - 0.5;
  const y = v - 0.5;
  const x0 = Math.max(0, Math.min(r.width - 2, Math.floor(x)));
  const y0 = Math.max(0, Math.min(r.height - 2, Math.floor(y)));
  const fx = Math.min(1, Math.max(0, x - x0));
  const fy = Math.min(1, Math.max(0, y - y0));
  const at = (xx: number, yy: number): number => {
    const i = (yy * r.width + xx) * 4;
    return f(r.data[i]!, r.data[i + 1]!, r.data[i + 2]!);
  };
  return at(x0, y0) * (1 - fx) * (1 - fy) + at(x0 + 1, y0) * fx * (1 - fy) + at(x0, y0 + 1) * (1 - fx) * fy + at(x0 + 1, y0 + 1) * fx * fy;
}
