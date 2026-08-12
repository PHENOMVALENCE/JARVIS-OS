import struct
import time
import unittest
from unittest.mock import Mock

from jarvis_os.live_transcribe import FRAME, LiveTranscriber


def frame(amplitude: int) -> bytes:
    """A frame of constant amplitude, loud enough or quiet enough for the VAD."""
    return struct.pack("<h", amplitude) * FRAME


LOUD = frame(4000)
QUIET = frame(5)


class FakeStream:
    """Replays a scripted sequence of frames, then silence forever."""

    def __init__(self, frames):
        self.frames = list(frames)
        self.reads = 0

    def read(self, _count, exception_on_overflow=False):
        self.reads += 1
        return self.frames.pop(0) if self.frames else QUIET


class CaptureTests(unittest.TestCase):
    def _transcriber(self, **overrides):
        settings = {"energy": 180, "pause": 0.2, "partial_interval": 0.1, "start_timeout": 1.0}
        settings.update(overrides)
        transcriber = LiveTranscriber(**settings)
        transcriber._transcribe = Mock(return_value="hello there")
        return transcriber

    def test_returns_the_final_transcript_after_silence(self):
        transcriber = self._transcriber()
        stream = FakeStream([LOUD] * 30 + [QUIET] * 10)
        self.assertEqual(transcriber._capture(stream, None, None), "hello there")

    def test_gives_up_when_nobody_speaks(self):
        transcriber = self._transcriber(start_timeout=0.2)
        stream = FakeStream([QUIET] * 200)
        self.assertEqual(transcriber._capture(stream, None, None), "")
        transcriber._transcribe.assert_not_called()

    def test_emits_partial_text_while_speaking(self):
        transcriber = self._transcriber()
        partials = []
        stream = FakeStream([LOUD] * 60 + [QUIET] * 10)
        transcriber._capture(stream, partials.append, None)
        deadline = time.time() + 2
        while not partials and time.time() < deadline:
            time.sleep(0.01)
        self.assertTrue(partials)
        self.assertEqual(partials[0], "hello there")

    def test_reports_input_level_during_capture(self):
        transcriber = self._transcriber()
        levels = []
        transcriber._capture(FakeStream([LOUD] * 20 + [QUIET] * 10), None, levels.append)
        self.assertTrue(levels)
        self.assertGreater(max(levels), 0.0)

    def test_stops_at_the_maximum_length(self):
        transcriber = self._transcriber(max_seconds=0.5, pause=99)
        stream = FakeStream([LOUD] * 500)
        transcriber._capture(stream, None, None)
        # 0.5s at 64ms per frame is about 8 frames, plus the pre-roll.
        self.assertLess(stream.reads, 40)

    def test_a_slow_partial_does_not_stack_up(self):
        transcriber = self._transcriber()
        transcriber._partial_running.set()  # pretend one is still running
        partials = []
        transcriber._capture(FakeStream([LOUD] * 40 + [QUIET] * 10), partials.append, None)
        self.assertEqual(partials, [])


class ModelSelectionTests(unittest.TestCase):
    def test_drafts_and_finals_use_different_models(self):
        transcriber = LiveTranscriber(model="base", partial_model="tiny")
        self.assertEqual(transcriber.model_name, "base")
        self.assertEqual(transcriber.partial_model_name, "tiny")

    def test_settings_drive_both_models(self):
        settings = Mock()
        settings.get.side_effect = lambda key, default=None: {
            "whisper_model": "small", "partial_whisper_model": "base", "mic_energy": 250,
        }.get(key, default)
        transcriber = LiveTranscriber.from_settings(settings)
        self.assertEqual(transcriber.model_name, "small")
        self.assertEqual(transcriber.partial_model_name, "base")
        self.assertEqual(transcriber.energy, 250)

    def test_a_missing_device_returns_empty_rather_than_raising(self):
        transcriber = LiveTranscriber()
        transcriber._capture = Mock(side_effect=OSError("no input device"))
        self.assertEqual(transcriber.listen(), "")


if __name__ == "__main__":
    unittest.main()
