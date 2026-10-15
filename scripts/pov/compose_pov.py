"""Step 6: composite the POV renders (render_pov_frames.py) onto their real frames (docs/pov-videos.md).

    python3 scripts/pov/compose_pov.py <video> <plate.png> <render_dir> [--track track.npz] [--sheet sheet.jpg]

Per render: the real frame whose camera the render used is the background. Its real figures and puck are removed
first: inside the space a figure can occupy (every slot +-45 mm, up to 60 mm high) every pixel whose softened colour differs
from the plate warped into the view (sum of |BGR| > 70, grown by 4 px, feathered) is replaced by the plate. The plate
is softer than the frame (it is a median at 1 px/mm), so those patches are blurred. The pinhole canvas is then
warped through the lens distortion into the 960 x 720 frame, and the figures, goals and puck are laid over it (alpha),
with a random contrast and gain and the cast shadows lightened (the hall light is diffuse). A light camera degradation follows (blur, head-motion blur in 15%, colour, noise,
JPEG), so the frames look like the LRF proxy. Writes <render_dir>/<seed>.jpg.
--track: warp the plate with that track's pose for the frame (the marking-fixed track, whose world agrees with the
plate's) instead of the render's pose; both poses put the slots on the same pixels, so the render still lines up.
"""
import json, os, random, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from pov_common import K_of, read_frames, W_PX, H_PX, project, resample, slots
import camera_fit as cf
import rink_plate as rp

_MAPS = {}
SLOTS = slots()


def distort_map(lens, margin):
    """For every distorted frame pixel, the canvas pixel of the pinhole render (map for cv2.remap)."""
    key = (lens["f"], lens["k1"], lens["k2"], margin)
    if key not in _MAPS:
        K, D = K_of(lens["f"]), cf.dist_of([lens["k1"], lens["k2"]])
        u, v = np.meshgrid(np.arange(W_PX, dtype=np.float64), np.arange(H_PX, dtype=np.float64))
        n = cv2.undistortPoints(np.c_[u.ravel(), v.ravel()].reshape(-1, 1, 2), K, D)[:, 0]
        m = (n * lens["f"] + [W_PX / 2 + margin, H_PX / 2 + margin]).reshape(H_PX, W_PX, 2).astype(np.float32)
        _MAPS[key] = (m[..., 0].copy(), m[..., 1].copy())
    return _MAPS[key]


def corridor_mask(rv, tv, K, D, half_mm=45.0, top_mm=60.0):
    """Image mask of the space real figures can occupy: every slot centreline +-half_mm, from the ice to top_mm."""
    m = np.zeros((H_PX, W_PX), np.uint8)
    for P in SLOTS.values():
        Q = resample(P, 6.0)
        for p in Q:
            box = np.array([(p[0] + dx, p[1] + dy, z) for dx in (-half_mm, half_mm) for dy in (-half_mm, half_mm) for z in (0.0, top_mm)])
            Rm = cv2.Rodrigues(np.asarray(rv, float))[0]
            if ((box @ Rm.T + tv)[:, 2] < 30).any(): continue
            q = project(box, rv, tv, K, D)
            if np.isfinite(q).all() and (np.abs(q) < 5000).all():
                cv2.fillConvexPoly(m, cv2.convexHull(np.round(q).astype(np.int32)), 1)
    return m.astype(bool)


def clean_background(real, plate, rv, tv, K, D):
    """Real frame with its real figures and puck replaced by the plate: only inside the figure corridors, and only
    where the (softened) real frame differs from the plate."""
    pv, inside = rp.plate_in_view(plate, rv, tv, K, D)
    soft = cv2.GaussianBlur(real, (0, 0), 1.5)
    d = (np.abs(soft.astype(np.int16) - pv.astype(np.int16)).sum(-1) > 70) & inside & corridor_mask(rv, tv, K, D)
    d = cv2.dilate(d.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool) & inside
    a = cv2.GaussianBlur(d.astype(np.float32), (0, 0), 2.0)[..., None]
    return (real * (1 - a) + pv * a).astype(np.uint8)


