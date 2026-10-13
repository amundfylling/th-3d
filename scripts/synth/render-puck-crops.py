"""Synthetic puck renders for the NM26 broadcast camera: a moving, motion-blurred puck, three consecutive frames.

    /root/venvs/blender/bin/python scripts/synth/render-puck-crops.py <out_dir> <first_seed> <count> [--shots]

docs/synthetic-puck.md. Per sample (seeded, reproducible):
- the puck's position at the middle frame: uniform on the ice inside the board boundary, with extra weight near the
  boards (20%) and around the two goals (15%, also behind and inside the cage);
- its velocity: 30% slow (0-300 mm/s), 70% fast (300-6000 mm/s, uniform), any direction; constant over the three frames
  (t-1, t, t+1 at 30 fps); a sample whose path leaves the ice is re-drawn;
- the shutter: open for 20-100% of the frame interval (the broadcast's exposure is not known), centred on the frame
  time, Cycles motion blur;
- puck material: base colour 0.008-0.05 (near black, matte: roughness 0.45-0.9, specular 0.1-0.5); sun 0-25 deg from
  overhead (the hall lights are above the table), random sun and ambient strength.
--shots (puck-det-v2, 2026-10-11): shot flights instead. Speed 3000-10000 mm/s, shutter 40-100% of the frame interval
(long, faint streaks); 60% of the samples start in front of a goal (up to 350 mm out, |y| <= 160 mm) and fly at its mouth
(aim uniform across the mouth +-30 mm), the rest anywhere in any direction. The path may end inside the goal (the cage
is a holdout, so the streak disappears into it as in the broadcast).
Only the puck is rendered: the figures are hidden (the detector learns them from real frames), the ice is a shadow
catcher, goals, boards and screens are holdouts (they occlude the puck exactly as in the real picture: behind the
cage, against the near board). Each frame is a separate crop around the swept puck (reference video px, 12 px margin).
Writes <out_dir>/<seed>_<k>.png (RGBA, k = 0, 1, 2) and one JSON line per sample to <out_dir>/labels.jsonl:
positions (world mm, puck centre on the ice), velocity, shutter, crop origins and the label pixel of each frame (the
projection of the puck's top-face centre at the frame time, reference video px).
"""
import json
import math
import random
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

REPO = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
SEED0, COUNT = int(sys.argv[2]), int(sys.argv[3])
SHOTS = "--shots" in sys.argv
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
G = json.loads((REPO / "data/geometry.json").read_text())
BOARD = np.array(G["board"]["inner_boundary"]["world"]["points_mm"], float)
R_PUCK = G["puck"]["diameter"]["value"] / 2
K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
W_IMG, H_IMG = CAM["image_size"]

bpy.ops.wm.open_mainfile(filepath=str(REPO / "assets/scene/full_static.blend"))
sc = bpy.context.scene


def set_camera():
    cam = bpy.data.cameras.new("NM26Ref"); ob = bpy.data.objects.new("NM26Ref", cam); sc.collection.objects.link(ob)
    cam.sensor_fit = "HORIZONTAL"; cam.sensor_width = 36.0; cam.lens = K[0, 0] * 36.0 / W_IMG
    cam.shift_x = (W_IMG / 2 - K[0, 2]) / W_IMG; cam.shift_y = (K[1, 2] - H_IMG / 2) / W_IMG; cam.clip_start = 0.05; cam.clip_end = 20
    M = np.eye(4); M[:3, :3] = R.T @ np.diag([1, -1, -1]); M[:3, 3] = -R.T @ t / 1000.0
    ob.matrix_world = Matrix(M.tolist()); sc.camera = ob
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W_IMG, H_IMG, 100


def project(P):
    P = np.atleast_2d(np.asarray(P, float)); q = (P @ R.T + t) @ K.T; return q[:, :2] / q[:, 2:]


