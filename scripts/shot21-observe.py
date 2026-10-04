"""Iteration 21: observations from one real shot recording (no motion fitting, no animation).

    /root/venvs/blender/bin/python scripts/shot21-observe.py [path/to/recording.mov]

Inputs: the recording (default references/shots/shovel-17-screen-recording.mov, SHA-256 pinned below),
shots/21-shovel/marks.json (hand-read image marks) and data/geometry.json (world frame, slot centrelines,
overhead landmarks). Outputs:
  shots/21-shovel/observations.json   timing analysis, camera mapping, figure/puck observations, events
  validation/21-contact-sheet.png     labelled stills: preparation, pass, blade contact, carry, goal entry
  validation/21-camera-calibration.png  segment-1 camera: projected slots/lines and correspondence residuals
Recording timestamps are the container's presentation times. The screen recording runs at ~60 fps but repeats
content frames; the content (playback) frame rate is measured from unique frames, never assumed from the
container rate.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
DEFAULT = REPO / "references" / "shots" / "shovel-17-screen-recording.mov"
SHA256 = "65eca3cd30a39eb7a90f559936fbb0ffffdad64f5a22165eca4734928e557886"
SHOT = REPO / "shots" / "21-shovel"
DUP_DIFF = 0.15   # mean abs grey difference (0-255, 639x295 thumbnails) below which a frame repeats its predecessor
CUT_DIFF = 30.0   # above this: hard cut (title card -> shot, shot -> replay)
FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
FS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def container_info(p):
    try:
        import imageio_ffmpeg
        out = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(p)], capture_output=True, text=True).stderr
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
    keep = [ln.strip() for ln in out.splitlines() if any(k in ln for k in ("Duration", "Stream #", "creation_time", "author", "rotation", "encoder"))]
    return {"ffmpeg_header": keep}


def read_frames(p):
    cap = cv2.VideoCapture(str(p))
    frames, ts, diffs, prev = [], [], [], None
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(cv2.resize(fr, (639, 295)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        diffs.append(float(np.mean(np.abs(g - prev))) if prev is not None else None)
        ts.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
        frames.append(fr)
        prev = g
    return frames, np.array(ts), diffs, {"container_fps": cap.get(cv2.CAP_PROP_FPS)}


def timing(ts, diffs):
    n = len(ts)
    cuts = [i for i in range(1, n) if diffs[i] > CUT_DIFF]
    bounds = [0] + cuts + [n]
    segs = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        uniq = [a] + [i for i in range(a + 1, b) if diffs[i] > DUP_DIFF]
        tu = ts[uniq]
        iv = np.diff(tu)
        segs.append({"first_frame": a, "last_frame": b - 1, "t_start_s": round(float(ts[a]), 4), "t_end_s": round(float(ts[b - 1]), 4),
                     "unique_content_frames": len(uniq),
                     "content_interval_median_ms": round(float(np.median(iv)) * 1000, 2) if len(iv) else None,
                     "content_interval_mean_ms": round(float(np.mean(iv)) * 1000, 2) if len(iv) else None,
                     "content_rate_fps": round(float((len(uniq) - 1) / (tu[-1] - tu[0])), 3) if len(uniq) > 2 else None,
                     "recording_frames_per_content_frame": dict(zip(*[x.tolist() for x in np.unique(np.diff(uniq), return_counts=True)])) if len(uniq) > 1 else {},
                     "unique_frames": uniq})
    rd = np.diff(ts)
    return {"recording_frames": n, "recording_duration_s": round(float(ts[-1]), 4),
            "recording_interval_ms": {"median": round(float(np.median(rd)) * 1000, 3), "min": round(float(rd.min()) * 1000, 3), "max": round(float(rd.max()) * 1000, 3)},
            "cut_frames": cuts, "segments": segs}


def world_of_overhead(g, px):
    M = np.array(g["image_to_world"][0]["matrix"]).reshape(3, 3)
    w = M @ np.array([px[0], px[1], 1.0])
    return (w[:2] / w[2]).tolist()


def calibrate(g, marks):
    lms = {l["id"]: l for l in g["landmarks"]}
    pts = []
    for p in marks["camera_correspondences"]["points"]:
        if "landmark_id" in p:
            w = world_of_overhead(g, lms[p["landmark_id"]]["px"])
            src = f"{p['landmark_id']} (overhead px via map.overhead.preview)"
        else:
            w = world_of_overhead(g, p["overhead_px"])
            src = "red dot centroid in stiga_se_fi_overhead via map.overhead.preview"
        pts.append({**p, "world_mm": [round(v, 2) for v in w], "world_source": src})
    W = np.array([p["world_mm"] for p in pts]); I = np.array([p["frame_px"] for p in pts], float)
    H, _ = cv2.findHomography(W, I, 0)
    res = np.linalg.norm(cv2.perspectiveTransform(W[None], H)[0] - I, axis=1)
    loo = []
    for i in range(len(pts)):
        m = np.ones(len(pts), bool); m[i] = False
        Hi, _ = cv2.findHomography(W[m], I[m], 0)
        loo.append(float(np.linalg.norm(cv2.perspectiveTransform(W[i:i + 1][None], Hi)[0][0] - I[i])))
    for p, r, l in zip(pts, res, loo):
        p["residual_px"] = round(float(r), 1); p["leave_one_out_px"] = round(l, 1)
        p["local_px_per_mm"] = round(px_per_mm(H, p["world_mm"]), 3)
    return H, pts, {"rms_px": round(float(np.sqrt(np.mean(res ** 2))), 2), "leave_one_out_rms_px": round(float(np.sqrt(np.mean(np.square(loo)))), 2),
                    "max_leave_one_out_px": round(max(loo), 1)}


def px_per_mm(H, w):
    w = np.array(w, float)
    a = cv2.perspectiveTransform(np.array([[w - [0.5, 0], w + [0.5, 0], w - [0, 0.5], w + [0, 0.5]]]), H)[0]
    return float((np.linalg.norm(a[1] - a[0]) + np.linalg.norm(a[3] - a[2])) / 2)


def to_world(H, px):
    return cv2.perspectiveTransform(np.array([[px]], float), np.linalg.inv(H))[0][0]


def path_projection(H, path):
    P = np.array(path["centreline"]["points_mm"], float)
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    return P, s, cv2.perspectiveTransform(P[None], H)[0]


def fixture_point(H, path, skate_px, unc_px):
    """Point of the projected slot centreline at the skate's image row (nearest crossing to the skate x)."""
    P, s, Q = path_projection(H, path)
    y = skate_px[1]
    cands = []
    for i in range(len(Q) - 1):
        y0, y1 = Q[i, 1], Q[i + 1, 1]
        if (y0 - y) * (y1 - y) <= 0 and y0 != y1:
            f = (y - y0) / (y1 - y0)
            cands.append((abs(Q[i, 0] + f * (Q[i + 1, 0] - Q[i, 0]) - skate_px[0]), i, f))
    if not cands:  # beyond the visible slot: clamp to the nearer end
        i = int(np.argmin(np.abs(Q[:, 1] - y)))
        return {"arc_mm": round(float(s[i]), 1), "world_mm": [round(v, 1) for v in P[i]], "clamped_to_slot_end": True,
                "arc_uncertainty_mm": None, "slot_length_mm": round(float(s[-1]), 1)}
    _, i, f = min(cands)
    w = P[i] + f * (P[i + 1] - P[i]); arc = s[i] + f * (s[i + 1] - s[i])
    dyds = (Q[i + 1, 1] - Q[i, 1]) / max(1e-9, s[i + 1] - s[i])  # image px per mm of slot travel along v
    return {"arc_mm": round(float(arc), 1), "world_mm": [round(float(v), 1) for v in w], "clamped_to_slot_end": False,
            "arc_uncertainty_mm": round(float(unc_px / max(abs(dyds), 1e-6)), 1), "slot_length_mm": round(float(s[-1]), 1)}


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    digest = sha256(src)
    if digest != SHA256:
        sys.exit(f"recording SHA-256 mismatch: {digest}")
    g = json.loads((REPO / "data" / "geometry.json").read_text())
    marks = json.loads((SHOT / "marks.json").read_text())
    frames, ts, diffs, cinfo = read_frames(src)
    tm = timing(ts, diffs)
    seg1 = next(sg for sg in tm["segments"] if sg["first_frame"] <= 167 <= sg["last_frame"])
    seg2 = next(sg for sg in tm["segments"] if sg["first_frame"] <= 282 <= sg["last_frame"])
    title = tm["segments"][0]
    t0 = float(ts[seg1["first_frame"]])
    content_ms = 1000.0 / seg1["content_rate_fps"]  # mean; the median (33 ms) hides the 2/3 recording-frame cadence

    def stamp(fr):
        u = seg1["unique_frames"]
        first = max(k for k in u if k <= fr)  # recording frame where this content frame first appears
        return {"recording_frame": fr, "content_first_recording_frame": first,
                "recording_time_s": round(float(ts[fr]), 4),
                "shot_time_s": round(float(ts[first]) - t0, 4),
                "content_frame_index": int(round((float(ts[first]) - t0) * 1000 / content_ms)),
                "time_uncertainty_s": 0.017}

    H, corr, fit = calibrate(g, marks)
    paths = {p["player_id"]: p for p in g["fixture_paths"]}
    figures = {}
    for pid, ms in marks["figure_marks"].items():
        if pid in ("note",):
            continue
        rows = []
        for m in ms:
            fp = fixture_point(H, paths[pid], m["skate_px"], m["uncertainty_px"])
            rows.append({**stamp(m["frame"]), "skate_px": m["skate_px"], "reading_uncertainty_px": m["uncertainty_px"], "state": m["state"], **fp})
        figures[pid] = {"fixture_path_id": f"path.{pid}", "observations": rows}
    pucks = []
    for m in marks["puck_marks"]["marks"]:
        row = {**stamp(m["frame"]), "state": m["state"]}
        if m["px"] is not None:
            w = to_world(H, m["px"]); k = px_per_mm(H, w)
            row.update({"image_px": m["px"], "reading_uncertainty_px": m["uncertainty_px"], "world_mm_blob_centre": [round(float(v), 1) for v in w],
                        "reading_uncertainty_mm": round(m["uncertainty_px"] / k, 1)})
            if "blob_size_px" in m and m["state"].startswith("sharp"):
                # scale check: the blob's horizontal image chord, mapped back to the ice plane (unforeshortened direction)
                hw = m["blob_size_px"][0] / 2
                a = cv2.perspectiveTransform(np.array([[[m["px"][0] - hw, m["px"][1]], [m["px"][0] + hw, m["px"][1]]]], float), np.linalg.inv(H))[0]
                row["apparent_diameter_mm"] = round(float(np.linalg.norm(a[1] - a[0])), 1)
        else:
            row.update({"image_px": None, "visible": False})
        pucks.append(row)

    t = lambda fr: stamp(fr)["shot_time_s"]  # noqa: E731
    events = [
        {"id": "prep.drag_1", "description": "W-RW drags the puck along its slot from the -y end-zone corner toward centre ice and back (W-C mirrors with a feint along its own slot)",
         "interval_s": [t(30), t(68)], "evidence": "puck marks 30-68; W-C marks 30, 47, 68"},
        {"id": "prep.drag_2", "description": "second drag of the puck toward centre ice by W-RW; W-C moves down to the near end of its slot",
         "interval_s": [t(68), t(102)], "evidence": "puck marks 68-102; W-C marks 68, 78, 95"},
        {"id": "pass.release", "description": "W-RW releases a cross-ice pass from its blade (rotating), puck leaves toward W-C",
         "interval_s": [t(102), t(107)], "exact_time": None, "evidence": "puck partly visible at the W-RW blade in 102, hidden in 104, in flight (236 px streak) in 107"},
        {"id": "contact.W-C_reception", "description": "puck reaches the W-C blade; W-C starts to travel up its slot (shovel). Exact first contact not observed (motion smear)",
         "interval_s": [t(107), t(111)], "exact_time": None, "evidence": "smear at the W-C blade in 109; replay frames 256-263"},
        {"id": "carry", "description": "W-C carries the puck on its blade up the slot toward the goal mouth; puck occluded by the blurred figure",
         "interval_s": [t(109), t(116)], "exact_time": None, "evidence": "W-C marks 109-116; replay frames 265-280 show the puck at the blade"},
        {"id": "goal_entry", "description": "puck enters goal.E past the goalie's right (+y; camera-right in the replay) side (corrected in iteration 22). Not visible in segment 1; time bounded by W-C reaching its slot end",
         "interval_s": [t(111), t(119)], "exact_time": None, "evidence": "replay frames 280-289 (puck smear into the net, then puck inside); segment 1 frame 116 W-C at slot end"},
        {"id": "return", "description": "W-C returns down its slot to the near end", "interval_s": [t(116), t(131)], "evidence": "W-C marks 116-131"},
    ]
    obs = {
        "schema": "shot-observation/1",
        "shot_id": "shot.21.shovel",
        "iteration": 21,
        "status": "observed (AI), not reviewed by the user; no motion fitted",
        "geometry_version": g["geometry_version"],
        "source": {
            "path": str(src.relative_to(REPO)) if src.is_relative_to(REPO) else str(src), "sha256": digest, "bytes": src.stat().st_size,
            "supplied_by": "user (chat upload, 2026-10-04)",
            "description": "iOS screen recording (ReplayKit) of a third-party video titled '#17 SHOVEL, difficulty 4/10' with a 'Brent Plast Bordhockey' watermark. The user states it shows one combination, first at full speed and then as a replay of the same shot.",
            "recorded_table": "A STIGA table with Play Off-style line and slot layout but different sponsor artwork (Loopia, Pirelli, Cramo, Hogia, Lindab, Pantamera, Corvara, Weber, Bygmax) than the reference variant 71-1145-01; not the user's own table. Teams: Sweden-style yellow vs Finland-style white figures (Finland skater no. 64 on W-RW here; the reference pack prints 64 on W-C).",
            "container": container_info(src), "decoder_container_fps": round(cinfo["container_fps"], 3)},
        "timing": {**{k: v for k, v in tm.items() if k != "segments"},
                   "segments": [{**{k: v for k, v in sg.items() if k != "unique_frames"}, "role": role} for sg, role in
                                zip(tm["segments"], ["title card over the first shot frame (no motion)", "segment 1: full-speed shot (calibrated camera, behind the W attack, looking at goal.E)", "segment 2: slow-motion replay from behind goal.E (not calibrated)"])],
                   "notes": [
                       "The container rate (~57.6-60 fps) is the screen recording, not the source camera. Content changes every 2 or 3 recording frames: the playback content of segment 1 runs at %.2f fps (%.1f ms per content frame)." % (seg1["content_rate_fps"], content_ms),
                       "Segment 1 is treated as real time on the user's statement ('full speed'); the source camera's own capture rate and exposure are unknown. Heavy motion blur shows a long exposure relative to the motion.",
                       "Shot time = recording time of the first recording frame showing a content frame minus the first frame of segment 1; a content frame can appear up to one recording interval (~17 ms) after it was presented.",
                       "Segment 2 is slow motion: the reception -> goal-entry interval spans about 10 replay content frames versus about 2 in segment 1 (slow-down roughly 3-10x; not determined). Its time base is NOT mapped to segment 1."]},
        "shot_window": {"smallest_useful_segment_s": [t(102), t(131)], "full_combination_s": [t(30), t(131)],
                        "active_figures": ["W-RW (puck carrier, passer)", "W-C (receiver, shooter)"],
                        "static_figures_observed": ["E-G", "E-LD", "E-RD"], "note": "Other figures are out of frame or not checked; the replay shows no other figure moving during the shot."},
        "camera_seg1": {"model": "planar homography world (ice plane z = 0, mm) -> recording frame px", "status": "traced",
                        "H_world_mm_to_frame_px": [[round(v, 9) for v in r] for r in H.tolist()], "fit": fit, "correspondences": corr,
                        "radial_distortion": "not modelled (pinhole + planar homography); residuals are consistent with the reading uncertainty plus table/edition differences",
                        "limitations": "Nine ice-plane points, all from the -y half and the E end except one +y faceoff dot (leave-one-out 24 px); the +y side and the W end are weakly constrained. Local scale 2.4-5.9 px/mm, so a 13 px leave-one-out error is about 2-5 mm on the ice. World positions additionally assume the recorded table shares the traced Play Off 21 layout (a different STIGA edition)."},
        "id_mapping": {
            "method": "slot topology: projected canonical slot centrelines (data/geometry.json fixture_paths) overlay the visible slots in frame 167 (validation/21-camera-calibration.png)",
            "figures": {"W-C": "white figure on the centre slot at the +y neutral-zone circle; the shooter", "W-RW": "white no. 64 on the curved -y winger slot; the passer",
                        "E-G": "yellow goalie in goal.E", "E-LD": "yellow figure on the straight slot ending behind goal.E on the -y side (static)",
                        "E-RD": "yellow no. 2 on the +y defender slot ending behind goal.E (static; reference pack E-RD is also no. 2)"},
            "team_side": "white attacks the yellow goalie's goal = W attacking goal.E (+x); image left = +y"},
        "figures": figures,
        "puck": {"diameter_mm_catalog_nominal": g["puck"]["diameter"]["value"], "observations": pucks,
                  "scale_check": "sharp puck frames 30 and 68: horizontal blob chord maps to 26.5-27.1 mm on the ice plane vs the approx. 25.4 mm catalog diameter (within ~7%); the faceoff circle E.neg_y chord maps to ~105 mm vs ~97-100 mm in the reference overhead. Consistent scale, not a measurement."},
        "events": events,
        "limitations": [
            "Recorded on a different table edition and figure pack than the user's; world positions assume the canonical Play Off 21 layout.",
            "No exact blade-puck contact time or point is claimed: release, reception and goal entry are intervals of one or more 40 ms content frames.",
            "Figure rotation is not measured (motion blur, unknown blade offset); only slot positions are observed.",
            "Fixture points use the skate row snapped to the projected slot centreline; the real fixture axis offset is unknown.",
            "Puck world points are blob centres, biased by up to half a puck thickness of parallax.",
            "Goal entry is only seen in the uncalibrated slow-motion replay."],
        "not_done": "no motion fitting, no puck simulation, no animation (iteration 22 onward)"}
    SHOT.mkdir(parents=True, exist_ok=True)
    (SHOT / "observations.json").write_text(json.dumps(obs, indent=1) + "\n")
    print("calibration", fit)
    for pid, f in figures.items():
        print(pid, [(o["recording_frame"], o["arc_mm"], o["arc_uncertainty_mm"]) for o in f["observations"]])
    print("puck", [(p["recording_frame"], p.get("world_mm_blob_centre"), p.get("apparent_diameter_mm")) for p in pucks])
    render_calibration(frames[167], H, g, corr)
    render_sheet(frames, H, obs, marks)


