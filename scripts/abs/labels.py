"""Held-out check against the user's facing labels (skater-labels.json, goalie-facing-labels.json), game 2:
fit every figure of the labelled frame from the tracker-v3 start and compare v3 and fitted heading/slot position with the label."""
import sys, json
from pathlib import Path
import numpy as np, torch, cv2
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/abs")); sys.path.insert(0, str(REPO / "scripts"))
import fit, synth
from synth import tc
from nm26_common import Registrar, frames, reference_frame
D = tc.NM26
SK = [l for l in json.loads((D / "skater-labels.json").read_text())["labels"] if l["game"] == "g2" and l["verdict"] == "facing"]
GL = [l for l in json.loads((D / "goalie-facing-labels.json").read_text())["labels"] if l["game"] == "g2" and l["verdict"] == "facing"]
items = [{"fid": l["pid"], "frame": l["frame"], "head": l["facing_deg"], "u": l["u"], "kind": "skater"} for l in SK]
items += [{"fid": l["end"] + "-G", "frame": int(l["id"].split("-")[-1]), "head": l["user_facing_deg"], "u": None, "kind": "goalie"} for l in GL]
T = fit.load_v3(); reg = Registrar(reference_frame("g2")); X0, Y0 = synth.HALF[:2]
byframe = {}
for it in items: byframe.setdefault(it["frame"], []).append(it)
def cd(a, b): return (a - b + 180) % 360 - 180
res = []
for fr in sorted(byframe):
    if fr not in T: continue
    a = next(img for i, img in frames(fr / 30 - 0.7, fr / 30 + 0.2) if False) if False else None
    for i, im in frames((fr - 20) / 30, (fr + 1) / 30):
        H, n = reg(im)
        if i == fr: break
    w = cv2.warpPerspective(im, np.array([[1, 0, -X0], [0, 1, -Y0], [0, 0, 1.0]]) @ H, (1000, 640), flags=cv2.INTER_CUBIC)
    init = {f: (T[fr][f][0], T[fr][f][1]) for f in fit.FIGS}
    out, dt = fit.fit_frame(w, init)
    for it in byframe[fr]:
        o = out.get(it["fid"])
        if not o: continue
        home = tc.HOME[it["fid"][0]]
        r = {"fid": it["fid"], "frame": fr, "label_head": it["head"], "v3_head": (home + o["theta_v3"]) % 360, "fit_head": (home + o["theta"]) % 360,
             "label_u": it["u"], "v3_u": o["u_v3"], "fit_u": o["u"], "iou_v3": o["iou_v3"], "iou_fit": o["iou_fit"], "kind": it["kind"]}
        r["err_v3"] = cd(r["v3_head"], r["label_head"]); r["err_fit"] = cd(r["fit_head"], r["label_head"]); res.append(r)
    print(fr, len(res), f"{dt:.1f}s", flush=True)
    Path(REPO / "out/abs/labels-eval.json").write_text(json.dumps(res))
