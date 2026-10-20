"""Decode the DJI Osmo Nano per-frame metadata track (codec tag djmd, dvtm_ow001.proto).

No schema is published; this is a generic protobuf walker. Field paths are reported as dotted numbers.
Usage: python3 scripts/pov/dji_meta.py <video> [--dump N] [--out frames.json]
"""
import json, struct, subprocess, sys


def varint(b, i):
    r = s = 0
    while True:
        c = b[i]; i += 1
        r |= (c & 0x7F) << s; s += 7
        if c < 0x80:
            return r, i


def walk(b, path=()):
    """Yield (path, wiretype, value). Length-delimited fields are recursed into when they parse cleanly."""
    i = 0
    out = []
    while i < len(b):
        key, i = varint(b, i)
        fn, wt = key >> 3, key & 7
        if fn == 0:
            raise ValueError
        p = path + (fn,)
        if wt == 0:
            v, i = varint(b, i); out.append((p, 0, v))
        elif wt == 1:
            out.append((p, 1, struct.unpack('<d', b[i:i + 8])[0])); i += 8
        elif wt == 5:
            out.append((p, 5, struct.unpack('<f', b[i:i + 4])[0])); i += 4
        elif wt == 2:
            n, i = varint(b, i); sub = b[i:i + n]; i += n
            if i > len(b):
                raise ValueError
            try:
                out.extend(walk(sub, p))
            except Exception:
                out.append((p, 2, sub))
        else:
            raise ValueError
    return out


def packets(video):
    """Raw metadata packets with their pts, via ffmpeg/ffprobe."""
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'd:0', '-show_entries', 'packet=pts_time,size',
                            '-of', 'csv=p=0', video], capture_output=True, text=True, check=True).stdout.split()
    meta = [(float(t), int(s)) for t, s in (l.split(',') for l in probe)]
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-map', '0:d:0', '-c', 'copy', '-f', 'data', '-'],
                         capture_output=True, check=True).stdout
    i = 0
    for t, s in meta:
        yield t, raw[i:i + s]; i += s


def quat_from(fields):
    """Field 3.2.9 (four floats 2,3,4,5 at paths ...9.1..9.4) is a unit quaternion in every packet seen."""
    q = {p[-1]: v for p, wt, v in fields if len(p) >= 2 and p[-2] == 9 and wt == 5}
    return [q.get(k, 0.0) for k in (1, 2, 3, 4)] if q else None


if __name__ == '__main__':
    video = sys.argv[1]
    if '--dump' in sys.argv:
        n = int(sys.argv[sys.argv.index('--dump') + 1])
        for k, (t, b) in enumerate(packets(video)):
            if k >= n:
                break
            print(f'--- packet {k} t={t:.4f} {len(b)} B')
            for p, wt, v in walk(b):
                print('.'.join(map(str, p)), wt, v if not isinstance(v, bytes) else v[:40])


def frames(video):
    """Per-frame records: index, pts, camera clock (us), quaternion 3.2.9 (w?,x,y,z order as stored), vector 3.2.10."""
    out = []
    for k, (t, b) in enumerate(packets(video)):
        f = walk(b)
        rec = {'i': k, 't': round(t, 5)}
        for p, wt, v in f:
            if p == (3, 1, 2):
                rec['clock_us'] = v
            if len(p) == 4 and p[:3] == (3, 2, 9) and wt == 5:
                rec.setdefault('q', [0.0] * 4)[p[3] - 1] = v
            if len(p) == 4 and p[:3] == (3, 2, 10) and wt == 5:
                rec.setdefault('v10', [0.0] * 4)[p[3] - 1] = v
            if p == (3, 2, 3, 1):
                rec['f3'] = v
            if p == (3, 2, 6, 1):
                rec['f6'] = v
        out.append(rec)
    return out
