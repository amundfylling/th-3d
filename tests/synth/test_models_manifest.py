"""The trained-model manifest (data/models/manifest.json, docs/models.md) and its use by the NM26 rebuild runner.

Every model a rebuild step reads outside the models stage must be published (in the manifest), so `fetch` can supply it.
"""
import importlib.util
import json
import re
import unittest

from _load import REPO

M = json.loads((REPO / "data/models/manifest.json").read_text())
spec = importlib.util.spec_from_file_location("nm26_rebuild", REPO / "scripts/pipeline/nm26_rebuild.py")
RB = importlib.util.module_from_spec(spec); spec.loader.exec_module(RB)
ALL = RB.steps(RB.GAMES)


class Manifest(unittest.TestCase):
    def test_entries_complete(self):
        rel = M["release"]
        self.assertEqual(rel["download_base"], f"https://github.com/{rel['repo']}/releases/download/{rel['tag']}")
        ids = [m["id"] for m in M["models"]]; files = [m["file"] for m in M["models"]]
        self.assertEqual(len(ids), len(set(ids))); self.assertEqual(len(files), len(set(files)))
        for m in M["models"]:
            self.assertRegex(m["sha256"], r"^[0-9a-f]{64}$", m["id"])
            self.assertGreater(m["size_bytes"], 0, m["id"])
            self.assertTrue(m["local_path"].startswith("out/synth/") and m["local_path"].endswith(".pt"), m["id"])
            self.assertIn(m["status"], ("exact", "retrained"), m["id"])
            self.assertTrue((REPO / m["doc"]).exists(), m["id"])
            for s in m["loaded_by"]: self.assertTrue((REPO / s).exists(), f"{m['id']}: {s}")

    def test_loaders_name_published_paths(self):
        """Each script listed as a loader really names the model's local path (or its file stem)."""
        for m in M["models"]:
            stem = m["local_path"].rsplit("/", 1)[1][:-3]
            for s in m["loaded_by"]:
                self.assertTrue(re.search(re.escape(stem), (REPO / s).read_text()), f"{s} does not name {stem}")

    def test_rebuild_steps_get_models_from_fetch(self):
        fetched = next(s for s in ALL if s.id == "fetch-models").outputs
        self.assertEqual(sorted(fetched), sorted(m["local_path"] for m in M["models"]))
        for s in ALL:
            if s.stage == "models": continue
            for p in s.needs:
                if p.startswith("out/synth/") and p.endswith(".pt"): self.assertIn(p, fetched, f"{s.id}: {p} is not published")


if __name__ == "__main__":
    unittest.main()
