"""User tap review of the new NM26 tracks against the old ones (docs/nm26-new-tracks.md).

    /root/venvs/blender/bin/python scripts/nm26-tap-review.py page [--n-puck 70] [--n-fig 30]
    python3 scripts/nm26-tap-review.py eval <taps.json>

page: samples frames where the old and new tracks disagree, crops the registered broadcast frame around both candidate
positions (neither is drawn, so the tap is not steered), and writes
- validation/tap-review/items.json: per item the game, frame, crop box (stab px) and both tracks' positions (hidden from
  the page);
- validation/tap-review/index.html: the phone page (published as an artifact with a db: one doc per item in "taps").
Puck items (live play, all seven games; seed 26):
- both: both tracks have a position, more than 30 px apart (old blob centre moved up 8.8 px to the top-face centre,
  docs/synthetic-puck.md 2C);
- old_only / new_only: only one track has a position in that frame;
- goal: the last 2 s before a user-marked goal, any of the three cases above;
- agree: both within 10 px (control).
Figure items: a skater whose old cleaned track (figure-tracks-smooth.json) and v3 track (figure-tracks-v3.json) put its
pivot more than 30 mm apart; half in the 30 fps goal windows, half at the 5 fps rate. The user taps where the named
figure stands (between its skates); the pivot is under the left skate, so a tap is within about 10 mm of it.
eval: reads an export of the page's db (a list of {item, answer, x_stab, y_stab}) and scores both tracks per item: a
puck position is right within 15 mm of the tap (moved up 8.8 px from the visible centre to the top face, 12 mm plane), a figure within 25 mm (ice plane); "none" answers make a
track that placed something in the picture wrong. Writes validation/tap-review/results.json.
"""
import base64
import json
import random
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
D = REPO / "data/games/nm26-semifinal"
OUT = REPO / "validation/tap-review"
CFG = json.loads((D / "config.json").read_text())
TL = json.loads((D / "timeline.json").read_text())["games"]
LABS = json.loads((D / "goal-labels.json").read_text())["labels"]
CAM = json.loads((D / "camera-ref.json").read_text())
K, R, T = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
X0, Y0 = CFG["roi_px"][:2]
GEO = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in GEO["fixture_paths"]}
ACC = {p: np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))] for p, P in SLOT.items()}
SKATERS = ["W-LW", "E-LW", "W-RW", "E-RW", "W-C", "E-C", "W-LD", "E-LD", "W-RD", "E-RD"]
GAMES = [f"g{k}" for k in range(1, 8)]
BLOB_DV = 8.8  # stab px: old blob centre lies this far below the top-face centre (docs/synthetic-puck.md 2C)
PUCK_Z, PUCK_OK_MM, FIG_OK_MM = 12.0, 15.0, 25.0
# the page asks for "the centre of the puck": a tap marks the visible puck, whose centre lies 8.8 px below the top-face
# centre that both tracks are scored in (docs/synthetic-puck.md 2C, puck-blob-offset.py); eval moves puck taps up by it
TAP_TO_TOP_PX = 8.8
ROLE = {"LW": "left wing", "RW": "right wing", "C": "centre", "LD": "left defence", "RD": "right defence"}
KIT = {"W": "white/blue", "E": "yellow"}


def to_stab(P, z):
    P = np.atleast_2d(np.asarray(P, float)); X = np.c_[P[:, :2], np.full(len(P), z)] @ R.T + T; q = X @ K.T
    return q[:, :2] / q[:, 2:] - [X0, Y0]


def from_stab(q, z):
    H = K @ np.c_[R[:, 0], R[:, 1], R[:, 2] * z + T]
    q = np.atleast_2d(np.asarray(q, float)) + [X0, Y0]
    w = np.c_[q, np.ones(len(q))] @ np.linalg.inv(H).T
    return w[:, :2] / w[:, 2:]


def pivot(pid, u):
    P, acc = SLOT[pid], ACC[pid]; s = u * acc[-1]
    return np.array([np.interp(s, acc, P[:, 0]), np.interp(s, acc, P[:, 1])])


def live(g, t):
    if not any(a <= t < b for a, b in TL[g]["live_play_s"]):
        return False
    return not any(x["overlay_change_s"] and x["overlay_change_s"] - 10 <= t < x["overlay_change_s"] for x in TL[g]["goals"])


def puck_rows(g, name):
    t = json.loads((D / g / name).read_text()); c = t["columns"]
    return {r[0]: (r[c.index("u_stab_px")], r[c.index("v_stab_px")]) for r in t["rows"] if r[c.index("x_mm")] is not None}


def fig_rows(g, name):
    t = json.loads((D / g / name).read_text()); c = t["columns"]
    return {r[0]: dict(zip(c, r)) for r in t["rows"]}


