"""Settings, permissions, and audit-history interface."""

from __future__ import annotations

import subprocess
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .security import AuditLog
from .storage import PermissionRepository, SettingsRepository


ACTIONS = (
    "open_app", "open_folder", "find_files", "web_search", "spotify_play",
    "media", "set_volume", "copy_clipboard", "focus_window", "window_state",
    "screenshot", "analyze_screen", "read_clipboard", "notification", "work_mode", "type_text",
    "close_app", "delete_path",
)


class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, settings: SettingsRepository, permissions: PermissionRepository, audit: AuditLog, project_root, plugins=None):
        super().__init__(parent)
        self.settings_repo = settings
        self.permissions_repo = permissions
        self.audit = audit
        self.project_root = project_root
        self.plugins = plugins
        self.title("J.A.R.V.I.S Settings")
        self.geometry("760x610")
        self.minsize(650, 500)
        self.transient(parent)
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self._build_general()
        self._build_permissions()
        self._build_plugins()
        self._build_audit()
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
        for text, variable in (
            ("Speak responses", self.speak), ("Minimize to system tray", self.tray),
            ("Start at Windows sign-in", self.startup), ("Store conversation memory", self.memory),
            ("Privacy mode (blocks capture and cloud features)", self.privacy),
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
        ttk.Label(frame, text="Work mode apps (comma separated)").pack(anchor="w", pady=(12, 2))
        self.work_apps = ttk.Entry(frame)
        self.work_apps.insert(0, ", ".join(values["work_apps"]))
        self.work_apps.pack(fill="x")

    def _build_permissions(self):
        frame = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(frame, text="Permissions")
        ttk.Label(frame, text="Choose whether each local capability runs, asks first, or is blocked.").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )
        configured = self.permissions_repo.all()
        self.permission_vars = {}
        for row, action in enumerate(ACTIONS, start=1):
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

    def save(self):
        before_startup = bool(self.settings_repo.get("startup_enabled"))
        values = {
            "speak_responses": self.speak.get(), "minimize_to_tray": self.tray.get(),
            "startup_enabled": self.startup.get(), "conversation_memory": self.memory.get(),
            "privacy_mode": self.privacy.get(), "ollama_model": self.model.get().strip() or "gemma2:2b",
            "whisper_model": self.whisper.get(),
            "work_apps": [item.strip() for item in self.work_apps.get().split(",") if item.strip()],
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
