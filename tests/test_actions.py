import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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
            opened = Path(startfile.call_args.args[0]).resolve()
            self.assertEqual(opened, (home / "Downloads").resolve())

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

    def test_web_research_returns_grounding_passages(self):
        service = Mock()
        item = Mock()
        item.passage.return_value = "SOURCE: Example\nURL: https://example.com"
        service.search.return_value = [item]
        result = WindowsActions(web_research=service).execute(Command("web_research", {"query": "topic"}))
        self.assertTrue(result.success)
        self.assertIn("https://example.com", result.data["matches"][0])


if __name__ == "__main__":
    unittest.main()
