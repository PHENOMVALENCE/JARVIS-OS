"""Permission-friendly Windows actions used by the desktop assistant."""

from __future__ import annotations

import ctypes
import os
import subprocess
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from .commands import ActionResult, Command
from .context import SW_MAXIMIZE, SW_MINIMIZE, SW_RESTORE, ContextEngine
from .diagnostics_log import failure, recent_problems
from .facts import FactService
from .file_search import FileSearch
from .music import SpotifyControl
from .router import browser_search_url
from .weather import WeatherService
from .web_research import WebResearch


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
    def __init__(self, home: Path | None = None, *, data_dir: Path | None = None, settings_repo=None, openai_api_key: str = "", knowledge=None, web_research=None, weather=None, reminders=None, context=None):
        self.home = (home or Path.home()).resolve()
        self.data_dir = data_dir or Path(__file__).resolve().parent.parent / "data"
        self.settings_repo = settings_repo
        self.openai_api_key = openai_api_key
        self.knowledge = knowledge
        self.web_research_service = web_research or WebResearch()
        self.facts = FactService(self.home)
        self.file_search = FileSearch(self.home)
        self.weather_service = weather or WeatherService()
        self.last_deleted: Path | None = None
        self.reminders = reminders
        self.context = context or ContextEngine(settings_repo)
        self.music = SpotifyControl(self.data_dir / 'spotify-token.json')
        self._handlers: dict[str, Callable[[dict], ActionResult]] = {
            "noop": lambda _: ActionResult(True, "Nothing to do."),
            "open_folder": self.open_folder,
            "open_app": self.open_app,
            "web_search": self.web_search,
            "web_research": self.web_research,
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
            "index_documents": self.index_documents,
            "semantic_search": self.semantic_search,
            "install_package": self.install_package,
            "upgrade_package": self.upgrade_package,
            "current_time": self.facts.current_time,
            "current_date": self.facts.current_date,
            "calculate": self.facts.calculate,
            "convert": self.facts.convert,
            "battery": self.facts.battery,
            "disk_space": self.facts.disk_space,
            "weather": self.weather,
            "forecast": self.forecast,
            "read_screen": self.read_screen,
            "undo_delete": self.undo_delete,
            "show_problems": self.show_problems,
            "add_reminder": self.add_reminder,
            "list_reminders": self.list_reminders,
            "clear_reminders": self.clear_reminders,
            "now_playing": self.now_playing,
            "close_window": self.close_window,
            "context_window_state": self.context_window_state,
            "describe_context": self.describe_context,
            "open_containing_folder": self.open_containing_folder,
        }

    def execute(self, command: Command) -> ActionResult:
        handler = self._handlers.get(command.action)
        if not handler:
            return ActionResult(False, f"Unsupported action: {command.action}")
        try:
            result = handler(command.arguments)
        except Exception as exc:
            failure("action", exc, command.action)
            result = ActionResult(False, f"{command.action} failed: {exc}")
        # Remember what was acted on, so "that" and "again" have a referent.
        self.context.note_action(command.action, result.success, result.message)
        return result

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
        self.context.note_target(folder=path)
        return ActionResult(True, f"Opened {path.name or path}.", {"path": str(path)})

    def close_window(self, args: dict) -> ActionResult:
        """Close whatever the user means by "this", and confirm that it closed.

        A close request is sent to the window rather than killing the process,
        so the application can prompt about unsaved work.
        """
        window = self.context.resolve_window(str(args.get("hint", "")))
        if window is None:
            return ActionResult(False, "I could not tell which window you mean.")
        user32 = ctypes.windll.user32
        user32.PostMessageW(window.handle, 0x0010, 0, 0)  # WM_CLOSE
        name = window.title or window.process or "that window"
        # Verify rather than assuming the message was honoured.
        for _ in range(12):
            time.sleep(0.1)
            if not user32.IsWindow(window.handle):
                return ActionResult(True, f"Closed {name}.")
        return ActionResult(
            False, f"{name} did not close. It may be asking you about unsaved work."
        )

    def context_window_state(self, args: dict) -> ActionResult:
        """Minimise, maximise, or restore the window a request refers to."""
        operation = str(args["operation"])
        window = self.context.resolve_window(str(args.get("hint", "")))
        if window is None:
            return ActionResult(False, "I could not tell which window you mean.")
        codes = {"minimize": SW_MINIMIZE, "maximize": SW_MAXIMIZE, "restore": SW_RESTORE}
        ctypes.windll.user32.ShowWindow(window.handle, codes[operation])
        self.context.note_target(window=window)
        name = window.title or window.process or "that window"
        return ActionResult(True, f"{operation.title()}d {name}.")

    def describe_context(self, _args: dict) -> ActionResult:
        return ActionResult(True, self.context.describe())

    def open_containing_folder(self, _args: dict) -> ActionResult:
        """"Open the folder this file is in", using the last file referred to."""
        folder = self.context.resolve_folder()
        if folder is None:
            return ActionResult(False, "I do not have a recent file to work from.")
        os.startfile(str(folder))
        return ActionResult(True, f"Opened {folder.name or folder}.")

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

    def web_research(self, args: dict) -> ActionResult:
        query = str(args["query"]).strip()
        if not query:
            return ActionResult(False, "Please provide a topic to research.")
        try:
            results = self.web_research_service.search(query)
        except Exception as exc:
            return ActionResult(False, f"Web research failed: {exc}")
        passages = [item.passage() for item in results]
        if not passages:
            hint = "" if self.web_research_service.has_full_web_access else (
                " Without SERPAPI_API_KEY I can only reach encyclopedic sources, "
                "which do not cover current events well."
            )
            return ActionResult(False, f"I could not find reliable web results for {query}.{hint}")
        return ActionResult(True, f"Found {len(passages)} web sources for {query}.", {"matches": passages})

    def find_files(self, args: dict) -> ActionResult:
        query = str(args["query"]).strip()
        if not query:
            return ActionResult(False, "Please provide a file name to search for.")
        matches = self.file_search.search(query)
        message = f"Found {len(matches)} matching item(s)." if matches else f"No files matched {query}."
        return ActionResult(bool(matches), message, {"matches": matches})

    def weather(self, args: dict) -> ActionResult:
        return self._weather_answer(str(args.get("place", "")), forecast=False)

    def forecast(self, args: dict) -> ActionResult:
        return self._weather_answer(str(args.get("place", "")), forecast=True)

    def _weather_answer(self, place: str, forecast: bool) -> ActionResult:
        place = place.strip() or str(
            self.settings_repo.get("home_location", "") if self.settings_repo else ""
        ).strip()
        if not place:
            return ActionResult(
                False,
                "Tell me which place you mean, or set your home location in Settings.",
            )
        try:
            service = self.weather_service
            answer = service.forecast(place) if forecast else service.current(place)
        except Exception as exc:
            return ActionResult(False, f"I could not reach the weather service: {exc}")
        if not answer:
            return ActionResult(False, f"I could not find a place called {place}.")
        return ActionResult(True, answer)

    def add_reminder(self, args: dict) -> ActionResult:
        if not self.reminders:
            return ActionResult(False, "Reminders are unavailable.")
        succeeded, message = self.reminders.create(str(args.get("text", "")))
        return ActionResult(succeeded, message)

    def list_reminders(self, _args: dict) -> ActionResult:
        if not self.reminders:
            return ActionResult(False, "Reminders are unavailable.")
        pending = self.reminders.store.pending()
        if not pending:
            return ActionResult(True, "You have no reminders set.")
        from datetime import datetime as _datetime

        lines = []
        for due_at, message in pending:
            try:
                when = _datetime.fromisoformat(due_at).strftime("%a %I:%M %p").replace(" 0", " ")
            except ValueError:
                when = due_at
            lines.append(f"{when} - {message}")
        return ActionResult(True, f"You have {len(pending)} reminder(s).", {"matches": lines})

    def clear_reminders(self, _args: dict) -> ActionResult:
        if not self.reminders:
            return ActionResult(False, "Reminders are unavailable.")
        count = self.reminders.store.clear()
        return ActionResult(True, "Cleared all reminders." if count else "There were none to clear.")

    def show_problems(self, _args: dict) -> ActionResult:
        """Surface recent failures, which are otherwise only in the log file."""
        problems = recent_problems(self.data_dir)
        if not problems:
            return ActionResult(True, "Nothing has gone wrong recently.")
        return ActionResult(
            True, f"{len(problems)} recent problem(s). The full log is in {self.data_dir / 'logs'}.",
            {"matches": problems},
        )

    def read_screen(self, args: dict) -> ActionResult:
        """Extract on-screen text locally, with no cloud vision call."""
        if self.settings_repo and self.settings_repo.get("privacy_mode", False):
            return ActionResult(False, "Screen reading is blocked while privacy mode is enabled.")
        from PIL import ImageGrab

        from .ocr import ScreenTextReader

        reader = ScreenTextReader()
        if not reader.available():
            return ActionResult(False, "Windows OCR is not available for this user profile.")
        folder = self.data_dir / "screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"ocr-{datetime.now():%Y%m%d-%H%M%S}.png"
        ImageGrab.grab(all_screens=True).save(path)
        try:
            text = reader.summarize(reader.read(path))
        finally:
            path.unlink(missing_ok=True)
        if not text:
            return ActionResult(False, "I could not find any readable text on the screen.")
        query = str(args.get("query", "")).strip()
        message = f"Read {len(text.splitlines())} line(s) of on-screen text."
        return ActionResult(True, message, {"matches": [text], "query": query})

    def spotify_play(self, args: dict) -> ActionResult:
        """Start playback properly when Spotify is configured, else open it."""
        query = str(args["query"]).strip()
        succeeded, message = self.music.play_query(query)
        if message:
            return ActionResult(succeeded, message)
        os.startfile(f"spotify:search:{quote(query)}")
        return ActionResult(True, f"Opened Spotify results for {query}.")

    def now_playing(self, _args: dict) -> ActionResult:
        succeeded, message = self.music.now_playing()
        if message:
            return ActionResult(succeeded, message)
        return ActionResult(False, "Connect Spotify in .env to read the current track.")

    def media(self, args: dict) -> ActionResult:
        """Prefer the Spotify API, and fall back to the media keys.

        The media keys act on whatever last had focus, which is often the wrong
        application, so controlling Spotify directly is more predictable.
        """
        operation = str(args["operation"])
        succeeded, message = self.music.control(operation)
        if message:
            return ActionResult(succeeded, message)
        keys = {"next": 0xB0, "previous": 0xB1, "pause": 0xB3, "play": 0xB3}
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
        self.last_deleted = path
        return ActionResult(True, f"Moved {path.name} to the Recycle Bin. Say undo that to put it back.")

    # "Restore" as Windows spells it in a few common locales.
    _RESTORE_VERBS = {"restore", "undelete", "wiederherstellen", "restaurer", "restaurar", "ripristina"}

    def undo_delete(self, _args: dict) -> ActionResult:
        """Put back whatever was last moved to the Recycle Bin."""
        path = self.last_deleted
        if path is None:
            return ActionResult(False, "I have not deleted anything this session.")
        if path.exists():
            return ActionResult(True, f"{path.name} is already back in place.")
        try:
            import win32com.client
        except ImportError:
            return ActionResult(False, "Restoring needs pywin32. Open the Recycle Bin to restore it by hand.")
        try:
            recycle_bin = win32com.client.Dispatch("Shell.Application").Namespace(10)
            items = recycle_bin.Items()
            for index in range(items.Count):
                item = items.Item(index)
                if item.Name.lower() != path.name.lower():
                    continue
                for verb in item.Verbs():
                    if verb.Name.replace("&", "").strip().lower() in self._RESTORE_VERBS:
                        verb.DoIt()
                        self.last_deleted = None
                        return ActionResult(True, f"Restored {path.name}.")
        except Exception as exc:
            return ActionResult(False, f"I could not restore {path.name}: {exc}")
        return ActionResult(False, f"I could not find {path.name} in the Recycle Bin.")

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

    def index_documents(self, _args: dict) -> ActionResult:
        return self.knowledge.index_configured() if self.knowledge else ActionResult(False, "Knowledge index unavailable.")

    def semantic_search(self, args: dict) -> ActionResult:
        return self.knowledge.search(str(args["query"])) if self.knowledge else ActionResult(False, "Knowledge index unavailable.")

    @staticmethod
    def install_package(args: dict) -> ActionResult:
        package_id = str(args["package_id"]).strip()
        if not package_id or not all(character.isalnum() or character in ".-_" for character in package_id):
            return ActionResult(False, "Package IDs may contain only letters, numbers, dots, hyphens, and underscores.")
        completed = subprocess.run(
            ["winget", "install", "--id", package_id, "--exact", "--silent", "--accept-package-agreements", "--accept-source-agreements"],
            capture_output=True, text=True, timeout=900,
        )
        return ActionResult(completed.returncode == 0, completed.stdout.strip()[-1000:] or completed.stderr.strip()[-1000:])

    @staticmethod
    def upgrade_package(args: dict) -> ActionResult:
        package_id = str(args["package_id"]).strip()
        if not package_id or not all(character.isalnum() or character in ".-_" for character in package_id):
            return ActionResult(False, "Invalid package ID.")
        completed = subprocess.run(
            ["winget", "upgrade", "--id", package_id, "--exact", "--silent", "--accept-package-agreements", "--accept-source-agreements"],
            capture_output=True, text=True, timeout=900,
        )
        return ActionResult(completed.returncode == 0, completed.stdout.strip()[-1000:] or completed.stderr.strip()[-1000:])

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
        configured = self.settings_repo.get("work_apps", []) if self.settings_repo else []
        if not configured:
            configured = [item.strip() for item in os.getenv("JARVIS_WORK_APPS", "").split(",") if item.strip()]
        if not configured:
            return ActionResult(False, "Work mode is not configured. Set JARVIS_WORK_APPS in .env.")
        messages = []
        for app in configured:
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
