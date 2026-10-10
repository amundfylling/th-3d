"""Hard-example skater crops for tracker v3 (docs/tracker-v3.md), on top of render-skater-crops.py.

    /root/venvs/blender/bin/python scripts/synth/render-skater-hard.py <out_dir> <first_seed> <count> [base|hard] [--threads n]

"base" draws exactly the samples of render-skater-crops.py ... nm26 (same seeds, same random sequence, same labels),
only faster: Cycles keeps its scene data between renders (persistent data) and the thread count can be fixed, so
several processes can share the CPU. Seeds already in <out_dir> are skipped (resume after a container restart).

"hard" (seeds from 100000 up, so they never collide with base seeds) adds the weak cases of docs/nm26-figure-tracks.md:
- target: a wing in half of the samples (W-RW and E-LW, whose slots run along the near board, in a quarter), at a
  slot end (u < 0.15 or u > 0.85, the corners and boards) in half of the samples;
- crowding: in half of the samples one or two other figures are placed 60-90 mm from the target (overlap in the image);
- lock-on negatives (presence 0), in 35% of the samples:
  - "offset": the crop is centred on the target's slot 45-200 mm (along the slot) away from the target, as when the
    kit-colour localiser follows noise or a neighbour;
  - "hidden": the target is not rendered at all (hidden by a hand, a neighbour or the board), the crop where it would be.
Every label line carries "present" (1 = the target's pivot is inside the crop's network window with a 10 px margin
and the target is rendered) and "kind" (base, hard, offset, hidden). Status: PROPOSED (assumed distributions).
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
SEED0, COUNT = int(sys.argv[2]), int(sys.argv[3]); MODE = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else "base"
KIT = "nm26"; THREADS = int(sys.argv[sys.argv.index("--threads") + 1]) if "--threads" in sys.argv else 0
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
HOME = {"W": 0.0, "E": 180.0}
ORDER = ["W-LW", "E-LW", "W-RW", "E-RW", "W-C", "E-C", "W-LD", "E-LD", "W-RD", "E-RD"]
ROI = (160, 360, 1900, 1000)  # reference video px, as scripts/synth/skater-frames.py
CS, AY = 200, 136             # crop size, pivot row in the crop
K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])

bpy.ops.wm.open_mainfile(filepath=str(REPO / "assets/scene/full_static.blend"))
sc = bpy.context.scene
W_IMG, H_IMG = CAM["image_size"]


def set_camera():
    cam = bpy.data.cameras.new("NM26Ref"); ob = bpy.data.objects.new("NM26Ref", cam); sc.collection.objects.link(ob)
    cam.sensor_fit = "HORIZONTAL"; cam.sensor_width = 36.0; cam.lens = K[0, 0] * 36.0 / W_IMG
    cam.shift_x = (W_IMG / 2 - K[0, 2]) / W_IMG; cam.shift_y = (K[1, 2] - H_IMG / 2) / W_IMG; cam.clip_start = 0.05; cam.clip_end = 20
    M = np.eye(4); M[:3, :3] = R.T @ np.diag([1, -1, -1]); M[:3, 3] = -R.T @ t / 1000.0
    ob.matrix_world = Matrix(M.tolist()); sc.camera = ob
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W_IMG, H_IMG, 100


def arc_point(P, u):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = u * seg.sum(); acc = np.r_[0, np.cumsum(seg)]
    k = min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1); f = (s - acc[k]) / seg[k]
    return P[k] + f * (P[k + 1] - P[k]), s


def place(ob, pid, u, theta):
    p, s = arc_point(SLOT[pid], u); head = HOME[pid[0]] + theta
    ob.matrix_world = Matrix.Translation((p[0] / 1000, p[1] / 1000, 0)) @ Matrix.Rotation(math.radians(head), 4, "Z")
    return p, s, head


def project(p):
    q = K @ (R @ np.array([p[0], p[1], 0.0]) + t); return q[:2] / q[2]


set_camera()
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 8; sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
sc.render.film_transparent = True; sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.render.use_persistent_data = True
if THREADS: sc.render.threads_mode = "FIXED"; sc.render.threads = THREADS
sc.render.use_border = True; sc.render.use_crop_to_border = True
bpy.data.objects["Ice"].is_shadow_catcher = True
for o in bpy.data.objects:
    if o.type == "MESH" and o.name.startswith(("Goal.", "InnerBoards", "EndScreen", "Housing")): o.is_holdout = True
figs = {o["player_id"]: o for o in bpy.data.objects if o.name.startswith("Figure.")}
kit = {m.name: tuple(m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value) for m in bpy.data.materials
       if m.use_nodes and m.node_tree.nodes.get("Principled BSDF") and m.name.startswith(("fig_kit", "fig_blue"))}
TEX = REPO / "assets/figures/textures"
prints = {e: [bpy.data.images.load(str(f)) for f in sorted(TEX.glob(f"print_skater_{k}_*.png"))] for e, k in (("W", "FIN"), ("E", "SWE"))}
pmat = {pid: figs[pid].children[0].material_slots[0].material for pid in ORDER}
ptex = {pid: next(n for n in pmat[pid].node_tree.nodes if n.type == "TEX_IMAGE") for pid in ORDER}

# NM26 table kits (KIT == "nm26"): filled in from the kit check against real crops (docs/synthetic-goalie-pilot.md)
KITS = {}
if KIT == "nm26":
    exec((Path(__file__).resolve().parent / "skater_kits_nm26.py").read_text())

sun = bpy.data.objects["Sun"]
world = sc.world; bg = world.node_tree.nodes.get("Background") if world and world.use_nodes else None
done = set()
if (OUT / "labels.jsonl").exists():
    done = {json.loads(l)["seed"] for l in open(OUT / "labels.jsonl") if l.strip()}
lab = open(OUT / "labels.jsonl", "a")
WINGS = ["W-LW", "E-LW", "W-RW", "E-RW"]; NEAR = ["W-RW", "E-LW"]


def slot_len(pid): return float(np.linalg.norm(np.diff(SLOT[pid], axis=0), axis=1).sum())


for seed in range(SEED0, SEED0 + COUNT):
    if seed in done or (OUT / f"{seed}.png").exists() and seed in done: continue
    rnd = random.Random(seed)
    pid = ORDER[seed % len(ORDER)]; kind = "base"; hrnd = random.Random(seed * 31 + 7)
    if MODE == "hard":
        kind = "hard"; r0 = hrnd.random()
        if r0 < 0.25: pid = hrnd.choice(NEAR)
        elif r0 < 0.5: pid = hrnd.choice(WINGS)
        r1 = hrnd.random(); kind = "offset" if r1 < 0.25 else "hidden" if r1 < 0.35 else "hard"
    if KITS: KITS["apply"](rnd)
    u, th = rnd.random(), rnd.uniform(0, 360)
    if MODE == "hard" and hrnd.random() < 0.5: u = hrnd.uniform(0, 0.15) if hrnd.random() < 0.5 else hrnd.uniform(0.85, 1.0)
    pv, s, head = place(figs[pid], pid, u, th); figs[pid].hide_render = kind == "hidden"
    piv = [pv]; others = []
    crowd = MODE == "hard" and hrnd.random() < 0.5; ncrowd = hrnd.randint(1, 2)
    for o_pid in [p for p in figs if p != pid]:
        o = figs[o_pid]; ok = False
        for k_ in range(10 if not crowd else 60):
            uo, tho = rnd.random(), rnd.uniform(0, 360)
            if crowd and ncrowd > 0 and k_ < 50: uo = hrnd.random()
            po, _, _ = place(o, o_pid, uo, tho); dmin = min(np.linalg.norm(po - q) for q in piv)
            if crowd and ncrowd > 0 and k_ < 50:
                if 60 <= np.linalg.norm(po - pv) <= 90 and dmin >= 60: ok = True; ncrowd -= 1; break
                continue
            if dmin >= 60: ok = True; break
        o.hide_render = not ok
        if ok: piv.append(po); others.append({"id": o_pid, "u": round(uo, 4), "theta_deg": round(tho, 2)})
    for p_ in ORDER:  # back prints: a random number of the team, hidden in 20%
        ptex[p_].image = rnd.choice(prints[p_[0]])
        for c in figs[p_].children: c.hide_render = rnd.random() < 0.2 or figs[p_].hide_render
    for g_ in ("W-G", "E-G"):
        for c in figs[g_].children: c.hide_render = figs[g_].hide_render
    pk = bpy.data.objects["Puck"]; puck = None; pk.hide_render = True
    if rnd.random() < 0.4:
        for _ in range(10):
            a = rnd.uniform(0, 2 * math.pi); r = rnd.uniform(20, 120); pp = pv + r * np.array([math.cos(a), math.sin(a)])
            if abs(pp[0]) < 400 and abs(pp[1]) < 200 and min(np.linalg.norm(pp - q) for q in piv) >= 45:
                pk.location = (pp[0] / 1000, pp[1] / 1000, pk.location.z); pk.hide_render = False; puck = [round(pp[0], 1), round(pp[1], 1)]; break
    for name, base in kit.items():
        base = (0.80, 0.56, 0.01) if "SWE" in name else base
        base, j = KITS["colour"](name, base) if KITS else (base, (0.85, 1.15))
        m = bpy.data.materials[name]; c = np.array(base[:3]) * rnd.uniform(*j) + np.array([rnd.uniform(-0.02, 0.02) for _ in range(3)])
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*np.clip(c, 0, 1), 1)
    sun.rotation_euler = (math.radians(rnd.uniform(5, 50)), 0, math.radians(rnd.uniform(0, 360)))
    sun.data.energy = rnd.uniform(1.5, 5.0)
    if bg: bg.inputs["Strength"].default_value = rnd.uniform(0.3, 1.2)
    f = project(pv); c = f
    if kind == "offset":  # crop centred on the same slot, 45-200 mm away from the target (a localiser lock-on)
        L_ = slot_len(pid); cand = [x for x in (s + hrnd.choice([-1, 1]) * hrnd.uniform(45, 200),) ]
        s2 = float(np.clip(cand[0], 0, L_)); s2 = s2 if abs(s2 - s) >= 45 else float(np.clip(s - (cand[0] - s), 0, L_))
        c = project(arc_point(SLOT[pid], s2 / L_)[0])
    x0 = int(round(c[0] - CS / 2 + rnd.uniform(-16, 16))); y0 = int(round(c[1] - AY + rnd.uniform(-16, 16)))
    x0 = min(max(x0, ROI[0]), ROI[2] - CS); y0 = min(max(y0, ROI[1]), ROI[3] - CS)
    # a quarter-pixel nudge keeps float rounding from dropping a pixel row or column (the crop must be exactly CS x CS)
    sc.render.border_min_x, sc.render.border_max_x = (x0 + 0.25) / W_IMG, (x0 + CS + 0.25) / W_IMG
    sc.render.border_min_y, sc.render.border_max_y = 1 - (y0 + CS + 0.25) / H_IMG, 1 - (y0 + 0.25) / H_IMG
    sc.cycles.seed = seed; sc.render.filepath = str(OUT / f"{seed}.png")
    bpy.ops.render.render(write_still=True)
    px_, py_ = f[0] - x0, f[1] - y0
    present = int(kind != "hidden" and 25 <= px_ <= 175 and 30 <= py_ <= 180)
    lab.write(json.dumps({"seed": seed, "pid": pid, "kind": kind, "present": present, "end": pid[0], "u": round(u, 5), "s_mm": round(float(s), 2), "theta_deg": round(th, 3),
                          "heading_deg": round(head, 3), "pivot_mm": [round(float(pv[0]), 2), round(float(pv[1]), 2)],
                          "crop_origin_ref_px": [x0, y0], "pivot_px": [round(float(f[0] - x0), 1), round(float(f[1] - y0), 1)],
                          "others": others, "puck_mm": puck, "kit": KIT}) + "\n"); lab.flush()
