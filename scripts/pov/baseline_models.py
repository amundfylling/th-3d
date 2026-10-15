"""Step 5 of the POV plan: run the NM26-trained models, unchanged, on solved POV frames of one game.

The models were trained on crops from the fixed NM26 broadcast camera (data/games/nm26-semifinal/camera-ref.json).
Each POV crop is placed so that it looks as much like a broadcast crop as a 2D warp allows:
- skaters (skater-v3): a similarity warp of the POV frame that puts the foot point at the crop position the tracker
  uses (100, 136) and maps the figure's projected vertical (foot to 50 mm above it) onto the broadcast's (same length,
  same image direction). The foot point is the kit-colour localiser's best spot along the slot, as in tracker v3,
  with the empty-rink plate (rink_plate.py) warped into the frame as background.
- goalies (goalie-c): the same similarity at the goalie slot's midpoint, placed where the slot midpoint falls in the
  broadcast goal box (camera-ref goal_crop_boxes_video_px).
- puck (puck-v1): the ice plane of frames t-1, t, t+1 re-projected into the broadcast's stabilised view
  (1580 x 460 stab px), the plate likewise as background.
The figures are 3D, so neither warp makes them look as from the broadcast camera: the test is how much the models
depend on that camera. No labels exist for this video; the measures are model-internal (presence, the pivot's
distance from the slot, agreement with the colour localiser) plus the review sheets.
Usage: python3 scripts/pov/baseline_models.py <video> <track.npz> <plate.png> <outdir> [n_frames]
"""
import json, math, os, sys
import numpy as np
import cv2
import torch
import torch.nn as nn
import torchvision

sys.path.insert(0, os.path.dirname(__file__))
from pov_common import REPO, K_of, read_frames, project, slots, to3, resample, W_PX, H_PX
import camera_fit as cf
import rink_plate as rp

torch.set_num_threads(4)
ORDER = ["W-LW", "E-LW", "W-RW", "E-RW", "W-C", "E-C", "W-LD", "E-LD", "W-RD", "E-RD"]
HOME = {"W": 0.0, "E": 180.0}
MEAN = np.array([0.485, 0.456, 0.406]); STD = np.array([0.229, 0.224, 0.225])
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
Kr, Rr, tr = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
BOX = CAM["goal_crop_boxes_video_px"]
CFG = json.loads((REPO / "data/games/nm26-semifinal/config.json").read_text())
SX0, SY0, SX1, SY1 = CFG["roi_px"]
FIG_H = 50.0     # mm above the foot used for the crop's vertical


def ground_scale(proj, p):
    """sqrt of the image area of a 1 mm^2 ice patch at p (px per mm) under the projection proj."""
    q = proj(np.array([p, p + [5.0, 0, 0], p + [0, 5.0, 0]]))
    J = np.c_[q[1] - q[0], q[2] - q[0]] / 5.0
    return math.sqrt(abs(np.linalg.det(J)))


def placement(proj_pov, p, dst, mode):
    """Similarity POV px -> crop px with the foot p at dst. mode 'vertical': the figure's projected vertical matched to
    the broadcast's (length and direction); 'ground': the ice-plane scale matched, the vertical's direction matched."""
    f3 = np.r_[p[:2], 0.0]
    fp, hp = proj_pov(np.array([f3, f3 + [0, 0, FIG_H]]))
    fr_, hr_ = proj_ref(np.array([f3, f3 + [0, 0, FIG_H]]))
    b = hr_ - fr_
    if mode == "ground":
        s = ground_scale(proj_ref, f3) / ground_scale(proj_pov, f3)
        a = hp - fp
        b = b / np.linalg.norm(b) * np.linalg.norm(a) * s
    return similarity(fp, hp, dst, dst + b), float(np.linalg.norm(hp - fp)), float(np.linalg.norm(hr_ - fr_))


def proj_ref(P):
    P = np.atleast_2d(np.asarray(P, float)); q = (P @ Rr.T + tr) @ Kr.T; return q[:, :2] / q[:, 2:]


def similarity(src_a, src_b, dst_a, dst_b):
    """2x3 similarity mapping src_a -> dst_a and the vector (src_b - src_a) onto (dst_b - dst_a)."""
    a = np.asarray(src_b, float) - src_a; b = np.asarray(dst_b, float) - dst_a
    s = np.linalg.norm(b) / max(np.linalg.norm(a), 1e-6)
    th = math.atan2(b[1], b[0]) - math.atan2(a[1], a[0])
    Rm = s * np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    return np.c_[Rm, np.asarray(dst_a, float) - Rm @ src_a]


def inv_affine(M, xy):
    A = np.r_[M, [[0, 0, 1]]]; p = np.linalg.solve(A, [xy[0], xy[1], 1.0]); return p[:2]


# ------------------------------------------------------------------ models (architectures as in scripts/synth)
def skater_model():
    m = torchvision.models.resnet18(weights=None)
    m.conv1 = nn.Conv2d(3 + len(ORDER), 64, 7, 2, 3, bias=False); m.fc = nn.Linear(512, 5)
    m.load_state_dict(torch.load(REPO / "out/synth/skater-pose-v3.pt", map_location="cpu")); return m.eval()


