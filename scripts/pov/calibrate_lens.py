"""Step 3 of the POV plan: lens calibration of the Osmo Nano (.LRF proxy, 960 x 720) from the rink itself.

No checkerboard clip exists, so the rink is the target: the slot centrelines and the inner board boundary of
data/geometry.json (world mm, the repo's preview scale; status assumed) are fitted to the dark line pixels of N frames
at once, with one shared f, k1, k2 and a pose per frame (camera_fit.fit). Frames are chosen from a camera track
(track_camera.py) among the OK frames, spread over head orientations so that the rink falls on different parts of
the sensor. Principal point: image centre (ASSUMED; a variant with it free is reported).
Usage: python3 scripts/pov/calibrate_lens.py <video> <track.npz> <out.json> <undistorted check.jpg> [n_frames]
"""
import json, os, sys
import numpy as np
import cv2
from scipy.spatial.transform import Rotation as R

sys.path.insert(0, os.path.dirname(__file__))
from pov_common import K_of, read_frames, W_PX, H_PX, project, slots, to3, resample, board_points
import camera_fit as cf

video, track, out, check = sys.argv[1:5]
N = int(sys.argv[5]) if len(sys.argv) > 5 else 24
T = np.load(track)
A, intr0 = T["rows"], T["intr"]
ok = A[A[:, 11] > 0]
# spread: farthest-point sampling on the camera rotation
rots = R.from_rotvec(ok[:, 1:4])
pick = [int(np.argmin(ok[:, 7]))]
dmin = (rots * rots[pick[0]].inv()).magnitude()
while len(pick) < N:
    k = int(np.argmax(dmin)); pick.append(k)
    dmin = np.minimum(dmin, (rots * rots[k].inv()).magnitude())
sel = ok[pick]
ids = sel[:, 0].astype(int)
frs = read_frames(video, ids)
K0, D0 = K_of(intr0[0]), cf.dist_of(intr0[1:])
targets = []
for r in sel:
    roi = cv2.dilate(__import__("pov_common").ice_polygon_mask(r[1:4], r[4:7], K0, D0).astype(np.uint8),
                     np.ones((21, 21), np.uint8)).astype(bool)
    targets.append(cf.Target(frs[int(r[0])], roi))
poses0 = [(r[1:4], r[4:7]) for r in sel]
res = {}
for name, start in [("from_seed", intr0), ("from_pinhole", np.r_[intr0[0], 0.0, 0.0])]:
    poses, intr, st = cf.fit(targets, poses0, start, free_intr=True, radii=(6, 4, 3, 3, 3))
    res[name] = {"f_px": float(intr[0]), "k1": float(intr[1]), "k2": float(intr[2]),
                 "median_px": float(np.median([s["median_px"] for s in st])),
                 "within2px": float(np.median([s["within2px"] for s in st]))}
    print(name, res[name], flush=True)
best = min(res.values(), key=lambda v: v["median_px"])
intr = np.array([best["f_px"], best["k1"], best["k2"]])
# per-frame stats at the final intrinsics and a no-distortion comparison
_, _, st_fin = cf.fit(targets, poses0, intr, free_intr=False, radii=(4, 3, 3))
_, _, st_pin = cf.fit(targets, poses0, np.r_[intr[0], 0, 0], free_intr=False, radii=(6, 4, 3, 3))
# leave-out check: fit intrinsics on half the frames, residual on the other half
half = np.arange(len(targets)) % 2 == 0
_, intr_a, _ = cf.fit([t for t, h in zip(targets, half) if h], [p for p, h in zip(poses0, half) if h], intr,
                      free_intr=True, radii=(4, 3, 3))
_, _, st_b = cf.fit([t for t, h in zip(targets, half) if not h], [p for p, h in zip(poses0, half) if not h], intr_a,
                    free_intr=False, radii=(4, 3, 3))
