"""The contact check of saved traces (scripts/shotlib/verify.py): every saved trace passes it from its file alone, it
agrees with what each generator recorded, and it catches what it is there to catch. Needs numpy and shapely."""
import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from shotlib import verify as V  # noqa: E402
from shotlib import world as W  # noqa: E402


def load(name):
    return json.loads((REPO / f"data/traces/{name}.trace.json").read_text())


def with_puck(trace, xy_of_t):
    """A copy of the trace whose puck nodes are moved to xy_of_t(t) (None keeps a node)."""
    t = copy.deepcopy(trace)
    for n in t["puck"]["nodes"]:
        xy = xy_of_t(n["t"])
        if xy is not None:
            n["x_mm"], n["y_mm"] = float(xy[0]), float(xy[1])
    return t


REPORTS = {p.name: V.verify_file(p) for p in V.saved_traces()}


class SavedTraces(unittest.TestCase):
    def test_every_saved_trace_passes_from_its_file_alone(self):
        self.assertGreaterEqual(len(REPORTS), 9)
        for name, r in REPORTS.items():
            with self.subTest(trace=name):
                self.assertEqual(r["unexpected_penetrations"], [])
                self.assertEqual(r["problems"], [])
                self.assertTrue(r["passed"])
                # the rule's terms: 0.25 ms or finer, 0.1 mm or tighter, all twelve figures, the whole window
                self.assertLessEqual(r["sampling_s"], 0.00025)
                self.assertLessEqual(r["penetration_tolerance_mm"], 0.1)
                self.assertEqual(r["figures_checked"], 12)
                t0, t1 = r["window_s"]
                self.assertEqual(r["samples"], int(round((t1 - t0) / r["sampling_s"])) + 1)
                self.assertLess(r["max_puck_step_mm"], 2.0)

    def test_every_phase_of_every_trace_is_checked(self):
        for p in V.saved_traces():
            trace = json.loads(p.read_text())
            r = REPORTS[p.name]
            checked = {x["phase"] for x in r["min_clearance_by_obstacle_and_phase"]}
            for ph in trace["puck"]["phases"]:
                if ph["t"][1] is None or ph["t"][1] > ph["t"][0]:
                    self.assertIn(ph["id"], checked, f"{p.name}: phase {ph['id']}")
            for pid in W.ALL_FIGURES:  # no figure is skipped, listed in the trace or not
                self.assertTrue(any(x["obstacle"] == pid for x in r["min_clearance_by_obstacle_and_phase"]), f"{p.name}: {pid}")

    def test_only_the_recorded_user_exception_is_used(self):
        used = {name: sorted(r["approved_exceptions"]) for name, r in REPORTS.items() if r["approved_exceptions"]}
        self.assertEqual(used, {"shovel-17.trace.json": ["shot.W-C_right_skate_brush"]})
        for r in REPORTS.values():
            self.assertEqual(r["unused_exceptions"], [])

    def test_agrees_with_the_clearances_each_generator_recorded(self):
        """Each generator measured on its own objects; this check measures on the saved file. Near a contact the two
        agree to 0.05 mm, elsewhere to 0.5 mm (the Edwall script measures the boards on a coarser outline)."""
        compared = 0
        for name, r in REPORTS.items():
            saved = json.loads((REPO / r["recorded_checks"]).read_text())
            mine = {(x["obstacle"], x["phase"]): x["min_clearance_mm"] for x in r["min_clearance_by_obstacle_and_phase"]}
            for row in saved.get("min_clearance_by_obstacle_and_phase", []):
                ob = row["obstacle"]
                # older checks files do not name the goal's end
                names = [ob] + [f"goal_{e}_{ob[5:]}" for e in "EW" if ob.startswith("goal_") and ob[5:6] not in "EW"]
                got = [mine[(n, row["phase"])] for n in names if (n, row["phase"]) in mine]
                if not got:
                    continue  # a phase one sample long at the generator's own time step
                d = min(abs(g - row["min_clearance_mm"]) for g in got)
                self.assertLessEqual(d, 0.05 if row["min_clearance_mm"] < 5 else 0.5, f"{name} {ob} {row['phase']}")
                compared += 1
        self.assertGreater(compared, 120)


