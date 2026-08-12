"""Installing and switching the models J.A.R.V.I.S runs on.

Three separate things are called "the model": the language model that Ollama
serves, the speech recognition weights faster-whisper downloads, and the voice
Piper speaks with. They install differently and fail differently, so this puts
one interface over all three.

Nothing here downloads without being asked. Sizes are stated before they are
spent, because a multi-gigabyte pull on a metered connection is the user's
decision, not the assistant's.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .diagnostics_log import failure, get
from .hardware import Hardware, ModelProfile, detect, fits, recommend

log = get("models")

# Recognition weights, with the download size faster-whisper pulls.
SPEECH_MODELS = {
    "tiny": 0.08,
    "base": 0.15,
    "small": 0.49,
    "medium": 1.5,
}


@dataclass(frozen=True)
class InstallResult:
    succeeded: bool
    message: str
    already_present: bool = False


@dataclass(frozen=True)
class ModelState:
    kind: str
    name: str
    installed: bool
    detail: str = ""


class OllamaModels:
    """The language model, served by Ollama."""

    def __init__(self, timeout: int = 900):
        self.timeout = timeout

    def _run(self, arguments: list[str], timeout: int | None = None):
        return subprocess.run(
            ["ollama", *arguments], capture_output=True, text=True,
            timeout=timeout or self.timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    @property
    def available(self) -> bool:
        import shutil

        return shutil.which("ollama") is not None

    def installed(self) -> tuple[str, ...]:
        if not self.available:
            return ()
        try:
            completed = self._run(["list"], timeout=20)
        except Exception as error:
            failure("models.list", error)
            return ()
        if completed.returncode:
            return ()
        names = []
        for line in completed.stdout.splitlines()[1:]:
            parts = line.split()
            if parts:
                names.append(parts[0])
        return tuple(names)

    def has(self, model: str) -> bool:
        wanted = model.split(":")[0]
        return any(name.split(":")[0] == wanted for name in self.installed())

    def pull(self, model: str, on_progress: Callable[[str], None] | None = None) -> InstallResult:
        """Download a model. Long-running; report progress as it goes."""
        if not self.available:
            return InstallResult(False, "Ollama is not installed. Install it from ollama.com.")
        if self.has(model):
            return InstallResult(True, f"{model} is already installed.", already_present=True)
        try:
            process = subprocess.Popen(
                ["ollama", "pull", model], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as error:
            failure("models.pull", error, model)
            return InstallResult(False, f"Could not start the download: {error}")
        last = ""
        for line in process.stdout or ():
            line = line.strip()
            if line and line != last:
                last = line
                if on_progress:
                    on_progress(line)
        process.wait()
        if process.returncode:
            return InstallResult(False, f"Downloading {model} failed: {last or 'unknown error'}")
        log.info("Installed language model %s", model)
        return InstallResult(True, f"{model} is ready.")

    def remove(self, model: str) -> InstallResult:
        if not self.has(model):
            return InstallResult(True, f"{model} is not installed.", already_present=True)
        try:
            completed = self._run(["rm", model], timeout=60)
        except Exception as error:
            failure("models.remove", error, model)
            return InstallResult(False, str(error))
        if completed.returncode:
            return InstallResult(False, completed.stderr.strip() or f"Could not remove {model}.")
        return InstallResult(True, f"Removed {model}.")


class SpeechModels:
    """Recognition weights, cached by faster-whisper on first use."""

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or (Path.home() / ".cache" / "huggingface" / "hub")

    def installed(self, name: str) -> bool:
        if not self.cache_dir.exists():
            return False
        # faster-whisper stores each size in its own snapshot directory.
        return any(f"faster-whisper-{name}" in str(path) for path in self.cache_dir.glob("models--*"))

    def ensure(self, name: str, on_progress: Callable[[str], None] | None = None) -> InstallResult:
        if self.installed(name):
            return InstallResult(True, f"The {name} recognition model is ready.", already_present=True)
        if on_progress:
            on_progress(f"Downloading the {name} recognition model "
                        f"({SPEECH_MODELS.get(name, 0):.2f} GB)")
        try:
            from faster_whisper import WhisperModel

            WhisperModel(name, device="cpu", compute_type="int8")
        except Exception as error:
            failure("models.speech", error, name)
            return InstallResult(False, f"The {name} recognition model could not be downloaded: {error}")
        log.info("Installed recognition model %s", name)
        return InstallResult(True, f"The {name} recognition model is ready.")


class VoiceModels:
    """Offline neural voices, downloaded by Piper."""

    def __init__(self, models_dir: Path):
        self.models_dir = Path(models_dir)

    def installed(self, voice: str) -> bool:
        return (self.models_dir / f"{voice}.onnx").exists()

    def ensure(self, voice: str, on_progress: Callable[[str], None] | None = None) -> InstallResult:
        if self.installed(voice):
            return InstallResult(True, f"The {voice} voice is ready.", already_present=True)
        if on_progress:
            on_progress(f"Downloading the {voice} voice (about 63 MB)")
        try:
            from .speech import PiperSpeech

            if not PiperSpeech(voice, self.models_dir).ensure_voice():
                return InstallResult(False, f"The {voice} voice could not be downloaded.")
        except Exception as error:
            failure("models.voice", error, voice)
            return InstallResult(False, f"The {voice} voice could not be downloaded: {error}")
        log.info("Installed voice %s", voice)
        return InstallResult(True, f"The {voice} voice is ready.")


class ModelManager:
    """One interface over the language, recognition, and voice models."""

    def __init__(self, models_dir: Path, settings_repo=None,
                 language=None, speech=None, voices=None, hardware: Hardware | None = None):
        self.models_dir = Path(models_dir)
        self.settings_repo = settings_repo
        self.language = language or OllamaModels()
        self.speech = speech or SpeechModels()
        self.voices = voices or VoiceModels(self.models_dir)
        self._hardware = hardware

    @property
    def hardware(self) -> Hardware:
        if self._hardware is None:
            self._hardware = detect()
        return self._hardware

    def recommended(self) -> ModelProfile:
        return recommend(self.hardware)

    def plan(self, profile: ModelProfile) -> tuple[list[str], float]:
        """What still needs downloading for a profile, and how large it is."""
        needed, size = [], 0.0
        if not self.language.has(profile.model):
            needed.append(f"language model {profile.model}")
            size += profile.download_gb
        if not self.speech.installed(profile.speech_model):
            needed.append(f"{profile.speech_model} recognition model")
            size += SPEECH_MODELS.get(profile.speech_model, 0.0)
        return needed, round(size, 2)

    def describe_plan(self, profile: ModelProfile) -> str:
        """State the cost before spending it."""
        ok, why = fits(profile, self.hardware)
        if not ok:
            return why
        needed, size = self.plan(profile)
        if not needed:
            return f"{profile.name} is already installed."
        items = ", ".join(needed)
        return f"{profile.name} needs {items}. About {size:.1f} GB to download."

    def install(self, profile: ModelProfile,
                on_progress: Callable[[str], None] | None = None) -> InstallResult:
        """Install everything a profile needs, stopping at the first failure."""
        ok, why = fits(profile, self.hardware)
        if not ok:
            return InstallResult(False, why)
        speech = self.speech.ensure(profile.speech_model, on_progress)
        if not speech.succeeded:
            return speech
        language = self.language.pull(profile.model, on_progress)
        if not language.succeeded:
            return language
        if self.settings_repo is not None:
            self.settings_repo.set("ollama_model", profile.model)
            self.settings_repo.set("whisper_model", profile.speech_model)
            self.settings_repo.set("model_profile", profile.name)
        return InstallResult(True, f"{profile.name} is ready. {profile.summary}")

    def state(self) -> list[ModelState]:
        """What is installed right now, for diagnostics and the settings screen."""
        wanted_language = str(self.settings_repo.get("ollama_model", "gemma2:2b")) if self.settings_repo else "gemma2:2b"
        wanted_speech = str(self.settings_repo.get("whisper_model", "base")) if self.settings_repo else "base"
        wanted_voice = str(self.settings_repo.get("piper_voice", "en_GB-alan-medium")) if self.settings_repo else "en_GB-alan-medium"
        return [
            ModelState("language", wanted_language, self.language.has(wanted_language),
                       "served by Ollama" if self.language.available else "Ollama is not installed"),
            ModelState("recognition", wanted_speech, self.speech.installed(wanted_speech),
                       "downloads on first use"),
            ModelState("voice", wanted_voice, self.voices.installed(wanted_voice),
                       "only needed for the offline voice"),
        ]

    def health(self) -> dict[str, str]:
        missing = [state.name for state in self.state() if not state.installed and state.kind != "voice"]
        if not self.language.available:
            return {"status": "NOT CONFIGURED", "detail": "Ollama is not installed."}
        if missing:
            return {"status": "DEGRADED", "detail": f"Not downloaded: {', '.join(missing)}"}
        return {"status": "OK", "detail": "All configured models are installed."}
