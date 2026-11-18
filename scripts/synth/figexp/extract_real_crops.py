"""Cut the real 200x200 skater crops of the user's feet/facing labels (all games) from the NM26 broadcast.

    python3 scripts/synth/figexp/extract_real_crops.py [out_dir]

Registers each label frame to its game's reference frame (nm26_common.Registrar) and warps to the crop origin in
skater-facing-crops.json. Writes <out>/<label id>.png and <out>/index.json. Hypothesis experiment, PROPOSED.
"""
import json, sys
from pathlib import Path
import cv2, numpy as np
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
from nm26_common import frames, Registrar, reference_frame, CFG  # noqa: E402
D = REPO / "data/games/nm26-semifinal"
out = Path(sys.argv[1] if len(sys.argv) > 1 else REPO / "out/synth/figexp/real"); out.mkdir(parents=True, exist_ok=True)
labels = [l for l in json.loads((D / "skater-labels.json").read_text())["labels"] if l["verdict"] == "facing"]
crops = {(c["player_id"], c["game"], c["frame"]): c for c in json.loads((D / "skater-facing-crops.json").read_text())["crops"]}
idx = []
for g in sorted({l["game"] for l in labels}):
    reg = Registrar(reference_frame(g))
    for l in sorted([l for l in labels if l["game"] == g], key=lambda l: l["frame"]):
        c = crops.get((l["pid"], g, l["frame"]))
        if c is None: continue
        t = l["frame"] / 30.0
        img = next((a for i, a in frames(t - 0.001, t + 0.1) if i == l["frame"]), None)
        if img is None: continue
        H, n = reg(img)
        x0, y0 = c["crop_origin_ref_px"]
        T = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.0]])
        cv2.imwrite(str(out / f"{l['id']}.png"), cv2.warpPerspective(img, T @ H, (200, 200), flags=cv2.INTER_LINEAR))
        idx.append({"id": l["id"], "pid": l["pid"], "game": g, "frame": l["frame"], "facing_deg": l["facing_deg"], "theta_deg": l["theta_deg"],
                    "u": l["u"], "crop_origin_ref_px": [x0, y0], "inliers": n})
    print(g, len(idx), flush=True)
(out / "index.json").write_text(json.dumps(idx))
