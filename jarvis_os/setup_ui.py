"""First-run setup.

Getting to "say Hey Jarvis and it answers" involves a microphone that has to
be heard, a voice that has to be downloaded, a wake word model, and a startup
entry. Left to a settings screen, most of that never gets configured, so the
wizard walks through it once and verifies each part as it goes.
"""

from __future__ import annotations

import threading
import tkinter as tk

from .audio_level import MicrophoneLevel, measure_ambient, suggested_energy
from .startup import set_startup
from .theme import Palette, Space, Type
from .widgets import Button, Card, LevelMeter, rounded_rect


class StepDots(tk.Canvas):
    """Progress along the wizard, drawn as a row of dots."""

    def __init__(self, parent, count: int, width: int = 200, height: int = 16):
        super().__init__(parent, bg=parent["bg"], highlightthickness=0, bd=0,
                         width=width, height=height)
        self.count = count
        self.index = 0
        self.bind("<Configure>", lambda _e: self._draw())

    def set_index(self, index: int) -> None:
        self.index = index
        self._draw()

    def _draw(self) -> None:
        width, height = self.winfo_width(), self.winfo_height()
        if width < 4:
            return
        self.delete("all")
        spacing = 18
        start = width - spacing * self.count
        for step in range(self.count):
            x = start + step * spacing
            y = height / 2
            if step < self.index:
                self.create_oval(x - 4, y - 4, x + 4, y + 4, fill=Palette.ACCENT_DIM, outline="")
            elif step == self.index:
                rounded_rect(self, x - 9, y - 4, x + 9, y + 4, 4, fill=Palette.ACCENT, outline="")
            else:
                self.create_oval(x - 4, y - 4, x + 4, y + 4, fill=Palette.SURFACE_HIGH, outline="")


