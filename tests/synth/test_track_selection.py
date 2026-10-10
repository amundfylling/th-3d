"""Track selection (scripts/nm26_tracks.py): which puck and figure tracks the NM26 analysis reads, and the 'slow' flag
that replaces the old track's 'disk' kind.
"""
import importlib
import json
import os
import sys
import unittest

from _load import REPO

sys.path.insert(0, str(REPO / "scripts"))


def fresh(env):
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        import nm26_tracks
        return importlib.reload(nm26_tracks)
    finally:
        for k, v in old.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v


def track(rows, kind="det"):
    return {"columns": ["frame", "video_t_s", "x_mm", "y_mm", "u_stab_px", "v_stab_px", "kind", "score"],
            "rows": [[f, f / 30, x, y, 0, 0, kind if isinstance(kind, str) else kind[i], 1.0] for i, (f, x, y) in enumerate(rows)]}


class Selection(unittest.TestCase):
    def test_defaults_are_the_new_tracks(self):
        m = fresh({})
        os.environ.pop("NM26_PUCK_TRACK", None); os.environ.pop("NM26_FIGURE_TRACKS", None)
        m = importlib.reload(m)
        self.assertEqual(m.PUCK_TRACK, "puck-track-synth.json")
        self.assertEqual(m.FIGURE_TRACKS, "figure-tracks-v3.json")
        for g in ("g1", "g7"):
            self.assertTrue(m.puck_path(g).exists()); self.assertTrue(m.figure_path(g).exists())

    def test_environment_override(self):
        m = fresh({"NM26_PUCK_TRACK": "puck-track.json", "NM26_FIGURE_TRACKS": "figure-tracks-smooth.json"})
        self.assertEqual(m.PUCK_TRACK, "puck-track.json"); self.assertEqual(m.FIGURE_TRACKS, "figure-tracks-smooth.json")
        importlib.reload(m)

    def test_v3_has_the_cleaned_columns(self):
        for g in ("g1", "g2"):
            a = json.loads((REPO / f"data/games/nm26-semifinal/{g}/figure-tracks-smooth.json").read_text())["columns"]
            b = json.loads((REPO / f"data/games/nm26-semifinal/{g}/figure-tracks-v3.json").read_text())["columns"]
            self.assertEqual(a, b)


class Slow(unittest.TestCase):
    def setUp(self):
        self.m = fresh({})

    def test_old_track_slow_is_disk(self):
        t = track([(1, 0, 0), (2, 50, 0), (3, 100, 0)], kind=["disk", "smudge", "disk_fill"])
        self.assertEqual(self.m.slow_flags(t), [True, False, False])

    def test_new_track_by_speed(self):
        # 3 mm per frame = 90 mm/s (slow); then 40 mm per frame = 1200 mm/s (fast)
        t = track([(1, 0, 0), (2, 3, 0), (3, 6, 0), (4, 46, 0), (5, 86, 0)])
        self.assertEqual(self.m.slow_flags(t), [True, True, False, False, False])

    def test_isolated_detection_is_not_slow(self):
        t = track([(1, 0, 0), (10, 0, 0), (11, 1, 0)])
        self.assertEqual(self.m.slow_flags(t), [False, True, True])

    def test_gap_scales_the_speed(self):
        # 9 mm over a 3-frame gap = 90 mm/s: slow; 9 mm over 1 frame = 270 mm/s: slow; 12 mm over 1 frame = 360 mm/s: not
        t = track([(1, 0, 0), (4, 9, 0), (5, 18, 0), (6, 30, 0)])
        self.assertEqual(self.m.slow_flags(t), [True, True, False, False])


if __name__ == "__main__":
    unittest.main()
