"""Top-down animated replays of every NM26 goal, the matching broadcast clips, and a phone review page.

    python3 scripts/nm26-replays.py [goal_id ...] [--no-clips] [--page-only]      (npm run nm26:replays)

Re-runnable: it reads only the committed tracks, so after a new puck track or tracker version lands, run it again.

Goals: every goal in data/games/nm26-semifinal/timeline.json with a score-box time (40 of the 41; game 4's overtime
winner is never shown by the box and has no time, so it has no replay).
- The 25 goals the user marked (goal-labels.json, `goal_video_s`): window 8 s before to 1 s after the user's moment.
- The other 15 goals have only the box time, and the user's marks put the box 3.0-13.6 s after the goal (median
  7.9 s). Their window runs from 18 s to 1 s before the box change, so the goal is inside it; the moment is unknown.
Inputs per goal:
- figures: the selected tracks (scripts/nm26_tracks.py: <game>/figure-tracks-v3.json, or $NM26_FIGURE_TRACKS; model
  output, PROPOSED). Rows are every frame in the goal windows and 5 per second elsewhere; frames between 5-per-second rows (gap <= 0.5 s) are
  interpolated here and drawn hollow, like the smoother's interpolated readings (src 1). Unknown figures are left out.
- puck: the selected track (<game>/puck-track-synth.json, or $NM26_PUCK_TRACK; PROPOSED). Slow detections
  (scripts/nm26_tracks.py; the old track's 'disk') filled, moving ones as a ring; the old track's *_fill rows (gaps
  filled by its tracker) pale. Frames without a row show no puck.
- rink: data/geometry.json (inner board boundary, slot centrelines); goals from validation/12-hardware-report.json
  (preview cage, assumed). Blue and centre lines are nominal (x = +-120, 0 mm), as in figure-tracks-board.py.
Figure glyph: dot at the tracked pivot, arrow in the facing direction, and a short stick to the mold-frame blade point
(12, 33) mm used by nm26-figure-analysis.py. Not the mold footprint (the mesh cache is not in git).

Writes (all under validation/replays/):
- <id>.mp4: replay, 1044 x 624, 30 fps, H.264; <id>.jpg: poster (the goal moment, or the box change - 8 s);
- clips/<id>.mp4: the broadcast video over the same window, registered to game 1's reference frame (one homography
  per goal from ORB features, camera fixed within a clip) and cropped to the rink; clips/<id>.jpg poster;
- replays.json: the goal list with windows, sources and data coverage; index.html: the review page.
Broadcast clips need the video at out/dl/nm26.webm (config.json → video.url; PyAV + libdav1d).
"""
import json, math, statistics, sys
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nm26_tracks  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
D = REPO / "data/games/nm26-semifinal"
OUT = REPO / "validation/replays"
FPS = 30
BEFORE, AFTER = 8.0, 1.0            # labelled goals: window around the user's moment
UNL_FROM, UNL_TO = 18.0, 1.0        # unlabelled goals: window before the box change
args = [a for a in sys.argv[1:] if not a.startswith("--")]
NO_CLIPS = "--no-clips" in sys.argv; PAGE_ONLY = "--page-only" in sys.argv

TL = json.loads((D / "timeline.json").read_text())["games"]
CFG = json.loads((D / "config.json").read_text())
LABS = {r["id"]: r for r in json.loads((D / "goal-labels.json").read_text())["labels"]}
G = json.loads((REPO / "data/geometry.json").read_text())
HW = json.loads((REPO / "validation/12-hardware-report.json").read_text())["goal"]
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
ACC = {p: np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))] for p, P in SLOT.items()}
BOARD = np.array(G["board"]["inner_boundary"]["world"]["points_mm"], float)
HOME = {"W": 0.0, "E": 180.0}
BLADE = np.array([12.0, 33.0])
PUCK_R = 12.7  # catalog nominal 25.4 mm diameter
NAME = {"nygard": "Nygård", "fjermestad": "Fjermestad"}
KIT = {"W": "white/blue, left end", "E": "yellow, right end"}
LAG = statistics.median(l["box_lag_s"] for l in LABS.values())
LAG_RANGE = (min(l["box_lag_s"] for l in LABS.values()), max(l["box_lag_s"] for l in LABS.values()))


