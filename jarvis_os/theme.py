"""Visual language for the desktop interface.

Every colour, size, and font used by the UI lives here so the interface stays
coherent as it grows. Tk has no styling cascade, so a single source of truth is
the only thing keeping panels from drifting apart.
"""

from __future__ import annotations


class Palette:
    """A deep, cool-toned dark scheme with a single luminous accent."""

    # Backgrounds, from furthest back to nearest the viewer.
    VOID = "#05070d"
    BASE = "#080b14"
    SURFACE = "#0d1220"
    SURFACE_HIGH = "#121a2c"
    SURFACE_INPUT = "#0f1626"

    # Hairlines and separators.
    BORDER = "#1b2740"
    BORDER_BRIGHT = "#25375a"
    BORDER_GLOW = "#2f5f8a"

    # Accents.
    ACCENT = "#3ddcff"
    ACCENT_DIM = "#1c8fb0"
    ACCENT_DEEP = "#0d4d63"
    VIOLET = "#8b7bff"
    VIOLET_DIM = "#4a3f96"

    # Meaning.
    SUCCESS = "#4df0a8"
    WARNING = "#ffc46b"
    DANGER = "#ff6b81"
    DANGER_DIM = "#5c2530"

    # Text.
    TEXT = "#e8f4ff"
    TEXT_SOFT = "#a9c0d4"
    TEXT_MUTED = "#6d8299"
    TEXT_FAINT = "#4a5c70"


class Type:
    """Segoe UI is present on every supported Windows build; Consolas for data."""

    DISPLAY = ("Segoe UI Semibold", 22)
    TITLE = ("Segoe UI Semibold", 14)
    HEADING = ("Segoe UI Semibold", 11)
    BODY = ("Segoe UI", 11)
    BODY_SMALL = ("Segoe UI", 10)
    LABEL = ("Segoe UI Semibold", 9)
    CAPTION = ("Segoe UI", 9)
    MONO = ("Consolas", 9)
    MONO_SMALL = ("Consolas", 8)
    BRAND = ("Segoe UI Semibold", 20)


class Space:
    XS = 4
    SM = 8
    MD = 14
    LG = 20
    XL = 28
    XXL = 40


RADIUS = 14


# Assistant states drive the orb, the status chip, and the accent colouring
# together, so they are defined once rather than in each widget.
STATES = {
    "idle": ("READY", Palette.SUCCESS),
    "listening": ("LISTENING", Palette.ACCENT),
    "thinking": ("THINKING", Palette.VIOLET),
    "speaking": ("SPEAKING", Palette.ACCENT),
    "working": ("WORKING", Palette.VIOLET),
    "paused": ("MIC PAUSED", Palette.TEXT_MUTED),
    "stopped": ("STOPPED", Palette.DANGER),
    "error": ("ERROR", Palette.DANGER),
}


def state_style(state: str) -> tuple[str, str]:
    return STATES.get(state, (state.upper(), Palette.ACCENT))


def blend(start: str, end: str, amount: float) -> str:
    """Mix two hex colours. Used for gradients Tk cannot draw natively."""
    amount = max(0.0, min(1.0, float(amount)))
    start_rgb = tuple(int(start[index:index + 2], 16) for index in (1, 3, 5))
    end_rgb = tuple(int(end[index:index + 2], 16) for index in (1, 3, 5))
    mixed = tuple(round(a + (b - a) * amount) for a, b in zip(start_rgb, end_rgb))
    return "#%02x%02x%02x" % mixed
