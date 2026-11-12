"""Move pictures: where every figure stands and how it is turned in each puck.no picture (docs/move-pictures.md).

    python3 scripts/move-pictures/detect.py [ids...]   -> data/move-pictures/detected/<id>.json, out/move-pictures/detect/<id>.png

puck.no draws every skater with one sprite (yellow or white jersey) rotated in the picture plane. The sprite is cut from
the Agdur picture (the attackers' right wing, which nothing overlaps) and matched at every position and rotation
(colour-class correlation: jersey, navy parts, dark outline and stick). A detection is the sprite's peg point in
picture px and its rotation phi (deg, counter-clockwise on the screen, 0 = the Agdur right wing).
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
PICS = REPO / "references/combinations/puck-no-pictures"
OUT = REPO / "out/move-pictures/detect"
DET = REPO / "data/move-pictures/detected"
PEG = (496, 308)  # sprite peg in the Agdur picture (px); refined by PEG_SHIFT below
HALF = 56
STEP = 2


def classes(rgb):
    r, g, b = [rgb[..., i].astype(int) for i in range(3)]
    yellow = (r > 130) & (g > 130) & (b < 110) & (abs(r - g) < 50)
    navy = (b > r + 25) & (b > g + 15) & (b > 60) & (r < 140)
    dark = (r < 90) & (g < 90) & (b < 100) & ~navy
    white = (r > 225) & (g > 225) & (b > 225)
    return {"yellow": yellow, "navy": navy, "dark": dark, "white": white}


def load(path):
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    im = Image.alpha_composite(bg, im).convert("RGB")
    if im.width != 600:
        im = im.resize((600, round(im.height * 600 / im.width)), Image.LANCZOS)
    return np.array(im)


def template():
    rgb = load(PICS / "trick-agdur-d68ac5fd.png")
    u0, v0 = PEG[0] - HALF, PEG[1] - HALF
    crop = rgb[v0:v0 + 2 * HALF + 1, u0:u0 + 2 * HALF + 1]
    c = classes(crop)
    fg = c["yellow"] | c["navy"] | c["dark"]
    # the slot line under the sprite (black column) is not part of it outside the body
    vv, uu = np.mgrid[0:fg.shape[0], 0:fg.shape[1]]
    slot = (abs(uu + u0 - 496) <= 5) & ((vv + v0 < 281) | (vv + v0 > 327))
    fg &= ~slot
    n, lab = cv2.connectedComponents(fg.astype(np.uint8), connectivity=8)
    keep = lab == lab[PEG[1] - v0 - 4, PEG[0] - u0 + 2]  # a jersey pixel
    # the stick is one component with the body through its outline; make sure by dilating once
    n, lab = cv2.connectedComponents(cv2.dilate(fg.astype(np.uint8), np.ones((3, 3), np.uint8)), connectivity=8)
    keep = (lab == lab[PEG[1] - v0 - 4, PEG[0] - u0 + 2]) & fg
    support = cv2.dilate(keep.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    t = {k: (c[k] & keep) for k in ("yellow", "navy", "dark")}
    return t, support, crop


def rotated(mask, phi):
    M = cv2.getRotationMatrix2D((HALF, HALF), phi, 1.0)
    return cv2.warpAffine(mask.astype(np.float32), M, mask.shape[::-1], flags=cv2.INTER_LINEAR)


def score_maps(img_c, t, support, phi, team):
    sup = rotated(support, phi)
    jersey_t = rotated(t["yellow"], phi)
    navy_t = rotated(t["navy"], phi)
    dark_t = rotated(t["dark"], phi)
    jimg = img_c["yellow" if team == "yellow" else "white"].astype(np.float32)
    s = cv2.matchTemplate(jimg, (2 * jersey_t - sup) if team == "yellow" else (jersey_t - 0.3 * (navy_t + dark_t)), cv2.TM_CCORR)
    if team == "white":  # no yellow anywhere on a white sprite
        s -= cv2.matchTemplate(img_c["yellow"].astype(np.float32), sup, cv2.TM_CCORR)
    s += 1.5 * cv2.matchTemplate(img_c["navy"].astype(np.float32), 2 * navy_t - sup, cv2.TM_CCORR)
    s += 0.7 * cv2.matchTemplate(img_c["dark"].astype(np.float32), 2 * dark_t - 0.5 * sup, cv2.TM_CCORR)
    return s


def detect(rgb, t, support):
    c = classes(rgb)
    pad = HALF
    cp = {k: np.pad(v, pad) for k, v in c.items()}
    norm = float(t["yellow"].sum() + 1.5 * t["navy"].sum() + 0.7 * t["dark"].sum())
    out = []
    for team in ("yellow", "white"):
        best, arg = None, None
        phis = np.arange(0, 360, STEP)
        for i, phi in enumerate(phis):
            s = score_maps(cp, t, support, phi, team)
            if best is None:
                best, arg = s.copy(), np.zeros(s.shape, int)
            else:
                m = s > best
                best[m], arg[m] = s[m], i
        b = best.copy()
        while True:
            v, u = np.unravel_index(np.argmax(b), b.shape)
            sc = b[v, u] / norm
            if sc < 0.42:
                break
            # refine the rotation at this spot
            fine = [(float(score_maps({k: x[v:v + 2 * HALF + 1, u:u + 2 * HALF + 1] for k, x in cp.items()}, t, support, p, team)[0, 0]), p)
                    for p in np.arange(phis[arg[v, u]] - STEP, phis[arg[v, u]] + STEP + 0.1, 0.5)]
            out.append({"team": team, "u": int(u), "v": int(v), "phi": round(float(max(fine)[1]) % 360, 1), "score": round(float(sc), 3)})
            cv2.circle(b, (int(u), int(v)), 26, -1e9, -1)
    # one sprite, one detection: where both colours answer at one spot, the better one stands
    out.sort(key=lambda d: -d["score"])
    keep = []
    for d in out:
        if all((d["u"] - k["u"]) ** 2 + (d["v"] - k["v"]) ** 2 > 24 ** 2 for k in keep):
            keep.append(d)
    return keep


def stamp(rgb, t, det):
    """The detection drawn back over the picture (magenta outline of the sprite, cyan peg) for review."""
    im = rgb.copy()
    sil = (t["yellow"] | t["navy"] | t["dark"]).astype(np.uint8)
    for d in det:
        r = rotated(sil, d["phi"]) > 0.5
        edge = r & ~cv2.erode(r.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        vs, us = np.nonzero(edge)
        vs, us = vs + d["v"] - HALF, us + d["u"] - HALF
        ok = (vs >= 0) & (vs < im.shape[0]) & (us >= 0) & (us < im.shape[1])
        im[vs[ok], us[ok]] = (255, 0, 255) if d["team"] == "yellow" else (0, 160, 255)
        cv2.circle(im, (d["u"], d["v"]), 2, (0, 255, 255), -1)
        cv2.putText(im, f"{d['phi']:.0f} {d['score']:.2f}", (d["u"] + 8, d["v"] - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (255, 0, 255), 1, cv2.LINE_AA)
    return im


def main():
    t, support, crop = template()
    OUT.mkdir(parents=True, exist_ok=True)
    DET.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.dstack([t["yellow"] * 255, t["dark"] * 255, t["navy"] * 255]).astype(np.uint8)).resize((452, 452), Image.NEAREST).save(OUT / "_template.png")
    want = sys.argv[1:]
    for p in sorted((REPO / "data/move-pictures").glob("*.json")):
        spec = json.loads(p.read_text())
        if "puck_no_picture" not in spec or (want and spec["id"] not in want):
            continue
        rgb = load(REPO / spec["puck_no_picture"])
        det = detect(rgb, t, support)
        (DET / f"{spec['id']}.json").write_text(json.dumps({"id": spec["id"], "picture": spec["puck_no_picture"], "note": "sprite detections: peg (u, v) in px of the 600 px wide picture, phi deg counter-clockwise on screen (0 = the Agdur right wing sprite)", "figures": det}, indent=1) + "\n")
        Image.fromarray(stamp(rgb, t, det)).resize((rgb.shape[1] * 2, rgb.shape[0] * 2), Image.LANCZOS).save(OUT / f"{spec['id']}.png")
        print(spec["id"], len(det), [(d["team"][0], d["u"], d["v"], d["phi"], d["score"]) for d in det])


if __name__ == "__main__":
    main()
