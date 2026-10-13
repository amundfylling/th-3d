"""Build the move-picture review page (docs/move-pictures.md, "Review page").

Writes out/move-pictures/review/index.html plus one JPEG per move picture (and the puck.no original where there is
one) for publishing as an artifact. Verdicts and comments are kept by the page in its artifact database
(collection "reviews", one document per move id), not in this repository.

Usage: python3 scripts/move-pictures/review-page.py
"""
import json
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "out/move-pictures/review"
SPECS = REPO / "data/move-pictures"
PIC = REPO / "validation/move-pictures"


def jpeg(src, dst, height):
    im = Image.open(src).convert("RGB")
    if im.height > height:
        im = im.resize((round(im.width * height / im.height), height), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, quality=84, optimize=True)


def main():
    idx = json.loads((REPO / "data/encyclopedia/index.json").read_text())["moves"]
    specs = {}
    for p in SPECS.glob("*.json"):
        if p.stem == "formation":
            continue
        s = json.loads(p.read_text())
        specs[s.get("index_id", s["id"])] = s
    moves = []
    for m in idx:
        s = specs.get(m["id"])
        if s is None or not (PIC / f"{s['id']}.png").exists():
            continue
        jpeg(PIC / f"{s['id']}.png", OUT / "img" / f"{s['id']}.jpg", 1000)
        orig = None
        if s.get("puck_no_picture"):
            orig = f"orig/{s['id']}.jpg"
            jpeg(REPO / s["puck_no_picture"], OUT / orig, 900)
        moves.append({"id": m["id"], "file": s["id"], "name": s.get("name", m["name"]), "player": m["player"],
                      "level": m["level"], "text": m["description"], "note": s.get("note", ""),
                      "source": "puckno" if orig else "designed", "img": f"img/{s['id']}.jpg", "orig": orig})
    order = {"Centre": 0, "Right wing": 1}
    moves.sort(key=lambda q: (order.get(q["player"], 9), q["level"], q["name"].lower()))
    tpl = (Path(__file__).parent / "review-page.html").read_text()
    page = tpl.replace("/*MOVES*/[]", json.dumps(moves, ensure_ascii=False).replace("</", "<\\/"))
    (OUT / "index.html").write_text(page)
    print("wrote", (OUT / "index.html").relative_to(REPO), len(moves), "moves,",
          sum(q["source"] == "designed" for q in moves), "designed")


if __name__ == "__main__":
    main()