def inside(p, margin):
    """Point-in-polygon for the board boundary, at least <margin> mm from it."""
    x, y = p; n = len(BOARD); ins = False
    for i in range(n):
        (x1, y1), (x2, y2) = BOARD[i], BOARD[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): ins = not ins
    if not ins: return False
    d = min(np.linalg.norm(np.cross(np.r_[b - a, 0], np.r_[a - p, 0])) / max(np.linalg.norm(b - a), 1e-9)
            if 0 <= np.dot(p - a, b - a) <= np.dot(b - a, b - a) else min(np.linalg.norm(p - a), np.linalg.norm(p - b))
            for a, b in zip(BOARD, np.roll(BOARD, -1, axis=0)))
    return d >= margin


set_camera()
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 24; sc.cycles.use_denoising = False
sc.cycles.max_bounces = 3; sc.cycles.diffuse_bounces = 1; sc.cycles.glossy_bounces = 1; sc.cycles.transmission_bounces = 0; sc.cycles.volume_bounces = 0; sc.cycles.transparent_max_bounces = 4
sc.render.threads_mode = "FIXED"; sc.render.threads = int(__import__("os").environ.get("RENDER_THREADS", 4))
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
sc.render.film_transparent = True; sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.render.use_border = True; sc.render.use_crop_to_border = True
sc.render.use_motion_blur = True; sc.cycles.motion_blur_position = "CENTER"; sc.render.use_persistent_data = True
bpy.data.objects["Ice"].is_shadow_catcher = True
for o in bpy.data.objects:
    if o.type == "MESH" and o.name.startswith(("Goal.", "InnerBoards", "EndScreen", "Housing")): o.is_holdout = True
for o in [o for o in bpy.data.objects if o.name.startswith("Figure.")]:
    for c in [o] + list(o.children_recursive):
        if c.name in bpy.data.objects: bpy.data.objects.remove(c)
pk = bpy.data.objects["Puck"]; pk.hide_render = False
zs = [(pk.matrix_world @ v.co).z for v in pk.data.vertices] if pk.type == "MESH" else [0.0, 0.012]
Z0, TOP = pk.location.z, max(zs) * 1000.0  # puck top face above the ice (mm)
mats = [s.material for s in pk.material_slots if s.material and s.material.use_nodes]
bsdf = [m.node_tree.nodes.get("Principled BSDF") for m in mats]
sun = bpy.data.objects["Sun"]
world = sc.world; bg = world.node_tree.nodes.get("Background") if world and world.use_nodes else None
def goal_centre(end):
    V = [o.matrix_world @ v.co for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(f"Goal.{end}") for v in o.data.vertices]
    return np.array([np.mean([w.x for w in V]) * 1000, np.mean([w.y for w in V]) * 1000]) if V else np.array([(-380.0 if end == "W" else 380.0), 0.0])


