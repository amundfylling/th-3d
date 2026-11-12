"""Step 4 outputs: the per-frame camera as JSON and an overlay sheet with the slots and the board projected.
Usage: python3 scripts/pov/camera_outputs.py <video> <track.npz> <lens.json> <outdir> [n_sheet]
"""
import json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from pov_common import K_of, read_frames, project, slots, to3, resample, board_points, W_PX, H_PX
import camera_fit as cf

video, track, lens, outdir = sys.argv[1:5]
NS = int(sys.argv[5]) if len(sys.argv) > 5 else 12
T = np.load(track); A = T["rows"]; intr = T["intr"]
K, D = K_of(intr[0]), cf.dist_of(intr[1:])
rows = []
for r in A:
    if not np.all(np.isfinite(r[1:7])):
        rows.append([int(r[0]), None]); continue
    Rm = cv2.Rodrigues(r[1:4])[0]; C = -Rm.T @ r[4:7]
    rows.append([int(r[0]), int(r[11]), [round(float(v), 6) for v in r[1:4]], [round(float(v), 2) for v in r[4:7]],
                 [round(float(v), 1) for v in C], round(float(r[7]), 3), round(float(r[9]), 3), round(float(r[13]), 3),
                 int(r[14])])
ok = A[:, 11] > 0
C_all = np.array([r[4] for r in rows if r[1] is not None and r[1]])
out = {
    "description": "POV camera per frame (track_camera.py): world mm (data/geometry.json, preview scale) -> LRF px "
                   "(960 x 720). Row: [frame, ok, rvec (Rodrigues, world->camera), tvec mm, camera centre mm, median "
                   "residual px, fraction of in-frame model points within 2 px of a line pixel, fraction of the board "
                   "boundary inside the frame, source (1 optical flow from the previous frame, 2 feature "
                   "relocalisation)]; [frame, null] = not solved.",
    "status": "PROPOSED", "video": os.path.basename(video), "fps": "30000/1001",
    "K": K.tolist(), "dist": D.tolist(), "intrinsics_source": "single-frame fit (seed); lens.json is the 24-frame fit",
    "summary": {"frames": int(len(A)), "ok": int(ok.sum()), "ok_fraction": round(float(ok.mean()), 3),
                "median_residual_px": round(float(np.median(A[ok, 7])), 3),
                "p90_residual_px": round(float(np.percentile(A[ok, 7], 90)), 3),
                "whole_board_in_frame_fraction_of_ok": round(float(np.mean(A[ok, 13] >= 0.98)), 3),
                "camera_centre_median_mm": [round(float(v), 1) for v in np.median(C_all, 0)],
                "camera_centre_p5_p95_mm": [[round(float(v), 1) for v in np.percentile(C_all, 5, 0)],
                                            [round(float(v), 1) for v in np.percentile(C_all, 95, 0)]],
                "relocalised_frames": int((A[:, 14] == 2).sum())},
    "rows": rows,
}
json.dump(out, open(os.path.join(outdir, "camera-track.json"), "w"), separators=(",", ":"))
print(json.dumps(out["summary"]))
rng = np.random.default_rng(1)
cand = np.flatnonzero(ok)
pick = sorted(rng.choice(cand, NS, replace=False))
frs = read_frames(video, A[pick, 0].astype(int))
tiles = []
for k in pick:
    r = A[k]; o = frs[int(r[0])].copy()
    for pid, P in slots().items():
        col = (0, 255, 255) if pid.endswith("-G") else (0, 255, 0)
        for p in project(to3(resample(P, 3)), r[1:4], r[4:7], K, D):
            if np.all(np.isfinite(p)) and 0 <= p[0] < W_PX and 0 <= p[1] < H_PX: cv2.circle(o, (int(p[0]), int(p[1])), 1, col, -1)
    for p in project(to3(board_points()), r[1:4], r[4:7], K, D):
        if np.all(np.isfinite(p)) and 0 <= p[0] < W_PX and 0 <= p[1] < H_PX: cv2.circle(o, (int(p[0]), int(p[1])), 1, (255, 0, 255), -1)
    cv2.putText(o, f"frame {int(r[0])}  residual {r[7]:.2f} px", (10, 30), 0, 0.9, (0, 255, 255), 2)
    tiles.append(cv2.resize(o, (640, 480)))
rows_img = [np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)]
cv2.imwrite(os.path.join(outdir, "camera-overlay-sheet.jpg"), np.vstack(rows_img), [cv2.IMWRITE_JPEG_QUALITY, 85])
