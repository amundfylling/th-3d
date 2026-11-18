import sys, json
from pathlib import Path
import numpy as np, torch, cv2
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/abs"))
import fit, synth
FIT = json.loads((REPO / "out/abs/g2-goal3-fit.json").read_text()); tiles = []
def contour(fid, u, th):
    S = fit.synth.splat(synth.project(synth.world_points(fid, torch.tensor(u), torch.tensor(th), 3000)) - fit.HALFOFF, (640, 1000), 1.0)
    return (S.numpy() > 0.5).astype(np.uint8)
for fr in (28336, 28341, 28345, 28349, 28352, 28355):
    img = cv2.imread(str(REPO / f"out/abs/g2-goal3/{fr}.png"))
    for f, v in FIT[str(fr)].items():
        for (u, th, col) in ((v["u_v3"], v["theta_v3"], (0, 0, 255)), (v["u"], v["theta"], (0, 220, 0))):
            c, _ = cv2.findContours(contour(f, u, th), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE); cv2.drawContours(img, c, -1, col, 1)
    img = img[90:470, 0:620]; cv2.putText(img, f"frame {fr}  red=tracker v3  green=fit", (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2); cv2.putText(img, f"frame {fr}  red=tracker v3  green=fit", (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    tiles.append(img)
cv2.imwrite(str(REPO / "out/abs/contact-sheet.jpg"), np.vstack([np.hstack(tiles[:3]), np.hstack(tiles[3:])]), [cv2.IMWRITE_JPEG_QUALITY, 85])
