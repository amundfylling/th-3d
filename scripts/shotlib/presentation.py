"""Analysis video for a move, generated from its move file's `story` and its built trace: the same VAR-style breakdown
as the hand-made videos (data/presentations/*.analysis.json, remotion/AnalysisVideo.tsx), with no hand timing.

    /root/venvs/blender/bin/python scripts/build-move.py <move-id> --video-spec

Writes data/presentations/<id>.analysis.json and remotion/encyclopedia-registry.ts (every move with a saved trace and a
presentation). Render: node scripts/analysis-render.ts move:<id>.

Story block (move.json `story`):
  {"title": "HJERPEFINTE", "subtitle": "...", "bug": "HJERPEFINTE", "end_steps": ["...", "..."],
   "setup": {"title": "THE SET-UP", "text": "...", "highlight": {"W-C": "CENTRE"}, "puck_label": "PUCK ON THE BLADE"},
   "beats": [{"contact": "shot", "title": "THE SHOT", "text": "...", "label": "SHOT · BLADE",
              "turn": {"figure": "W-C", "event": "turn.onset", "direction": "ccw", "label": "TURN"}}]}
One beat per named contact the video stops at, in time order. The timeline: intro, the move at full speed, goal, rewind,
the set-up (freeze), then per beat a slow-motion approach and a freeze with its text, the shot to the goal, a replay.
Timing, slow-motion rates and camera views are derived from the trace (rates so each approach lasts about 2 s; views
aimed at each contact point from the broadcast side).
"""
import json

import numpy as np

from . import world as W

FPS = 30


def _r(x, n=4):
    return round(float(x), n)


def views_for(trace, beats_ev, attack):
    """Camera views (mm, deg) from the trace: the broadcast side is -y; mirrored in x when the attack goes to the W goal."""
    s = 1.0 if attack == "E" else -1.0
    nodes = trace["puck"]["nodes"]
    P = np.array([[n["x_mm"], n["y_mm"]] for n in nodes])
    c = (P.min(0) + P.max(0)) / 2
    view = lambda off, tgt, fov=30: {"positionMm": [_r(tgt[0] + s * off[0], 1), _r(tgt[1] + off[1], 1), _r(off[2], 1)], "targetMm": [_r(tgt[0], 1), _r(tgt[1], 1), _r(tgt[2], 1)], "fovDeg": fov}
    t0 = nodes[0]
    views = {"intro_high": view((-590, -820, 820), (c[0], 0.0, 0.0)), "broadcast": view((-365, -330, 380), (c[0], c[1] * 0.5, 0.0)),
             "setup": view((50, -225, 178), (t0["x_mm"] - s * 10, t0["y_mm"], 12.0)), "replay": view((-180, -330, 330), (c[0], c[1] * 0.5, 0.0), 32)}
    for b, ev in beats_ev:
        p = _puck_at(trace, ev["t_estimate"])
        views[f"beat_{b['contact']}"] = view((-150, -170, 230), (p[0], p[1], 8.0))
    return views


def _puck_at(trace, t):
    nodes = trace["puck"]["nodes"]
    nt = np.array([n["t"] for n in nodes])
    return [float(np.interp(t, nt, [n["x_mm"] for n in nodes])), float(np.interp(t, nt, [n["y_mm"] for n in nodes]))]