class Catches(unittest.TestCase):
    def setUp(self):
        self.trace = load("hjerpefinte")
        self.t0, self.t1 = self.trace["time_base"]["window_s"]

    def test_the_untouched_trace_passes(self):
        self.assertTrue(V.contact_check(self.trace)["passed"])

    def test_a_puck_moved_into_a_listed_figure(self):
        f = next(f for f in V.figures_of(self.trace) if f.pid == "W-C")
        r = V.contact_check(with_puck(self.trace, lambda t: f.pose(t)[0]))
        self.assertFalse(r["passed"])
        self.assertIn("W-C", {o["obstacle"] for o in r["unexpected_penetrations"]})

    def test_a_puck_moved_into_a_figure_the_trace_does_not_list(self):
        self.assertNotIn("E-LD", [p for p, f in self.trace["figures"].items() if isinstance(f, dict)])
        piv = W.assembly_figure("E-LD").piv
        r = V.contact_check(with_puck(self.trace, lambda t: piv))
        self.assertEqual({o["obstacle"] for o in r["unexpected_penetrations"]}, {"E-LD"})

    def test_an_overlap_a_few_samples_long_between_the_generators_nodes(self):
        """One node pushed 1 mm into the blade it rests against: 0.5 ms long, still found."""
        f = next(f for f in V.figures_of(self.trace) if f.pid == "W-C")
        n0 = self.trace["puck"]["nodes"][40]
        p0 = np.array([n0["x_mm"], n0["y_mm"]])
        loc, nrm = W.local_contact(f, n0["t"], p0)
        inward = -np.array([np.cos(np.radians(nrm)), np.sin(np.radians(nrm))])
        r = V.contact_check(with_puck(self.trace, lambda t: p0 + 1.0 * inward if t == n0["t"] else None))
        self.assertEqual([o["obstacle"] for o in r["unexpected_penetrations"]], ["W-C"])
        o = r["unexpected_penetrations"][0]
        self.assertLess(o["t1"] - o["t0"], 0.002)
        self.assertLess(o["worst_mm"], -0.5)

    def test_a_puck_outside_the_boards_however_far(self):
        for x in (W.BOARD.bounds[2] + 1.0, W.BOARD.bounds[2] + 500.0):
            r = V.contact_check(with_puck(self.trace, lambda t: (x, 0.0)))
            self.assertIn("boards", {o["obstacle"] for o in r["unexpected_penetrations"]}, x)

    def test_a_puck_through_a_goal_post_and_through_the_cage_from_outside(self):
        g = W.GOALS["E"]
        r = V.contact_check(with_puck(self.trace, lambda t: g.posts[0]))
        self.assertIn("goal_E_post_pos_y", {o["obstacle"] for o in r["unexpected_penetrations"]})
        side = (g.x + g.depth / 2, g.y + g.half)  # on the side net, never having crossed the goal line
        r = V.contact_check(with_puck(self.trace, lambda t: side))
        self.assertIn("goal_E_cage", {o["obstacle"] for o in r["unexpected_penetrations"]})

    def test_a_puck_that_enters_the_goal_and_goes_on_through_the_net(self):
        """In the net the puck may rest against the cage; leaving it through the back or a side is an overlap."""
        g = W.GOALS["E"]
        r = V.contact_check(self.trace)
        self.assertEqual(r["goal_entered"], "E")
        nodes = self.trace["puck"]["nodes"]
        k = next(i for i, n in enumerate(nodes) if g.sign * (n["x_mm"] - g.x) >= 0)
        t_in, t_end = nodes[k]["t"], nodes[-1]["t"]
        back = lambda t: None if t <= t_in else (g.x + g.sign * (g.depth + 30.0 * (t - t_in) / (t_end - t_in)), g.y)
        side = lambda t: None if t <= t_in else (g.x + g.sign * g.depth / 2, g.y + (g.half + 30.0) * (t - t_in) / (t_end - t_in))
        for name, path in (("back", back), ("side", side)):
            r = V.contact_check(with_puck(self.trace, path))
            self.assertEqual(r["goal_entered"], "E", name)
            self.assertIn("goal_E_cage", {o["obstacle"] for o in r["unexpected_penetrations"]}, name)
            self.assertFalse(r["passed"], name)

    def test_a_jump_between_samples(self):
        tm = (self.t0 + self.t1) / 2
        nodes = self.trace["puck"]["nodes"]
        r = V.contact_check(with_puck(self.trace, lambda t: (nodes[0]["x_mm"], nodes[0]["y_mm"] + (40.0 if t > tm else 0.0))))
        self.assertFalse(r["passed"])
        self.assertTrue(any("jumps" in p for p in r["problems"]))

    def test_malformed_traces_are_refused(self):
        bad = copy.deepcopy(self.trace); bad["schema"] = "shot-trace/2"
        self.assertRaises(ValueError, V.contact_check, bad)
        bad = copy.deepcopy(self.trace); bad["puck"]["nodes"][5]["t"] = bad["puck"]["nodes"][4]["t"]
        self.assertRaises(ValueError, V.contact_check, bad)
        bad = copy.deepcopy(self.trace); bad["puck"]["radius_mm"] = 5.0  # a smaller puck would hide overlaps
        self.assertRaises(ValueError, V.contact_check, bad)
        bad = copy.deepcopy(self.trace); bad["figures"]["W-C"]["arc_keyframes"] = []
        self.assertRaises(ValueError, V.contact_check, bad)
        self.assertRaises(ValueError, V.contact_check, self.trace, (), 0.001)  # coarser than 0.25 ms


