"""Analysis video for a move, generated from its story (moves/<id>/story.json) and its built trace: the same VAR-style
breakdown as the hand-made videos (data/presentations/*.analysis.json, remotion/AnalysisVideo.tsx), with no hand timing.

    python3 scripts/build-move.py <move-id> --presentation     presentation only, from the saved trace (no simulation)
    python3 scripts/build-move.py <move-id> --video-spec       build the move, then the presentation

Writes data/presentations/<id>.analysis.json (generated: never edit it; edit the story and regenerate) and
remotion/encyclopedia-registry.ts (every move with a saved trace, checks and presentation). The presentation is only
written when the saved trace still matches the move file, the engine and the model and passed its checks
(scripts/shotlib/identity.py motion_gate); otherwise rebuild the move first. Render: node scripts/video.ts ... move:<id>.

Story file (moves/<id>/story.json; older moves keep a "story" block in move.json, read when there is no story.json):
  {"schema": "move-story/1", "move": "<id>",
   "title": "HJERPEFINTE", "subtitle": "...", "bug": "HJERPEFINTE", "end_steps": ["...", "..."],
   "theme": "classic" | "nbhf",                                   (optional, remotion/theme.ts; default classic)
   "setup": {"title": "THE SET-UP", "text": "...", "highlight": {"W-C": "CENTRE"}, "puck_label": "PUCK ON THE BLADE",
             "frame_highlighted": false},
   "beats": [{"contact": "shot", "title": "THE SHOT", "text": "...", "label": "SHOT · BLADE", "label_offset_px": [150, 120],
              "turn": {"figure": "W-C", "event": "turn.onset", "direction": "ccw", "label": "TURN"},
              "highlight": {"E-G": "GOALIE"}, "freeze_frames": 96, "camera": {"offset_mm": [-150, -170, 230], "fov_deg": 30}},
             {"id": "feint", "event": "goalie.reacts", "title": "...", "text": "..."}],
   "timing": {...DEFAULT_TIMING overrides...},
   "camera": {"<view>": {"offset_mm": [dx, dy, height], "fov_deg": 30}}}   views: intro_high, broadcast, setup, beat, replay
One beat per moment the video stops at, in time order: a named contact ({"contact": id}) or a move event without a
contact ({"id": "feint", "event": "feint.onset"}, e.g. a feint the goalie reacts to); a beat's "highlight" ({pid: label})
marks figures during its freeze, and its camera view then takes them in. "setup": {"frame_highlighted": true} does the
same for the set-up view. The timeline: intro, the move at full speed, goal, rewind, the set-up (freeze), then per beat a
slow-motion approach and a freeze with its text, the shot to the goal, a replay. Slow-motion rates and camera views are
derived from the trace (rates so each approach lasts about approach_s on screen; views aimed at each contact point from
the broadcast side). Nothing in the story changes the trace.
"""
import json

import numpy as np

from . import identity
from . import world as W

FPS = 30
# presentation timing (frames at 30 fps, rates as source seconds per presentation second); story.json "timing" overrides
DEFAULT_TIMING = {"intro_frames": 45, "goal_hold_frames": 20, "rewind_rate": 1.2, "setup_set_frames": 20, "setup_freeze_frames": 108,
                  "to_beat_frames": 33, "approach_s": 2.0, "beat_freeze_frames": 96, "shot_out_min_rate": 0.15, "goal_freeze_frames": 30,
                  "to_replay_frames": 38, "replay_rate": 0.4, "outro_frames": 50}
# camera offsets from each view's target (mm: along the attack, toward the broadcast side -y, height) and vertical fov (deg)
DEFAULT_CAMERA = {"intro_high": {"offset_mm": [-590, -820, 820], "fov_deg": 30}, "broadcast": {"offset_mm": [-365, -330, 380], "fov_deg": 30},
                  "setup": {"offset_mm": [50, -225, 178], "fov_deg": 30}, "beat": {"offset_mm": [-150, -170, 230], "fov_deg": 30},
                  "replay": {"offset_mm": [-180, -330, 330], "fov_deg": 32}}
