"""Figure tracker v3 for the NM26 broadcast (docs/tracker-v3.md). PROPOSED.

    /root/venvs/blender/bin/python scripts/synth/track-figures-v3.py plates
    /root/venvs/blender/bin/python scripts/synth/track-figures-v3.py obs <game> [--labels] [--model out/synth/skater-pose-v3.pt]
    /root/venvs/blender/bin/python scripts/synth/track-figures-v3.py decode <game> [--labels]

What changes against track-figures.py (v2):
- Candidates instead of one guess. The kit-colour localiser (same mask and scoring as v2) keeps the two best separate
  peaks along each skater's slot (at least 40 mm apart; the second only if it scores at least 30% of the first), and the
  skater model reads a crop at each.
- A presence check. Skater model v3 (train-skater-v3.py) has a fifth output: is this skater's pivot in the crop at all?
  It was trained on hard-example renders (render-skater-hard.py): crops centred 45-200 mm off the skater along its slot
  (the localiser on noise or on a neighbour), crops where the skater is hidden, wings at the boards and crowded scenes.
- A temporal prior (tracker_v3_decode.py): per figure, the path through the candidates that a figure can actually move
  along (speed limits, frames may be dropped at a cost), then front/back flips undone along that path; dropped frames
  are interpolated up to 1 s, longer gaps stay unknown. This replaces the separate clean-up (smooth-tracks.py).
- Goalies: model C is unchanged (its readings are copied from the v2 raw tracks at the same frames); only the
  rotation decoding (flips) is applied.

Steps:
- plates: registers the 280 label frames (skater-facing-crops.json, 40 per game) to the reference frame and writes the
  rink plates (out/synth/skaters/plate_<game>.png), as skater-frames.py + skater-plates.py (which need frames.json).
- obs: per frame, the candidates and the model readings -> out/synth/v3/obs-<game>[-labels].json. Frames: the v2 raw
  track's frames (all of them: 5 fps plus every frame around each goal), or with --labels every 6th frame (5 fps, the rate of most of each v2 track) within +-0.8 s
  of each skater label frame (the evaluation windows).
- decode: v3 tracks. Full game -> data/games/nm26-semifinal/<game>/figure-tracks-v3.json (same columns as
  figure-tracks-smooth.json: u, theta_deg, src per figure; plus <fig>_conf); --labels -> out/synth/v3/labels-{v2,v3}-<game>.json
  (v2 = the v2 rule on the same readings: the strongest colour peak, then smooth-tracks.py's clean-up).
"""
import importlib.util, json, sys, time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "scripts/synth"))
import tracker_v3_decode as dec  # noqa: E402

DATA = REPO / "data/games/nm26-semifinal"; V3 = REPO / "out/synth/v3"; V3.mkdir(parents=True, exist_ok=True)
A = sys.argv[1:]; CMD = A[0] if A else ""
def arg(n, d): return A[A.index(n) + 1] if n in A else d
ROI = (160, 360, 1900, 1000); x0, y0, x1, y1 = ROI
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
SLOT_LEN = {p: float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum()) for p, P in SLOT.items()}
ORDER = ["W-LW", "E-LW", "W-RW", "E-RW", "W-C", "E-C", "W-LD", "E-LD", "W-RD", "E-RD"]
SEP_MM, SECOND_FRAC, NCAND = 40.0, 0.3, 2  # assumed


def label_frames():
    C = json.loads((DATA / "skater-facing-crops.json").read_text())["crops"]; out = {}
    for c in C: out.setdefault(c["game"], set()).add(c["frame"])
    return {g: sorted(v) for g, v in out.items()}


def registered(frame_list):
    """Yield (frame, registered ROI image) for the given frame indices (each frame registered on its own)."""
    import cv2
    from nm26_common import Registrar, frames, reference_frame
    reg = Registrar(reference_frame("g1")); T0 = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.0]])
    want = sorted(set(frame_list)); segs = []
    for f in want:
        if segs and f - segs[-1][1] <= 90: segs[-1][1] = f
        else: segs.append([f, f])
    wset = set(want)
    for a, b in segs:
        for i, img in frames(a / 30.0 - 0.02, b / 30.0 + 0.02):
            if i in wset:
                H, _ = reg(img); yield i, cv2.warpPerspective(img, T0 @ H, (x1 - x0, y1 - y0))


