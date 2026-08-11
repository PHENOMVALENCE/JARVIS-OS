"""Canvas-drawn widgets that give Tk a modern surface treatment.

Tk has no rounded corners, no borders with radius, and no shadows. Each of
those is drawn here on a Canvas and reused, so the rest of the interface can be
composed from panels and buttons rather than from drawing primitives.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from .theme import RADIUS, Palette, Space, Type, blend


def rounded_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float,
                 radius: float = RADIUS, **options) -> int:
    """A rounded rectangle as a smoothed polygon.

    Tk smooths polygons with a spline, so duplicating the corner points pulls
    the curve tight enough to read as a real radius.
    """
    radius = max(0.0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1,
        x2, y1 + radius, x2, y2 - radius, x2, y2,
        x2 - radius, y2, x1 + radius, y2, x1, y2,
        x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **options)


class Card(tk.Frame):
    """A rounded, bordered surface with an optional accent glow along the top.

    The card paints itself onto a background Canvas and exposes `body`, so
    callers pack ordinary widgets without knowing about the drawing.
    """

    def __init__(self, parent, *, fill: str = Palette.SURFACE, border: str = Palette.BORDER,
                 glow: str | None = None, padding: int = Space.MD, radius: int = RADIUS, **kwargs):
        super().__init__(parent, bg=parent["bg"], **kwargs)
        self._fill, self._border, self._glow, self._radius = fill, border, glow, radius
        # The canvas is placed rather than packed so it fills the card as a
        # backdrop without contributing to the requested size. The body is
        # packed, so the card sizes itself from its contents as a frame would.
        self.canvas = tk.Canvas(self, bg=parent["bg"], highlightthickness=0, bd=0)
        self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=fill)
        self.body.pack(fill="both", expand=True, padx=padding, pady=padding)
        self.bind("<Configure>", self._redraw)

    def set_glow(self, colour: str | None) -> None:
        if colour != self._glow:
            self._glow = colour
            self._redraw()

    def _redraw(self, _event=None) -> None:
        width, height = self.winfo_width(), self.winfo_height()
        if width < 4 or height < 4:
            return
        self.canvas.delete("all")
        rounded_rect(self.canvas, 1, 1, width - 1, height - 1, self._radius,
                     fill=self._fill, outline=self._border, width=1)
        if self._glow:
            # A short accent bar reads as a lit edge without needing real shadows.
            inset = self._radius + 6
            self.canvas.create_line(inset, 2, width - inset, 2, fill=self._glow, width=2)


class Button(tk.Canvas):
    """A flat rounded button with hover and press feedback."""

    def __init__(self, parent, text: str, command: Callable[[], None], *,
                 style: str = "ghost", width: int = 0, height: int = 38,
                 font=Type.LABEL, radius: int = 10):
        colours = {
            "primary": (Palette.ACCENT, Palette.VOID, "#7ceaff"),
            "ghost": (Palette.SURFACE_HIGH, Palette.TEXT_SOFT, Palette.BORDER_BRIGHT),
            "danger": (Palette.DANGER_DIM, "#ffb3be", "#7d3341"),
            "quiet": (Palette.BASE, Palette.TEXT_MUTED, Palette.SURFACE_HIGH),
        }
        self.fill, self.foreground, self.hover_fill = colours.get(style, colours["ghost"])
        self.text_value, self.command, self.radius, self.font = text, command, radius, font
        measured = width or (len(text) * 8 + Space.XL)
        super().__init__(parent, bg=parent["bg"], highlightthickness=0, bd=0,
                         width=measured, height=height)
        self._hovered = False
        self._enabled = True
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.configure(cursor="hand2")

    def set_text(self, text: str) -> None:
        self.text_value = text
        self._draw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def _enter(self, _event=None):
        self._hovered = True
        self._draw()

    def _leave(self, _event=None):
        self._hovered = False
        self._draw()

    def _press(self, _event=None):
        if self._enabled:
            self._draw(pressed=True)

    def _release(self, _event=None):
        self._draw()
        if self._enabled and self._hovered:
            self.command()

    def _draw(self, pressed: bool = False) -> None:
        width, height = self.winfo_width(), self.winfo_height()
        if width < 4 or height < 4:
            return
        self.delete("all")
        fill = self.hover_fill if (self._hovered and self._enabled) else self.fill
        if pressed:
            fill = blend(fill, Palette.VOID, 0.25)
        if not self._enabled:
            fill = blend(fill, Palette.BASE, 0.6)
        rounded_rect(self, 1, 1, width - 1, height - 1, self.radius, fill=fill, outline="")
        colour = self.foreground if self._enabled else Palette.TEXT_FAINT
        self.create_text(width / 2, height / 2, text=self.text_value, fill=colour, font=self.font)


class StatusChip(tk.Canvas):
    """A pill showing the assistant's current state, with a pulsing dot."""

    def __init__(self, parent, width: int = 148, height: int = 30):
        super().__init__(parent, bg=parent["bg"], highlightthickness=0, bd=0,
                         width=width, height=height)
        self.label, self.colour = "READY", Palette.SUCCESS
        self._phase = 0.0
        self.bind("<Configure>", lambda _e: self._draw())

    def set_state(self, label: str, colour: str) -> None:
        self.label, self.colour = label, colour
        self._draw()

    def pulse(self, phase: float) -> None:
        self._phase = phase
        self._draw()

    def _draw(self) -> None:
        import math

        width, height = self.winfo_width(), self.winfo_height()
        if width < 4 or height < 4:
            return
        self.delete("all")
        rounded_rect(self, 1, 1, width - 1, height - 1, height / 2,
                     fill=Palette.SURFACE_HIGH, outline=Palette.BORDER, width=1)
        radius = 4 + math.sin(self._phase) * 1.4
        centre_y = height / 2
        self.create_oval(14 - radius, centre_y - radius, 14 + radius, centre_y + radius,
                         fill=self.colour, outline="")
        self.create_text(30, centre_y, text=self.label, anchor="w",
                         fill=Palette.TEXT_SOFT, font=Type.MONO_SMALL)


