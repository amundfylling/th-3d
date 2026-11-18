"""Real frame triplets (t-1, t, t+1; stab px) for training backgrounds, away from the goal windows.
    python3 scripts/synth/streak/extract-train-triplets.py [per_game=160]
A sample is kept where puck-track-synth-v2 sees a still puck (score >= 0.55, neighbours within 4 px): its top-face centre
(u, v) is the real label, or the puck is erased. Output out/streak/train/<game>_<frame>_{a,b,c}.jpg + <game>.jsonl."""
import json, random, sys
from multiprocessing import Pool
from pathlib import Path
import av, cv2, numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from nm26_common import CFG, DATA, T_ROI, W_STAB, H_STAB, Registrar, reference_frame, REPO, VIDEO, FPS
DEST = REPO / "out/streak/train"; N = int(sys.argv[1]) if len(sys.argv) > 1 else 160
GOALS = json.loads((DATA / "goal-labels.json").read_text())["labels"]

def pick(game):
    rows = json.loads((DATA / game / "puck-track-synth-v2.json").read_text())["rows"]; by = {r[0]: r for r in rows}
    gt = [g["goal_video_s"] * FPS for g in GOALS if g["game"] == game]
    ok = []
    for r in rows:
        a, c = by.get(r[0] - 1), by.get(r[0] + 1)
        if a and c and r[7] >= 0.55 and all(np.hypot(r[4] - q[4], r[5] - q[5]) <= 4 for q in (a, c)) and all(abs(r[0] - g) > 4 * FPS for g in gt):
            ok.append(r)
    random.Random(f"tr-{game}").shuffle(ok); out, used = [], []
    for r in ok:
        if all(abs(r[0] - u) > 20 for u in used): out.append(r); used.append(r[0])
        if len(out) >= N: break
    return out

def job(game):
    DEST.mkdir(parents=True, exist_ok=True)
    reg = Registrar(reference_frame(game)); meta = []
    c = av.open(str(VIDEO)); s = c.streams.video[0]; s.thread_type = "AUTO"
    for r in sorted(pick(game)):
        f = r[0]; c.seek(int(max(0.0, (f - 4) / FPS) / s.time_base), stream=s); got = {}
        for fr in c.decode(s):
            i = int(round(fr.time * FPS))
            if i >= f - 1: got[i] = fr.to_ndarray(format="bgr24")
            if i >= f + 1: break
        if len(got) < 3: continue
        for k, i in enumerate((f - 1, f, f + 1)):
            H, n = reg(got[i]); w = cv2.warpPerspective(got[i], T_ROI @ H, (W_STAB, H_STAB), flags=cv2.INTER_LINEAR)
            cv2.imwrite(str(DEST / f"{game}_{f}_{'abc'[k]}.jpg"), w, [cv2.IMWRITE_JPEG_QUALITY, 92])
        meta.append({"game": game, "frame": f, "uv": [r[4], r[5]]})
    (DEST / f"{game}.jsonl").write_text("\n".join(json.dumps(m) for m in meta) + "\n")
    return game, len(meta)

if __name__ == "__main__":
    with Pool(4) as p: print(p.map(job, list(CFG["games"])))
