"""Score figure tracks against the user's labels (docs/tracker-v3.md).

    python3 scripts/synth/tracker-v3-eval.py <name>=<file pattern with {game}> [...] [--out out/synth/v3/eval.json]
    python3 scripts/synth/tracker-v3-eval.py --lite      (also builds "v3-lite": the v3 decoder on the committed raw tracks)

Labels:
- skaters: data/games/nm26-semifinal/skater-labels.json (400 crops, 352 with feet and facing taps, 48 "can't see it");
  u from the feet tap, theta_deg relative to the team's home heading;
- goalies: data/games/nm26-semifinal/goalie-facing-labels.json (200 crops, facing taps; world heading).
A label counts for a track file when the file has a row at exactly the label's frame. Per file and label set: slot
error (mm along the slot), facing error (deg), gross slot error (over 30 mm: the tracker on the wrong spot), flips
(facing error over 90 deg), unknown (no value at the label frame). "test" = games 3, 5, 7, whose labels no model
trained on; "all" = every game.
Track files: raw (columns <fig>_u, <fig>_theta_deg[, <fig>_slot_dist_mm]) or cleaned (<fig>_u, <fig>_theta_deg, <fig>_src).
"""
import json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]; D = REPO / "data/games/nm26-semifinal"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tracker_v3_decode as dec  # noqa: E402

G = json.loads((REPO / "data/geometry.json").read_text())
SLOT_LEN = {f["player_id"]: float(np.linalg.norm(np.diff(np.array(f["centreline"]["points_mm"]), axis=0), axis=1).sum()) for f in G["fixture_paths"]}
GAMES = [f"g{k}" for k in range(1, 8)]; TEST = {"g3", "g5", "g7"}; HOME = {"W": 0.0, "E": 180.0}
SK = json.loads((D / "skater-labels.json").read_text())["labels"]
GL = json.loads((D / "goalie-facing-labels.json").read_text())["labels"]
GC = {c["id"]: c for c in json.loads((D / "goalie-facing-crops.json").read_text())["crops"]}


def load_track(path):
    T = json.loads(Path(path).read_text()); ci = {c: i for i, c in enumerate(T["columns"])}
    return {r[0]: r for r in T["rows"]}, ci


def lite(game):
    """v3 decoder on the committed raw readings (one candidate per frame; cost from the pivot's distance to the slot)."""
    T = json.loads((D / game / "figure-tracks.json").read_text()); C = T["columns"]; R = T["rows"]; ci = {c: i for i, c in enumerate(C)}
    fr = np.array([r[0] for r in R]); dense = np.array([r[1] for r in R]) > 0
    figs = [c[:-2] for c in C if c.endswith("_u")]; cols = ["frame", "dense"] + [f"{f}_{k}" for f in figs for k in ("u", "theta_deg", "src")]
    out = [fr.tolist(), dense.astype(int).tolist()]
    for f in figs:
        L = SLOT_LEN[f]; cands = []
        for r in R:
            sd = r[ci[f"{f}_slot_dist_mm"]] if f"{f}_slot_dist_mm" in ci else None
            c = dec.reading_cost(sd)
            cands.append([] if c is None else [(r[ci[f"{f}_u"]] * L, r[ci[f"{f}_theta_deg"]], c)])
        s, th, src, _ = dec.decode(fr, cands, dense)
        out += [[None if np.isnan(x) else round(float(x / L), 4) for x in s], [None if np.isnan(x) else round(float(x), 1) for x in th], src.tolist()]
    return {"description": "v3-lite: tracker_v3_decode on the committed raw readings (scripts/synth/tracker-v3-eval.py --lite). PROPOSED.",
            "columns": cols, "rows": [list(r) for r in zip(*out)]}


