"""Step 6 of the POV plan: synthetic full frames in the head-mounted POV camera (docs/pov-videos.md).

    /root/venvs/blender/bin/python scripts/pov/render_pov_frames.py <poses.json> <out_dir> <first_seed> <count>

<poses.json> (from scripts/pov/pov_synth_poses.py): the lens {f, k1, k2} the camera track was solved with and a list of
solved real frames {frame, rv, tv} (OpenCV world-to-camera, mm). Per sample (seeded, reproducible):
- the camera of one real solved frame (so the render lines up with that frame's boards, goals and hall, which
  compose_pov.py uses as background); a pinhole render with the track's focal length on a canvas with a MARGIN px border,
  the lens distortion is applied afterwards (compose_pov.py);
- all twelve figures at uniform random slot positions and a uniform rotation in [0, 360) (goalies too: the user's
  goalie stands turned toward its own goal in most game-0002 frames, user 2026-10-16; v1 renders, seeds < 10000, had
  goalies within +-100 deg of home), the pivot on the slot centreline (assumed, as scripts/synth); a figure whose pivot would
  come within 60 mm of an already placed one is re-drawn (10 tries) or hidden; 8% of figures hidden at random;
- a puck in 75% of samples: half next to a random figure (20-90 mm from its pivot), half anywhere on the ice;
- kit colour jitter (white/blue W, yellow E, as the game), random back prints, random sun and ambient light.
Cycles (CPU), ice = shadow catcher, inner boards/screens/housing = holdouts (they come from the real frame), goals
rendered. Writes <out_dir>/<seed>.png (RGBA canvas) and one JSON line per sample to <out_dir>/labels.jsonl.
"""
import json
import math
import random
import sys
from pathlib import Path

import bpy
import cv2
import numpy as np
from mathutils import Matrix

REPO = Path(__file__).resolve().parents[2]
POSES = json.loads(Path(sys.argv[1]).read_text())
OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
SEED0, COUNT = int(sys.argv[3]), int(sys.argv[4])
SAMPLES = int(sys.argv[5]) if len(sys.argv) > 5 else 12
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
HOME = {"W": 0.0, "E": 180.0}
W_PX, H_PX, MARGIN = 960, 720, 64
CW, CH = W_PX + 2 * MARGIN, H_PX + 2 * MARGIN
F = POSES["lens"]["f"]

bpy.ops.wm.open_mainfile(filepath=str(REPO / "assets/scene/full_static.blend"))
sc = bpy.context.scene
cam = bpy.data.cameras.new("POV"); cob = bpy.data.objects.new("POV", cam); sc.collection.objects.link(cob); sc.camera = cob
cam.sensor_fit = "HORIZONTAL"; cam.sensor_width = 36.0; cam.lens = F * 36.0 / CW; cam.clip_start = 0.02; cam.clip_end = 30
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = CW, CH, 100


def set_camera(rv, tv):
    R = cv2.Rodrigues(np.array(rv, float))[0]; t = np.array(tv, float)
    M = np.eye(4); M[:3, :3] = R.T @ np.diag([1, -1, -1]); M[:3, 3] = -R.T @ t / 1000.0
    cob.matrix_world = Matrix(M.tolist())
    return R, t


def arc_point(P, u):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = u * seg.sum(); acc = np.r_[0, np.cumsum(seg)]
    k = min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1); f = (s - acc[k]) / seg[k]
    return P[k] + f * (P[k + 1] - P[k]), s


def place(ob, pid, u, theta):
    p, s = arc_point(SLOT[pid], u); head = HOME[pid[0]] + theta
    ob.matrix_world = Matrix.Translation((p[0] / 1000, p[1] / 1000, 0)) @ Matrix.Rotation(math.radians(head), 4, "Z")
    return p, s, head


sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
sc.render.film_transparent = True; sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.render.use_border = True; sc.render.use_crop_to_border = False
bpy.data.objects["Ice"].is_shadow_catcher = True
for o in bpy.data.objects:
    if o.type == "MESH" and o.name.startswith(("InnerBoards", "EndScreen", "Housing")): o.is_holdout = True
figs = {o["player_id"]: o for o in bpy.data.objects if o.name.startswith("Figure.")}
ALL = sorted(figs)
kit = {m.name: tuple(m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value) for m in bpy.data.materials
       if m.use_nodes and m.node_tree.nodes.get("Principled BSDF") and m.name.startswith(("fig_kit", "fig_blue"))}
