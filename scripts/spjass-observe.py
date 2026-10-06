"""Spjass: observations from the user's TikTok (references/shots/spjass-tiktok.mp4), take 1 (fixed top-down camera).

    /root/venvs/blender/bin/python scripts/spjass-observe.py

Inputs: shots/spjass/marks.json (hand-read marks), data/geometry.json (slots, landmarks, puck).
Outputs: shots/spjass/observations.json, validation/spjass-observations.png (calibration overlay, puck track, solved W-C poses).

Method:
- Camera: planar homography ice (world mm, z = 0) -> frame px, fitted to the marked slot/line crossings and slot ends
  (residuals and leave-one-out). A full pinhole camera (principal point at the image centre, square pixels) is
  decomposed from it only to correct the parallax of the puck's visible top (the decomposition of a near-top-down view
  is weakly conditioned; it is used for a ~3 mm correction, not for geometry).
- Puck: automatic dark-blob centre per frame (morphological opening removes the thin slot), corrected from the
  assumed blob height (puck mid-height to top) to the ice.
- W-C pose: from the blade-toe mark, the pivot on the W-C slot at the toe's local radius; of the (up to) two
  solutions, the one nearest the visual heading reading. Frames whose toe solution leaves the slot are reported, not used.
"""
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "references/shots/spjass-tiktok.mp4"
SRC_SHA = "bf0da0e1292e47fbad0ceb06334b2991d5d1347048965faf00780203715aebcc"
G = json.loads((REPO / "data/geometry.json").read_text())
M = json.loads((REPO / "shots/spjass/marks.json").read_text())
FIG = json.loads((REPO / "validation/players/figures-report.json").read_text())
OUT = REPO / "shots/spjass/observations.json"
OUT_PNG = REPO / "validation/spjass-observations.png"
FPS = 30.0
TOE = np.array(FIG["assets"]["skater_FIN"]["blade_toe_mm"], float)
PUCK_T = 12.0  # preview puck thickness (validation/12-hardware-report.json)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def overhead_to_world(px):
    Mx = np.array(G["image_to_world"][0]["matrix"]).reshape(3, 3)
    w = Mx @ np.array([px[0], px[1], 1.0])
    return w[:2] / w[2]


LMS = {l["id"]: l for l in G["landmarks"]}
PATHS = {p["player_id"]: np.array(p["centreline"]["points_mm"], float) for p in G["fixture_paths"]}


def line_x(ids):
    return float(np.mean([overhead_to_world(LMS[i]["px"])[0] for i in ids]))


def slot_y_at_x(pid, x):
    P = PATHS[pid]
    o = np.argsort(P[:, 0])
    return float(np.interp(x, P[o, 0], P[o, 1]))


def world_of(pt):
    w = pt["world"]
    if "slot_end" in w:
        return PATHS[w["slot_end"]][-1].copy() if PATHS[w["slot_end"]][-1][0] > PATHS[w["slot_end"]][0][0] else PATHS[w["slot_end"]][0].copy()
    x = line_x(w["line_x_landmarks"])
    return np.array([x, slot_y_at_x(w["slot"], x)])


class Slot:
    def __init__(self, pid):
        self.P = PATHS[pid]
        self.s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(self.P, axis=0), axis=1))]

    def at(self, a):
        return np.array([np.interp(a, self.s, self.P[:, 0]), np.interp(a, self.s, self.P[:, 1])])


