"""Speech output and hands-free listening services."""

from __future__ import annotations

import queue
import re
import threading
import time
import unicodedata
from collections.abc import Callable


def prepare_for_speech(text: str) -> str:
    """Turn display-oriented assistant text into clean spoken language."""
    value = str(text)
    value = re.sub(r"```.*?```", " ", value, flags=re.DOTALL)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", value)
    value = re.sub(r"(?m)^\s*[-*+]\s+", "", value)
    value = value.replace("**", "").replace("__", "").replace("~~", "")
    value = re.sub(r"\bJ\.A\.R\.V\.I\.S\b", "Jarvis", value, flags=re.IGNORECASE)
    value = "".join(
        character for character in value
        if not unicodedata.category(character).startswith(("So", "Sk"))
    )
    value = re.sub(r"\s*\n+\s*", ". ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    value = re.sub(r"\.{2,}", ".", value)
    return f"{value}." if value and value[-1] not in ".!?" else value


class SentenceBuffer:
    """Collects streamed model tokens into speakable sentences.

    Speaking each token would stutter and speaking the whole reply would waste
    the time the model spends generating it, so release at sentence boundaries
    once there is enough text to sound natural.
    """

    BOUNDARY = re.compile(r"(?<=[.!?])[\"')\]]*\s")
    # Long enough to skip "Sure." and "Yes." openers, short enough that a real
    # short sentence still gets spoken on its own.
    MIN_LENGTH = 15

    def __init__(self, min_length: int = MIN_LENGTH):
        self.min_length = min_length
        self._pending = ""

    def push(self, chunk: str) -> list[str]:
        """Add streamed text and return whatever is now safe to speak."""
        self._pending += str(chunk)
        released: list[str] = []
        while True:
            match = self.BOUNDARY.search(self._pending)
            if not match:
                break
            candidate = self._pending[: match.end()].strip()
            if len(candidate) < self.min_length:
                # Too short to stand alone: let it join the next sentence.
                following = self.BOUNDARY.search(self._pending, match.end())
                if not following:
                    break
                candidate = self._pending[: following.end()].strip()
                self._pending = self._pending[following.end():]
            else:
                self._pending = self._pending[match.end():]
            if candidate:
                released.append(candidate)
        return released

    def flush(self) -> str:
        remainder, self._pending = self._pending.strip(), ""
        return remainder


DEFAULT_EDGE_VOICE = "en-GB-RyanNeural"

EDGE_VOICES = {
    "en-GB-RyanNeural": "British male — closest to the J.A.R.V.I.S character",
    "en-GB-ThomasNeural": "British male, softer and slower",
    "en-US-GuyNeural": "American male, warm and conversational",
    "en-US-ChristopherNeural": "American male, deeper and calmer",
    "en-GB-SoniaNeural": "British female",
    "en-US-JennyNeural": "American female, conversational",
}


class EdgeSpeech:
    """Microsoft Edge neural voices: natural sounding, free, and no API key.

    Synthesis needs an internet connection, so callers fall back to SAPI offline.
    """

    def __init__(self, voice: str = DEFAULT_EDGE_VOICE, rate: int = 178, volume: float = 1.0):
        self.voice = (voice or DEFAULT_EDGE_VOICE).strip() or DEFAULT_EDGE_VOICE
        self.rate_percent = self.rate_to_percent(rate)
        self.volume = max(0.0, min(1.0, float(volume)))
        self._mixer = None

    @staticmethod
    def rate_to_percent(rate: int) -> str:
        """Map a pyttsx3 words-per-minute rate onto Edge's relative cadence."""
        percent = max(-50, min(50, round((int(rate) - 200) / 2)))
        return f"{percent:+d}%"

    def synthesize(self, text: str) -> bytes:
        import asyncio

        import edge_tts

        async def collect() -> bytes:
            audio = bytearray()
            stream = edge_tts.Communicate(text, self.voice, rate=self.rate_percent).stream()
            async for chunk in stream:
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
            return bytes(audio)

        return asyncio.run(collect())

    def play(self, payload: bytes) -> None:
        import io
        import os

        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame

        if self._mixer is None:
            pygame.mixer.init()
            self._mixer = pygame.mixer
        self._mixer.music.load(io.BytesIO(payload))
        self._mixer.music.set_volume(self.volume)
        self._mixer.music.play()
        while self._mixer.music.get_busy():
            time.sleep(0.05)

    def say(self, text: str) -> None:
        payload = self.synthesize(text)
        if not payload:
            raise RuntimeError("Edge TTS returned no audio.")
        self.play(payload)

    def stop(self) -> None:
        if self._mixer is not None:
            self._mixer.music.stop()


class _SpeechActivity:
    """Event-like view that also counts queued speech.

    Streamed replies are spoken one sentence at a time, so `speaking` clears
    briefly between them. Listening in those gaps would capture the assistant's
    own voice, so treat pending speech as still speaking.
    """

    def __init__(self, engine: "SpeechEngine"):
        self._engine = engine

    def is_set(self) -> bool:
        return self._engine.speaking.is_set() or not self._engine.queue.empty()


class SpeechEngine:
    """Thread-safe queued text-to-speech, preferring a natural neural voice."""

    MALE_HINTS = ("david", "mark", "guy", "male")
    MAX_EDGE_FAILURES = 3

    def __init__(
        self,
        rate: int = 178,
        volume: float = 1.0,
        voice_hint: str = "",
        engine: str = "edge",
        edge_voice: str = DEFAULT_EDGE_VOICE,
    ):
        self.rate = max(100, min(260, int(rate)))
        self.volume = max(0.0, min(1.0, float(volume)))
        self.voice_hint = voice_hint.strip().lower()
        self.engine_name = (engine or "edge").strip().lower()
        self.edge_voice = edge_voice or DEFAULT_EDGE_VOICE
        self.queue: queue.Queue[str | None] = queue.Queue()
        self.speaking = threading.Event()
        self._thread: threading.Thread | None = None
        self._edge: EdgeSpeech | None = None
        self._windows = None
        self._edge_failures = 0
        self.activity = _SpeechActivity(self)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="jarvis-speech")
        self._thread.start()

    def say(self, text: str) -> None:
        cleaned = prepare_for_speech(text)
        if cleaned:
            self.queue.put(cleaned)

    def stop(self) -> None:
        self.queue.put(None)

    def silence(self) -> None:
        """Drop queued speech and cut off anything already playing."""
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break
        if self._edge is not None:
            self._edge.stop()
        if self._windows is not None:
            try:
                self._windows.stop()
            except Exception:
                self._windows = None

    def _select_voice(self, engine) -> None:
        voices = list(engine.getProperty("voices") or [])
        hints = (self.voice_hint, *self.MALE_HINTS) if self.voice_hint else self.MALE_HINTS
        for hint in hints:
            for voice in voices:
                searchable = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".lower()
                if hint and hint in searchable:
                    engine.setProperty("voice", voice.id)
                    return

    def _speak_windows(self, text: str) -> None:
        if self._windows is None:
            import pyttsx3

            engine = pyttsx3.init()
            self._select_voice(engine)
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)
            self._windows = engine
        self._windows.say(text)
        self._windows.runAndWait()

    def _speak_edge(self, text: str) -> None:
        if self._edge is None:
            self._edge = EdgeSpeech(self.edge_voice, self.rate, self.volume)
        self._edge.say(text)

    def speak_now(self, text: str) -> None:
        """Speak once, falling back to the offline Windows voice when Edge fails."""
        if self.engine_name == "edge" and self._edge_failures < self.MAX_EDGE_FAILURES:
            try:
                self._speak_edge(text)
                self._edge_failures = 0
                return
            except Exception:
                # Usually no internet connection. Retry a few times, then stay on SAPI.
                self._edge_failures += 1
                self._edge = None
        self._speak_windows(text)

    def _run(self) -> None:
        while (text := self.queue.get()) is not None:
            self.speaking.set()
            try:
                self.speak_now(text)
            except Exception:
                self._windows = None
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
        barge_in: bool = False,
        on_interrupt: Callable[[], None] | None = None,
    ):
        self.listen_once = listen_once
        self.on_text = on_text
        self.on_state = on_state
        self.speaking = speaking
        # Without acoustic echo cancellation the microphone hears the speakers,
        # so listening over playback only works on headphones. Opt in.
        self.barge_in = barge_in
        self.on_interrupt = on_interrupt
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
            interrupting = self.speaking.is_set()
            if interrupting and not self.barge_in:
                self.on_state("speaking")
                time.sleep(0.15)
                continue
            try:
                self.on_state("listening")
                text = self.listen_once()
                if not text or not self.enabled.is_set():
                    continue
                if self.speaking.is_set():
                    if not self.barge_in:
                        continue
                    if self.on_interrupt:
                        self.on_interrupt()
                self.on_text(text)
            except Exception as exc:
                self.on_state(f"error: {exc}")
                self.enabled.clear()
            time.sleep(0.1)
