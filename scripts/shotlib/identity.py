"""What a saved move trace was built from, and whether it still is (the gate of the presentation-only route).

A move has two sources:
  moves/<id>/move.json   the motion: figures, puck start, contacts, expectations (build: scripts/build-move.py <id>)
  moves/<id>/story.json  the presentation: titles, text, beats, timing, camera, theme (scripts/build-move.py <id> --presentation)

The build records the motion's identity in the trace: the move file without presentation keys, the engine code and the
data files the simulation reads. A presentation may only be (re)generated from a trace whose identity still matches and
whose checks passed; otherwise the move has to be rebuilt first. Nothing here simulates.
"""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# move.json keys that only feed the video (older move files kept the story there); never part of the motion identity
PRESENTATION_KEYS = ("story",)
# engine files that do not change a simulation: the video spec generator, the robustness reruns and this module
NOT_ENGINE = ("presentation.py", "robustness.py", "identity.py")
# data files the simulation reads (scripts/shotlib/world.py, build.py)
ENGINE_DATA = ("data/geometry.json", "validation/12-hardware-report.json", "validation/16-assembly-poses.json",
               "data/figures/contact-footprints.json", "shots/spjass/checks.json")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def motion_sha256(spec):
    """SHA-256 of the move file's motion: canonical JSON without the presentation keys."""
    motion = {k: v for k, v in spec.items() if k not in PRESENTATION_KEYS}
    return hashlib.sha256(json.dumps(motion, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def engine_files():
    return sorted(p for p in (REPO / "scripts/shotlib").glob("*.py") if p.name not in NOT_ENGINE)


def engine_identity():
    """Engine code (one hash over every simulating file) and each data input, as the build records them."""
    code = hashlib.sha256("\n".join(f"{p.relative_to(REPO)}:{sha(p)}" for p in engine_files()).encode()).hexdigest()
    return {"code_sha256": code, "inputs_sha256": {p: sha(REPO / p) for p in ENGINE_DATA}}


def motion_gate(move_id):
    """Problems that forbid using the saved trace of a move without rebuilding it (empty list: the trace is current and
    passed every check). Compares the trace and checks with the move file, the engine and the model files of today."""
    problems = []
    mpath = REPO / "moves" / move_id / "move.json"
    tpath, cpath = REPO / f"data/traces/{move_id}.trace.json", REPO / f"shots/{move_id}/checks.json"
    for p in (mpath, tpath, cpath):
        if not p.exists():
            return [f"{p.relative_to(REPO)} is missing"]
    spec, trace, checks = (json.loads(p.read_text()) for p in (mpath, tpath, cpath))
    if spec.get("legacy"):
        return [f"{move_id} is a legacy move: its trace is owned by {spec['legacy'].get('script')}"]
    if trace.get("trace_id") != spec.get("trace_id"):
        problems.append(f"trace is {trace.get('trace_id')}, the move file names {spec.get('trace_id')}")
    if trace.get("status") != spec.get("status"):
        problems.append(f"trace status {trace.get('status')}, move file {spec.get('status')}")
    src = trace.get("source", {})
    if src.get("overrides"):
        problems.append(f"trace was built with overrides {src['overrides']}")
    if "move_motion_sha256" in src:
        if src["move_motion_sha256"] != motion_sha256(spec):
            problems.append("the motion in move.json changed since the build")
    elif src.get("move_file_sha256") != sha(mpath):
        problems.append("move.json changed since the build (trace predates motion hashes)")
    eng = trace.get("engine", {})
    if eng.get("contact_footprints_sha256") != sha(REPO / "data/figures/contact-footprints.json"):
        problems.append("contact footprints changed since the build")
    now = engine_identity()
    if "code_sha256" in eng and eng["code_sha256"] != now["code_sha256"]:
        problems.append("engine code (scripts/shotlib) changed since the build")
    for p, h in eng.get("inputs_sha256", {}).items():
        if now["inputs_sha256"].get(p, sha(REPO / p) if (REPO / p).exists() else None) != h:
            problems.append(f"{p} changed since the build")
    geo = json.loads((REPO / "data/geometry.json").read_text())
    manifest = json.loads((REPO / "remotion/asset-manifest.json").read_text())
    if trace.get("geometry_version") != geo["geometry_version"]:
        problems.append(f"geometry_version {trace.get('geometry_version')} != {geo['geometry_version']}")
    for k, p in manifest.get("asset_files", {}).items():
        if trace.get("asset_refs", {}).get(k) != sha(REPO / p):
            problems.append(f"model asset {p} changed since the build ({k})")
    # the checks that let a trace be saved and played (CLAUDE.md "Contact physics", "Slide or bounce")
    if checks.get("trace_id") != trace.get("trace_id"):
        problems.append(f"checks are for {checks.get('trace_id')}")
    if not checks.get("passed"):
        problems.append("checks did not pass")
    if checks.get("unexpected_penetrations"):
        problems.append(f"overlaps: {checks['unexpected_penetrations'][:3]}")
    if not checks.get("slide_check", {}).get("passed"):
        problems.append("slide check did not pass")
    if checks.get("unexplained_count", 1):
        problems.append(f"{checks.get('unexplained_count')} unexplained velocity changes")
    for e in checks.get("expectations", []):
        if not e.get("passed"):
            problems.append(f"expectation failed: {e.get('what')}")
    return problems


def load_story(move_id, spec=None):
    """The presentation source of a move: moves/<id>/story.json, else the legacy "story" block of move.json."""
    p = REPO / "moves" / move_id / "story.json"
    if p.exists():
        story = json.loads(p.read_text())
        if story.get("move", move_id) != move_id:
            raise SystemExit(f"{p.relative_to(REPO)} is for move {story['move']}")
        return story, str(p.relative_to(REPO))
    spec = spec or json.loads((REPO / "moves" / move_id / "move.json").read_text())
    if "story" not in spec:
        raise SystemExit(f"move {move_id} has no story (moves/{move_id}/story.json)")
    return spec["story"], f"moves/{move_id}/move.json#story"


def story_sha256(story):
    return hashlib.sha256(json.dumps(story, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def presentation_gate(move_id):
    """motion_gate plus: the generated presentation was made from today's story and today's saved trace."""
    problems = motion_gate(move_id)
    p = REPO / f"data/presentations/{move_id}.analysis.json"
    if not p.exists():
        return problems + [f"{p.relative_to(REPO)} is missing (python3 scripts/build-move.py {move_id} --presentation)"]
    gen = json.loads(p.read_text()).get("generated_from")
    if not gen:
        return problems + [f"{p.relative_to(REPO)} has no generated_from record (regenerate: --presentation)"]
    if gen.get("trace_sha256") != sha(REPO / f"data/traces/{move_id}.trace.json"):
        problems.append("the presentation was generated from another trace (regenerate: --presentation)")
    if gen.get("story_sha256") != story_sha256(load_story(move_id)[0]):
        problems.append("the story changed since the presentation was generated (regenerate: --presentation)")
    return problems
