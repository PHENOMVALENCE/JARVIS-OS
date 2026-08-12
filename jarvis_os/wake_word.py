"""Wake-word listeners with explicit lifecycle controls.

Two backends. openWakeWord is the default because it ships a pretrained
"hey jarvis" model, runs locally, and needs no account or key. Porcupine stays
available for anyone who already has an access key.
"""

from __future__ import annotations

import struct
import threading

from .diagnostics_log import failure


FRAME_LENGTH = 1280
SAMPLE_RATE = 16000


class OpenWakeWordListener:
    """Local wake word with no API key, using the pretrained hey_jarvis model."""

    def __init__(self, callback, keyword: str = "hey_jarvis", sensitivity: float = 0.55):
        self.callback = callback
        self.keyword = keyword
        # openWakeWord scores 0-1; treat the configured sensitivity as the bar
        # to clear, so a higher setting triggers more readily.
        self.threshold = 1.0 - max(0.0, min(1.0, float(sensitivity)))
        self.stop_event = threading.Event()
        self.thread = None

    def available(self) -> bool:
        try:
            import openwakeword  # noqa: F401
        except ImportError:
            return False
        return True

    def start(self) -> bool:
        if (self.thread and self.thread.is_alive()) or not self.available():
            return False
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True, name="jarvis-wake-word")
        self.thread.start()
        return True

    def stop(self) -> None:
        self.stop_event.set()

    def _model(self):
        import openwakeword.utils
        from openwakeword.model import Model

        try:
            openwakeword.utils.download_models([self.keyword])
        except Exception:
            pass
        return Model(wakeword_models=[self.keyword], inference_framework="onnx")

    def _run(self) -> None:
        import numpy
        import pyaudio

        stream = audio = None
        try:
            model = self._model()
            audio = pyaudio.PyAudio()
            stream = audio.open(
                rate=SAMPLE_RATE, channels=1, format=pyaudio.paInt16,
                input=True, frames_per_buffer=FRAME_LENGTH,
            )
            triggered = False
            while not self.stop_event.is_set():
                data = stream.read(FRAME_LENGTH, exception_on_overflow=False)
                scores = model.predict(numpy.frombuffer(data, dtype=numpy.int16))
                hit = any(score >= self.threshold for score in scores.values())
                # Only fire on the rising edge; the score stays high for several
                # frames after the phrase, which would otherwise retrigger.
                if hit and not triggered:
                    self.callback()
                triggered = hit
        except Exception as error:
            failure("wake_word", error)
        finally:
            if stream:
                stream.close()
            if audio:
                audio.terminate()


class WakeWordListener:
    """Porcupine wake word. Requires an access key from Picovoice."""

    def __init__(self, access_key: str, callback, keyword: str = "jarvis", sensitivity: float = 0.55):
        self.access_key = access_key
        self.callback = callback
        self.keyword = keyword
        self.sensitivity = max(0.0, min(1.0, float(sensitivity)))
        self.stop_event = threading.Event()
        self.thread = None

    def start(self) -> bool:
        if not self.access_key or (self.thread and self.thread.is_alive()):
            return False
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True, name="jarvis-wake-word")
        self.thread.start()
        return True

    def stop(self) -> None:
        self.stop_event.set()

    def _run(self) -> None:
        import pyaudio
        import pvporcupine
        engine = stream = audio = None
        try:
            engine = pvporcupine.create(
                access_key=self.access_key,
                keywords=[self.keyword],
                sensitivities=[self.sensitivity],
            )
            audio = pyaudio.PyAudio()
            stream = audio.open(
                rate=engine.sample_rate, channels=1, format=pyaudio.paInt16,
                input=True, frames_per_buffer=engine.frame_length,
            )
            while not self.stop_event.is_set():
                data = stream.read(engine.frame_length, exception_on_overflow=False)
                samples = struct.unpack_from("h" * engine.frame_length, data)
                if engine.process(samples) >= 0:
                    self.callback()
        finally:
            if stream:
                stream.close()
            if audio:
                audio.terminate()
            if engine:
                engine.delete()


def make_wake_word(callback, access_key: str = "", backend: str = "openwakeword",
                   keyword: str = "", sensitivity: float = 0.55):
    """Pick a backend, preferring the one that needs no account."""
    if backend == "porcupine" and access_key:
        return WakeWordListener(access_key, callback, keyword or "jarvis", sensitivity)
    listener = OpenWakeWordListener(callback, keyword or "hey_jarvis", sensitivity)
    if listener.available():
        return listener
    return WakeWordListener(access_key, callback, "jarvis", sensitivity)
