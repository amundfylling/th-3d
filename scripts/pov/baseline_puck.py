"""Step 5 of the POV plan, puck part: run puck-v1 (scripts/synth/train-puck-detector.py, trained in the NM26
broadcast's stabilised view) unchanged on solved POV frames.

Input as NM26: frames t-1, t, t+1 and the empty rink, in stab px (reference video px - roi_px origin, 1580 x 460),
at half resolution. Here each POV frame's ice plane is re-projected into that view (the broadcast reference camera,
camera-ref.json): every stab pixel is a world point on the ice, looked up in the POV frame through its solved camera.
The background is the POV game's own empty-rink plate (rink_plate.py) seen the same way. Anything above the ice
(figures, the puck's top face) is placed wrongly by this warp, by its height times the difference in view angle.
Output: per frame the top heatmap peaks (stab px, score) and their world point on the ice (z = 0 plane).
Usage: python3 scripts/pov/baseline_puck.py <video> <track.npz> <plate.png> <outdir> [n_frames]
"""
import json, os, sys
import numpy as np
import cv2
import torch

sys.path.insert(0, os.path.dirname(__file__))
from pov_common import REPO, K_of, read_frames, project, W_PX, H_PX
import camera_fit as cf
import rink_plate as rp
from baseline_models import Kr, Rr, tr, SX0, SY0, SX1, SY1

torch.set_num_threads(4)
WS, HS = SX1 - SX0, SY1 - SY0
STRIDE = 4


def load_puck_net():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tp_src", REPO / "scripts/synth/train-puck-detector.py")
    src = open(spec.origin).read()
    # only the model definition is needed (the training script loads its data at import)
    start = src.index("def cbr("); end = src.index("def to_input(")
    ns = {"nn": torch.nn, "F": torch.nn.functional, "torch": torch}
    exec(src[start:end], ns)
    net = ns["PuckNet"](); net.load_state_dict(torch.load(REPO / "out/synth/puck-det-v1.pt", map_location="cpu"))
    return net.eval()


Hr = Kr @ np.c_[Rr[:, 0], Rr[:, 1], tr]
Hr_inv = np.linalg.inv(Hr)
u, v = np.meshgrid(np.arange(WS) + SX0 + 0.0, np.arange(HS) + SY0 + 0.0)
_w = np.c_[u.ravel(), v.ravel(), np.ones(u.size)] @ Hr_inv.T
WORLD = _w[:, :2] / _w[:, 2:]
WORLD3 = np.c_[WORLD, np.zeros(len(WORLD))]


def stab_of_pov(img, rv, tv, K, D):
    q = project(WORLD3, rv, tv, K, D).reshape(HS, WS, 2).astype(np.float32)
    q = np.nan_to_num(q, nan=-10, posinf=-10, neginf=-10)
    return cv2.remap(img, q[..., 0], q[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def stab_background(plate):
    mx = (WORLD[:, 0] - rp.X0 - 0.5).reshape(HS, WS).astype(np.float32)
    my = (rp.Y1 - WORLD[:, 1] - 0.5).reshape(HS, WS).astype(np.float32)
    return cv2.remap(plate, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def peaks(logit, k=6):
    p = torch.sigmoid(logit); m = torch.nn.functional.max_pool2d(p, 3, 1, 1); p = p * (p == m).float()
    B = p.shape[0]; val, idx = p.view(B, -1).topk(k); W = p.shape[-1]
    return val, idx // W, idx % W


if __name__ == "__main__":
    video, track, plate_path, outdir = sys.argv[1:5]
    N = int(sys.argv[5]) if len(sys.argv) > 5 else 200
    os.makedirs(outdir, exist_ok=True)
    T = np.load(track); A = T["rows"]; intr = T["intr"]
    K, D = K_of(intr[0]), cf.dist_of(intr[1:])
    okf = {int(r[0]): r for r in A if r[11] > 0}
    cand = [i for i in sorted(okf) if i - 1 in okf and i + 1 in okf and okf[i][13] >= 0.7]
    sel = [cand[j] for j in np.linspace(0, len(cand) - 1, min(N, len(cand))).astype(int)]
    bg = stab_background(cv2.imread(plate_path))
    bgh = cv2.resize(bg, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    net = load_puck_net()
    rows, keep = [], []
    for chunk in np.array_split(np.array(sel), max(1, len(sel) // 30)):
        need = sorted({j for i in chunk for j in (i - 1, i, i + 1)})
        frs = read_frames(video, need)
        st = {j: cv2.resize(stab_of_pov(frs[j], okf[j][1:4], okf[j][4:7], K, D), None, fx=0.5, fy=0.5,
                            interpolation=cv2.INTER_AREA) for j in need}
        xs = [np.concatenate([st[i - 1], st[i], st[i + 1], bgh], 2).astype(np.float32) / 255.0 - 0.5 for i in chunk]
        x = torch.from_numpy(np.stack(xs).transpose(0, 3, 1, 2).copy())
        with torch.no_grad():
            lg, of = net(x)
        val, iy, ix = peaks(lg[:, 0])
        for b, i in enumerate(chunk):
            r = okf[int(i)]; C = -cv2.Rodrigues(r[1:4])[0].T @ r[4:7]
            c = []
            for j in range(val.shape[1]):
                s = float(val[b, j]); yy, xx = int(iy[b, j]), int(ix[b, j])
                pu = (xx + float(of[b, 0, yy, xx])) * STRIDE; pv = (yy + float(of[b, 1, yy, xx])) * STRIDE
                w = Hr_inv @ [pu + SX0, pv + SY0, 1.0]; w = w[:2] / w[2]
                pov = project(np.array([[w[0], w[1], 0.0]]), r[1:4], r[4:7], K, D)[0]
                c.append({"stab_px": [round(pu, 1), round(pv, 1)], "score": round(s, 4),
                          "world_mm": [round(float(w[0]), 1), round(float(w[1]), 1)], "pov_px": [round(float(pov[0]), 1), round(float(pov[1]), 1)],
                          "dist_from_camera_mm": round(float(np.linalg.norm(np.r_[w, 0] - C)), 1)})
            rows.append({"frame": int(i), "cands": c})
            keep.append((int(i), st[int(i)], c))
        print(len(rows), "/", len(sel), flush=True)
    json.dump({"status": "PROPOSED", "video": os.path.basename(video), "rows": rows}, open(os.path.join(outdir, "puck.json"), "w"))
    import pickle
    pickle.dump(keep[:: max(1, len(keep) // 40)], open(os.path.join(outdir, "puck-stab.pkl"), "wb"))