# ---------------------------------------------------------------- goal list
def goal_list():
    goals = []
    for g, v in TL.items():
        for k, x in enumerate(v["goals"]):
            gid = f"{g}-goal{k + 1}"
            end = "W" if x["scorer"] == v["left_end_player"] else "E"
            base = {"id": gid, "game": g, "n": k + 1, "scorer": x["scorer"], "end": end, "box_s": x["overlay_change_s"],
                    "in_regulation": x.get("in_regulation"), "game_time_s": x.get("game_time_s")}
            if x["overlay_change_s"] is None:
                base["skipped"] = "no score-box time (the box never shows this goal) and no user mark: no window"
                goals.append(base); continue
            lab = LABS.get(gid)
            if lab and lab.get("goal_video_s"):
                tg = lab["goal_video_s"]
                base.update(goal_s=tg, moment="user_marked", t0=tg - BEFORE, t1=tg + AFTER,
                            label={k2: lab.get(k2) for k2 in ("scorer", "assist", "family", "combination", "notes")})
            else:
                b = x["overlay_change_s"]
                base.update(goal_s=None, goal_estimate_s=round(b - LAG, 1), moment="unmarked",
                            t0=b - UNL_FROM, t1=b - UNL_TO, label=None)
            goals.append(base)
    return goals


# ---------------------------------------------------------------- tracks
def arc_point(pid, u):
    P, acc = SLOT[pid], ACC[pid]; s = u * acc[-1]
    return np.array([np.interp(s, acc, P[:, 0]), np.interp(s, acc, P[:, 1])])


_cache = {}


def tracks(game):
    if game in _cache: return _cache[game]
    T = nm26_tracks.load_figures(game)
    C = T["columns"]; R = T["rows"]; figs = [c[:-2] for c in C if c.endswith("_u")]
    fr = np.array([r[0] for r in R]); dense = np.array([r[C.index("dense")] for r in R])
    F = {}
    for f in figs:
        iu, it, isrc = C.index(f"{f}_u"), C.index(f"{f}_theta_deg"), C.index(f"{f}_src")
        u = np.array([np.nan if r[iu] is None else r[iu] for r in R], float)
        th = np.array([np.nan if r[it] is None else r[it] for r in R], float)
        src = np.array([2 if r[isrc] is None else r[isrc] for r in R])
        u[src == 2] = np.nan
        F[f] = (u, th, src)
    P = nm26_tracks.load_puck(game); pc = P["columns"]
    kind = lambda r, slow: "disk" if slow else ("smudge" if r[pc.index("kind")] in ("smudge", "det") else r[pc.index("kind")])
    puck = {int(r[pc.index("frame")]): (r[pc.index("x_mm")], r[pc.index("y_mm")], kind(r, s)) for r, s in zip(P["rows"], P["slow"])
            if r[pc.index("x_mm")] is not None}
    _cache[game] = (fr, dense, F, puck, figs)
    return _cache[game]


def figure_state(game, frame):
    """{fig: (x, y, heading_deg, style)}; style 0 = model reading, 1 = interpolated (smoother or here)."""
    fr, dense, F, _, figs = tracks(game)
    j = np.searchsorted(fr, frame)
    out = {}
    for f in figs:
        u, th, src = F[f]
        if j < len(fr) and fr[j] == frame:
            if np.isnan(u[j]): continue
            uu, tt, st = u[j], th[j], int(src[j])
        else:
            a, b = j - 1, j
            if a < 0 or b >= len(fr) or fr[b] - fr[a] > 0.5 * FPS or np.isnan(u[a]) or np.isnan(u[b]): continue
            w = (frame - fr[a]) / (fr[b] - fr[a])
            uu = u[a] + w * (u[b] - u[a])
            d = (th[b] - th[a] + 180) % 360 - 180; tt = th[a] + w * d; st = 1
        p = arc_point(f, uu)
        out[f] = (p[0], p[1], HOME[f[0]] + tt, st)
    return out


