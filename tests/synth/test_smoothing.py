"""Track cleaning (scripts/synth/smooth-tracks.py): reject impossible readings, fill short gaps, light smoothing.

Synthetic tracks are written to a temporary game directory and cleaned by the script's own smooth_game. The last test
re-cleans the committed raw tracks and compares with the committed figure-tracks-smooth.json: the cleaned tracks are
reproducible from the raw ones.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from _load import REPO, load_defs

SCRIPT = "scripts/synth/smooth-tracks.py"
G = json.loads((REPO / "data/geometry.json").read_text())
NM26 = REPO / "data/games/nm26-semifinal"


def cleaner(data_dir):
    ns = load_defs(SCRIPT, ["SLOT_LEN", "WIN", "DS_MM", "DTH", "GAP", "SD", "circ_diff", "smooth_game"],
                   {"np": np, "json": json, "G": G, "__doc__": "Clean the raw figure tracks.\n\nTest."})
    ns["D"] = Path(data_dir)
    return ns


NS = cleaner(NM26)
L = {p: NS["SLOT_LEN"][p] for p in ("W-LW", "W-G")}


class Track:
    """Raw track for one skater (W-LW) and one goalie (W-G) in a temporary game directory."""

    def __init__(self, frames, dense, u, th, slot_dist=None, gu=None, gth=None):
        n = len(frames)
        self.tmp = tempfile.mkdtemp(); (Path(self.tmp) / "gt").mkdir()
        sd = slot_dist if slot_dist is not None else [3.0] * n
        gu = gu if gu is not None else [0.5] * n; gth = gth if gth is not None else [10.0] * n
        rows = [[frames[i], dense[i], u[i], th[i], sd[i], gu[i], gth[i]] for i in range(n)]
        cols = ["frame", "dense", "W-LW_u", "W-LW_theta_deg", "W-LW_slot_dist_mm", "W-G_u", "W-G_theta_deg"]
        (Path(self.tmp) / "gt/figure-tracks.json").write_text(json.dumps({"columns": cols, "rows": rows}))
        self.ns = cleaner(self.tmp)

    def clean(self):
        self.stats = self.ns["smooth_game"]("gt")
        out = json.loads((Path(self.tmp) / "gt/figure-tracks-smooth.json").read_text()); shutil.rmtree(self.tmp)
        ci = {c: i for i, c in enumerate(out["columns"])}; R = out["rows"]
        return {c: [r[ci[c]] for r in R] for c in out["columns"]}


def sparse(n=50, step=3):
    """n readings at 10 fps (every 3rd frame at 30 fps; the tracker's default --fps), not dense."""
    return [i * step for i in range(n)], [0] * n


class Helpers(unittest.TestCase):
    def test_circ_diff(self):
        cd = NS["circ_diff"]
        self.assertEqual(cd(10, 350), 20); self.assertEqual(cd(350, 10), -20); self.assertEqual(cd(90, 90), 0)
        self.assertEqual(cd(180, 0), -180)  # half a turn maps to -180
        np.testing.assert_allclose(cd(np.array([0, 359, 721]), 1), [-1, -2, 0])

    def test_limits_are_the_documented_ones(self):
        self.assertEqual((NS["WIN"], NS["DS_MM"], NS["DTH"], NS["GAP"], NS["SD"]), (0.3, 25.0, 45.0, 1.0, 15.0))

    def test_slot_lengths_from_geometry(self):
        for f in G["fixture_paths"]:
            P = np.array(f["centreline"]["points_mm"])
            self.assertAlmostEqual(NS["SLOT_LEN"][f["player_id"]], float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum()))