def render_calibration(fr, H, g, corr):
    img = fr.copy()
    for p in g["fixture_paths"]:
        q = cv2.perspectiveTransform(np.array(p["centreline"]["points_mm"], float)[None], H)[0]
        col = (255, 255, 0) if p["player_id"].startswith("W") else (0, 160, 255)
        cv2.polylines(img, [np.round(q).astype(np.int32)], False, col, 3, cv2.LINE_AA)
        j = len(q) // 2
        cv2.putText(img, p["player_id"], (int(q[j][0]) + 8, int(q[j][1])), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 3, cv2.LINE_AA)
    for c in corr:
        a = np.array(c["frame_px"]); b = cv2.perspectiveTransform(np.array([[c["world_mm"]]], float), H)[0][0]
        cv2.circle(img, tuple(np.round(a).astype(int)), 9, (255, 0, 255), 3)
        cv2.line(img, tuple(np.round(a).astype(int)), tuple(np.round(a + (b - a) * 3).astype(int)), (0, 0, 255), 3)
    im = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).crop((230, 0, 2330, 1180))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 2100, 64), fill=(255, 255, 255))
    d.text((10, 6), "21 - segment-1 camera (frame 167): canonical slot centrelines projected by the fitted homography (cyan W, orange E). "
           "Magenta = measured correspondence, red = residual x3.", fill=(0, 0, 0), font=FS)
    d.text((10, 34), "Recorded table: different STIGA edition; overlay checks slot topology for ID mapping, not dimensions. AI review.", fill=(0, 0, 0), font=FS)
    im.save(REPO / "validation" / "21-camera-calibration.png")


