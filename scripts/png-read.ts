// Minimal PNG reader (8-bit RGB/RGBA, non-interlaced) for review scripts; no dependencies.
import { readFileSync } from "node:fs";
import { inflateSync } from "node:zlib";

export const PNG = {
  read(path: string): { width: number; height: number; data: Uint8Array } {
    const b = readFileSync(path);
    let p = 8, width = 0, height = 0, ctype = 0;
    const idat: Buffer[] = [];
    while (p < b.length) {
      const len = b.readUInt32BE(p), type = b.toString("ascii", p + 4, p + 8), d = b.subarray(p + 8, p + 8 + len);
      if (type === "IHDR") {
        width = d.readUInt32BE(0); height = d.readUInt32BE(4);
        if (d[8] !== 8 || d[12] !== 0) throw new Error("only 8-bit non-interlaced PNG");
        ctype = d[9]!;
      } else if (type === "IDAT") idat.push(d);
      p += 12 + len;
    }
    const ch = ctype === 6 ? 4 : ctype === 2 ? 3 : 0;
    if (!ch) throw new Error(`unsupported colour type ${ctype}`);
    const raw = inflateSync(Buffer.concat(idat));
    const stride = width * ch;
    const out = new Uint8Array(width * height * 4);
    const prev = new Uint8Array(stride), cur = new Uint8Array(stride);
    for (let y = 0; y < height; y++) {
      const f = raw[y * (stride + 1)]!;
      const line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
      for (let x = 0; x < stride; x++) {
        const a = x >= ch ? cur[x - ch]! : 0, up = prev[x]!, c = x >= ch ? prev[x - ch]! : 0;
        let v = line[x]!;
        if (f === 1) v += a; else if (f === 2) v += up; else if (f === 3) v += (a + up) >> 1;
        else if (f === 4) { const pa = Math.abs(up - c), pb = Math.abs(a - c), pc = Math.abs(a + up - 2 * c); v += pa <= pb && pa <= pc ? a : pb <= pc ? up : c; }
        cur[x] = v & 255;
      }
      for (let x = 0; x < width; x++) {
        out[(y * width + x) * 4] = cur[x * ch]!; out[(y * width + x) * 4 + 1] = cur[x * ch + 1]!; out[(y * width + x) * 4 + 2] = cur[x * ch + 2]!; out[(y * width + x) * 4 + 3] = ch === 4 ? cur[x * ch + 3]! : 255;
      }
      prev.set(cur);
    }
    return { width, height, data: out };
  },
};