class Cleaning(unittest.TestCase):
    def test_clean_track_is_kept(self):
        fr, de = sparse(); u = list(np.linspace(0.2, 0.4, len(fr)).round(4)); th = [30.0] * len(fr)
        c = Track(fr, de, u, th).clean()
        self.assertEqual(c["W-LW_src"], [0] * len(fr))
        np.testing.assert_allclose(c["W-LW_u"], u, atol=1e-4); np.testing.assert_allclose(c["W-LW_theta_deg"], th)

    def test_single_jump_is_rejected_and_interpolated(self):
        """One reading 60 mm off its neighbours is a localiser lock-on: replaced by the line through its neighbours."""
        fr, de = sparse(); u = [0.3] * len(fr); u[20] = 0.3 + 60.0 / L["W-LW"]
        c = Track(fr, de, u, [0.0] * len(fr)).clean()
        self.assertEqual(c["W-LW_src"][20], 1); self.assertEqual(sum(c["W-LW_src"]), 1)
        self.assertAlmostEqual(c["W-LW_u"][20], 0.3, places=4)

    def test_small_step_is_motion_not_noise(self):
        """A 20 mm step (under the 25 mm limit) is kept."""
        fr, de = sparse(); u = [0.3] * len(fr); u[20] = 0.3 + 20.0 / L["W-LW"]
        c = Track(fr, de, u, [0.0] * len(fr)).clean()
        self.assertEqual(c["W-LW_src"][20], 0)

    def test_rotation_jump_is_rejected(self):
        fr, de = sparse(); th = [100.0] * len(fr); th[10] = 160.0
        c = Track(fr, de, [0.5] * len(fr), th).clean()
        self.assertEqual(c["W-LW_src"][10], 1); self.assertAlmostEqual(c["W-LW_theta_deg"][10], 100.0)

    def test_pivot_off_the_slot_is_rejected(self):
        """slot_dist over 15 mm rejects the reading even when its value looks plausible."""
        fr, de = sparse(); sd = [3.0] * len(fr); sd[30] = 15.5; u = list(np.linspace(0.1, 0.3, len(fr)).round(4))
        c = Track(fr, de, u, [0.0] * len(fr), slot_dist=sd).clean()
        self.assertEqual(c["W-LW_src"][30], 1); self.assertAlmostEqual(c["W-LW_u"][30], u[30], delta=1.5e-4)
        sd[30] = 15.0  # exactly at the limit is kept
        self.assertEqual(Track(fr, de, u, [0.0] * len(fr), slot_dist=sd).clean()["W-LW_src"][30], 0)

    def test_goalies_have_no_slot_distance(self):
        """Goalie columns carry no slot_dist_mm: only the outlier test applies."""
        fr, de = sparse(); gu = [0.5] * len(fr); gu[25] = 0.5 + 40.0 / L["W-G"]
        c = Track(fr, de, [0.5] * len(fr), [0.0] * len(fr), gu=gu).clean()
        self.assertEqual(c["W-G_src"][25], 1); self.assertEqual(c["W-G_src"].count(1), 1)

    def test_rotation_fills_along_the_shorter_arc(self):
        """Filling between 350 and 10 degrees passes through 0, not 180."""
        fr, de = sparse(); th = [350.0] * 25 + [10.0] * 25; sd = [3.0] * 50; sd[25] = 30.0
        c = Track(fr, de, [0.5] * 50, th, slot_dist=sd).clean()
        self.assertEqual(c["W-LW_src"][25], 1)
        # the filled reading lies halfway between frame 24 (350) and frame 26 (10)
        self.assertAlmostEqual(c["W-LW_theta_deg"][25], 0.0, places=6)

    def test_gap_up_to_one_second_is_filled_longer_is_unknown(self):
        fr, de = sparse(80); sd = [3.0] * 80
        for i in range(10, 18): sd[i] = 40.0   # 8 readings: valid neighbours 0.9 s apart -> filled
        for i in range(40, 51): sd[i] = 40.0   # 11 readings: 1.2 s apart -> unknown
        c = Track(fr, de, [0.5] * 80, [0.0] * 80, slot_dist=sd).clean()
        self.assertEqual(c["W-LW_src"][10:18], [1] * 8)
        self.assertEqual(c["W-LW_src"][40:51], [2] * 11)
        self.assertTrue(all(v is None for v in c["W-LW_u"][40:51] + c["W-LW_theta_deg"][40:51]))

    def test_dense_windows_get_a_three_frame_average(self):
        """On consecutive 30 fps frames u is the mean of the frame and its two neighbours; window edges are kept."""
        fr = list(range(0, 60, 6)) + list(range(60, 90)) + list(range(96, 160, 6))
        de = [0] * 10 + [1] * 30 + [0] * (len(fr) - 40)
        rng = np.random.default_rng(0)
        u = [0.5] * len(fr); u[10:40] = list((0.5 + rng.uniform(-5, 5, 30) / L["W-LW"]).round(4))
        c = Track(fr, de, u, [0.0] * len(fr)).clean()
        self.assertEqual(set(c["W-LW_src"]), {0})
        for i in range(11, 39):
            self.assertAlmostEqual(c["W-LW_u"][i], round((u[i - 1] + u[i] + u[i + 1]) / 3, 4), delta=1.5e-4, msg=i)
        self.assertAlmostEqual(c["W-LW_u"][10], u[10], places=4)  # first dense frame: neighbour is 6 frames back
        self.assertAlmostEqual(c["W-LW_u"][39], u[39], places=4)  # last dense frame: next is not consecutive
        self.assertEqual(c["W-LW_u"][:10], u[:10])  # sparse frames untouched

    def test_too_few_neighbours_skips_the_outlier_test(self):
        """With fewer than 3 valid readings within +-0.3 s a reading is never called an outlier (1 fps here)."""
        fr = [i * 30 for i in range(20)]; u = [0.3] * 20; u[10] = 0.6
        c = Track(fr, [0] * 20, u, [0.0] * 20).clean()
        self.assertEqual(c["W-LW_src"], [0] * 20)

    def test_at_5_fps_the_outlier_test_cannot_fire(self):
        """KNOWN LIMITATION (current behaviour, see docs/pipeline.md): at 5 fps only two readings lie within +-0.3 s,
        fewer than the 3 the outlier test needs, so a 60 mm jump is kept. The committed full-game tracks are mostly
        5 fps outside the goal windows; there only the 15 mm slot-distance rule rejects readings."""
        fr, de = sparse(step=6); u = [0.3] * len(fr); u[20] = 0.3 + 60.0 / L["W-LW"]
        c = Track(fr, de, u, [0.0] * len(fr)).clean()
        self.assertEqual(c["W-LW_src"][20], 0)

    def test_stats_are_shares(self):
        fr, de = sparse(); sd = [3.0] * 50; sd[5] = 99.0
        t = Track(fr, de, [0.5] * 50, [0.0] * 50, slot_dist=sd); t.clean()
        self.assertEqual(t.stats["W-LW"], {"rejected": 0.02, "interpolated": 0.02, "unknown": 0.0})


