"""Track the goal windows with each detector's candidates and count goals with the puck seen in the last 0.2 s.
    python3 scripts/synth/streak/eval-goals-track.py     (needs out/streak/goal-cands.json from eval-streak.py goals)
Tracker = scripts/synth/track-puck.py's Viterbi (sigma 60 mm, d_max 350 mm/frame, switch 3, emission logit clipped [-4,5] + 1.0).
'streak' tracking adds a penalty when a candidate's streak axis (length >= 15 px) disagrees with the step direction."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from streaklib import *
SIGMA, DMAX, SWITCH, BIAS = 60.0, 350.0, 3.0, 1.0
H_TOP = np.array([[1, 0, -X0], [0, 1, -Y0], [0, 0, 1.0]]) @ Kc @ np.c_[Rc[:, 0], Rc[:, 1], Rc[:, 2] * TOP_MM + tc]
HI = np.linalg.inv(H_TOP)
HW = json.loads((REPO / "validation/12-hardware-report.json").read_text())["goal"]
GOALS = json.loads((REPO / "data/games/nm26-semifinal/goal-labels.json").read_text())["labels"]

def world(u, v):
    q = HI @ np.array([u, v, 1.0]); return q[:2] / q[2]

def cands(raw, f, min_s=0.05):
    out = []
    for u, v, s, e in raw.get(str(f), []):
        if s < min_s: continue
        L = np.hypot(e[2] - e[0], e[3] - e[1])
        ax = np.array([e[2] - e[0], e[3] - e[1]]) / L if L > 1e-3 else None
        out.append(dict(u=u, v=v, s=s, xy=world(u, v), L=L, ax=ax,
                        em=float(np.clip(np.log(s / (1 - s + 1e-6)), -4, 5) + BIAS)))
    return out

def viterbi(rows_in, streak):
    prevS, prev, prevI, back = np.array([0.0]), [], None, []
    for i, cs in rows_in:
        gap = 1 if prevI is None else max(1, i - prevI); prevI = i; n = len(cs)
        S, B = np.zeros(n + 1), np.zeros(n + 1, int)
        o = np.r_[prevS[0], prevS[1:] - SWITCH]; S[0], B[0] = o.max(), int(o.argmax())
        for j, c in enumerate(cs):
            o = [prevS[0] - SWITCH]
            for k, p in enumerate(prev):
                d = np.hypot(*(p["xy"] - c["xy"])) / gap
                cost = 0.5 * (d / SIGMA) ** 2 if d <= DMAX else 1e9
                if streak and d > 40 and c["ax"] is not None and c["L"] >= 15:
                    step = (c["xy"] - p["xy"]); step_px = np.array([c["u"] - p["u"], c["v"] - p["v"]])
                    cosang = abs(float(step_px @ c["ax"])) / (np.hypot(*step_px) + 1e-6)
                    cost += 3.0 * (1 - cosang)            # streak axis must be along the motion
                o.append(prevS[1 + k] - cost)
            k = int(np.argmax(o)); S[j + 1], B[j + 1] = o[k] + c["em"], k
        back.append(B); prevS = S; prev = cs
    st = int(np.argmax(prevS)); rows = []
    for (i, cs), B in zip(reversed(rows_in), reversed(back)):
        if st > 0: rows.append((i, cs[st - 1]))
        st = B[st]
    return rows[::-1]

def goal_dist(g, xy):
    end = g["scoring_end"]  # the scorer's team end; the goal attacked is the opposite end of the table
    for e in ("W", "E"):
        pass
    gx = {e: HW["placement_mm"][e] for e in ("W", "E")}
    return min(np.hypot(*(np.array(gx[e]) - xy)) for e in gx)

def main():
    C = json.loads((REPO / "out/streak/goal-cands.json").read_text()); res = {}
    base = {}
    for gl in GOALS:
        gid, game = gl["id"], gl["game"]; gf = C[gid]["goal_frame"]
        res[gid] = {"gf": gf}
        for name, tr_name in (("v1-committed", "puck-track-synth.json"), ("v1-committed-t2", "puck-track-synth-v2.json")):
            rows = json.loads((REPO / f"data/games/nm26-semifinal/{game}/{tr_name}").read_text())["rows"]
            seen = sorted(r[0] for r in rows if gf - 24 <= r[0] <= gf + 3)
            res[gid][name] = dict(last=max([s for s in seen if s <= gf], default=None), seen_last6=any(gf - 6 <= s <= gf for s in seen))
        for k in "PSL":
            for streak in ((False, True) if k != "P" else (False,)):
                name = k + ("+streakTrack" if streak else "")
                raw = C[gid]["cands"][k]
                rows_in = [(f, cands(raw, f)) for f in range(gf - 23, gf + 4)]
                rows_in = [(f, c) for f, c in rows_in if str(f) in raw]
                rows = viterbi(rows_in, streak)
                fr = [r[0] for r in rows]
                res[gid][name] = dict(last=max([f for f in fr if f <= gf], default=None), seen_last6=any(gf - 6 <= f <= gf for f in fr),
                    rows=[[f, round(c["xy"][0], 1), round(c["xy"][1], 1), round(c["s"], 3), round(c["L"], 1), round(c["u"], 1), round(c["v"], 1)] for f, c in rows])
    names = [n for n in res["g1-goal1"] if n != "gf"]
    print("goals with the puck seen in the last 0.2 s (gf-6..gf), of 25:")
    for n in names: print(f"  {n:18s}", sum(res[g][n]["seen_last6"] for g in res))
    (REPO / "out/streak/goal-eval.json").write_text(json.dumps(res))

if __name__ == "__main__": main()
