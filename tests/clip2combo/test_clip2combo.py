"""Checks of the goal clip -> combo pipeline (scripts/clip2combo.py). numpy only; reads the committed NM26 tracks."""
import json, math, sys, unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import clip2combo as C  # noqa: E402
import table_common as T  # noqa: E402

LABELS = json.loads((C.D / "goal-labels.json").read_text())["labels"]


class Clip2Combo(unittest.TestCase):
    def test_every_marked_goal_gives_a_well_formed_combo(self):
        for r in LABELS:
            c = C.clip_to_combo(r["game"], r["goal_video_s"], name=r["id"])
            self.assertEqual(c["schema"], "th-combo/1")
            self.assertEqual(sorted(c["figures"]), sorted(T.SKATERS + T.GOALIES))
            for pid, f in c["figures"].items():
                self.assertTrue(0.5 <= f["arc_mm"] <= T.SLOT_LEN[pid] - 0.5, (r["id"], pid, f))
                self.assertTrue(-180 <= f["theta_deg"] <= 180)
            self.assertGreaterEqual(len(c["arrows"]), 1, r["id"])
            for a in c["arrows"]:
                self.assertGreaterEqual(len(a["points_mm"]), 2)
                self.assertTrue(all(math.isfinite(v) for p in a["points_mm"] for v in p))
            self.assertEqual(c["clip2combo"]["status"], "PROPOSED")

    def test_east_end_is_turned_into_the_attacker_frame(self):
        # E-X slots are the W-X slots turned 180 degrees with the arc running the other way
        for r in ("LW", "RW", "C", "LD", "RD"):
            for arc in (30.0, 120.0, 200.0):
                a = min(arc, T.SLOT_LEN["E-" + r] - 1)
                piv = -T.slot_point("E-" + r, a / T.SLOT_LEN["E-" + r])
                d, u = T.nearest_on_slot(T.SLOT["W-" + r], piv)
                self.assertLess(d, 3.0, (r, d))  # the turned slot lies on the W slot
                bw_e = C.blade_world("E-" + r, a, 25.0)
                bw_w = C.blade_world("W-" + r, u * T.SLOT_LEN["W-" + r], 25.0)
                self.assertLess(math.dist(bw_w, [-bw_e[0], -bw_e[1]]), 3.5, (r, bw_w, bw_e))

    def test_golden_touch_sequences(self):
        want = {"g1-goal1": ["LD", "LW", "RW", "C"], "g3-goal1": ["RW", "C"], "g1-goal6": ["LW", "C"], "g4-goal1": ["C"]}
        for r in LABELS:
            if r["id"] in want:
                c = C.clip_to_combo(r["game"], r["goal_video_s"])
                self.assertEqual(c["clip2combo"]["roles"], want[r["id"]], r["id"])

    def test_scoring_end_from_the_clip_alone(self):
        ok = sum(C.clip_to_combo(r["game"], r["goal_video_s"])["clip2combo"]["scoring_end"] == r["scoring_end"] for r in LABELS)
        self.assertGreaterEqual(ok, 23)


if __name__ == "__main__":
    unittest.main()