class Reproducible(unittest.TestCase):
    def test_committed_clean_tracks_rebuild_exactly(self):
        """Every game's committed figure-tracks-smooth.json is what smooth_game makes from its figure-tracks.json."""
        games = sorted(p.name for p in NM26.glob("g*") if (p / "figure-tracks.json").exists() and (p / "figure-tracks-smooth.json").exists())
        self.assertTrue(games)
        tmp = Path(tempfile.mkdtemp())
        try:
            for g in games:
                (tmp / g).mkdir(); shutil.copy(NM26 / g / "figure-tracks.json", tmp / g / "figure-tracks.json")
                ns = cleaner(tmp); ns["__doc__"] = load_doc()
                ns["smooth_game"](g)
                want = json.loads((NM26 / g / "figure-tracks-smooth.json").read_text())
                got = json.loads((tmp / g / "figure-tracks-smooth.json").read_text())
                self.assertEqual(got["columns"], want["columns"], g)
                self.assertEqual(got["rows"], want["rows"], g)
                self.assertEqual(got["stats"], want["stats"], g)
        finally:
            shutil.rmtree(tmp)


def load_doc():
    import ast
    return ast.get_docstring(ast.parse((REPO / SCRIPT).read_text()), clean=False)


if __name__ == "__main__":
    unittest.main()
