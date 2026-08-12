"""The reactive voice core.

A single widget carries most of the interface's personality, so it has to read
at a glance: whether J.A.R.V.I.S is listening, whether it heard you, and
whether it is thinking or replying. Live microphone level drives the geometry,
so speaking visibly moves it rather than playing a canned animation.
"""

from __future__ import annotations

import math
import tkinter as tk

from .theme import Palette, Type, blend


class VoiceOrb(tk.Canvas):
    """Concentric reactive rings around a core that responds to input level."""

    RING_POINTS = 72

    STATE_COLOURS = {
        "idle": (Palette.ACCENT_DIM, Palette.VIOLET_DIM),
        "listening": (Palette.ACCENT, Palette.VIOLET),
        "thinking": (Palette.VIOLET, Palette.ACCENT),
        "speaking": (Palette.ACCENT, Palette.SUCCESS),
        "working": (Palette.VIOLET, Palette.ACCENT),
        "paused": (Palette.TEXT_FAINT, Palette.TEXT_MUTED),
        "error": (Palette.DANGER, Palette.WARNING),
        "stopped": (Palette.DANGER, Palette.DANGER_DIM),
    }

    def __init__(self, parent, size: int = 210, background: str | None = None):
        self.size = size
        self.background = background or parent["bg"]
        super().__init__(parent, bg=self.background, highlightthickness=0, bd=0,
                         width=size, height=size)
        self.state = "idle"
        self.level = 0.0
        self._display_level = 0.0
        self._phase = 0.0
        self._running = False

    def set_state(self, state: str) -> None:
        self.state = state if state in self.STATE_COLOURS else "idle"

    def set_level(self, level: float) -> None:
        self.level = max(0.0, min(1.0, float(level)))

    def start(self, interval: int = 40) -> None:
        if self._running:
            return
        self._running = True
        self._tick(interval)

    def stop(self) -> None:
        self._running = False

    def _tick(self, interval: int) -> None:
        if not self._running:
            return
        self._phase += 0.09
        # Ease the drawn level toward the measured one so the orb never jitters.
        self._display_level += (self.level - self._display_level) * 0.3
        try:
            self._draw()
        except tk.TclError:
            return
        self.after(interval, lambda: self._tick(interval))

    def _energy(self) -> float:
        """How animated the orb should be, independent of microphone input."""
        if self.state in {"thinking", "working"}:
            return 0.45 + math.sin(self._phase * 1.6) * 0.2
        if self.state == "speaking":
            return 0.5 + math.sin(self._phase * 3.1) * 0.28
        if self.state == "listening":
            return 0.15 + self._display_level * 0.85
        if self.state in {"paused", "stopped"}:
            return 0.05
        return 0.12 + math.sin(self._phase * 0.7) * 0.05

    def _draw(self) -> None:
        width = self.winfo_width() or self.size
        height = self.winfo_height() or self.size
        if width < 10 or height < 10:
            return
        self.delete("all")
        centre_x, centre_y = width / 2, height / 2
        radius = min(width, height) / 2 - 6
        primary, secondary = self.STATE_COLOURS.get(self.state, self.STATE_COLOURS["idle"])
        energy = self._energy()

        self._draw_halo(centre_x, centre_y, radius, primary, energy)
        self._draw_orbits(centre_x, centre_y, radius, primary, secondary, energy)
        self._draw_reactive_ring(centre_x, centre_y, radius * 0.6, primary, secondary, energy)
        self._draw_core(centre_x, centre_y, radius * 0.34, primary, secondary, energy)

    def _draw_halo(self, cx: float, cy: float, radius: float, colour: str, energy: float) -> None:
        """Concentric fading circles stand in for a real glow."""
        layers = 5
        for index in range(layers, 0, -1):
            fraction = index / layers
            ring_radius = radius * (0.62 + fraction * 0.38) * (1 + energy * 0.06)
            shade = blend(self.background, colour, 0.10 * (1 - fraction) + energy * 0.08)
            self.create_oval(cx - ring_radius, cy - ring_radius, cx + ring_radius, cy + ring_radius,
                             outline=shade, width=1)

    def _draw_orbits(self, cx: float, cy: float, radius: float,
                     primary: str, secondary: str, energy: float) -> None:
        """Two counter-rotating arcs give a sense of active machinery."""
        for index, (colour, direction, span) in enumerate(
            ((primary, 1, 110), (secondary, -1, 70))
        ):
            ring_radius = radius * (0.86 - index * 0.12)
            start = math.degrees(self._phase * direction * (0.6 + index * 0.35)) % 360
            self.create_arc(
                cx - ring_radius, cy - ring_radius, cx + ring_radius, cy + ring_radius,
                start=start, extent=span, style="arc",
                outline=blend(self.background, colour, 0.55 + energy * 0.45),
                width=2,
            )

    def _draw_reactive_ring(self, cx: float, cy: float, radius: float,
                            primary: str, secondary: str, energy: float) -> None:
        """The ring that actually deforms with your voice."""
        points: list[float] = []
        for index in range(self.RING_POINTS):
            angle = index * math.tau / self.RING_POINTS
            # Three harmonics keep the deformation organic rather than sinusoidal.
            wobble = (
                math.sin(angle * 3 + self._phase * 2.0) * 0.55
                + math.sin(angle * 5 - self._phase * 1.3) * 0.30
                + math.sin(angle * 8 + self._phase * 0.7) * 0.15
            )
            offset = radius * (1 + wobble * energy * 0.26)
            points.extend((cx + math.cos(angle) * offset, cy + math.sin(angle) * offset))
        self.create_polygon(
            points, smooth=True, splinesteps=8,
            fill=blend(self.background, primary, 0.10 + energy * 0.10),
            outline=blend(self.background, secondary, 0.65 + energy * 0.35),
            width=2,
        )
        # A clean circle tracking loudness reads more precisely than the
        # organic ring alone, so the two together show both life and level.
        if self._display_level > 0.03:
            level_radius = radius * (0.52 + self._display_level * 0.62)
            self.create_oval(cx - level_radius, cy - level_radius,
                             cx + level_radius, cy + level_radius,
                             outline=blend(self.background, Palette.ACCENT,
                                           0.35 + self._display_level * 0.65),
                             width=2)

    def _draw_core(self, cx: float, cy: float, radius: float,
                   primary: str, secondary: str, energy: float) -> None:
        core_radius = radius * (0.82 + energy * 0.3)
        for step in range(4, 0, -1):
            fraction = step / 4
            shade = blend(self.background, primary, 0.12 + (1 - fraction) * 0.4)
            size = core_radius * (0.6 + fraction * 0.55)
            self.create_oval(cx - size, cy - size, cx + size, cy + size, fill=shade, outline="")
        self.create_oval(cx - core_radius * 0.55, cy - core_radius * 0.55,
                         cx + core_radius * 0.55, cy + core_radius * 0.55,
                         fill=blend(primary, "#ffffff", 0.25 + energy * 0.3), outline="")


