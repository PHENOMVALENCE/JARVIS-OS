import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jarvis_os import diagnostics_log
from jarvis_os.earcons import DONE, ERROR, WAKE, Earcons, tone
from jarvis_os.router import CommandRouter


class LogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        diagnostics_log._configured = False
        diagnostics_log.get().handlers.clear()
        diagnostics_log.configure(self.dir)

    def tearDown(self):
        diagnostics_log.get().handlers.clear()
        diagnostics_log._configured = False
        self.temp.cleanup()

    def test_creates_a_log_file(self):
        self.assertTrue(diagnostics_log.log_path(self.dir).exists())

    def test_records_a_swallowed_failure(self):
        diagnostics_log.failure("microphone", OSError("device in use"), "attempt 1")
        text = diagnostics_log.log_path(self.dir).read_text(encoding="utf-8")
        self.assertIn("microphone failed", text)
        self.assertIn("device in use", text)

    def test_surfaces_only_warnings_and_errors(self):
        diagnostics_log.get("noise").info("routine startup chatter")
        diagnostics_log.failure("speech.edge", OSError("no internet"))
        problems = diagnostics_log.recent_problems(self.dir)
        self.assertEqual(len(problems), 1)
        self.assertIn("no internet", problems[0])

    def test_reports_nothing_when_the_log_is_missing(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(diagnostics_log.recent(Path(empty)), [])

    def test_configuring_twice_does_not_duplicate_handlers(self):
        before = len(diagnostics_log.get().handlers)
        diagnostics_log.configure(self.dir)
        self.assertEqual(len(diagnostics_log.get().handlers), before)


class EarconTests(unittest.TestCase):
    def test_renders_a_playable_wav(self):
        payload = tone(WAKE)
        self.assertTrue(payload.startswith(b"RIFF"))
        self.assertIn(b"WAVE", payload[:16])
        self.assertGreater(len(payload), 2000)

    def test_each_cue_is_distinct(self):
        self.assertNotEqual(tone(WAKE), tone(DONE))
        self.assertNotEqual(tone(DONE), tone(ERROR))

    def test_disabled_earcons_play_nothing(self):
        earcons = Earcons(enabled=False)
        earcons._play = Mock()
        earcons.play("wake")
        earcons._play.assert_not_called()

    def test_playback_is_cached_between_calls(self):
        earcons = Earcons()
        first = earcons._payload("wake", WAKE)
        second = earcons._payload("wake", WAKE)
        self.assertIs(first, second)

    def test_a_broken_audio_device_does_not_raise(self):
        earcons = Earcons()
        with patch.object(Earcons, "_play", side_effect=OSError("no audio device")):
            earcons.play("wake")  # runs on a thread; must not raise here


class ProblemRoutingTests(unittest.TestCase):
    def test_asking_what_went_wrong_reaches_the_log(self):
        router = CommandRouter()
        for text in ("What went wrong", "Show me the log", "Any errors",
                     "Jarvis diagnostics"):
            self.assertEqual(router.route(text).action, "show_problems", text)

    def test_ordinary_requests_are_unaffected(self):
        router = CommandRouter()
        self.assertEqual(router.route("What is the weather").action, "weather")
        self.assertEqual(router.route("Open Notepad").action, "open_app")


if __name__ == "__main__":
    unittest.main()
