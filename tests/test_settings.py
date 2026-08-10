import unittest

from jarvis_os.settings import PROJECT_ROOT, Settings


class SettingsTests(unittest.TestCase):
    def test_data_directory_is_separate_from_secrets(self):
        settings = Settings()
        self.assertNotEqual(settings.data_dir.name, ".env")
        self.assertTrue(PROJECT_ROOT.is_absolute())


if __name__ == "__main__":
    unittest.main()
