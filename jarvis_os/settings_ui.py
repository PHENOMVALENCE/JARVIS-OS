"""Settings, permissions, and audit-history interface."""

from __future__ import annotations

import subprocess
import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .security import AuditLog
from .storage import PermissionRepository, SettingsRepository


ACTIONS = (
    "open_app", "open_folder", "find_files", "web_search", "spotify_play",
    "media", "set_volume", "copy_clipboard", "focus_window", "window_state",
    "screenshot", "analyze_screen", "read_clipboard", "notification", "work_mode", "type_text",
    "close_app", "delete_path", "index_documents", "semantic_search",
    "install_package", "upgrade_package",
)


class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, settings: SettingsRepository, permissions: PermissionRepository, audit: AuditLog, project_root, plugins=None, conversation_store=None):
        super().__init__(parent)
        self.settings_repo = settings
        self.permissions_repo = permissions
        self.audit = audit
        self.project_root = project_root
        self.plugins = plugins
        self.conversation_store = conversation_store
        self.title("J.A.R.V.I.S Settings")
        self.geometry("820x780")
        self.minsize(650, 500)
        self.transient(parent)
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self._build_general()
        self._build_permissions()
        self._build_plugins()
        self._build_audit()
        self._build_data_tools()
        ttk.Button(self, text="Save", command=self.save).pack(pady=(0, 12))

    def _build_general(self):
        frame = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(frame, text="General")
        values = self.settings_repo.all()
        self.speak = tk.BooleanVar(value=values["speak_responses"])
        self.tray = tk.BooleanVar(value=values["minimize_to_tray"])
        self.startup = tk.BooleanVar(value=values["startup_enabled"])
        self.memory = tk.BooleanVar(value=values["conversation_memory"])
        self.privacy = tk.BooleanVar(value=values["privacy_mode"])
        self.proactive = tk.BooleanVar(value=values.get("proactive_enabled", True))
        self.hello = tk.BooleanVar(value=values.get("hello_for_high_risk", False))
        self.wake_word = tk.BooleanVar(value=values.get("wake_word_enabled", False))
        self.hands_free = tk.BooleanVar(value=values.get("hands_free_enabled", True))
        for text, variable in (
            ("Speak responses", self.speak), ("Minimize to system tray", self.tray),
            ("Start at Windows sign-in", self.startup), ("Store conversation memory", self.memory),
            ("Privacy mode (blocks capture and cloud features)", self.privacy),
            ("Proactive reminders and system health alerts", self.proactive),
            ("Require Windows Hello for high-risk actions", self.hello),
            ("Listen for the 'Jarvis' wake word (requires PORCUPINE_API_KEY)", self.wake_word),
            ("Hands-free conversation (continuously listen when not speaking)", self.hands_free),
        ):
            ttk.Checkbutton(frame, text=text, variable=variable).pack(anchor="w", pady=5)
        ttk.Label(frame, text="Ollama model").pack(anchor="w", pady=(16, 2))
        self.model = ttk.Entry(frame)
        self.model.insert(0, values["ollama_model"])
        self.model.pack(fill="x")
        ttk.Label(frame, text="Whisper model").pack(anchor="w", pady=(12, 2))
        self.whisper = ttk.Combobox(frame, values=("tiny", "base", "small", "medium", "large"), state="readonly")
        self.whisper.set(values["whisper_model"])
        self.whisper.pack(fill="x")
        ttk.Label(frame, text="Speech voice hint (for example: David or Mark)").pack(anchor="w", pady=(12, 2))
        self.tts_voice = ttk.Entry(frame)
        self.tts_voice.insert(0, values.get("tts_voice", "david"))
        self.tts_voice.pack(fill="x")
        ttk.Label(frame, text="Speech rate (words per minute)").pack(anchor="w", pady=(12, 2))
        self.tts_rate = ttk.Spinbox(frame, from_=100, to=260)
        self.tts_rate.set(values.get("tts_rate", 178)); self.tts_rate.pack(fill="x")
        ttk.Label(frame, text="Work mode apps (comma separated)").pack(anchor="w", pady=(12, 2))
        self.work_apps = ttk.Entry(frame)
        self.work_apps.insert(0, ", ".join(values["work_apps"]))
        self.work_apps.pack(fill="x")
        ttk.Label(frame, text="Indexed folders (one absolute path per line)").pack(anchor="w", pady=(12, 2))
        self.indexed_folders = tk.Text(frame, height=4, wrap="none")
        self.indexed_folders.insert("1.0", "\n".join(values.get("indexed_folders", [])))
        self.indexed_folders.pack(fill="x")
        ttk.Label(frame, text="Local embedding model").pack(anchor="w", pady=(12, 2))
        self.embedding_model = ttk.Entry(frame)
        self.embedding_model.insert(0, values.get("embedding_model", "nomic-embed-text"))
        self.embedding_model.pack(fill="x")
        ttk.Label(frame, text="Quiet hours (start and end, HH:MM)").pack(anchor="w", pady=(12, 2))
        quiet = ttk.Frame(frame); quiet.pack(fill="x")
        self.quiet_start = ttk.Entry(quiet, width=10); self.quiet_start.insert(0, values.get("quiet_hours_start", "22:00")); self.quiet_start.pack(side="left")
        ttk.Label(quiet, text=" to ").pack(side="left")
        self.quiet_end = ttk.Entry(quiet, width=10); self.quiet_end.insert(0, values.get("quiet_hours_end", "07:00")); self.quiet_end.pack(side="left")
        ttk.Label(frame, text="Security inactivity timeout (minutes)").pack(anchor="w", pady=(12, 2))
        self.security_timeout = ttk.Spinbox(frame, from_=1, to=240)
        self.security_timeout.set(values.get("security_timeout_minutes", 15)); self.security_timeout.pack(fill="x")

    def _build_permissions(self):
        frame = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(frame, text="Permissions")
        ttk.Label(frame, text="Choose whether each local capability runs, asks first, or is blocked.").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )
        configured = self.permissions_repo.all()
        self.permission_vars = {}
        actions = list(ACTIONS)
        if self.plugins:
            for loaded in self.plugins.plugins.values():
                actions.extend(name for name in loaded.manifest.actions if name not in actions)
        for row, action in enumerate(actions, start=1):
            default = "ask" if action in {"type_text", "close_app", "delete_path"} else "allow"
            ttk.Label(frame, text=action.replace("_", " ").title()).grid(row=row, column=0, sticky="w", pady=3)
            variable = tk.StringVar(value=configured.get(action, default))
            ttk.Combobox(frame, textvariable=variable, values=("allow", "ask", "deny"), state="readonly", width=12).grid(
                row=row, column=1, sticky="e", padx=(30, 0)
            )
            self.permission_vars[action] = variable

    def _build_audit(self):
        frame = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(frame, text="Audit history")
        text = scrolledtext.ScrolledText(frame, wrap="word", state="normal", font=("Consolas", 9))
        text.pack(fill="both", expand=True)
        for item in self.audit.recent(100):
            status = "OK" if item["success"] else "BLOCKED/FAILED"
            text.insert("end", f'{item["created_at"]}  {status:14} {item["action"]}\n  {item["message"]}\n\n')
        text.configure(state="disabled")
        integrity = "Verified" if self.audit.verify() else "WARNING: audit chain verification failed"
        ttk.Label(frame, text=f"Audit integrity: {integrity}").pack(anchor="w", pady=(8, 0))
        if self.conversation_store:
            ttk.Button(frame, text="Clear conversation memory", command=self._clear_memory).pack(anchor="e", pady=(8, 0))

    def _build_plugins(self):
        frame = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(frame, text="Plugins")
        self.plugin_vars = {}
        if not self.plugins:
            ttk.Label(frame, text="Plugin service is unavailable.").pack(anchor="w")
            return
        for item in self.plugins.status():
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=6)
            variable = tk.BooleanVar(value=item["enabled"])
            ttk.Checkbutton(row, text=f'{item["name"]}  v{item["version"]}', variable=variable).pack(side="left")
            status = item["error"] or ("Network access" if item["network"] else "Local only")
            ttk.Label(row, text=status).pack(side="right")
            self.plugin_vars[item["id"]] = variable

    def _build_data_tools(self):
        frame = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(frame, text="Data")
        ttk.Label(frame, text="Settings exports never include passwords, API keys, or integration tokens.", wraplength=620).pack(anchor="w", pady=(0, 16))
        ttk.Button(frame, text="Export settings", command=self._export_settings).pack(anchor="w", pady=4)
        ttk.Button(frame, text="Import settings", command=self._import_settings).pack(anchor="w", pady=4)
        ttk.Separator(frame).pack(fill="x", pady=16)
        ttk.Button(frame, text="Back up local J.A.R.V.I.S data", command=self._backup).pack(anchor="w", pady=4)
        ttk.Button(frame, text="Restore local data backup", command=self._restore).pack(anchor="w", pady=4)

    def save(self):
        before_startup = bool(self.settings_repo.get("startup_enabled"))
        values = {
            "speak_responses": self.speak.get(), "minimize_to_tray": self.tray.get(),
            "startup_enabled": self.startup.get(), "conversation_memory": self.memory.get(),
            "privacy_mode": self.privacy.get(), "ollama_model": self.model.get().strip() or "gemma2:2b",
            "whisper_model": self.whisper.get(),
            "work_apps": [item.strip() for item in self.work_apps.get().split(",") if item.strip()],
            "indexed_folders": [item.strip() for item in self.indexed_folders.get("1.0", "end").splitlines() if item.strip()],
            "embedding_model": self.embedding_model.get().strip() or "nomic-embed-text",
            "proactive_enabled": self.proactive.get(),
            "quiet_hours_start": self.quiet_start.get().strip(), "quiet_hours_end": self.quiet_end.get().strip(),
            "hello_for_high_risk": self.hello.get(), "security_timeout_minutes": int(self.security_timeout.get()),
            "wake_word_enabled": self.wake_word.get(),
            "hands_free_enabled": self.hands_free.get(),
            "tts_voice": self.tts_voice.get().strip() or "david",
            "tts_rate": int(self.tts_rate.get()),
        }
        for key, value in values.items():
            self.settings_repo.set(key, value)
        for action, variable in self.permission_vars.items():
            self.permissions_repo.set(action, variable.get())
        if self.plugins:
            current = {item["id"]: item["enabled"] for item in self.plugins.status()}
            for plugin_id, variable in self.plugin_vars.items():
                if current.get(plugin_id) != variable.get():
                    self.plugins.set_enabled(plugin_id, variable.get())
        if before_startup != self.startup.get():
            script = "Install-Startup.ps1" if self.startup.get() else "Remove-Startup.ps1"
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.project_root / script)],
                capture_output=True, text=True,
            )
            if completed.returncode:
                messagebox.showerror("Startup setting", completed.stderr.strip() or "Could not update startup task.", parent=self)
                return
        messagebox.showinfo("Settings", "Settings saved. Model and microphone changes apply after restart.", parent=self)
        self.destroy()

    def _clear_memory(self):
        if messagebox.askyesno("Clear memory", "Permanently clear stored conversation history?", parent=self):
            self.conversation_store.clear()
            messagebox.showinfo("Memory", "Conversation history cleared.", parent=self)

    def _export_settings(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            Path(path).write_text(json.dumps(self.settings_repo.export_safe(), indent=2), encoding="utf-8")

    def _import_settings(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            values = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(values, dict):
                raise ValueError("Settings file must contain a JSON object.")
            allowed = set(self.settings_repo.DEFAULTS)
            for key, value in values.items():
                if key in allowed:
                    self.settings_repo.set(key, value)
            messagebox.showinfo("Settings", "Settings imported. Restart J.A.R.V.I.S to apply all changes.", parent=self)
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc), parent=self)

    def _backup(self):
        destination = filedialog.askdirectory(parent=self)
        if destination:
            from .recovery import create_backup
            path = create_backup(self.settings_repo.database.path.parent, Path(destination))
            messagebox.showinfo("Backup complete", f"Created {path}", parent=self)

    def _restore(self):
        archive = filedialog.askopenfilename(parent=self, filetypes=[("J.A.R.V.I.S backup", "*.zip")])
        if archive and messagebox.askyesno("Restore backup", "Restore this backup and restart J.A.R.V.I.S afterward?", parent=self):
            try:
                from .recovery import restore_backup
                restore_backup(Path(archive), self.settings_repo.database.path.parent)
                messagebox.showinfo("Restore complete", "Backup restored. Restart J.A.R.V.I.S.", parent=self)
            except Exception as exc:
                messagebox.showerror("Restore failed", str(exc), parent=self)
