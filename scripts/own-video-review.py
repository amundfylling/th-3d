"""Review artifacts for the own-video pipeline (docs/own-video-tracking.md, step 3).

    /root/venvs/blender/bin/python scripts/own-video-review.py

- validation/own-video-camera.jpg: four frames with every slot centreline and the inner board line projected with the
  frame's camera, plus a 51 mm figure mold standing at each slot's middle (height check);
- validation/own-video-tracks.jpg: 12 frames at random over the match (seed 7) with every tracked figure's projected
  mold outline (team W green, team E magenta) and the puck track's position (yellow ring) when seen;
- validation/own-video-tracks-clip.mp4: 20 s of play, the video with outlines beside a top-down board of the tracks;
- own-video/review.json: puck-figure consistency. In frames where the puck is seen and lies in one skater's exclusive
  reach area (game-possession.py), the distance from the puck centre to that skater's tracked mold (lowest 12 mm:
  skates and blade) against the same distance with the skater's track shifted by a random time (null). A working
  tracker puts the figure at the puck much more often than the null does.
"""
import json, sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from own_video_common import *  # noqa: E402,F403
from matplotlib.path import Path as MPath  # noqa: E402

VAL = REPO / "validation"
T = load(OUTD / "figure-tracks.json"); F0 = T["frames"][0]; FIGS = list(T["tracks"])
TR = {p: np.array(v) for p, v in T["tracks"].items()}
PK = {int(r[0]): (r[2], r[3]) for r in load(GAME / "puck-track.json")["rows"]}
G = geometry(); BOUND = np.array(G["board"]["inner_boundary"]["world"]["points_mm"], float)
MOLD = {k: mold(k, "SWE", 3) for k in ("skater", "goalie")}


def pose(pid, i):
    r = TR[pid][i - F0]; return r[0], r[1], r[4]


def figure_world(pid, u, h):
    P, L = MOLD["goalie" if pid.endswith("G") else "skater"]; return place(P, pid, u, h), L