def sample(n_puck, n_fig, rng):
    items = []
    goal_frames = {}
    for lab in LABS:
        if lab.get("goal_video_s"):
            f1 = int(round(lab["goal_video_s"] * 30)); goal_frames.setdefault(lab["game"], set()).update(range(f1 - 60, f1 + 1))
    cases = {"both": [], "old_only": [], "new_only": [], "goal": [], "agree": []}
    for g in GAMES:
        old, new = puck_rows(g, "puck-track.json"), puck_rows(g, "puck-track-synth.json")
        for f in sorted(set(old) | set(new)):
            if not live(g, f / 30):
                continue
            o = None if f not in old else (old[f][0], old[f][1] - BLOB_DV); n = new.get(f)
            if o and n:
                d = float(np.hypot(o[0] - n[0], o[1] - n[1]))
                case = "both" if d > 30 else ("agree" if d < 10 else None)
            else:
                case = "old_only" if o else "new_only"
            if case is None:
                continue
            key = "goal" if f in goal_frames.get(g, ()) and case != "agree" else case
            cases[key].append((g, f, o, n))
    quota = {"both": 0.32, "old_only": 0.2, "new_only": 0.2, "goal": 0.21, "agree": 0.07}
    for case, share in quota.items():
        k = round(n_puck * share)
        pool = cases[case]
        # spread over games: shuffle, then take frames at least 3 s apart
        rng.shuffle(pool); took = []
        for g, f, o, n in pool:
            if len(took) >= k:
                break
            if any(g == g2 and abs(f - f2) < 90 for g2, f2, *_ in took):
                continue
            took.append((g, f, o, n))
        for g, f, o, n in took:
            items.append({"kind": "puck", "case": case, "game": g, "frame": f, "old_stab": o, "new_stab": n})
    fcand = {"window": [], "rate5": []}
    for g in GAMES:
        old, new = fig_rows(g, "figure-tracks-smooth.json"), fig_rows(g, "figure-tracks-v3.json")
        for f, a in old.items():
            b = new.get(f)
            if b is None or not live(g, f / 30):
                continue
            for p in SKATERS:
                ua, ub = a[f"{p}_u"], b[f"{p}_u"]
                if ua is None and ub is None:
                    continue
                d = None if ua is None or ub is None else abs(ua - ub) * ACC[p][-1]
                if d is not None and d <= 30:
                    continue
                fcand["window" if a["dense"] else "rate5"].append((g, f, p, ua, a[f"{p}_theta_deg"], ub, b[f"{p}_theta_deg"]))
    for key, k in (("window", n_fig - n_fig // 2), ("rate5", n_fig // 2)):
        pool = fcand[key]; rng.shuffle(pool); took = []
        for c in pool:
            if len(took) >= k:
                break
            if any(c[0] == t[0] and abs(c[1] - t[1]) < 90 for t in took):
                continue
            took.append(c)
        for g, f, p, ua, ta, ub, tb in took:
            st = lambda u: None if u is None else [round(float(v), 1) for v in to_stab(pivot(p, u), 0.0)[0]]
            items.append({"kind": "figure", "case": key, "game": g, "frame": f, "figure": p,
                          "old_stab": st(ua), "new_stab": st(ub), "old_u": ua, "new_u": ub, "old_theta_deg": ta, "new_theta_deg": tb})
    return items


def build_page(n_puck, n_fig):
    import cv2
    from nm26_common import H_STAB, T_ROI, W_STAB, Registrar, frames, reference_frame
    rng = random.Random(26)
    items = sample(n_puck, n_fig, rng)
    items.sort(key=lambda it: it["frame"])
    reg = Registrar(reference_frame("g1"))
    OUT.mkdir(parents=True, exist_ok=True)
    kept = []
    for it in items:
        img = next((a for i, a in frames(it["frame"] / 30 - 0.001, it["frame"] / 30 + 0.03)), None)
        if img is None:
            continue
        reg.prev = np.eye(3); H, n = reg(img)
        if n < 25:
            print("skip (registration)", it["game"], it["frame"]); continue
        st = cv2.warpPerspective(img, T_ROI @ H, (W_STAB, H_STAB))
        pts = [p for p in (it["old_stab"], it["new_stab"]) if p]
        lo, hi = np.min(pts, 0), np.max(pts, 0)
        cw = int(np.clip(hi[0] - lo[0] + 300, 420, 760)); ch = int(np.clip(hi[1] - lo[1] + 200, 260, 420))
        cx, cy = (lo + hi) / 2
        x0 = int(np.clip(cx - cw / 2, 0, W_STAB - cw)); y0 = int(np.clip(cy - ch / 2, 0, H_STAB - ch))
        crop = st[y0:y0 + ch, x0:x0 + cw]
        ok, jpg = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 82])
        n_ = len(kept) + 1
        it.update(id=f"t{n_:03d}", crop_stab=[x0, y0, cw, ch], registration_inliers=int(n), video_t_s=round(it["frame"] / 30, 3))
        it["img"] = "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode()
        if it["kind"] == "figure":
            p = it["figure"]
            it["prompt"] = f"Tap where the {KIT[p[0]]} {ROLE[p.split('-')[1]]} stands (between its skates)."
            sl = to_stab(SLOT[p], 0.0) - [x0, y0]
            it["slot_px"] = [[round(float(a), 1), round(float(b), 1)] for a, b in sl]
        else:
            it["prompt"] = "Tap the centre of the puck."
        kept.append(it)
        print(it["id"], it["kind"], it["case"], it["game"], it["frame"], flush=True)
    hidden = [{k: v for k, v in it.items() if k not in ("img", "slot_px", "prompt")} for it in kept]
    (OUT / "items.json").write_text(json.dumps({"description": __doc__.split("\n\n")[0] + " Sampled items with both tracks' positions (stab px).",
                                                "status": "PROPOSED (sampling); the user's taps are the truth once exported", "items": hidden}, indent=1) + "\n")
    page_items = [{"id": it["id"], "kind": it["kind"], "game": int(it["game"][1:]), "t": it["video_t_s"], "w": it["crop_stab"][2],
                   "h": it["crop_stab"][3], "crop": it["crop_stab"][:2], "img": it["img"], "prompt": it["prompt"], "slot": it.get("slot_px")} for it in kept]
    html = (REPO / "scripts/nm26-tap-review.template.html").read_text().replace("/*ITEMS*/[]", json.dumps(page_items, separators=(",", ":")))
    (OUT / "index.html").write_text(html)
    print("items", len(kept), "page MB", round(len(html) / 1e6, 2))


