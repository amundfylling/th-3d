"""Hypothesis xg-shot-model, step 1: extract every observable shot attempt from the seven NM26 games
(puck-track-synth-v2.json), label it goal / no goal from the 40 goal moments in combo-labels.json, and add features.
Usage: python3 scripts/hypotheses/xg_dataset.py [outdir]   (needs numpy, shapely)
Writes <outdir>/attempts.csv and <outdir>/dataset-summary.json."""
import sys, json, csv
import numpy as np
from shapely.geometry import LineString, Point
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from xg_common import *

OUT = __import__("pathlib").Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/project-files/hypotheses/xg-shot-model")
# detector parameters (relaxed vs passes-synth-v1 which finds only 3 of 40 goals; chosen a priori, not tuned on outcomes)
VMIN, DMAX, YTOL, GAP, MERGE = 500.0, 300.0, 40.0, 0.3, 1.0
MATCH_PRE, MATCH_POST = 0.5, 1.0
SLOTS = {f["player_id"]: LineString(f["centreline"]["points_mm"]) for f in GEO["fixture_paths"]}
FAM = {}
for l in json.load(open(D / "goal-labels.json"))["labels"]:
    FAM[l["id"]] = l["family"]
for gid, c in GOALS.items():
    FAM.setdefault(gid, (c.get("predictions") or {}).get("vote"))


def goalie_y(g, end, t, cache={}):
    key = (g, end)
    if key not in cache:
        f = json.load(open(D / f"g{g}/figure-tracks-v3.json"))
        a = np.array(f["rows"], float)
        cache[key] = (a[:, 0] / FPS, a[:, f["columns"].index(f"{end}-G_u")])
    tt, uu = cache[key]
    u = float(np.interp(t, tt, uu))
    L = SLOTS[f"{end}-G"]
    return L.interpolate(min(max(u, 0), 1) * L.length).y


def episodes(r, goal):
    t, x, y = r[:, 1], r[:, 2], r[:, 3]
    cand = []
    for i in range(1, len(r) - 1):
        if r[i + 1, 0] - r[i - 1, 0] > 6:
            continue
        dt = t[i + 1] - t[i - 1]
        vt = (depth(x[i - 1], goal) - depth(x[i + 1], goal)) / dt
        di = depth(x[i], goal)
        if vt < VMIN or di > DMAX:
            continue
        vy = (y[i + 1] - y[i - 1]) / dt
        yc = y[i] + vy * (max(di, 0) / vt)
        if abs(yc - GY[goal]) <= HALF[goal] + YTOL:
            cand.append((i, vt, yc, vy))
    eps = []
    for c in cand:
        if eps and t[c[0]] - t[eps[-1][-1][0]] <= GAP:
            eps[-1].append(c)
        else:
            eps.append([c])
    merged = []
    for e in eps:
        if merged and t[e[0][0]] - t[merged[-1][-1][0]] <= MERGE:
            merged[-1].extend(e)
        else:
            merged.append(list(e))
    return merged


def pass_context(ev, attacker, t_rel):
    """passes by the attacking team before t_rel: consecutive chain length and time since the last one."""
    prior = [e for e in ev if e["t_release_s"] < t_rel - 0.05]
    n, last = 0, None
    for e in reversed(prior):
        end = e["from"][0] if e["from"] else None
        if e["kind"] == "pass" and end == attacker:
            n += 1
            last = last if last is not None else e["t_reception_s"]
        elif e["kind"] in ("carry",) and end == attacker:
            continue
        else:
            break
    return n, (None if last is None else t_rel - last)


rows, summary = [], {"per_game": {}}
for g in range(1, 8):
    r = load_track(g)
    ev = json.load(open(D / f"g{g}/passes-synth-v1.json"))["events"]
    t = r[:, 1]
    win = CFG["games"][f"g{g}"]["video_window_s"]
    goals_g = {gid: c for gid, c in GOALS.items() if c["game"] == f"g{g}"}
    attempts = []
    for goal in "WE":
        attacker = "E" if goal == "W" else "W"
        for e in episodes(r, goal):
            i0, i1 = e[0][0], e[-1][0]
            T0, T1 = t[i0], t[i1]
            # release: walk back from first candidate to last slow (<300 mm/s) detection within 1.0 s
            k = i0
            while k > 0 and T0 - t[k - 1] <= 1.0:
                v = np.hypot(*(r[k, 2:4] - r[k - 1, 2:4])) / ((r[k, 0] - r[k - 1, 0]) / FPS)
                if v < 300:
                    break
                k -= 1
            ox, oy, ot = r[k, 2], r[k, 3], t[k]
            speeds = [c[1] for c in e]
            ycross = float(np.mean([c[2] for c in e[-3:]]))
            vy_l = float(np.mean([c[3] for c in e[-3:]]))
            ang = abs(np.degrees(np.arctan2(vy_l, float(np.mean(speeds[-3:])))))
            role = min(((SLOTS[s].distance(Point(ox, oy)), s) for s in SLOTS if s.startswith(attacker) and not s.endswith("-G")))[1]
            npass, since = pass_context(ev, attacker, ot)
            gy = goalie_y(g, goal, T1)
            attempts.append(dict(game=g, goal_end=goal, attacker_end=attacker, player=team_of_end(g, attacker), role=role.split("-")[1],
                                 t_release=round(ot, 2), t_last=round(T1, 2), n_det=len(e), origin_x=round(ox, 1), origin_y=round(oy, 1),
                                 origin_depth=round(depth(ox, goal), 1), speed_max=round(max(speeds)), speed_last=round(speeds[-1]),
                                 y_cross=round(ycross, 1), aim_miss_mm=round(abs(ycross - GY[goal]), 1), aim_miss_rel=round(abs(ycross - GY[goal]) / HALF[goal], 2),
                                 angle_deg=round(float(ang), 1), end_depth=round(depth(r[i1, 2], goal), 1),
                                 goalie_y=round(gy, 1), goalie_gap_mm=round(abs(gy - ycross), 1), passes_before=npass,
                                 since_pass_s=None if since is None else round(since, 2), is_goal=0, goal_id="", family=""))
    # match goals one-to-one: nearest episode whose window contains the goal moment, same goal end
    used = set()
    for gid, c in goals_g.items():
        goal = "W" if c["scoring_end"] == "E" else "E"
        T = c["goal_moment_s"]
        best = None
        for j, a in enumerate(attempts):
            if a["goal_end"] != goal or j in used:
                continue
            if a["t_release"] - MATCH_PRE <= T <= a["t_last"] + MATCH_POST:
                dd = abs(T - a["t_last"])
                if best is None or dd < best[0]:
                    best = (dd, j)
        if best:
            used.add(best[1]); a = attempts[best[1]]
            a["is_goal"], a["goal_id"], a["family"] = 1, gid, FAM.get(gid) or ""
    rows += attempts
    summary["per_game"][f"g{g}"] = dict(attempts=len(attempts), goals_labelled=len(goals_g), goals_matched=len(used))

cols = list(rows[0].keys())
with open(OUT / "attempts.csv", "w", newline="") as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)
summary.update(n_attempts=len(rows), n_goals_total=len(GOALS), n_goals_matched=sum(a["is_goal"] for a in rows),
               params=dict(VMIN=VMIN, DMAX=DMAX, YTOL=YTOL, GAP=GAP, MERGE=MERGE, MATCH_PRE=MATCH_PRE, MATCH_POST=MATCH_POST))
json.dump(summary, open(OUT / "dataset-summary.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
