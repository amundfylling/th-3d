"""Fetch the trained models from their GitHub release into out/synth/, checked against their sha256 (docs/models.md).

    python3 scripts/fetch-models.py [model_id ...] [--list] [--force]

The models are listed in data/models/manifest.json: release tag, file name, local path, sha256 and size of each.
Without ids every model is fetched. A local file that already matches its sha256 is kept. A local file with a different
sha256 (for example a model retrained here) is NOT overwritten unless --force is given; the script then exits 1, so a
rebuild never silently mixes a published and a local model. --list prints each model and whether its local copy matches.
Needs only the standard library and curl. Exit 0 when every requested model is present and matches.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((REPO / "data/models/manifest.json").read_text())


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def url(m): return f"{MANIFEST['release']['download_base']}/{m['file']}"


def state(m):
    p = REPO / m["local_path"]
    if not p.exists(): return "missing"
    return "ok" if sha256(p) == m["sha256"] else "differs"


def fetch(m, force=False):
    p = REPO / m["local_path"]; s = state(m)
    if s == "ok": print(f"  {m['id']}: present, sha256 ok"); return 0
    if s == "differs" and not force:
        print(f"  {m['id']}: {m['local_path']} differs from the published sha256 (a local model?); kept. --force replaces it")
        return 1
    p.parent.mkdir(parents=True, exist_ok=True); tmp = p.with_suffix(p.suffix + ".part")
    r = subprocess.run(["curl", "-sS", "-L", "--fail", "-o", str(tmp), url(m)])
    if r.returncode: tmp.unlink(missing_ok=True); print(f"  {m['id']}: download failed (curl exit {r.returncode})"); return 1
    if sha256(tmp) != m["sha256"]: tmp.unlink(); print(f"  {m['id']}: sha256 MISMATCH after download; nothing written"); return 1
    tmp.replace(p); print(f"  {m['id']}: fetched {m['local_path']} ({p.stat().st_size / 1e6:.1f} MB), sha256 ok"); return 0


def main(argv):
    ids = [a for a in argv if not a.startswith("--")]
    models = MANIFEST["models"]
    unknown = [i for i in ids if i not in {m["id"] for m in models}]
    if unknown: sys.exit(f"unknown model {unknown}; models: {[m['id'] for m in models]}")
    todo = [m for m in models if not ids or m["id"] in ids]
    if "--list" in argv:
        for m in todo: print(f"{m['id']:14s} {m['local_path']:36s} {state(m):8s} {m['status']}")
        return 0
    print(f"release {MANIFEST['release']['tag']}")
    return 1 if sum(fetch(m, "--force" in argv) for m in todo) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