def make(spec, trace):
    story = spec["story"]
    ev = {e["id"]: e for e in trace["events"]}
    t_start = trace["time_base"]["window_s"][0]
    goal = ev.get("goal_entry")
    net = ev.get("goal_net")
    t_end = min(trace["time_base"]["window_s"][1], (net["t_estimate"] + 0.15) if net else trace["time_base"]["window_s"][1])
    beats = [(b, ev[f"contact.{b['contact']}"]) for b in story["beats"]]
    attack = (spec.get("expect", {}).get("goal") or "E")
    rate = lambda dur: max(0.05, min(1.0, round(dur / 2.0, 3)))  # an approach lasts about 2 s on screen
    seg = [{"id": "intro", "kind": "hold", "at": t_start, "frames": 45},
           {"id": "full", "kind": "play", "from": t_start, "to": _r(t_end), "rate": 1},
           {"id": "goal_hold", "kind": "hold", "at": _r(t_end), "frames": 20},
           {"id": "rewind", "kind": "rewind", "from": _r(t_end), "to": t_start, "rate": 1.2},
           {"id": "setup_set", "kind": "hold", "at": t_start, "frames": 20},
           {"id": "setup_freeze", "kind": "hold", "at": t_start, "frames": 108}]
    prev = t_start
    for b, e in beats:
        k = b["contact"]
        seg += [{"id": f"to_{k}", "kind": "hold", "at": prev if prev == t_start else {"event": f"contact.{prev_k}"}, "frames": 33},
                {"id": f"{k}_in", "kind": "play", "from": prev if prev == t_start else {"event": f"contact.{prev_k}"}, "to": {"event": f"contact.{k}"},
                 "rate": rate(e["t_estimate"] - prev)},
                {"id": f"{k}_freeze", "kind": "hold", "at": {"event": f"contact.{k}"}, "frames": 96}]
        prev, prev_k = e["t_estimate"], k
    t_goal = _r(goal["t_estimate"] + 0.05) if goal else _r(t_end)
    seg += [{"id": "shot_out", "kind": "play", "from": {"event": f"contact.{prev_k}"}, "to": t_goal, "rate": rate(t_goal - prev) if t_goal - prev > 0.3 else 0.15},
            {"id": "goal_freeze", "kind": "hold", "at": t_goal, "frames": 30},
            {"id": "to_replay", "kind": "hold", "at": t_goal, "frames": 38},
            {"id": "replay", "kind": "play", "from": t_start, "to": _r(t_end), "rate": 0.4},
            {"id": "outro", "kind": "hold", "at": _r(t_end), "frames": 50}]
    cam = [{"at": "intro.start", "view": "intro_high"}, {"at": "intro.start+0.15", "view": "intro_high"}, {"at": "intro.end-0.1", "view": "broadcast"},
           {"at": "goal_hold.end", "view": "broadcast"}, {"at": "setup_set.end", "view": "setup", "lift": 60}]
    last_view = "setup"
    for b, _ in beats:
        k = b["contact"]
        cam += [{"at": f"to_{k}.start", "view": last_view}, {"at": f"to_{k}.end", "view": f"beat_{k}", "lift": 60}]
        last_view = f"beat_{k}"
    cam += [{"at": "to_replay.start", "view": last_view}, {"at": "to_replay.end", "view": "replay", "lift": 80}]
    su = story["setup"]
    first = beats[0][0]["contact"]
    chapters = [{"id": "setup", "number": "1", "title": su["title"], "text": su["text"], "from": "setup_set.start", "to": f"to_{first}.start+0.2"}]
    for i, (b, _) in enumerate(beats):
        k = b["contact"]
        nxt = f"to_{beats[i + 1][0]['contact']}.start+0.2" if i + 1 < len(beats) else "goal_freeze.end"
        chapters.append({"id": k, "number": str(i + 2), "title": b["title"], "text": b["text"], "from": f"to_{k}.end-0.2", "to": nxt})
    gr = [{"id": "title", "type": "title_card", "from": "intro.start+0.3", "to": "intro.end"},
          {"id": "goal_full", "type": "goal_banner", "from": "goal_hold.start", "to": "goal_hold.end"}]
    for pid, label in su.get("highlight", {}).items():
        gr.append({"id": f"hl_{pid}", "type": "highlight", "target": pid, "label": label, "accent": "cyan", "from": "setup_set.start", "to": f"to_{first}.start+0.3"})
    if su.get("puck_label"):
        gr.append({"id": "puck_start", "type": "puck_marker", "label": su["puck_label"], "accent": "amber", "from": "setup_freeze.start+0.2", "to": f"to_{first}.start+0.3"})
    for i, (b, e) in enumerate(beats):
        k = b["contact"]
        end = f"to_{beats[i + 1][0]['contact']}.start+0.3" if i + 1 < len(beats) else "shot_out.start+0.3"
        if b.get("turn"):
            tr = b["turn"]
            gr.append({"id": f"turn_{k}", "type": "rotation_arrow", "target": tr["figure"], "event": tr["event"], "direction": tr["direction"], "radius_mm": 36,
                       "start_deg": tr.get("start_deg", -70 if tr["direction"] == "ccw" else 30), "sweep_deg": tr.get("sweep_deg", 60), "label": tr.get("label", "TURN"),
                       "accent": "cyan", "label_offset_px": [0, -45], "from": f"to_{k}.end", "to": f"{k}_freeze.end"})
        gr.append({"id": f"contact_{k}", "type": "contact_marker", "target": e["figure"], "event": f"contact.{k}", "label": b["label"], "accent": "amber",
                   "from": f"{k}_freeze.start+0.15", "to": end})
        gr.append({"id": f"dir_{k}", "type": "puck_arrow", "event": f"contact.{k}", "start_mm": 18, "length_mm": 60, "accent": "amber", "from": f"{k}_freeze.start+0.6", "to": end})
        gr.append({"id": f"trail_{k}", "type": "puck_trail", "event": f"contact.{k}", "back_s": 0.0,
                   "from": f"{k}_freeze.end" if i + 1 < len(beats) else "shot_out.start", "to": f"to_{beats[i + 1][0]['contact']}.start+0.3" if i + 1 < len(beats) else "goal_freeze.end"})
    gr += [{"id": "goal_slow", "type": "goal_banner", "from": "goal_freeze.start", "to": "goal_freeze.end"},
           {"id": "trail_replay", "type": "puck_trail", "event": f"contact.{beats[0][0]['contact']}", "back_s": 0.0, "from": "replay.start", "to": "replay.end"},
           {"id": "end", "type": "end_card", "from": "replay.end-0.3", "to": "outro.end"}]
    return {"schema": "shot-analysis/1", "analysis_id": f"analysis.{spec['id']}.v1", "trace_id": trace["trace_id"],
            "note": f"Generated by scripts/shotlib/presentation.py from moves/{spec['id']}/move.json (story) and data/traces/{spec['id']}.trace.json; do not edit by hand, change the story and regenerate.",
            "fps": FPS, "width": 1920, "height": 1080, "segments": seg, "unlabelled_holds": ["intro", "outro", "to_replay"], "replay_segments": ["replay"],
            "views": views_for(trace, beats, attack), "camera": cam, "chapters": chapters, "graphics": gr}


