"""Optional Porcupine wake-word listener with explicit lifecycle controls."""

from __future__ import annotations

import struct
import threading


class WakeWordListener:
    def __init__(self, access_key: str, callback, keyword: str = "jarvis"):
        self.access_key = access_key
        self.callback = callback
        self.keyword = keyword
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
            engine = pvporcupine.create(access_key=self.access_key, keywords=[self.keyword])
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