if CMD == "plates":
    import cv2
    d = REPO / "out/synth/skaters/frames"; d.mkdir(parents=True, exist_ok=True)
    for g, fl in label_frames().items():
        for i, img in registered(fl): cv2.imwrite(str(d / f"{g}_{i}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 93])
        print(g, len(fl), flush=True)
    import runpy; runpy.run_path(str(REPO / "scripts/synth/skater-plates.py"), run_name="__main__")
    sys.exit()


class Localiser:
    """Kit-colour localiser along each skater's slot. variant "v2": exactly track-figures.py (pixel difference from the
    rink plate over 60, team colour, best slot position). variant "v3": the difference is taken against the plate's
    local range (per channel, min and max over 5 x 5 px), so a registration error of a pixel or two at a high-contrast
    edge (white letters on the near-board adverts) no longer counts as a figure. Only below the ice (the near board and
    its adverts): on the ice the local range swallows white kit next to white ice (tried 2026-10-10: lock-ons on the
    label frames 2.3% -> 5.7%), and at the far board white kit in front of white board parts (all off-ice: W-LW 2.8% ->
    8.3%; for the yellow kit everywhere: E-LW 8.3% -> 13.9%), so elsewhere the plain difference stays. The colour
    rules are v2's. On the label frames this variant finds the same peaks as v2 (2.3% lock-ons both).
    peaks() returns up to NCAND separate peaks (at least SEP_MM apart; the second at least SECOND_FRAC of the first)."""

    def __init__(self, plate, variant="v3"):
        import cv2
        self.cv2, self.plate, self.variant = cv2, plate.astype(np.int16), variant
        k = np.ones((5, 5), np.uint8)
        self.pmin = cv2.erode(plate, k).astype(np.int16); self.pmax = cv2.dilate(plate, k).astype(np.int16)
        # the ice (config ice_polygon_stab_px, stab px = reference px - roi_px origin), in this ROI's px
        CFG = json.loads((DATA / "config.json").read_text()); ox, oy = CFG["roi_px"][0] - x0, CFG["roi_px"][1] - y0
        self.ice = np.zeros(plate.shape[:2], np.uint8)
        cv2.fillPoly(self.ice, [np.array([[x + ox, y + oy] for x, y in CFG["ice_polygon_stab_px"]], np.int32)], 1); self.ice = self.ice.astype(bool)
        # the near board and the adverts below it: image rows below the ice in each column
        self.near = np.cumsum(self.ice[::-1], 0)[::-1] == 0
        self.near &= np.cumsum(self.ice, 0) > 0
        CAM = json.loads((DATA / "camera-ref.json").read_text()); K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])

        def proj3(P):
            X = np.atleast_2d(P) @ R.T + t; q = X @ K.T; return q[:, :2] / q[:, 2:] - [x0, y0]

        def resample(P, step=3.0):
            seg = np.linalg.norm(np.diff(P, axis=0), axis=1); acc = np.r_[0, np.cumsum(seg)]; s = np.arange(0, acc[-1], step)
            return np.c_[np.interp(s, acc, P[:, 0]), np.interp(s, acc, P[:, 1])], s

        ring = np.array([(r * np.cos(a), r * np.sin(a), z) for r in (0, 8) for a in np.linspace(0, 2 * np.pi, 8, endpoint=False) for z in (8, 18, 28, 38)])
        self.CAND = {}
        for pid in ORDER:  # identical to track-figures.py (v2)
            pts, s_mm = resample(SLOT[pid]); q = np.stack([proj3(ring + [p[0], p[1], 0]) for p in pts])
            self.CAND[pid] = (pts, np.round(q).astype(int), proj3(np.c_[pts, np.zeros(len(pts))]), s_mm)

    def team_mask(self, img, end):
        cv2 = self.cv2; im = img.astype(np.int16)
        if self.variant == "v2":
            d = np.abs(im - self.plate).sum(-1) > 60
        else:  # below the ice (near board, adverts): the plate's local range; elsewhere v2's plain difference
            d = np.abs(im - self.plate).sum(-1) > 60
            off = self.near; d[off] = ((np.maximum(0, self.pmin - im) + np.maximum(0, im - self.pmax)).sum(-1) > 60)[off]
        h = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); H, Sa, V = h[..., 0], h[..., 1], h[..., 2]
        col = ((H >= 15) & (H <= 35) & (Sa > 110) & (V > 110)) if end == "E" else (((H >= 100) & (H <= 130) & (Sa > 100)) | ((Sa < 45) & (V > 185)))
        return cv2.blur((d & col).astype(np.float32), (3, 3))

    def set_image(self, img):
        self.masks = {e: self.team_mask(img, e) for e in "WE"}; self.shape = img.shape

    def profile(self, pid):
        m = self.masks[pid[0]]; pts, q, foot, s_mm = self.CAND[pid]; hh, ww = m.shape
        ok = (q[..., 0] >= 0) & (q[..., 0] < ww) & (q[..., 1] >= 0) & (q[..., 1] < hh)
        return np.where(ok, m[np.clip(q[..., 1], 0, hh - 1), np.clip(q[..., 0], 0, ww - 1)], 0).sum(1)

    def peaks(self, pid, n=None):
        sc = self.profile(pid); pts, q, foot, s_mm = self.CAND[pid]; out, rest = [], sc.copy()
        for k in range(n or NCAND):
            i = int(np.argmax(rest))
            if k and (rest[i] <= 0 or rest[i] < SECOND_FRAC * out[0][1]): break
            out.append((i, float(sc[i]))); rest[np.abs(s_mm - s_mm[i]) < SEP_MM] = -1
        return [(foot[i], float(s_mm[i]), v) for i, v in out]


