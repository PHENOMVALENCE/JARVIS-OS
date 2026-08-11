"""Unified keyboard and voice desktop interface for J.A.R.V.I.S Mark 6."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import math
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, scrolledtext

from .actions import WindowsActions
from .assistant import AssistantController, ConversationStore, VoiceInput, make_provider
from .commands import Command
from .security import AuditLog, SecureExecutor
from .plugins import PluginManager
from .settings import Settings
from .settings_ui import SettingsWindow
from .storage import Database, PermissionRepository, SettingsRepository
from .workflows import WorkflowEngine, WorkflowRepository
from .workflow_ui import WorkflowWindow
from .knowledge import KnowledgeIndex
from .proactive import ProactiveScheduler
from .user_presence import SecuritySession
from .setup_ui import FirstRunWizard
from .updates import UpdateChecker
from . import __version__
from .wake_word import WakeWordListener
from .speech import HandsFreeListener, SpeechEngine


BG = "#070b12"
PANEL = "#0b1421"
PANEL_2 = "#101d2d"
ACCENT = "#36d7ff"
ACCENT_2 = "#806bff"
TEXT = "#e7f8ff"
MUTED = "#8aa7b5"
SUCCESS = "#63f5a5"
WARNING = "#ffbf69"


class JarvisApp:
    def __init__(self, root: tk.Tk, settings: Settings | None = None):
        self.root = root
        self.settings = settings or Settings()
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.work: queue.Queue[str | None] = queue.Queue()
        self.voice = None
        self._voice_lock = threading.Lock()
        database = Database(self.settings.data_dir / "jarvis.db")
        self.settings_repo = SettingsRepository(database)
        self.permissions_repo = PermissionRepository(database)
        audit = AuditLog(self.settings.data_dir / "jarvis.db")
        self.audit = audit
        self.security_session = SecuritySession(
            timeout_minutes=int(self.settings_repo.get("security_timeout_minutes", 15)),
            always_verify=bool(self.settings_repo.get("hello_for_high_risk", False)),
        )
        self.knowledge = KnowledgeIndex(database, self.settings_repo)
        self.plugins = PluginManager(
            self.settings.project_root / "plugins", database,
            WindowsActions(
                data_dir=self.settings.data_dir, settings_repo=self.settings_repo,
                openai_api_key=self.settings.openai_api_key, knowledge=self.knowledge,
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
        self.proactive = ProactiveScheduler(database, self.settings_repo, self.workflows)
        self.tray_icon = None
        self._closing = False
        self.speech_engine = SpeechEngine(
            rate=int(self.settings_repo.get("tts_rate", 178)),
            volume=float(self.settings_repo.get("tts_volume", 1.0)),
            voice_hint=str(self.settings_repo.get("tts_voice", "david")),
        )
        self.hands_free = HandsFreeListener(
            self._listen_once,
            lambda text: self.root.after(0, lambda: self._submit_voice(text)),
            lambda state: self.root.after(0, lambda: self._voice_state(state)),
            self.speech_engine.speaking,
        )

        self._configure_window()
        self._build_ui()
        threading.Thread(target=self._worker, daemon=True, name="jarvis-actions").start()
        self.speech_engine.start()
        self._start_tray()
        self._start_emergency_hotkey()
        self._start_wake_word()
        if self.settings_repo.get("hands_free_enabled", True):
            self.root.after(900, self.hands_free.start)
        self.proactive.start()
        self.add_message("J.A.R.V.I.S", "Systems online. Type a message or press the microphone button.")
        if not self.settings_repo.get("first_run_complete", False):
            self.root.after(250, lambda: FirstRunWizard(self.root, self.settings_repo))
        threading.Thread(target=self._check_updates, daemon=True, name="jarvis-updates").start()

    def _configure_window(self) -> None:
        self.root.title("J.A.R.V.I.S — Mark 7 Command Center")
        width = min(1480, max(1180, self.root.winfo_screenwidth() - 160))
        height = min(940, max(760, self.root.winfo_screenheight() - 120))
        self.root.geometry(f"{width}x{height}+60+40")
        self.root.minsize(1040, 680)
        self.root.configure(bg=BG)
        minimize = self.settings_repo.get("minimize_to_tray", self.settings.minimize_to_tray)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window if minimize else self.exit_app)

    def _build_ui(self) -> None:
        top = tk.Frame(self.root, bg="#080e18", height=74, padx=28, pady=14)
        top.pack(fill="x")
        top.pack_propagate(False)
        brand = tk.Frame(top, bg="#080e18")
        brand.pack(side="left", fill="y")
        tk.Label(brand, text="J.A.R.V.I.S", fg=ACCENT, bg="#080e18", font=("Segoe UI Semibold", 24)).pack(anchor="w")
        tk.Label(brand, text="JUST A RATHER VERY INTELLIGENT SYSTEM  /  MARK 7", fg=MUTED, bg="#080e18", font=("Consolas", 8)).pack(anchor="w")
        self.clock = tk.Label(top, fg=MUTED, bg="#080e18", font=("Consolas", 10))
        self.clock.pack(side="right", padx=(24, 0))
        self.status = tk.Label(top, text="● READY", fg=SUCCESS, bg="#080e18", font=("Segoe UI Semibold", 10), padx=14)
        self.status.pack(side="right")
        for label, command in (("SETTINGS", self.open_settings), ("WORKFLOWS", self.open_workflows)):
            tk.Button(top, text=label, command=command, bg="#080e18", fg=MUTED,
                      activebackground=PANEL_2, activeforeground=TEXT, relief="flat",
                      font=("Segoe UI Semibold", 9), cursor="hand2", padx=12).pack(side="right", padx=3)

        body = tk.Frame(self.root, bg=BG, padx=18, pady=16)
        body.pack(fill="both", expand=True)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        left = tk.Frame(body, bg=PANEL, width=224, padx=16, pady=16, highlightthickness=1, highlightbackground="#172a3d")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_propagate(False)
        tk.Label(left, text="VOICE CORE", bg=PANEL, fg=MUTED, font=("Consolas", 9)).pack(anchor="w")
        self.orb = tk.Canvas(left, width=190, height=190, bg=PANEL, highlightthickness=0)
        self.orb.pack(pady=(15, 8))
        self._orb_phase = 0.0
        self.voice_mode_label = tk.Label(left, text="HANDS-FREE ONLINE", bg=PANEL, fg=SUCCESS, font=("Segoe UI Semibold", 10))
        self.voice_mode_label.pack()
        self.voice_toggle = tk.Button(left, text="PAUSE LISTENING", command=self.toggle_hands_free,
                                      bg="#15334a", fg=ACCENT, activebackground="#204963",
                                      activeforeground=TEXT, relief="flat", cursor="hand2",
                                      font=("Segoe UI Semibold", 9), pady=9)
        self.voice_toggle.pack(fill="x", pady=(10, 18))
        self._metric(left, "VOICE ENGINE", str(self.settings_repo.get("whisper_model", "base")).upper())
        self._metric(left, "LANGUAGE MODEL", str(self.settings_repo.get("ollama_model", "gemma2:2b")))
        self._metric(left, "SECURITY", "PERMISSION GATED")
        self._metric(left, "PRIVACY", "ACTIVE" if self.settings_repo.get("privacy_mode", False) else "STANDARD")

        center = tk.Frame(body, bg=BG)
        center.grid(row=0, column=1, sticky="nsew")
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)
        section = tk.Frame(center, bg=BG)
        section.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(section, text="CONVERSATION STREAM", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(side="left")
        tk.Label(section, text="LOCAL-FIRST • LIVE CONTROL • SOURCE-GROUNDED", bg=BG, fg=MUTED, font=("Consolas", 8)).pack(side="right")
        self.transcript = scrolledtext.ScrolledText(
            center, wrap="word", bg=PANEL, fg=TEXT, insertbackground=TEXT, selectbackground="#214860",
            relief="flat", padx=24, pady=20, font=("Segoe UI", 11), state="disabled",
            highlightthickness=1, highlightbackground="#172a3d",
        )
        self.transcript.grid(row=1, column=0, sticky="nsew")
        self.transcript.tag_configure("name_user", foreground="#b5c5d1", font=("Segoe UI Semibold", 9), spacing1=8)
        self.transcript.tag_configure("name_jarvis", foreground=ACCENT, font=("Segoe UI Semibold", 9), spacing1=8)
        self.transcript.tag_configure("body", foreground=TEXT, spacing3=12, lmargin1=4, lmargin2=4)
        self.transcript.tag_configure("detail", foreground=MUTED, lmargin1=18, lmargin2=18, spacing3=3)

        quick = tk.Frame(center, bg=BG, pady=9)
        quick.grid(row=2, column=0, sticky="ew")
        for label, command in (("WEB RESEARCH", "Research "), ("OPEN APP", "Open "),
                               ("FIND FILE", "Find file "), ("WORK MODE", "Start work mode")):
            tk.Button(quick, text=label, command=lambda value=command: self._quick_prompt(value),
                      bg=PANEL_2, fg=MUTED, activebackground="#1b3046", activeforeground=TEXT,
                      relief="flat", font=("Consolas", 8), padx=10, pady=6, cursor="hand2").pack(side="left", padx=(0, 7))

        input_panel = tk.Frame(center, bg=PANEL_2, padx=12, pady=10, highlightthickness=1, highlightbackground="#23415a")
        input_panel.grid(row=3, column=0, sticky="ew")
        self.entry = tk.Entry(
            input_panel, bg=PANEL_2, fg=TEXT, insertbackground=ACCENT, relief="flat",
            font=("Segoe UI", 12), bd=0,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=9, padx=(5, 10))
        self.entry.bind("<Return>", self.submit)
        self.entry.focus_set()
        tk.Button(
            input_panel, text="MIC", command=self.listen, bg="#183149", fg=ACCENT,
            activebackground="#244866", activeforeground=TEXT, relief="flat",
            font=("Segoe UI Semibold", 9), padx=15, pady=9, cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            input_panel, text="SEND", command=self.submit, bg=ACCENT, fg=BG,
            activebackground="#7ce7ff", relief="flat", font=("Segoe UI Semibold", 9),
            padx=18, pady=9, cursor="hand2",
        ).pack(side="left")

        right = tk.Frame(body, bg=PANEL, width=244, padx=16, pady=16, highlightthickness=1, highlightbackground="#172a3d")
        right.grid(row=0, column=2, sticky="nsew", padx=(12, 0))
        right.grid_propagate(False)
        tk.Label(right, text="CAPABILITY MATRIX", bg=PANEL, fg=MUTED, font=("Consolas", 9)).pack(anchor="w", pady=(0, 12))
        for title, subtitle, color in (
            ("PC CONTROL", "Apps • files • windows", SUCCESS),
            ("LIVE RESEARCH", "Web sources • answers", ACCENT),
            ("LOCAL KNOWLEDGE", "Documents • citations", ACCENT_2),
            ("AUTOMATION", "Workflows • schedules", WARNING),
            ("VISION", "Screen-aware assistance", "#ff83b6"),
        ):
            self._capability(right, title, subtitle, color)
        tk.Frame(right, bg="#1b3146", height=1).pack(fill="x", pady=14)
        tk.Label(right, text="ACTIVE SESSION", bg=PANEL, fg=MUTED, font=("Consolas", 9)).pack(anchor="w")
        self.session_detail = tk.Label(right, text="Awaiting command\nVoice channel initializing", justify="left",
                                       bg=PANEL, fg=TEXT, font=("Segoe UI", 9), wraplength=205)
        self.session_detail.pack(anchor="w", pady=(8, 0))
        tk.Label(right, text="Emergency stop\nCTRL + ALT + J", justify="left", bg=PANEL, fg="#ff7185",
                 font=("Consolas", 9)).pack(anchor="w", side="bottom")

        self._update_clock()
        self._animate_orb()

    @staticmethod
    def _metric(parent, title: str, value: str) -> None:
        panel = tk.Frame(parent, bg=PANEL_2, padx=10, pady=8)
        panel.pack(fill="x", pady=4)
        tk.Label(panel, text=title, bg=PANEL_2, fg=MUTED, font=("Consolas", 7)).pack(anchor="w")
        tk.Label(panel, text=value, bg=PANEL_2, fg=TEXT, font=("Segoe UI Semibold", 8), wraplength=170).pack(anchor="w")

    @staticmethod
    def _capability(parent, title: str, subtitle: str, color: str) -> None:
        panel = tk.Frame(parent, bg=PANEL_2, padx=10, pady=9)
        panel.pack(fill="x", pady=4)
        tk.Label(panel, text="●", bg=PANEL_2, fg=color, font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        labels = tk.Frame(panel, bg=PANEL_2)
        labels.pack(side="left")
        tk.Label(labels, text=title, bg=PANEL_2, fg=TEXT, font=("Segoe UI Semibold", 8)).pack(anchor="w")
        tk.Label(labels, text=subtitle, bg=PANEL_2, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")

    def _quick_prompt(self, value: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, value)
        self.entry.focus_set()
        if value == "Start work mode":
            self.submit()

    def _update_clock(self) -> None:
        if self._closing:
            return
        self.clock.configure(text=datetime.now().strftime("%A  %H:%M:%S"))
        self.root.after(1000, self._update_clock)

    def _animate_orb(self) -> None:
        if self._closing:
            return
        self.orb.delete("all")
        self._orb_phase += 0.10
        active = self.hands_free.enabled.is_set()
        color = ACCENT if active else "#466477"
        cx = cy = 95
        for index in range(4):
            pulse = math.sin(self._orb_phase + index * 0.8) * 4
            radius = 70 - index * 13 + pulse
            self.orb.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                                 outline=color if index < 2 else ACCENT_2, width=2)
        points = []
        for index in range(48):
            angle = index * math.tau / 48
            radius = 38 + math.sin(self._orb_phase * 2 + index * 0.75) * (7 if active else 2)
            points.extend((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
        self.orb.create_polygon(points, outline=color, fill="#0d2233", smooth=True, width=2)
        self.orb.create_text(cx, cy, text="J7", fill=TEXT, font=("Consolas", 18, "bold"))
        self.root.after(70, self._animate_orb)

    def add_message(self, sender: str, text: str, details: list[str] | None = None) -> None:
        self.transcript.configure(state="normal")
        tag = "name_user" if sender == "YOU" else "name_jarvis"
        self.transcript.insert("end", f"{sender}\n", tag)
        self.transcript.insert("end", f"{text}\n", "body")
        if details:
            for item in details:
                self.transcript.insert("end", f"• {item}\n", "detail")
            self.transcript.insert("end", "\n")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def set_status(self, text: str, color: str = ACCENT) -> None:
        self.status.configure(text=f"● {text.upper()}", fg=color)
        if hasattr(self, "session_detail"):
            self.session_detail.configure(text=f"{text.title()}\nSecure session active")

    def submit(self, _event=None) -> str:
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, "end")
            self.add_message("YOU", text)
            self.set_status("working")
            self.work.put(text)
            self.security_session.touch()
        return "break"

    def listen(self) -> None:
        self.set_status("listening")
        if self.voice is None:
            self.voice = VoiceInput(self.settings_repo.get("whisper_model", self.settings.whisper_model))
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
        self.voice_toggle.configure(text="PAUSE LISTENING" if active else "ENABLE LISTENING")
        self.voice_mode_label.configure(
            text="HANDS-FREE ONLINE" if active else "VOICE CHANNEL PAUSED",
            fg=SUCCESS if active else MUTED,
        )

    def _listen_once(self) -> str:
        with self._voice_lock:
            if self.voice is None:
                self.voice = VoiceInput(self.settings_repo.get("whisper_model", self.settings.whisper_model))
            return self.voice.listen()

    def _listen_worker(self) -> None:
        try:
            text = self._listen_once()
            if text:
                self.root.after(0, lambda: self._submit_voice(text))
            else:
                self.root.after(0, lambda: self.set_status("no speech", MUTED))
        except Exception as exc:
            self.root.after(0, lambda: self._show_error(f"Microphone error: {exc}"))

    def _submit_voice(self, text: str) -> None:
        self.add_message("YOU", text)
        self.set_status("working")
        self.work.put(text)
        self.security_session.touch()

    def _worker(self) -> None:
        while (text := self.work.get()) is not None:
            try:
                reply = self.controller.process(text)
                self.root.after(0, lambda r=reply: self._deliver(r.text, r.details))
            except Exception as exc:
                self.root.after(0, lambda e=exc: self._show_error(str(e)))

    def _deliver(self, text: str, details: list[str] | None) -> None:
        self.add_message("J.A.R.V.I.S", text, details)
        self.set_status("ready", SUCCESS)
        if self.settings_repo.get("speak_responses", self.settings.speak_responses):
            self.speech_engine.say(text)

    def _voice_state(self, state: str) -> None:
        self._refresh_voice_controls()
        if state == "listening":
            self.set_status("listening", ACCENT)
        elif state == "speaking":
            self.set_status("speaking", "#b78cff")
        elif state == "paused":
            self.set_status("voice paused", MUTED)
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
        self.add_message("J.A.R.V.I.S", message)
        self.set_status("error", "#ff6b7a")

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
            self.emergency_hotkey = GlobalHotKeys({"<ctrl>+<alt>+j": lambda: self.root.after(0, self.emergency_stop)})
            self.emergency_hotkey.start()
        except Exception:
            self.emergency_hotkey = None

    def _start_wake_word(self) -> None:
        import os
        self.wake_word = WakeWordListener(
            os.getenv("PORCUPINE_API_KEY", ""), lambda: self.root.after(0, self.listen)
        )
        if self.settings_repo.get("wake_word_enabled", False):
            self.wake_word.start()

    def emergency_stop(self) -> None:
        self.workflows.cancel()
        while True:
            try:
                self.work.get_nowait()
            except queue.Empty:
                break
        self.security_session.lock()
        self.add_message("J.A.R.V.I.S", "Emergency stop activated. Pending work was cleared and sensitive actions are locked.")
        self.set_status("stopped", "#ff6b7a")

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
