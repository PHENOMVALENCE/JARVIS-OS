import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from jarvis_os.proactive import ProactiveScheduler
from jarvis_os.storage import Database, SettingsRepository


class ProactiveTests(unittest.TestCase):
    def test_quiet_hours_store_but_suppress_normal_notification(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "state.db")
            settings = SettingsRepository(database)
            settings.set("quiet_hours_start", "22:00"); settings.set("quiet_hours_end", "07:00")
            notifier = Mock()
            scheduler = ProactiveScheduler(database, settings, Mock(), notifier)
            now = datetime(2026, 8, 10, 23, 0).astimezone()
            self.assertTrue(scheduler.notify("Test", "Message", "normal", "one", now))
            notifier.send.assert_not_called()
            self.assertEqual(len(scheduler.history()), 1)

    def test_duplicate_event_is_suppressed(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "state.db")
            scheduler = ProactiveScheduler(database, SettingsRepository(database), Mock(), Mock())
            self.assertTrue(scheduler.notify("Test", "Message", "high", "same"))
            self.assertFalse(scheduler.notify("Test", "Message", "high", "same"))


if __name__ == "__main__":
    unittest.main()
