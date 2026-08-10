"""First-run setup wizard for essential privacy and runtime choices."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk


class FirstRunWizard(tk.Toplevel):
    def __init__(self, parent, settings_repo):
        super().__init__(parent)
        self.settings = settings_repo
        self.title("Welcome to J.A.R.V.I.S")
        self.geometry("560x440")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        frame = ttk.Frame(self, padding=28); frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="J.A.R.V.I.S Mark 7", font=("Segoe UI Semibold", 20)).pack(anchor="w")
        ttk.Label(
            frame,
            text="Choose the capabilities you want enabled. You can change these later in Settings.",
            wraplength=490,
        ).pack(anchor="w", pady=(8, 20))
        self.speech = tk.BooleanVar(value=True)
        self.memory = tk.BooleanVar(value=True)
        self.proactive = tk.BooleanVar(value=True)
        self.privacy = tk.BooleanVar(value=False)
        for text, variable in (
            ("Speak assistant responses", self.speech),
            ("Remember recent conversations locally", self.memory),
            ("Enable reminders and system health notifications", self.proactive),
            ("Start in privacy mode (blocks screen capture and cloud vision)", self.privacy),
        ):
            ttk.Checkbutton(frame, text=text, variable=variable).pack(anchor="w", pady=6)
        ttk.Label(
            frame,
            text="Sensitive actions ask for confirmation. Ctrl+Alt+J immediately stops pending automation.",
            wraplength=490,
        ).pack(anchor="w", pady=(18, 12))
        ttk.Button(frame, text="Finish setup", command=self.finish).pack(anchor="e", pady=(14, 0))
        self.protocol("WM_DELETE_WINDOW", self.finish)

    def finish(self):
        self.settings.set("speak_responses", self.speech.get())
        self.settings.set("conversation_memory", self.memory.get())
        self.settings.set("proactive_enabled", self.proactive.get())
        self.settings.set("privacy_mode", self.privacy.get())
        self.settings.set("first_run_complete", True)
        self.destroy()
