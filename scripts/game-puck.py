"""Puck track of the match recording: candidate dark blobs per frame, a logistic classifier, and a Viterbi track.

    /root/venvs/blender/bin/python scripts/game-puck.py            # all stages
    /root/venvs/blender/bin/python scripts/game-puck.py --reuse    # reuse out/game/candidates.json

Inputs: the recording, data/games/fylling-vs-moe-2022/{stabilisation.json, background.png, calibration.json,
puck-labels.json}, data/geometry.json (inner board boundary).
Outputs: data/games/fylling-vs-moe-2022/puck-track.json; out/game/candidates.json (cache, not committed).

1. Candidates (every frame, stabilised crop): seed pixels darker than 80 (HSV value), grey (saturation < 120) and
   at least 45 darker than the background; grown into pixels darker than 145 and 50 darker than the background
   (closing 3 px). A component is a candidate when its area is 25-500 px, at most 45 x 32 px, and 0.2-3x the
   projected top face of a 25.4 mm puck at its position, inside the inner board boundary shrunk by the puck radius.
   Features: size ratios, fill, aspect, darkness, colour, the colours in a ring around it (white ice; yellow or blue
   that is not in the background: jerseys and trousers, not the yellow crease circles or the blue logos), and how many
   candidates of the whole recording fall at the same place (static structures that keep producing candidates).
2. Classifier: logistic regression on puck-labels.json (each label matched to the nearest candidate within 6 px;
   the other candidates of a frame that holds a labelled puck are negatives). Cross-validated in 10 time blocks.
3. Track: Viterbi over states {absent, candidate 1..n} per frame. Score = classifier logit (clipped to +-6) plus
   PRESENCE_BONUS for a candidate; moving between candidates costs d^2 / (2 SIGMA^2) (d in world mm, impossible above
   D_MAX); entering or leaving "absent" costs SWITCH. No position is interpolated: frames without a candidate on the
   track are "not seen".
"""
import sys

import cv2
import numpy as np
from scipy.optimize import minimize

from game_common import GAME, OUT, FPS, geometry, load, proj, save, stabilised_crops, world_to_crop

SIGMA, SWITCH, PRESENCE_BONUS, D_MAX = 30.0, 3.0, 2.0, 160.0
R_PUCK = geometry()["puck"]["diameter"]["value"] / 2
FEATURES = ["area_ratio", "fill", "aspect", "mean_value", "b_minus_g", "b_minus_r", "mean_saturation", "ring_new_yellow",
            "ring_white", "ring_new_blue", "on_dark_background", "width_ratio", "height_ratio", "dark_fraction",
            "log_candidate_density"]
H = world_to_crop()
Hi = np.linalg.inv(H)


def expected(cx, cy):
    """World position and projected bounding box of a puck's top face centred at crop (cx, cy)."""
    w = proj(Hi, [[cx, cy]])[0]
    ring = proj(H, w + R_PUCK * np.c_[np.cos(np.linspace(0, 2 * np.pi, 24)), np.sin(np.linspace(0, 2 * np.pi, 24))])
    ew, eh = np.ptp(ring[:, 0]), np.ptp(ring[:, 1])
    return w, ew, eh


