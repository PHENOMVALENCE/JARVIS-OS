"""How much to say, and whether to say it out loud.

Every result was spoken in full, so "open Notepad" produced a spoken sentence
where a chime would do. That is what makes an assistant feel like a chatbot
bolted onto Windows rather than part of it.

The rule is simple: if you can see that it worked, do not narrate it. Opening
an application is visible; the window appears. A weather answer is not visible,
so it is spoken. Failures are always surfaced, because a silent failure is the
worst outcome of all.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Delivery(str, Enum):
    SILENT = "silent"          # nothing at all
    EARCON = "earcon"          # a tone, no words
    BRIEF = "brief"            # short line on screen, no speech
    SPOKEN = "spoken"          # short line, spoken
    FULL = "full"              # the whole answer, spoken and shown


@dataclass(frozen=True)
class Response:
    delivery: Delivery
    text: str
    earcon: str = ""

    @property
    def speaks(self) -> bool:
        return self.delivery in {Delivery.SPOKEN, Delivery.FULL}

    @property
    def shows(self) -> bool:
        return self.delivery in {Delivery.BRIEF, Delivery.SPOKEN, Delivery.FULL}


# Actions whose effect is visible on screen the moment they happen. Saying
# "I have opened Notepad" while Notepad is opening is pure noise.
SELF_EVIDENT = {
    "open_app", "open_folder", "open_containing_folder", "focus_window",
    "window_state", "context_window_state", "close_window", "close_app",
    "screenshot", "web_search", "notification", "work_mode", "type_text",
    "spotify_play", "media", "set_volume", "change_volume", "noop",
}

# Answers exist only in what is said, so they are always delivered in full.
INFORMATIONAL = {
    "current_time", "current_date", "calculate", "convert", "battery",
    "disk_space", "weather", "forecast", "web_research", "semantic_search",
    "read_screen", "analyze_screen", "now_playing", "describe_context",
    "read_clipboard", "list_reminders", "show_problems", "inspect_ui",
}


class ResponsePolicy:
    """Decides how a result should reach the user."""

    def __init__(self, settings_repo=None):
        self.settings_repo = settings_repo

    def _terse(self) -> bool:
        return not self.settings_repo or bool(self.settings_repo.get("terse_responses", True))

    def _speaks(self, default: bool = True) -> bool:
        if not self.settings_repo:
            return default
        return bool(self.settings_repo.get("speak_responses", default))

    def for_action(self, action: str, succeeded: bool, message: str,
                   spoken_request: bool = False) -> Response:
        """How to report the outcome of a typed action."""
        if not succeeded:
            # Never quiet about failure, and never only a tone: the user needs
            # to know what happened and what to do next.
            return Response(Delivery.SPOKEN if self._speaks() else Delivery.BRIEF,
                            message, earcon="error")
        if not self._terse():
            return Response(Delivery.FULL if self._speaks() else Delivery.BRIEF, message)
        if action in INFORMATIONAL:
            return Response(Delivery.FULL if self._speaks() else Delivery.BRIEF, message)
        if action in SELF_EVIDENT:
            # Confirm by tone when the request was spoken and the user may be
            # looking elsewhere; stay silent when they are watching the screen.
            if spoken_request:
                return Response(Delivery.EARCON, message, earcon="done")
            return Response(Delivery.BRIEF, message)
        return Response(Delivery.SPOKEN if self._speaks() else Delivery.BRIEF, message)

    def for_conversation(self) -> Response:
        """Model replies are the answer itself, so they are always delivered."""
        return Response(Delivery.FULL if self._speaks() else Delivery.BRIEF, "")