class Exceptions(unittest.TestCase):
    """The Shovel's skate brush (2.05 mm, user-approved up to 2.7 mm): an exception covers exactly what was approved."""

    def setUp(self):
        self.trace = load("shovel-17")
        self.exc = json.loads((REPO / "shots/22-shovel/inputs.json").read_text())["approved_overlap_exceptions"]

    def check(self, **change):
        return V.contact_check(self.trace, [{**self.exc[0], **change}])

    def test_without_the_exception_the_brush_is_an_overlap(self):
        r = V.contact_check(self.trace)
        self.assertEqual([(o["obstacle"], o["phase"]) for o in r["unexpected_penetrations"]], [("W-C", "shot_free")])
        self.assertAlmostEqual(r["unexpected_penetrations"][0]["worst_mm"], -2.05, delta=0.01)

    def test_with_it_the_trace_passes_and_the_report_says_so(self):
        r = self.check()
        self.assertTrue(r["passed"])
        self.assertEqual(list(r["approved_exceptions"]), ["shot.W-C_right_skate_brush"])

    def test_it_does_not_cover_a_deeper_overlap_another_phase_or_another_figure(self):
        self.assertFalse(self.check(max_overlap_mm=1.0)["passed"])
        self.assertFalse(self.check(phase="carried_by_W-C")["passed"])
        self.assertFalse(self.check(obstacle="W-RW")["passed"])

    def test_it_covers_only_samples_that_both_phase_readings_put_in_its_phase(self):
        """A phase boundary can fall between two puck nodes: the node before a sample says one phase, the recorded
        interval (puck.phases, what the renderer reads) another. There the exception does not apply."""
        r = V.contact_check(self.trace, self.exc)
        self.assertTrue(r["passed"])
        self.assertGreater(r["phase_boundary_samples"], 0)  # the Shovel has such samples, away from the brush
        moved = copy.deepcopy(self.trace)
        q = next(q for q in moved["puck"]["phases"] if q["id"] == "shot_free")
        b = r["approved_exceptions"]["shot.W-C_right_skate_brush"]
        q["t"][0] = (b["t0"] + b["t1"]) / 2  # the interval now says the brush starts in the phase before
        i = moved["puck"]["phases"].index(q)
        moved["puck"]["phases"][i - 1]["t"][1] = q["t"][0]
        r = V.contact_check(moved, self.exc)
        self.assertFalse(r["passed"])
        self.assertEqual(r["approved_exceptions"], {})

    def test_it_needs_the_users_approval(self):
        self.assertFalse(self.check(approved_by="AI review")["passed"])


