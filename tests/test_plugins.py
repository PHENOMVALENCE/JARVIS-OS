import tempfile
import unittest
from pathlib import Path

from jarvis_os.actions import WindowsActions
from jarvis_os.plugins import PluginManager
from jarvis_os.storage import Database


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(__file__).resolve().parent.parent
        self.manager = PluginManager(
            root / "plugins", Database(Path(self.temp.name) / "state.db"), WindowsActions(Path(self.temp.name)), Path(self.temp.name)
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_discovers_notes_plugin(self):
        self.assertIn("notes", self.manager.plugins)
        self.assertIn("productivity", self.manager.plugins)
        self.assertFalse(self.manager.plugins["notes"].error)

    def test_routes_and_executes_plugin_action(self):
        command = self.manager.route("Remember buy milk")
        self.assertEqual(command.action, "save_note")
        self.assertTrue(self.manager.execute(command).success)
        listed = self.manager.execute(self.manager.route("List notes"))
        self.assertEqual(listed.data["matches"], ["buy milk"])

    def test_disabled_plugin_no_longer_routes(self):
        self.manager.set_enabled("notes", False)
        self.assertIsNone(self.manager.route("Remember buy milk"))

    def test_routes_productivity_commands(self):
        self.assertEqual(self.manager.route("Daily brief").action, "daily_brief")
        send = self.manager.route("Send email to test@example.com subject Hello message Checking in")
        self.assertEqual(send.action, "send_email")
        self.assertEqual(send.risk.value, "high")


if __name__ == "__main__":
    unittest.main()
