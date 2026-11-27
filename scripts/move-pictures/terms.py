#!/usr/bin/env python3
"""Reference pictures of the grips and catches the move texts name (docs/move-pictures.md, "Term pictures").

One close-up per term from straight above: the skater, the puck where build.py's GRIPS puts it, a short label. These
are reusable templates: every move picture that names a groove uses the same local puck position.

  python3 scripts/move-pictures/terms.py            # writes out/move-pictures/terms-jobs.json
  MOVE_PICTURES_JOBS=out/move-pictures/terms-jobs.json node scripts/move-pictures/render.ts
  python3 scripts/move-pictures/terms.py --draw     # validation/move-pictures/terms/<id>.png and terms-sheet.png
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import build as B  # noqa: E402

OUT = B.OUT
VAL = B.REPO / "validation/move-pictures/terms"
W = H = 900
SPAN_MM = 130.0  # width of the view

# id, title, line under it, figure, arc mm, theta deg, grip, status
TERMS = [
    ("heel-groove", "Hælgrop / heel groove", "Pucken mellom skøyta og hælen på kølla, bak kølla",
     "W-C", 200.0, 0.0, "heel", "user rule 2026-11-27"),
    ("heel-groove-carry", "Edwall-drag (hælgrop)", "Høyrewing: kølla ca. 45° mot høyre vant, pucken i hælgropa",
     "W-RW", 150.0, B.HEEL_CARRY_THETA, "heel", "user rule 2026-11-27"),
    ("stick-groove", "Køllegrop / stick groove", "Pucken foran kølla, inntil skøyta",
     "W-C", 200.0, 0.0, "stick", "assumed, please check"),
    ("toe-groove", "Tågrop / toe groove", "Pucken rett foran skøytetuppen",
     "W-C", 200.0, 0.0, "toe", "assumed, please check"),
    ("back-catch", "Mottak med ryggen", "Senteren tar imot med ryggen mot høyrewingen",
     "W-C", 225.0, 100.0, "back", "user rule 2026-11-27"),
]


def all_pids():
    return list(B.default_poses().keys()) + list(B.GOALIES.keys())


def jobs():
    out, meta = [], []
    for tid, title, line, pid, arc, th, grip, status in TERMS:
        slot = B.Slot(pid)
        piv = slot.at(arc)
        local = np.array(B.GRIPS[grip], float)
        puck = piv + B.rot(B.HOME[pid[0]] + th) @ local
        cx, cy = (piv + puck) / 2
        dist = 400.0
        fov = float(np.degrees(2 * np.arctan(SPAN_MM / 2 / dist)))
        poses = {k: v for k, v in B.default_poses().items()}
        poses.update(B.GOALIES)
        poses[pid] = {"arc_mm": arc, "theta_deg": th}
        poses = {k: {"arc_mm": v["arc_mm"], "theta_deg": v["theta_deg"]} for k, v in poses.items()}
        out.append({"id": f"term-{tid}", "poses": poses, "puckMm": [round(float(puck[0]), 2), round(float(puck[1]), 2)],
                    "hidden": [k for k in all_pids() if k != pid],
                    "camera": {"positionMm": [float(cx), float(cy), dist], "targetMm": [float(cx), float(cy), 0.0],
                               "upMm": [1, 0, 0], "fovDeg": round(fov, 4)},
                    "widthPx": W, "heightPx": H, "background": "#%02x%02x%02x" % B.NAVY})
        meta.append({"id": tid, "title": title, "line": line, "pid": pid, "arc_mm": arc, "theta_deg": th,
                     "grip": grip, "puck_local_mm": B.GRIPS[grip], "status": status})
    return out, meta


def draw(meta):
    VAL.mkdir(parents=True, exist_ok=True)
    tiles = []
    for m in meta:
        im = Image.open(OUT / f"term-{m['id']}-base.png").convert("RGB")
        band = 150
        t = Image.new("RGB", (im.width, im.height + band), B.NAVY)
        t.paste(im, (0, band))
        d = ImageDraw.Draw(t)
        d.text((30, 22), m["title"], font=ImageFont.truetype(B.FONT, 56), fill=(255, 255, 255))
        d.text((30, 92), m["line"], font=ImageFont.truetype(B.FONT, 34), fill=(200, 215, 235))
        if "assumed" in m["status"]:
            d.text((im.width - 30, 30), "UTKAST", font=ImageFont.truetype(B.FONT, 40), fill=(255, 200, 60), anchor="ra")
        t.save(VAL / f"{m['id']}.png")
        tiles.append(t)
        print("wrote", (VAL / f"{m['id']}.png").relative_to(B.REPO))
    tw, th_ = tiles[0].size
    s = 0.5
    sheet = Image.new("RGB", (int(tw * s) * len(tiles), int(th_ * s)), B.NAVY)
    for i, t in enumerate(tiles):
        sheet.paste(t.resize((int(tw * s), int(th_ * s)), Image.LANCZOS), (i * int(tw * s), 0))
    sheet.save(VAL / "terms-sheet.png")
    (VAL / "terms.json").write_text(json.dumps({"description": "term pictures (PROPOSED); puck positions from scripts/move-pictures/build.py GRIPS, skater local mm (x forward, y to the stick side)", "terms": meta}, indent=1, ensure_ascii=False) + "\n")
    print("wrote", (VAL / "terms-sheet.png").relative_to(B.REPO))


if __name__ == "__main__":
    js, meta = jobs()
    if "--draw" in sys.argv:
        draw(meta)
    else:
        (OUT / "terms-jobs.json").write_text(json.dumps(js, indent=1) + "\n")
        print("wrote", (OUT / "terms-jobs.json").relative_to(B.REPO), len(js), "jobs")
