"""Ablation of the clip2combo segmentation switches (one more switch on per row) -> data/clip2combo/ablation.json.

    python3 scripts/clip2combo-ablation.py [--site DIR]
Each row runs scripts/clip2combo-eval.py with the later switches off, in a temporary directory.
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
SW = ["repair", "end_by_holder", "shot_aware", "restart_at_carrier", "unseen_pass"]
ap = argparse.ArgumentParser(); ap.add_argument("--site", default=str(REPO / "site")); a = ap.parse_args()
rows = []
for k in range(len(SW) + 1):
    for auto in (False, True):
        off = ",".join(SW[k:])
        with tempfile.TemporaryDirectory() as d:
            cmd = [sys.executable, str(REPO / "scripts/clip2combo-eval.py"), "--outdir", d, "--site", a.site, "--off", off] + (["--auto-end"] if auto else [])
            subprocess.run(cmd, check=True, capture_output=True)
            s = json.loads((Path(d) / "eval.json").read_text())["summary"]
        rows.append({"switches_on": SW[:k], "clip_end": "pipeline estimate" if auto else "user mark", **{x: s[x] for x in ("editor_loads", "editor_clean_no_repairs", "scoring_end_ok", "scorer_ok", "assist_ok", "scorer_and_assist_ok", "family_ok", "name_top1", "name_top3")}})
        print(rows[-1], flush=True)
out = REPO / "data/clip2combo"; out.mkdir(parents=True, exist_ok=True)
(out / "ablation.json").write_text(json.dumps({"description": "clip2combo switches turned on one by one, on the 25 marked NM26 goals (docs/clip2combo.md). Tuned on these same goals: in-sample.", "rows": rows}, indent=1) + "\n")