def goalie_model():
    m = torchvision.models.resnet18(weights=None)
    m.conv1 = nn.Conv2d(4, 64, 7, 2, 3, bias=False); m.fc = nn.Linear(512, 3)
    m.load_state_dict(torch.load(REPO / "out/synth/goalie-pose-v2c.pt", map_location="cpu")); return m.eval()


def crop_tensor(bgr, extra):
    x = cv2.resize(bgr[20:190, 15:185], (160, 160), interpolation=cv2.INTER_AREA)[..., ::-1] / 255.0
    x = (x - MEAN) / STD
    return torch.tensor(np.concatenate([x, extra], -1).transpose(2, 0, 1), dtype=torch.float32)


def skater_tensor(bgr, pid):
    oh = np.zeros((160, 160, len(ORDER))); oh[..., ORDER.index(pid)] = 1.0; return crop_tensor(bgr, oh)


def goalie_tensor(bgr, end):
    return crop_tensor(bgr, np.full((160, 160, 1), 1.0 if end == "E" else -1.0))


def net_to_px(v): return (v[0] * 170.0 + 15, v[1] * 170.0 + 20)


# ------------------------------------------------------------------ geometry along slots
SL = slots()


def slot_samples(pid, step=3.0):
    P = SL[pid]; Q = resample(P, step)
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
    return Q, s


def u_and_dist(pid, xy):
    P = SL[pid]; seg = np.diff(P, axis=0); L = np.linalg.norm(seg, axis=1); acc = np.r_[0, np.cumsum(L)]
    best = (1e9, 0.0)
    for k in range(len(seg)):
        f = np.clip(np.dot(xy - P[k], seg[k]) / (L[k] ** 2), 0, 1); d = np.linalg.norm(P[k] + f * seg[k] - xy)
        if d < best[0]: best = (d, (acc[k] + f * L[k]) / acc[-1])
    return best[1], best[0]


RING = np.array([(r * np.cos(a), r * np.sin(a), z) for r in (0, 8) for a in np.linspace(0, 2 * np.pi, 8, endpoint=False)
                 for z in (8, 18, 28, 38)])


def team_mask(img, plate_view, inside, end):
    d = (np.abs(img.astype(np.int16) - plate_view.astype(np.int16)).sum(-1) > 60) & inside
    h = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); H, Sa, V = h[..., 0], h[..., 1], h[..., 2]
    col = ((H >= 15) & (H <= 35) & (Sa > 110) & (V > 110)) if end == "E" else \
        (((H >= 100) & (H <= 130) & (Sa > 100)) | ((Sa < 45) & (V > 185)))
    return cv2.blur((d & col).astype(np.float32), (3, 3))


def locate(mask, pid, rv, tv, K, D):
    pts, s = slot_samples(pid)
    X = (RING[None] + np.c_[pts, np.zeros(len(pts))][:, None]).reshape(-1, 3)
    q = np.round(project(X, rv, tv, K, D)).reshape(len(pts), len(RING), 2)
    q = np.nan_to_num(q, nan=-1).astype(int)
    ok = (q[..., 0] >= 0) & (q[..., 0] < W_PX) & (q[..., 1] >= 0) & (q[..., 1] < H_PX)
    sc = np.where(ok, mask[np.clip(q[..., 1], 0, H_PX - 1), np.clip(q[..., 0], 0, W_PX - 1)], 0).sum(1)
    i = int(np.argmax(sc)); return pts[i], float(sc[i]), float(ok.mean(1)[i])


def backproject(px, rv, tv, K, D, z=0.0):
    n = cv2.undistortPoints(np.asarray(px, float).reshape(1, 1, 2), K, D)[0, 0]
    Rm = cv2.Rodrigues(np.asarray(rv, float))[0]; C = -Rm.T @ np.asarray(tv, float)
    d = Rm.T @ np.r_[n, 1.0]; s = (z - C[2]) / d[2]; return (C + s * d)[:2]


def view_azimuth(C, p):
    return math.degrees(math.atan2(p[1] - C[1], p[0] - C[0]))


C_REF = -Rr.T @ tr


