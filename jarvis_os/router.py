"""Deterministic natural-language routing for local PC actions."""

from __future__ import annotations

import re
from urllib.parse import quote_plus

from .commands import Command, Risk


WAKE_NAME = re.compile(
    r"""^\s*
    (?:(?:hey|hi|hello|ok|okay|yo)\s+)?      # optional greeting
    (?:j\.?\s?a\.?\s?r\.?\s?v\.?\s?i\.?\s?s|jarvis|jervis|javis|jarviss)
    \s*[,:.!?-]*\s*                            # trailing punctuation after the name
    """,
    re.IGNORECASE | re.VERBOSE,
)

LEAD_IN = re.compile(
    r"""^\s*
    (?:
        please
      | (?:can|could|would|will)\s+you(?:\s+please)?
      | i\s+(?:want|need)\s+you\s+to
      | i\s+(?:want|need)\s+to
      | go\s+ahead\s+and
      | for\s+me
    )
    [\s,]+
    """,
    re.IGNORECASE | re.VERBOSE,
)

TRAILING_POLITENESS = re.compile(r"[\s,]*\b(?:please|for me|thanks|thank you)\b[\s.!?]*$", re.IGNORECASE)


def strip_wake_name(text: str) -> str:
    """Remove a leading 'Jarvis'/'Hey Jarvis' address and surrounding politeness.

    Spoken commands almost always begin with the assistant's name. Without this the
    name becomes part of the command text and every request falls through to chat.
    """
    value = str(text).strip()
    previous = None
    while previous != value:
        previous = value
        value = WAKE_NAME.sub("", value, count=1).strip()
        value = LEAD_IN.sub("", value, count=1).strip()
    return TRAILING_POLITENESS.sub("", value).strip() or str(text).strip()


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
        raw = strip_wake_name(text)
        normalized = re.sub(r"\s+", " ", raw.lower()).strip(" .!?")
        if not normalized:
            return Command("noop", raw_text=raw)

        # Grounded spoken answer from live sources.
        match = re.match(
            r"""(?:research
                |look\s+(?:it\s+|this\s+|that\s+)?up
                |look\s+up
                |find\s+out(?:\s+about)?
                |search\s+online(?:\s+for)?
                |search\s+the\s+net(?:\s+for)?
                |answer\s+from\s+(?:the\s+)?(?:web|internet)
                |explain\s+from\s+(?:the\s+)?(?:web|internet)
                |what\s+does\s+the\s+(?:web|internet)\s+say\s+about
                |check\s+(?:the\s+)?(?:web|internet|online)\s+for
            )\s+(.+)""",
            normalized,
            re.VERBOSE,
        )
        if match:
            return Command("web_research", {"query": match.group(1)}, raw_text=raw)

        # Explicitly asking for browser results rather than a spoken answer.
        match = re.match(
            r"(?:search (?:the )?(?:web|internet|google) for"
            r"|google"
            r"|(?:open|show(?: me)?) (?:the )?(?:google |web |browser )?(?:search )?results for"
            r"|browse for)\s+(.+)",
            normalized,
        )
        if match:
            return Command("web_search", {"query": match.group(1)}, raw_text=raw)

        if normalized in {"index my documents", "update document index", "index documents"}:
            return Command("index_documents", risk=Risk.MEDIUM, raw_text=raw)

        match = re.match(r"(?:search|find) (?:my )?(?:documents|knowledge|files) for\s+(.+)", normalized)
        if match:
            return Command("semantic_search", {"query": match.group(1)}, raw_text=raw)

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

        match = re.match(r"install package\s+([a-z0-9._-]+)", normalized)
        if match:
            return Command("install_package", {"package_id": match.group(1)}, Risk.HIGH, raw)

        match = re.match(r"(?:upgrade|update) package\s+([a-z0-9._-]+)", normalized)
        if match:
            return Command("upgrade_package", {"package_id": match.group(1)}, Risk.HIGH, raw)

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
            return Command("screenshot", risk=Risk.MEDIUM, raw_text=raw)

        match = re.match(r"(?:what(?:'s| is) on (?:my |the )?screen|analyze (?:my |the )?screen|describe (?:my |the )?screen)(?:\s+(.+))?", normalized)
        if match:
            prompt = match.group(1) or "Describe the visible screen and identify important text and controls."
            return Command("analyze_screen", {"prompt": prompt}, Risk.MEDIUM, raw)

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
