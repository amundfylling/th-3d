"""Step 2 of the POV plan: gate frames and cut a game into usable segments.

A frame is GOOD when (thresholds ASSUMED, checked by eye on the contact sheets):
  - the camera points within MAX_ANGLE deg of the game's median orientation (DJI quaternion 3.2.9);
  - the angular speed (quaternion difference, smoothed over 3 frames) is below MAX_SPEED deg/s (motion blur);
  - the roll from the smoothed accelerometer (3.2.10, 0.5 s median) is within MAX_ROLL deg of the game median (upright);
  - the central-image Laplacian sharpness is at least MIN_SHARP_REL of its 10 s running median.
Good runs shorter than MIN_SEG s are dropped; gaps shorter than MAX_GAP s inside a run are bridged.
Usage: python3 scripts/pov/segment_game.py <video.LRF> <indexdir> <outdir>
"""
import json, os, subprocess, sys
import numpy as np
from scipy.ndimage import median_filter, uniform_filter1d
from scipy.spatial.transform import Rotation as R

MAX_ANGLE, MAX_SPEED, MAX_ROLL, MIN_SHARP_REL = 20.0, 40.0, 15.0, 0.75
MIN_SEG, MAX_GAP = 1.0, 0.2
FPS = 30000 / 1001

video, idx, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
d = np.load(os.path.join(idx, 'frames.npz'))
t, n = d['t'], len(d['t'])
r = R.from_quat(d['q'][:, [1, 2, 3, 0]])  # stored w,x,y,z (unit norm in every frame)
ref = r.mean()
angle = np.degrees((r * ref.inv()).magnitude())
speed = np.r_[0, np.degrees((r[1:] * r[:-1].inv()).magnitude()) * FPS]
speed = uniform_filter1d(speed, 3)
g = median_filter(d['acc'], size=(15, 1))
roll = np.degrees(np.arctan2(g[:, 1], -g[:, 0]))
roll -= np.median(roll)
sharp_rel = d['sharp'] / median_filter(d['sharp'], size=int(10 * FPS), mode='nearest')
reasons = {'turned_away': angle > MAX_ANGLE, 'fast_turn': speed > MAX_SPEED, 'rotated': np.abs(roll) > MAX_ROLL,
           'blurred': sharp_rel < MIN_SHARP_REL}
good = ~np.any(list(reasons.values()), axis=0)

# bridge short gaps, then drop short runs
g2 = good.copy()
i = 0
while i < n:
    if not g2[i]:
        j = i
        while j < n and not g2[j]:
            j += 1
        if 0 < i and j < n and (j - i) / FPS <= MAX_GAP:
            g2[i:j] = True
        i = j
    else:
        i += 1
segs, i = [], 0
while i < n:
    if g2[i]:
        j = i
        while j < n and g2[j]:
            j += 1
        if (j - i) / FPS >= MIN_SEG:
            segs.append((i, j - 1))
        i = j
    else:
        i += 1
usable = np.zeros(n, bool)
for a, b in segs:
    usable[a:b + 1] = True

res = {
    'video': os.path.basename(video), 'frames': int(n), 'fps': '30000/1001', 'status': 'PROPOSED',
    'thresholds': {'max_angle_deg': MAX_ANGLE, 'max_speed_deg_s': MAX_SPEED, 'max_roll_deg': MAX_ROLL,
                   'min_sharp_rel': MIN_SHARP_REL, 'min_segment_s': MIN_SEG, 'max_gap_s': MAX_GAP,
                   'status': 'assumed'},
    'usable_frames': int(usable.sum()), 'usable_fraction': round(float(usable.mean()), 3),
    'reject_counts': {k: int(v.sum()) for k, v in reasons.items()},
    'segments': [{'start_frame': int(a), 'end_frame': int(b), 'start_s': round(float(t[a]), 3),
                  'end_s': round(float(t[b]), 3), 'duration_s': round(float(t[b] - t[a] + 1 / FPS), 3)} for a, b in segs],
}
json.dump(res, open(os.path.join(out, 'segments.json'), 'w'), indent=1)
np.savez(os.path.join(out, 'gate.npz'), good=good, usable=usable, angle=angle, speed=speed, roll=roll, sharp_rel=sharp_rel)
print(f"{len(segs)} segments, usable {usable.sum()}/{n} = {usable.mean():.1%}; rejects", res['reject_counts'])


def sheet(frames_idx, path, cols=6, w=320, label=None):
    sel = '+'.join(f'eq(n\\,{k})' for k in frames_idx)
    rows = int(np.ceil(len(frames_idx) / cols))
    vf = f"select='{sel}',scale={w}:{w * 3 // 4},drawtext=text='%{{n}}':x=4:y=4:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6,tile={cols}x{rows}"
    subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-map', '0:v:0', '-vf', vf, '-vsync', '0', '-frames:v', '1',
                    '-y', path], check=True)


rng = np.random.default_rng(0)
ui = np.flatnonzero(usable)
mid = ui[(ui > 0.1 * n) & (ui < 0.9 * n)]
sheet(sorted(rng.choice(mid, 24, replace=False)), os.path.join(out, 'usable-sheet.jpg'))
bad = np.flatnonzero(~usable)
if len(bad):
    sheet(sorted(rng.choice(bad, min(24, len(bad)), replace=False)), os.path.join(out, 'rejected-sheet.jpg'))
