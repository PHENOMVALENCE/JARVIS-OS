import threading
import time
import unittest
from unittest.mock import Mock

from jarvis_os.speech import HandsFreeListener, SpeechEngine


class SpeechEngineTests(unittest.TestCase):
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
