"""Rebuild the NM26 outputs step by step, from the video and the frame cache (docs/pipeline.md).

    python3 scripts/pipeline/nm26_rebuild.py [stage ...] [--check] [--list] [--games g1,g2] [--keep-going]

Stages, in order (default: every stage marked "default" below):
- fetch     the broadcast video from the GitHub release (config.json url), checked against its sha256;
- cache     register every frame and find puck candidates (scripts/nm26-detect.py): out/nm26/<game>/frames.json;
- calibrate rink-plane calibration of game 1 (the reference frame all games are registered to);
- meshes    the figure meshes (out/figures/*.npz, Blender) that nm26-passes.py reads the reach of a figure from;
- puck      puck track, flights and passes per game, cross-game patterns;
- figures   cleaned figure tracks, figure analysis, tactics boards (committed tracks only: no video, no models);
- analysis  combination recognition and the old/synthetic puck-track comparison (committed tracks and labels only);
- sheets    checking sheets drawn on the video frames;
- pages     the pass review page (game 1), the goal clips and goal review page, the all-goals replays;
- edwall    the Edwall hat-trick traces and video specs from their fitted inputs (not default; videos rendered outside);
- models    renders, training and tracking of the figure (v2, v3) and puck (synthetic detector) models (hours;
            out/synth/*.pt are not committed). Never run by default.

Every step names its inputs and outputs. A step whose inputs or Python modules are missing is SKIPPED with the reason;
nothing is faked. --check compares the outputs that git tracks with the committed versions afterwards (git status and,
for JSON, the share of rows that differ) and writes out/pipeline/rebuild-report.json. --list prints the steps and
whether each can run here. Step commands run with $NM26_PY, else /root/venvs/blender/bin/python (docs/blender.md),
else this interpreter. Status of every rebuilt output: as the script that writes it says (PROPOSED for all NM26 tracks).
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = "data/games/nm26-semifinal"
CFG = json.loads((REPO / DATA / "config.json").read_text())
GAMES = [f"g{k}" for k in range(1, 8)]
HATTRICK = ["g2-goal2", "g2-goal3", "g2-goal4"]
VIDEO = CFG["video"]["local_path"]
CACHE = "out/nm26/{g}/frames.json"
BLENDER_PY = "/root/venvs/blender/bin/python"
sys.path.insert(0, str(REPO / "scripts"))
from nm26_tracks import FIGURE_TRACKS as FIGS, PUCK_TRACK as PUCK  # noqa: E402  (the tracks the analysis reads)
PY = os.environ.get("NM26_PY") or (BLENDER_PY if Path(BLENDER_PY).exists() else sys.executable)


@dataclass
class Step:
    id: str
    stage: str
    cmd: list                     # argv; "{py}" is replaced by the step interpreter
    needs: list = field(default_factory=list)      # files that must exist (repo-relative)
    modules: list = field(default_factory=list)    # Python modules the step interpreter must import
    outputs: list = field(default_factory=list)    # files the step writes (repo-relative)
    note: str = ""
    log: str = ""                 # also write the step's stdout to this file (repo-relative)


def py(script, *args): return ["{py}", script, *args]


def steps(games):
    S = []
    S.append(Step("fetch-video", "fetch", ["@fetch"], outputs=[VIDEO], note="about 660 MB"))
    for g in games:
        S.append(Step(f"detect-{g}", "cache", py("scripts/nm26-detect.py", g), [VIDEO, f"{DATA}/{g}/background.png"],
                      ["av", "cv2"], [CACHE.format(g=g)], "about 12 min per game on 4 CPUs; background.png is reused"))
    S.append(Step("calibrate-g1", "calibrate", py("scripts/nm26-calibrate.py", "g1"),
                  [f"{DATA}/g1/background.png", f"{DATA}/g1/calibration-inputs.json"], ["av", "cv2", "scipy"],
                  [f"{DATA}/g1/calibration.json", "validation/nm26-g1-calibration.jpg"]))
    S.append(Step("figure-meshes", "meshes", py("assets/blender/preview_molds.py", "skater", "goalie"), [], ["bpy"],
                  ["out/figures/skater.npz", "out/figures/goalie.npz"], "Blender (bpy 4.5); about 1 min"))
    for g in games:
        S.append(Step(f"puck-track-{g}", "puck", py("scripts/nm26-track.py", g), [CACHE.format(g=g)], ["av", "cv2", "shapely"],
                      [f"{DATA}/{g}/puck-track.json"]))
    for g in games:
        S.append(Step(f"passes-{g}", "puck", py("scripts/nm26-passes.py", g),
                      [f"{DATA}/{g}/{PUCK}", "out/figures/skater.npz", "out/figures/goalie.npz"], ["av", "cv2", "shapely"],
                      [f"{DATA}/{g}/passes.json"], f"reads {PUCK} (scripts/nm26_tracks.py)"))
    S.append(Step("patterns", "puck", py("scripts/nm26-patterns.py"), [f"{DATA}/{g}/{f}" for g in GAMES for f in ("passes.json", PUCK)], ["av", "cv2", "shapely"],
                  [f"{DATA}/patterns.json", "validation/nm26-control-nygard.png", "validation/nm26-control-fjermestad.png"]))
    S.append(Step("smooth-tracks", "figures", py("scripts/synth/smooth-tracks.py", *games), [f"{DATA}/{g}/figure-tracks.json" for g in games],
                  ["numpy"], [f"{DATA}/{g}/figure-tracks-smooth.json" for g in games]))
    S.append(Step("figure-analysis", "figures", py("scripts/nm26-figure-analysis.py"),
                  [f"{DATA}/{g}/{f}" for g in GAMES for f in ("figure-tracks.json", FIGS, PUCK)], ["numpy"],
                  [f"{DATA}/figure-analysis.json"] + [f"{DATA}/rebuild/{gid}-figures.json" for gid in HATTRICK]))
    S.append(Step("board-g2-goal2", "figures", py("scripts/synth/figure-tracks-board.py", "g2-goal2"),
                  [f"{DATA}/rebuild/g2-goal2-figures.json", f"{DATA}/g2/{PUCK}"], ["cv2"], ["validation/board-g2-goal2.png"]))
    S.append(Step("board-g2-goal2-smooth", "figures", py("scripts/synth/figure-tracks-board.py", "g2-goal2", "--smooth"),
                  [f"{DATA}/rebuild/g2-goal2-figures.json", f"{DATA}/g2/{FIGS}", f"{DATA}/g2/{PUCK}"], ["cv2"],
                  ["validation/board-g2-goal2-smooth.png"]))
    for g in games:
        S.append(Step(f"figure-sheet-{g}", "sheets", py("scripts/synth/figure-tracks-sheet.py", g, "4"),
                      [VIDEO, CACHE.format(g=g), f"{DATA}/{g}/figure-tracks.json"], ["av", "cv2"], [f"validation/figure-tracks-{g}.jpg"]))
    for gid in HATTRICK:
        S.append(Step(f"rebuild-evidence-{gid}", "sheets", py("scripts/nm26-rebuild-evidence.py", gid),
                      [VIDEO, CACHE.format(g="g2"), "out/synth/goalie-pose-v2c.pt"], ["av", "cv2", "torch", "torchvision"],
                      [f"{DATA}/rebuild/{gid}-evidence.json", f"validation/rebuild-{gid}-sheet.jpg"],
                      "needs goalie model C (out/synth/goalie-pose-v2c.pt, not committed: stage models)"))
    S.append(Step("review-page-g1", "pages", py("scripts/nm26-review-page.py", "g1"),
                  [VIDEO, CACHE.format(g="g1"), f"{DATA}/g1/passes.json"], ["av", "cv2"], ["validation/nm26-g1-review.html"]))
    S.append(Step("goal-clips", "pages", py("scripts/nm26-goal-clips.py"), [VIDEO] + [CACHE.format(g=g) for g in GAMES], ["av", "cv2"],
                  ["out/nm26/goal-clips/clips.json", "out/nm26/goal-clips/log.txt"], "about 40 short H.264 clips (not committed; published with the page)",
                  log="out/nm26/goal-clips/log.txt"))
    S.append(Step("goal-page", "pages", py("scripts/nm26-goal-page.py"), ["out/nm26/goal-clips/clips.json", "out/nm26/goal-clips/log.txt"], [],
                  ["validation/nm26-goals-review.html"]))

    # ---- stage models: from zero, hours of CPU; out/synth is not committed. Listed for completeness, never default. ----
    # Goal-box plates (out/synth/plates/plate_{W,E}_raw.png) have no committed script: a gap (docs/pipeline.md, section 3).
    GPLATES = ["out/synth/plates/plate_W_raw.png", "out/synth/plates/plate_E_raw.png"]
    S.append(Step("goalie-renders", "models", py("scripts/synth/render-goalie-crops.py", "out/synth/train", "0", "5000"), [], ["bpy"],
                  ["out/synth/train/labels.jsonl"], "Blender Cycles, about 1 s per render"))
    S.append(Step("goalie-renders-w-nm26", "models", py("scripts/synth/render-goalie-crops.py", "out/synth/train_w2", "10000", "2500", "W", "nm26"),
                  [], ["bpy"], ["out/synth/train_w2/labels.jsonl"], "the NM26 white-goalie kit"))
    for g in GAMES:
        S.append(Step(f"skater-frames-{g}", "models", py("scripts/synth/skater-frames.py", g), [VIDEO, CACHE.format(g=g)], ["av", "cv2"],
                      ["out/synth/skaters/frames"], "40 registered live-play frames per game"))
    S.append(Step("skater-plates", "models", py("scripts/synth/skater-plates.py"), ["out/synth/skaters/frames"], ["cv2"],
                  ["out/synth/skaters/plate_all.png"]))
    S.append(Step("skater-renders", "models", py("scripts/synth/render-skater-crops.py", "out/synth/skaters/train", "0", "6000", "nm26"), [],
                  ["bpy"], ["out/synth/skaters/train/labels.jsonl"], "Blender Cycles"))
    S.append(Step("train-goalie-v2a", "models", py("scripts/synth/train-goalie-pose.py", "--renders", "train,train_w2", "--drop-ref-w", "--out", "goalie-pose-v2a"),
                  ["out/synth/train/labels.jsonl", "out/synth/train_w2/labels.jsonl"] + GPLATES, ["torch", "torchvision"],
                  ["out/synth/goalie-pose-v2a.pt"], "options reconstructed from docs/synthetic-goalie-pilot.md; epochs not recorded"))
    S.append(Step("train-goalie-v2c", "models", py("scripts/synth/train-goalie-pose.py", "--renders", "train,train_w2", "--drop-ref-w",
                  "--real-train", "g1,g2,g4,g6", "--real-u-from", "out/synth/goalie-pose-v2a.pt", "--out", "goalie-pose-v2c"),
                  ["out/synth/goalie-pose-v2a.pt"] + GPLATES, ["torch", "torchvision"], ["out/synth/goalie-pose-v2c.pt"],
                  "model C; options reconstructed, not verified"))
    S.append(Step("train-skater-v2b", "models", py("scripts/synth/train-skater-pose.py", "10", "--renders", "train", "--real-train", "g1,g2,g4,g6",
                  "--out", "skater-pose-v2b"), ["out/synth/skaters/train/labels.jsonl", "out/synth/skaters/plate_all.png"],
                  ["torch", "torchvision"], ["out/synth/skater-pose-v2b.pt"], "model v2b; options reconstructed, not verified"))
    for g in games:
        S.append(Step(f"track-figures-{g}", "models", py("scripts/synth/track-figures.py", g, "--fps", "5"),
                      [VIDEO, CACHE.format(g=g), "out/synth/skater-pose-v2b.pt", "out/synth/goalie-pose-v2c.pt"],
                      ["av", "cv2", "torch", "torchvision"], [f"{DATA}/{g}/figure-tracks.json"], "about 25 min per game"))

    # ---- Steps from the parallel workstreams (puck detector, tracker v3, combination recognition, all-goals replays,
    # Edwall rebuild) go here: one Step per script with its stage, inputs, modules and outputs. ----
    # Registered at consolidation (2026-10-10, docs/pipeline.md section 5). Command lines are taken from each workstream's
    # doc; only the "analysis" steps were run here. The own-video pipeline is not an NM26 step (docs/own-video-tracking.md).

    # Synthetic puck detector (docs/synthetic-puck.md): stage models (video, Blender, PyTorch; out/synth is not committed).
    for g in games:
        S.append(Step(f"puck-frames-{g}", "models", py("scripts/synth/puck-frames.py", g), [VIDEO, f"{DATA}/{g}/puck-track.json"],
                      ["av", "cv2"], [f"out/nm26/{g}/H.npz", f"out/synth/puck/real/{g}.jsonl"],
                      "every 6th frame registered (the tracker interpolates) and real training triplets; about 45 min for all games"))
    for k in range(3):
        S.append(Step(f"puck-renders-{k}", "models", py("scripts/synth/render-puck-crops.py", "out/synth/puck/renders", str(500 * k), "500"),
                      ["assets/scene/full_static.blend"], ["bpy"], ["out/synth/puck/renders/labels.jsonl"], "Blender Cycles, 3 frames per sample"))
    S.append(Step("puck-blob-offset", "models", py("scripts/synth/puck-blob-offset.py"), [f"{DATA}/camera-ref.json"], ["cv2"],
                  ["out/synth/puck/blob-offset.json"], "blob centre to top-face centre in the reference camera (geometry only)"))
    S.append(Step("train-puck-v0", "models", py("scripts/synth/train-puck-detector.py", "--epochs", "2", "--steps", "250", "--name", "puck-det-v0"),
                  ["out/synth/puck/renders/labels.jsonl", "out/synth/puck/blob-offset.json"] + [f"out/synth/puck/real/{g}.jsonl" for g in GAMES],
                  ["torch", "cv2"], ["out/synth/puck-det-v0.pt"], "500-step pilot"))
    S.append(Step("train-puck-v1", "models", py("scripts/synth/train-puck-detector.py", "--epochs", "7", "--steps", "1000", "--name", "puck-det-v1",
                  "--init", "puck-det-v0"), ["out/synth/puck-det-v0.pt"], ["torch", "cv2"], ["out/synth/puck-det-v1.pt"],
                  "about 14 min per epoch on CPU; not bit-reproducible"))
    S.append(Step("eval-puck-v1", "models", py("scripts/synth/eval-puck-detector.py", "--n", "500"), ["out/synth/puck-det-v1.pt"],
                  ["torch", "cv2"], ["out/synth/puck-det-v1-eval.json"], "held-out games 3 and 7"))
    for g in games:
        S.append(Step(f"track-puck-synth-{g}", "models", py("scripts/synth/track-puck.py", g),
                      [VIDEO, f"out/nm26/{g}/H.npz", "out/synth/puck-det-v1.pt", f"{DATA}/{g}/background.png"], ["av", "cv2", "torch"],
                      [f"{DATA}/{g}/puck-track-synth.json", f"out/nm26/{g}/puck-cands-puck-det-v1.json"],
                      "about 8-10 min per game; with the candidates cached, track-puck.py <game> --track-only re-runs the tracker in seconds"))

    # Figure tracker v3 (docs/tracker-v3.md): stage models (video, Blender, PyTorch, timm's ResNet-18 start weights at
    # /root/.cache/torch/hub/checkpoints/alt/resnet18_a1.pth). The base renders are the v2 recipe (render-skater-hard.py
    # "base" draws the same samples as skater-renders and skips seeds already rendered); v3 used seeds 0-999 and 1500-2499.
    for first in ("0", "1500"):
        S.append(Step(f"skater-renders-v3-base-{first}", "models",
                      py("scripts/synth/render-skater-hard.py", "out/synth/skaters/train", first, "1000", "base", "--threads", "2"), [], ["bpy"],
                      ["out/synth/skaters/train/labels.jsonl"], "Blender Cycles, about 1.7 s per render"))
    S.append(Step("skater-renders-v3-hard", "models",
                  py("scripts/synth/render-skater-hard.py", "out/synth/skaters/hard", "100000", "1000", "hard", "--threads", "2"), [], ["bpy"],
                  ["out/synth/skaters/hard/labels.jsonl"], "hard examples: near-board wings, slot ends, crowding, offset and hidden negatives"))
    S.append(Step("figure-plates-v3", "models", py("scripts/synth/track-figures-v3.py", "plates"), [VIDEO, f"{DATA}/skater-facing-crops.json"],
                  ["av", "cv2"], ["out/synth/skaters/frames", "out/synth/skaters/plate_all.png"] + [f"out/synth/skaters/plate_{g}.png" for g in GAMES],
                  "registers the 280 label frames and writes the rink plates"))
    S.append(Step("train-skater-v3-a", "models", py("scripts/synth/train-skater-v3.py", "4", "--presence-weight", "1", "--out", "skater-pose-v3-ep4"),
                  ["out/synth/skaters/train/labels.jsonl", "out/synth/skaters/hard/labels.jsonl", "out/synth/skaters/plate_all.png"],
                  ["torch", "torchvision"], ["out/synth/skater-pose-v3-ep4.pt"],
                  "as run (docs/tracker-v3.md); --out added so the three runs chain (the doc names the checkpoints -ep4, -ep16)"))
    S.append(Step("train-skater-v3-b", "models", py("scripts/synth/train-skater-v3.py", "12", "--init", "out/synth/skater-pose-v3-ep4.pt",
                  "--out", "skater-pose-v3-ep16"), ["out/synth/skater-pose-v3-ep4.pt"], ["torch", "torchvision"], ["out/synth/skater-pose-v3-ep16.pt"],
                  "presence weight 5 (default)"))
    S.append(Step("train-skater-v3-c", "models", py("scripts/synth/train-skater-v3.py", "8", "--init", "out/synth/skater-pose-v3-ep16.pt",
                  "--lr", "3e-4"), ["out/synth/skater-pose-v3-ep16.pt"], ["torch", "torchvision"], ["out/synth/skater-pose-v3.pt"],
                  "fine-tune; about 2.7 min per epoch; not bit-reproducible"))
    for g in games:
        S.append(Step(f"figure-obs-v3-{g}", "models", py("scripts/synth/track-figures-v3.py", "obs", g),
                      [VIDEO, "out/synth/skater-pose-v3.pt", f"out/synth/skaters/plate_{g}.png", f"{DATA}/{g}/figure-tracks.json"],
                      ["av", "cv2", "torch", "torchvision"], [f"out/synth/v3/obs-{g}.json"],
                      "every frame of the v2 raw track; about 0.45 s per frame (2.7 h for all seven games)"))
        S.append(Step(f"figure-tracks-v3-{g}", "models", py("scripts/synth/track-figures-v3.py", "decode", g),
                      [f"out/synth/v3/obs-{g}.json", f"{DATA}/{g}/figure-tracks.json"], ["numpy"], [f"{DATA}/{g}/figure-tracks-v3.json"],
                      "decoder only (seconds); goalies: model C readings from figure-tracks.json"))

    # Stage analysis (default): from committed tracks and labels only, numpy (+ Pillow), seconds; no video, no models.
    S.append(Step("combo-recognition", "analysis", py("scripts/nm26-combo-recognition.py"),
                  [f"{DATA}/{g}/{f}" for g in GAMES for f in (FIGS, PUCK)]
                  + [f"{DATA}/goal-labels.json", f"{DATA}/timeline.json"], ["numpy", "PIL"],
                  [f"{DATA}/combo-labels.json", "validation/nm26-combo-spots.png"],
                  "docs/nm26-combinations.md; tracks from scripts/nm26_tracks.py"))
    S.append(Step("puck-synth-compare", "analysis", py("scripts/synth/puck-compare.py"),
                  [f"{DATA}/{g}/{f}" for g in GAMES for f in ("puck-track.json", "puck-track-synth.json", "passes.json")]
                  + [f"{DATA}/goal-labels.json", f"{DATA}/timeline.json", "validation/12-hardware-report.json"], ["numpy"],
                  [f"{DATA}/puck-synth-compare.json"],
                  "uses out/synth/puck/blob-offset.json when present, else its recorded mean (0.15, -8.81) px"))

    # All-goals replays (validation/replays/README.md): stage pages (the broadcast clips need the video).
    S.append(Step("goal-replays", "pages", py("scripts/nm26-replays.py"),
                  [VIDEO] + [f"{DATA}/{g}/{f}" for g in GAMES for f in (FIGS, PUCK)]
                  + [f"{DATA}/goal-labels.json", f"{DATA}/timeline.json"], ["av", "cv2"],
                  ["validation/replays/replays.json", "validation/replays/index.html"],
                  "40 replays and broadcast clips (validation/replays/*.mp4); about 7 min on 4 cores"))

    # Edwall hat-trick rebuild v2 (docs/rebuild-g2-edwall-v2.md): stage edwall (not default). Replays the fitted
    # parameters in shots/edwall/<goal>.inputs.json (edwall-trace.py --fit pass / --fit shot refit them, slow). The videos
    # are rendered outside the runner: node scripts/edwall-render.ts <goal> (about 75 min each).
    for gid in HATTRICK:
        S.append(Step(f"edwall-trace-{gid}", "edwall", py("scripts/edwall-trace.py", gid),
                      [f"shots/edwall/{gid}.inputs.json", "shots/edwall/puck-readings.json", f"{DATA}/g2/{FIGS}", f"{DATA}/g2/puck-track-synth.json",
                       "out/figures/skater.npz", "out/figures/goalie.npz"], ["numpy", "shapely", "PIL"],
                      [f"data/traces/edwall-{gid}.trace.json", f"shots/edwall/{gid}.checks.json", f"validation/edwall-{gid}-trace.png"]))
        S.append(Step(f"edwall-presentation-{gid}", "edwall", py("scripts/edwall-presentation.py", gid), [f"data/traces/edwall-{gid}.trace.json"],
                      [], [f"data/presentations/edwall-{gid}.analysis.json"]))

    # Track switch (docs/nm26-new-tracks.md): the before/after numbers (default stage analysis) and the tap review page
    # (stage pages: needs the video; seed 26, so the same frames come back).
    S.append(Step("track-switch-compare", "analysis", py("scripts/nm26-track-switch-compare.py"),
                  [f"{DATA}/combo-labels.json", f"{DATA}/patterns.json", f"{DATA}/figure-analysis.json"] + [f"{DATA}/{g}/passes.json" for g in GAMES],
                  ["numpy"], ["validation/nm26-track-switch.json"], "before = the outputs at git rev ee0681d (old tracks)"))
    S.append(Step("tap-review-page", "pages", py("scripts/nm26-tap-review.py", "page"),
                  [VIDEO] + [f"{DATA}/{g}/{f}" for g in GAMES for f in ("puck-track.json", "puck-track-synth.json", "figure-tracks-smooth.json", "figure-tracks-v3.json")],
                  ["av", "cv2"], ["validation/tap-review/items.json", "validation/tap-review/index.html"], "published with a db for the user's taps"))
    return S


# Committed NM26 files that no rebuild step writes: hand-made settings, the user's labels (exported from the review
# pages' databases), and outputs of steps that need the user or the label pages. tests/synth/test_rebuild_steps.py checks
# that every committed file under data/games/nm26-semifinal is either a step output or listed here.
SOURCES = {
    f"{DATA}/config.json": "hand-made settings: video URL and sha256, game windows, teams, ice polygon",
    f"{DATA}/timeline.json": "hand-made from the video: timer tones, score-overlay changes, goals (docs/nm26-game-patterns.md)",
    f"{DATA}/camera-ref.json": "decomposed by hand from g1/calibration.json (docs/synthetic-goalie-pilot.md, section A); no script",
    f"{DATA}/g1/calibration-inputs.json": "hand-picked line/board crossings in g1/background.png",
    f"{DATA}/g1/review-claude.json": "Claude's review of the game-1 pass candidates (docs/nm26-passes.md); not scripted",
    f"{DATA}/goal-labels.json": "user labels: scripts/nm26-goal-labels.py <db export of validation/nm26-goals-review.html>",
    f"{DATA}/skater-labels.json": "user labels: scripts/synth/skater-labels.py <db export of validation/skater-facing-review.html>",
    f"{DATA}/goalie-facing-labels.json": "user labels: scripts/synth/goalie-facing-eval.py <db export of validation/goalie-facing-review.html>",
    f"{DATA}/skater-facing-crops.json": "crop list of the skater label page (scripts/synth/skater-facing-page.py; needs out/synth/skaters/frames)",
    f"{DATA}/goalie-facing-crops.json": "crop list of the goalie label page (scripts/synth/goalie-facing-page.py; needs the pilot model)",
    f"{DATA}/puck-synth-review-claude.json": "Claude's verdicts on 56 frames, old vs synthetic puck track (docs/synthetic-puck.md section 3); "
                                             "not scripted (the sheet is drawn by scripts/synth/puck-review-sheet.py)",
    **{f"{DATA}/{g}/background.png": "scripts/nm26-detect.py <game> --bg (median of registered frames); reused, not rebuilt by default"
       for g in GAMES},
    **{f"{DATA}/{g}/calibration.json": "earlier per-game calibration; unused since all games share g1's (config calibration_from)"
       for g in GAMES[1:]},
}

STAGES = ["fetch", "cache", "calibrate", "meshes", "puck", "figures", "analysis", "sheets", "pages", "edwall", "models"]
DEFAULT = ["calibrate", "meshes", "puck", "figures", "analysis", "sheets", "pages"]
_mod_cache = {}


def has_modules(mods):
    key = tuple(mods)
    if key not in _mod_cache:
        if not mods: _mod_cache[key] = []
        else:
            missing = []
            for m in mods:
                r = subprocess.run([PY, "-c", f"import {m}"], capture_output=True, cwd=REPO)
                if r.returncode: missing.append(m)
            _mod_cache[key] = missing
    return _mod_cache[key]


def why_not(s, failed_outputs=frozenset()):
    stale = [p for p in s.needs if p in failed_outputs]
    if stale: return "an earlier step failed to rebuild " + ", ".join(stale[:3]) + (" ..." if len(stale) > 3 else "")
    miss = [p for p in s.needs if not (REPO / p).exists()]
    if miss: return "missing input " + ", ".join(miss[:3]) + (" ..." if len(miss) > 3 else "")
    mods = has_modules(s.modules)
    if mods: return f"{PY} cannot import " + ", ".join(mods)
    return None


def fetch_video():
    v = CFG["video"]; dst = REPO / VIDEO
    if dst.exists() and sha256(dst) == v["sha256"]: print("  video present, sha256 ok"); return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["curl", "-sS", "-L", "--fail", "-o", str(dst), v["url"]])
    if r.returncode: return r.returncode
    ok = sha256(dst) == v["sha256"]; print("  sha256", "ok" if ok else "MISMATCH"); return 0 if ok else 1


def run(argv, log=""):
    """Run a step; with `log`, its stdout is also written to that file (nm26-goal-page.py reads the clip log)."""
    if not log: return subprocess.run(argv, cwd=REPO).returncode
    p = subprocess.Popen(argv, cwd=REPO, stdout=subprocess.PIPE, text=True); lines = []
    for line in p.stdout: print(line, end="", flush=True); lines.append(line)
    rc = p.wait(); (REPO / log).parent.mkdir(parents=True, exist_ok=True); (REPO / log).write_text("".join(lines))
    return rc


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def git(*a): return subprocess.run(["git", *a], capture_output=True, text=True, cwd=REPO).stdout


def compare(path):
    """Committed vs rebuilt: 'identical', 'new' (untracked), 'not tracked', or a change summary."""
    if not git("ls-files", path).strip(): return "not tracked (cache)"
    if not git("status", "--porcelain", "--", path).strip(): return "identical"
    if path.endswith(".json"):
        try:
            old = json.loads(git("show", f"HEAD:{path}")); new = json.loads((REPO / path).read_text())
            for key in ("rows", "events", "frames"):
                if isinstance(old.get(key), list) and isinstance(new.get(key), list):
                    a, b = old[key], new[key]; n = max(len(a), len(b))
                    diff = sum(1 for k in range(n) if k >= len(a) or k >= len(b) or a[k] != b[k])
                    return f"changed: {key} {len(a)} -> {len(b)}, {diff} differ ({100 * diff / max(n, 1):.1f}%)"
            return "changed: " + ", ".join(k for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k))[:200]
        except Exception as e:  # noqa: BLE001
            return f"changed ({e.__class__.__name__})"
    return "changed (binary or text; compare by eye)"


def main(argv):
    flags = {a for a in argv if a.startswith("--")}; args = [a for a in argv if not a.startswith("--")]
    games = GAMES
    if "--games" in argv:
        games = argv[argv.index("--games") + 1].split(","); args = [a for a in args if a != argv[argv.index("--games") + 1]]
    stages = args or DEFAULT
    bad = [s for s in stages if s not in STAGES]
    if bad: sys.exit(f"unknown stage {bad}; stages: {STAGES}")
    todo = [s for s in steps(games) if s.stage in stages]
    print(f"interpreter for steps: {PY}")
    if "--list" in flags:
        for s in todo:
            r = why_not(s) if s.cmd != ["@fetch"] else None
            print(f"{s.stage:9s} {s.id:28s} {'ready' if not r else 'SKIP: ' + r}" + (f"  ({s.note})" if s.note else ""))
        return 0
    report = {"interpreter": PY, "stages": stages, "steps": []}; failed = 0
    failed_outputs = set()  # outputs of failed steps: an old copy on disk must not feed later steps
    for s in todo:
        r = None if s.cmd == ["@fetch"] else why_not(s, failed_outputs)
        entry = {"id": s.id, "stage": s.stage, "outputs": s.outputs}
        if r:
            print(f"SKIP {s.id}: {r}"); entry.update(result="skipped", reason=r); report["steps"].append(entry); continue
        print(f"RUN  {s.id}: {' '.join(c.replace('{py}', Path(PY).name) for c in s.cmd)}", flush=True)
        t0 = time.time()
        rc = fetch_video() if s.cmd == ["@fetch"] else run([c.replace("{py}", PY) for c in s.cmd], s.log)
        entry.update(result="ok" if rc == 0 else f"failed (exit {rc})", seconds=round(time.time() - t0, 1))
        print(f"     {entry['result']} in {entry['seconds']} s", flush=True)
        report["steps"].append(entry)
        if rc:
            failed += 1; failed_outputs |= set(s.outputs)
            if "--keep-going" not in flags: break
    if "--check" in flags:
        print("\nCommitted outputs after the rebuild:")
        for e in report["steps"]:
            if e["result"] != "ok": continue
            e["compare"] = {p: compare(p) for p in e["outputs"]}
            for p, c in e["compare"].items(): print(f"  {p}: {c}")
    out = REPO / "out/pipeline/rebuild-report.json"; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    n = {k: sum(1 for e in report["steps"] if e["result"].startswith(k)) for k in ("ok", "skipped", "failed")}
    print(f"\n{n['ok']} ran, {n['skipped']} skipped, {n['failed']} failed. Report: {out.relative_to(REPO)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