THEMES = ("classic", "nbhf")


def _r(x, n=4):
    return round(float(x), n)


load_story = identity.load_story


def views_for(trace, beats_ev, attack, setup_pids=(), cam=None):
    """Camera views (mm, deg) from the trace: the broadcast side is -y; mirrored in x when the attack goes to the W goal."""
    cam = {k: {**v, **(cam or {}).get(k, {})} for k, v in DEFAULT_CAMERA.items()}
    s = 1.0 if attack == "E" else -1.0
    nodes = trace["puck"]["nodes"]
    P = np.array([[n["x_mm"], n["y_mm"]] for n in nodes])
    c = (P.min(0) + P.max(0)) / 2
    view = lambda off, tgt, fov=30: {"positionMm": [_r(tgt[0] + s * off[0], 1), _r(tgt[1] + off[1], 1), _r(off[2], 1)], "targetMm": [_r(tgt[0], 1), _r(tgt[1], 1), _r(tgt[2], 1)], "fovDeg": fov}
    t0 = nodes[0]

    def framed(off, p, pids, t, fov):
        """A view of the puck that also takes in the given figures: aimed between them and pulled back with their spread."""
        pts = [np.array(p)] + [_figure_xy(trace, pid, t) for pid in pids]
        tgt = np.mean(pts, axis=0)
        spread = max(float(np.linalg.norm(q - tgt)) for q in pts)
        k = min(2.2, max(1.0, 0.6 + spread / 70.0)) if pids else 1.0
        return view(tuple(o * k for o in off), (tgt[0], tgt[1], 8.0 if not pids else 0.0), fov)

    o = lambda k: tuple(cam[k]["offset_mm"])
    views = {"intro_high": view(o("intro_high"), (c[0], 0.0, 0.0), cam["intro_high"]["fov_deg"]),
             "broadcast": view(o("broadcast"), (c[0], c[1] * 0.5, 0.0), cam["broadcast"]["fov_deg"]),
             "replay": view(o("replay"), (c[0], c[1] * 0.5, 0.0), cam["replay"]["fov_deg"])}
    if setup_pids:
        views["setup"] = framed(o("setup"), (t0["x_mm"], t0["y_mm"]), setup_pids, t0["t"], cam["setup"]["fov_deg"])
    else:
        views["setup"] = view(o("setup"), (t0["x_mm"] - s * 10, t0["y_mm"], 12.0), cam["setup"]["fov_deg"])
    for b, ev in beats_ev:
        bc = {**cam["beat"], **b.get("camera", {})}
        p = _puck_at(trace, ev["t_estimate"])
        views[f"beat_{_key(b)}"] = framed(tuple(bc["offset_mm"]), p, list(b.get("highlight", {})), ev["t_estimate"], bc["fov_deg"])
    return views


def _figure_xy(trace, pid, t):
    """A figure's pivot on its slot at time t (arc keyframes interpolated linearly: for camera aiming only); a figure the
    trace does not move stands at its assembly pose."""
    f = trace["figures"].get(pid)
    if not isinstance(f, dict):
        return np.array(W.ASM[pid]["pivot_mm"][:2], dtype=float)
    ks = f["arc_keyframes"]
    a = float(np.interp(t, [k["t"] for k in ks], [k["arc_mm"] for k in ks]))
    return W.Slot(pid).at(a)


def _puck_at(trace, t):
    nodes = trace["puck"]["nodes"]
    nt = np.array([n["t"] for n in nodes])
    return [float(np.interp(t, nt, [n["x_mm"] for n in nodes])), float(np.interp(t, nt, [n["y_mm"] for n in nodes]))]


def _key(b):
    return b.get("contact") or b["id"]


def _ev(b):
    return b.get("event") or f"contact.{b['contact']}"


