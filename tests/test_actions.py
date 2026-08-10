import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis_os.actions import WindowsActions
from jarvis_os.commands import Command


class WindowsActionTests(unittest.TestCase):
    def test_open_folder_uses_resolved_known_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "Downloads").mkdir()
            with patch("os.startfile", create=True) as startfile:
                result = WindowsActions(home).execute(Command("open_folder", {"path": "Downloads"}))
            self.assertTrue(result.success)
            startfile.assert_called_once_with(str(home / "Downloads"))

    def test_missing_folder_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            result = WindowsActions(Path(directory)).execute(Command("open_folder", {"path": "missing"}))
            self.assertFalse(result.success)

    def test_unknown_action_does_not_execute(self):
        result = WindowsActions().execute(Command("run_any_shell_command"))
        self.assertFalse(result.success)

    def test_delete_cannot_target_home(self):
        with tempfile.TemporaryDirectory() as directory:
            result = WindowsActions(Path(directory)).execute(Command("delete_path", {"path": "~"}))
            self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
