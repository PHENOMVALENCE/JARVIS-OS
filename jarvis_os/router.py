"""Deterministic natural-language routing for local PC actions."""

from __future__ import annotations

import re
from urllib.parse import quote_plus

from .commands import Command, Risk
from .facts import calculate, convert


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


_EXPLICIT_BROWSER_SEARCH = re.compile(
    r"^(?:search\s+(?:the\s+)?(?:web|internet|google)\s+for"
    r"|google\s"
    r"|browse\s+for"
    r"|(?:open|show(?:\s+me)?)\s+(?:the\s+)?.*results\s+for)\b",
    re.IGNORECASE,
)


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

        # Weather has its own free provider; encyclopedic search cannot answer it.
        # An explicit request for browser results still wins over the shortcut.
        wants_browser = _EXPLICIT_BROWSER_SEARCH.match(normalized)
        if not wants_browser and (
            re.search(r"\b(?:weather|forecast)\b", normalized)
            or re.match(r"(?:is|will) it (?:going to )?(?:rain|snow|be (?:hot|cold|warm|sunny))", normalized)
        ):
            place = ""
            location = re.search(
                r"\b(?:in|for|at)\s+(.+?)"
                r"(?:\s+(?:today|tonight|tomorrow|this week|next week|this weekend|right now))?$",
                normalized,
            )
            if location:
                place = location.group(1).strip()
            ahead = re.search(
                r"\bforecast\b|\bthis week\b|\bnext (?:few days|week)\b|\btomorrow\b|\bweekend\b|\bcoming days\b",
                normalized,
            )
            return Command("forecast" if ahead else "weather", {"place": place}, raw_text=raw)

        match = re.match(
            r"(?:read|what does)\s+(?:the\s+)?screen(?:\s+say)?(?:\s+(.+))?$"
            r"|read (?:the )?(?:text|words) on (?:my |the )?screen"
            r"|what does (?:it|this) say(?: on (?:my |the )?screen)?",
            normalized,
        )
        if match:
            return Command("read_screen", {"query": (match.group(1) or "").strip()}, Risk.MEDIUM, raw)

        # Questions the computer can answer exactly, with no model round trip.
        if re.fullmatch(r"(?:what(?:'s| is)\s+)?(?:the\s+)?time(?:\s+is\s+it)?|what time is it(?:\s+now)?|tell me the time", normalized):
            return Command("current_time", raw_text=raw)

        if re.fullmatch(
            r"(?:what(?:'s| is)\s+)?(?:the\s+|today'?s\s+)?date(?:\s+today)?"
            r"|what(?:'s| is) today(?:'s date)?|what day is it(?:\s+today)?|tell me the date",
            normalized,
        ):
            return Command("current_date", raw_text=raw)

        if re.search(r"\bbattery\b", normalized) and re.match(r"(?:what|how|check|tell|is|show)\b", normalized):
            return Command("battery", raw_text=raw)

        if re.search(r"\b(?:disk|drive|storage)\s+space\b|\bhow much (?:disk|drive|storage|space)\b|\bfree space\b", normalized):
            return Command("disk_space", raw_text=raw)

        match = re.match(
            r"(?:convert\s+)?([-\d.]+)\s*([a-z]+)\s+(?:in|to|into)\s+([a-z]+)$", normalized
        )
        if match and self._convertible(match.group(2), match.group(3)):
            return Command(
                "convert",
                {"value": float(match.group(1)), "source": match.group(2), "target": match.group(3)},
                raw_text=raw,
            )

        arithmetic = re.match(
            r"(?:what(?:'s| is)|calculate|compute|work out|how much is)\s+(.+)", normalized
        )
        candidate = arithmetic.group(1) if arithmetic else normalized
        if calculate(candidate) is not None:
            return Command("calculate", {"expression": candidate}, raw_text=raw)

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

    @staticmethod
    def _convertible(source: str, target: str) -> bool:
        return convert(1.0, source, target) is not None

    @classmethod
    def _folder(cls, value: str) -> str:
        cleaned = value.strip().lower()
        return cls._FOLDERS.get(cleaned, value.strip())


def browser_search_url(query: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(query)}"


# A local model answers from frozen training weights, so anything time-sensitive
# needs live sources instead. These patterns stay deliberately narrow: a false
# positive turns ordinary conversation into a search engine.
_RECENCY = re.compile(
    r"""\b(?:
        today|tonight|tomorrow|yesterday|right\s+now|currently|current|now
      | latest|newest|most\s+recent|recent|recently|so\s+far
      | this\s+(?:week|month|year|morning|afternoon|evening)
      | last\s+(?:night|week|month|year)
      | at\s+the\s+moment|these\s+days|nowadays|up[-\s]to[-\s]date
      | breaking|live|upcoming|still\s+(?:alive|open|running)
      | 20[2-9]\d
    )\b""",
    re.VERBOSE,
)

_VOLATILE = re.compile(
    r"""(?:
        \bweather\b|\bforecast\b|\btemperature\s+(?:in|at|of)\b
      | \bprice\s+of\b|\bhow\s+much\s+(?:is|are|does|do)\b|\bcost\s+of\b
      | \bstock\s+price\b|\bshare\s+price\b|\bexchange\s+rate\b|\bworth\s+now\b
      | \bwho\s+won\b|\bwho\s+is\s+winning\b|\bscore\s+(?:of|in|for)\b|\bfinal\s+score\b
      | \belection\s+results?\b|\bwho\s+is\s+the\s+(?:current\s+)?(?:president|prime\s+minister|ceo|champion)\b
      | \bnews\b|\bheadlines\b|\bwhat(?:'s|\s+is)\s+happening\b
      | \brelease\s+date\b|\bout\s+yet\b|\bwhen\s+(?:is|does)\s+.+\s+(?:release|launch|come\s+out)\b
    )""",
    re.VERBOSE,
)

_ASKING = re.compile(
    r"""^(?:
        who|what|whats|what's|when|where|which|why|how|is|are|was|were
      | do|does|did|can|could|should|will|would|has|have|any
      | tell\s+me|show\s+me|give\s+me|remind\s+me\s+what
    )\b""",
    re.VERBOSE,
)


def needs_live_information(text: str) -> bool:
    """True when a question depends on facts the local model cannot know.

    Explicit phrasings ("research X", "look up X") are handled by the router.
    This covers the questions people ask without thinking to say "search".
    """
    normalized = re.sub(r"\s+", " ", str(text).lower()).strip()
    if not normalized:
        return False
    asking = bool(_ASKING.match(normalized)) or normalized.endswith("?")
    if not asking:
        return False
    return bool(_VOLATILE.search(normalized)) or bool(_RECENCY.search(normalized))