def coverage(gl):
    fr, dense, F, puck, figs = tracks(gl["game"])
    k0, k1 = int(round(gl["t0"] * FPS)), int(round(gl["t1"] * FPS))
    n = k1 - k0
    sel = (fr >= k0) & (fr < k1)
    dn = int(np.sum(dense[sel] == 1))
    pk = sum(1 for k in range(k0, k1) if k in puck)
    pkd = sum(1 for k in range(k0, k1) if k in puck and puck[k][2] == "disk")
    shown = [len(figure_state(gl["game"], k)) for k in range(k0, k1, 3)]
    return {"frames": n, "figure_rows_every_frame": round(dn / n, 3), "puck_seen": round(pk / n, 3),
            "puck_disk": round(pkd / n, 3), "figures_shown_mean": round(float(np.mean(shown)), 2)}


# ---------------------------------------------------------------- drawing
S = 1.2; HEAD = 60; RW, RH = int(870 * S), int(470 * S); W, H = RW, RH + HEAD
INK = (30, 30, 30); WCOL = (190, 90, 25); ECOL = (0, 160, 235)


def px(p): return (int(round((p[0] + 435) * S)), int(round((235 - p[1]) * S)) + HEAD)


def base_rink():
    im = np.full((H, W, 3), 255, np.uint8)
    cv2.fillPoly(im, [np.array([px(p) for p in BOARD], np.int32)], (250, 247, 243))
    for x, col in ((0, (70, 70, 215)), (-120, (205, 140, 70)), (120, (205, 140, 70))):
        cv2.line(im, px((x, -215)), px((x, 215)), col, 2)
    for pid, P in SLOT.items(): cv2.polylines(im, [np.array([px(p) for p in P], np.int32)], False, (214, 214, 214), 3, cv2.LINE_AA)
    for e, sgn in (("W", -1), ("E", 1)):
        gx, gy = HW["placement_mm"][e]; half = HW["mouth_width_per_goal_mm"][e] / 2; dep = HW["depth_per_goal_mm"][e]
        q = [(gx, gy + half), (gx + sgn * dep, gy + half), (gx + sgn * dep, gy - half), (gx, gy - half)]
        cv2.polylines(im, [np.array([px(p) for p in q], np.int32)], False, (90, 90, 90), 2, cv2.LINE_AA)
        cv2.line(im, px((gx, gy + half)), px((gx, gy - half)), (80, 80, 200), 1, cv2.LINE_AA)
    cv2.polylines(im, [np.array([px(p) for p in BOARD], np.int32)], True, (60, 60, 60), 3, cv2.LINE_AA)
    return im


_FONTS = {}


def font(scale, th):
    """Barlow (public/fonts) at about the size of OpenCV's Hershey font at `scale`; SemiBold for thick text. OpenCV's own
    fonts have no 'å' (Nygård)."""
    from PIL import ImageFont
    key = (round(scale * 30), th >= 2)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(str(REPO / "public/fonts" / ("Barlow-SemiBold.ttf" if key[1] else "Barlow-Medium.ttf")), key[0])
    return _FONTS[key]


def text_width(s, scale=0.55, th=1):
    return int(round(font(scale, th).getlength(s)))


def text(im, s, org, scale=0.55, col=INK, th=1):
    """Draw s with its baseline at org (as cv2.putText); col is BGR."""
    from PIL import Image, ImageDraw
    f = font(scale, th); x0, y0, x1, y1 = f.getbbox(s, anchor="ls")
    x0, y0 = max(0, org[0] + x0 - 1), max(0, org[1] + y0 - 1)
    x1, y1 = min(im.shape[1], org[0] + x1 + 1), min(im.shape[0], org[1] + y1 + 2)
    if x1 <= x0 or y1 <= y0:
        return
    tile = Image.fromarray(np.ascontiguousarray(im[y0:y1, x0:x1, ::-1]))
    ImageDraw.Draw(tile).text((org[0] - x0, org[1] - y0), s, font=f, fill=tuple(int(c) for c in col[::-1]), anchor="ls")
    im[y0:y1, x0:x1] = np.asarray(tile)[:, :, ::-1]