def score(pattern):
    sk, gk = [], []
    for g in GAMES:
        p = Path(str(pattern).format(game=g))
        if not p.exists(): continue
        rows, ci = load_track(p)
        for l in SK:
            if l["game"] != g or l["frame"] not in rows: continue
            r = rows[l["frame"]]; pid = l["pid"]; u = r[ci[f"{pid}_u"]]; th = r[ci[f"{pid}_theta_deg"]]
            src = r[ci[f"{pid}_src"]] if f"{pid}_src" in ci else 0
            e = {"id": l["id"], "game": g, "pid": pid, "verdict": l["verdict"], "unknown": u is None or src == 2}
            if l["verdict"] == "facing" and not e["unknown"]:
                e["slot_mm"] = abs(u - l["u"]) * SLOT_LEN[pid]; e["deg"] = abs(float(dec.circ(th - l["theta_deg"])))
            sk.append(e)
        for l in GL:
            c = GC[l["id"]]
            if l["game"] != g or c["frame"] not in rows or f"{l['end']}-G_theta_deg" not in ci: continue
            r = rows[c["frame"]]; pid = f"{l['end']}-G"; th = r[ci[f"{pid}_theta_deg"]]
            src = r[ci[f"{pid}_src"]] if f"{pid}_src" in ci else 0
            e = {"id": l["id"], "game": g, "pid": pid, "unknown": th is None or src == 2}
            if not e["unknown"]: e["deg"] = abs(float(dec.circ(HOME[l["end"]] + th - l["user_facing_deg"])))
            gk.append(e)
    return sk, gk


def summ(rows, slot=True):
    f = [r for r in rows if r.get("verdict", "facing") == "facing"]; k = [r for r in f if not r["unknown"]]
    if not f: return None
    d = np.array([r["deg"] for r in k]) if k else np.array([np.nan])
    o = {"n": len(f), "unknown": round(1 - len(k) / len(f), 3), "deg_median": round(float(np.median(d)), 1),
         "deg_p90": round(float(np.percentile(d, 90)), 1), "flipped": round(float(np.mean(d > 90)), 3)}
    if slot:
        m = np.array([r["slot_mm"] for r in k]) if k else np.array([np.nan])
        o.update({"slot_mm_median": round(float(np.median(m)), 1), "slot_mm_p90": round(float(np.percentile(m, 90)), 1),
                  "gross_over_30mm": round(float(np.mean(m > 30)), 3)})
    uns = [r for r in rows if r.get("verdict") == "unsure"]
    if uns: o["unsure_n"] = len(uns); o["unsure_reported_unknown"] = round(float(np.mean([r["unknown"] for r in uns])), 3)
    return o


def temporal(pattern):
    """Jumps between consecutive 30 fps frames (slot over 30 mm, rotation over 60 deg: faster than a figure moves, as
    docs/nm26-figure-tracks.md), and the share of unknown frames, over all skaters and all seven games."""
    js = jr = n = unk = tot = 0; jg = ng = 0
    for g in GAMES:
        p = Path(str(pattern).format(game=g))
        if not p.exists(): continue
        rows, ci = load_track(p); fr = sorted(rows)
        for f in [c[:-2] for c in ci if c.endswith("_u")]:
            src = ci.get(f"{f}_src"); u = ci[f"{f}_u"]; th = ci[f"{f}_theta_deg"]; L = SLOT_LEN[f]
            for a, b in zip(fr[:-1], fr[1:]):
                ra, rb = rows[a], rows[b]; tot += 1
                if ra[u] is None or (src and ra[src] == 2): unk += 1
                if b - a != 1 or ra[u] is None or rb[u] is None or (src and (ra[src] == 2 or rb[src] == 2)): continue
                if f.endswith("-G"):
                    ng += 1; jg += abs(float(dec.circ(ra[th] - rb[th]))) > 60; continue
                n += 1; js += abs(ra[u] - rb[u]) * L > 30; jr += abs(float(dec.circ(ra[th] - rb[th]))) > 60
    return {"steps": n, "slot_jumps": round(js / max(n, 1), 4), "rotation_jumps": round(jr / max(n, 1), 4),
            "goalie_rotation_jumps": round(jg / max(ng, 1), 4), "unknown": round(unk / max(tot, 1), 4)}


def presence_on_labels():
    """Skater model v3's presence on real frames: at each skater label frame, every candidate the localiser kept, split
    into right spots (the model's slot position within 30 mm of the user's feet tap) and wrong ones; and the first
    candidate at the "can't see it" labels."""
    right, wrong, uns = [], [], []
    for g in GAMES:
        p = REPO / f"out/synth/v3/obs-{g}-labels.json"
        if not p.exists(): continue
        O = {r[0]: r for r in json.loads(p.read_text())["rows"]}
        for l in SK:
            if l["game"] != g or l["frame"] not in O: continue
            cs = O[l["frame"]][2].get(l["pid"], [])
            if l["verdict"] != "facing":
                if cs: uns.append(cs[0][5])
                continue
            for c in cs: (right if abs(c[2] - l["u"]) * SLOT_LEN[l["pid"]] <= 30 else wrong).append(c[5])
    f = lambda v: {"n": len(v), "presence_over_0.5": round(float(np.mean(np.array(v) > 0.5)), 3) if v else None,
                   "presence_median": round(float(np.median(v)), 3) if v else None}
    return {"right_spot": f(right), "wrong_spot": f(wrong), "unsure_first_candidate": f(uns)}


