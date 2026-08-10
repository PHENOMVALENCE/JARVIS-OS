"""Unified keyboard and voice desktop interface for J.A.R.V.I.S Mark 6."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
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


BG = "#070b12"
PANEL = "#0d1724"
ACCENT = "#36d7ff"
TEXT = "#e7f8ff"
MUTED = "#8aa7b5"
SUCCESS = "#63f5a5"


class JarvisApp:
    def __init__(self, root: tk.Tk, settings: Settings | None = None):
        self.root = root
        self.settings = settings or Settings()
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.work: queue.Queue[str | None] = queue.Queue()
        self.speech: queue.Queue[str | None] = queue.Queue()
        self.voice = VoiceInput(self.settings.whisper_model)
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
            executor, store, make_provider(self.settings), self.plugins, self.workflows
        )
        self.proactive = ProactiveScheduler(database, self.settings_repo, self.workflows)
        self.tray_icon = None
        self._closing = False

        self._configure_window()
        self._build_ui()
        threading.Thread(target=self._worker, daemon=True, name="jarvis-actions").start()
        threading.Thread(target=self._speaker, daemon=True, name="jarvis-speech").start()
        self._start_tray()
        self._start_emergency_hotkey()
        self.proactive.start()
        self.add_message("J.A.R.V.I.S", "Systems online. Type a message or press the microphone button.")
        if not self.settings_repo.get("first_run_complete", False):
            self.root.after(250, lambda: FirstRunWizard(self.root, self.settings_repo))
        threading.Thread(target=self._check_updates, daemon=True, name="jarvis-updates").start()

    def _configure_window(self) -> None:
        self.root.title("J.A.R.V.I.S — Mark 6")
        self.root.geometry("980x700")
        self.root.minsize(720, 520)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window if self.settings.minimize_to_tray else self.exit_app)

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=BG, padx=24, pady=18)
        header.pack(fill="x")
        tk.Label(header, text="J.A.R.V.I.S", fg=ACCENT, bg=BG, font=("Segoe UI Semibold", 22)).pack(side="left")
        self.status = tk.Label(header, text="● READY", fg=SUCCESS, bg=BG, font=("Segoe UI Semibold", 10))
        self.status.pack(side="right")
        tk.Button(
            header, text="SETTINGS", command=self.open_settings, bg=BG, fg=MUTED,
            activebackground=PANEL, activeforeground=TEXT, relief="flat", cursor="hand2",
        ).pack(side="right", padx=(0, 18))
        tk.Button(
            header, text="WORKFLOWS", command=self.open_workflows, bg=BG, fg=MUTED,
            activebackground=PANEL, activeforeground=TEXT, relief="flat", cursor="hand2",
        ).pack(side="right", padx=(0, 8))

        self.transcript = scrolledtext.ScrolledText(
            self.root, wrap="word", bg=PANEL, fg=TEXT, insertbackground=TEXT,
            relief="flat", padx=22, pady=18, font=("Segoe UI", 11), state="disabled",
        )
        self.transcript.pack(fill="both", expand=True, padx=24, pady=(0, 14))
        self.transcript.tag_configure("name_user", foreground=MUTED, font=("Segoe UI Semibold", 9))
        self.transcript.tag_configure("name_jarvis", foreground=ACCENT, font=("Segoe UI Semibold", 9))
        self.transcript.tag_configure("body", foreground=TEXT, spacing3=14)
        self.transcript.tag_configure("detail", foreground=MUTED, lmargin1=18, lmargin2=18)

        input_panel = tk.Frame(self.root, bg=BG, padx=24, pady=0)
        input_panel.pack(fill="x", pady=(0, 22))
        self.entry = tk.Entry(
            input_panel, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
            font=("Segoe UI", 12), bd=0,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=13, padx=(0, 10))
        self.entry.bind("<Return>", self.submit)
        self.entry.focus_set()
        tk.Button(
            input_panel, text="MIC", command=self.listen, bg="#183149", fg=ACCENT,
            activebackground="#244866", activeforeground=TEXT, relief="flat",
            font=("Segoe UI Semibold", 10), padx=18, pady=12, cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            input_panel, text="SEND", command=self.submit, bg=ACCENT, fg=BG,
            activebackground="#7ce7ff", relief="flat", font=("Segoe UI Semibold", 10),
            padx=20, pady=12, cursor="hand2",
        ).pack(side="left")

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
        threading.Thread(target=self._listen_worker, daemon=True, name="jarvis-microphone").start()

    def _listen_worker(self) -> None:
        try:
            text = self.voice.listen()
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
            self.speech.put(text)

    def open_settings(self) -> None:
        SettingsWindow(
            self.root, self.settings_repo, self.permissions_repo, self.audit,
            self.settings.project_root, self.plugins,
        )

    def open_workflows(self) -> None:
        WorkflowWindow(self.root, self.workflows)

    def _speaker(self) -> None:
        engine = None
        while (text := self.speech.get()) is not None:
            try:
                if engine is None:
                    import pyttsx3
                    engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except Exception:
                engine = None

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
        if not self.settings.minimize_to_tray:
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
        self.speech.put(None)
        if self.tray_icon:
            self.tray_icon.stop()
        if self.emergency_hotkey:
            self.emergency_hotkey.stop()
        self.proactive.stop()
        self.root.destroy()


def run() -> None:
    root = tk.Tk()
    JarvisApp(root)
    root.mainloop()
