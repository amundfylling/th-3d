"""Clean plate of the E half by the temporal median of registered frames (figures move; the median removes them)."""
import sys
from pathlib import Path
import cv2, numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from nm26_common import Registrar, frames, reference_frame
t0, t1, step = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
HALF = (900, 360, 1900, 1000); x0, y0, x1, y1 = HALF
reg = Registrar(reference_frame("g2")); acc = []
for i, a in frames(t0, t1):
    if i % step: continue
    H, n = reg(a)
    if n < 100: continue
    acc.append(cv2.warpPerspective(a, np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.0]]) @ H, (x1 - x0, y1 - y0), flags=cv2.INTER_CUBIC))
print(len(acc))
cv2.imwrite(str(REPO / "out/abs/plate-g2.png"), np.median(np.stack(acc), 0).astype(np.uint8))