class SetupWizard(tk.Toplevel):
    """A guided, verified first run."""

    def __init__(self, parent, settings_repo, project_root=None, speech_engine=None):
        super().__init__(parent)
        self.settings = settings_repo
        self.project_root = project_root
        self.speech_engine = speech_engine
        self.title("Set up J.A.R.V.I.S")
        self.configure(bg=Palette.BASE)
        self.geometry("720x620")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.finish)

        self.wake_word = tk.BooleanVar(value=True)
        self.autostart = tk.BooleanVar(value=True)
        self.speak = tk.BooleanVar(value=True)
        self.memory = tk.BooleanVar(value=True)
        self.proactive = tk.BooleanVar(value=True)
        self.privacy = tk.BooleanVar(value=False)
        self.offline_voice = tk.BooleanVar(value=False)

        self.mic_level: MicrophoneLevel | None = None
        self.calibrated_energy: int | None = None
        self._notes: list[str] = []

        self.steps = (
            ("Welcome", self._step_welcome),
            ("Microphone", self._step_microphone),
            ("Voice", self._step_voice),
            ("Wake word", self._step_wake),
            ("Startup", self._step_startup),
            ("Privacy", self._step_privacy),
            ("Ready", self._step_done),
        )
        self.index = 0
        self._build_shell()
        self._render()

    # ---------------------------------------------------------------- shell

    def _build_shell(self) -> None:
        header = tk.Frame(self, bg=Palette.VOID, height=76, padx=Space.XL, pady=Space.MD)
        header.pack(fill="x")
        header.pack_propagate(False)
        titles = tk.Frame(header, bg=Palette.VOID)
        titles.pack(side="left", fill="y")
        self.step_title = tk.Label(titles, text="", bg=Palette.VOID, fg=Palette.TEXT,
                                   font=Type.TITLE)
        self.step_title.pack(anchor="w")
        self.step_subtitle = tk.Label(titles, text="", bg=Palette.VOID, fg=Palette.TEXT_MUTED,
                                      font=Type.CAPTION)
        self.step_subtitle.pack(anchor="w", pady=(2, 0))
        self.dots = StepDots(header, len(self.steps))
        self.dots.pack(side="right", pady=Space.MD)

        self.content = tk.Frame(self, bg=Palette.BASE, padx=Space.XL, pady=Space.LG)
        self.content.pack(fill="both", expand=True)

        footer = tk.Frame(self, bg=Palette.BASE, padx=Space.XL, pady=Space.MD)
        footer.pack(fill="x")
        self.back_button = Button(footer, "BACK", self._back, style="quiet", width=96)
        self.back_button.pack(side="left")
        self.next_button = Button(footer, "CONTINUE", self._next, style="primary", width=136)
        self.next_button.pack(side="right")
        self.skip_button = Button(footer, "SKIP SETUP", self.finish, style="quiet", width=118)
        self.skip_button.pack(side="right", padx=(0, Space.SM))

    def _render(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()
        name, builder = self.steps[self.index]
        self.step_title.configure(text=name)
        self.dots.set_index(self.index)
        builder(self.content)
        self.back_button.set_enabled(self.index > 0)
        last = self.index == len(self.steps) - 1
        self.next_button.set_text("FINISH" if last else "CONTINUE")
        self.skip_button.pack_forget() if last else None

    def _next(self) -> None:
        if self.index == len(self.steps) - 1:
            self.finish()
            return
        self._leave_step()
        self.index += 1
        self._render()

    def _back(self) -> None:
        if self.index == 0:
            return
        self._leave_step()
        self.index -= 1
        self._render()

    def _leave_step(self) -> None:
        """Release the microphone when moving off the step that uses it."""
        if self.mic_level is not None:
            self.mic_level.stop()
            self.mic_level = None

    # ------------------------------------------------------------ building

    def _heading(self, parent, text: str, detail: str) -> None:
        tk.Label(parent, text=text, bg=Palette.BASE, fg=Palette.TEXT,
                 font=Type.DISPLAY, justify="left").pack(anchor="w")
        tk.Label(parent, text=detail, bg=Palette.BASE, fg=Palette.TEXT_SOFT, font=Type.BODY,
                 wraplength=620, justify="left").pack(anchor="w", pady=(Space.SM, Space.LG))

    @staticmethod
    def _check(parent, text: str, variable: tk.BooleanVar, detail: str = "") -> None:
        row = tk.Frame(parent, bg=parent["bg"])
        row.pack(fill="x", pady=Space.SM)
        box = tk.Checkbutton(
            row, text=text, variable=variable, bg=parent["bg"], fg=Palette.TEXT,
            activebackground=parent["bg"], activeforeground=Palette.TEXT,
            selectcolor=Palette.SURFACE_HIGH, font=Type.BODY, anchor="w",
            highlightthickness=0, bd=0, cursor="hand2",
        )
        box.pack(anchor="w")
        if detail:
            tk.Label(row, text=detail, bg=parent["bg"], fg=Palette.TEXT_MUTED,
                     font=Type.CAPTION, wraplength=580, justify="left").pack(anchor="w", padx=(24, 0))

    # --------------------------------------------------------------- steps

    def _step_welcome(self, parent) -> None:
        self.step_subtitle.configure(text="A few minutes, once")
        self._heading(
            parent, "Let's get you talking to it",
            "This sets up the parts that make J.A.R.V.I.S work hands-free: hearing you "
            "clearly, speaking back in a natural voice, and answering when you say "
            "“Hey Jarvis”. Everything here is free and nothing needs an account.",
        )
        card = Card(parent, padding=Space.LG)
        card.pack(fill="x")
        for title, detail in (
            ("Runs on your machine", "The language model, speech recognition, and voice all work locally."),
            ("Asks before acting", "Typing into apps, closing them, or deleting files needs your confirmation."),
            ("Stops instantly", "Escape interrupts speech. Ctrl+Alt+J clears pending work."),
        ):
            row = tk.Frame(card.body, bg=Palette.SURFACE)
            row.pack(fill="x", pady=Space.SM)
            tk.Label(row, text=title, bg=Palette.SURFACE, fg=Palette.ACCENT,
                     font=Type.HEADING).pack(anchor="w")
            tk.Label(row, text=detail, bg=Palette.SURFACE, fg=Palette.TEXT_MUTED,
                     font=Type.BODY_SMALL, wraplength=580, justify="left").pack(anchor="w")

    def _step_microphone(self, parent) -> None:
        self.step_subtitle.configure(text="Make sure it can hear you")
        self._heading(
            parent, "Say something",
            "The bars should move while you talk. If they stay still, pick a different "
            "input device in Windows sound settings.",
        )
        card = Card(parent, padding=Space.LG)
        card.pack(fill="x")
        self.setup_meter = LevelMeter(card.body, height=34)
        self.setup_meter.pack(fill="x", pady=(0, Space.MD))
        self.mic_status = tk.Label(card.body, text="Starting microphone…", bg=Palette.SURFACE,
                                   fg=Palette.TEXT_MUTED, font=Type.BODY)
        self.mic_status.pack(anchor="w")
        self.calibrate_note = tk.Label(
            card.body,
            text="Calibrating measures the noise in your room and sets the level at which "
                 "J.A.R.V.I.S decides you are speaking.",
            bg=Palette.SURFACE, fg=Palette.TEXT_FAINT, font=Type.CAPTION,
            wraplength=560, justify="left",
        )
        self.calibrate_note.pack(anchor="w", pady=(Space.MD, Space.SM))
        self.calibrate_button = Button(card.body, "CALIBRATE FOR THIS ROOM",
                                       self._calibrate, style="ghost", width=250)
        self.calibrate_button.pack(anchor="w")

        self.mic_level = MicrophoneLevel(self._on_setup_level)
        self.mic_level.start()
        self.after(700, self._refresh_mic_status)

    def _on_setup_level(self, level: float) -> None:
        try:
            self.after(0, lambda: self._draw_setup_level(level))
        except (tk.TclError, RuntimeError):
            pass

    def _draw_setup_level(self, level: float) -> None:
        if getattr(self, "setup_meter", None) is not None and self.setup_meter.winfo_exists():
            self.setup_meter.set_level(level)

    def _refresh_mic_status(self) -> None:
        if not getattr(self, "mic_status", None) or not self.mic_status.winfo_exists():
            return
        if self.mic_level is None:
            return
        if self.mic_level.available:
            self.mic_status.configure(text="Microphone is working.", fg=Palette.SUCCESS)
        elif self.mic_level.error:
            self.mic_status.configure(
                text=f"No microphone found. {self.mic_level.error[:70]}", fg=Palette.WARNING
            )
        self.after(900, self._refresh_mic_status)

    def _calibrate(self) -> None:
        self.calibrate_button.set_enabled(False)
        self.mic_status.configure(text="Listening to the room, stay quiet…", fg=Palette.ACCENT)
        if self.mic_level is not None:
            self.mic_level.stop()
            self.mic_level = None

        def work() -> None:
            try:
                ambient = measure_ambient(1.8)
                energy = suggested_energy(ambient)
            except Exception as exc:
                self.after(0, lambda: self._calibrated(None, str(exc)))
                return
            self.after(0, lambda: self._calibrated(energy, ""))

        threading.Thread(target=work, daemon=True, name="jarvis-calibrate").start()

    def _calibrated(self, energy: int | None, error: str) -> None:
        if not self.mic_status.winfo_exists():
            return
        self.calibrate_button.set_enabled(True)
        if energy is None:
            self.mic_status.configure(text=f"Could not calibrate: {error[:70]}", fg=Palette.WARNING)
            return
        self.calibrated_energy = energy
        self.mic_status.configure(
            text=f"Calibrated. Speech threshold set to {energy}.", fg=Palette.SUCCESS
        )
        self.mic_level = MicrophoneLevel(self._on_setup_level)
        self.mic_level.start()

    def _step_voice(self, parent) -> None:
        self.step_subtitle.configure(text="How it speaks back")
        self._heading(
            parent, "Pick a voice",
            "Both options are free neural voices and sound close to a person. The offline "
            "voice is faster and keeps working without internet, but downloads about 63 MB once.",
        )
        card = Card(parent, padding=Space.LG)
        card.pack(fill="x")
        self._check(card.body, "Use the offline voice (recommended)", self.offline_voice,
                    "Downloads once, then never needs a connection. Leave unticked to use the "
                    "Microsoft Edge voice, which needs internet each time it speaks.")
        self.voice_status = tk.Label(card.body, text="", bg=Palette.SURFACE,
                                     fg=Palette.TEXT_MUTED, font=Type.BODY_SMALL,
                                     wraplength=560, justify="left")
        self.voice_status.pack(anchor="w", pady=(Space.SM, Space.MD))
        Button(card.body, "TEST THE VOICE", self._test_voice, style="ghost", width=180).pack(anchor="w")

    def _test_voice(self) -> None:
        self.voice_status.configure(text="Speaking…", fg=Palette.ACCENT)
        engine = self.speech_engine

        def work() -> None:
            message = "Good afternoon. I am Jarvis, and I am ready when you are."
            try:
                if engine is not None:
                    engine.say(message)
                    result = "If you heard that, the voice is working."
                else:
                    result = "Voice will be available once setup finishes."
            except Exception as exc:
                result = f"The voice could not play: {exc}"
            self.after(0, lambda: self.voice_status.configure(text=result, fg=Palette.TEXT_SOFT))

        threading.Thread(target=work, daemon=True, name="jarvis-voice-test").start()

    def _step_wake(self, parent) -> None:
        self.step_subtitle.configure(text="Answering without touching anything")
        self._heading(
            parent, "“Hey Jarvis”",
            "With this on, J.A.R.V.I.S listens for its name in the background and wakes up "
            "when it hears you. The wake word runs entirely on your machine and needs no account.",
        )
        card = Card(parent, padding=Space.LG, glow=Palette.ACCENT)
        card.pack(fill="x")
        self._check(card.body, "Wake when I say “Hey Jarvis”", self.wake_word,
                    "Uses a small local model. Only the wake phrase is listened for; nothing "
                    "is recorded or sent anywhere until it wakes.")
        self._check(card.body, "Keep listening after it wakes", self.speak,
                    "Speak your request straight after the wake phrase, with no button press.")
        tk.Label(card.body,
                 text="You can pause listening at any time from the main window.",
                 bg=Palette.SURFACE, fg=Palette.TEXT_FAINT, font=Type.CAPTION,
                 wraplength=560, justify="left").pack(anchor="w", pady=(Space.MD, 0))

    def _step_startup(self, parent) -> None:
        self.step_subtitle.configure(text="Always there when you sign in")
        self._heading(
            parent, "Start automatically",
            "For “Hey Jarvis” to work whenever you are at your desk, J.A.R.V.I.S needs to be "
            "running. Starting it at sign-in is the simplest way to do that.",
        )
        card = Card(parent, padding=Space.LG)
        card.pack(fill="x")
        self._check(card.body, "Start J.A.R.V.I.S when I sign in", self.autostart,
                    "Runs in your session with limited privileges, restarts if it crashes, "
                    "and sits in the system tray until you need it.")
        self.startup_status = tk.Label(card.body, text="", bg=Palette.SURFACE,
                                       fg=Palette.TEXT_MUTED, font=Type.BODY_SMALL,
                                       wraplength=560, justify="left")
        self.startup_status.pack(anchor="w", pady=(Space.SM, 0))

    def _step_privacy(self, parent) -> None:
        self.step_subtitle.configure(text="What it may keep and do")
        self._heading(
            parent, "Your choices",
            "All of these can be changed later in Settings.",
        )
        card = Card(parent, padding=Space.LG)
        card.pack(fill="x")
        self._check(card.body, "Remember recent conversations", self.memory,
                    "Stored locally so follow-ups like “what about Berlin” make sense.")
        self._check(card.body, "Reminders and system health alerts", self.proactive)
        self._check(card.body, "Start in privacy mode", self.privacy,
                    "Blocks screen capture and any cloud vision until you turn it off.")

    def _step_done(self, parent) -> None:
        self.step_subtitle.configure(text="That's everything")
        self._heading(
            parent, "Ready",
            "Try it now: say “Hey Jarvis, what's the weather today”, or type into the box "
            "at the bottom of the window.",
        )
        card = Card(parent, padding=Space.LG, glow=Palette.SUCCESS)
        card.pack(fill="x")
        summary = [
            ("Wake word", "“Hey Jarvis”" if self.wake_word.get() else "Off — use the MIC button"),
            ("Voice", "Offline neural" if self.offline_voice.get() else "Edge neural"),
            ("At sign-in", "Starts automatically" if self.autostart.get() else "Start it yourself"),
            ("Microphone", f"Calibrated to {self.calibrated_energy}"
                           if self.calibrated_energy else "Using the default threshold"),
        ]
        for label, value in summary:
            row = tk.Frame(card.body, bg=Palette.SURFACE)
            row.pack(fill="x", pady=Space.XS)
            tk.Label(row, text=label, bg=Palette.SURFACE, fg=Palette.TEXT_MUTED,
                     font=Type.BODY_SMALL, width=14, anchor="w").pack(side="left")
            tk.Label(row, text=value, bg=Palette.SURFACE, fg=Palette.TEXT,
                     font=Type.LABEL, anchor="w").pack(side="left")
        self.finish_status = tk.Label(parent, text="", bg=Palette.BASE, fg=Palette.WARNING,
                                      font=Type.CAPTION, wraplength=620, justify="left")
        self.finish_status.pack(anchor="w", pady=(Space.MD, 0))

    # -------------------------------------------------------------- saving

    def finish(self) -> None:
        self._leave_step()
        values = {
            "wake_word_enabled": self.wake_word.get(),
            "hands_free_enabled": self.speak.get(),
            "speak_responses": True,
            "conversation_memory": self.memory.get(),
            "proactive_enabled": self.proactive.get(),
            "privacy_mode": self.privacy.get(),
            "tts_engine": "piper" if self.offline_voice.get() else "edge",
            "first_run_complete": True,
        }
        if self.calibrated_energy:
            values["mic_energy"] = self.calibrated_energy
        for key, value in values.items():
            self.settings.set(key, value)

        if self.autostart.get():
            succeeded, message = set_startup(True, self.project_root)
            self.settings.set("startup_enabled", succeeded)
            if not succeeded and getattr(self, "finish_status", None) is not None:
                try:
                    self.finish_status.configure(text=f"Startup could not be enabled: {message}")
                    return
                except tk.TclError:
                    pass
        else:
            self.settings.set("startup_enabled", False)
        self.destroy()


# Kept so existing callers and tests keep working.
FirstRunWizard = SetupWizard
