"""scripts/table_common.py: the one definition of figure ids, home headings, slots and the NM26 reference camera.

The helpers are pinned against the formulas the scripts each carried before (restated here, so a change to the shared
module that would move a render, a track or a label by one bit fails), and the scripts are scanned so the copies do not
come back."""
import json
import re
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import table_common as tc  # noqa: E402

G = json.loads((REPO / "data/geometry.json").read_text())
CAM = json.loads((REPO / "data/games/nm26-semifinal/camera-ref.json").read_text())
RNG = np.random.default_rng(11)


def old_arc_point(P, u):
    """The helper as eleven scripts defined it (scripts/synth/render-skater-crops.py and others, before 2026-11-11)."""
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); s = u * seg.sum(); acc = np.r_[0, np.cumsum(seg)]
    k = min(np.searchsorted(acc, s, side="right") - 1, len(seg) - 1); f = (s - acc[k]) / seg[k]
    return P[k] + f * (P[k + 1] - P[k]), s


def old_on_slot(P, q):
    """scripts/synth/skater-labels.py on_slot and train-skater-pose.py pivot_to_u, before 2026-11-11."""
    seg = np.diff(P, axis=0); L = np.linalg.norm(seg, axis=1); acc = np.r_[0, np.cumsum(L)]; best = (1e9, 0.0)
    for k in range(len(seg)):
        f = np.clip(np.dot(q - P[k], seg[k]) / (L[k] ** 2), 0, 1); d = np.linalg.norm(P[k] + f * seg[k] - q)
        if d < best[0]: best = (d, (acc[k] + f * L[k]) / acc[-1])
    return best


class Ids(unittest.TestCase):
    def test_skater_order_is_the_models_one_hot_order(self):
        # the skater-pose models (v2b, v3) were trained with this order; a different order silently misreads every crop
        self.assertEqual(tc.SKATERS, ["W-LW", "E-LW", "W-RW", "E-RW", "W-C", "E-C", "W-LD", "E-LD", "W-RD", "E-RD"])
        self.assertEqual(tc.GOALIES, ["W-G", "E-G"])

    def test_every_figure_of_the_geometry_has_a_slot_and_nothing_else_does(self):
        self.assertEqual(sorted(tc.SKATERS + tc.GOALIES), sorted(f["player_id"] for f in G["fixture_paths"]))
        self.assertEqual(sorted(tc.SLOT), sorted(tc.SKATERS + tc.GOALIES))
        self.assertEqual(sorted(p["id"] for p in G["players"]), sorted(tc.SLOT))

    def test_home_headings(self):
        self.assertEqual(tc.HOME, {"W": 0.0, "E": 180.0})
        # theta = 0 faces the opponent's goal: W attacks +x, E attacks -x (docs/pose.md)
        for end, goal in (("W", "E"), ("E", "W")):
            own, other = tc.SLOT[f"{end}-G"].mean(0), tc.SLOT[f"{goal}-G"].mean(0)
            h = np.radians(tc.HOME[end])
            self.assertGreater(float(np.dot([np.cos(h), np.sin(h)], other - own)), 0)