class Evaluation(unittest.TestCase):
    def test_vector_poses_equal_the_engines_figure_poses(self):
        """verify.figure_poses against world.Figure.pose (the Python mirror of src/model/trace.ts) on moving figures."""
        for name in ("invers-kryssar-velodrom", "shovel-17", "edwall-g2-goal3"):
            trace = load(name)
            t0, t1 = trace["time_base"]["window_s"]
            t = np.r_[np.linspace(t0 - 0.1, t1 + 0.1, 997), [k["t"] for f in trace["figures"].values() if isinstance(f, dict) for k in f["arc_keyframes"][:50]]]
            for f in V.figures_of(trace):
                piv, head = V.figure_poses(f, t)
                for k in range(0, len(t), 7):
                    p, h = f.pose(float(t[k]))
                    self.assertLess(float(np.abs(piv[k] - p).max()), 1e-9, f"{name} {f.pid} t {t[k]}")
                    self.assertLess(abs(float(head[k]) - h), 1e-9, f"{name} {f.pid} t {t[k]}")

    def test_vector_clearance_equals_the_engines_clearance(self):
        trace = load("invers-kryssar-velodrom")
        t0, t1 = trace["time_base"]["window_s"]
        t = np.arange(t0, t1, 0.0137)
        nodes = trace["puck"]["nodes"]
        p = np.c_[np.interp(t, [n["t"] for n in nodes], [n["x_mm"] for n in nodes]), np.interp(t, [n["t"] for n in nodes], [n["y_mm"] for n in nodes])]
        for f in V.figures_of(trace):
            c = V.figure_clearance(f, t, p, exact=True)
            for k in range(len(t)):
                self.assertAlmostEqual(float(c[k]), W.clearance(f, float(t[k]), p[k]), delta=1e-9)

    def test_the_pruned_clearance_keeps_every_minimum_and_every_overlap_exact(self):
        """figure_clearance measures the exact distance only where it can matter (hull distance first). Against the
        exact distance at every sample: the same minimum at the same sample per group, the same values wherever the
        puck is within its radius of the footprint (so the same overlaps), and never a value below the exact one."""
        rng = np.random.default_rng(3)
        for name in ("shovel-17", "invers-kryssar-velodrom", "edwall-g2-goal2"):
            trace = load(name)
            t0, t1 = trace["time_base"]["window_s"]
            t = np.arange(t0, t1 + 1e-9, 0.001)
            nodes = trace["puck"]["nodes"]
            p = np.c_[np.interp(t, [n["t"] for n in nodes], [n["x_mm"] for n in nodes]), np.interp(t, [n["t"] for n in nodes], [n["y_mm"] for n in nodes])]
            p[::9] += rng.normal(0, 6.0, (len(p[::9]), 2))  # some samples pushed into and around the figures
            group = (np.arange(len(t)) * 5) // len(t)
            for f in V.figures_of(trace):
                full = V.figure_clearance(f, t, p, exact=True)
                fast = V.figure_clearance(f, t, p, group)
                self.assertTrue(np.all(fast <= full + 1e-9), f"{name} {f.pid}")
                near = full < 1.0
                self.assertTrue(np.array_equal(fast[near], full[near]), f"{name} {f.pid}")
                for g in range(5):
                    sel = np.flatnonzero(group == g)
                    self.assertEqual(int(sel[np.argmin(fast[sel])]), int(sel[np.argmin(full[sel])]), f"{name} {f.pid} group {g}")
                    self.assertEqual(float(fast[sel].min()), float(full[sel].min()), f"{name} {f.pid} group {g}")

    def test_the_check_is_not_part_of_the_engine_identity(self):
        from shotlib import identity
        self.assertNotIn("verify.py", [p.name for p in identity.engine_files()])


if __name__ == "__main__":
    unittest.main()