def render_sheet(frames, H, obs, marks):
    pm = {m["frame"]: m for m in marks["puck_marks"]["marks"]}
    fig = {pid: {m["frame"]: m for m in ms} for pid, ms in marks["figure_marks"].items() if pid != "note"}
    seg_t = {o["recording_frame"]: o for f in obs["figures"].values() for o in f["observations"]}
    seg_t.update({o["recording_frame"]: o for o in obs["puck"]["observations"]})
    stills = [
        (30, "PREPARATION: W-RW holds the puck at the -y corner; W-C up its slot", (1250, 150, 2330, 1180)),
        (68, "PREPARATION: second cycle, puck back at the W-RW blade", (1250, 150, 2330, 1180)),
        (102, "BEFORE PASS: W-C at the near end of its slot, puck at W-RW (partly hidden)", (700, 300, 2330, 1180)),
        (107, "PASS IN FLIGHT: release between 102 and 107", (700, 300, 2330, 1180)),
        (109, "BLADE CONTACT (interval): puck smear reaches the W-C blade", (500, 300, 1700, 1180)),
        (111, "CARRY: W-C travels up its slot; puck hidden", (500, 150, 1700, 1050)),
        (116, "AT GOAL MOUTH: W-C at its slot end; goal entry hidden from this camera", (500, 0, 1700, 900)),
        (282, "GOAL ENTRY (replay, slow motion): puck smear enters goal.E", (380, 300, 1700, 1180)),
        (289, "IN THE NET (replay): puck inside goal.E", (380, 300, 1700, 1180)),
        (131, "RETURN: W-C back down its slot; puck in the net", (500, 300, 2330, 1180)),
    ]
    tiles = []
    for fr, label, box in stills:
        img = frames[fr].copy()
        if fr in pm and pm[fr]["px"] is not None:
            p = tuple(int(v) for v in pm[fr]["px"]); r = int(max(14, pm[fr]["uncertainty_px"]))
            cv2.circle(img, p, r, (0, 0, 255), 4, cv2.LINE_AA)
        for pid, d in fig.items():
            if fr in d:
                p = tuple(int(v) for v in d[fr]["skate_px"])
                cv2.drawMarker(img, p, (255, 255, 0), cv2.MARKER_TILTED_CROSS, 34, 4)
                cv2.putText(img, pid, (p[0] + 20, p[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255, 255, 0), 4, cv2.LINE_AA)
        im = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).crop(box)
        im.thumbnail((640, 540), Image.LANCZOS)
        t = Image.new("RGB", (640, 540 + 64), "white"); t.paste(im, (0, 64))
        d = ImageDraw.Draw(t)
        if fr in seg_t:
            o = seg_t[fr]; ts = f"shot t = {o['shot_time_s']:.3f} s +/- 0.017 (content frame {o['content_frame_index']})"
        else:
            ts = "replay (segment 2): slow motion, time not mapped"
        d.text((6, 4), f"rec frame {fr}: {ts}", fill=(0, 0, 0), font=FS)
        d.text((6, 30), label, fill=(160, 0, 0), font=FS)
        tiles.append(t)
    cols = 5
    W, Hh = 640, 604
    sheet = Image.new("RGB", (cols * W, 90 + 2 * Hh), "white")
    d = ImageDraw.Draw(sheet)
    d.text((10, 8), "21 - '#17 Shovel' observations (references/shots/shovel-17-screen-recording.mov). Red circle = puck mark (radius = reading uncertainty); "
           "cyan cross = skate mark of the named figure.", fill=(0, 0, 0), font=FB)
    d.text((10, 48), "Segment 1 at full speed, 25 fps content; events are intervals, not exact contacts. Recorded table differs from the user's (artwork, pack). AI observation, not user-reviewed.",
           fill=(0, 0, 0), font=FS)
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * W, 90 + (i // cols) * Hh))
    sheet.save(REPO / "validation" / "21-contact-sheet.png")


if __name__ == "__main__":
    main()
