"""Speech output and hands-free listening services."""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable


class SpeechEngine:
    """Thread-safe queued text-to-speech with a preferred Windows male voice."""

    MALE_HINTS = ("david", "mark", "guy", "male")

    def __init__(self, rate: int = 178, volume: float = 1.0, voice_hint: str = ""):
        self.rate = max(100, min(260, int(rate)))
        self.volume = max(0.0, min(1.0, float(volume)))
        self.voice_hint = voice_hint.strip().lower()
        self.queue: queue.Queue[str | None] = queue.Queue()
        self.speaking = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="jarvis-speech")
        self._thread.start()

    def say(self, text: str) -> None:
        cleaned = " ".join(str(text).split())
        if cleaned:
            self.queue.put(cleaned)

    def stop(self) -> None:
        self.queue.put(None)

    def _select_voice(self, engine) -> None:
        voices = list(engine.getProperty("voices") or [])
        hints = (self.voice_hint, *self.MALE_HINTS) if self.voice_hint else self.MALE_HINTS
        for hint in hints:
            for voice in voices:
                searchable = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".lower()
                if hint and hint in searchable:
                    engine.setProperty("voice", voice.id)
                    return

    def _run(self) -> None:
        engine = None
        while (text := self.queue.get()) is not None:
            try:
                if engine is None:
                    import pyttsx3

                    engine = pyttsx3.init()
                    self._select_voice(engine)
                    engine.setProperty("rate", self.rate)
                    engine.setProperty("volume", self.volume)
                self.speaking.set()
                engine.say(text)
                engine.runAndWait()
            except Exception:
                engine = None
            finally:
                self.speaking.clear()


class HandsFreeListener:
    """Continuously requests speech while avoiding the assistant's own output."""

    def __init__(
        self,
        listen_once: Callable[[], str],
        on_text: Callable[[str], None],
        on_state: Callable[[str], None],
        speaking: threading.Event,
    ):
        self.listen_once = listen_once
        self.on_text = on_text
        self.on_state = on_state
        self.speaking = speaking
        self.enabled = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.enabled.set()
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="jarvis-hands-free")
        self._thread.start()

    def pause(self) -> None:
        self.enabled.clear()
        self.on_state("paused")

    def stop(self) -> None:
        self.enabled.clear()
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            if not self.enabled.wait(0.2):
                continue
            if self.speaking.is_set():
                self.on_state("speaking")
                time.sleep(0.15)
                continue
            try:
                self.on_state("listening")
                text = self.listen_once()
                if text and self.enabled.is_set() and not self.speaking.is_set():
                    self.on_text(text)
            except Exception as exc:
                self.on_state(f"error: {exc}")
                self.enabled.clear()
            time.sleep(0.1)