GOALS = [goal_centre("W"), goal_centre("E")]
print("goal centres mm", GOALS)
ring = np.array([[R_PUCK * math.cos(a), R_PUCK * math.sin(a)] for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)])
lab = open(OUT / "labels.jsonl", "a")
for seed in range(SEED0, SEED0 + COUNT):
    rnd = random.Random(seed)
    for _ in range(200):
        if SHOTS:
            sp = rnd.uniform(3000, 10000)
            if rnd.random() < 0.6:
                gi = rnd.randrange(2); sgn = -1 if gi == 0 else 1     # GOALS[0] = W (-x), GOALS[1] = E (+x)
                mouth_x = GOALS[gi][0] - sgn * 60.0                   # about the goal line, in front of the cage centre
                aim = np.array([mouth_x, GOALS[gi][1] + rnd.uniform(-75, 75)])
                p = np.array([mouth_x - sgn * rnd.uniform(20, 350), rnd.uniform(-160, 160)])
                d = (aim - p) / np.linalg.norm(aim - p); v = sp * d
                p = p + d * rnd.uniform(0, 1) * min(np.linalg.norm(aim - p), sp / 30.0)
            else:
                p = np.array([rnd.uniform(-430, 430), rnd.uniform(-240, 240)])
                a = rnd.uniform(0, 2 * math.pi); v = sp * np.array([math.cos(a), math.sin(a)])
            P = [p + (k - 1) * v / 30.0 for k in range(3)]
            if inside(P[0], R_PUCK + 0.5) and inside(P[1], R_PUCK + 0.5) or (not inside(P[1], R_PUCK + 0.5) and abs(P[1][0]) > 230 and inside(P[0], R_PUCK + 0.5)):
                break
            continue
        r = rnd.random()
        if r < 0.20:   # near the boards
            p = BOARD[rnd.randrange(len(BOARD))] * rnd.uniform(0.90, 0.99)
        elif r < 0.35:  # around a goal
            p = GOALS[rnd.randrange(2)] + np.array([rnd.uniform(-90, 90), rnd.uniform(-90, 90)])
        else:
            p = np.array([rnd.uniform(-430, 430), rnd.uniform(-240, 240)])
        sp = rnd.uniform(0, 300) if rnd.random() < 0.3 else rnd.uniform(300, 6000)
        a = rnd.uniform(0, 2 * math.pi); v = sp * np.array([math.cos(a), math.sin(a)])
        P = [p + (k - 1) * v / 30.0 for k in range(3)]
        if all(inside(q, R_PUCK + 0.5) for q in P): break
    shutter = rnd.uniform(0.4, 1.0) if SHOTS else rnd.uniform(0.2, 1.0)
    sc.render.motion_blur_shutter = shutter
    pk.animation_data_clear()
    for fr, q in ((-1, p - 2 * v / 30.0), (3, p + 2 * v / 30.0)):
        pk.location = (q[0] / 1000, q[1] / 1000, Z0); pk.keyframe_insert("location", frame=fr)
    for fc in pk.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
    pk.rotation_euler = (0, 0, rnd.uniform(0, 2 * math.pi))
    for b in bsdf:
        if b is None: continue
        g = rnd.uniform(0.008, 0.05); b.inputs["Base Color"].default_value = (g, g, g * rnd.uniform(0.95, 1.1), 1)
        b.inputs["Roughness"].default_value = rnd.uniform(0.45, 0.9)
        if "Specular IOR Level" in b.inputs: b.inputs["Specular IOR Level"].default_value = rnd.uniform(0.1, 0.5)
    sun.rotation_euler = (math.radians(rnd.uniform(0, 25)), 0, math.radians(rnd.uniform(0, 360)))
    sun.data.energy = rnd.uniform(1.0, 4.0)
    if bg: bg.inputs["Strength"].default_value = rnd.uniform(0.3, 1.2)
    crops, labels = [], []
    ok = True
    for k in range(3):
        sc.frame_set(k)
        ends = [P[k] - shutter / 2 * v / 30.0, P[k] + shutter / 2 * v / 30.0]
        pts = np.vstack([np.c_[e + ring, np.full(len(ring), z)] for e in ends for z in (0.0, TOP)])
        q = project(pts)
        x0, y0 = int(math.floor(q[:, 0].min())) - 12, int(math.floor(q[:, 1].min())) - 12
        x1, y1 = int(math.ceil(q[:, 0].max())) + 12, int(math.ceil(q[:, 1].max())) + 12
        x1, y1 = max(x1, x0 + 48), max(y1, y0 + 48)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W_IMG), min(y1, H_IMG)
        if x1 - x0 < 16 or y1 - y0 < 16: ok = False; break   # the swept puck leaves the picture (shot renders)
        sc.render.border_min_x, sc.render.border_max_x = (x0 + 0.25) / W_IMG, (x1 + 0.25) / W_IMG
        sc.render.border_min_y, sc.render.border_max_y = 1 - (y1 + 0.25) / H_IMG, 1 - (y0 + 0.25) / H_IMG
        sc.cycles.seed = seed * 3 + k; sc.render.filepath = str(OUT / f"{seed}_{k}.png")
        bpy.ops.render.render(write_still=True)
        crops.append([x0, y0, x1 - x0, y1 - y0])
        labels.append([round(float(z), 2) for z in project([[P[k][0], P[k][1], TOP]])[0]])
    if not ok: continue
    lab.write(json.dumps({"seed": seed, "pos_mm": [[round(float(c), 2) for c in q] for q in P], "vel_mm_s": [round(float(c), 1) for c in v],
                          "shutter_frames": round(shutter, 3), "crop_ref_px": crops, "label_ref_px": labels, "top_mm": round(TOP, 2), "shot": SHOTS}) + "\n")
    lab.flush()
