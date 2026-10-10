"""Clean rink plates for the skater crops: per-pixel median of the sampled registered frames (skater-frames.py).

    /root/venvs/blender/bin/python scripts/synth/skater-plates.py

Writes out/synth/skaters/plate_all.png (all 280 frames) and plate_<game>.png (that game's 40 frames), in the ROI of
reference video px. Figures that stand still for long can leave faint remnants (as with the goalie plates).
"""
from pathlib import Path
import cv2, numpy as np
REPO = Path(__file__).resolve().parents[2]; D = REPO / "out/synth/skaters"
files = sorted((D / "frames").glob("g*_*.jpg")); games = sorted({f.stem.split("_")[0] for f in files})
A = np.stack([cv2.imread(str(f)) for f in files]); gi = np.array([f.stem.split("_")[0] for f in files])
cv2.imwrite(str(D / "plate_all.png"), np.median(A, 0).astype(np.uint8))
for g in games: cv2.imwrite(str(D / f"plate_{g}.png"), np.median(A[gi == g], 0).astype(np.uint8))
print(A.shape)