class Slots(unittest.TestCase):
    def test_slots_are_the_geometry_centrelines(self):
        for f in G["fixture_paths"]:
            P = np.array(f["centreline"]["points_mm"], float)
            self.assertTrue(np.array_equal(tc.SLOT[f["player_id"]], P))
            self.assertTrue(np.array_equal(tc.ACC[f["player_id"]], np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]))
            # both spellings the scripts used for the length give the same float
            a = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
            b = float(np.linalg.norm(np.diff(np.array(f["centreline"]["points_mm"]), axis=0), axis=1).sum())
            self.assertEqual(tc.SLOT_LEN[f["player_id"]], a)
            self.assertEqual(a, b)
            # ... and with or without `float` the points are the same float64 array (scripts/nm26-calibrate.py)
            self.assertEqual(np.array(f["centreline"]["points_mm"]).dtype, np.float64)

    def test_arc_point_is_bit_for_bit_the_old_helper(self):
        for pid, P in tc.SLOT.items():
            for u in np.r_[0.0, 1.0, 0.5, RNG.uniform(0, 1, 200), -0.05, 1.05]:
                p0, s0 = old_arc_point(P, u)
                p1, s1 = tc.arc_point_s(P, u)
                self.assertTrue(np.array_equal(p0, p1), f"{pid} u {u}")
                self.assertEqual(s0, s1)
                self.assertTrue(np.array_equal(tc.arc_point(P, u), p0))

    def test_ends_and_arc_length(self):
        for pid, P in tc.SLOT.items():
            self.assertLess(float(np.abs(tc.arc_point(P, 0.0) - P[0]).max()), 1e-9)
            self.assertLess(float(np.abs(tc.arc_point(P, 1.0) - P[-1]).max()), 1e-9)
            p, s = tc.arc_point_s(P, 0.25)
            self.assertAlmostEqual(s, 0.25 * tc.SLOT_LEN[pid], places=9)
            # equal steps of u are equal steps along the slot
            pts = np.array([tc.arc_point(P, u) for u in np.linspace(0, 1, 400)])
            step = np.linalg.norm(np.diff(pts, axis=0), axis=1)
            self.assertLess(float(step.max()), tc.SLOT_LEN[pid] / 399 + 1e-9)

    def test_slot_point_forms_agree(self):
        """slot_point / slot_points (np.interp along the arc; used by the analysis and the replays) and arc_point (used
        by the renders and trackers) are the same point inside the slot; outside [0, 1] slot_point holds the end."""
        for pid, P in tc.SLOT.items():
            u = RNG.uniform(0, 1, 100)
            many = tc.slot_points(pid, u)
            for k, x in enumerate(u):
                self.assertTrue(np.array_equal(tc.slot_point(pid, x), many[k]))
                self.assertLess(float(np.abs(tc.arc_point(P, x) - many[k]).max()), 1e-9, f"{pid} u {x}")
            self.assertTrue(np.array_equal(tc.slot_point(pid, 1.3), tc.slot_point(pid, 1.0)))
            self.assertTrue(np.array_equal(tc.slot_points(pid, -0.2)[0], tc.slot_point(pid, 0.0)))

    def test_nearest_on_slot_is_bit_for_bit_the_old_helper_and_inverts_arc_point(self):
        for pid, P in tc.SLOT.items():
            for u in RNG.uniform(0, 1, 25):
                p = tc.arc_point(P, u)
                d, u1 = tc.nearest_on_slot(P, p)
                self.assertLess(float(d), 1e-9)
                self.assertAlmostEqual(float(u1), float(u), places=9)
                q = p + RNG.normal(0, 20, 2)
                self.assertEqual(tuple(map(float, tc.nearest_on_slot(P, q))), tuple(map(float, old_on_slot(P, q))))
            d, u1 = tc.nearest_on_slot(P, P[-1] + 3 * (P[-1] - P[-2]))  # past the end: clamped
            self.assertEqual(float(u1), 1.0)
            self.assertGreater(float(d), 0)


