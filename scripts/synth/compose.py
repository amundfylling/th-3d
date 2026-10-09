"""Composite a synthetic RGBA goalie crop onto a real clean plate, with augmentation (docs/synthetic-goalie-pilot.md)."""
import random
from pathlib import Path

import cv2
import numpy as np

PLATES = Path(__file__).resolve().parents[2] / "out/synth/plates"


def load_plates():
    P = {"W": [], "E": []}
    for f in sorted(PLATES.glob("plate_*.png")):
        end = "W" if "_W" in f.stem else "E"
        P[end].append(cv2.imread(str(f)).astype(np.float32))
    return P


def compose(rgba, plate, rnd: random.Random):
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    fg = rgba[..., :3].astype(np.float32)
    # figure colour/brightness to the broadcast look: contrast and saturation up a little, random gain
    fg = np.clip((fg - 128) * rnd.uniform(1.0, 1.35) + 128 + rnd.uniform(-15, 15), 0, 255)
    img = plate * (1 - a) + fg * a
    # table drift and calibration error: small shift and scale
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), rnd.uniform(-1.5, 1.5), rnd.uniform(0.96, 1.04)); M[:, 2] += [rnd.uniform(-6, 6), rnd.uniform(-6, 6)]
    img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)
    # camera softness, colour, noise, compression
    img = cv2.GaussianBlur(img, (0, 0), rnd.uniform(0.4, 1.3))
    hsv = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 0] = (hsv[..., 0] + rnd.uniform(-4, 4)) % 180; hsv[..., 1] *= rnd.uniform(0.8, 1.25); hsv[..., 2] *= rnd.uniform(0.85, 1.15)
    img = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    img += np.random.default_rng(rnd.randrange(1 << 30)).normal(0, rnd.uniform(1, 4), img.shape)
    ok, buf = cv2.imencode(".jpg", np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, rnd.randint(35, 85)])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)
