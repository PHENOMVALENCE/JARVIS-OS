"""Deterministic natural-language routing for local PC actions."""

from __future__ import annotations

import re
from urllib.parse import quote_plus

from .commands import Command, Risk


class CommandRouter:
    """Route common commands locally and leave general conversation to the LLM."""

    _FOLDERS = {
        "desktop": "Desktop",
        "documents": "Documents",
        "downloads": "Downloads",
        "music": "Music",
        "pictures": "Pictures",
        "videos": "Videos",
        "home": "~",
    }

    def route(self, text: str) -> Command:
        raw = text.strip()
        normalized = re.sub(r"\s+", " ", raw.lower()).strip(" .!?")
        if not normalized:
            return Command("noop", raw_text=raw)

        match = re.match(r"(?:search (?:the )?(?:web|internet|google) for|google)\s+(.+)", normalized)
        if match:
            return Command("web_search", {"query": match.group(1)}, raw_text=raw)

        match = re.match(r"(?:open|show)\s+(?:my\s+)?(.+?)\s+folder$", normalized)
        if match:
            return Command("open_folder", {"path": self._folder(match.group(1))}, raw_text=raw)

        match = re.match(r"(?:open|show)\s+(desktop|documents|downloads|music|pictures|videos|home)$", normalized)
        if match:
            return Command("open_folder", {"path": self._folder(match.group(1))}, raw_text=raw)

        match = re.match(r"(?:find|search for|locate)\s+(?:the\s+)?(?:file\s+)?(.+)", normalized)
        if match:
            return Command("find_files", {"query": match.group(1)}, raw_text=raw)

        if normalized in {"start work mode", "begin work mode", "work mode"}:
            return Command("work_mode", raw_text=raw)

        match = re.match(r"(?:open|launch|start)\s+(.+)", normalized)
        if match:
            return Command("open_app", {"name": match.group(1)}, raw_text=raw)

        match = re.match(r"(?:play|listen to)\s+(.+?)(?:\s+on spotify)?$", normalized)
        if match and match.group(1) not in {"music", "spotify"}:
            return Command("spotify_play", {"query": match.group(1)}, raw_text=raw)

        media = {
            "pause": "pause", "pause music": "pause", "resume": "play",
            "resume music": "play", "next song": "next", "skip": "next",
            "previous song": "previous", "go back": "previous",
        }
        if normalized in media:
            return Command("media", {"operation": media[normalized]}, raw_text=raw)

        match = re.match(r"(?:set )?(?:the )?volume(?: to)?\s+(\d{1,3})(?: percent|%)?", normalized)
        if match:
            return Command("set_volume", {"level": min(100, int(match.group(1)))}, raw_text=raw)

        if normalized in {"volume up", "turn it up"}:
            return Command("change_volume", {"delta": 10}, raw_text=raw)
        if normalized in {"volume down", "turn it down"}:
            return Command("change_volume", {"delta": -10}, raw_text=raw)

        if normalized in {"take a screenshot", "take screenshot", "capture the screen", "screenshot"}:
            return Command("screenshot", raw_text=raw)

        match = re.match(r"(?:read|inspect)\s+(?:the\s+)?(.+?)\s+window$", normalized)
        if match:
            return Command("inspect_ui", {"window": match.group(1)}, raw_text=raw)

        match = re.match(r"(?:click|press|activate)\s+(.+?)\s+in\s+(.+)", normalized)
        if match:
            return Command("invoke_ui", {"control": match.group(1), "window": match.group(2)}, Risk.MEDIUM, raw)

        match = re.match(r"(?:enter|set)\s+(.+?)\s+in\s+(.+?)\s+(?:field|box)\s+in\s+(.+)", normalized)
        if match:
            return Command(
                "set_ui_text", {"text": match.group(1), "control": match.group(2), "window": match.group(3)},
                Risk.MEDIUM, raw,
            )

        match = re.match(r"select\s+(.+?)\s+in\s+(.+)", normalized)
        if match:
            return Command("select_ui", {"item": match.group(1), "window": match.group(2)}, Risk.MEDIUM, raw)

        if normalized in {"read clipboard", "what is on my clipboard", "show clipboard"}:
            return Command("read_clipboard", raw_text=raw)

        match = re.match(r"(?:switch to|focus|bring up)\s+(.+)", normalized)
        if match:
            return Command("focus_window", {"title": match.group(1)}, raw_text=raw)

        match = re.match(r"(minimize|maximize|restore)\s+(.+)", normalized)
        if match:
            return Command("window_state", {"operation": match.group(1), "title": match.group(2)}, raw_text=raw)

        match = re.match(r"(?:type|enter)\s+(.+)", normalized)
        if match:
            return Command("type_text", {"text": match.group(1)}, Risk.MEDIUM, raw)

        match = re.match(r"(?:show|display) notification\s+(.+)", normalized)
        if match:
            return Command("notification", {"message": match.group(1)}, raw_text=raw)

        match = re.match(r"(?:copy|put)\s+(.+?)(?:\s+to (?:the )?clipboard)?$", normalized)
        if match:
            return Command("copy_clipboard", {"text": match.group(1)}, raw_text=raw)

        match = re.match(r"(?:close|quit|terminate)\s+(.+)", normalized)
        if match:
            return Command("close_app", {"name": match.group(1)}, Risk.MEDIUM, raw)

        match = re.match(r"(?:delete|remove)\s+(?:the\s+)?(?:file|folder)?\s*(.+)", normalized)
        if match:
            return Command("delete_path", {"path": match.group(1)}, Risk.HIGH, raw)

        return Command("chat", {"message": raw}, raw_text=raw)

    @classmethod
    def _folder(cls, value: str) -> str:
        cleaned = value.strip().lower()
        return cls._FOLDERS.get(cleaned, value.strip())


def browser_search_url(query: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(query)}"
