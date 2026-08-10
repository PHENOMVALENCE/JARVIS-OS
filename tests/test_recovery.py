import tempfile
import unittest
import zipfile
from pathlib import Path

from jarvis_os.recovery import create_backup, restore_backup


class RecoveryTests(unittest.TestCase):
    def test_backup_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"; data.mkdir(); (data / "notes.json").write_text("hello")
            archive = create_backup(data, root / "backups")
            restored = root / "restored"
            restore_backup(archive, restored)
            self.assertEqual((restored / "notes.json").read_text(), "hello")

    def test_restore_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../outside.txt", "bad")
            with self.assertRaises(ValueError):
                restore_backup(archive, Path(directory) / "restore")


if __name__ == "__main__":
    unittest.main()
