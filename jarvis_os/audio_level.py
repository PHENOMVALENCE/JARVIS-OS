"""Live microphone loudness, so the interface can react while you speak.

This deliberately does not transcribe anything. It opens a small input stream,
measures loudness, and throws the audio away, which is enough to drive the
visualiser and to tell the user their microphone is actually working.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable


SAMPLE_RATE = 16000
CHUNK = 1024

# Speech sits well above room tone but far below digital full scale, so the
# meter is calibrated against a realistic speaking range rather than 0-32768.
NOISE_FLOOR = 130.0
SPEECH_CEILING = 6000.0


def normalise(rms: float) -> float:
    """Map a raw RMS amplitude onto 0-1 with a logarithmic response."""
    if rms <= NOISE_FLOOR:
        return 0.0
    span = math.log10(SPEECH_CEILING / NOISE_FLOOR)
    value = math.log10(min(rms, SPEECH_CEILING) / NOISE_FLOOR) / span
    return max(0.0, min(1.0, value))


class MicrophoneLevel:
    """Reports smoothed input level to a callback until stopped."""

    def __init__(self, on_level: Callable[[float], None], device_index: int | None = None,
                 interval: float = 0.05):
        self.on_level = on_level
        self.device_index = device_index
        self.interval = interval
        self.level = 0.0
        self.available = False
        self.error = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="jarvis-mic-level")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _open(self):
        import pyaudio

        audio = pyaudio.PyAudio()
        stream = audio.open(
            rate=SAMPLE_RATE, channels=1, format=pyaudio.paInt16, input=True,
            frames_per_buffer=CHUNK,
            input_device_index=self.device_index if self.device_index is not None else None,
        )
        return audio, stream

    def _run(self) -> None:
        audio = stream = None
        try:
            import audioop

            audio, stream = self._open()
            self.available = True
            while not self._stop.is_set():
                data = stream.read(CHUNK, exception_on_overflow=False)
                target = normalise(audioop.rms(data, 2))
                # Rise quickly so speech registers immediately, fall slowly so the
                # visualiser glides instead of flickering between syllables.
                weight = 0.55 if target > self.level else 0.18
                self.level += (target - self.level) * weight
                self.on_level(self.level)
                time.sleep(self.interval)
        except Exception as exc:
            self.available = False
            self.error = str(exc)
            self.on_level(0.0)
        finally:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            if audio is not None:
                try:
                    audio.terminate()
                except Exception:
                    pass


def measure_ambient(seconds: float = 1.5, device_index: int | None = None) -> float:
    """Sample room tone, used to calibrate the speech detection threshold."""
    import audioop

    import pyaudio

    audio = pyaudio.PyAudio()
    stream = None
    readings: list[float] = []
    try:
        stream = audio.open(
            rate=SAMPLE_RATE, channels=1, format=pyaudio.paInt16, input=True,
            frames_per_buffer=CHUNK,
            input_device_index=device_index if device_index is not None else None,
        )
        deadline = time.time() + seconds
        while time.time() < deadline:
            readings.append(audioop.rms(stream.read(CHUNK, exception_on_overflow=False), 2))
    finally:
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass
        audio.terminate()
    if not readings:
        return 0.0
    readings.sort()
    # Median ignores the occasional door slam during calibration.
    return float(readings[len(readings) // 2])


def suggested_energy(ambient: float) -> int:
    """Turn a room-tone reading into a whisper_mic energy threshold.

    The threshold has to clear room tone without climbing so high that normal
    speech fails to trigger it, so it sits a little under twice the ambient
    reading with a floor for very quiet rooms.
    """
    return int(max(120, min(500, ambient * 1.8 + 60)))