if CMD == "loc-eval":
    # model-free: the localiser's peaks on the 280 label frames (out/synth/skaters/frames, written by "plates") against
    # the user's feet taps. lock-on = the first peak more than 30 mm from the feet along the slot.
    import cv2
    L = json.loads((DATA / "skater-labels.json").read_text())["labels"]; res = {}
    for variant in ("v2", "v3"):
        rows = []
        for g in sorted({l["game"] for l in L}):
            loc = Localiser(cv2.imread(str(REPO / f"out/synth/skaters/plate_{g}.png")), variant)
            for f in sorted({l["frame"] for l in L if l["game"] == g}):
                loc.set_image(cv2.imread(str(REPO / f"out/synth/skaters/frames/{g}_{f}.jpg")))
                for l in [l for l in L if l["game"] == g and l["frame"] == f and l["verdict"] == "facing"]:
                    pk = loc.peaks(l["pid"], 3); su = l["u"] * SLOT_LEN[l["pid"]]; d = [abs(p[1] - su) for p in pk]
                    rows.append({"id": l["id"], "pid": l["pid"], "d1": d[0], "dbest2": min(d[:2]), "n": len(pk)})
        d1 = np.array([r["d1"] for r in rows]); d2 = np.array([r["dbest2"] for r in rows])
        res[variant] = {"n": len(rows), "first_peak_median_mm": round(float(np.median(d1)), 1), "lock_on_first_over_30mm": round(float(np.mean(d1 > 30)), 3),
                        "lock_on_both_over_30mm": round(float(np.mean(d2 > 30)), 3), "two_peaks": round(float(np.mean([r["n"] > 1 for r in rows])), 3),
                        "lock_on_by_skater": {p: round(float(np.mean([r["d1"] > 30 for r in rows if r["pid"] == p])), 3) for p in ORDER}}
        print(variant, res[variant], flush=True)
    (V3 / "loc-eval.json").write_text(json.dumps(res, indent=1)); sys.exit()


def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    argv = sys.argv; sys.argv = [argv[0], "0"]; spec.loader.exec_module(m); sys.argv = argv; return m


if CMD == "obs":
    import cv2, torch
    game = A[1]; LAB = "--labels" in A; torch.set_num_threads(int(arg("--threads", 4)))
    ts = load_mod("ts", REPO / "scripts/synth/train-skater-pose.py"); tv = load_mod("tv", REPO / "scripts/synth/train-skater-v3.py")
    net = tv.model(False); net.load_state_dict(torch.load(REPO / arg("--model", "out/synth/skater-pose-v3.pt"))); net.eval()
    loc = Localiser(cv2.imread(str(REPO / f"out/synth/skaters/plate_{game}.png")), arg("--loc", "v3"))

    if LAB:
        fl = sorted({f + 6 * k for f in label_frames()[game] for k in range(-4, 5)}); dense_set = set()  # 5 fps, as most of each game
    else:
        RAW = json.loads((DATA / game / "figure-tracks.json").read_text()); fl = [r[0] for r in RAW["rows"]]
        dense_set = {r[0] for r in RAW["rows"] if r[1]}
    dest = V3 / f"obs-{game}{'-labels' if LAB else ''}.json"; part = dest.with_suffix(".partial.json")
    rows = json.loads(part.read_text()) if part.exists() else []; done = {r[0] for r in rows}; t_start = time.time()
    if "--max-frames" in A: fl = fl[:int(arg("--max-frames", 0))]
    for i, img in registered([f for f in fl if f not in done]):
        crops, meta = [], []; loc.set_image(img)
        for pid in ORDER:
            for rank, (foot, s_mm, sc) in enumerate(loc.peaks(pid)):
                cx = min(max(int(round(foot[0] - 100)), 0), img.shape[1] - 200); cy = min(max(int(round(foot[1] - 136)), 0), img.shape[0] - 200)
                crops.append(ts.to_tensor(img[cy:cy + 200, cx:cx + 200], pid)); meta.append((pid, rank, s_mm, sc, (cx + x0, cy + y0)))
        with torch.no_grad(): P = net(torch.stack(crops)).numpy()
        row = [i, int(i in dense_set), {}]
        for (pid, rank, s_mm, sc, o), p in zip(meta, P):
            u, d = ts.pivot_to_u(pid, ts.net_to_px(p[:2]), o)
            row[2].setdefault(pid, []).append([round(s_mm, 1), round(sc, 1), round(float(u), 4), round(float(np.degrees(np.arctan2(p[2], p[3])) % 360), 1),
                                               round(float(d), 1), round(float(1 / (1 + np.exp(-p[4]))), 3)])
        rows.append(row)
        if len(rows) % 200 == 0:
            part.write_text(json.dumps(rows, separators=(",", ":"))); print(game, len(rows), "/", len(fl), round(time.time() - t_start), "s", flush=True)
    rows.sort(key=lambda r: r[0])
    dest.write_text(json.dumps({"description": "Tracker v3 observations (track-figures-v3.py obs): per frame [frame, dense, {skater: "
        "[[colour-peak slot position mm, colour score, model u, model theta_deg, pivot distance from the slot mm, presence], ...]}], "
        "candidates in colour-score order (the first is v2's guess).", "rows": rows}, separators=(",", ":")))
    if part.exists(): part.unlink()
    print(game, "obs done", len(rows), round(time.time() - t_start), "s")
    sys.exit()


