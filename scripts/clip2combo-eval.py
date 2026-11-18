"""Run the clip -> combo pipeline on the 25 marked NM26 goals and score it (hypothesis experiment).

    python3 scripts/clip2combo-eval.py [--auto-end] [--no-repair] [--outdir DIR] [--site DIR]

Per goal: the combo is written to DIR/<goal>.json, opened with the editor's own reader (scripts/clip2combo-load.ts, needs
the site/ of PR #23 and node 22), and compared with the user's labels (data/games/nm26-semifinal/goal-labels.json):
scoring end, scorer, assist (the last two touches), family, and the combination name against the nearest library move.
Writes DIR/eval.json.
"""
import argparse, json, subprocess, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import clip2combo as C

# the user's combination names that exist as moves in the editor library (the others, "Short centrifuge" and the
# unnamed ones, have no library move)
NAME2ID = {"Edwallskyffel lang": "edwallskyffel-lang", "Spade": "spade", "Spjass": "spjass", "Ceuleman": "senter-ceuleman"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto-end", action="store_true"); ap.add_argument("--off", default="")
    ap.add_argument("--outdir", default=str(REPO / "out/clip2combo")); ap.add_argument("--site", default=str(REPO / "site"))
    a = ap.parse_args()
    for k in filter(None, a.off.split(",")): C.OPTS[k] = False
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    LB = json.loads((C.D / "goal-labels.json").read_text())["labels"]
    est = {g["id"]: g["goal_moment_estimate_s"] for g in json.loads((C.D / "combo-labels.json").read_text())["goals"]}
    rows = []
    for r in LB:
        t = est[r["id"]] if a.auto_end else r["goal_video_s"]
        c = C.clip_to_combo(r["game"], t, name=f"Draft {r['id']}")
        (out / f"{r['id']}.json").write_text(json.dumps(c, indent=1) + "\n")
        m = c["clip2combo"]; roles = m["roles"]
        scorer = roles[-1] if roles else None
        assist = roles[-2] if len(roles) > 1 else "none"
        row = {"id": r["id"], "clip_end_s": t, "end_ok": m["scoring_end_inferred"] == r["scoring_end"], "scoring_end": r["scoring_end"],
               "touches": roles, "label_scorer": r["scorer"], "label_assist": r["assist"], "scorer_ok": scorer == r["scorer"],
               "assist_ok": assist == r["assist"], "family": m["family"], "label_family": r["family"], "family_ok": m["family"] == r["family"],
               "label_combination": r["combination"], "figures_tracked": m["figures_tracked"], "puck_seen_last6s": m["puck_seen_fraction_last_6s"], "inferred_pass": m["inferred_pass"], "shot_seen": m["shot_seen"]}
        cand = m["library_candidates"] or []
        row["library_top3"] = [(x[1], round(x[0])) for x in cand]; row["n_candidates_top5"] = len(cand)
        if r["combination"] in NAME2ID:
            row["name_in_library"] = True; row["name_top1"] = bool(cand) and cand[0][1] == NAME2ID[r["combination"]]
            row["name_top3"] = any(x[1] == NAME2ID[r["combination"]] for x in cand[:3])
            row["name_top5"] = any(x[1] == NAME2ID[r["combination"]] for x in cand)
        else:
            row["name_in_library"] = False
        rows.append(row)
    # the 15 goals without a user label: the clip ends at the pipeline's own goal-moment estimate; the family is compared with
    # the recognition script's PROPOSED family (agreement, not accuracy: neither side is a label)
    extra = []
    for g in json.loads((C.D / "combo-labels.json").read_text())["goals"]:
        if g["id"] in {r["id"] for r in LB}: continue
        c = C.clip_to_combo(g["game"], g["goal_moment_s"], name=f"Draft {g['id']}")
        (out / f"{g['id']}.json").write_text(json.dumps(c, indent=1) + "\n")
        extra.append({"id": g["id"], "family": c["clip2combo"]["family"], "recognised_family": g["family"], "touches": c["clip2combo"]["roles"], "end_ok": c["clip2combo"]["scoring_end_inferred"] == g["scoring_end"]})
    p = subprocess.run(["node", str(REPO / "scripts/clip2combo-load.ts")] + [str(out / f"{r['id']}.json") for r in rows] + [str(out / f"{e['id']}.json") for e in extra], capture_output=True, text=True,
                       env={**__import__("os").environ, "SITE_DIR": a.site})
    if p.returncode: print(p.stderr, file=sys.stderr)
    loads = {json.loads(l)["file"]: json.loads(l) for l in p.stdout.splitlines() if l.startswith("{")}
    for row in rows:
        row["editor"] = loads.get(row["id"] + ".json")
    for e in extra:
        e["editor_loads"] = bool(loads.get(e["id"] + ".json", {}).get("loads")); e["editor_clean"] = bool(loads.get(e["id"] + ".json", {}).get("loads")) and not loads[e["id"] + ".json"]["notes"]
    n = len(rows); S = lambda k: sum(1 for r in rows if r.get(k))
    named = [r for r in rows if r["name_in_library"]]
    summ = {"goals": n, "auto_end": a.auto_end, "switches_on": [k for k, v in C.OPTS.items() if v],
            "editor_loads": sum(1 for r in rows if r["editor"] and r["editor"]["loads"]),
            "editor_clean_no_repairs": sum(1 for r in rows if r["editor"] and r["editor"]["loads"] and not r["editor"]["notes"] and r["editor"]["stable"] and not r["editor"]["pose_changed"] and not r["editor"]["arrows_dropped"] and not r["editor"]["puck_moved"]),
            "unlabelled_goals": len(extra), "unlabelled_load": sum(e["editor_loads"] for e in extra), "unlabelled_clean": sum(e["editor_clean"] for e in extra), "unlabelled_family_agrees_with_recognition": sum(e["family"] == e["recognised_family"] for e in extra), "unlabelled_end_ok": sum(e["end_ok"] for e in extra), "mean_puck_seen_last6s": round(sum(r["puck_seen_last6s"] for r in rows) / n, 3), "inferred_pass_goals": S("inferred_pass"), "shot_seen_goals": S("shot_seen"), "scoring_end_ok": S("end_ok"), "scorer_ok": S("scorer_ok"), "assist_ok": S("assist_ok"),
            "scorer_and_assist_ok": sum(1 for r in rows if r["scorer_ok"] and r["assist_ok"]), "family_ok": S("family_ok"),
            "named_in_library": len(named), "name_top1": sum(1 for r in named if r["name_top1"]), "name_top3": sum(1 for r in named if r["name_top3"]), "name_top5": sum(1 for r in named if r["name_top5"])}
    (out / "eval.json").write_text(json.dumps({"summary": summ, "rows": rows, "unlabelled": extra}, indent=1) + "\n")
    print(json.dumps(summ))
    for r in rows:
        print(f"{r['id']:10s} end{'+' if r['end_ok'] else '-'} {'>'.join(r['touches']) or '-':12s} truth {r['label_assist']}>{r['label_scorer']:3s} {'OK ' if r['scorer_ok'] and r['assist_ok'] else '.. '}"
              f"fam {r['family']:10s}/{r['label_family']:10s}{'OK' if r['family_ok'] else '..'} name {r['label_combination']} -> {[x[0] for x in r['library_top3'][:2]]}")

if __name__ == "__main__":
    main()