class MetricRow(tk.Frame):
    """A label/value pair used in the side panels."""

    def __init__(self, parent, label: str, value: str, accent: str = Palette.TEXT):
        super().__init__(parent, bg=parent["bg"])
        tk.Label(self, text=label, bg=parent["bg"], fg=Palette.TEXT_FAINT,
                 font=Type.MONO_SMALL).pack(anchor="w")
        self.value = tk.Label(self, text=value, bg=parent["bg"], fg=accent,
                              font=Type.LABEL, wraplength=180, justify="left")
        self.value.pack(anchor="w", pady=(1, 0))

    def set(self, value: str) -> None:
        self.value.configure(text=value)


class LevelMeter(tk.Canvas):
    """A row of bars showing live microphone input.

    Seeing the meter move is the fastest way to know the microphone is working,
    which is otherwise invisible until a request silently fails.
    """

    BARS = 22

    def __init__(self, parent, width: int = 190, height: int = 26):
        super().__init__(parent, bg=parent["bg"], highlightthickness=0, bd=0,
                         width=width, height=height)
        self._level = 0.0
        self._peak = 0.0
        self.bind("<Configure>", lambda _e: self._draw())

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, float(level)))
        self._peak = max(self._level, self._peak * 0.92)
        self._draw()

    def _draw(self) -> None:
        width, height = self.winfo_width(), self.winfo_height()
        if width < 4 or height < 4:
            return
        self.delete("all")
        gap = 3
        bar_width = max(2, (width - gap * (self.BARS - 1)) / self.BARS)
        active = self._level * self.BARS
        peak_bar = self._peak * self.BARS
        for index in range(self.BARS):
            x = index * (bar_width + gap)
            fraction = index / max(1, self.BARS - 1)
            if index < active:
                colour = blend(Palette.ACCENT, Palette.VIOLET, fraction)
            elif index < peak_bar:
                colour = Palette.ACCENT_DEEP
            else:
                colour = Palette.SURFACE_HIGH
            # Taller bars toward the middle give the meter a subtle waveform shape.
            scale = 0.45 + 0.55 * (1 - abs(fraction - 0.5) * 2) ** 0.6
            bar_height = max(3, height * scale)
            top = (height - bar_height) / 2
            self.create_rectangle(x, top, x + bar_width, top + bar_height,
                                  fill=colour, outline="")


class Divider(tk.Frame):
    def __init__(self, parent, pad: int = Space.MD):
        super().__init__(parent, bg=parent["bg"])
        tk.Frame(self, bg=Palette.BORDER, height=1).pack(fill="x", pady=pad)
