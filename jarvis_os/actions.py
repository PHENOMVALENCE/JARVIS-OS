"""Permission-friendly Windows actions used by the desktop assistant."""

from __future__ import annotations

import ctypes
import os
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from .commands import ActionResult, Command
from .router import browser_search_url


APP_ALIASES = {
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "command prompt": "cmd.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "powershell": "powershell.exe",
    "settings": "ms-settings:",
    "spotify": "spotify:",
    "task manager": "taskmgr.exe",
    "terminal": "wt.exe",
}

PROCESS_ALIASES = {
    "calculator": "CalculatorApp.exe",
    "calc": "CalculatorApp.exe",
    "notepad": "Notepad.exe",
    "paint": "mspaint.exe",
    "spotify": "Spotify.exe",
    "terminal": "WindowsTerminal.exe",
}

KNOWN_FOLDERS = {name.lower(): name for name in (
    "Desktop", "Documents", "Downloads", "Music", "Pictures", "Videos"
)}


class WindowsActions:
    def __init__(self, home: Path | None = None, *, data_dir: Path | None = None, settings_repo=None, openai_api_key: str = ""):
        self.home = (home or Path.home()).resolve()
        self.data_dir = data_dir or Path(__file__).resolve().parent.parent / "data"
        self.settings_repo = settings_repo
        self.openai_api_key = openai_api_key
        self._handlers: dict[str, Callable[[dict], ActionResult]] = {
            "noop": lambda _: ActionResult(True, "Nothing to do."),
            "open_folder": self.open_folder,
            "open_app": self.open_app,
            "web_search": self.web_search,
            "find_files": self.find_files,
            "spotify_play": self.spotify_play,
            "media": self.media,
            "set_volume": self.set_volume,
            "change_volume": self.change_volume,
            "copy_clipboard": self.copy_clipboard,
            "close_app": self.close_app,
            "delete_path": self.delete_path,
            "screenshot": self.screenshot,
            "read_clipboard": self.read_clipboard,
            "focus_window": self.focus_window,
            "window_state": self.window_state,
            "type_text": self.type_text,
            "notification": self.notification,
            "work_mode": self.work_mode,
            "inspect_ui": self.inspect_ui,
            "invoke_ui": self.invoke_ui,
            "set_ui_text": self.set_ui_text,
            "select_ui": self.select_ui,
            "analyze_screen": self.analyze_screen,
        }

    def execute(self, command: Command) -> ActionResult:
        handler = self._handlers.get(command.action)
        if not handler:
            return ActionResult(False, f"Unsupported action: {command.action}")
        try:
            return handler(command.arguments)
        except Exception as exc:
            return ActionResult(False, f"{command.action} failed: {exc}")

    def _resolve_path(self, value: str) -> Path:
        value = value.strip().strip('"')
        if value == "~":
            return self.home
        known = KNOWN_FOLDERS.get(value.lower())
        if known:
            return self.home / known
        candidate = Path(os.path.expandvars(os.path.expanduser(value)))
        return candidate if candidate.is_absolute() else self.home / candidate

    def open_folder(self, args: dict) -> ActionResult:
        path = self._resolve_path(str(args["path"]))
        if not path.is_dir():
            return ActionResult(False, f"Folder not found: {path}")
        os.startfile(str(path))
        return ActionResult(True, f"Opened {path.name or path}.", {"path": str(path)})

    def open_app(self, args: dict) -> ActionResult:
        name = str(args["name"]).strip().lower()
        target = APP_ALIASES.get(name)
        if target:
            os.startfile(target)
            return ActionResult(True, f"Opened {name}.")
        shortcut = self._find_start_menu_shortcut(name)
        if shortcut:
            os.startfile(str(shortcut))
            return ActionResult(True, f"Opened {shortcut.stem}.")
        return ActionResult(False, f"I could not find an installed app named {name}.")

    @staticmethod
    def _find_start_menu_shortcut(name: str) -> Path | None:
        roots = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        ]
        wanted = name.replace(" ", "")
        matches: list[Path] = []
        for root in roots:
            if root.is_dir():
                matches.extend(p for p in root.rglob("*.lnk") if wanted in p.stem.lower().replace(" ", ""))
        return min(matches, key=lambda p: len(p.stem), default=None)

    @staticmethod
    def web_search(args: dict) -> ActionResult:
        query = str(args["query"]).strip()
        webbrowser.open(browser_search_url(query))
        return ActionResult(True, f"Searching the web for {query}.")

    def find_files(self, args: dict) -> ActionResult:
        query = str(args["query"]).lower().strip("* ")
        if not query:
            return ActionResult(False, "Please provide a file name to search for.")
        matches: list[str] = []
        for root, dirs, files in os.walk(self.home):
            dirs[:] = [d for d in dirs if d not in {".git", ".venv", "node_modules", "AppData"}]
            for name in [*dirs, *files]:
                if query in name.lower():
                    matches.append(str(Path(root) / name))
                    if len(matches) == 50:
                        break
            if len(matches) == 50:
                break
        message = f"Found {len(matches)} matching item(s)." if matches else f"No files matched {query}."
        return ActionResult(bool(matches), message, {"matches": matches})

    @staticmethod
    def spotify_play(args: dict) -> ActionResult:
        query = str(args["query"]).strip()
        os.startfile(f"spotify:search:{quote(query)}")
        return ActionResult(True, f"Opened Spotify results for {query}.")

    @staticmethod
    def media(args: dict) -> ActionResult:
        keys = {"next": 0xB0, "previous": 0xB1, "pause": 0xB3, "play": 0xB3}
        operation = str(args["operation"])
        virtual_key = keys.get(operation)
        if virtual_key is None:
            return ActionResult(False, f"Unknown media operation: {operation}")
        ctypes.windll.user32.keybd_event(virtual_key, 0, 0, 0)
        ctypes.windll.user32.keybd_event(virtual_key, 0, 2, 0)
        return ActionResult(True, f"Media {operation} command sent.")

    @staticmethod
    def _volume_endpoint():
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        device = AudioUtilities.GetSpeakers()
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return interface.QueryInterface(IAudioEndpointVolume)

    def set_volume(self, args: dict) -> ActionResult:
        level = max(0, min(100, int(args["level"])))
        self._volume_endpoint().SetMasterVolumeLevelScalar(level / 100, None)
        return ActionResult(True, f"Volume set to {level} percent.")

    def change_volume(self, args: dict) -> ActionResult:
        endpoint = self._volume_endpoint()
        level = max(0, min(100, round(endpoint.GetMasterVolumeLevelScalar() * 100 + int(args["delta"]))))
        endpoint.SetMasterVolumeLevelScalar(level / 100, None)
        return ActionResult(True, f"Volume set to {level} percent.")

    @staticmethod
    def copy_clipboard(args: dict) -> ActionResult:
        text = str(args["text"])
        subprocess.run(["clip.exe"], input=text, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return ActionResult(True, "Copied text to the clipboard.")

    @staticmethod
    def close_app(args: dict) -> ActionResult:
        name = str(args["name"]).strip().lower()
        process = PROCESS_ALIASES.get(name)
        if not process:
            return ActionResult(False, "That app is not on the safe close list.")
        completed = subprocess.run(
            ["taskkill.exe", "/IM", process], capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if completed.returncode:
            return ActionResult(False, completed.stderr.strip() or f"Could not close {name}.")
        return ActionResult(True, f"Closed {name}.")

    def delete_path(self, args: dict) -> ActionResult:
        from send2trash import send2trash
        path = self._resolve_path(str(args["path"]))
        if not path.exists():
            return ActionResult(False, f"Path not found: {path}")
        if path == self.home or self.home not in path.parents:
            return ActionResult(False, "Deletion is limited to items inside your user folder.")
        send2trash(str(path))
        return ActionResult(True, f"Moved {path.name} to the Recycle Bin.")

    @staticmethod
    def _matching_window(title: str) -> int | None:
        user32 = ctypes.windll.user32
        matches: list[int] = []
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def inspect(handle, _extra):
            length = user32.GetWindowTextLengthW(handle)
            if length and user32.IsWindowVisible(handle):
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(handle, buffer, length + 1)
                if title.lower() in buffer.value.lower():
                    matches.append(handle)
            return True
        user32.EnumWindows(callback_type(inspect), 0)
        return matches[0] if matches else None

    def focus_window(self, args: dict) -> ActionResult:
        title = str(args["title"])
        handle = self._matching_window(title)
        if not handle:
            return ActionResult(False, f"No visible window matched {title}.")
        ctypes.windll.user32.ShowWindow(handle, 9)
        ctypes.windll.user32.SetForegroundWindow(handle)
        return ActionResult(True, f"Focused the {title} window.")

    def window_state(self, args: dict) -> ActionResult:
        title, operation = str(args["title"]), str(args["operation"])
        handle = self._matching_window(title)
        if not handle:
            return ActionResult(False, f"No visible window matched {title}.")
        codes = {"minimize": 6, "maximize": 3, "restore": 9}
        ctypes.windll.user32.ShowWindow(handle, codes[operation])
        return ActionResult(True, f"Set {title} window to {operation}.")

    def screenshot(self, _args: dict) -> ActionResult:
        from .screen import ScreenService
        return ScreenService(self.data_dir, self.settings_repo, self.openai_api_key).capture()

    def analyze_screen(self, args: dict) -> ActionResult:
        from .screen import ScreenService
        return ScreenService(self.data_dir, self.settings_repo, self.openai_api_key).capture(
            analyze=True, prompt=str(args.get("prompt", "Describe the visible screen and any important text or controls."))
        )

    @staticmethod
    def read_clipboard(_args: dict) -> ActionResult:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        text = completed.stdout.strip()
        if completed.returncode or not text:
            return ActionResult(False, "The clipboard is empty or could not be read.")
        return ActionResult(True, "Clipboard contents:", {"matches": [text]})

    @staticmethod
    def type_text(args: dict) -> ActionResult:
        from pynput.keyboard import Controller
        text = str(args["text"])
        Controller().type(text)
        return ActionResult(True, f"Typed {len(text)} character(s) into the active window.")

    @staticmethod
    def notification(args: dict) -> ActionResult:
        message = str(args["message"])
        ctypes.windll.user32.MessageBoxW(0, message, "J.A.R.V.I.S", 0x40)
        return ActionResult(True, "Notification displayed.")

    def work_mode(self, _args: dict) -> ActionResult:
        configured = os.getenv("JARVIS_WORK_APPS", "").strip()
        if not configured:
            return ActionResult(False, "Work mode is not configured. Set JARVIS_WORK_APPS in .env.")
        messages = []
        for app in (item.strip() for item in configured.split(",") if item.strip()):
            messages.append(self.open_app({"name": app}).message)
        return ActionResult(True, "Work mode started. " + " ".join(messages))

    @staticmethod
    def _automation():
        from .ui_automation import UIAutomationService
        return UIAutomationService()

    def inspect_ui(self, args: dict) -> ActionResult:
        return self._automation().read(str(args["window"]))

    def invoke_ui(self, args: dict) -> ActionResult:
        return self._automation().invoke(str(args["window"]), str(args["control"]))

    def set_ui_text(self, args: dict) -> ActionResult:
        return self._automation().set_text(str(args["window"]), str(args["control"]), str(args["text"]))

    def select_ui(self, args: dict) -> ActionResult:
        return self._automation().select(str(args["window"]), str(args["item"]))
