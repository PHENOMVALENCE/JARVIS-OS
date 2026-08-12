"""Proof that a frozen build can actually do its job.

PyInstaller follows imports statically, and this codebase imports heavy
dependencies inside functions so startup stays fast. That combination produces
builds that launch happily and then fail the first time somebody speaks,
reads the screen, or triggers the wake word.

This imports every one of those lazily-loaded dependencies in the order the
running application would, and reports which are missing. It runs inside the
frozen executable, so it tests the bundle rather than the developer's machine.
"""

from __future__ import annotations

import sys

# Ordered as the application loads them. onnxruntime is deliberately first:
# initialising the Windows Runtime before it is loaded breaks its DLL load,
# which silently disables the wake word and the offline voice.
SUBSYSTEMS: tuple[tuple[str, str], ...] = (
    ("onnxruntime", "wake word and offline voice runtime"),
    ("numpy", "audio maths"),
    ("pyaudio", "microphone"),
    ("faster_whisper", "speech recognition"),
    ("ctranslate2", "recognition runtime"),
    ("edge_tts", "online neural voice"),
    ("piper", "offline neural voice"),
    ("pygame", "audio playback"),
    ("pyttsx3", "fallback Windows voice"),
    ("openwakeword", "wake word"),
    ("ollama", "local language model"),
    ("requests", "weather and research"),
    ("win32com.client", "indexed file search"),
    ("pywinauto", "control of other applications"),
    ("winotify", "notifications"),
    ("pystray", "system tray"),
    ("PIL", "screen capture"),
    ("winrt.windows.media.ocr", "on-device screen reading"),
    ("send2trash", "recoverable deletion"),
    ("tkinter", "the interface"),
)


def run(stream=None) -> int:
    """Import every subsystem. Returns 0 when all of them load."""
    stream = stream or sys.stdout
    missing: list[tuple[str, str, str]] = []
    for module, purpose in SUBSYSTEMS:
        try:
            __import__(module)
        except Exception as error:  # noqa: BLE001 - the reason is the point
            missing.append((module, purpose, f"{type(error).__name__}: {error}"))
            print(f"FAILED  {module:32} {purpose}", file=stream)
            print(f"        {type(error).__name__}: {str(error)[:120]}", file=stream)
        else:
            print(f"ok      {module:32} {purpose}", file=stream)

    # The application's own modules, which a broken bundle can also lose.
    try:
        from . import actions, app, capabilities, context, health, router  # noqa: F401

        print(f"ok      {'jarvis_os':32} application modules", file=stream)
    except Exception as error:  # noqa: BLE001
        missing.append(("jarvis_os", "application modules", str(error)))
        print(f"FAILED  {'jarvis_os':32} {error}", file=stream)

    if missing:
        print(f"\n{len(missing)} subsystem(s) missing from this build:", file=stream)
        for module, purpose, reason in missing:
            print(f"  {module} ({purpose}) - {reason[:100]}", file=stream)
        return 1
    print(f"\nAll {len(SUBSYSTEMS) + 1} subsystems loaded.", file=stream)
    return 0
