"""Transcription that reports words while you are still speaking.

Waiting for a whole phrase before showing anything means a misheard word is
only discovered after you have finished the sentence. Capturing continuously
and transcribing the audio so far lets the text appear as you talk, so you can
see it going wrong and stop.

The capture loop never blocks on transcription. A partial runs on its own
thread against a snapshot of the audio, and is skipped if the previous one has
not finished, which keeps the microphone from overflowing on a slow machine.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from .audio_level import normalise, rms
from .diagnostics_log import failure

SAMPLE_RATE = 16000
FRAME = 1024
FRAME_SECONDS = FRAME / SAMPLE_RATE


class LiveTranscriber:
    """Records until you stop speaking, emitting partial text along the way."""

    def __init__(
        self,
        model: str = "base",
        partial_model: str = "tiny",
        energy: int = 180,
        pause: float = 1.25,
        partial_interval: float = 1.2,
        max_seconds: float = 30.0,
        start_timeout: float = 18.0,
        device_index: int | None = None,
    ):
        self.model_name = model
        # Drafts favour speed over accuracy and the final result favours
        # accuracy over speed. Measured on this class of machine: tiny returns
        # in about 1.2s where base takes 2.2s, but hears "Javas" for "Jarvis".
        self.partial_model_name = partial_model
        self.energy = energy
        self.pause = pause
        self.partial_interval = partial_interval
        self.max_seconds = max_seconds
        self.start_timeout = start_timeout
        self.device_index = device_index
        self._models: dict[str, object] = {}
        self._model_lock = threading.Lock()
        self._partial_running = threading.Event()

    # ------------------------------------------------------------- model

    def signature(self) -> tuple:
        """What must match for a transcriber to be reusable: its models."""
        return (self.model_name, self.partial_model_name, self.device_index)

    def apply(self, other: "LiveTranscriber") -> None:
        """Adopt another's tuning without discarding the loaded models."""
        self.energy = other.energy
        self.pause = other.pause
        self.partial_interval = other.partial_interval
        self.max_seconds = other.max_seconds
        self.start_timeout = other.start_timeout

    def _load(self, name: str):
        with self._model_lock:
            if name not in self._models:
                from faster_whisper import WhisperModel

                self._models[name] = WhisperModel(name, device="cpu", compute_type="int8")
            return self._models[name]

    def warm(self) -> None:
        """Load the recogniser up front so the first phrase is not slow."""
        for name in {self.model_name, self.partial_model_name}:
            try:
                self._load(name)
            except Exception as error:
                failure("live_transcribe.warm", error, name)

    def _transcribe(self, audio: bytes, draft: bool = False) -> str:
        import numpy

        samples = numpy.frombuffer(audio, dtype=numpy.int16).astype(numpy.float32) / 32768.0
        if samples.size < SAMPLE_RATE // 4:
            return ""
        model = self._load(self.partial_model_name if draft else self.model_name)
        segments, _info = model.transcribe(samples, language=None, beam_size=1, vad_filter=False)
        return " ".join(segment.text for segment in segments).strip()

    # ----------------------------------------------------------- capture

    def listen(self, on_partial: Callable[[str], None] | None = None,
               on_level: Callable[[float], None] | None = None) -> str:
        """Capture one phrase and return it. Emits partials while speaking."""
        import pyaudio

        audio = stream = None
        try:
            audio = pyaudio.PyAudio()
            stream = audio.open(
                rate=SAMPLE_RATE, channels=1, format=pyaudio.paInt16, input=True,
                frames_per_buffer=FRAME,
                input_device_index=self.device_index if self.device_index is not None else None,
            )
            return self._capture(stream, on_partial, on_level)
        except Exception as error:
            failure("live_transcribe.listen", error)
            return ""
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

    def _capture(self, stream, on_partial, on_level) -> str:
        # A short pre-roll keeps the first syllable, which is otherwise clipped
        # because speech is only detected after it has already begun.
        preroll: list[bytes] = []
        preroll_frames = max(1, int(0.3 / FRAME_SECONDS))
        collected: list[bytes] = []
        speaking = False
        silence = 0.0
        waited = 0.0
        spoken_for = 0.0
        since_partial = 0.0
        latest = ""

        while True:
            data = stream.read(FRAME, exception_on_overflow=False)
            level = rms(data)
            if on_level:
                on_level(normalise(level))
            loud = level > self.energy

            if not speaking:
                preroll.append(data)
                del preroll[:-preroll_frames]
                waited += FRAME_SECONDS
                if loud:
                    speaking = True
                    collected.extend(preroll)
                    collected.append(data)
                elif waited >= self.start_timeout:
                    return ""
                continue

            collected.append(data)
            spoken_for += FRAME_SECONDS
            since_partial += FRAME_SECONDS
            silence = 0.0 if loud else silence + FRAME_SECONDS

            if on_partial and since_partial >= self.partial_interval and not self._partial_running.is_set():
                since_partial = 0.0
                self._emit_partial(b"".join(collected), on_partial)

            if silence >= self.pause or spoken_for >= self.max_seconds:
                break

        try:
            latest = self._transcribe(b"".join(collected))
        except Exception as error:
            failure("live_transcribe.final", error)
        return latest

    def _emit_partial(self, audio: bytes, on_partial: Callable[[str], None]) -> None:
        self._partial_running.set()

        def work() -> None:
            try:
                text = self._transcribe(audio, draft=True)
                if text:
                    on_partial(text)
            except Exception as error:
                failure("live_transcribe.partial", error)
            finally:
                self._partial_running.clear()

        threading.Thread(target=work, daemon=True, name="jarvis-partial").start()

    @classmethod
    def from_settings(cls, settings_repo=None, fallback_model: str = "base") -> "LiveTranscriber":
        if not settings_repo:
            return cls(model=fallback_model)
        return cls(
            model=str(settings_repo.get("whisper_model", fallback_model)),
            partial_model=str(settings_repo.get("partial_whisper_model", "tiny")),
            energy=int(settings_repo.get("mic_energy", 180)),
            pause=float(settings_repo.get("mic_pause", 1.25)),
            partial_interval=float(settings_repo.get("partial_interval", 1.2)),
            start_timeout=float(settings_repo.get("mic_timeout", 18)),
            device_index=settings_repo.get("mic_device_index"),
        )