def draw_frame(base, gl, k, trail):
    im = base.copy()
    game = gl["game"]
    for f, (x, y, hd, st) in figure_state(game, k).items():
        col = WCOL if f[0] == "W" else ECOL
        a = math.radians(hd); c, s = math.cos(a), math.sin(a); p = np.array([x, y])
        gk = f.endswith("-G")
        if not gk:
            b = p + np.array([c * BLADE[0] - s * BLADE[1], s * BLADE[0] + c * BLADE[1]])
            cv2.line(im, px(p), px(b), col, 2, cv2.LINE_AA)
            bd = np.array([c, s]) * 9
            cv2.line(im, px(b - bd), px(b + bd), col, 4, cv2.LINE_AA)
        r = 10 if gk else 7
        if st == 0: cv2.circle(im, px(p), r, col, -1, cv2.LINE_AA)
        else: cv2.circle(im, px(p), r, col, 2, cv2.LINE_AA)
        cv2.arrowedLine(im, px(p), px(p + (34 if gk else 26) * np.array([c, s])), col, 2, cv2.LINE_AA, tipLength=0.35)
        lab = f.split("-")[1]
        text(im, lab, (px(p)[0] + 9, px(p)[1] - 9), 0.45, col, 1)
    if len(trail) > 1:
        for i in range(1, len(trail)):
            gap = trail[i][0] - trail[i - 1][0]
            if gap > 3 or math.dist(trail[i][1:3], trail[i - 1][1:3]) > 90 * gap: continue  # no line across a track switch
            g = int(200 - 140 * i / len(trail))
            cv2.line(im, px(trail[i - 1][1:3]), px(trail[i][1:3]), (g, g, g), 2, cv2.LINE_AA)
    _, _, _, puck, _ = tracks(game)
    if k in puck:
        x, y, kind = puck[k]; rr = int(round(PUCK_R * S))
        if kind == "disk": cv2.circle(im, px((x, y)), rr, (15, 15, 15), -1, cv2.LINE_AA)
        elif kind == "smudge": cv2.circle(im, px((x, y)), rr, (15, 15, 15), 2, cv2.LINE_AA)
        else: cv2.circle(im, px((x, y)), rr, (150, 150, 150), 2, cv2.LINE_AA)
    # header
    t = k / FPS
    sc = NAME[gl["scorer"]]
    text(im, f"Game {game[1:]}, goal {gl['n']}: {sc} ({KIT[gl['end']]})", (12, 24), 0.62, INK, 2)
    if gl["moment"] == "user_marked":
        dt = t - gl["goal_s"]
        clock = f"{dt:+.2f} s to the goal" if dt < 0 else ("GOAL" if dt < 0.35 else f"{dt:+.2f} s after the goal")
        lb = gl["label"]; fam = lb["family"] + (f", {lb['combination']}" if lb.get("combination") else "")
        text(im, f"{lb['scorer']} scores ({fam})", (12, 50), 0.52, (90, 90, 90), 1)
    else:
        clock = f"{t - gl['box_s']:+.2f} s to the score box"
        text(im, "goal moment not marked (box comes 3-14 s after the goal)", (12, 50), 0.52, (90, 90, 90), 1)
    tw = text_width(clock, 0.7, 2)
    text(im, clock, (W - tw - 12, 26), 0.7, (40, 40, 200) if clock == "GOAL" else INK, 2)
    text(im, "PROPOSED: model tracks", (W - 222, 50), 0.5, (110, 110, 110), 1)
    # progress bar
    y0 = H - 6; f0 = (t - gl["t0"]) / (gl["t1"] - gl["t0"])
    cv2.line(im, (0, y0), (W, y0), (225, 225, 225), 6)
    cv2.line(im, (0, y0), (int(W * f0), y0), (120, 120, 120), 6)
    if gl["goal_s"] is not None:
        gx = int(W * (gl["goal_s"] - gl["t0"]) / (gl["t1"] - gl["t0"])); cv2.line(im, (gx, y0 - 9), (gx, H), (40, 40, 200), 3)
    return im


