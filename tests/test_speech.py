import threading
import time
import unittest
from unittest.mock import Mock

from jarvis_os.speech import (
    DEFAULT_EDGE_VOICE,
    EdgeSpeech,
    HandsFreeListener,
    SpeechEngine,
    prepare_for_speech,
)


class SpeechEngineTests(unittest.TestCase):
    def test_prepares_display_text_without_speaking_markup_or_emoji(self):
        spoken = prepare_for_speech("## Result 🤖\n- **Open** [the guide](https://example.com) ✅")
        self.assertEqual(spoken, "Result. Open the guide.")

    def test_pronounces_jarvis_as_a_word(self):
        self.assertEqual(prepare_for_speech("J.A.R.V.I.S is ready"), "Jarvis is ready.")

    def test_prefers_matching_male_voice(self):
        engine = Mock()
        engine.getProperty.return_value = [
            type("Voice", (), {"name": "Microsoft Zira", "id": "zira"})(),
            type("Voice", (), {"name": "Microsoft David", "id": "david"})(),
        ]
        SpeechEngine(voice_hint="david")._select_voice(engine)
        engine.setProperty.assert_called_once_with("voice", "david")

    def test_clamps_voice_properties(self):
        speech = SpeechEngine(rate=900, volume=4)
        self.assertEqual(speech.rate, 260)
        self.assertEqual(speech.volume, 1.0)


    def test_defaults_to_the_natural_neural_voice(self):
        speech = SpeechEngine()
        self.assertEqual(speech.engine_name, "edge")
        self.assertEqual(speech.edge_voice, DEFAULT_EDGE_VOICE)

    def test_maps_words_per_minute_onto_edge_cadence(self):
        self.assertEqual(EdgeSpeech.rate_to_percent(200), "+0%")
        self.assertEqual(EdgeSpeech.rate_to_percent(178), "-11%")
        self.assertEqual(EdgeSpeech.rate_to_percent(9000), "+50%")
        self.assertEqual(EdgeSpeech.rate_to_percent(-9000), "-50%")

    def test_falls_back_to_windows_voice_when_edge_fails(self):
        speech = SpeechEngine()
        speech._speak_edge = Mock(side_effect=OSError("no internet"))
        speech._speak_windows = Mock()
        speech.speak_now("hello")
        speech._speak_windows.assert_called_once_with("hello")
        self.assertEqual(speech._edge_failures, 1)

    def test_stops_retrying_edge_after_repeated_failures(self):
        speech = SpeechEngine()
        speech._speak_edge = Mock(side_effect=OSError("no internet"))
        speech._speak_windows = Mock()
        for _ in range(speech.MAX_EDGE_FAILURES + 2):
            speech.speak_now("hello")
        self.assertEqual(speech._speak_edge.call_count, speech.MAX_EDGE_FAILURES)

    def test_windows_engine_setting_skips_edge_entirely(self):
        speech = SpeechEngine(engine="windows")
        speech._speak_edge = Mock()
        speech._speak_windows = Mock()
        speech.speak_now("hello")
        speech._speak_edge.assert_not_called()
        speech._speak_windows.assert_called_once_with("hello")

    def test_silence_drops_queued_speech(self):
        speech = SpeechEngine()
        speech.queue.put("one")
        speech.queue.put("two")
        speech.silence()
        self.assertTrue(speech.queue.empty())


class HandsFreeListenerTests(unittest.TestCase):
    def test_submits_recognized_text(self):
        received = []
        listener = HandsFreeListener(
            lambda: "hello jarvis",
            received.append,
            lambda _state: None,
            threading.Event(),
        )
        listener.start()
        deadline = time.time() + 1
        while not received and time.time() < deadline:
            time.sleep(0.01)
        listener.stop()
        self.assertEqual(received[0], "hello jarvis")

    def test_does_not_listen_over_speech(self):
        speaking = threading.Event()
        speaking.set()
        listen = Mock(return_value="echo")
        listener = HandsFreeListener(listen, Mock(), lambda _state: None, speaking)
        listener.start()
        time.sleep(0.25)
        listener.stop()
        listen.assert_not_called()