class Camera(unittest.TestCase):
    def test_ref_camera_is_the_file_and_returns_new_arrays(self):
        K, R, t = tc.ref_camera()
        self.assertTrue(np.array_equal(K, np.array(CAM["K"])) and np.array_equal(R, np.array(CAM["R"])) and np.array_equal(t, np.array(CAM["t_mm"])))
        K[0, 0] = 0.0  # a script scaling its own copy must not change anyone else's
        self.assertEqual(tc.ref_camera()[0][0, 0], CAM["K"][0][0])
        self.assertLess(float(np.abs(R @ R.T - np.eye(3)).max()), 1e-6)

    def test_project_equals_the_scalar_form_the_scripts_use(self):
        K, R, t = tc.ref_camera()
        X = np.c_[RNG.uniform(-420, 420, 50), RNG.uniform(-230, 230, 50), RNG.uniform(0, 60, 50)]
        got = tc.ref_project(X)
        for k, x in enumerate(X):
            q = K @ (R @ x + t)
            self.assertLess(float(np.abs(got[k] - q[:2] / q[2]).max()), 1e-9)
        self.assertLess(float(np.abs(tc.ref_project(X[:, :2]) - tc.ref_project(np.c_[X[:, :2], np.zeros(50)])).max()), 1e-12)

    def test_the_table_is_in_the_picture(self):
        W, H = CAM["image_size"]
        px = np.vstack([tc.ref_project(tc.slot_points(p, np.linspace(0, 1, 20))) for p in tc.SLOT])
        self.assertTrue(np.all((px[:, 0] > 0) & (px[:, 0] < W) & (px[:, 1] > 0) & (px[:, 1] < H)))

    def test_plane_round_trip_on_the_ice_and_on_the_puck_top(self):
        xy = np.c_[RNG.uniform(-420, 420, 50), RNG.uniform(-230, 230, 50)]
        for z in (0.0, 12.0):
            px = tc.ref_project(np.c_[xy, np.full(50, z)])
            self.assertLess(float(np.abs(tc.ref_to_plane(px, z) - xy).max()), 1e-6)
        # the plane homography at z = 0 is the one train-skater-pose.py inverts (K [r1 r2 t])
        K, R, t = tc.ref_camera()
        self.assertTrue(np.array_equal(tc.ref_plane_homography(0.0), K @ np.c_[R[:, 0], R[:, 1], t]))


class NoCopies(unittest.TestCase):
    """The tracking-side scripts take these from table_common. The move engine and the two oldest trace scripts keep
    theirs (engine identity; historical record), and the own-video pipeline has its own skater order."""
    KEEP = {"scripts/table_common.py", "scripts/shot22-trace.py", "scripts/spjass-trace.py", "scripts/own_video_common.py"}
    PATTERNS = {
        "a slot-position helper of its own": re.compile(r"^def (arc_point|on_slot)\(", re.M),
        "the home headings spelled out": re.compile(r'\{"W": 0\.0, "E": 180\.0\}'),
        "the model skater order spelled out": re.compile(r'\["W-LW", "E-LW", "W-RW", "E-RW", "W-C", "E-C", "W-LD", "E-LD", "W-RD", "E-RD"\]'),
        "slots read from the geometry file": re.compile(r'np\.array\(f\["centreline"\]\["points_mm"\](, float)?\) for f in \w+\["fixture_paths"\]'),
        "the reference camera read from its file": re.compile(r'json\.loads\(\([^)]*camera-ref\.json"\)\.read_text\(\)\)'),
    }

    def scripts(self):
        return sorted(p for p in [*(REPO / "scripts").glob("*.py"), *(REPO / "scripts/synth").glob("*.py"), *(REPO / "scripts/pipeline").glob("*.py")]
                      if str(p.relative_to(REPO)) not in self.KEEP)

    def test_no_script_carries_its_own_copy(self):
        found = [f"{p.relative_to(REPO)}: {what}" for p in self.scripts() for what, pat in self.PATTERNS.items() if pat.search(p.read_text())]
        self.assertEqual(found, [])

    def test_every_script_compiles(self):
        for p in self.scripts() + [REPO / k for k in self.KEEP]:
            compile(p.read_text(), str(p), "exec")

    def test_scripts_import_the_module_before_they_use_it(self):
        users = [p for p in self.scripts() if "table_common." in p.read_text()]
        self.assertGreaterEqual(len(users), 30)
        for p in users:
            lines = p.read_text().split("\n")
            imp = next((k for k, l in enumerate(lines) if re.match(r"import table_common\b", l)), None)
            self.assertIsNotNone(imp, f"{p.name}: uses table_common without importing it at the top level")
            first = next(k for k, l in enumerate(lines) if "table_common." in l)
            self.assertLess(imp, first, p.name)
            if p.parent.name != "scripts":  # a script in scripts/ has its own folder on sys.path; the others add it
                path = next((k for k, l in enumerate(lines) if "sys.path.insert(0" in l and ('REPO / "scripts")' in l or "parents[1]" in l)), None)
                self.assertTrue(path is not None and path < imp, f"{p.name}: scripts/ must be on sys.path before the import")


if __name__ == "__main__":
    unittest.main()
