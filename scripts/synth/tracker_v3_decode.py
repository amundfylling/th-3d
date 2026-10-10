"""Temporal decoding for figure tracker v3 (docs/tracker-v3.md). Pure functions, no video, no model.

A figure's track is decoded from per-frame candidate readings (slot position s in mm, rotation theta in degrees, a
per-reading cost) with two dynamic programmes:

1. Position: a shortest path through the candidates in time order. A step from one reading to the next costs its slot
   distance relative to what a figure can move in that time; a frame may be skipped (no candidate kept) at a fixed cost,
   so a one-frame lock-on (the localiser on the board, or on a neighbour) is cheaper to drop than to follow. Steps beyond
   the hard speed limit are not allowed.
2. Rotation: along the kept readings, each frame takes the model's rotation or the rotation turned by 180 degrees (a
   front/back flip of the model) at a fixed cost; a step costs the rotation change relative to what a rod can turn in
   that time. An isolated 180-degree flip is cheaper to undo than to follow.
Dropped frames are filled by interpolation (in time; rotation along the shorter arc) when the gap is at most GAP_S,
else they stay unknown. Last, a 3-sample centred average on consecutive 30 fps frames (as smooth-tracks.py).

All limits are ASSUMED (tuned on nothing but the stated physics; see docs/tracker-v3.md):
"""
import numpy as np

V_TYP = 600.0      # mm/s: slot speed that costs one unit per step (a wing carrying the puck)
V_MAX = 2500.0     # mm/s: hard limit along the slot (a hard rod pull); plus HARD_SLACK for reading noise
POS_SLACK = 12.0   # mm: reading noise that is free of motion cost
HARD_SLACK = 35.0  # mm
SKIP = 1.6         # cost of dropping one frame's readings
W_TYP = 900.0      # deg/s: rotation speed that costs one unit per step
ROT_SLACK = 15.0   # deg
FLIP = 2.5         # cost of turning one reading by 180 degrees
GAP_S = 1.0        # s: longest gap that is interpolated
MAX_BACK = 30      # how many frames back a step may reach (skips)


def circ(a):
    return (np.asarray(a) + 180.0) % 360.0 - 180.0


def decode_position(t, cands):
    """t: (n,) seconds; cands: list of n lists of (s_mm, cost). Returns the chosen candidate index per frame (-1 = dropped)."""
    n = len(t); INF = 1e18
    best = [np.full(len(c), INF) for c in cands]; back = [[None] * len(c) for c in cands]
    for k in range(n):
        if not cands[k]: continue
        s_k = np.array([c[0] for c in cands[k]]); u_k = np.array([c[1] for c in cands[k]])
        best[k] = SKIP * k + u_k  # start here, all earlier frames dropped
        back[k] = [None] * len(s_k)
        for j in range(max(0, k - MAX_BACK), k):
            if not cands[j] or not np.isfinite(best[j]).any(): continue
            dt = t[k] - t[j]; s_j = np.array([c[0] for c in cands[j]])
            d = np.abs(s_k[:, None] - s_j[None, :])
            step = np.maximum(0.0, d - POS_SLACK) / (V_TYP * dt + 1e-6)
            step[d > HARD_SLACK + V_MAX * dt] = INF
            tot = best[j][None, :] + step + SKIP * (k - j - 1) + u_k[:, None]
            a = np.argmin(tot, 1); v = tot[np.arange(len(s_k)), a]
            for i in np.where(v < best[k])[0]:
                best[k][i] = v[i]; back[k][i] = (j, int(a[i]))
    # end anywhere, later frames dropped
    end, ev = None, INF
    for k in range(n):
        if cands[k] and len(best[k]):
            i = int(np.argmin(best[k])); v = best[k][i] + SKIP * (n - 1 - k)
            if v < ev: ev, end = v, (k, i)
    pick = np.full(n, -1)
    while end is not None:
        k, i = end; pick[k] = i; end = back[k][i]
    return pick


def decode_rotation(t, th):
    """t, th: readings along the kept path. Returns th with isolated front/back flips undone."""
    n = len(th)
    if n == 0: return th
    S = np.stack([th, (th + 180.0) % 360.0], 1); u = np.array([0.0, FLIP])
    best = u.copy(); back = np.zeros((n, 2), int)
    for k in range(1, n):
        dt = t[k] - t[k - 1]; d = np.abs(circ(S[k][:, None] - S[k - 1][None, :]))
        step = np.maximum(0.0, d - ROT_SLACK) / (W_TYP * dt + 1e-6)
        tot = best[None, :] + step; back[k] = np.argmin(tot, 1); best = tot[np.arange(2), back[k]] + u
    st = np.zeros(n, int); st[-1] = int(np.argmin(best))
    for k in range(n - 1, 0, -1): st[k - 1] = back[k][st[k]]
    return S[np.arange(n), st], st


def decode(frames, cands, dense):
    """frames: (n,) frame indices (30 fps); cands: per frame a list of (s_mm, theta_deg, cost); dense: (n,) bool.
    Returns s (mm, nan = unknown), theta (deg), src (0 kept, 1 interpolated, 2 unknown), flipped (bool)."""
    t = np.asarray(frames, float) / 30.0; n = len(t)
    pick = decode_position(t, [[(c[0], c[2]) for c in cs] for cs in cands])
    kept = np.where(pick >= 0)[0]
    s = np.full(n, np.nan); th = np.full(n, np.nan); src = np.full(n, 2); flipped = np.zeros(n, bool)
    if len(kept):
        s[kept] = [cands[k][pick[k]][0] for k in kept]
        th_k, st = decode_rotation(t[kept], np.array([cands[k][pick[k]][1] for k in kept], float))
        th[kept] = th_k; flipped[kept] = st == 1; src[kept] = 0
        for a, b in zip(kept[:-1], kept[1:]):
            if b - a > 1 and t[b] - t[a] <= GAP_S:
                w = (t[a + 1:b] - t[a]) / (t[b] - t[a])
                s[a + 1:b] = s[a] + w * (s[b] - s[a]); th[a + 1:b] = (th[a] + w * circ(th[b] - th[a])) % 360; src[a + 1:b] = 1
    s3, th3 = s.copy(), th.copy(); fr = np.asarray(frames)
    for i in range(1, n - 1):
        if dense[i] and fr[i + 1] - fr[i] == 1 and fr[i] - fr[i - 1] == 1 and src[i - 1] < 2 and src[i] < 2 and src[i + 1] < 2:
            s3[i] = (s[i - 1] + s[i] + s[i + 1]) / 3
            th3[i] = (th[i] + (circ(th[i - 1] - th[i]) + circ(th[i + 1] - th[i])) / 3) % 360
    return s3, th3, src, flipped


def reading_cost(slot_dist_mm=None, presence=None, rank=0, colour=None):
    """Cost of one reading: far from the slot (the pivot off its slot), a very weak kit-colour peak (on the 352 label
    frames true first peaks score 10-23 (5th-50th percentile), so under 6 is mostly noise) and, with the v3 model, a low
    presence; the second colour peak pays a little more than the first."""
    c = 0.0
    if colour is not None: c += max(0.0, 6.0 - colour) / 3.0
    if slot_dist_mm is not None:
        if slot_dist_mm > 25: return None
        c += max(0.0, slot_dist_mm - 6.0) / 6.0
    if presence is not None:
        c += -np.log(max(presence, 1e-4)) * 1.5
    return c + 0.3 * rank