TEX = REPO / "assets/figures/textures"
prints = {e: [bpy.data.images.load(str(f)) for f in sorted(TEX.glob(f"print_skater_{k}_*.png"))] for e, k in (("W", "FIN"), ("E", "SWE"))}
SKATERS = [p for p in ALL if not p.endswith("-G")]
pmat = {pid: figs[pid].children[0].material_slots[0].material for pid in SKATERS}
ptex = {pid: next(n for n in pmat[pid].node_tree.nodes if n.type == "TEX_IMAGE") for pid in SKATERS}
sun = bpy.data.objects["Sun"]
world = sc.world; bg = world.node_tree.nodes.get("Background") if world and world.use_nodes else None
pk = bpy.data.objects["Puck"]

lab = open(OUT / "labels.jsonl", "a")
for seed in range(SEED0, SEED0 + COUNT):
    rnd = random.Random(seed)
    pose = POSES["frames"][rnd.randrange(len(POSES["frames"]))]
    R, t = set_camera(pose["rv"], pose["tv"])
    placed, piv = {}, []
    for pid in rnd.sample(ALL, len(ALL)):
        ob = figs[pid]; ok = False
        for _ in range(10):
            u = rnd.random(); th = rnd.uniform(-100, 100) if (pid.endswith("-G") and seed < 10000) else rnd.uniform(0, 360)
            p, s, head = place(ob, pid, u, th)
            if all(np.linalg.norm(p - q) >= 60 for q in piv): ok = True; break
        if ok and rnd.random() < 0.08: ok = False
        ob.hide_render = not ok
        for c in ob.children: c.hide_render = not ok
        if ok:
            piv.append(p); placed[pid] = {"u": round(u, 5), "s_mm": round(float(s), 2), "theta_deg": round(th % 360, 3),
                                          "heading_deg": round(head % 360, 3), "pivot_mm": [round(float(p[0]), 2), round(float(p[1]), 2)]}
    for p_ in SKATERS:  # back prints: a random number of the team, hidden in 20%
        ptex[p_].image = rnd.choice(prints[p_[0]])
        for c in figs[p_].children: c.hide_render = figs[p_].hide_render or rnd.random() < 0.2
    puck = None; pk.hide_render = True
    if rnd.random() < 0.75:
        for _ in range(20):
            if piv and rnd.random() < 0.5:
                a = rnd.uniform(0, 2 * math.pi); r = rnd.uniform(20, 90); pp = rnd.choice(piv) + r * np.array([math.cos(a), math.sin(a)])
            else:
                pp = np.array([rnd.uniform(-400, 400), rnd.uniform(-200, 200)])
            if abs(pp[0]) < 405 and abs(pp[1]) < 205 and all(np.linalg.norm(pp - q) >= 40 for q in piv):
                pk.location = (pp[0] / 1000, pp[1] / 1000, pk.location.z); pk.hide_render = False
                puck = [round(float(pp[0]), 1), round(float(pp[1]), 1)]; break
    for name, base in kit.items():
        base = (0.80, 0.56, 0.01) if "SWE" in name else base
        m = bpy.data.materials[name]; c = np.array(base[:3]) * rnd.uniform(0.85, 1.15) + np.array([rnd.uniform(-0.02, 0.02) for _ in range(3)])
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*np.clip(c, 0, 1), 1)
    sun.rotation_euler = (math.radians(rnd.uniform(5, 50)), 0, math.radians(rnd.uniform(0, 360)))
    sun.data.energy = rnd.uniform(1.5, 5.0)
    if bg: bg.inputs["Strength"].default_value = rnd.uniform(0.3, 1.2)
    # render only the rink's image box (ice corners and 80 mm above them), in canvas px
    X = np.array([(x, y, z) for x in (-470, 470) for y in (-280, 280) for z in (0, 80)], float)
    q = (X @ R.T + t); q = q[q[:, 2] > 10]; uv = q[:, :2] / q[:, 2:] * F + [CW / 2, CH / 2]
    x0, y0 = np.clip(uv.min(0) - 8, 0, [CW, CH]); x1, y1 = np.clip(uv.max(0) + 8, 0, [CW, CH])
    sc.render.border_min_x, sc.render.border_max_x = x0 / CW, x1 / CW
    sc.render.border_min_y, sc.render.border_max_y = 1 - y1 / CH, 1 - y0 / CH
    sc.cycles.seed = seed; sc.render.filepath = str(OUT / f"{seed}.png")
    bpy.ops.render.render(write_still=True)
    lab.write(json.dumps({"seed": seed, "frame": pose["frame"], "rv": pose["rv"], "tv": pose["tv"], "lens": POSES["lens"],
                          "margin_px": MARGIN, "figures": placed, "puck_mm": puck}) + "\n"); lab.flush()
