"""Synthetic goalie crops for the NM26 broadcast camera (pilot, docs/synthetic-goalie-pilot.md).

    /root/venvs/blender/bin/python scripts/synth/render-goalie-crops.py <out_dir> <first_seed> <count> [W|E|both] [ref|nm26]

Optional: render one end only (default both: even seeds W, odd E), and the kit: "ref" (default, the reference
Sweden/Finland variant) or "nm26", the W goalie as seen on the NM26 table (docs/synthetic-goalie-pilot.md, section 2):
blue legs and pads below a randomised jersey hem (22, 26 or 30 mm; the reference kit in 15%) and a "1" back print.

Per sample (seeded, reproducible):
- the end's goalie (W: Finland-like white kit, E: Sweden-like yellow kit) at a uniform slot position u in [0, 1] and a
  uniform rotation theta in [0, 360) degrees relative to the team's home heading, pivot on the slot centreline
  (assume.fixture_axis_on_slot_centreline);
- 0-3 distractor skaters whose slots pass the goal crop, at random slot positions and rotations, dropped if their
  pivot is within 75 mm of another figure's (no overlap);
- a puck on the ice in half the samples, dropped if within 50 mm of a figure's pivot;
- kit colour jitter, random sun and ambient light.
Rendered with Cycles (CPU) in the reference camera (data/games/nm26-semifinal/camera-ref.json) as an RGBA crop of the
goal box; the ice is a shadow catcher; goals, boards and screens are holdouts (they are in the real background plate).
Writes <out_dir>/<seed>.png and appends one JSON line per sample to <out_dir>/labels.jsonl.
"""
import json
import math
import random
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix
from mathutils.bvhtree import BVHTree

REPO = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
SEED0, COUNT = int(sys.argv[2]), int(sys.argv[3])
ENDS = sys.argv[4] if len(sys.argv) > 4 else "both"; KIT = sys.argv[5] if len(sys.argv) > 5 else "ref"
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
BOX = CAM["goal_crop_boxes_video_px"]
G = json.loads((REPO / "data/geometry.json").read_text())
SLOT = {f["player_id"]: np.array(f["centreline"]["points_mm"], float) for f in G["fixture_paths"]}
HOME = {"W": 0.0, "E": 180.0}
DISTRACT = {"W": ["W-LD", "W-RD", "E-LW", "E-RW", "E-C"], "E": ["E-LD", "E-RD", "W-LW", "W-RW", "W-C"]}

bpy.ops.wm.open_mainfile(filepath=str(REPO / "assets/scene/full_static.blend"))
sc = bpy.context.scene


def set_camera():
    K, R, t = np.array(CAM["K"]), np.array(CAM["R"]), np.array(CAM["t_mm"])
    cam = bpy.data.cameras.new("NM26Ref"); ob = bpy.data.objects.new("NM26Ref", cam); sc.collection.objects.link(ob)
    W, H = CAM["image_size"]
    cam.sensor_fit = "HORIZONTAL"; cam.sensor_width = 36.0; cam.lens = K[0, 0] * 36.0 / W
    cam.shift_x = (W / 2 - K[0, 2]) / W; cam.shift_y = (K[1, 2] - H / 2) / W; cam.clip_start = 0.05; cam.clip_end = 20
    M = np.eye(4); M[:3, :3] = R.T @ np.diag([1, -1, -1]); M[:3, 3] = -R.T @ t / 1000.0
    ob.matrix_world = Matrix(M.tolist()); sc.camera = ob
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100


def arc_point(P, u):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = u * seg.sum(); acc = np.r_[0, np.cumsum(seg)]
    k = min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1); f = (s - acc[k]) / seg[k]
    return P[k] + f * (P[k + 1] - P[k]), s


def place(ob, pid, u, theta):
    p, s = arc_point(SLOT[pid], u); head = HOME[pid[0]] + theta
    ob.matrix_world = Matrix.Translation((p[0] / 1000, p[1] / 1000, 0)) @ Matrix.Rotation(math.radians(head), 4, "Z")
    return p, s, head


def tree(ob):
    dg = bpy.context.evaluated_depsgraph_get(); e = ob.evaluated_get(dg); me = e.to_mesh()
    t = BVHTree.FromPolygons([ob.matrix_world @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]); e.to_mesh_clear()
    return t


set_camera()
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 8; sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"  # AgX washes out the saturated kits
sc.render.film_transparent = True; sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.render.use_border = True; sc.render.use_crop_to_border = True
for n in ("Ice",):
    bpy.data.objects[n].is_shadow_catcher = True
for o in bpy.data.objects:
    if o.type == "MESH" and (o.name.startswith(("Goal.", "InnerBoards", "EndScreen", "Housing"))):
        o.is_holdout = True
figs = {o["player_id"]: o for o in bpy.data.objects if o.name.startswith("Figure.")}
kit = {o.name: tuple(o.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value) for o in bpy.data.materials
       if o.use_nodes and o.node_tree.nodes.get("Principled BSDF") and o.name.startswith(("fig_kit", "fig_blue"))}
