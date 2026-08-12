"""Short tones that confirm the assistant heard you.

Saying "Hey Jarvis" into silence gives no sign it registered, so you end up
repeating yourself or talking before it is listening. A brief rising chime
closes that loop in a way a visual cue alone cannot, because you are usually
looking somewhere else when you speak.

Tones are synthesised rather than shipped as files, so there is nothing to
package and nothing to lose.
"""

from __future__ import annotations

import io
import math
import struct
import threading
import wave

from .diagnostics_log import failure

SAMPLE_RATE = 22050


def tone(notes: list[tuple[float, float]], volume: float = 0.35) -> bytes:
    """Render a sequence of (frequency, seconds) as a WAV.

    Each note is enveloped so the tone fades in and out; without that, the
    abrupt edges click audibly.
    """
    frames = bytearray()
    for frequency, duration in notes:
        count = int(SAMPLE_RATE * duration)
        for index in range(count):
            progress = index / max(1, count - 1)
            envelope = math.sin(math.pi * progress) ** 0.6
            sample = math.sin(math.tau * frequency * index / SAMPLE_RATE)
            frames.extend(struct.pack("<h", int(sample * envelope * volume * 32767)))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(bytes(frames))
    return buffer.getvalue()


# Rising for attention, falling for completion, low for refusal.
WAKE = [(660.0, 0.09), (990.0, 0.13)]
DONE = [(880.0, 0.08), (660.0, 0.10)]
ERROR = [(330.0, 0.14), (247.0, 0.16)]


class Earcons:
    """Plays short tones without blocking the caller."""

    def __init__(self, enabled: bool = True, volume: float = 0.35):
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, float(volume)))
        self._cache: dict[str, bytes] = {}
        self._sound = None

    def _payload(self, name: str, notes: list[tuple[float, float]]) -> bytes:
        if name not in self._cache:
            self._cache[name] = tone(notes, self.volume)
        return self._cache[name]

    def _play(self, payload: bytes) -> None:
        import os

        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame

        if not pygame.mixer.get_init():
            pygame.mixer.init()
        # A Sound rather than the music channel, so a chime can overlap speech
        # instead of interrupting it.
        sound = pygame.mixer.Sound(io.BytesIO(payload))
        sound.set_volume(self.volume)
        sound.play()

    def play(self, name: str = "wake") -> None:
        if not self.enabled:
            return
        notes = {"wake": WAKE, "done": DONE, "error": ERROR}.get(name, WAKE)
        payload = self._payload(name, notes)

        def work() -> None:
            try:
                self._play(payload)
            except Exception as error:
                failure("earcon", error, name)

        threading.Thread(target=work, daemon=True, name=f"jarvis-earcon-{name}").start()
