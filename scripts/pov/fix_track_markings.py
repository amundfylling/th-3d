"""Step 4 fix: remove the camera track's slide along the table (docs/pov-videos.md).

    python3 scripts/pov/fix_track_markings.py <video> <track.npz> <out.npz> [frame ...]

The step-4 track fits slot centrelines and the board boundary. Most slot length runs along x, so the fit leaves the
camera free to slide along the table: rectified frames showed the red centre line anywhere between x -26 and +34 mm.
Per solved frame:
  1. the frame is rectified onto the ice plane with its current pose (rink_plate.to_plate) and the red centre line and
     the two blue lines are found as peaks of the column profile of red or blue excess (median over the rink's middle
     rows, minus a 15 mm running mean), searched within +-70 mm of where they should be (x = 0, +-BLUE_X);
  2. the pose is shifted by the median offset of the lines found (a line counts when its peak excess is >= 4);
  3. the pose is refitted on slots + board (dark line pixels) plus the three marking lines (red and blue line pixels).
New columns: x_offset_mm (step 2's shift, NaN when no line was found), lines_found, red_med_px, blue_med_px, and
x_offset_after_mm (the offset measured again after step 3). With frame numbers, only those frames are run and printed.
"""
import os, sys, time
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from pov_common import K_of, ice_polygon_mask, read_frames
import camera_fit as cf
import rink_plate as rp

XS = np.arange(rp.PW) + rp.X0 + 0.5


def line_offset(img, rv, tv, K, D):
    w = rp.to_plate(img, rv, tv, K, D)[0].astype(np.float32)
    B, G, R = w[..., 0], w[..., 1], w[..., 2]
    found = []
    for ex, x0 in ((R - (G + B) / 2, 0.0), (B - (R + G) / 2, -cf.BLUE_X), (B - (R + G) / 2, cf.BLUE_X)):
        prof = np.median(ex[60:420], 0); prof = prof - np.convolve(prof, np.ones(15) / 15, "same")
        s = np.abs(XS - x0) < 70; j = int(np.argmax(np.where(s, prof, -99)))
        if prof[j] >= 4: found.append(XS[j] - x0)
    return (float(np.median(found)) if found else float("nan")), len(found)


def stream(video, n):
    import subprocess
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-map", "0:v:0", "-vsync", "0", "-pix_fmt", "bgr24",
                          "-f", "rawvideo", "-"], stdout=subprocess.PIPE, bufsize=960 * 720 * 3 * 4)
    for i in range(n):
        b = p.stdout.read(960 * 720 * 3)
        if len(b) < 960 * 720 * 3: break
        yield i, np.frombuffer(b, np.uint8).reshape(720, 960, 3)
    p.kill()


def fix(img, rv, tv, K, D, intr):
    off, nf = line_offset(img, rv, tv, K, D)
    if np.isfinite(off):
        tv = tv + off * cv2.Rodrigues(rv)[0][:, 0]
    roi = cv2.dilate(ice_polygon_mask(rv, tv, K, D).astype(np.uint8), np.ones((21, 21), np.uint8)).astype(bool)
    pairs = [(cf.MODEL, cf.Target(img, roi)), (cf.MARK_RED, cf.ColourLineTarget(img, "red", roi)),
             (cf.MARK_BLUE, cf.ColourLineTarget(img, "blue", roi))]
    (rv2, tv2), st = cf.refine_pairs(pairs, (rv, tv), intr, radii=(6, 4, 3))
    after, _ = line_offset(img, rv2, tv2, K, D)
    return rv2, tv2, off, nf, st, after


if __name__ == "__main__":
    video, track, out = sys.argv[1:4]; only = [int(a) for a in sys.argv[4:]]
    T = np.load(track); A = T["rows"].copy(); intr = T["intr"]; K, D = K_of(intr[0]), cf.dist_of(intr[1:])
    extra = np.full((len(A), 6), np.nan); t0 = time.time()
    src = read_frames(video, only).items() if only else stream(video, len(A))
    for i, img in src:
        r = A[i]
        if not r[11] > 0: continue
        rv, tv, off, nf, st, after = fix(img, r[1:4], r[4:7], K, D, intr)
        A[i, 1:4], A[i, 4:7] = rv, tv
        A[i, 7], A[i, 8], A[i, 9] = st[0]["median_px"], st[0]["p90_px"], st[0]["within2px"]
        extra[i] = [off, nf, st[1]["median_px"], st[2]["median_px"], after, st[0]["points_in_frame"]]
        if only: print(i, "offset", round(off, 1), "lines", nf, "after", round(after, 1), "slot/board med", round(st[0]["median_px"], 2),
                       "red", round(st[1]["median_px"], 2), "blue", round(st[2]["median_px"], 2), flush=True)
        elif i % 500 == 0: print(i, f"{time.time() - t0:.0f}s", flush=True)
    if not only:
        np.savez(out, rows=A, intr=intr, cols=T["cols"], markings=extra,
                 markings_cols=np.array("x_offset_mm lines_found red_med_px blue_med_px x_offset_after_mm slot_board_points".split()))
        ok = A[:, 11] > 0; e = extra[ok]
        print("solved", int(ok.sum()), "|offset| median", np.nanmedian(np.abs(e[:, 0])), "p90", np.nanpercentile(np.abs(e[:, 0]), 90),
              "after median", np.nanmedian(np.abs(e[:, 4])), "p90", np.nanpercentile(np.abs(e[:, 4]), 90),
              "no line", int(np.isnan(e[:, 0]).sum()), f"{time.time() - t0:.0f}s")