W_VARIANTS = {}
if KIT == "nm26":
    gw = figs["W-G"]; names = [sl.material.name for sl in gw.material_slots]; ki, bi = names.index("fig_kit_FIN"), names.index("fig_blue")
    W_VARIANTS["ref"] = gw.data
    for hem in (22, 26, 30):  # NM26 W goalie: blue legs and pads below the white jersey (hem height not measured)
        me = gw.data.copy(); me.name = f"goalie_W_nm26_hem{hem}"
        for poly in me.polygons:
            if poly.material_index == ki and poly.center.z < hem / 1000: poly.material_index = bi
        W_VARIANTS[f"hem{hem}"] = me
    import cv2  # "1" back print: the reference print's "1" moved to the centre, the "3" removed
    tex = REPO / "out/synth/textures/print_goalie_FIN_1.png"; tex.parent.mkdir(parents=True, exist_ok=True)
    a = cv2.imread(str(REPO / "assets/figures/textures/print_goalie_FIN_31.png"), cv2.IMREAD_UNCHANGED); b = a.copy()
    b[340:930, 230:920] = 0; one = a[340:930, 660:920]; x0 = (a.shape[1] - one.shape[1]) // 2; b[340:930, x0:x0 + one.shape[1]] = one
    cv2.imwrite(str(tex), b)
    pm = figs["W-G"].children[0].material_slots[0].material
    for nd in pm.node_tree.nodes:
        if nd.type == "TEX_IMAGE": nd.image = bpy.data.images.load(str(tex))
sun = bpy.data.objects["Sun"]
world = sc.world; bg = world.node_tree.nodes.get("Background") if world and world.use_nodes else None
lab = open(OUT / "labels.jsonl", "a")
for seed in range(SEED0, SEED0 + COUNT):
    rnd = random.Random(seed)
    end = ("W" if seed % 2 == 0 else "E") if ENDS == "both" else ENDS
    kit_variant = "ref"
    if W_VARIANTS and end == "W":
        kit_variant = "ref" if rnd.random() < 0.15 else rnd.choice(["hem22", "hem26", "hem30"]); figs["W-G"].data = W_VARIANTS[kit_variant]
    x0, y0, x1, y1 = BOX[end]
    W, H = CAM["image_size"]
    sc.render.border_min_x, sc.render.border_max_x = x0 / W, x1 / W
    sc.render.border_min_y, sc.render.border_max_y = 1 - y1 / H, 1 - y0 / H
    for pid, o in figs.items():
        o.hide_render = True
        for c in o.children: c.hide_render = True
    gid = f"{end}-G"; g = figs[gid]; g.hide_render = False
    for c in g.children: c.hide_render = rnd.random() < 0.3
    u, th = rnd.random(), rnd.uniform(0, 360)
    pv, s, head = place(g, gid, u, th)
    # overlap test by pivot distance (a figure's blade reaches about 35 mm from its axis; mesh BVH tests were too slow)
    dist = []; piv = [pv]
    for pid in rnd.sample(DISTRACT[end], rnd.randint(0, 3)):
        o = figs[pid]; ud = rnd.random(); thd = rnd.uniform(0, 360); pd, _, _ = place(o, pid, ud, thd)
        if min(np.linalg.norm(pd - q) for q in piv) < 75:
            continue
        o.hide_render = False
        for c in o.children: c.hide_render = False
        piv.append(pd); dist.append({"id": pid, "u": round(ud, 4), "theta_deg": round(thd, 2)})
    pk = bpy.data.objects["Puck"]; puck = None
    if rnd.random() < 0.5:
        gx = -255 if end == "W" else 255
        px, py = gx + rnd.uniform(-60, 110) * (1 if end == "W" else -1), rnd.uniform(-90, 90)
        if min(np.linalg.norm(np.array([px, py]) - q) for q in piv) < 50:
            pk.hide_render = True
        else:
            pk.location = (px / 1000, py / 1000, pk.location.z); pk.hide_render = False; puck = [round(px, 1), round(py, 1)]
    else:
        pk.hide_render = True
    for name, base in kit.items():
        # the NM26 yellow kit is a saturated yellow, not the reference variant's orange-yellow (compare docs/synthetic-goalie-pilot.md)
        base = (0.80, 0.56, 0.01) if "SWE" in name else base
        # NM26 W blue: darker and more saturated than the reference blue (real crops sRGB median (34, 57, 116) against
        # the first renders' (75, 96, 146), then (63, 73, 122); base colour scaled per channel in linear light), wider jitter
        nm26_blue = KIT == "nm26" and name == "fig_blue"
        base = (0.004, 0.03, 0.25) if nm26_blue else base; j = (0.75, 1.25) if nm26_blue else (0.85, 1.15)
        m = bpy.data.materials[name]; c = np.array(base[:3]) * rnd.uniform(*j) + np.array([rnd.uniform(-0.02, 0.02) for _ in range(3)])
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*np.clip(c, 0, 1), 1)
    sun.rotation_euler = (math.radians(rnd.uniform(5, 50)), 0, math.radians(rnd.uniform(0, 360)))
    sun.data.energy = rnd.uniform(1.5, 5.0)
    if bg: bg.inputs["Strength"].default_value = rnd.uniform(0.3, 1.2)
    sc.cycles.seed = seed
    sc.render.filepath = str(OUT / f"{seed}.png")
    bpy.ops.render.render(write_still=True)
    lab.write(json.dumps({"seed": seed, "end": end, "u": round(u, 5), "s_mm": round(float(s), 2), "theta_deg": round(th, 3),
                          "heading_deg": round(head, 3), "pivot_mm": [round(float(pv[0]), 2), round(float(pv[1]), 2)],
                          "distractors": dist, "puck_mm": puck, "kit": KIT if end == "W" else "ref",
                          "kit_variant": kit_variant}) + "\n"); lab.flush()