def evaluate(taps_path):
    items = {it["id"]: it for it in json.loads((OUT / "items.json").read_text())["items"]}
    taps = json.loads(Path(taps_path).read_text())
    taps = taps.get("taps", taps) if isinstance(taps, dict) else taps
    rows = []
    for tp in taps:
        it = items.get(tp["item"])
        if not it or tp.get("answer") == "unsure":
            continue
        x0, y0 = it["crop_stab"][:2]
        z = PUCK_Z if it["kind"] == "puck" else 0.0
        lim = PUCK_OK_MM if it["kind"] == "puck" else FIG_OK_MM
        r = {"item": it["id"], "kind": it["kind"], "case": it["case"], "game": it["game"], "frame": it["frame"], "answer": tp["answer"]}
        if tp["answer"] == "tap":
            up = TAP_TO_TOP_PX if it["kind"] == "puck" else 0.0
            w = from_stab([tp["x_stab"], tp["y_stab"] - up], z)[0]
            for k in ("old", "new"):
                p = it[f"{k}_stab"]
                if p is None:
                    r[k] = "missing"; continue
                d = float(np.linalg.norm(from_stab(p, z)[0] - w)); r[f"{k}_err_mm"] = round(d, 1)
                r[k] = "right" if d <= lim else "wrong"
        else:  # "none": nothing to tap in the picture
            for k in ("old", "new"):
                r[k] = "missing_ok" if it[f"{k}_stab"] is None else "wrong"
        rows.append(r)
    def rate(sel, k):
        n = len(sel); ok = sum(1 for r in sel if r[k] in ("right", "missing_ok"))
        return {"n": n, "right": ok, "share": round(ok / n, 3) if n else None}
    summ = {}
    for kind in ("puck", "figure"):
        sel = [r for r in rows if r["kind"] == kind]
        summ[kind] = {"old": rate(sel, "old"), "new": rate(sel, "new"),
                      "by_case": {c: {"old": rate([r for r in sel if r["case"] == c], "old"), "new": rate([r for r in sel if r["case"] == c], "new")}
                                  for c in sorted({r["case"] for r in sel})}}
    (OUT / "results.json").write_text(json.dumps({"description": "User taps scored against both tracks (scripts/nm26-tap-review.py eval).",
                                                  "thresholds_mm": {"puck": PUCK_OK_MM, "figure": FIG_OK_MM}, "summary": summ, "items": rows}, indent=1) + "\n")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "page":
        arg = lambda n, d: int(a[a.index(n) + 1]) if n in a else d
        build_page(arg("--n-puck", 70), arg("--n-fig", 30))
    elif a and a[0] == "eval":
        evaluate(a[1])
    else:
        raise SystemExit(__doc__)
