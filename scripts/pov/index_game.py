"""Step 2 of the POV plan: per-frame quality signals for one .LRF game file.

Signals per frame: Laplacian sharpness of the central image, angular speed and angle from the median "playing"
orientation (DJI quaternion 3.2.9), gravity direction in the camera (accelerometer 3.2.10).
Writes <out>/frames.npz. Segmenting is done by segment_game.py.
Usage: python3 scripts/pov/index_game.py <video.LRF> <outdir>
"""
import os, subprocess, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
import dji_meta

video, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
W, H = 480, 360
fr = dji_meta.frames(video)
q = np.array([f['q'] for f in fr])
acc = np.array([f.get('v10', [0, 0, 0, 0])[1:] for f in fr])
p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', video, '-map', '0:v:0', '-vf', f'scale={W}:{H}', '-pix_fmt', 'gray',
                      '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
sharp, mean = [], []
while True:
    b = p.stdout.read(W * H)
    if len(b) < W * H:
        break
    g = np.frombuffer(b, np.uint8).reshape(H, W)
    c = g[H // 6: H - H // 6, W // 6: W - W // 6]
    sharp.append(cv2.Laplacian(c, cv2.CV_32F).var())
    mean.append(c.mean())
p.wait()
n = min(len(sharp), len(q))
np.savez(os.path.join(out, 'frames.npz'), t=np.array([f['t'] for f in fr[:n]]), q=q[:n], acc=acc[:n],
         sharp=np.array(sharp[:n]), mean=np.array(mean[:n]))
print(n, 'frames; sharpness p5/50/95', np.percentile(sharp, [5, 50, 95]))