def report(name, pattern, ids=None):
    sk, gk = score(pattern)
    if ids is not None: sk = [r for r in sk if r["id"] in ids["sk"]]; gk = [r for r in gk if r["id"] in ids["gk"]]
    return {"temporal": temporal(pattern), "skaters": {"all": summ(sk), "test": summ([r for r in sk if r["game"] in TEST]),
                        "by_figure_all": {p: summ([r for r in sk if r["pid"] == p]) for p in sorted({r["pid"] for r in sk})}},
            "goalies": {"all": summ(gk, False), "test": summ([r for r in gk if r["game"] in TEST], False)},
            "rows": {"skaters": sk, "goalies": gk}}


if __name__ == "__main__":
    A = sys.argv[1:]; outp = Path(A[A.index("--out") + 1]) if "--out" in A else REPO / "out/synth/v3/eval.json"
    specs = [a.split("=", 1) for a in A if "=" in a and not a.startswith("--")]
    if "--lite" in A and "--no-build" not in A:
        (REPO / "out/synth/v3").mkdir(parents=True, exist_ok=True)
        for g in GAMES: (REPO / f"out/synth/v3/lite-{g}.json").write_text(json.dumps(lite(g), separators=(",", ":")))
    if "--windows" in A:
        # the label windows (track-figures-v3.py obs/decode --labels): v2's rule (first colour peak) raw and after
        # smooth-tracks.py's clean-up, and v3, all on the same frames and the same model readings
        import importlib.util, shutil
        spec = importlib.util.spec_from_file_location("sm", REPO / "scripts/synth/smooth-tracks.py"); sm = importlib.util.module_from_spec(spec); spec.loader.exec_module(sm)
        W = REPO / "out/synth/v3/v2clean"; sm.D = W
        for g in GAMES:
            src = REPO / f"out/synth/v3/labels-v2raw-{g}.json"
            if src.exists(): (W / g).mkdir(parents=True, exist_ok=True); shutil.copy(src, W / g / "figure-tracks.json"); sm.smooth_game(g)
        specs = [["v2 rule, raw (windows)", str(REPO / "out/synth/v3/labels-v2raw-{game}.json")], ["v2 rule + clean-up (windows)", str(W / "{game}/figure-tracks-smooth.json")],
                 ["v3 (windows)", str(REPO / "out/synth/v3/labels-v3-{game}.json")]] + specs
    if "--lite" in A:
        specs = [["raw (committed)", str(D / "{game}/figure-tracks.json")], ["cleaned (committed)", str(D / "{game}/figure-tracks-smooth.json")],
                 ["v3-lite", str(REPO / "out/synth/v3/lite-{game}.json")]] + specs
    R = {n: report(n, p) for n, p in specs}
    # the label set every file covers (same frames for a fair comparison)
    common = None
    for n in R:
        ids = {"sk": {r["id"] for r in R[n]["rows"]["skaters"]}, "gk": {r["id"] for r in R[n]["rows"]["goalies"]}}
        common = ids if common is None else {k: common[k] & ids[k] for k in ids}
    C = {n: report(n, p, common) for n, p in specs}
    PR = presence_on_labels() if "--windows" in A else None
    if PR: print("presence on the label frames", PR)
    outp.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"per_file": {n: {k: v for k, v in r.items() if k != "rows"} for n, r in R.items()},
               "common_labels": {n: {k: v for k, v in r.items() if k != "rows"} for n, r in C.items()}, "presence_on_labels": PR,
               "rows": {n: r["rows"] for n, r in R.items()}}, open(outp, "w"), indent=1)
    for n, r in C.items():
        print(f"== {n} (common labels)", r["temporal"])
        for k in ("skaters", "goalies"):
            for s in ("all", "test"): print(f"  {k:8s} {s:4s}", r[k][s])