def encoder(path, w, h, crf):
    c = av.open(str(path), "w", options={"movflags": "+faststart"})
    s = c.add_stream("libx264", rate=FPS); s.width, s.height = w, h; s.pix_fmt = "yuv420p"
    s.options = {"crf": str(crf), "preset": "medium"}; s.time_base = Fraction(1, FPS)
    return c, s


def write(c, s, img, n):
    fr = av.VideoFrame.from_ndarray(img, format="bgr24"); fr.pts = n
    for p in s.encode(fr): c.mux(p)


def close(c, s):
    for p in s.encode(): c.mux(p)
    c.close()


def render_replay(gl):
    base = base_rink(); _, _, _, puck, _ = tracks(gl["game"])
    k0, k1 = int(round(gl["t0"] * FPS)), int(round(gl["t1"] * FPS))
    pk = int(round((gl["goal_s"] if gl["goal_s"] is not None else gl["box_s"] - LAG) * FPS))
    c, s = encoder(OUT / f"{gl['id']}.mp4", W, H, 26)
    for n, k in enumerate(range(k0, k1)):
        trail = [(j, puck[j][0], puck[j][1]) for j in range(k - 15, k + 1) if j in puck]
        im = draw_frame(base, gl, k, trail)
        write(c, s, im, n)
        if k == pk: cv2.imwrite(str(OUT / f"{gl['id']}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 80])
    close(c, s)


# ---------------------------------------------------------------- broadcast clips
VIDEO = REPO / CFG["video"]["local_path"]
ROI = (160, 360, 1900, 1000); CW, CH = 1044, 384
_ref = {}


def frame_at(t):
    c = av.open(str(VIDEO)); s = c.streams.video[0]; s.thread_type = "AUTO"
    c.seek(int(max(0.0, t - 2.0) / s.time_base), stream=s)
    for fr in c.decode(s):
        if fr.time >= t - 1e-6:
            img = fr.to_ndarray(format="bgr24"); c.close(); return img
    c.close()


def ref_features():
    if not _ref:
        img = cv2.cvtColor(frame_at(CFG["games"]["g1"]["reference_frame_s"]), cv2.COLOR_BGR2GRAY)
        orb = cv2.ORB_create(4000); kp, de = orb.detectAndCompute(img, None)
        _ref.update(orb=orb, kp=kp, de=de)
    return _ref


def register(img):
    R = ref_features(); g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    kp, de = R["orb"].detectAndCompute(g, None)
    m = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(de, R["de"])
    if len(m) < 30: return None, len(m)
    a = np.float32([kp[x.queryIdx].pt for x in m]); b = np.float32([R["kp"][x.trainIdx].pt for x in m])
    Hm, inl = cv2.findHomography(a, b, cv2.RANSAC, 3.0)
    return Hm, int(inl.sum()) if inl is not None else 0


def render_clip(gl):
    (OUT / "clips").mkdir(parents=True, exist_ok=True)
    x0, y0, x1, y1 = ROI; T0 = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.0]])
    Hm, inl = register(frame_at(gl["t0"] + 0.5))
    ok = Hm is not None and inl >= 60
    gl["clip_registration_inliers"] = inl
    gl["clip_registered"] = bool(ok)
    k0, k1 = int(round(gl["t0"] * FPS)), int(round(gl["t1"] * FPS))
    pk = int(round((gl["goal_s"] if gl["goal_s"] is not None else gl["box_s"] - LAG) * FPS))
    c, s = encoder(OUT / "clips" / f"{gl['id']}.mp4", CW, CH, 30)
    cont = av.open(str(VIDEO)); vs = cont.streams.video[0]; vs.thread_type = "AUTO"
    cont.seek(int(max(0.0, gl["t0"] - 2.0) / vs.time_base), stream=vs)
    n = 0; last = None
    for fr in cont.decode(vs):
        k = int(round(fr.time * FPS))
        if k < k0: continue
        if k >= k1: break
        a = fr.to_ndarray(format="bgr24")
        img = cv2.warpPerspective(a, T0 @ Hm, (x1 - x0, y1 - y0)) if ok else a[y0:y1, x0:x1]
        img = cv2.resize(img, (CW, CH), interpolation=cv2.INTER_AREA)
        while n < k - k0:  # keep the clip frame-aligned with the replay if a frame is missing
            write(c, s, last if last is not None else img, n); n += 1
        write(c, s, img, n); n += 1; last = img
        if k == pk: cv2.imwrite(str(OUT / "clips" / f"{gl['id']}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 75])
    while n < k1 - k0 and last is not None:
        write(c, s, last, n); n += 1
    cont.close(); close(c, s)


# ---------------------------------------------------------------- main
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    goals = goal_list()
    idx_path = OUT / "replays.json"
    old = {g["id"]: g for g in json.loads(idx_path.read_text())["goals"]} if idx_path.exists() else {}
    for gl in goals:
        if "skipped" in gl: print(gl["id"], "SKIPPED:", gl["skipped"]); continue
        gl["coverage"] = coverage(gl)
        if PAGE_ONLY or (args and gl["id"] not in args):
            for k in ("clip_registered", "clip_registration_inliers"):
                if k in old.get(gl["id"], {}): gl[k] = old[gl["id"]][k]
            continue
        render_replay(gl)
        if not NO_CLIPS and VIDEO.exists(): render_clip(gl)
        elif gl["id"] in old:
            for k in ("clip_registered", "clip_registration_inliers"):
                if k in old[gl["id"]]: gl[k] = old[gl["id"]][k]
        print(gl["id"], gl["moment"], gl["coverage"], "clip inliers", gl.get("clip_registration_inliers"), flush=True)
    for gl in goals:
        for k in ("t0", "t1"):
            if k in gl: gl[k] = round(gl[k], 2)
    idx = {"description": "NM26 all-goals replays (scripts/nm26-replays.py). PROPOSED: drawn from model tracks, not user-checked.",
           "status": "PROPOSED",
           "sources": {"figures": f"data/games/nm26-semifinal/<game>/{nm26_tracks.FIGURE_TRACKS}",
                       "puck": f"data/games/nm26-semifinal/<game>/{nm26_tracks.PUCK_TRACK}",
                       "goal_moments": "data/games/nm26-semifinal/goal-labels.json (user marks)",
                       "goals": "data/games/nm26-semifinal/timeline.json"},
           "window": {"user_marked": f"{BEFORE} s before to {AFTER} s after the user's goal moment",
                      "unmarked": f"{UNL_FROM} s to {UNL_TO} s before the score-box change"},
           "box_lag_s_from_user_marks": {"median": LAG, "min": LAG_RANGE[0], "max": LAG_RANGE[1]},
           "fps": FPS, "goals": goals}
    idx_path.write_text(json.dumps(idx, indent=1, ensure_ascii=False) + "\n")
    page(goals)
    print("wrote", idx_path.relative_to(REPO), "and validation/replays/index.html")


def page(goals):
    rows = []
    for gl in goals:
        r = {"id": gl["id"], "game": int(gl["game"][1:]), "n": gl["n"], "scorer": NAME[gl["scorer"]], "end": gl["end"],
             "ot": gl.get("in_regulation") is False}
        if "skipped" in gl: r["skipped"] = gl["skipped"]
        else:
            r.update(moment=gl["moment"], dur=round(gl["t1"] - gl["t0"], 2),
                     goal_at=round(gl["goal_s"] - gl["t0"], 2) if gl["goal_s"] is not None else None,
                     box_at=round(gl["box_s"] - gl["t0"], 2), label=gl["label"], cov=gl["coverage"],
                     reg=gl.get("clip_registered"))
        rows.append(r)
    html = (REPO / "scripts/nm26-replays.template.html").read_text()
    html = html.replace("/*DATA*/[]", json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("/*LAG*/0", str(LAG))
    (OUT / "index.html").write_text(html)


if __name__ == "__main__":
    main()