def write_tracks(path, desc, frames, dense, per_fig, conf=None):
    cols = ["frame", "dense"]; out = [list(map(int, frames)), list(map(int, dense))]
    for f, (u, th, src) in per_fig.items():
        cols += [f"{f}_u", f"{f}_theta_deg", f"{f}_src"]
        out += [[None if not np.isfinite(x) else round(float(x), 4) for x in u], [None if not np.isfinite(x) else round(float(x), 1) for x in th], list(map(int, src))]
    Path(path).write_text(json.dumps({"description": desc, "columns": cols, "rows": [list(r) for r in zip(*out)]}, separators=(",", ":")) + "\n")


if CMD == "decode":
    game = A[1]; LAB = "--labels" in A
    O = json.loads((V3 / f"obs-{game}{'-labels' if LAB else ''}.json").read_text())["rows"]
    fr = np.array([r[0] for r in O]); dense = np.array([r[1] for r in O]) > 0; per = {}; raw_v2 = {}
    for pid in ORDER:
        L = SLOT_LEN[pid]; cands = []
        for r in O:
            cs = []
            for rank, c in enumerate(r[2].get(pid, [])):
                cost = dec.reading_cost(c[4], c[5], rank, c[1])
                if cost is not None: cs.append((c[2] * L, c[3], cost))
            cands.append(cs)
        s, th, src, _ = dec.decode(fr, cands, dense); per[pid] = (s / L, th, src)
        raw_v2[pid] = [(r[2][pid][0][2], r[2][pid][0][3], r[2][pid][0][4]) if r[2].get(pid) else (None, None, 99) for r in O]
    # goalies: model C readings from the v2 raw track at the same frames; v3 adds only the flip decoding
    RAW = json.loads((DATA / game / "figure-tracks.json").read_text()); ci = {c: i for i, c in enumerate(RAW["columns"])}
    rr = {r[0]: r for r in RAW["rows"]}
    for g in ("W-G", "E-G"):
        cands = [[(rr[f][ci[f"{g}_u"]] * SLOT_LEN[g], rr[f][ci[f"{g}_theta_deg"]], 0.0)] if f in rr else [] for f in fr]
        s, th, src, _ = dec.decode(fr, cands, dense); per[g] = (s / SLOT_LEN[g], th, src)
    if LAB:
        write_tracks(V3 / f"labels-v3-{game}.json", "tracker v3 on the label windows", fr, dense, per)
        cols = ["frame", "dense"] + [f"{p}_{c}" for p in ORDER for c in ("u", "theta_deg", "slot_dist_mm")]
        rows = [[int(f), int(d)] + sum([list(raw_v2[p][k]) for p in ORDER], []) for k, (f, d) in enumerate(zip(fr, dense))]
        Path(V3 / f"labels-v2raw-{game}.json").write_text(json.dumps({"columns": cols, "rows": rows}))
    else:
        write_tracks(DATA / game / "figure-tracks-v3.json", "Figure tracks v3 (scripts/synth/track-figures-v3.py; docs/tracker-v3.md): "
                     "u = slot position 0-1, theta_deg relative to the team's home heading, src 0 = reading kept, 1 = interpolated, "
                     "2 = unknown. PROPOSED.", fr, dense, per)
    print(game, "decoded", len(fr))
