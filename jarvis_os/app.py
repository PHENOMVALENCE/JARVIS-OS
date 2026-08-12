"""Unified keyboard and voice desktop interface for J.A.R.V.I.S Mark 6."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, scrolledtext

from .actions import WindowsActions
from .assistant import AssistantController, ConversationStore, VoiceConfig, VoiceInput, make_provider
from .commands import Command
from .security import AuditLog, SecureExecutor
from .plugins import PluginManager
from .settings import Settings
from .settings_cache import CachedSettings
from .settings_ui import SettingsWindow
from .storage import Database, PermissionRepository, SettingsRepository
from .workflows import WorkflowEngine, WorkflowRepository
from .workflow_ui import WorkflowWindow
from .knowledge import KnowledgeIndex
from .proactive import ProactiveScheduler
from .user_presence import SecuritySession
from .setup_ui import SetupWizard
from .updates import UpdateChecker
from . import __version__
from .wake_word import make_wake_word
from .speech import DEFAULT_EDGE_VOICE, DEFAULT_PIPER_VOICE, HandsFreeListener, SentenceBuffer, SpeechEngine
from .audio_level import MicrophoneLevel
from .diagnostics_log import configure as configure_logging
from .diagnostics_log import failure, get as get_logger
from .earcons import Earcons
from .language import SWAHILI, voice_for
from .live_transcribe import LiveTranscriber
from .reminders import ReminderService, ReminderStore
from .orb import OrbCaption, VoiceOrb
from .theme import Palette, Space, Type, state_style
from .widgets import Button, Card, LevelMeter, MetricRow, StatusChip


class JarvisApp:
    def __init__(self, root: tk.Tk, settings: Settings | None = None):
        self.root = root
        self.settings = settings or Settings()
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        configure_logging(self.settings.data_dir)
        self.log = get_logger('app')
        self.work: queue.Queue[tuple[str, bool] | None] = queue.Queue()
        self.voice = None
        self._voice_lock = threading.Lock()
        database = Database(self.settings.data_dir / "jarvis.db")
        # Reads happen per streamed token, so they come from memory.
        self.settings_repo = CachedSettings(SettingsRepository(database))
        self.permissions_repo = PermissionRepository(database)
        audit = AuditLog(self.settings.data_dir / "jarvis.db")
        self.audit = audit
        self.security_session = SecuritySession(
            timeout_minutes=int(self.settings_repo.get("security_timeout_minutes", 15)),
            always_verify=bool(self.settings_repo.get("hello_for_high_risk", False)),
        )
        self.knowledge = KnowledgeIndex(database, self.settings_repo)
        self.reminders = ReminderService(
            ReminderStore(database), speak=lambda text: self.speech_engine.say(text)
        )
        self.plugins = PluginManager(
            self.settings.project_root / "plugins", database,
            WindowsActions(
                data_dir=self.settings.data_dir, settings_repo=self.settings_repo,
                openai_api_key=self.settings.openai_api_key, knowledge=self.knowledge,
                reminders=self.reminders,
            ),
            self.settings.data_dir,
        )
        executor = SecureExecutor(
            self.plugins, audit, self.confirm_action, self.permissions_repo,
            self.security_session.authorize,
        )
        self.workflows = WorkflowEngine(
            WorkflowRepository(database), executor, database, self.settings_repo
        )
        store = ConversationStore(self.settings.data_dir / "conversation.db")
        self.controller = AssistantController(
            executor, store, make_provider(self.settings, self.settings_repo), self.plugins, self.workflows, self.settings_repo
        )
        self.proactive = ProactiveScheduler(
            database, self.settings_repo, self.workflows, reminders=self.reminders
        )
        self.tray_icon = None
        self._closing = False
        self.speech_engine = SpeechEngine(
            rate=int(self.settings_repo.get("tts_rate", 178)),
            volume=float(self.settings_repo.get("tts_volume", 1.0)),
            voice_hint=str(self.settings_repo.get("tts_voice", "david")),
            engine=str(self.settings_repo.get("tts_engine", "edge")),
            edge_voice=str(self.settings_repo.get("edge_voice", DEFAULT_EDGE_VOICE)),
            piper_voice=str(self.settings_repo.get("piper_voice", DEFAULT_PIPER_VOICE)),
            models_dir=self.settings.project_root / "models",
        )
        self._streaming = False
        self._sentences = SentenceBuffer()
        self._pulse = 0.0
        self._state = "idle"
        self.mic_level = MicrophoneLevel(self._on_level)
        self.live_transcriber = LiveTranscriber.from_settings(
            self.settings_repo, self.settings.whisper_model
        )
        self.earcons = Earcons(bool(self.settings_repo.get('earcons_enabled', True)))
        self.hands_free = HandsFreeListener(
            self._listen_once,
            lambda text: self.root.after(0, lambda: self._submit_voice(text)),
            lambda state: self.root.after(0, lambda: self._voice_state(state)),
            self.speech_engine.activity,
            barge_in=bool(self.settings_repo.get("voice_barge_in", False)),
            on_interrupt=self.stop_speaking,
        )

        self._configure_window()
        self._build_ui()
        threading.Thread(target=self._worker, daemon=True, name="jarvis-actions").start()
        self.speech_engine.start()
        self.orb.start()
        self.mic_level.start()
        self._start_tray()
        self._start_emergency_hotkey()
        self._start_wake_word()
        if self.settings_repo.get("hands_free_enabled", True):
            self.root.after(900, self.hands_free.start)
        self.proactive.start()
        self.add_message("J.A.R.V.I.S", "Systems online. Type a message or press the microphone button.")
        if not self.settings_repo.get("first_run_complete", False):
            self.root.after(250, lambda: SetupWizard(
                self.root, self.settings_repo, self.settings.project_root, self.speech_engine
            ))
        threading.Thread(target=self._check_updates, daemon=True, name="jarvis-updates").start()
        threading.Thread(target=self._warm_model, daemon=True, name="jarvis-warmup").start()

    def _configure_window(self) -> None:
        self.root.title("J.A.R.V.I.S")
        # Fit the screen first. Preferring a large window over the available
        # space produced a window taller than the display on 1280x800 laptops,
        # which quietly cut off the input bar.
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = max(980, min(1520, screen_width - 80))
        height = max(640, min(960, screen_height - 90))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 3)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(min(980, screen_width - 40), min(640, screen_height - 60))
        self.root.configure(bg=Palette.BASE)
        minimize = self.settings_repo.get("minimize_to_tray", self.settings.minimize_to_tray)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window if minimize else self.exit_app)

    def _build_ui(self) -> None:
        self._build_header()
        body = tk.Frame(self.root, bg=Palette.BASE, padx=Space.LG, pady=Space.MD)
        body.pack(fill="both", expand=True)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        self._build_left_rail(body)
        self._build_center(body)
        self._build_right_rail(body)
        self._update_clock()
        self._animate()

    def _build_header(self) -> None:
        top = tk.Frame(self.root, bg=Palette.VOID, height=84, padx=Space.XL, pady=Space.SM)
        top.pack(fill="x")
        top.pack_propagate(False)

        brand = tk.Frame(top, bg=Palette.VOID)
        brand.pack(side="left", fill="y")
        mark = tk.Canvas(brand, width=34, height=34, bg=Palette.VOID, highlightthickness=0)
        mark.pack(side="left", padx=(0, Space.MD))
        mark.create_oval(3, 3, 31, 31, outline=Palette.ACCENT, width=2)
        mark.create_oval(10, 10, 24, 24, fill=Palette.ACCENT, outline="")
        words = tk.Frame(brand, bg=Palette.VOID)
        words.pack(side="left", fill="y")
        tk.Label(words, text="J.A.R.V.I.S", fg=Palette.TEXT, bg=Palette.VOID,
                 font=Type.BRAND).pack(anchor="w")
        tk.Label(words, text="MARK 7  ·  LOCAL FIRST", fg=Palette.TEXT_FAINT, bg=Palette.VOID,
                 font=Type.MONO_SMALL).pack(anchor="w")

        self.clock = tk.Label(top, fg=Palette.TEXT_MUTED, bg=Palette.VOID, font=Type.MONO)
        self.clock.pack(side="right", padx=(Space.LG, 0))
        for label, command in (("WORKFLOWS", self.open_workflows), ("SETTINGS", self.open_settings)):
            Button(top, label, command, style="quiet", height=32, width=104).pack(
                side="right", padx=Space.XS
            )
        self.status_chip = StatusChip(top)
        self.status_chip.pack(side="right", padx=(0, Space.MD))

    def _build_left_rail(self, body: tk.Frame) -> None:
        rail = tk.Frame(body, bg=Palette.BASE, width=252)
        rail.grid(row=0, column=0, sticky="nsew", padx=(0, Space.MD))
        rail.grid_propagate(False)

        voice = Card(rail, glow=Palette.ACCENT, padding=Space.MD)
        voice.pack(fill="x")
        tk.Label(voice.body, text="VOICE", bg=Palette.SURFACE, fg=Palette.TEXT_FAINT,
                 font=Type.MONO_SMALL).pack(anchor="w")
        self.voice_mode_label = tk.Label(voice.body, text="HANDS-FREE ON", bg=Palette.SURFACE,
                                         fg=Palette.SUCCESS, font=Type.LABEL)
        self.voice_mode_label.pack(anchor="w", pady=(Space.SM, Space.SM))
        self.level_meter = LevelMeter(voice.body, height=24)
        self.level_meter.pack(fill="x", pady=(0, Space.XS))
        self.mic_hint = tk.Label(voice.body, text="Waiting for microphone", bg=Palette.SURFACE,
                                 fg=Palette.TEXT_FAINT, font=Type.CAPTION, wraplength=200,
                                 justify="left")
        self.mic_hint.pack(anchor="w", pady=(0, Space.SM))
        self.voice_toggle = Button(voice.body, "PAUSE LISTENING", self.toggle_hands_free,
                                   style="ghost", height=36)
        self.voice_toggle.pack(fill="x", pady=(Space.XS, 0))

        system = Card(rail, padding=Space.MD)
        system.pack(fill="x", pady=(Space.MD, 0))
        tk.Label(system.body, text="SYSTEM", bg=Palette.SURFACE, fg=Palette.TEXT_FAINT,
                 font=Type.MONO_SMALL).pack(anchor="w", pady=(0, Space.SM))
        self.metrics = {}
        for key, label, value in (
            ("model", "LANGUAGE MODEL", str(self.settings_repo.get("ollama_model", "gemma2:2b"))),
            ("voice", "SPEECH ENGINE", str(self.settings_repo.get("tts_engine", "edge")).upper()),
            ("hearing", "RECOGNITION", str(self.settings_repo.get("whisper_model", "base")).upper()),
            ("privacy", "PRIVACY",
             "PRIVATE MODE" if self.settings_repo.get("privacy_mode", False) else "STANDARD"),
        ):
            row = MetricRow(system.body, label, value)
            row.pack(fill="x", pady=(0, Space.SM))
            self.metrics[key] = row

    def _build_center(self, body: tk.Frame) -> None:
        center = tk.Frame(body, bg=Palette.BASE)
        center.grid(row=0, column=1, sticky="nsew")
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)

        stage = Card(center, fill=Palette.SURFACE, padding=Space.MD)
        stage.grid(row=0, column=0, sticky="ew", pady=(0, Space.MD))
        inner = tk.Frame(stage.body, bg=Palette.SURFACE)
        inner.pack(pady=Space.SM)
        self.orb = VoiceOrb(inner, size=178, background=Palette.SURFACE)
        self.orb.pack()
        self.orb_caption = OrbCaption(inner)
        self.orb_caption.pack(pady=(Space.SM, Space.XS))

        conversation = Card(center, padding=0)
        conversation.grid(row=1, column=0, sticky="nsew")
        self.transcript = scrolledtext.ScrolledText(
            conversation.body, wrap="word", bg=Palette.SURFACE, fg=Palette.TEXT,
            insertbackground=Palette.ACCENT, selectbackground=Palette.ACCENT_DEEP,
            relief="flat", padx=Space.XL, pady=Space.LG, font=Type.BODY, state="disabled",
            highlightthickness=0, bd=0, spacing1=2, spacing3=4,
            # A text widget requests 80x24 characters by default, which would
            # crowd out the side rails and the input bar. Ask for very little
            # and let the grid weights hand it the space that is left.
            width=20, height=6,
        )
        self.transcript.pack(fill="both", expand=True, padx=2, pady=2)
        self.transcript.tag_configure("name_user", foreground=Palette.TEXT_MUTED,
                                      font=Type.MONO_SMALL, spacing1=Space.MD)
        self.transcript.tag_configure("name_jarvis", foreground=Palette.ACCENT,
                                      font=Type.MONO_SMALL, spacing1=Space.MD)
        self.transcript.tag_configure("body", foreground=Palette.TEXT, spacing3=Space.SM,
                                      lmargin1=2, lmargin2=2)
        self.transcript.tag_configure("detail", foreground=Palette.TEXT_MUTED,
                                      font=Type.CAPTION, lmargin1=Space.MD, lmargin2=Space.LG)
        self.transcript.tag_configure("system", foreground=Palette.TEXT_FAINT, font=Type.CAPTION)

        quick = tk.Frame(center, bg=Palette.BASE)
        quick.grid(row=2, column=0, sticky="ew", pady=(Space.MD, Space.SM))
        for label, value in (("RESEARCH", "Research "), ("WEATHER", "What's the weather"),
                             ("OPEN APP", "Open "), ("FIND FILE", "Find "),
                             ("READ SCREEN", "Read the screen")):
            Button(quick, label, lambda v=value: self._quick_prompt(v),
                   style="ghost", height=32, width=len(label) * 8 + 28).pack(
                side="left", padx=(0, Space.SM)
            )

        bar = Card(center, fill=Palette.SURFACE_INPUT, border=Palette.BORDER_BRIGHT,
                   padding=Space.SM, radius=12)
        bar.grid(row=3, column=0, sticky="ew")
        self.entry = tk.Entry(bar.body, bg=Palette.SURFACE_INPUT, fg=Palette.TEXT,
                              insertbackground=Palette.ACCENT, relief="flat",
                              font=Type.BODY, bd=0)
        self.entry.pack(side="left", fill="x", expand=True, ipady=10, padx=(Space.MD, Space.MD))
        self.entry.bind("<Return>", self.submit)
        self.entry.focus_set()
        self.root.bind("<Escape>", self.stop_speaking)
        Button(bar.body, "SEND", self.submit, style="primary", height=38, width=84).pack(
            side="right", padx=(Space.SM, 0)
        )
        Button(bar.body, "MIC", self.listen, style="ghost", height=38, width=68).pack(side="right")
        Button(bar.body, "STOP", self.stop_speaking, style="danger", height=38, width=68).pack(
            side="right", padx=(0, Space.SM)
        )

    def _build_right_rail(self, body: tk.Frame) -> None:
        rail = tk.Frame(body, bg=Palette.BASE, width=258)
        rail.grid(row=0, column=2, sticky="nsew", padx=(Space.MD, 0))
        rail.grid_propagate(False)

        capability = Card(rail, padding=Space.MD)
        capability.pack(fill="x")
        tk.Label(capability.body, text="CAPABILITIES", bg=Palette.SURFACE,
                 fg=Palette.TEXT_FAINT, font=Type.MONO_SMALL).pack(anchor="w", pady=(0, Space.SM))
        for title, subtitle, colour in (
            ("PC control", "Apps, files, windows", Palette.SUCCESS),
            ("Live research", "Cited web answers", Palette.ACCENT),
            ("Weather", "Free, no API key", Palette.ACCENT),
            ("Documents", "Local semantic search", Palette.VIOLET),
            ("Screen reading", "On-device OCR", Palette.WARNING),
        ):
            self._capability(capability.body, title, subtitle, colour)

        session = Card(rail, padding=Space.MD)
        session.pack(fill="x", pady=(Space.MD, 0))
        tk.Label(session.body, text="SESSION", bg=Palette.SURFACE, fg=Palette.TEXT_FAINT,
                 font=Type.MONO_SMALL).pack(anchor="w")
        self.session_detail = tk.Label(session.body, text="Awaiting your first request",
                                       justify="left", bg=Palette.SURFACE, fg=Palette.TEXT_SOFT,
                                       font=Type.CAPTION, wraplength=210)
        self.session_detail.pack(anchor="w", pady=(Space.SM, 0))

        shortcuts = Card(rail, padding=Space.MD)
        shortcuts.pack(fill="x", pady=(Space.MD, 0))
        tk.Label(shortcuts.body, text="SHORTCUTS", bg=Palette.SURFACE, fg=Palette.TEXT_FAINT,
                 font=Type.MONO_SMALL).pack(anchor="w", pady=(0, Space.SM))
        for keys, meaning in (("Hey Jarvis", "wake by voice"),
                              ("Ctrl+Alt+Space", "summon and listen"),
                              ("Esc", "stop speaking"),
                              ("Ctrl+Alt+J", "emergency stop")):
            row = tk.Frame(shortcuts.body, bg=Palette.SURFACE)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=keys, bg=Palette.SURFACE, fg=Palette.ACCENT,
                     font=Type.MONO_SMALL).pack(side="left")
            tk.Label(row, text=meaning, bg=Palette.SURFACE, fg=Palette.TEXT_FAINT,
                     font=Type.CAPTION).pack(side="right")

    @staticmethod
    def _capability(parent, title: str, subtitle: str, colour: str) -> None:
        row = tk.Frame(parent, bg=Palette.SURFACE)
        row.pack(fill="x", pady=3)
        dot = tk.Canvas(row, width=10, height=10, bg=Palette.SURFACE, highlightthickness=0)
        dot.pack(side="left", padx=(0, Space.SM), pady=(4, 0), anchor="n")
        dot.create_oval(2, 2, 8, 8, fill=colour, outline="")
        text = tk.Frame(row, bg=Palette.SURFACE)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=title, bg=Palette.SURFACE, fg=Palette.TEXT_SOFT,
                 font=Type.LABEL).pack(anchor="w")
        tk.Label(text, text=subtitle, bg=Palette.SURFACE, fg=Palette.TEXT_FAINT,
                 font=Type.CAPTION).pack(anchor="w")

    def _quick_prompt(self, value: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, value)
        self.entry.focus_set()
        if not value.endswith(" "):
            self.submit()

    def _update_clock(self) -> None:
        if self._closing:
            return
        self.clock.configure(text=datetime.now().strftime("%a %d %b  ·  %H:%M"))
        self.root.after(1000, self._update_clock)

    def _animate(self) -> None:
        """Drive the chip pulse. The orb runs its own loop at its own rate."""
        if self._closing:
            return
        self._pulse += 0.18
        self.status_chip.pulse(self._pulse)
        self._mic_ticks = getattr(self, "_mic_ticks", 0) + 1
        if self._mic_ticks % 12 == 0:
            self._refresh_mic_hint()
        self.root.after(90, self._animate)

    def _on_level(self, level: float) -> None:
        """Called from the microphone thread; hop to the UI thread to draw."""
        if self._closing:
            return
        try:
            self.root.after(0, lambda: self._apply_level(level))
        except (tk.TclError, RuntimeError):
            # The window closed between the check and the schedule.
            pass

    def _apply_level(self, level: float) -> None:
        if self._closing:
            return
        self.orb.set_level(level)
        self.level_meter.set_level(level)

    SESSION_NOTES = {
        "idle": "Ready. Ask anything, or say “Hey Jarvis”.",
        "listening": "Listening to you now.",
        "working": "Carrying out your request.",
        "thinking": "Working out an answer.",
        "speaking": "Replying. Press Escape to interrupt.",
        "paused": "Hands-free listening is paused.",
        "stopped": "Emergency stop. Pending work was cleared.",
        "error": "The last request did not complete.",
    }

    def set_state(self, state: str) -> None:
        """Single place that moves the orb, chip, and caption together."""
        self._state = state
        label, colour = state_style(state)
        self.status_chip.set_state(label, colour)
        self.orb.set_state(state)
        self.orb_caption.set_state(state)
        if hasattr(self, "session_detail"):
            self.session_detail.configure(
                text=self.SESSION_NOTES.get(state, label.title()), fg=colour
            )

    def set_status(self, text: str, color: str = Palette.ACCENT) -> None:
        self.set_state(text)

    def _write(self, text: str, tag: str) -> None:
        self.transcript.configure(state="normal")
        self.transcript.insert("end", text, tag)
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def begin_message(self, sender: str) -> None:
        self._write(f"{sender}\n", "name_user" if sender == "YOU" else "name_jarvis")

    def end_message(self, details: list[str] | None = None) -> None:
        self._write("\n", "body")
        if details:
            for item in details:
                self._write(f"• {item}\n", "detail")
            self._write("\n", "body")

    def add_message(self, sender: str, text: str, details: list[str] | None = None) -> None:
        self.begin_message(sender)
        self._write(text, "body")
        self.end_message(details)


    def stop_speaking(self, _event=None) -> str:
        """Cut off the reply in progress. Interrupting should always be possible."""
        self.speech_engine.silence()
        return "break"

    def submit(self, _event=None) -> str:
        text = self.entry.get().strip()
        if text:
            self.stop_speaking()
            self.entry.delete(0, "end")
            self.add_message("YOU", text)
            self.set_state("working")
            self.work.put((text, False))
            self.security_session.touch()
        return "break"

    def _on_wake(self) -> None:
        """Confirm the wake word landed before listening.

        Without this the assistant starts listening in silence, so you either
        repeat yourself or talk over the start of the capture.
        """
        self.log.info("Woken by wake word")
        self.earcons.play("wake")
        self.show_window()
        self.listen()

    def _make_voice_input(self) -> VoiceInput:
        return VoiceInput(VoiceConfig.from_settings(self.settings_repo, self.settings.whisper_model))

    def listen(self) -> None:
        self.stop_speaking()
        self.set_state("listening")
        if self.voice is None:
            self.voice = self._make_voice_input()
        threading.Thread(target=self._listen_worker, daemon=True, name="jarvis-microphone").start()

    def toggle_hands_free(self) -> None:
        if self.hands_free.enabled.is_set():
            self.hands_free.pause()
        else:
            self.hands_free.start()
        self._refresh_voice_controls()

    def _refresh_voice_controls(self) -> None:
        if not hasattr(self, "voice_toggle"):
            return
        active = self.hands_free.enabled.is_set()
        self.voice_toggle.set_text("PAUSE LISTENING" if active else "ENABLE LISTENING")
        self.voice_mode_label.configure(
            text="HANDS-FREE ON" if active else "HANDS-FREE PAUSED",
            fg=Palette.SUCCESS if active else Palette.TEXT_MUTED,
        )
        self._refresh_mic_hint()

    def _refresh_mic_hint(self) -> None:
        """Say plainly whether the microphone is working, rather than failing quietly."""
        if not hasattr(self, "mic_hint"):
            return
        if self.mic_level.available:
            text, colour = "Microphone live", Palette.TEXT_MUTED
        elif self.mic_level.error:
            text, colour = f"No microphone: {self.mic_level.error[:60]}", Palette.WARNING
        else:
            text, colour = "Waiting for microphone", Palette.TEXT_FAINT
        self.mic_hint.configure(text=text, fg=colour)

    def _on_partial(self, text: str) -> None:
        """Draft text from the recogniser, shown while you are still talking."""
        if not self._closing:
            try:
                self.root.after(0, lambda: self.orb_caption.set_live_text(text))
            except (tk.TclError, RuntimeError):
                pass

    def _refresh_transcriber(self) -> None:
        """Rebuild only when the settings behind it change.

        Constructing a LiveTranscriber discards its loaded models, and reloading
        both faster-whisper models cost 2.35s on every spoken request.
        """
        wanted = LiveTranscriber.from_settings(self.settings_repo, self.settings.whisper_model)
        current = self.live_transcriber
        if current is None or current.signature() != wanted.signature():
            self.live_transcriber = wanted
        else:
            current.apply(wanted)

    def _listen_once(self) -> str:
        with self._voice_lock:
            if self.settings_repo.get("live_transcription", True):
                self._refresh_transcriber()
                return self.live_transcriber.listen(self._on_partial)
            if self.voice is None:
                self.voice = self._make_voice_input()
            else:
                self.voice.config = VoiceConfig.from_settings(self.settings_repo, self.settings.whisper_model)
            return self.voice.listen()

    def _listen_worker(self) -> None:
        try:
            text = self._listen_once()
            if text:
                self.root.after(0, lambda: self._submit_voice(text))
            else:
                self.root.after(0, lambda: self.set_state("idle"))
        except Exception as exc:
            self.root.after(0, lambda: self._show_error(f"Microphone error: {exc}"))

    def _submit_voice(self, text: str) -> None:
        self.add_message("YOU", text)
        self.set_state("working")
        self.work.put((text, True))
        self.security_session.touch()

    def _worker(self) -> None:
        while (item := self.work.get()) is not None:
            try:
                text, spoken = item
                self._streaming = False
                self._sentences = SentenceBuffer()
                reply = self.controller.process(text, spoken=spoken, on_chunk=self._queue_chunk)
                self.root.after(0, lambda r=reply: self._deliver(r.text, r.details))
            except Exception as exc:
                failure("worker", exc)
                self.root.after(0, lambda e=exc: self._show_error(str(e)))

    def _speaks(self) -> bool:
        return bool(self.settings_repo.get("speak_responses", self.settings.speak_responses))

    def _match_voice_to_language(self) -> None:
        """Answer Swahili in a Swahili voice, English in the configured one."""
        language = getattr(self.controller, "last_language", "en")
        configured = str(self.settings_repo.get("edge_voice", DEFAULT_EDGE_VOICE))
        engine = self.speech_engine.engine_name
        self.speech_engine.use_voice(voice_for(language, engine, configured))
        if language == SWAHILI and engine == "piper":
            # No Swahili Piper voice exists, so fall back to the cloud voice
            # for this reply rather than reading Swahili with an English one.
            self.speech_engine.engine_name = "edge"
            self.speech_engine.use_voice(voice_for(language, "edge", configured))

    def _queue_chunk(self, chunk: str) -> None:
        """Called from the worker thread as model tokens arrive."""
        self.root.after(0, lambda: self._render_chunk(chunk))

    def _render_chunk(self, chunk: str) -> None:
        if not self._streaming:
            self._match_voice_to_language()
            self._streaming = True
            self.begin_message("J.A.R.V.I.S")
            self.set_state("speaking")
        self._write(chunk, "body")
        if self._speaks():
            for sentence in self._sentences.push(chunk):
                self.speech_engine.say(sentence)

    def _deliver(self, text: str, details: list[str] | None) -> None:
        if self._streaming:
            remainder = self._sentences.flush()
            if remainder and self._speaks():
                self.speech_engine.say(remainder)
            self.end_message(details)
            self._streaming = False
        else:
            self.add_message("J.A.R.V.I.S", text, details)
            if self._speaks():
                self._match_voice_to_language()
                self.speech_engine.say(text)
        self.set_state("idle")

    def _voice_state(self, state: str) -> None:
        self._refresh_voice_controls()
        if state == "listening":
            self.set_state("listening")
        elif state == "speaking":
            self.set_state("speaking")
        elif state == "paused":
            self.set_state("paused")
        elif state.startswith("error:"):
            self._show_error(f"Hands-free microphone {state}")

    def open_settings(self) -> None:
        SettingsWindow(
            self.root, self.settings_repo, self.permissions_repo, self.audit,
            self.settings.project_root, self.plugins, self.controller.store,
        )

    def open_workflows(self) -> None:
        WorkflowWindow(self.root, self.workflows)

    def confirm_action(self, command: Command) -> bool:
        answer: list[bool] = []
        complete = threading.Event()
        def ask() -> None:
            summary = "\n".join(f"{key}: {value}" for key, value in command.arguments.items())
            answer.append(messagebox.askyesno("Confirm J.A.R.V.I.S action", f"Allow {command.action}?\n\n{summary}"))
            complete.set()
        self.root.after(0, ask)
        complete.wait()
        return answer[0]

    def _show_error(self, message: str) -> None:
        self.log.error(message)
        self.earcons.play("error")
        self.add_message("J.A.R.V.I.S", message)
        self.set_state("error")

    def _start_tray(self) -> None:
        if not self.settings_repo.get("minimize_to_tray", self.settings.minimize_to_tray):
            return
        try:
            import pystray
            from PIL import Image
            image_path = self.settings.project_root / "GUI_images" / "Hacker.png"
            image = Image.open(image_path).convert("RGBA")
            menu = pystray.Menu(
                pystray.MenuItem("Open J.A.R.V.I.S", lambda: self.root.after(0, self.show_window), default=True),
                pystray.MenuItem("Exit", lambda: self.root.after(0, self.exit_app)),
            )
            self.tray_icon = pystray.Icon("jarvis", image, "J.A.R.V.I.S", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True, name="jarvis-tray").start()
        except Exception:
            self.tray_icon = None

    def _start_emergency_hotkey(self) -> None:
        try:
            from pynput.keyboard import GlobalHotKeys
            self.emergency_hotkey = GlobalHotKeys({
                "<ctrl>+<alt>+j": lambda: self.root.after(0, self.emergency_stop),
                # Summon: bring the window forward and start listening, which
                # is the fastest route in when the microphone is paused.
                "<ctrl>+<alt>+space": lambda: self.root.after(0, self.summon),
            })
            self.emergency_hotkey.start()
        except Exception:
            self.emergency_hotkey = None

    def _start_wake_word(self) -> None:
        import os
        self.wake_word = make_wake_word(
            lambda: self.root.after(0, self._on_wake),
            access_key=os.getenv("PORCUPINE_API_KEY", ""),
            backend=str(self.settings_repo.get("wake_word_backend", "openwakeword")),
            sensitivity=float(self.settings_repo.get("wake_word_sensitivity", 0.55)),
        )
        if self.settings_repo.get("wake_word_enabled", False):
            self.wake_word.start()

    def summon(self) -> None:
        """Bring J.A.R.V.I.S forward and listen, from anywhere."""
        self.log.info("Summoned by hotkey")
        self.show_window()
        self.earcons.play("wake")
        self.listen()

    def emergency_stop(self) -> None:
        self.workflows.cancel()
        self.speech_engine.silence()
        while True:
            try:
                self.work.get_nowait()
            except queue.Empty:
                break
        self.security_session.lock()
        self.add_message("J.A.R.V.I.S", "Emergency stop activated. Pending work was cleared and sensitive actions are locked.")
        self.set_state("stopped")

    def _warm_model(self) -> None:
        """Load the local model during startup so the first question is not slow."""
        self.speech_engine.warm()
        self.live_transcriber.warm()
        warm = getattr(self.controller.provider, "warm", None)
        if not callable(warm):
            return
        try:
            warm()
        except Exception as error:
            failure("model_warmup", error)

    def _check_updates(self) -> None:
        try:
            update = UpdateChecker().check(__version__)
            if update:
                self.proactive.notify(
                    "J.A.R.V.I.S update available", f"Version {update['version']} is available on GitHub.",
                    "normal", f"update:{update['version']}",
                )
        except Exception:
            pass

    def hide_window(self) -> None:
        if self.tray_icon:
            self.root.withdraw()
        else:
            self.exit_app()

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.entry.focus_set()

    def exit_app(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.work.put(None)
        self.hands_free.stop()
        self.orb.stop()
        self.mic_level.stop()
        self.speech_engine.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        if self.emergency_hotkey:
            self.emergency_hotkey.stop()
        self.wake_word.stop()
        self.proactive.stop()
        self.root.destroy()


def run() -> None:
    root = tk.Tk()
    JarvisApp(root)
    root.mainloop()
