"""Modifier grammar over the 121 NTHF combination names (experiment, PROPOSED).

Parses every catalogue name into (prefix modifiers, base, suffix modifiers), looks the base up in the catalogue and tests
how well the modifier predicts the variant's NTHF text from the base's text:
  python3 scripts/modifiers/grammar.py            -> prints the table, writes validation/modifiers/grammar-coverage.json
"""
import difflib
import json
import re
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAT = json.loads((REPO / "data/combinations/nthf-catalogue.json").read_text())["combinations"]


def norm(s):
    s = s.lower().replace("ø", "o").replace("æ", "ae").replace("å", "a")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def aliases(name):
    return [norm(p) for p in re.split(r"\s*/\s*", name)]


INDEX = {}
for c in CAT:
    for a in aliases(c["name"]):
        INDEX.setdefault(a, c)

# word-level mirror (left <-> right) for the text transform
SWAP = {"left": "right", "right": "left"}


def mirror_text(t):
    return re.sub(r"\b(left|right|Left|Right)\b", lambda m: SWAP[m.group(1).lower()].capitalize() if m.group(1)[0].isupper() else SWAP[m.group(1)], t)


def swap_groove(t):
    return re.sub(r"\b(toe|heel)\b", lambda m: "heel" if m.group(1) == "toe" else "toe", t)


def parse(name):
    """-> (mods, base_slug). Modifiers are peeled from the first alias of the name."""
    s = norm(name.split("/")[0] if "/" in name and not name.strip().lower().startswith(("lillstovel",)) else name)
    mods, base = [], s
    changed = True
    while changed:
        changed = False
        for pre in ("fakie-", "invers-", "senter-", "halv-"):
            if base.startswith(pre):
                mods.append(pre[:-1]); base = base[len(pre):]; changed = True
        for suf in ("-finte", "finte", "-kort", "-lang"):
            if base.endswith(suf):
                mods.append(suf.strip("-")); base = base[: -len(suf)].strip("-"); changed = True
        m = re.match(r"^(lang|kort)-(.+)$", base)
        if m:
            mods.append(m.group(1)); base = m.group(2); changed = True
    return mods, base


def similarity(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def run():
    rows = []
    for c in CAT:
        mods, base = parse(c["name"])
        # lookup: the base with its own modifiers re-added in stages (e.g. "tryykari" -> tryykari-kort)
        cand = INDEX.get(base) or INDEX.get(base + "-kort") or INDEX.get(base + "-lang") or INDEX.get(base + "o")
        if base.endswith("o") and not cand:
            cand = INDEX.get(base[:-1])
        row = {"name": c["name"], "player": c["player"], "mods": mods, "base": base,
               "base_found": cand["name"] if cand and cand["name"] != c["name"] else None, "text": c["description"]}
        rows.append(row)
    return rows


if __name__ == "__main__":
    rows = run()
    n_mod = sum(1 for r in rows if r["mods"])
    n_found = sum(1 for r in rows if r["mods"] and r["base_found"])
    print(f"{len(rows)} moves; {n_mod} carry a modifier; {n_found} of those have their base in the catalogue")
    for r in rows:
        if r["mods"]:
            print(f"{r['name']:34s} {','.join(r['mods']):18s} base={r['base']:22s} found={r['base_found']}")


def evaluate(rows):
    """Text-level test of each modifier: predict the variant's NTHF text from the base's text and measure similarity."""
    by_name = {r["name"]: r for r in rows}
    out = []
    for r in rows:
        if not r["mods"] or not r["base_found"]:
            continue
        b = by_name[r["base_found"]]["text"]
        v = r["text"]
        preds = {"identity": b, "mirror LR": mirror_text(b), "swap toe/heel": swap_groove(b), "mirror+groove": swap_groove(mirror_text(b))}
        best = max(preds, key=lambda k: similarity(preds[k], v))
        out.append({"name": r["name"], "mods": r["mods"], "base": r["base_found"], "best_pred": best,
                    "sim": {k: round(similarity(p, v), 3) for k, p in preds.items()}, "variant_text": v, "base_text": b})
    return out


def toks(t):
    return re.findall(r"[a-zåäöæø0-9]+", t.lower())


def flip_corner(t):
    t = re.sub(r"\b(right|left) corner", lambda m: ("left" if m.group(1) == "right" else "right") + " corner", t)
    return re.sub(r"\bnear corner", "far corner", t) if "near corner" in t else t


def finte_text(base_name, base_text):
    corner = re.findall(r"(right|left) corner", base_text)
    other = "left" if (corner[-1] if corner else "right") == "right" else "right"
    return f"Center performs a {base_name}, but places the puck in the {other} corner. Only works against a reacting goalie"


RULES = {  # modifier -> deterministic text transform on the base text
    "fakie": lambda bn, bt: mirror_text(bt),
    "lang": lambda bn, bt: flip_corner(bt),
    "finte": lambda bn, bt: finte_text(bn, bt),
}


def score_rules(rows):
    by_name = {r["name"]: r for r in rows}
    res = []
    for r in rows:
        if not r["base_found"] or len(r["mods"]) != 1 or r["mods"][0] not in RULES:
            continue
        bn = by_name[r["base_found"]]
        pred = RULES[r["mods"][0]](bn["name"].split(" /")[0], bn["text"])
        res.append({"name": r["name"], "mod": r["mods"][0], "exact": toks(pred) == toks(r["text"]),
                    "sim": round(difflib.SequenceMatcher(None, toks(pred), toks(r["text"])).ratio(), 3)})
    return res
