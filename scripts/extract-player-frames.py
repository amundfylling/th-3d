"""Player-figure references: decode the user's HEIC photos and selected MP4 frames into cropped JPEG stills.

    /root/venvs/blender/bin/python scripts/extract-player-frames.py
Needs pillow-heif and imageio-ffmpeg (docs/tools.md). The originals in references/players_images/ are only
read. Outputs references/derived/players/<id>.jpg (full-resolution crops around the figure) and
references/derived/players/manifest.json (source hash, timestamp, crop box, full frame size and camera
hints, so a pinhole camera can be fitted in full-frame pixel coordinates later).
Video frames are HLG/BT.2020 10-bit; they are tone-mapped to BT.709 SDR with a fixed ffmpeg filter chain.
"""
import hashlib
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import pillow_heif
from PIL import Image
from PIL.ExifTags import TAGS

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "references" / "players_images"
OUT = REPO / "references" / "derived" / "players"
pillow_heif.register_heif_opener()
TONEMAP = "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=rgb24"
VIDEO_GOALIE = "IMG_2573_under25MB(1).mp4"
VIDEO_SKATER = "IMG_2574_under25MB(1).mp4"

# id: (source file, time s or None, figure, view note). Views were chosen from 4 fps contact sheets.
# In 0-12 s of each video the camera is (nearly) still and the figure is turned on the table by a finger.
SELECT = {
    "goalie-photo-front": ("IMG_2564 2.HEIC", None, "goalie", "front, camera slightly above"),
    "goalie-photo-front-oblique": ("IMG_2565 2.HEIC", None, "goalie", "front, turned slightly to the goalie's right"),
    "goalie-photo-back": ("IMG_2566 2.HEIC", None, "goalie", "back, from above"),
    "goalie-photo-top": ("IMG_2567 2.HEIC", None, "goalie", "near top-down, back up"),
    "goalie-photo-underside": ("IMG_2568 2.HEIC", None, "goalie", "lying face down, feet toward camera: mount socket under the right skate"),
    "goalie-photo-lying-side": ("IMG_2569 2.HEIC", None, "goalie", "lying on its side"),
    "goalie-photo-lying-back": ("IMG_2570 2.HEIC", None, "goalie", "lying face down, from above: back print"),
    "goalie-photo-lying-back-2": ("IMG_2571 2.HEIC", None, "goalie", "lying face down, oblique: back print"),
    "goalie-photo-side": ("IMG_2572 2.HEIC", None, "goalie", "standing, goalie's right side"),
    "goalie-video-t00.50": (VIDEO_GOALIE, 0.5, "goalie", "front from above (turntable)"),
    "goalie-video-t05.00": (VIDEO_GOALIE, 5.0, "goalie", "side from above (turntable)"),
    "goalie-video-t07.75": (VIDEO_GOALIE, 7.75, "goalie", "back from above (turntable)"),
    "goalie-video-t12.25": (VIDEO_GOALIE, 12.25, "goalie", "front, low camera"),
    "goalie-video-t16.75": (VIDEO_GOALIE, 16.75, "goalie", "near top-down"),
    "skater-video-t00.00": (VIDEO_SKATER, 0.0, "skater", "front-left from above (turntable)"),
    "skater-video-t01.50": (VIDEO_SKATER, 1.5, "skater", "turntable"),
    "skater-video-t03.00": (VIDEO_SKATER, 3.0, "skater", "turntable"),
    "skater-video-t04.50": (VIDEO_SKATER, 4.5, "skater", "turntable, profile"),
    "skater-video-t06.00": (VIDEO_SKATER, 6.0, "skater", "turntable, back-left"),
    "skater-video-t07.25": (VIDEO_SKATER, 7.25, "skater", "turntable, back"),
    "skater-video-t08.50": (VIDEO_SKATER, 8.5, "skater", "turntable, back-right"),
    "skater-video-t09.75": (VIDEO_SKATER, 9.75, "skater", "turntable, right"),
    "skater-video-t10.75": (VIDEO_SKATER, 10.75, "skater", "turntable, front-right"),
    "skater-video-t11.75": (VIDEO_SKATER, 11.75, "skater", "held, underside of the left skate: mount socket"),
    "skater-video-t13.25": (VIDEO_SKATER, 13.25, "skater", "front, camera high"),
    "skater-video-t14.50": (VIDEO_SKATER, 14.5, "skater", "front, camera high"),
    "skater-video-t22.60": (VIDEO_SKATER, 22.6, "skater", "held, front: socket under the left skate, stick"),
}