if __name__ == "__main__":
    video, track, plate_path, outdir = sys.argv[1:5]
    N = int(sys.argv[5]) if len(sys.argv) > 5 else 300
    MODE = sys.argv[6] if len(sys.argv) > 6 else "ground"
    os.makedirs(outdir, exist_ok=True)
    T = np.load(track); A = T["rows"]; intr = T["intr"]
    K, D = K_of(intr[0]), cf.dist_of(intr[1:])
    plate = cv2.imread(plate_path)
    good = A[(A[:, 11] > 0) & (A[:, 13] >= 0.98)]
    sel = good[np.linspace(0, len(good) - 1, min(N, len(good))).astype(int)]
    sk, gk = skater_model(), goalie_model()
    rows, crops_keep = [], {}
    for chunk in np.array_split(sel, max(1, len(sel) // 40)):
        frs = read_frames(video, chunk[:, 0].astype(int))
        for r in chunk:
            i = int(r[0]); img = frs[i]; rv, tv = r[1:4], r[4:7]
            Rm = cv2.Rodrigues(rv)[0]; C = -Rm.T @ tv
            pv, inside = rp.plate_in_view(plate, rv, tv, K, D)
            pp = lambda X, rv=rv, tv=tv: project(X, rv, tv, K, D)
            masks = {e: team_mask(img, pv, inside, e) for e in "WE"}
            tens, meta = [], []
            for pid in ORDER:
                foot, sc, vis = locate(masks[pid[0]], pid, rv, tv, K, D)
                M, hpov, href = placement(pp, foot, np.array([100.0, 136.0]), MODE)
                crop = cv2.warpAffine(img, M, (200, 200), flags=cv2.INTER_AREA, borderMode=cv2.BORDER_REPLICATE)
                tens.append(skater_tensor(crop, pid))
                meta.append((pid, foot, sc, vis, M, crop, hpov, href, float(M[0, 0] ** 2 + M[0, 1] ** 2) ** 0.5))
            gtens, gmeta = [], []
            for e in "WE":
                gpid = f"{e}-G"; P = SL[gpid]; mid = resample(P, 1.0)[len(resample(P, 1.0)) // 2]
                bx = BOX[e]; o = proj_ref(np.r_[mid, 0.0])[0] - [bx[0], bx[1]]
                M, _, _ = placement(pp, mid, o, MODE)
                crop = cv2.warpAffine(img, M, (bx[2] - bx[0], bx[3] - bx[1]), flags=cv2.INTER_AREA,
                                      borderMode=cv2.BORDER_REPLICATE)
                gfoot, gsc, _ = locate(masks[e], gpid, rv, tv, K, D)
                gtens.append(goalie_tensor(crop, e)); gmeta.append((gpid, crop, gfoot, gsc, mid))
            with torch.no_grad():
                P = sk(torch.stack(tens)).numpy(); G = gk(torch.stack(gtens)).numpy()
            row = {"frame": i, "cam_centre_mm": [round(float(v), 1) for v in C], "skaters": {}, "goalies": {}}
            for (pid, foot, sc, vis, M, crop, hpov, href, zoom), p in zip(meta, P):
                cxy = net_to_px(p[:2]); pov_px = inv_affine(M, cxy)
                w = backproject(pov_px, rv, tv, K, D)
                u, d = u_and_dist(pid, w); u_loc, _ = u_and_dist(pid, foot)
                L = float(np.sum(np.linalg.norm(np.diff(SL[pid], axis=0), axis=1)))
                th = float(np.degrees(np.arctan2(p[2], p[3])) % 360)
                corr = (th + view_azimuth(C, foot) - view_azimuth(C_REF, foot)) % 360
                row["skaters"][pid] = {
                    "loc_xy_mm": [round(float(v), 1) for v in foot], "loc_score": round(sc, 2), "loc_visible": round(vis, 2),
                    "dist_from_camera_mm": round(float(np.linalg.norm(np.r_[foot, 0] - C)), 1),
                    "fig_px_pov": round(hpov, 1), "fig_px_ref": round(href, 1), "crop_zoom": round(zoom, 2),
                    "model_xy_mm": [round(float(v), 1) for v in w], "model_u": round(float(u), 4),
                    "pivot_slot_dist_mm": round(float(d), 1), "model_vs_loc_mm": round(float(abs(u - u_loc) * L), 1),
                    "presence": round(float(1 / (1 + np.exp(-p[4]))), 3), "theta_raw_deg": round(th, 1),
                    "theta_view_corrected_deg": round(float(corr), 1)}
                crops_keep.setdefault(pid, []).append((i, crop, cxy, th, row["skaters"][pid]))
            for (gpid, crop, gfoot, gsc, mid), q in zip(gmeta, G):
                u = float(np.clip(q[0], 0, 1)); ul, dl = u_and_dist(gpid, gfoot)
                L = float(np.sum(np.linalg.norm(np.diff(SL[gpid], axis=0), axis=1)))
                th = float(np.degrees(np.arctan2(q[1], q[2])) % 360)
                row["goalies"][gpid] = {"model_u": round(u, 4), "loc_u": round(float(ul), 4), "loc_score": round(gsc, 2),
                                        "model_vs_loc_mm": round(abs(u - ul) * L, 1), "theta_raw_deg": round(th, 1),
                                        "dist_from_camera_mm": round(float(np.linalg.norm(np.r_[mid, 0] - C)), 1)}
                crops_keep.setdefault(gpid, []).append((i, crop, None, th, row["goalies"][gpid]))
            rows.append(row)
        print(len(rows), "/", len(sel), flush=True)
    json.dump({"status": "PROPOSED", "video": os.path.basename(video), "placement": MODE, "rows": rows}, open(os.path.join(outdir, "figures.json"), "w"))
    # sample crops for the review sheet
    import pickle
    keep = {k: [v[j] for j in np.linspace(0, len(v) - 1, min(12, len(v))).astype(int)] for k, v in crops_keep.items()}
    pickle.dump(keep, open(os.path.join(outdir, "crops.pkl"), "wb"))
