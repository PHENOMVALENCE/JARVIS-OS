"""What the user is doing right now, in one place.

Modules previously worked out the machine's state independently: window
enumeration lived in actions, capture in screen, and the assistant tracked
recent commands separately from anything the interface knew. Nothing could
answer "close this", because "this" was never represented.

This collects the machine's observable state behind one structured API and
remembers the objects a conversation has referred to, so pronouns resolve
against something real rather than being guessed at by the model.

Everything here is read-only observation. It performs no actions and it is
subject to privacy mode, which suppresses window titles and selected text
because those leak the contents of whatever is on screen.
"""

from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path

from .diagnostics_log import failure

# Windows constants, named rather than inlined at the call sites.
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9


@dataclass(frozen=True)
class WindowInfo:
    handle: int = 0
    title: str = ""
    process: str = ""
    process_id: int = 0
    minimized: bool = False

    @property
    def present(self) -> bool:
        return bool(self.handle)


@dataclass(frozen=True)
class PowerInfo:
    on_battery: bool = False
    percent: int = 100
    has_battery: bool = True


@dataclass
class Referents:
    """The objects a conversation has pointed at, for resolving pronouns."""

    window: WindowInfo | None = None
    application: str = ""
    file: Path | None = None
    folder: Path | None = None
    location: str = ""
    subject: str = ""
    action: str = ""
    failure: str = ""
    updated_at: float = field(default_factory=time.time)

    def note(self, **values) -> None:
        for key, value in values.items():
            if value:
                setattr(self, key, value)
        self.updated_at = time.time()


@dataclass(frozen=True)
class Snapshot:
    """One observation of the machine, taken at a point in time."""

    foreground: WindowInfo
    windows: tuple[WindowInfo, ...]
    clipboard_kind: str
    power: PowerInfo
    online: bool
    privacy: bool
    language: str
    taken_at: float

    def window_matching(self, text: str) -> WindowInfo | None:
        needle = text.strip().lower()
        if not needle:
            return None
        for window in self.windows:
            if needle in window.title.lower() or needle in window.process.lower():
                return window
        return None


class WindowsObserver:
    """Reads window and system state through native APIs."""

    IGNORED_TITLES = {"Program Manager", "Windows Input Experience", "Settings"}

    def __init__(self):
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32

    def _process_name(self, handle: int) -> tuple[str, int]:
        pid = wintypes.DWORD()
        self._user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        if not pid.value:
            return "", 0
        # QueryFullProcessImageName avoids needing psutil and works without
        # elevation for processes owned by the current user.
        access = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
        process = self._kernel32.OpenProcess(access, False, pid.value)
        if not process:
            return "", pid.value
        try:
            size = wintypes.DWORD(260)
            buffer = ctypes.create_unicode_buffer(size.value)
            if self._kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
                return Path(buffer.value).name, pid.value
            return "", pid.value
        finally:
            self._kernel32.CloseHandle(process)

    def _title(self, handle: int) -> str:
        length = self._user32.GetWindowTextLengthW(handle)
        if not length:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(handle, buffer, length + 1)
        return buffer.value

    def describe(self, handle: int) -> WindowInfo:
        if not handle:
            return WindowInfo()
        process, pid = self._process_name(handle)
        return WindowInfo(
            handle=int(handle),
            title=self._title(handle),
            process=process,
            process_id=pid,
            minimized=bool(self._user32.IsIconic(handle)),
        )

    def foreground(self) -> WindowInfo:
        return self.describe(self._user32.GetForegroundWindow())

    def visible_windows(self, limit: int = 40) -> tuple[WindowInfo, ...]:
        handles: list[int] = []

        def collect(handle, _extra):
            if self._user32.IsWindowVisible(handle) and self._user32.GetWindowTextLengthW(handle):
                handles.append(handle)
            return True

        callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(collect)
        self._user32.EnumWindows(callback, 0)
        found = []
        for handle in handles[:limit]:
            window = self.describe(handle)
            if window.title and window.title not in self.IGNORED_TITLES:
                found.append(window)
        return tuple(found)

    def power(self) -> PowerInfo:
        class Status(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong),
            ]

        status = Status()
        if not self._kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return PowerInfo()
        return PowerInfo(
            on_battery=status.ACLineStatus == 0,
            percent=int(status.BatteryLifePercent) if status.BatteryLifePercent != 255 else 100,
            has_battery=status.BatteryFlag != 128,
        )

    @staticmethod
    def online() -> bool:
        """Whether Windows believes there is a usable connection."""
        try:
            flags = wintypes.DWORD()
            return bool(ctypes.windll.wininet.InternetGetConnectedState(ctypes.byref(flags), 0))
        except Exception:
            return True