# Manual crop boxes (full-frame px) where the automatic colour box misses the figure: at 12.25 s the lit
# helmet separates from the body mask; at 16.75 s the light wooden floor passes the yellow test.
CROP_OVERRIDE = {"goalie-video-t12.25": [150, 800, 2000, 2700], "goalie-video-t16.75": [100, 1450, 1500, 2550]}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def video_frame(path: Path, t: float) -> Image.Image:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    probe = subprocess.run([ff, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    import re
    w, h = [int(v) for v in re.search(r"Video:.*?, (\d{3,5})x(\d{3,5})", probe).groups()]
    raw = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                          "-vf", TONEMAP, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return Image.frombytes("RGB", (w, h), raw)


def figure_box(im: Image.Image, margin: float = 0.25):
    """Bounding box of saturated figure plastic (blue/yellow/peach) nearest the frame centre."""
    small = im.resize((im.width // 8, im.height // 8))
    hsv = np.asarray(small.convert("HSV")).astype(int)
    rgb = np.asarray(small).astype(int)
    blue = (hsv[..., 0] > 135) & (hsv[..., 0] < 175) & (hsv[..., 1] > 110) & (hsv[..., 2] > 70)
    yellow = (rgb[..., 0] > 150) & (rgb[..., 1] > 110) & (rgb[..., 2] < 70) & (rgb[..., 0] - rgb[..., 2] > 110)
    import cv2
    # dilate so the helmet, jersey, legs and skates (separated by shading and seams) merge into one component
    mask = cv2.dilate((blue | yellow).astype(np.uint8), np.ones((9, 9), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(mask, 8)
    if n <= 1:
        raise RuntimeError("no figure pixels")
    # the largest component (the photographed figure; the second figure in the background is smaller)
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h = stats[k, :4]
    x0, y0, x1, y1 = x * 8, y * 8, (x + w) * 8, (y + h) * 8
    mx, my = int((x1 - x0) * margin) + 120, int((y1 - y0) * margin) + 120
    return [int(v) for v in (max(0, x0 - mx), max(0, y0 - my), min(im.width, x1 + mx), min(im.height, y1 + my))]


def exif(im):
    ex = im.getexif()
    d = {TAGS.get(k, k): v for k, v in list(ex.items()) + list(ex.get_ifd(0x8769).items())}
    return {k: (float(d[k]) if k.startswith("Focal") else str(d[k])) for k in ("Model", "LensModel", "FocalLength", "FocalLengthIn35mmFilm", "DateTimeOriginal") if k in d}


OUT.mkdir(parents=True, exist_ok=True)
manifest = {
    "description": "Cropped stills from the user's figure photos and videos (references/players_images, uploaded to main 2026-09-30). Crops are full resolution; crop_box_px is in full-frame pixels [x0, y0, x1, y1]. Generated by scripts/extract-player-frames.py; originals unchanged.",
    "tone_mapping_video": TONEMAP,
    "items": {},
}
hashes = {}
for fid, (fname, t, fig, note) in SELECT.items():
    src = SRC / fname
    hashes.setdefault(fname, sha256(src))
    if t is None:
        im = Image.open(src)
        meta = exif(im)
        im = im.convert("RGB")
    else:
        im = video_frame(src, t)
        meta = {"video_fps": 30, "note": "iPhone 15 video; focal length not recorded in the frame"}
    box = CROP_OVERRIDE.get(fid) or figure_box(im)
    crop = im.crop(box)
    out = OUT / f"{fid}.jpg"
    crop.save(out, quality=90)
    manifest["items"][fid] = {
        "source_file": f"references/players_images/{fname}", "source_sha256": hashes[fname], "time_s": t, "figure": fig,
        "team": "Sweden", "view": note, "full_size_px": [im.width, im.height], "crop_box_px": box, "camera": meta,
        "file": f"references/derived/players/{fid}.jpg", "sha256": sha256(out),
    }
    print(fid, box, crop.size)
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
