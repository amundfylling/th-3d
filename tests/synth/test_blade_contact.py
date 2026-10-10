"""Blade contact point (scripts/nm26-figure-analysis.py): where a tracked skater receives the puck.

The touch analysis places each skater's blade contact point at the mold-frame point (12, 33) mm (+x = facing, +y = the
figure's left), rotated by the team's home heading plus the tracked rotation, at the pivot on the slot; a puck within
TOUCH_MM of it counts as a touch. The same mold point is the contact in scripts/defence-trace.py (blade_point).
"""
import json
import math
import re
import unittest

import numpy as np

from _load import REPO, load_defs

G = json.loads((REPO / "data/geometry.json").read_text())
NS = load_defs("scripts/nm26-figure-analysis.py", ["SLOT", "HOME", "BLADE", "TOUCH_MM", "ACC", "pivots", "blade"],
               {"np": np, "G": G})
SLOT, HOME, BLADE, blade, pivots = NS["SLOT"], NS["HOME"], NS["BLADE"], NS["blade"], NS["pivots"]
REACH = math.hypot(12.0, 33.0)


def rot(v, deg):
    a = math.radians(deg); return np.array([math.cos(a) * v[0] - math.sin(a) * v[1], math.sin(a) * v[0] + math.cos(a) * v[1]])


class Pivots(unittest.TestCase):
    def test_ends_and_middle(self):
        for pid, P in SLOT.items():
            np.testing.assert_allclose(pivots(pid, [0.0, 1.0]), P[[0, -1]], atol=1e-9)
            acc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
            mid = pivots(pid, [0.5])[0]
            # the midpoint is half the arc length from each end, along the polyline
            k = np.searchsorted(acc, acc[-1] / 2) - 1; f = (acc[-1] / 2 - acc[k]) / (acc[k + 1] - acc[k])
            np.testing.assert_allclose(mid, P[k] + f * (P[k + 1] - P[k]), atol=1e-9)

    def test_vectorised(self):
        self.assertEqual(pivots("W-LW", np.linspace(0, 1, 7)).shape, (7, 2))


class Blade(unittest.TestCase):
    def test_constants(self):
        np.testing.assert_array_equal(BLADE, [12.0, 33.0])
        self.assertEqual(HOME, {"W": 0.0, "E": 180.0})
        self.assertEqual(NS["TOUCH_MM"], 25.0)

    def test_white_end_at_home_heading(self):
        """W figures face +x at theta 0: the contact is 12 mm ahead and 33 mm to the left (+y) of the pivot."""
        for pid in ("W-LW", "W-C", "W-RD"):
            np.testing.assert_allclose(blade(pid, [0.3], [0.0])[0] - pivots(pid, [0.3])[0], [12.0, 33.0], atol=1e-9)

    def test_yellow_end_is_turned_half_a_turn(self):
        for pid in ("E-LW", "E-C", "E-RD"):
            np.testing.assert_allclose(blade(pid, [0.6], [0.0])[0] - pivots(pid, [0.6])[0], [-12.0, -33.0], atol=1e-9)

    def test_rotation_is_counter_clockwise_from_above(self):
        for pid in ("W-RW", "E-LD"):
            for th in (0.0, 45.0, 90.0, 211.0, 359.0):
                off = blade(pid, [0.5], [th])[0] - pivots(pid, [0.5])[0]
                np.testing.assert_allclose(off, rot(BLADE, HOME[pid[0]] + th), atol=1e-9)
                self.assertAlmostEqual(float(np.linalg.norm(off)), REACH, places=9)

    def test_vectorised_per_frame(self):
        u = np.array([0.1, 0.2, 0.9]); th = np.array([0.0, 90.0, 180.0])
        b = blade("W-C", u, th)
        self.assertEqual(b.shape, (3, 2))
        for k in range(3): np.testing.assert_allclose(b[k], blade("W-C", [u[k]], [th[k]])[0])

    def test_touch_radius(self):
        """The 25 mm touch rule: a puck 24 mm from the contact point touches, 26 mm does not."""
        b = blade("W-C", [0.5], [30.0])[0]
        for d, touched in ((24.0, True), (26.0, False)):
            puck = b + d * np.array([math.cos(1.0), math.sin(1.0)])
            self.assertEqual(float(np.linalg.norm(blade("W-C", [0.5], [30.0])[0] - puck)) < NS["TOUCH_MM"], touched)

    def test_same_mold_point_as_the_defence_trace(self):
        """scripts/defence-trace.py blade_point uses the same (12, 33) mm mid-blade point."""
        src = (REPO / "scripts/defence-trace.py").read_text()
        body = src[src.index("def blade_point"):].split("\ndef ", 1)[0]
        self.assertRegex(body, re.escape("np.array([12.0, 33.0])"))


if __name__ == "__main__":
    unittest.main()