class OrbCaption(tk.Frame):
    """Text under the orb explaining what it is doing, in plain words."""

    MESSAGES = {
        "idle": ("Say “Hey Jarvis”", "or press the microphone"),
        "listening": ("Listening", "speak naturally, pauses are fine"),
        "thinking": ("Thinking", "working out an answer"),
        "working": ("Working", "carrying out your request"),
        "speaking": ("Speaking", "press Escape or STOP to interrupt"),
        "paused": ("Microphone paused", "hands-free listening is off"),
        "stopped": ("Stopped", "pending work was cleared"),
        "error": ("Something went wrong", "see the message above"),
    }

    def __init__(self, parent):
        super().__init__(parent, bg=parent["bg"])
        self.title = tk.Label(self, text="Say “Hey Jarvis”", bg=parent["bg"],
                              fg=Palette.TEXT, font=Type.TITLE)
        self.title.pack()
        self.detail = tk.Label(self, text="or press the microphone", bg=parent["bg"],
                               fg=Palette.TEXT_MUTED, font=Type.CAPTION, wraplength=420)
        self.detail.pack(pady=(2, 0))
        self._live = ""

    def set_state(self, state: str) -> None:
        self._live = ""
        title, detail = self.MESSAGES.get(state, self.MESSAGES["idle"])
        self.title.configure(text=title)
        self.detail.configure(text=detail, fg=Palette.TEXT_MUTED)

    def set_live_text(self, text: str) -> None:
        """Show what is being heard, replacing the hint while speech arrives."""
        self._live = text.strip()
        if not self._live:
            return
        shown = self._live if len(self._live) <= 90 else "..." + self._live[-87:]
        self.detail.configure(text=shown, fg=Palette.ACCENT)
