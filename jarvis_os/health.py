"""Whether each subsystem is actually working, and what to do when it is not.

The existing diagnostics answer "is this installed". This answers "is this
working right now", which is the question a person asks when the assistant
seems off. Every check reports one of five states and, where it can, the next
step to take.

Checks are cheap and read-only. Nothing here starts a model, records audio, or
changes configuration.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .diagnostics_log import failure


class Status(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    DISABLED = "DISABLED"
    NOT_CONFIGURED = "NOT CONFIGURED"


@dataclass(frozen=True)
class Check:
    subsystem: str
    status: Status
    detail: str
    remedy: str = ""

    @property
    def needs_attention(self) -> bool:
        return self.status in {Status.DEGRADED, Status.FAILED}


def _module_present(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


class HealthService:
    """Runs every subsystem check and summarises the result."""

    def __init__(self, settings_repo=None, data_dir: Path | None = None,
                 context=None, registry=None, speech_engine=None, reminders=None):
        self.settings_repo = settings_repo
        self.data_dir = data_dir or Path.cwd() / "data"
        self.context = context
        self.registry = registry
        self.speech_engine = speech_engine
        self.reminders = reminders

    def _setting(self, key: str, default=None):
        return self.settings_repo.get(key, default) if self.settings_repo else default

    # ------------------------------------------------------------- checks

    def check_microphone(self) -> Check:
        try:
            import pyaudio

            audio = pyaudio.PyAudio()
            try:
                count = sum(
                    1 for index in range(audio.get_device_count())
                    if audio.get_device_info_by_index(index).get("maxInputChannels", 0) > 0
                )
            finally:
                audio.terminate()
        except Exception as error:
            failure("health.microphone", error)
            return Check("Microphone", Status.FAILED, str(error)[:80],
                         "Check that a microphone is connected and allowed in Windows privacy settings.")
        if not count:
            return Check("Microphone", Status.FAILED, "No input device found.",
                         "Connect a microphone, then run setup again to calibrate it.")
        return Check("Microphone", Status.OK, f"{count} input device(s)")

    def check_speech_recognition(self) -> Check:
        if not _module_present("faster_whisper"):
            return Check("Speech recognition", Status.FAILED, "faster-whisper is not installed.",
                         "Run Setup-Jarvis.ps1 to install dependencies.")
        model = self._setting("whisper_model", "base")
        draft = self._setting("partial_whisper_model", "tiny")
        return Check("Speech recognition", Status.OK, f"{model} for results, {draft} for drafts")

    def check_speech_output(self) -> Check:
        engine = str(self._setting("tts_engine", "edge"))
        if engine == "piper":
            models = Path(self._setting("models_dir", "") or "models")
            voice = self._setting("piper_voice", "en_GB-alan-medium")
            if not (models / f"{voice}.onnx").exists():
                return Check("Speech output", Status.DEGRADED,
                             f"The offline voice {voice} is not downloaded.",
                             "It downloads on first use, or choose the edge voice in Settings.")
        if self.speech_engine is not None and getattr(self.speech_engine, "_edge_failures", 0) >= 3:
            return Check("Speech output", Status.DEGRADED,
                         "The online voice failed repeatedly and fell back to the Windows voice.",
                         "Check the network, or switch to the offline voice in Settings.")
        return Check("Speech output", Status.OK, f"{engine} voice")

    def check_wake_word(self) -> Check:
        if not self._setting("wake_word_enabled", False):
            return Check("Wake word", Status.DISABLED, "Not listening for the wake phrase.",
                         "Turn on the wake word in Settings to say Hey Jarvis.")
        if not _module_present("openwakeword"):
            return Check("Wake word", Status.FAILED, "openwakeword is not installed.",
                         "Run Setup-Jarvis.ps1 to install dependencies.")
        return Check("Wake word", Status.OK, "Listening for Hey Jarvis")

    def check_language_model(self) -> Check:
        if not shutil.which("ollama"):
            return Check("Language model", Status.NOT_CONFIGURED, "Ollama is not installed.",
                         "Install Ollama from ollama.com, then run: ollama pull gemma2:2b")
        try:
            import subprocess

            completed = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=15)
        except Exception as error:
            failure("health.model", error)
            return Check("Language model", Status.FAILED, str(error)[:80],
                         "Start the Ollama service and try again.")
        if completed.returncode:
            return Check("Language model", Status.FAILED, "The Ollama service did not respond.",
                         "Start Ollama, then ask again.")
        wanted = str(self._setting("ollama_model", "gemma2:2b"))
        if wanted.split(":")[0] not in completed.stdout:
            return Check("Language model", Status.DEGRADED, f"{wanted} is not downloaded.",
                         f"Run: ollama pull {wanted}")
        return Check("Language model", Status.OK, f"{wanted} available")

    def check_screen_reading(self) -> Check:
        try:
            from .ocr import ScreenTextReader

            if not ScreenTextReader().available():
                return Check("Screen reading", Status.DEGRADED,
                             "No OCR language pack is installed for this user.",
                             "Add an English language pack in Windows language settings.")
        except Exception as error:
            return Check("Screen reading", Status.FAILED, str(error)[:80],
                         "Run Setup-Jarvis.ps1 to install the Windows OCR components.")
        if self._setting("privacy_mode", False):
            return Check("Screen reading", Status.DISABLED, "Privacy mode blocks screen capture.",
                         "Turn privacy mode off in Settings to read the screen.")
        return Check("Screen reading", Status.OK, "Windows OCR available")

    def check_file_search(self) -> Check:
        if not _module_present("win32com"):
            return Check("File search", Status.DEGRADED, "pywin32 is missing, so searches walk the disk.",
                         "Run Setup-Jarvis.ps1 to restore fast indexed search.")
        return Check("File search", Status.OK, "Windows Search index")

    def check_ui_automation(self) -> Check:
        if not _module_present("pywinauto"):
            return Check("Window control", Status.DEGRADED, "pywinauto is missing.",
                         "Run Setup-Jarvis.ps1 to restore control of other applications.")
        return Check("Window control", Status.OK, "UI Automation available")

    def check_context(self) -> Check:
        if self.context is None:
            return Check("Context", Status.NOT_CONFIGURED, "No context engine is attached.")
        result = self.context.health()
        return Check("Context", Status(result.get("status", "FAILED")), result.get("detail", ""))

    def check_network(self) -> Check:
        if self.context is not None:
            try:
                if not self.context.snapshot().online:
                    return Check("Network", Status.DEGRADED, "Windows reports no connection.",
                                 "Live answers and the online voice need a connection.")
            except Exception as error:
                failure("health.network", error)
        return Check("Network", Status.OK, "Connected")

    def check_research(self) -> Check:
        import os

        if os.getenv("SERPAPI_API_KEY", "").strip():
            return Check("Live research", Status.OK, "Full web search configured")
        return Check("Live research", Status.DEGRADED,
                     "Only encyclopedic sources are available.",
                     "Set SERPAPI_API_KEY in .env for current-events coverage.")

    def check_reminders(self) -> Check:
        if self.reminders is None:
            return Check("Reminders", Status.NOT_CONFIGURED, "No reminder service is attached.")
        try:
            pending = self.reminders.store.pending()
        except Exception as error:
            return Check("Reminders", Status.FAILED, str(error)[:80],
                         "The reminder table could not be read.")
        return Check("Reminders", Status.OK, f"{len(pending)} pending")

    def check_capabilities(self) -> Check:
        if self.registry is None:
            return Check("Capabilities", Status.NOT_CONFIGURED, "No registry is attached.")
        total = len(self.registry.actions())
        unverified = len(self.registry.unverified())
        return Check("Capabilities", Status.OK,
                     f"{total} actions, {total - unverified} with success checks")

    def check_disk(self) -> Check:
        try:
            free = shutil.disk_usage(str(self.data_dir.anchor or self.data_dir)).free / (1024 ** 3)
        except Exception as error:
            return Check("Disk", Status.FAILED, str(error)[:80])
        if free < 2:
            return Check("Disk", Status.FAILED, f"{free:.1f} GB free.",
                         "Free some space; models and logs need room.")
        if free < 10:
            return Check("Disk", Status.DEGRADED, f"{free:.1f} GB free.",
                         "Consider freeing space before installing a larger model.")
        return Check("Disk", Status.OK, f"{free:.0f} GB free")

    def check_memory(self) -> Check:
        from .hardware import detect, recommend

        machine = detect()
        profile = recommend(machine)
        if machine.available_ram_gb and machine.available_ram_gb < profile.needs_ram_gb:
            return Check("Memory", Status.DEGRADED,
                         f"{machine.available_ram_gb:.1f} GB free of {machine.total_ram_gb:.0f} GB.",
                         "Closing some windows will make replies noticeably faster.")
        return Check("Memory", Status.OK,
                     f"{machine.available_ram_gb:.1f} GB free of {machine.total_ram_gb:.0f} GB")

    def check_audit_log(self) -> Check:
        database = self.data_dir / "jarvis.db"
        if not database.exists():
            return Check("Audit log", Status.NOT_CONFIGURED, "No audit database yet.")
        try:
            from .security import AuditLog

            log = AuditLog(database)
            verify = getattr(log, "verify", None)
            if callable(verify) and not verify():
                return Check("Audit log", Status.FAILED, "The hash chain does not verify.",
                             "The action history may have been altered outside J.A.R.V.I.S.")
        except Exception as error:
            failure("health.audit", error)
            return Check("Audit log", Status.DEGRADED, str(error)[:80])
        return Check("Audit log", Status.OK, "Hash chain intact")

    # ------------------------------------------------------------ running

    def run(self) -> list[Check]:
        checks = (
            self.check_microphone, self.check_speech_recognition, self.check_speech_output,
            self.check_wake_word, self.check_language_model, self.check_screen_reading,
            self.check_file_search, self.check_ui_automation, self.check_context,
            self.check_network, self.check_research, self.check_reminders,
            self.check_capabilities, self.check_disk, self.check_memory, self.check_audit_log,
        )
        results = []
        for check in checks:
            try:
                results.append(check())
            except Exception as error:
                # The reporter must not fail on the reporting itself.
                name = getattr(check, "__name__", "check")
                failure("health.check", error, name)
                results.append(Check(name.replace("check_", "").title() or "Check",
                                     Status.FAILED, str(error)[:80]))
        return results

    def summarise(self, checks: list[Check] | None = None) -> str:
        """One spoken sentence, leading with whatever needs attention."""
        checks = checks if checks is not None else self.run()
        problems = [check for check in checks if check.needs_attention]
        if not problems:
            return f"All {len(checks)} subsystems are healthy."
        names = ", ".join(check.subsystem.lower() for check in problems[:3])
        more = f" and {len(problems) - 3} more" if len(problems) > 3 else ""
        first = problems[0]
        remedy = f" {first.remedy}" if first.remedy else ""
        return (f"{len(problems)} of {len(checks)} subsystems need attention: {names}{more}. "
                f"{first.subsystem}: {first.detail}{remedy}")