def outline(img, i, pid, u, h, col, thick=1, scale=1):
    W, L = figure_world(pid, u, h); q = project(i, W) * scale
    m = np.zeros(img.shape[:2], np.uint8); qi = np.round(q).astype(int)
    ok = (qi[:, 0] >= 0) & (qi[:, 0] < img.shape[1]) & (qi[:, 1] >= 0) & (qi[:, 1] < img.shape[0])
    m[qi[ok, 1], qi[ok, 0]] = 1
    m = cv2.morphologyEx(cv2.dilate(m, np.ones((scale, scale), np.uint8)), cv2.MORPH_CLOSE, np.ones((2 * scale + 1,) * 2, np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE); cv2.drawContours(img, cs, -1, col, thick)


COL = {"W": (60, 220, 60), "E": (230, 60, 230)}


def overlay(img, i, scale=3, labels=True):
    big = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    for pid in FIGS:
        u, h, sc = pose(pid, i)
        outline(big, i, pid, u, h, COL[pid[0]] if sc >= 0.1 else (0, 140, 255), 1, scale)
        if labels:
            p = project(i, np.r_[slot_point(pid, u), 0])[0] * scale
            cv2.putText(big, pid, (int(p[0]) - 14, int(p[1]) + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1, cv2.LINE_AA)
    if i in PK:
        p = project(i, np.r_[PK[i], 0])[0] * scale; cv2.circle(big, (int(p[0]), int(p[1])), 4 * scale, (0, 230, 255), 2)
    return big


def table_box(i, scale, pad=40):
    q = project(i, np.c_[BOUND, np.zeros(len(BOUND))]) * scale
    x0, y0 = np.maximum(q.min(0) - pad, 0).astype(int); x1, y1 = (q.max(0) + pad).astype(int)
    return x0, y0, min(x1, 640 * scale), min(y1, 360 * scale)


def fit(im, w, h):
    s = min(w / im.shape[1], h / im.shape[0]); im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    c = np.full((h, w, 3), 255, np.uint8); c[:im.shape[0], :im.shape[1]] = im; return c


def topdown(i, s=0.9):
    """Top-down board of the tracks at frame i: 900 x 500 px, s px per mm."""
    W, H = 900, 500; img = np.full((H, W, 3), 245, np.uint8)
    tp = lambda P: np.c_[W / 2 + P[:, 0] * s, H / 2 - P[:, 1] * s].astype(np.int32)
    cv2.polylines(img, [tp(BOUND)], True, (90, 90, 90), 2)
    for pid, P in slots().items(): cv2.polylines(img, [tp(P)], False, (200, 200, 200), 3)
    for pid in FIGS:
        u, h, sc = pose(pid, i); Wp, L = figure_world(pid, u, h)
        col = COL[pid[0]] if sc >= 0.1 else (0, 140, 255)
        for part, c in ((0, (120, 60, 20)), (2, col), (3, (70, 70, 70))):
            q = tp(Wp[L == part][:, :2])
            if len(q) > 2: cv2.fillPoly(img, [cv2.convexHull(q)], c) if part != 3 else cv2.polylines(img, [q[np.argsort(q[:, 0])]], False, c, 1)
        p = tp(slot_point(pid, u)[None])[0]; cv2.circle(img, tuple(p), 2, (0, 0, 0), -1)
        cv2.putText(img, pid, (p[0] - 14, p[1] + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (40, 40, 40), 1, cv2.LINE_AA)
    if i in PK:
        p = tp(np.array([PK[i]]))[0]; cv2.circle(img, tuple(p), int(12.7 * s), (20, 20, 20), -1)
    cv2.putText(img, f"match {i / FPS - MATCH_START_S:6.2f} s   frame {i}", (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    return img


def consistency():
    poss = load(GAME / "possession.json")
    rng = np.random.default_rng(3); res = {}
    low = {k: (P[:, 2] < 12) for k, (P, L) in MOLD.items()}
    for pid in SKATERS:
        polys = [MPath(np.array(a)) for a in poss["exclusive_areas_mm"][pid]]
        fr = [i for i, xy in PK.items() if F0 <= i < F0 + len(TR[pid]) and any(pp.contains_point(xy) for pp in polys)]
        if not fr: continue
        d_t, d_n = [], []
        for i in fr:
            xy = np.array(PK[i])
            for k, dst in ((i, d_t), (F0 + int(rng.integers(len(TR[pid]))), d_n)):
                u, h, _ = pose(pid, k); Wp, L = figure_world(pid, u, h); Wp = Wp[low["skater"]]
                dst.append(float(np.min(np.linalg.norm(Wp[:, :2] - xy, axis=1))))
        d_t, d_n = np.array(d_t), np.array(d_n)
        res[pid] = {"frames": len(fr), "median_mm_tracked": round(float(np.median(d_t)), 1), "median_mm_null": round(float(np.median(d_n)), 1),
                    "within_20mm_tracked": round(float((d_t < 20).mean()), 3), "within_20mm_null": round(float((d_n < 20).mean()), 3)}
        print(pid, res[pid], flush=True)
    allt = sum(r["frames"] for r in res.values())
    res["all"] = {"frames": allt, **{k: round(sum(r[k] * r["frames"] for r in res.values() if "frames" in r) / allt, 3)
                                     for k in ("within_20mm_tracked", "within_20mm_null")}}
    return res


if __name__ == "__main__":
    want_cam = [int(round((t + MATCH_START_S) * FPS)) for t in (10, 100, 200, 290)]
    rng = np.random.default_rng(7); want_tr = sorted(rng.choice(np.arange(F0, F0 + len(TR["W-C"])), 12, replace=False).tolist())
    clip0 = int(round((float(sys.argv[1]) if len(sys.argv) > 1 else 60.0) + MATCH_START_S) * FPS); clip = range(clip0, clip0 + 500)
    cam_tiles, tr_tiles = [], []
    vw = None
    for i, img in frames():
        if i in want_cam:
            big = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            for pid, P in slots().items():
                cv2.polylines(big, [(project(i, np.c_[P, np.zeros(len(P))]) * 2).astype(np.int32)], False, (0, 0, 255), 1, cv2.LINE_AA)
            cv2.polylines(big, [(project(i, np.c_[BOUND, np.zeros(len(BOUND))]) * 2).astype(np.int32)], True, (255, 160, 0), 1, cv2.LINE_AA)
            for pid in FIGS: outline(big, i, pid, 0.5, HOME[pid[0]], (0, 255, 0), 1, 2)
            cv2.putText(big, f"frame {i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2); cam_tiles.append(big)
        if i in want_tr:
            big = overlay(img, i); x0, y0, x1, y1 = table_box(i, 3)
            t = big[y0:y1, x0:x1].copy(); cv2.putText(t, f"match {i / FPS - MATCH_START_S:.2f} s", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            tr_tiles.append(fit(t, 1100, 520))
        if i in clip:
            big = overlay(img, i, 2, labels=False); x0, y0, x1, y1 = table_box(i, 2, 30)
            fr = np.hstack([fit(big[y0:y1, x0:x1], 900, 500), topdown(i)])
            if vw is None:
                vw = cv2.VideoWriter(str(REPO / "out/own-video/clip.avi"), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (fr.shape[1], fr.shape[0]))
            vw.write(fr)
        if i > max(max(want_cam), max(want_tr), clip[-1]): break
    vw.release()
    cv2.imwrite(str(VAL / "own-video-camera.jpg"), np.vstack([np.hstack(cam_tiles[:2]), np.hstack(cam_tiles[2:])]), [cv2.IMWRITE_JPEG_QUALITY, 85])
    rows = [np.hstack(tr_tiles[k:k + 2]) for k in range(0, 12, 2)]
    cv2.imwrite(str(VAL / "own-video-tracks.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 82])
    import subprocess
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(REPO / "out/own-video/clip.avi"), "-c:v", "libx264", "-crf", "26", "-pix_fmt", "yuv420p",
                    str(VAL / "own-video-tracks-clip.mp4")], check=True)
    save(OUTD / "review.json", {"description": "Puck-figure consistency of the own-video figure tracks (scripts/own-video-review.py). "
                                "Distance from the seen puck to the tracked mold's lowest 12 mm of the skater whose exclusive area holds the "
                                "puck, against a time-shuffled null.", "sheet_frames": want_tr, "clip_start_frame": clip0,
                                "consistency": consistency()})
