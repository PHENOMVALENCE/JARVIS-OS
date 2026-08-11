import tempfile
import unittest
from pathlib import Path

from jarvis_os.screen import ScreenService, VISION_SYSTEM_PROMPT


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

    def test_build_prompt_includes_conversation_context(self):
        service = ScreenService(Path("."))
        prompt = service._build_prompt("What error is showing?", "user: my app crashed\nassistant: checking now")
        self.assertIn(VISION_SYSTEM_PROMPT, prompt)
        self.assertIn("my app crashed", prompt)
        self.assertIn("What error is showing?", prompt)


if __name__ == "__main__":
    unittest.main()