def make(spec, trace, story=None):
    story = story if story is not None else spec["story"]
    unknown = set(story.get("timing", {})) - set(DEFAULT_TIMING)
    if unknown:
        raise SystemExit(f"story timing: unknown keys {sorted(unknown)} (known: {sorted(DEFAULT_TIMING)})")
    unknown = set(story.get("camera", {})) - set(DEFAULT_CAMERA)
    if unknown:
        raise SystemExit(f"story camera: unknown views {sorted(unknown)} (known: {sorted(DEFAULT_CAMERA)})")
    tm = {**DEFAULT_TIMING, **story.get("timing", {})}
    ev = {e["id"]: e for e in trace["events"]}
    t_start = trace["time_base"]["window_s"][0]
    goal = ev.get("goal_entry")
    net = ev.get("goal_net")
    t_end = min(trace["time_base"]["window_s"][1], (net["t_estimate"] + 0.15) if net else trace["time_base"]["window_s"][1])
    missing = [_ev(b) for b in story["beats"] if _ev(b) not in ev]
    if missing:
        raise SystemExit(f"story beats name events the trace does not have: {missing} (trace events: {sorted(ev)})")
    beats = [(b, ev[_ev(b)]) for b in story["beats"]]
    attack = (spec.get("expect", {}).get("goal") or "E")
    rate = lambda dur: max(0.05, min(1.0, round(dur / tm["approach_s"], 3)))  # an approach lasts about approach_s on screen
    seg = [{"id": "intro", "kind": "hold", "at": t_start, "frames": tm["intro_frames"]},
           {"id": "full", "kind": "play", "from": t_start, "to": _r(t_end), "rate": 1},
           {"id": "goal_hold", "kind": "hold", "at": _r(t_end), "frames": tm["goal_hold_frames"]},
           {"id": "rewind", "kind": "rewind", "from": _r(t_end), "to": t_start, "rate": tm["rewind_rate"]},
           {"id": "setup_set", "kind": "hold", "at": t_start, "frames": tm["setup_set_frames"]},
           {"id": "setup_freeze", "kind": "hold", "at": t_start, "frames": tm["setup_freeze_frames"]}]
    prev = t_start
    for b, e in beats:
        k, en = _key(b), _ev(b)
        seg += [{"id": f"to_{k}", "kind": "hold", "at": prev if prev == t_start else {"event": prev_e}, "frames": tm["to_beat_frames"]},
                {"id": f"{k}_in", "kind": "play", "from": prev if prev == t_start else {"event": prev_e}, "to": {"event": en},
                 "rate": rate(e["t_estimate"] - prev)},
                {"id": f"{k}_freeze", "kind": "hold", "at": {"event": en}, "frames": b.get("freeze_frames", tm["beat_freeze_frames"])}]
        prev, prev_e = e["t_estimate"], en
    t_goal = _r(goal["t_estimate"] + 0.05) if goal else _r(t_end)
    seg += [{"id": "shot_out", "kind": "play", "from": {"event": prev_e}, "to": t_goal, "rate": rate(t_goal - prev) if t_goal - prev > 0.3 else tm["shot_out_min_rate"]},
            {"id": "goal_freeze", "kind": "hold", "at": t_goal, "frames": tm["goal_freeze_frames"]},
            {"id": "to_replay", "kind": "hold", "at": t_goal, "frames": tm["to_replay_frames"]},
            {"id": "replay", "kind": "play", "from": t_start, "to": _r(t_end), "rate": tm["replay_rate"]},
            {"id": "outro", "kind": "hold", "at": _r(t_end), "frames": tm["outro_frames"]}]
    cam = [{"at": "intro.start", "view": "intro_high"}, {"at": "intro.start+0.15", "view": "intro_high"}, {"at": "intro.end-0.1", "view": "broadcast"},
           {"at": "goal_hold.end", "view": "broadcast"}, {"at": "setup_set.end", "view": "setup", "lift": 60}]
    last_view = "setup"
    for b, _ in beats:
        k = _key(b)
        cam += [{"at": f"to_{k}.start", "view": last_view}, {"at": f"to_{k}.end", "view": f"beat_{k}", "lift": 60}]
        last_view = f"beat_{k}"
    cam += [{"at": "to_replay.start", "view": last_view}, {"at": "to_replay.end", "view": "replay", "lift": 80}]
    su = story["setup"]
    first = _key(beats[0][0])
    chapters = [{"id": "setup", "number": "1", "title": su["title"], "text": su["text"], "from": "setup_set.start", "to": f"to_{first}.start+0.2"}]
    for i, (b, _) in enumerate(beats):
        k = _key(b)
        nxt = f"to_{_key(beats[i + 1][0])}.start+0.2" if i + 1 < len(beats) else "goal_freeze.end"
        chapters.append({"id": k, "number": str(i + 2), "title": b["title"], "text": b["text"], "from": f"to_{k}.end-0.2", "to": nxt})
    gr = [{"id": "title", "type": "title_card", "from": "intro.start+0.3", "to": "intro.end"},
          {"id": "goal_full", "type": "goal_banner", "from": "goal_hold.start", "to": "goal_hold.end"}]
    for pid, label in su.get("highlight", {}).items():
        gr.append({"id": f"hl_{pid}", "type": "highlight", "target": pid, "label": label, "accent": "cyan", "from": "setup_set.start", "to": f"to_{first}.start+0.3"})
    if su.get("puck_label"):
        gr.append({"id": "puck_start", "type": "puck_marker", "label": su["puck_label"], "accent": "amber", "from": "setup_freeze.start+0.2", "to": f"to_{first}.start+0.3"})
    for i, (b, e) in enumerate(beats):
        k = _key(b)
        end = f"to_{_key(beats[i + 1][0])}.start+0.3" if i + 1 < len(beats) else "shot_out.start+0.3"
        if b.get("turn"):
            tr = b["turn"]
            gr.append({"id": f"turn_{k}", "type": "rotation_arrow", "target": tr["figure"], "event": tr["event"], "direction": tr["direction"], "radius_mm": 36,
                       "start_deg": tr.get("start_deg", -70 if tr["direction"] == "ccw" else 30), "sweep_deg": tr.get("sweep_deg", 60), "label": tr.get("label", "TURN"),
                       "accent": "cyan", "label_offset_px": [0, -45], "from": f"to_{k}.end", "to": f"{k}_freeze.end"})
        for pid, label in b.get("highlight", {}).items():
            gr.append({"id": f"hl_{k}_{pid}", "type": "highlight", "target": pid, "label": label, "accent": "amber", "from": f"to_{k}.end", "to": f"{k}_freeze.end"})
        if "contact" not in b:
            continue
        gr.append({"id": f"contact_{k}", "type": "contact_marker", "target": e["figure"], "event": f"contact.{k}", "label": b["label"], "accent": "amber",
                   "from": f"{k}_freeze.start+0.15", "to": end, **({"label_offset_px": b["label_offset_px"]} if "label_offset_px" in b else {})})
        gr.append({"id": f"dir_{k}", "type": "puck_arrow", "event": f"contact.{k}", "start_mm": 18, "length_mm": 60, "accent": "amber", "from": f"{k}_freeze.start+0.6", "to": end})
        gr.append({"id": f"trail_{k}", "type": "puck_trail", "event": f"contact.{k}", "back_s": 0.0,
                   "from": f"{k}_freeze.end" if i + 1 < len(beats) else "shot_out.start", "to": f"to_{_key(beats[i + 1][0])}.start+0.3" if i + 1 < len(beats) else "goal_freeze.end"})
    gr += [{"id": "goal_slow", "type": "goal_banner", "from": "goal_freeze.start", "to": "goal_freeze.end"},
           {"id": "trail_replay", "type": "puck_trail", "event": next(_ev(b) for b, _ in beats if "contact" in b), "back_s": 0.0, "from": "replay.start", "to": "replay.end"},
           {"id": "end", "type": "end_card", "from": "replay.end-0.3", "to": "outro.end"}]
    return {"schema": "shot-analysis/1", "analysis_id": f"analysis.{spec['id']}.v1", "trace_id": trace["trace_id"],
            "note": f"Generated by scripts/shotlib/presentation.py from moves/{spec['id']}/story.json and data/traces/{spec['id']}.trace.json; do not edit by hand, change the story and regenerate.",
            "fps": FPS, "width": 1920, "height": 1080, "segments": seg, "unlabelled_holds": ["intro", "outro", "to_replay"], "replay_segments": ["replay"],
            "views": views_for(trace, beats, attack, [p for p in su.get("highlight", {}) if su.get("frame_highlighted")], story.get("camera")),
            "camera": cam, "chapters": chapters, "graphics": gr}


