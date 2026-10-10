"""Clean the raw figure tracks: drop impossible jumps, fill short gaps, light smoothing.

    python3 scripts/synth/smooth-tracks.py [game ...]      (default: all seven)

Input: data/games/nm26-semifinal/<game>/figure-tracks.json (raw model output). Per figure, over time:
1. A skater reading is rejected when its pivot lies more than 15 mm from the slot (slot_dist_mm).
2. Robust outliers: a reading is rejected when its slot position is more than 25 mm, or its rotation more than 45
   degrees, from the median of the valid readings within +-0.3 s (at least 3 neighbours). A figure cannot move like
   that; these are the localiser locking onto the wrong spot for a frame or a few.
   The 25 mm / 45 degree limits are assumed (a wing moves up to about 1 m/s: 300 mm in 0.3 s, but not 25 mm away
   from where it was just before and just after).
3. Rejected readings are filled by linear interpolation in time (rotation along the shorter arc) when the gap is at
   most 1.0 s; longer gaps stay empty (null).
4. A 3-sample centred average on the dense (30 fps) windows.
Output: data/games/nm26-semifinal/<game>/figure-tracks-smooth.json: columns frame, dense, then per figure u,
theta_deg, src (0 = model reading kept, 1 = interpolated, 2 = unknown). Status: PROPOSED.
"""
import json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]; D = REPO / "data/games/nm26-semifinal"
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT_LEN = {f["player_id"]: float(np.linalg.norm(np.diff(np.array(f["centreline"]["points_mm"]), axis=0), axis=1).sum()) for f in G["fixture_paths"]}
WIN, DS_MM, DTH, GAP, SD = 0.3, 25.0, 45.0, 1.0, 15.0


def circ_diff(a, b): return (a - b + 180) % 360 - 180


def smooth_game(g):
    T = json.loads((D / g / "figure-tracks.json").read_text()); C = T["columns"]; R = np.array(T["rows"], float); ci = {c: i for i, c in enumerate(C)}
    t = R[:, 0] / 30.0; dense = R[:, 1] > 0; figs = [c[:-2] for c in C if c.endswith("_u")]
    cols = ["frame", "dense"] + [f"{f}_{k}" for f in figs for k in ("u", "theta_deg", "src")]
    out = [R[:, 0].astype(int).tolist(), R[:, 1].astype(int).tolist()]; stats = {}
    for f in figs:
        L = SLOT_LEN[f]; s = R[:, ci[f"{f}_u"]] * L; th = R[:, ci[f"{f}_theta_deg"]].copy()
        ok = np.ones(len(R), bool)
        if f"{f}_slot_dist_mm" in ci: ok &= R[:, ci[f"{f}_slot_dist_mm"]] <= SD
        lo = np.searchsorted(t, t - WIN); hi = np.searchsorted(t, t + WIN, side="right"); bad = ~ok.copy()
        for i in range(len(R)):
            if not ok[i]: continue
            nb = [j for j in range(lo[i], hi[i]) if j != i and ok[j]]
            if len(nb) < 3: continue
            ms = np.median(s[nb]); ref = th[nb[0]]; mth = (ref + np.median(circ_diff(th[nb], ref))) % 360
            if abs(s[i] - ms) > DS_MM or abs(circ_diff(th[i], mth)) > DTH: bad[i] = True
        good = np.where(~bad)[0]; src = np.zeros(len(R), int); s2 = s.copy(); th2 = th.copy()
        for i in np.where(bad)[0]:
            k = np.searchsorted(good, i)
            if 0 < k < len(good) and t[good[k]] - t[good[k - 1]] <= GAP:
                a, b = good[k - 1], good[k]; w = (t[i] - t[a]) / (t[b] - t[a])
                s2[i] = s[a] + w * (s[b] - s[a]); th2[i] = (th[a] + w * circ_diff(th[b], th[a])) % 360; src[i] = 1
            else:
                s2[i] = np.nan; th2[i] = np.nan; src[i] = 2
        # light smoothing on consecutive dense frames
        s3, th3 = s2.copy(), th2.copy()
        for i in range(1, len(R) - 1):
            if dense[i] and R[i + 1, 0] - R[i, 0] == 1 and R[i, 0] - R[i - 1, 0] == 1 and src[i - 1] < 2 and src[i] < 2 and src[i + 1] < 2:
                s3[i] = (s2[i - 1] + s2[i] + s2[i + 1]) / 3
                th3[i] = (th2[i] + (circ_diff(th2[i - 1], th2[i]) + circ_diff(th2[i + 1], th2[i])) / 3) % 360
        out += [[None if np.isnan(x) else round(float(x / L), 4) for x in s3], [None if np.isnan(x) else round(float(x), 1) for x in th3], src.tolist()]
        stats[f] = {"rejected": round(float(bad.mean()), 4), "interpolated": round(float((src == 1).mean()), 4), "unknown": round(float((src == 2).mean()), 4)}
    rows = [list(r) for r in zip(*out)]
    (D / g / "figure-tracks-smooth.json").write_text(json.dumps({"description": __doc__.split("\n\n")[0] + " (scripts/synth/smooth-tracks.py; "
        "src 0 = model reading kept, 1 = interpolated, 2 = unknown; u null when unknown). PROPOSED.", "columns": cols, "rows": rows,
        "stats": stats}, separators=(",", ":")) + "\n")
    return stats


if __name__ == "__main__":
    games = sys.argv[1:] or [f"g{k}" for k in range(1, 8)]
    for g in games:
        st = smooth_game(g); r = np.mean([v["rejected"] for v in st.values()]); u = np.mean([v["unknown"] for v in st.values()])
        print(g, "rejected %.1f%%, unknown after filling %.1f%%" % (100 * r, 100 * u), "| worst:", max(st, key=lambda k: st[k]["rejected"]), st[max(st, key=lambda k: st[k]["rejected"])])