class ContextEngine:
    """Cached observation of the machine, plus conversational referents."""

    # Enumerating windows costs a few milliseconds, and context is consulted
    # several times per request, so a short cache avoids repeating it.
    CACHE_SECONDS = 1.5

    def __init__(self, settings_repo=None, observer: WindowsObserver | None = None, clock=time.time):
        self.settings_repo = settings_repo
        self.observer = observer or WindowsObserver()
        self.clock = clock
        self.referents = Referents()
        self._snapshot: Snapshot | None = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------ observing

    def _privacy(self) -> bool:
        return bool(self.settings_repo.get("privacy_mode", False)) if self.settings_repo else False

    def _language(self) -> str:
        return str(self.settings_repo.get("last_language", "en")) if self.settings_repo else "en"

    def _clipboard_kind(self) -> str:
        """The shape of the clipboard, never its contents."""
        try:
            user32 = ctypes.windll.user32
            for fmt, name in ((13, "text"), (1, "text"), (15, "files"), (2, "image"), (8, "image")):
                if user32.IsClipboardFormatAvailable(fmt):
                    return name
        except Exception as error:
            failure("context.clipboard", error)
        return "empty"

    def snapshot(self, refresh: bool = False) -> Snapshot:
        with self._lock:
            now = self.clock()
            if not refresh and self._snapshot and now - self._snapshot.taken_at < self.CACHE_SECONDS:
                return self._snapshot
            privacy = self._privacy()
            try:
                foreground = self.observer.foreground()
                windows = self.observer.visible_windows()
                power = self.observer.power()
                online = self.observer.online()
            except Exception as error:
                failure("context.observe", error)
                foreground, windows = WindowInfo(), ()
                power, online = PowerInfo(), True
            if privacy:
                # Titles name documents and web pages, so they are withheld.
                foreground = WindowInfo(foreground.handle, "", foreground.process,
                                        foreground.process_id, foreground.minimized)
                windows = tuple(WindowInfo(w.handle, "", w.process, w.process_id, w.minimized)
                                for w in windows)
            self._snapshot = Snapshot(
                foreground=foreground, windows=windows,
                clipboard_kind="hidden" if privacy else self._clipboard_kind(),
                power=power, online=online, privacy=privacy,
                language=self._language(), taken_at=now,
            )
            return self._snapshot

    # ----------------------------------------------------------- remembering

    def note_action(self, action: str, succeeded: bool, message: str = "", **referents) -> None:
        """Record what just happened so follow-ups can refer back to it."""
        self.referents.note(action=action, **referents)
        if not succeeded:
            self.referents.failure = message

    def note_target(self, **referents) -> None:
        self.referents.note(**referents)

    # ------------------------------------------------------------- resolving

    def resolve_window(self, hint: str = "") -> WindowInfo | None:
        """Which window a request means.

        A named window wins over the foreground one, and the assistant's own
        window is never the answer: saying "close this" while looking at
        J.A.R.V.I.S means the thing behind it.
        """
        snapshot = self.snapshot()
        if hint:
            named = snapshot.window_matching(hint)
            if named:
                return named
        foreground = snapshot.foreground
        if foreground.present and not self.is_own_window(foreground):
            return foreground
        if self.referents.window and self.referents.window.present:
            return self.referents.window
        for window in snapshot.windows:
            if not self.is_own_window(window):
                return window
        return None

    @staticmethod
    def is_own_window(window: WindowInfo) -> bool:
        title = (window.title or "").lower()
        process = (window.process or "").lower()
        return "j.a.r.v.i.s" in title or process in {"python.exe", "pythonw.exe", "jarvis-mark-7.exe"}

    def resolve_folder(self) -> Path | None:
        """The folder a request like "open the folder this file is in" means."""
        if self.referents.folder and self.referents.folder.exists():
            return self.referents.folder
        if self.referents.file:
            parent = self.referents.file.parent
            if parent.exists():
                return parent
        return None

    def describe(self) -> str:
        """A short, human-readable statement of the current context."""
        snapshot = self.snapshot()
        if snapshot.privacy:
            return "Privacy mode is on, so I am not reading window titles."
        window = snapshot.foreground
        if not window.present:
            return "Nothing appears to be in the foreground."
        name = window.title or window.process or "an untitled window"
        return f"You are in {name}."

    def health(self) -> dict[str, str]:
        """Diagnostics, as every subsystem is required to expose."""
        try:
            snapshot = self.snapshot(refresh=True)
        except Exception as error:
            return {"status": "FAILED", "detail": str(error)}
        if not snapshot.foreground.present and not snapshot.windows:
            return {"status": "DEGRADED", "detail": "No windows are visible to the observer."}
        return {
            "status": "OK",
            "detail": f"{len(snapshot.windows)} window(s), foreground "
                      f"{snapshot.foreground.process or 'unknown'}",
        }


def home_relative(path: Path, home: Path | None = None) -> str:
    """Show a path the way a person would say it."""
    home = home or Path.home()
    try:
        return str(path.relative_to(home))
    except ValueError:
        return str(path)


def working_directory() -> Path:
    return Path(os.getcwd())
