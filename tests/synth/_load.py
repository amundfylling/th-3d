"""Load named top-level functions and constants from a pipeline script without running it.

The synth and NM26 scripts are command-line programs: importing them would parse sys.argv, load torch models, open
the video or write outputs. These tests check the helpers exactly as they are written in the scripts, so this loader
parses the script, takes only the requested top-level definitions (functions, classes, simple assignments) and executes
them in a namespace seeded with the caller's globals (numpy, a stub camera, a slot table ...).
"""
import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load_defs(script, names, env=None):
    """Return a namespace dict holding `names` from `script` (path relative to the repo), executed over `env`."""
    src = (REPO / script).read_text()
    tree = ast.parse(src)
    want, found = set(names), set()
    body = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in want:
            body.append(node); found.add(node.name)
        elif isinstance(node, ast.Assign):
            targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
            targets |= {e.id for t in node.targets if isinstance(t, ast.Tuple) for e in t.elts if isinstance(e, ast.Name)}
            if targets & want:
                body.append(node); found |= targets & want
    missing = want - found
    if missing:
        raise LookupError(f"{script}: no top-level definition of {sorted(missing)}")
    ns = dict(env or {})
    exec(compile(ast.Module(body=body, type_ignores=[]), str(REPO / script), "exec"), ns)
    return ns
