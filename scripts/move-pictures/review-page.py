"""Build the move-picture review page (docs/move-pictures.md, "Review page").

Writes out/move-pictures/review/index.html plus one JPEG per move picture (and the puck.no original where there is
one) for publishing as an artifact. Verdicts and comments are kept by the page in its artifact database
(collection "reviews", one document per move id), not in this repository.

Usage: python3 scripts/move-pictures/review-page.py              all moves (out/move-pictures/review/)
       python3 scripts/move-pictures/review-page.py --designed   only the moves without a puck.no picture
                                                                 (out/move-pictures/review-designed/; 2026-11-11)
--earlier <json> adds the user's comments from the first review page ({move id: {comment, date}}) to the cards.
"""
import sys
import json
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
DESIGNED = "--designed" in sys.argv
OUT = REPO / ("out/move-pictures/review-designed" if DESIGNED else "out/move-pictures/review")
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
    earlier = {}
    if "--earlier" in sys.argv:
        earlier = json.loads(Path(sys.argv[sys.argv.index("--earlier") + 1]).read_text())
    moves = []
    for m in idx:
        s = specs.get(m["id"])
        if s is None or not (PIC / f"{s['id']}.png").exists():
            continue
        if DESIGNED and s.get("puck_no_picture"):
            continue
        jpeg(PIC / f"{s['id']}.png", OUT / "img" / f"{s['id']}.jpg", 1000)
        orig = None
        if s.get("puck_no_picture"):
            orig = f"orig/{s['id']}.jpg"
            jpeg(REPO / s["puck_no_picture"], OUT / orig, 900)
        moves.append({"id": m["id"], "file": s["id"], "name": s.get("name", m["name"]), "player": m["player"],
                      "level": m["level"], "text": m["description"], "note": s.get("note", ""),
                      "source": "puckno" if orig else "designed", "img": f"img/{s['id']}.jpg", "orig": orig,
                      "earlier": earlier.get(m["id"])})
    order = {"Centre": 0, "Right wing": 1}
    moves.sort(key=lambda q: (order.get(q["player"], 9), q["level"], q["name"].lower()))
    tpl = (Path(__file__).parent / "review-page.html").read_text()
    page = tpl.replace("/*MOVES*/[]", json.dumps(moves, ensure_ascii=False).replace("</", "<\\/"))
    if DESIGNED:
        cfg = {"designedOnly": True, "heading": "New move pictures",
               "lede": f"The {len(moves)} NTHF moves that have no picture on puck.no, drawn on our Play Off 21 rink from the NTHF text. "
                       "Players that are not part of the move stand and turn as on the puck.no pictures. Mark each one <b>Looks good</b> "
                       "or <b>Needs change</b> and say what to change in the comment, for example which figure, arrow or boards."}
        page = page.replace("/*PAGE*/{}", json.dumps(cfg, ensure_ascii=False)).replace("/*TITLE*/Move Picture Review", "New Move Pictures")
    else:
        page = page.replace("/*TITLE*/", "")
    (OUT / "index.html").write_text(page)
    print("wrote", (OUT / "index.html").relative_to(REPO), len(moves), "moves,",
          sum(q["source"] == "designed" for q in moves), "designed")


if __name__ == "__main__":
    main()