def main():
    assert sha(SRC) == SRC_SHA, "source video changed"
    cap = cv2.VideoCapture(str(SRC))
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    # ---- camera
    pts = M["camera_correspondences"]["points"]
    W = np.array([world_of(p) for p in pts]); I = np.array([p["frame_px"] for p in pts], float)
    H, _ = cv2.findHomography(W, I, 0)
    res = np.linalg.norm(cv2.perspectiveTransform(W[None], H)[0] - I, axis=1)
    corr = []
    for k, p in enumerate(pts):
        m = np.ones(len(pts), bool); m[k] = False
        Hk, _ = cv2.findHomography(W[m], I[m], 0)
        loo = float(np.linalg.norm(cv2.perspectiveTransform(W[k:k + 1][None], Hk)[0][0] - I[k]))
        corr.append({"id": p["id"], "frame_px": p["frame_px"], "world_mm": [round(float(v), 2) for v in W[k]], "residual_px": round(float(res[k]), 1), "leave_one_out_px": round(loo, 1)})
    HI = np.linalg.inv(H)
    cx, cy = frames[0].shape[1] / 2, frames[0].shape[0] / 2

    def ortho(f):
        A = np.linalg.inv(np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])) @ H
        a1, a2 = A[:, 0], A[:, 1]
        return abs(a1 @ a2) / (np.linalg.norm(a1) * np.linalg.norm(a2)) + abs(np.linalg.norm(a1) / np.linalg.norm(a2) - 1)
    fs = np.arange(300, 4000, 1.0)
    f_px = float(fs[int(np.argmin([ortho(f) for f in fs]))])
    K = np.array([[f_px, 0, cx], [0, f_px, cy], [0, 0, 1.0]])
    A = np.linalg.inv(K) @ H
    lam = 1 / np.linalg.norm(A[:, 0])
    r1, r2, t = A[:, 0] * lam, A[:, 1] * lam, A[:, 2] * lam
    if t[2] < 0:
        r1, r2, t = -r1, -r2, -t
    R = np.c_[r1, r2, np.cross(r1, r2)]
    C = -R.T @ t

    def ground_of(px, z):
        """World point at height z seen at frame px (camera ray), returned as its ice position (x, y)."""
        d = R.T @ (np.linalg.inv(K) @ np.array([px[0], px[1], 1.0]))
        s = (z - C[2]) / d[2]
        return (C + s * d)[:2]

    # ---- puck track (take 1)
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    puck = []
    for i in range(96, 134):
        hsv = cv2.cvtColor(frames[i], cv2.COLOR_BGR2HSV)
        m = (hsv[:, :, 2] < 75).astype(np.uint8) * 255
        m[:330] = 0  # goal interior and the area behind the goal
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, ker)
        n, lab, st, cen = cv2.connectedComponentsWithStats(m)
        cand = [(st[k][4], cen[k], st[k]) for k in range(1, n) if 400 <= st[k][4] <= 6000]
        if not cand:
            continue
        a, c, s_ = max(cand, key=lambda q: q[0])
        blur = s_[2] / s_[3] < 0.85 or s_[3] / s_[2] < 0.85
        z_mid, z_top = PUCK_T / 2, PUCK_T
        g_mid, g_top = ground_of(c, z_mid), ground_of(c, z_top)
        puck.append({"frame": i, "t_s": round(i / FPS, 4), "blob_px": [round(float(v), 1) for v in c], "blob_size_px": [int(s_[2]), int(s_[3])],
                     "motion_blurred": bool(blur), "world_mm": [round(float(v), 2) for v in (g_mid + g_top) / 2],
                     "parallax_range_mm": round(float(np.linalg.norm(g_mid - g_top)), 2),
                     "reading_uncertainty_mm": 6.0 if blur else 2.5})
    # ---- W-C poses from blade-toe marks
    slot = Slot("W-C")
    rt = float(np.linalg.norm(TOE)); a_toe = math.degrees(math.atan2(TOE[1], TOE[0]))
    poses = []
    for fr, px in M["blade_toe_marks"]["frames"].items():
        T = cv2.perspectiveTransform(np.array([[px]], float), HI)[0][0]
        sols = []
        a = 0.0
        prev = None
        while a <= slot.s[-1]:
            d = T - slot.at(a)
            e = np.linalg.norm(d) - rt
            if prev is not None and prev[1] * e <= 0:
                # refine the crossing linearly
                a0, e0 = prev
                ac = a0 + (a - a0) * e0 / (e0 - e) if e0 != e else a
                dc = T - slot.at(ac)
                sols.append((ac, (math.degrees(math.atan2(dc[1], dc[0])) - a_toe) % 360))
            prev = (a, e)
            a += 0.1
        vis = M["blade_toe_marks"]["visual_heading_deg"].get(fr)
        rec = {"frame": int(fr), "t_s": round(int(fr) / FPS, 4), "toe_px": px, "toe_world_mm": [round(float(v), 1) for v in T],
               "solutions": [{"arc_mm": round(s0, 1), "heading_deg": round(h, 1)} for s0, h in sols], "visual_heading_deg": vis}
        if sols and vis is not None:
            best = min(sols, key=lambda q: abs(((q[1] - vis + 180) % 360) - 180))
            rec["chosen"] = {"arc_mm": round(best[0], 1), "heading_deg": round(best[1], 1),
                             "heading_minus_visual_deg": round(((best[1] - vis + 180) % 360) - 180, 1)}
        poses.append(rec)
    # ---- E-G pose from its blade mark
    gm = M["goalie_blade_mark"]
    gh, gt = (cv2.perspectiveTransform(np.array([[gm[k]]], float), HI)[0][0] for k in ("heel_px", "toe_px"))
    lh, lt = (np.array(FIG["assets"]["goalie_SWE"][k], float) for k in ("blade_heel_mm", "blade_toe_mm"))
    g_head = math.degrees(math.atan2(*(gt - gh)[::-1])) - math.degrees(math.atan2(*(lt - lh)[::-1]))
    Rg = np.array([[math.cos(math.radians(g_head)), -math.sin(math.radians(g_head))], [math.sin(math.radians(g_head)), math.cos(math.radians(g_head))]])
    g_piv = gh - Rg @ lh
    eg_slot = Slot("E-G")
    a_best = min(np.arange(0, eg_slot.s[-1] + 1e-9, 0.1), key=lambda a: np.linalg.norm(eg_slot.at(a) - g_piv))
    goalie = {"frame": gm["frame"], "heel_world_mm": [round(float(v), 1) for v in gh], "toe_world_mm": [round(float(v), 1) for v in gt],
              "blade_length_mm": round(float(np.linalg.norm(gt - gh)), 1), "model_blade_length_mm": round(float(np.linalg.norm(lt - lh)), 1),
              "heading_deg": round(g_head % 360, 1), "pivot_mm": [round(float(v), 1) for v in g_piv], "nearest_arc_mm": round(float(a_best), 1),
              "pivot_to_slot_mm": round(float(np.linalg.norm(eg_slot.at(a_best) - g_piv)), 1)}
    obs = {
        "schema": "shot-observations/1",
        "shot": "spjass (centre move) - user TikTok",
        "source": {"path": str(SRC.relative_to(REPO)), "sha256": SRC_SHA, "frames": len(frames), "fps": FPS,
                   "size_px": [frames[0].shape[1], frames[0].shape[0]], "time_base": "t_s = frame / 30 (real time; take 1 shows normal motion)"},
        "camera_take1": {"H_world_mm_to_frame_px": H.tolist(), "rms_px": round(float(np.sqrt(np.mean(res ** 2))), 2),
                         "leave_one_out_rms_px": round(float(np.sqrt(np.mean([c["leave_one_out_px"] ** 2 for c in corr]))), 2),
                         "correspondences": corr,
                         "pinhole_estimate": {"f_px": f_px, "camera_centre_mm": [round(float(v), 1) for v in C],
                                              "note": "principal point at the image centre and square pixels assumed; weakly conditioned (near top-down view); used only for the puck parallax correction"}},
        "puck_take1": puck,
        "w_c_blade_poses": poses,
        "e_g_blade_pose": goalie,
        "qualitative_evidence": M["qualitative_evidence"],
        "interpretation": [
            "rest (frames 66-121): W-C faces away from goal.E (heading about 190 deg), the puck lies behind its back on the slot line, near the slot end.",
            "turn and sweep (122-128): W-C turns counter-clockwise (seen from above) to about 296 deg; the blade comes round to the puck's -y side and pushes it toward +y (blade speed matches the puck speed, about 8 mm per frame).",
            "free slide (128-131): the puck slides on in a straight line, decelerating evenly (ice friction).",
            "spin and shot (129-132, motion-blurred): W-C spins clockwise almost a full turn while sliding up its slot about 25 mm; the blade arrives behind the puck (its -x side) and drives it along +x (puck about 55 mm per frame).",
            "goal (133): the puck crosses the goal line inside the +y post; W-C follows through to about 300 deg and turns back (134-140)."],
    }
    OUT.write_text(json.dumps(obs, indent=1) + "\n")
    # ---- overlay
    img = frames[100].copy()
    for pid, P in PATHS.items():
        Q = cv2.perspectiveTransform(P[None], H)[0]
        cv2.polylines(img, [Q.astype(np.int32)], False, (255, 160, 0), 1, cv2.LINE_AA)
    for c in corr:
        p = np.array(c["frame_px"]); q = cv2.perspectiveTransform(np.array([[c["world_mm"]]]), H)[0][0]
        cv2.circle(img, tuple(int(v) for v in p), 5, (0, 0, 255), 1, cv2.LINE_AA)
        cv2.drawMarker(img, tuple(int(v) for v in q), (0, 200, 0), cv2.MARKER_CROSS, 9, 1)
    for r in puck:
        q = cv2.perspectiveTransform(np.array([[r["world_mm"]]], float), H)[0][0]
        cv2.circle(img, tuple(int(v) for v in q), 2, (0, 255, 255) if not r["motion_blurred"] else (0, 128, 255), -1)
    for r in poses:
        if "chosen" in r:
            piv = slot.at(r["chosen"]["arc_mm"]); h = math.radians(r["chosen"]["heading_deg"])
            Rh = np.array([[math.cos(h), -math.sin(h)], [math.sin(h), math.cos(h)]])
            heel, toe = piv + Rh @ np.array(FIG["assets"]["skater_FIN"]["blade_heel_mm"]), piv + Rh @ TOE
            q = cv2.perspectiveTransform(np.array([[piv, heel, toe]], float), H)[0].astype(int)
            cv2.line(img, tuple(q[1]), tuple(q[2]), (255, 0, 255), 2, cv2.LINE_AA)
            cv2.circle(img, tuple(q[0]), 3, (255, 0, 255), -1)
    big = cv2.resize(img, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    cv2.putText(big, "spjass take 1 - frame 100 with projected slots (blue), marks (red) vs fit (green),", (8, 24), 0, 0.55, (0, 0, 0), 2)
    cv2.putText(big, "puck track 96-133 (yellow; blurred orange), W-C blade poses from toe marks (magenta)", (8, 46), 0, 0.55, (0, 0, 0), 2)
    cv2.imwrite(str(OUT_PNG), big)
    print(json.dumps({"rms_px": obs["camera_take1"]["rms_px"], "loo_rms_px": obs["camera_take1"]["leave_one_out_rms_px"], "camera": obs["camera_take1"]["pinhole_estimate"],
                      "poses": [(r["frame"], r.get("chosen")) for r in poses], "goalie": goalie}, indent=1))


if __name__ == "__main__":
    main()
