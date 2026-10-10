"""Rebuild the NM26 outputs step by step, from the video and the frame cache (docs/pipeline.md).

    python3 scripts/pipeline/nm26_rebuild.py [stage ...] [--check] [--list] [--games g1,g2] [--keep-going]

Stages, in order (default: every stage marked "default" below):
- fetch     the broadcast video from the GitHub release (config.json url), checked against its sha256;
- cache     register every frame and find puck candidates (scripts/nm26-detect.py): out/nm26/<game>/frames.json;
- calibrate rink-plane calibration of game 1 (the reference frame all games are registered to);
- meshes    the figure meshes (out/figures/*.npz, Blender) that nm26-passes.py reads the reach of a figure from;
- puck      puck track, flights and passes per game, cross-game patterns;
- figures   cleaned figure tracks, figure analysis, tactics boards (committed tracks only: no video, no models);
- sheets    checking sheets drawn on the video frames;
- pages     the pass review page (game 1) and the goal clips and goal review page;
- models    renders, training and figure tracking (hours; out/synth/*.pt are not committed). Never run by default.

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
                      [f"{DATA}/{g}/puck-track.json", "out/figures/skater.npz", "out/figures/goalie.npz"], ["av", "cv2", "shapely"],
                      [f"{DATA}/{g}/passes.json"]))
    S.append(Step("patterns", "puck", py("scripts/nm26-patterns.py"), [f"{DATA}/{g}/passes.json" for g in GAMES], ["av", "cv2", "shapely"],
                  [f"{DATA}/patterns.json", "validation/nm26-control-nygard.png", "validation/nm26-control-fjermestad.png"]))
    S.append(Step("smooth-tracks", "figures", py("scripts/synth/smooth-tracks.py", *games), [f"{DATA}/{g}/figure-tracks.json" for g in games],
                  ["numpy"], [f"{DATA}/{g}/figure-tracks-smooth.json" for g in games]))
    S.append(Step("figure-analysis", "figures", py("scripts/nm26-figure-analysis.py"),
                  [f"{DATA}/{g}/figure-tracks.json" for g in GAMES] + [f"{DATA}/{g}/puck-track.json" for g in GAMES], ["numpy"],
                  [f"{DATA}/figure-analysis.json"] + [f"{DATA}/rebuild/{gid}-figures.json" for gid in HATTRICK]))
    S.append(Step("board-g2-goal2", "figures", py("scripts/synth/figure-tracks-board.py", "g2-goal2"),
                  [f"{DATA}/rebuild/g2-goal2-figures.json"], ["cv2"], ["validation/board-g2-goal2.png"]))
    S.append(Step("board-g2-goal2-smooth", "figures", py("scripts/synth/figure-tracks-board.py", "g2-goal2", "--smooth"),
                  [f"{DATA}/rebuild/g2-goal2-figures.json", f"{DATA}/g2/figure-tracks-smooth.json"], ["cv2"],
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
                  ["out/nm26/goal-clips/clips.json"], "about 40 short H.264 clips (not committed; published with the page)"))
    S.append(Step("goal-page", "pages", py("scripts/nm26-goal-page.py"), ["out/nm26/goal-clips/clips.json"], [],
                  ["validation/nm26-goals-review.html"]))

    # ---- stage models: from zero, hours of CPU; out/synth is not committed. Listed for completeness, never default. ----
    S.append(Step("goalie-renders", "models", py("scripts/synth/render-goalie-crops.py", "out/synth/train", "0", "6000"), [], ["bpy"],
                  ["out/synth/train/labels.jsonl"], "Blender Cycles; see docs/synthetic-goalie-pilot.md for the exact runs"))
    S.append(Step("skater-renders", "models", py("scripts/synth/render-skater-crops.py", "out/synth/skaters/train", "0", "6000", "nm26"), [],
                  ["bpy"], ["out/synth/skaters/train/labels.jsonl"], "Blender Cycles"))
    S.append(Step("train-goalie", "models", py("scripts/synth/train-goalie-pose.py"), ["out/synth/train/labels.jsonl"], ["torch", "torchvision"],
                  ["out/synth/goalie-pose.pt"], "model C needs the options in docs/synthetic-goalie-pilot.md"))
    S.append(Step("train-skater", "models", py("scripts/synth/train-skater-pose.py"), ["out/synth/skaters/train/labels.jsonl"],
                  ["torch", "torchvision"], ["out/synth/skater-pose.pt"], "model v2b needs the options in docs/synthetic-goalie-pilot.md"))
    for g in games:
        S.append(Step(f"track-figures-{g}", "models", py("scripts/synth/track-figures.py", g, "--fps", "5"),
                      [VIDEO, CACHE.format(g=g), "out/synth/skater-pose-v2b.pt", "out/synth/goalie-pose-v2c.pt"],
                      ["av", "cv2", "torch", "torchvision"], [f"{DATA}/{g}/figure-tracks.json"], "about 25 min per game"))

    # ---- Steps from the parallel workstreams (puck detector, tracker v3, combination recognition, all-goals replays,
    # Edwall rebuild) go here: one Step per script with its stage, inputs, modules and outputs. ----
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
    **{f"{DATA}/{g}/background.png": "scripts/nm26-detect.py <game> --bg (median of registered frames); reused, not rebuilt by default"
       for g in GAMES},
    **{f"{DATA}/{g}/calibration.json": "earlier per-game calibration; unused since all games share g1's (config calibration_from)"
       for g in GAMES[1:]},
}

STAGES = ["fetch", "cache", "calibrate", "meshes", "puck", "figures", "sheets", "pages", "models"]
DEFAULT = ["calibrate", "meshes", "puck", "figures", "sheets", "pages"]
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


def why_not(s):
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
    for s in todo:
        r = None if s.cmd == ["@fetch"] else why_not(s)
        entry = {"id": s.id, "stage": s.stage, "outputs": s.outputs}
        if r:
            print(f"SKIP {s.id}: {r}"); entry.update(result="skipped", reason=r); report["steps"].append(entry); continue
        print(f"RUN  {s.id}: {' '.join(c.replace('{py}', Path(PY).name) for c in s.cmd)}", flush=True)
        t0 = time.time()
        rc = fetch_video() if s.cmd == ["@fetch"] else subprocess.run([c.replace("{py}", PY) for c in s.cmd], cwd=REPO).returncode
        entry.update(result="ok" if rc == 0 else f"failed (exit {rc})", seconds=round(time.time() - t0, 1))
        print(f"     {entry['result']} in {entry['seconds']} s", flush=True)
        report["steps"].append(entry)
        if rc:
            failed += 1
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