def motion_blur(img, rnd, n=None):
    n = n or rnd.randint(3, 7); k = np.zeros((n, n), np.float32); k[n // 2, :] = 1.0 / n
    k = cv2.warpAffine(k, cv2.getRotationMatrix2D((n / 2 - 0.5, n / 2 - 0.5), rnd.uniform(0, 180), 1.0), (n, n)); k /= max(k.sum(), 1e-6)
    return cv2.filter2D(img, -1, k)


def degrade(img, rnd, blur=(0.15, 0.7), jpeg=(55, 92)):
    img = cv2.GaussianBlur(np.asarray(img, np.float32), (0, 0), rnd.uniform(*blur))
    if rnd.random() < 0.15: img = motion_blur(img, rnd)
    hsv = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 0] = (hsv[..., 0] + rnd.uniform(-3, 3)) % 180; hsv[..., 1] *= rnd.uniform(0.85, 1.2); hsv[..., 2] *= rnd.uniform(0.88, 1.12)
    img = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    img += np.random.default_rng(rnd.randrange(1 << 30)).normal(0, rnd.uniform(1, 3.5), img.shape)
    ok, buf = cv2.imencode(".jpg", np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, rnd.randint(*jpeg)])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def compose(rgba, real, plate, lab, rnd, plate_pose=None):
    lens = lab["lens"]; K, D = K_of(lens["f"]), cf.dist_of([lens["k1"], lens["k2"]])
    rv, tv = plate_pose if plate_pose is not None else (np.array(lab["rv"]), np.array(lab["tv"]))
    bg = clean_background(real, plate, rv, tv, K, D).astype(np.float32)
    mx, my = distort_map(lens, lab["margin_px"])
    r = cv2.remap(rgba, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0).astype(np.float32)
    a = r[..., 3:4] / 255.0
    a = np.where(a < 0.97, a * rnd.uniform(0.35, 0.8), a)   # shadows (shadow catcher, alpha < 1) lighter: the hall light is diffuse
    fg = np.clip((r[..., :3] - 128) * rnd.uniform(1.0, 1.3) + 128 + rnd.uniform(-12, 12), 0, 255)
    return degrade(bg * (1 - a) + fg * a, rnd)


if __name__ == "__main__":
    video, plate_path, rdir = sys.argv[1:4]
    plate = cv2.imread(plate_path)
    TR = np.load(sys.argv[sys.argv.index("--track") + 1])["rows"] if "--track" in sys.argv else None
    L = [json.loads(s) for s in open(os.path.join(rdir, "labels.jsonl"))]
    L = [l for l in L if os.path.exists(os.path.join(rdir, f"{l['seed']}.png")) and not os.path.exists(os.path.join(rdir, f"{l['seed']}.jpg"))]
    L.sort(key=lambda l: l["frame"])
    for k in range(0, len(L), 60):
        chunk = L[k:k + 60]; frs = read_frames(video, [l["frame"] for l in chunk])
        for l in chunk:
            rgba = cv2.imread(os.path.join(rdir, f"{l['seed']}.png"), cv2.IMREAD_UNCHANGED)
            pp = (TR[l["frame"], 1:4], TR[l["frame"], 4:7]) if TR is not None else None
            out = compose(rgba, frs[l["frame"]], plate, l, random.Random(l["seed"] * 31 + 7), pp)
            cv2.imwrite(os.path.join(rdir, f"{l['seed']}.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(k + len(chunk), "/", len(L), flush=True)
    if "--sheet" in sys.argv:
        J = sorted(int(f[:-4]) for f in os.listdir(rdir) if f.endswith(".jpg"))[:6]
        ims = [cv2.imread(os.path.join(rdir, f"{j}.jpg")) for j in J]
        while len(ims) % 2: ims.append(np.zeros_like(ims[0]))
        cv2.imwrite(sys.argv[sys.argv.index("--sheet") + 1], np.vstack([np.hstack(ims[i:i + 2]) for i in range(0, len(ims), 2)]))