K, D = K_of(intr[0]), cf.dist_of(intr[1:])
# horizontal / vertical / diagonal field of view of the distorted image
edge = np.array([[0, H_PX / 2], [W_PX, H_PX / 2], [W_PX / 2, 0], [W_PX / 2, H_PX], [0, 0], [W_PX, H_PX]], float)
n = cv2.undistortPoints(edge.reshape(-1, 1, 2), K, D)[:, 0]
fov = lambda a, b: float(np.degrees(np.arccos(np.dot(np.r_[a, 1], np.r_[b, 1]) / np.linalg.norm(np.r_[a, 1]) / np.linalg.norm(np.r_[b, 1]))))
result = {
    "description": "Osmo Nano lens model for the .LRF proxy (960 x 720), fitted to the rink (slots + inner board boundary) "
                   "in several frames of one game. OpenCV model: K = [[f,0,cx],[0,f,cy],[0,0,1]], dist = [k1,k2,0,0,0].",
    "status": "PROPOSED", "video": os.path.basename(video), "frames": [int(i) for i in ids],
    "image_size_px": [W_PX, H_PX],
    "f_px": {"value": round(float(intr[0]), 2), "unit": "px (LRF 960 x 720)", "status": "fitted"},
    "principal_point_px": {"value": [W_PX / 2, H_PX / 2], "status": "assumed (image centre)"},
    "dist_k1_k2": [round(float(intr[1]), 5), round(float(intr[2]), 5)],
    "fov_deg": {"horizontal": round(fov(n[0], n[1]), 1), "vertical": round(fov(n[2], n[3]), 1),
                "diagonal": round(fov(n[4], n[5]), 1)},
    "for_4k_main_file": "scale f, cx, cy by 4 (3840 x 2880, same field of view as the proxy: ASSUMED, unchecked)",
    "fits": res,
    "residual_px": {"with_distortion_median": float(np.median([s["median_px"] for s in st_fin])),
                    "pinhole_same_f_median": float(np.median([s["median_px"] for s in st_pin])),
                    "with_distortion_within2px": float(np.median([s["within2px"] for s in st_fin])),
                    "pinhole_within2px": float(np.median([s["within2px"] for s in st_pin])),
                    "held_out_half_median": float(np.median([s["median_px"] for s in st_b])),
                    "held_out_half_intrinsics": [float(v) for v in intr_a]},
    "world_scale_note": "World mm are the repo's preview scale (geometry.json image_to_world, assumed); f is in px and "
                        "does not depend on it, the camera distance does.",
}
json.dump(result, open(out, "w"), indent=1)
print(json.dumps(result["residual_px"]), result["fov_deg"])
# undistorted check image: frame with the most rink spread, undistorted, with straight lines drawn
i0 = int(sel[0, 0]); img = frs[i0]
newK, _ = cv2.getOptimalNewCameraMatrix(K, D, (W_PX, H_PX), 1.0)
und = cv2.undistort(img, K, D, None, newK)
pose = poses0[0]
_, _, _ = None, None, None
o1, o2 = img.copy(), und.copy()
for P in list(slots().values()) + [np.r_[board_points(), board_points()[:1]]]:
    Q = to3(resample(P, 3))
    for p in project(Q, pose[0], pose[1], K, D):
        if np.all(np.isfinite(p)): cv2.circle(o1, tuple(int(v) for v in p), 1, (0, 255, 0), -1)
    for p in project(Q, pose[0], pose[1], newK, np.zeros(5)):
        if np.all(np.isfinite(p)): cv2.circle(o2, tuple(int(v) for v in p), 1, (0, 255, 0), -1)
# a straight-edge test: the table/hall lines should be straight in the undistorted image; draw a grid for reference
for x in range(0, W_PX, 80): cv2.line(o2, (x, 0), (x, H_PX), (0, 200, 255), 1)
for y in range(0, H_PX, 80): cv2.line(o2, (0, y), (W_PX, y), (0, 200, 255), 1)
for im, txt in [(o1, f"frame {i0}: distorted, model with k1,k2"), (o2, "undistorted (alpha=1), model as pinhole")]:
    cv2.putText(im, txt, (10, 28), 0, 0.8, (0, 255, 255), 2)
cv2.imwrite(check, np.hstack([o1, o2]), [cv2.IMWRITE_JPEG_QUALITY, 88])