def candidates():
    from shapely.geometry import Polygon
    bg = cv2.imread(str(GAME / "background.png"))
    bgv = cv2.cvtColor(bg, cv2.COLOR_BGR2HSV)[..., 2].astype(int)
    bg_dark = cv2.erode(bgv.astype(np.uint8), np.ones((7, 7), np.uint8)) < 110
    bh = cv2.cvtColor(bg, cv2.COLOR_BGR2HSV).astype(int)
    bg_yellow = (bh[..., 0] >= 18) & (bh[..., 0] <= 40) & (bh[..., 1] > 90) & (bh[..., 2] > 110)
    bg_blue = (bh[..., 0] >= 95) & (bh[..., 0] <= 135) & (bh[..., 1] > 70)
    inner = Polygon(geometry()["board"]["inner_boundary"]["world"]["points_mm"]).buffer(-R_PUCK)
    rink = np.zeros(bg.shape[:2], np.uint8)
    cv2.fillPoly(rink, [proj(H, np.array(inner.exterior.coords)).astype(np.int32)], 1)
    out = []
    for i, f in stabilised_crops():
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        v, s = hsv[..., 2].astype(int), hsv[..., 1]
        seed = (v < 80) & (s < 120) & (bgv > v + 45) & (rink > 0)
        lo = (((v < 145) & (s < 110) & (bgv > v + 50) & (rink > 0)) | seed).astype(np.uint8)
        lo = cv2.morphologyEx(lo, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        n0, l0 = cv2.connectedComponents(lo)
        keep = np.zeros(n0, bool)
        keep[np.unique(l0[seed])] = True
        keep[0] = False
        m = cv2.morphologyEx(keep[l0].astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        n, lab, st, cen = cv2.connectedComponentsWithStats(m)
        for k in range(1, n):
            x, y, w, h, a = st[k]
            if a < 25 or a > 500 or w > 45 or h > 32:
                continue
            wp, ew, eh = expected(*cen[k])
            r = a / (np.pi / 4 * ew * eh)
            if r < 0.2 or r > 3.0:
                continue
            y0, y1, x0, x1 = max(0, y - 6), y + h + 6, max(0, x - 6), x + w + 6
            bm = lab[y0:y1, x0:x1] == k
            pf, ph = f[y0:y1, x0:x1].astype(int), hsv[y0:y1, x0:x1].astype(int)
            ring = cv2.dilate(bm.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool) & ~bm
            Bm, Gm, Rm = pf[bm].mean(0)
            rh, rs, rv = ph[..., 0][ring], ph[..., 1][ring], ph[..., 2][ring]
            by_, bb_ = bg_yellow[y0:y1, x0:x1][ring], bg_blue[y0:y1, x0:x1][ring]
            feat = [a / (np.pi / 4 * ew * eh), a / (w * h), w / max(h, 1), ph[..., 2][bm].mean(), Bm - Gm, Bm - Rm,
                    ph[..., 1][bm].mean(), ((rh >= 18) & (rh <= 40) & (rs > 90) & (rv > 110) & ~by_).mean(),
                    ((rs < 60) & (rv > 150)).mean(), ((rh >= 95) & (rh <= 135) & (rs > 70) & ~bb_).mean(),
                    bg_dark[y0:y1, x0:x1][bm].mean(), w / ew, h / eh, (ph[..., 2][bm] < 75).mean()]
            out.append([i, round(float(cen[k][0]), 2), round(float(cen[k][1]), 2), round(float(wp[0]), 1), round(float(wp[1]), 1),
                        [round(float(q), 4) for q in feat]])
        if i % 1000 == 0:
            print("candidates: frame", i, len(out), flush=True)
    save(OUT / "candidates.json", out)
    return out


def train(C):
    by = {}
    for c in C:
        by.setdefault(c[0], []).append(c)
    L = load(GAME / "puck-labels.json")["points"]
    X, y, grp, matched = [], [], [], 0
    for i, u, v, lab in L:
        cs = by.get(i, [])
        if not cs:
            continue
        d = [np.hypot(c[1] - u, c[2] - v) for c in cs]
        j = int(np.argmin(d))
        if d[j] > 6:
            continue
        matched += 1
        X.append(cs[j][5]); y.append(lab); grp.append(i)
        if lab == 1:
            for jj, c in enumerate(cs):
                if jj != j:
                    X.append(c[5]); y.append(0); grp.append(i)
    X, y, grp = np.array(X, float), np.array(y, float), np.array(grp)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = (X - mu) / sd

    def fit(Z, y):
        n, d = Z.shape
        f = lambda w: np.sum(np.logaddexp(0, Z @ w[:d] + w[d]) - y * (Z @ w[:d] + w[d])) / n + 0.5 * np.sum(w[:d] ** 2) / n
        return minimize(f, np.zeros(d + 1), method="L-BFGS-B").x

    folds = np.digitize(grp, np.quantile(grp, np.linspace(0, 1, 11)[1:-1]))
    pp = np.zeros(len(y))
    for k in range(10):
        tr = folds != k
        w = fit(Z[tr], y[tr])
        pp[~tr] = 1 / (1 + np.exp(-(Z[~tr] @ w[:-1] + w[-1])))
    top = tot = 0
    for i in set(grp[y == 1]):
        m = grp == i
        tot += 1
        top += int(y[m][np.argmax(pp[m])] == 1)
    w = fit(Z, y)
    cv = {"labels_matched": matched, "labels_total": len(L), "examples": int(len(y)), "positives": int(y.sum()),
          "puck_ranked_first_in_labelled_frames": [top, tot],
          "precision_recall": {str(t): [round(float((y[pp > t] == 1).mean()), 3), round(float((pp[y == 1] > t).mean()), 3)] for t in (0.3, 0.5, 0.7)}}
    return {"features": FEATURES, "mean": mu.tolist(), "std": sd.tolist(), "weights": w[:-1].tolist(), "bias": float(w[-1]), "cross_validation": cv}


def track(C, clf):
    mu, sd, w =np.array(clf["mean"]), np.array(clf["std"]), np.array(clf["weights"])
    b = clf["bias"]
    by = {}
    for c in C:
        by.setdefault(c[0], []).append(c)
    N = max(by) + 1
    prevS, prevXY, back = np.array([0.0]), np.zeros((0, 2)), []
    for i in range(N):
        cs = by.get(i, [])
        z = np.clip(((np.array([c[5] for c in cs]) - mu) / sd) @ w + b, -6, 6) + PRESENCE_BONUS if cs else np.zeros(0)
        XY = np.array([[c[3], c[4]] for c in cs]) if cs else np.zeros((0, 2))
        S, Bk = np.zeros(len(cs) + 1), np.zeros(len(cs) + 1, int)
        opts = np.r_[prevS[0], prevS[1:] - SWITCH]
        S[0], Bk[0] = opts.max(), int(opts.argmax())
        for j in range(len(cs)):
            o = [prevS[0] - SWITCH]
            if len(prevXY):
                d = np.hypot(*(prevXY - XY[j]).T)
                t = prevS[1:] - d ** 2 / (2 * SIGMA ** 2)
                t[d > D_MAX] = -1e9
                o += list(t)
            k = int(np.argmax(o))
            S[j + 1], Bk[j + 1] = o[k] + z[j], k
        back.append(Bk)
        prevS, prevXY = S, XY
    st = int(np.argmax(prevS))
    rows = []
    for i in range(N - 1, -1, -1):
        if st > 0:
            c = by[i][st - 1]
            p = 1 / (1 + np.exp(-(((np.array(c[5]) - mu) / sd) @ w + b)))
            rows.append([i, round(i / FPS, 2), c[3], c[4], round(c[1], 1), round(c[2], 1), round(float(p), 3)])
        st = back[i][st]
    return rows[::-1], N


def add_density(C):
    """Append log(1 + number of candidates of the whole recording within ~3 px of this one): static structures that
    flicker into candidates frame after frame (the dark rim of the green ice logo, a goalie's trousers) score high;
    the puck rarely rests in one place that long."""
    from game_common import CROP_W, CROP_H
    D = np.zeros((CROP_H, CROP_W), np.float32)
    for c in C:
        D[min(int(c[2]), CROP_H - 1), min(int(c[1]), CROP_W - 1)] += 1
    K = cv2.GaussianBlur(D, (0, 0), 3) * 2 * np.pi * 9
    for c in C:
        c[5] = c[5][:14] + [round(float(np.log1p(K[min(int(c[2]), CROP_H - 1), min(int(c[1]), CROP_W - 1)])), 4)]
    return C


if __name__ == "__main__":
    C = add_density(load(OUT / "candidates.json") if "--reuse" in sys.argv else candidates())
    clf = train(C)
    rows, N = track(C, clf)
    seen = set(r[0] for r in rows)
    from game_common import match_frames
    mf = list(match_frames())
    save(GAME / "puck-track.json", {
        "description": "Puck positions of the match recording (scripts/game-puck.py). One row per frame where the track has a puck; other frames are 'not seen' (hidden under a figure, motion-blurred, or missed).",
        "columns": ["frame", "video_t_s", "x_mm", "y_mm", "u_crop_px", "v_crop_px", "p_puck"],
        "position_note": "Centre of the dark blob, projected onto the ice plane. The blob includes the puck's visible side, so the point lies a few mm toward the camera (-y) from the puck centre. Status: assumed (calibration status assumed).",
        "tracker": {"sigma_mm": SIGMA, "switch_cost": SWITCH, "presence_bonus": PRESENCE_BONUS, "d_max_mm_per_frame": D_MAX},
        "classifier": clf,
        "candidates": len(C),
        "frames": N,
        "match_frames": [mf[0], mf[-1] + 1],
        "match_frames_seen_fraction": round(sum(1 for i in mf if i in seen) / len(mf), 3),
        "rows": rows,
    })
    print("candidates", len(C), "cv", clf["cross_validation"], "seen in match", round(sum(1 for i in mf if i in seen) / len(mf), 3))
