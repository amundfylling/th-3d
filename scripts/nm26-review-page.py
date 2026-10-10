"""Review page for one NM 2026 game's pass candidates: validation/nm26-<game>-review.html.

    /root/venvs/blender/bin/python scripts/nm26-review-page.py g1

Inputs: data/games/nm26-semifinal/<game>/{passes.json, calibration.json}, out/nm26/<game>/frames.json, the video,
data/geometry.json. Template: scripts/nm26-review.template.html (this script injects the data).

For every candidate (pass, turnover, shot, loose; at least MIN_LEN_MM long) it cuts three registered frames from the
video (release, middle, reception), crops them around the measured line, and draws the line thinly on the first and
last. Claude's review (<game>/review-claude.json: verdict and confidence 0-100 per candidate) is shown on each card
when present. The page stores the user's verdicts in the artifact's db (collections "reviews" and "missed"); Claude reads them
back with ArtifactData.
"""
import base64
import sys

import cv2
import numpy as np

from nm26_common import CFG, FPS, OUT, REPO, T_ROI, W_STAB, H_STAB, frames, game_dir, load, proj

GAME = sys.argv[1] if len(sys.argv) > 1 else "g1"
MIN_LEN_MM = 100.0
KINDS = ("pass", "turnover", "shot", "loose", "loose_received")
P = load(game_dir(GAME) / "passes.json")
Hc = np.array(load(game_dir(GAME) / "calibration.json")["H_world_mm_to_stab_px"])
Fr = {f[0]: f for f in load(OUT / GAME / "frames.json")}
G = load(REPO / "data/geometry.json")
CG = CFG["games"][GAME]
HW = load(REPO / "validation/12-hardware-report.json")["goal"]
EV = [e for e in P["events"] if e["kind"] in KINDS and e["length_mm"] >= MIN_LEN_MM]
# Claude's own review (verdict + confidence per candidate), when it exists
RC = game_dir(GAME) / "review-claude.json"
CL = {r["id"]: {k: r[k] for k in ("verdict", "confidence", "why", "fix") if k in r} for r in load(RC)["events"]} if RC.exists() else {}
want = {}
for n, e in enumerate(EV):
    mid = (e["frame_release"] + e["frame_reception"]) // 2
    for tag, f in (("rel", e["frame_release"]), ("mid", mid), ("rec", e["frame_reception"])):
        want.setdefault(f, []).append((n, tag))
crops = {}
t0, t1 = min(want) / FPS - 0.05, max(want) / FPS + 0.1
for i, a in frames(t0, t1):
    if i not in want:
        continue
    H = np.r_[Fr[i][2], 1].reshape(3, 3)
    w = cv2.warpPerspective(a, T_ROI @ H, (W_STAB, H_STAB), flags=cv2.INTER_LINEAR)
    for n, tag in want[i]:
        L = proj(Hc, EV[n]["line_mm"])
        x0, y0 = np.maximum(L.min(0) - 60, 0).astype(int)
        x1, y1 = np.minimum(L.max(0) + 60, [W_STAB, H_STAB]).astype(int)
        # keep a 16:9-ish box at least 260 px wide
        cx, cy, bw, bh = (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, 260), max(y1 - y0, 150)
        bw, bh = max(bw, bh * 1.6), max(bh, bw / 1.6)
        x0, x1 = int(max(0, cx - bw / 2)), int(min(W_STAB, cx + bw / 2))
        y0, y1 = int(max(0, cy - bh / 2)), int(min(H_STAB, cy + bh / 2))
        g = w.copy()
        if tag != "mid":
            cv2.polylines(g, [L.astype(np.int32)], False, (0, 220, 0), 1, cv2.LINE_AA)
            end = L[0] if tag == "rel" else L[-1]
            cv2.circle(g, tuple(end.astype(int)), 16, (0, 220, 0), 1, cv2.LINE_AA)
        c = g[y0:y1, x0:x1]
        c = cv2.resize(c, (360, int(360 * c.shape[0] / c.shape[1])), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", c, [cv2.IMWRITE_JPEG_QUALITY, 72])
        crops[(n, tag)] = "data:image/jpeg;base64," + base64.b64encode(buf).decode()

TEAM = {"W": CG["team_W"], "E": CG["team_E"]}
NAMES = {k: v["name"].split()[-1] for k, v in CFG["players"].items()}
M = np.array(G["image_to_world"][0]["matrix"]).reshape(3, 3)
LM = {l["id"]: proj(M, [l["px"]])[0] for l in G["landmarks"] if l["source_image_id"] == "stiga_se_fi_overhead"}
lines = [{"kind": k, "a": [round(float(v), 1) for v in LM[f"lm.board.{n}.top"]], "b": [round(float(v), 1) for v in LM[f"lm.board.{n}.bottom"]]}
         for n, k in [("goal_line.W", "red"), ("blue_line.W", "blue"), ("centre_line", "red"), ("blue_line.E", "blue"), ("goal_line.E", "red")]]
DATA = {
    "game": GAME, "title": "Nygård vs Fjermestad · NM 2026 semi-final · game 1" if GAME == "g1" else GAME,
    "result": CG.get("result_nygard_fjermestad", ""), "teams": TEAM, "names": NAMES,
    # the figures stay with the table ends, so the kit colour follows the end, not the player (config.json)
    "kits": {k: CFG["figure_colours_by_end"][k] for k in "WE"},
    "board": [[round(x, 1), round(y, 1)] for x, y in G["board"]["inner_boundary"]["world"]["points_mm"][::3]],
    "lines": lines,
    "slots": {f["player_id"]: [[round(x, 1), round(y, 1)] for x, y in f["centreline"]["points_mm"][::2]] for f in G["fixture_paths"]},
    "goals": {t: {"x": HW["placement_mm"][t][0], "y": HW["placement_mm"][t][1], "w": HW["mouth_width_per_goal_mm"][t], "d": HW["depth_per_goal_mm"][t]} for t in "WE"},
    "events": [{
        "id": f"{GAME}-{e['frame_release']}", "kind": e["kind"], "from": e["from"], "to": e["to"],
        "uncertain": e["from_uncertain"] or e["to_uncertain"], "t": e["t_release_s"], "t_end": e["t_reception_s"],
        "line": e["line_mm"], "len": e["length_mm"], "speed": e["speed_mm_s"][1], "bounces": e["bounces"],
        "img": [crops.get((n, tag), "") for tag in ("rel", "mid", "rec")],
        "claude": CL.get(f"{GAME}-{e['frame_release']}"),
    } for n, e in enumerate(EV)],
}
import json
tpl = (REPO / "scripts/nm26-review.template.html").read_text()
out = tpl.replace("/*__DATA__*/null", json.dumps(DATA, separators=(",", ":")))
dst = REPO / f"validation/nm26-{GAME}-review.html"
dst.write_text(out)
print("events", len(EV), "bytes", len(out))
