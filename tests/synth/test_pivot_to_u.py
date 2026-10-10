"""pivot_to_u (scripts/synth/train-skater-pose.py): pivot pixel in a crop -> slot position u and distance from the slot.

The skater model predicts the pivot (feet) pixel in a 200 x 200 crop; scripts/synth/track-figures.py turns it into the
figure's slot position with this helper (the inverse of the reference camera's ice-plane homography, then the nearest
point on the slot centreline of data/geometry.json).
"""
import json
import unittest

import numpy as np

from _load import REPO, load_defs

NS = load_defs("scripts/synth/train-skater-pose.py",
               ["CAM", "_K", "_R", "_t", "_Hinv", "_G", "SLOT", "px_to_net", "net_to_px", "ice_from_ref_px", "pivot_to_u"],
               {"json": json, "np": np, "REPO": REPO})
SLOT, pivot_to_u = NS["SLOT"], NS["pivot_to_u"]
K, R, t = NS["_K"], NS["_R"], NS["_t"]
SKATERS = ["W-LW", "E-LW", "W-RW", "E-RW", "W-C", "E-C", "W-LD", "E-LD", "W-RD", "E-RD"]


def on_slot(pid, u):
    """Point at arc-length fraction u along the slot centreline (mm)."""
    P = SLOT[pid]; acc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]; s = u * acc[-1]
    return np.array([np.interp(s, acc, P[:, 0]), np.interp(s, acc, P[:, 1])])


def to_px(xy):
    """Ice point (z = 0, mm) -> reference video px through the reference camera."""
    q = K @ (R @ np.array([xy[0], xy[1], 0.0]) + t); return q[:2] / q[2]


def crop(px, at=(100.0, 100.0)):
    """Split a reference pixel into (crop_xy, crop_origin) with the point at `at` in the crop."""
    return (float(at[0]), float(at[1])), (float(px[0] - at[0]), float(px[1] - at[1]))


class PivotToU(unittest.TestCase):
    def test_round_trip_through_the_camera(self):
        """A point on the slot, projected to the image and back, returns its own u at ~0 mm from the slot."""
        for pid in SKATERS:
            for u in (0.0, 0.07, 0.25, 0.5, 0.73, 0.98, 1.0):
                got_u, d = pivot_to_u(pid, *crop(to_px(on_slot(pid, u))))
                self.assertAlmostEqual(got_u, u, delta=1e-6, msg=f"{pid} u={u}")
                self.assertLess(d, 1e-6, f"{pid} u={u}")

    def test_crop_split_does_not_matter(self):
        """Only crop_xy + crop_origin counts: where the pivot sits inside the crop is irrelevant."""
        px = to_px(on_slot("W-C", 0.4))
        ref = pivot_to_u("W-C", *crop(px))
        for at in ((0, 0), (37.5, 160.25), (199, 199)):
            got = pivot_to_u("W-C", *crop(px, at))
            self.assertAlmostEqual(got[0], ref[0], places=9); self.assertAlmostEqual(got[1], ref[1], places=6)

    def test_offset_from_the_slot_is_measured_in_mm(self):
        """A pivot 10 mm to the side of the slot (mid segment) keeps its u and reports 10 mm."""
        for pid in ("W-C", "E-LD", "W-RW"):
            P = SLOT[pid]; k = len(P) // 2; a, b = P[k], P[k + 1]
            m = (a + b) / 2; n = np.array([-(b - a)[1], (b - a)[0]]) / np.linalg.norm(b - a)
            u0, _ = pivot_to_u(pid, *crop(to_px(m)))
            for side in (+1, -1):
                u, d = pivot_to_u(pid, *crop(to_px(m + side * 10.0 * n)))
                self.assertAlmostEqual(d, 10.0, delta=0.05, msg=pid)
                self.assertAlmostEqual(u, u0, delta=0.002, msg=pid)

    def test_beyond_the_ends_clamps(self):
        """Past either end of the slot, u is 0 or 1 and the distance is to the end point."""
        for pid in ("W-C", "E-C", "W-LD"):
            P = SLOT[pid]
            for end, out, u_exp in ((P[0], P[0] - P[1], 0.0), (P[-1], P[-1] - P[-2], 1.0)):
                q = end + 20.0 * out / np.linalg.norm(out)
                u, d = pivot_to_u(pid, *crop(to_px(q)))
                self.assertEqual(u, u_exp, pid); self.assertAlmostEqual(d, 20.0, delta=0.05, msg=pid)

    def test_u_increases_along_the_slot(self):
        us = [pivot_to_u("E-RW", *crop(to_px(on_slot("E-RW", u))))[0] for u in np.linspace(0, 1, 41)]
        self.assertTrue(all(b > a for a, b in zip(us, us[1:])))

    def test_network_coordinates_round_trip(self):
        """px_to_net / net_to_px: the to_tensor window [20:190, 15:185] scaled to 0..1."""
        px_to_net, net_to_px = NS["px_to_net"], NS["net_to_px"]
        self.assertEqual(px_to_net((15, 20)), (0.0, 0.0)); self.assertEqual(px_to_net((185, 190)), (1.0, 1.0))
        for xy in ((15, 20), (100, 100), (3.5, 199.25)):
            back = net_to_px(px_to_net(xy)); self.assertAlmostEqual(back[0], xy[0]); self.assertAlmostEqual(back[1], xy[1])

    def test_camera_maps_the_rink_into_the_frame(self):
        """Sanity: every slot point projects inside the 1920 x 1080 broadcast frame (camera-ref.json is used as is)."""
        for pid in SKATERS:
            for u in (0.0, 0.5, 1.0):
                x, y = to_px(on_slot(pid, u))
                self.assertTrue(0 <= x < 1920 and 0 <= y < 1080, f"{pid} u={u}: {x:.0f}, {y:.0f}")


if __name__ == "__main__":
    unittest.main()
