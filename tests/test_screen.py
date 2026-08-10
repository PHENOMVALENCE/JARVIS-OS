import tempfile
import unittest
from pathlib import Path

from jarvis_os.screen import ScreenService


class FakeSettings:
    def __init__(self, privacy):
        self.privacy = privacy

    def get(self, key, default=None):
        return self.privacy if key == "privacy_mode" else default


class ScreenTests(unittest.TestCase):
    def test_privacy_mode_blocks_capture_before_accessing_screen(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ScreenService(Path(directory), FakeSettings(True)).capture()
        self.assertFalse(result.success)
        self.assertIn("privacy mode", result.message.lower())


if __name__ == "__main__":
    unittest.main()
