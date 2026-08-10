import tempfile
import unittest
from pathlib import Path

from jarvis_os.knowledge import KnowledgeIndex
from jarvis_os.storage import Database, SettingsRepository


class FakeEmbedder:
    def embed(self, texts):
        return [[float("budget" in text.lower()), float("launch" in text.lower()), 0.5] for text in texts]


class KnowledgeTests(unittest.TestCase):
    def test_indexes_and_cites_local_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = root / "plan.txt"
            document.write_text("The launch budget is twelve thousand dollars.", encoding="utf-8")
            database = Database(root / "state.db")
            settings = SettingsRepository(database)
            settings.set("indexed_folders", [str(root)])
            index = KnowledgeIndex(database, settings, FakeEmbedder())
            self.assertTrue(index.index_configured().success)
            result = index.search("launch budget")
            self.assertTrue(result.success)
            self.assertIn("plan.txt", result.data["matches"][0])


if __name__ == "__main__":
    unittest.main()
