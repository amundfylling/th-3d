"""The NM26 rebuild runner (scripts/pipeline/nm26_rebuild.py) covers every committed NM26 data file.

When a new script writes a file under data/games/nm26-semifinal, add a Step for it in nm26_rebuild.py (or, for a hand-made
or user-labelled file, a SOURCES entry saying where it comes from). Then `npm run rebuild:nm26` rebuilds it too.
"""
import importlib.util
import subprocess
import unittest

from _load import REPO

spec = importlib.util.spec_from_file_location("nm26_rebuild", REPO / "scripts/pipeline/nm26_rebuild.py")
RB = importlib.util.module_from_spec(spec); spec.loader.exec_module(RB)
ALL = RB.steps(RB.GAMES)


class Steps(unittest.TestCase):
    def test_ids_unique_and_stages_known(self):
        ids = [s.id for s in ALL]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(s.stage in RB.STAGES for s in ALL))
        self.assertTrue(set(RB.DEFAULT) <= set(RB.STAGES)); self.assertNotIn("models", RB.DEFAULT)

    def test_every_script_exists(self):
        for s in ALL:
            for a in s.cmd:
                if a.endswith(".py"): self.assertTrue((REPO / a).exists(), f"{s.id}: {a}")

    def test_inputs_come_before_use(self):
        """A step's input is committed, a SOURCE, or written by an earlier step (or by the models stage)."""
        made = set()
        tracked = set(subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=REPO).stdout.split())
        for s in ALL:
            for p in s.needs:
                self.assertTrue(p in made or p in tracked or p in RB.SOURCES or p.startswith("out/synth/"), f"{s.id}: {p}")
            made |= set(s.outputs)

    def test_every_committed_nm26_data_file_is_rebuilt_or_a_source(self):
        files = subprocess.run(["git", "ls-files", RB.DATA], capture_output=True, text=True, cwd=REPO).stdout.split()
        outputs = {p for s in ALL for p in s.outputs}
        orphans = [f for f in files if f not in outputs and f not in RB.SOURCES]
        self.assertEqual(orphans, [], "no rebuild step writes these; add a Step or a SOURCES entry in scripts/pipeline/nm26_rebuild.py")


if __name__ == "__main__":
    unittest.main()