def write(spec):
    """Writes the presentation of a move from its story and SAVED trace. Refuses (SystemExit) when the trace is stale or
    failed its checks: a presentation never quietly reuses motion that no longer matches the move, engine or model."""
    mid = spec["id"]
    problems = identity.motion_gate(mid)
    if problems:
        raise SystemExit(f"{mid}: the saved trace cannot be used for a presentation; rebuild it (python3 scripts/build-move.py {mid} --video-spec):\n  - " + "\n  - ".join(problems))
    tpath = W.REPO / f"data/traces/{mid}.trace.json"
    trace = json.loads(tpath.read_text())
    story, story_src = load_story(mid, spec)
    if story.get("theme", "classic") not in THEMES:
        raise SystemExit(f"story theme {story['theme']} is not one of {THEMES}")
    pres = make(spec, trace, story)
    pres["generated_from"] = {"story": story_src, "story_sha256": identity.story_sha256(story),
                              "trace": f"data/traces/{mid}.trace.json", "trace_sha256": identity.sha(tpath), "generator": "scripts/shotlib/presentation.py"}
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
        if sp.get("legacy") or not ("story" in sp or (mf.parent / "story.json").exists()) or not all((W.REPO / p).exists() for p in (f"data/traces/{mid}.trace.json", f"shots/{mid}/checks.json", f"data/presentations/{mid}.analysis.json")):
            continue
        rows.append((mid, load_story(mid, sp)[0]))
    v = lambda mid: "m_" + mid.replace("-", "_")
    lines = ["// Generated by scripts/shotlib/presentation.py (scripts/build-move.py --presentation / --video-spec); do not edit.",
             "// One analysis composition per encyclopedia move (moves/<id>/move.json + story.json) with a saved trace, contact checks and presentation.",
             'import type { AnalysisSpec } from "../src/model/analysis.ts";', 'import type { AnalysisTrace, ContactChecks } from "./AnalysisVideo.tsx";']
    for mid, _ in rows:
        lines += [f'import {v(mid)}_trace from "../data/traces/{mid}.trace.json" with {{ type: "json" }};',
                  f'import {v(mid)}_checks from "../shots/{mid}/checks.json" with {{ type: "json" }};',
                  f'import {v(mid)}_spec from "../data/presentations/{mid}.analysis.json" with {{ type: "json" }};']
    lines += ["", "export interface EncyclopediaEntry {", "  id: string;", "  spec: AnalysisSpec;", "  trace: AnalysisTrace;", "  checks: ContactChecks;",
              "  text: { kicker: string; title: string; subtitle: string; bug: string; endTitle: string; endSteps: string[] };",
              '  theme: "classic" | "nbhf";', "}", "",
              "export const ENCYCLOPEDIA: EncyclopediaEntry[] = ["]
    for mid, st in rows:
        text = {"kicker": st.get("kicker", "SHOT ENCYCLOPEDIA"), "title": st["title"], "subtitle": st["subtitle"], "bug": st.get("bug", st["title"]),
                "endTitle": st.get("end_title", st["title"]), "endSteps": st["end_steps"]}
        lines.append(f"  {{ id: {json.dumps(mid)}, spec: {v(mid)}_spec as unknown as AnalysisSpec, trace: {v(mid)}_trace as unknown as AnalysisTrace, checks: {v(mid)}_checks, text: {json.dumps(text, ensure_ascii=False)}, theme: {json.dumps(st.get('theme', 'classic'))} }},")
    lines += ["];", ""]
    (W.REPO / "remotion/encyclopedia-registry.ts").write_text("\n".join(lines))
