"""Deterministic transforms on a move-spec/1 recipe (experiment, PROPOSED). Each takes a spec dict and returns a new one.

mirror:   reflect the move in the table's long axis (y -> -y): headings negate, goalies re-placed by y, puck start and the
          expected goal window mirrored. Arcs of SKATERS are kept (a figure cannot leave its slot), which is exactly where a
          pure mirror stops being physical (the slots are not symmetric and the blades are chiral) - the experiment measures it.
rot180:   mirror, but the figure turns 180 deg about its axis instead of being reflected (blade ends up on the other side)
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shotlib import world as W  # noqa: E402


def _walk_theta(th, fn):
    if "start" in th:
        th["start"] = fn(th["start"])
    for tr in th.get("turns", []):
        tr[2], tr[3] = fn(tr[2]), fn(tr[3])


def mirror(spec, new_id, new_name, groove_flip=False):
    s = copy.deepcopy(spec)
    s["id"], s["name"], s["trace_id"] = new_id, new_name, f"trace.{new_id}.v1"
    ang = (lambda v: -v) if not groove_flip else (lambda v: 180.0 - v)
    for pid, fs in s["figures"].items():
        if "static" in fs:
            st = fs["static"]
            if isinstance(st, dict):
                if "theta_deg" in st:
                    st["theta_deg"] = ang(st["theta_deg"])
                if "y_mm" in st:
                    st["y_mm"] = -st["y_mm"]
            continue
        if "theta" in fs:
            _walk_theta(fs["theta"], ang)
        if W.kind_of(pid) == "goalie":  # re-place by y
            slot = W.Slot(pid)
            conv = lambda a: slot.arc_of_y(-float(slot.at(a)[1]))
            for k in fs["arc"].get("keys", []):
                k[1] = conv(k[1])
            for m in fs["arc"].get("moves", []):
                m[2], m[4] = conv(m[2]), conv(m[4])
    st = s["puck"]["start"]
    if "local_mm" in st:
        loc = st["local_mm"]
        st["local_mm"] = [-loc[0], loc[1]] if groove_flip else [loc[0], -loc[1]]
    if "expect" in s and "goal_y_mm" in s["expect"]:
        lo, hi = s["expect"]["goal_y_mm"]
        s["expect"]["goal_y_mm"] = [-hi, -lo]
    return s
