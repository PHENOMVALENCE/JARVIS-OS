import tempfile
import unittest
from pathlib import Path

from jarvis_os.storage import Database, PermissionRepository, SettingsRepository


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "state.db")

    def tearDown(self):
        self.temp.cleanup()

    def test_migrations_are_idempotent(self):
        Database(self.database.path)
        with self.database.connect() as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 5)

    def test_settings_use_typed_json_values(self):
        settings = SettingsRepository(self.database)
        settings.set("work_apps", ["notepad", "spotify"])
        self.assertEqual(settings.get("work_apps"), ["notepad", "spotify"])
        self.assertNotIn("OPENAI_API_KEY", settings.export_safe())

    def test_permissions_validate_modes(self):
        permissions = PermissionRepository(self.database)
        permissions.set("type_text", "ask")
        self.assertEqual(permissions.get("type_text", "deny"), "ask")
        with self.assertRaises(ValueError):
            permissions.set("type_text", "sometimes")


if __name__ == "__main__":
    unittest.main()