def write(spec):
    mid = spec["id"]
    trace = json.loads((W.REPO / f"data/traces/{mid}.trace.json").read_text())
    pres = make(spec, trace)
    out = W.REPO / f"data/presentations/{mid}.analysis.json"
    out.write_text(json.dumps(pres, indent=1, ensure_ascii=False) + "\n")
    write_registry()
    return str(out.relative_to(W.REPO))


def write_registry():
    """remotion/encyclopedia-registry.ts: one analysis composition per move with a saved trace, checks and presentation."""
    rows = []
    for mf in sorted((W.REPO / "moves").glob("*/move.json")):
        sp = json.loads(mf.read_text())
        mid = sp["id"]
        if sp.get("legacy") or "story" not in sp or not all((W.REPO / p).exists() for p in (f"data/traces/{mid}.trace.json", f"shots/{mid}/checks.json", f"data/presentations/{mid}.analysis.json")):
            continue
        st = sp["story"]
        rows.append((mid, st))
    v = lambda mid: "m_" + mid.replace("-", "_")
    lines = ["// Generated by scripts/shotlib/presentation.py (scripts/build-move.py --video-spec); do not edit.",
             "// One analysis composition per encyclopedia move (moves/<id>/move.json) with a saved trace, contact checks and presentation.",
             'import type { AnalysisSpec } from "../src/model/analysis.ts";', 'import type { AnalysisTrace, ContactChecks } from "./AnalysisVideo.tsx";']
    for mid, _ in rows:
        lines += [f'import {v(mid)}_trace from "../data/traces/{mid}.trace.json" with {{ type: "json" }};',
                  f'import {v(mid)}_checks from "../shots/{mid}/checks.json" with {{ type: "json" }};',
                  f'import {v(mid)}_spec from "../data/presentations/{mid}.analysis.json" with {{ type: "json" }};']
    lines += ["", "export interface EncyclopediaEntry {", "  id: string;", "  spec: AnalysisSpec;", "  trace: AnalysisTrace;", "  checks: ContactChecks;",
              "  text: { kicker: string; title: string; subtitle: string; bug: string; endTitle: string; endSteps: string[] };", "}", "",
              "export const ENCYCLOPEDIA: EncyclopediaEntry[] = ["]
    for mid, st in rows:
        text = {"kicker": st.get("kicker", "SHOT ENCYCLOPEDIA"), "title": st["title"], "subtitle": st["subtitle"], "bug": st.get("bug", st["title"]),
                "endTitle": st.get("end_title", st["title"]), "endSteps": st["end_steps"]}
        lines.append(f"  {{ id: {json.dumps(mid)}, spec: {v(mid)}_spec as unknown as AnalysisSpec, trace: {v(mid)}_trace as unknown as AnalysisTrace, checks: {v(mid)}_checks, text: {json.dumps(text, ensure_ascii=False)} }},")
    lines += ["];", ""]
    (W.REPO / "remotion/encyclopedia-registry.ts").write_text("\n".join(lines))
