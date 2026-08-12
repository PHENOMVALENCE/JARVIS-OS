"""What each action is, and what it promises.

Action metadata was spread across three files: a pattern in the router, a
handler in the actions dict, and a name in the settings permission list. The
lists had already drifted — several actions could not be permission-configured
because nobody had added them to the third place.

One registry now describes every capability. The permissions screen, the
planner, and diagnostics read from it instead of keeping their own copies, and
plugins can register their actions at runtime.

A capability also states how success is checked. Returning without raising is
not evidence that anything happened: a close request can be ignored, a file can
fail to move. Where a check is cheap and meaningful, it is declared here and
run after the action.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .commands import Risk


@dataclass(frozen=True)
class Capability:
    """One thing J.A.R.V.I.S can do."""

    action: str
    summary: str
    risk: Risk = Risk.LOW
    permissions: tuple[str, ...] = ()
    reversible: bool = False
    local_only: bool = True
    # Cloud-backed capabilities are unavailable in privacy mode and when offline.
    needs_network: bool = False
    # Checked after execution. Returns (verified, detail); a capability with no
    # verifier is reported as unverified rather than as verified.
    verifier: Callable[[dict, Any], tuple[bool, str]] | None = None
    owner: str = "core"
    version: str = "1.0"
    parameters: tuple[str, ...] = ()

    @property
    def confirmation(self) -> str:
        if self.risk is Risk.HIGH:
            return "always"
        return "conditional" if self.risk is Risk.MEDIUM else "never"

    @property
    def verifiable(self) -> bool:
        return self.verifier is not None


class CapabilityRegistry:
    """The set of known capabilities, extensible by plugins."""

    def __init__(self):
        self._items: dict[str, Capability] = {}

    def register(self, capability: Capability, replace: bool = False) -> None:
        if capability.action in self._items and not replace:
            raise ValueError(f"{capability.action} is already registered")
        self._items[capability.action] = capability

    def get(self, action: str) -> Capability | None:
        return self._items.get(action)

    def risk_of(self, action: str, default: Risk = Risk.LOW) -> Risk:
        capability = self.get(action)
        return capability.risk if capability else default

    def actions(self) -> tuple[str, ...]:
        return tuple(sorted(self._items))

    def all(self) -> tuple[Capability, ...]:
        return tuple(self._items[name] for name in self.actions())

    def requiring_network(self) -> tuple[str, ...]:
        return tuple(name for name in self.actions() if self._items[name].needs_network)

    def unverified(self) -> tuple[str, ...]:
        """Capabilities that still take success on trust, for diagnostics."""
        return tuple(name for name in self.actions() if not self._items[name].verifiable)

    def describe(self, action: str) -> dict[str, Any]:
        capability = self.get(action)
        if capability is None:
            return {}
        return {
            "action": capability.action,
            "summary": capability.summary,
            "risk": capability.risk.value,
            "confirmation": capability.confirmation,
            "permissions": list(capability.permissions),
            "reversible": capability.reversible,
            "local_only": capability.local_only,
            "needs_network": capability.needs_network,
            "verified": capability.verifiable,
            "owner": capability.owner,
            "version": capability.version,
        }


# --------------------------------------------------------------- verifiers

def _verify_path_gone(arguments: dict, result: Any) -> tuple[bool, str]:
    from pathlib import Path

    path = (result.data or {}).get("path") if getattr(result, "data", None) else None
    if not path:
        return True, "no path recorded to check"
    return (not Path(path).exists(), f"{path} still exists")


def _verify_path_exists(arguments: dict, result: Any) -> tuple[bool, str]:
    from pathlib import Path

    path = (result.data or {}).get("path") if getattr(result, "data", None) else None
    if not path:
        return True, "no path recorded to check"
    return (Path(path).exists(), f"{path} was not created")


def _verify_matches_found(arguments: dict, result: Any) -> tuple[bool, str]:
    matches = (result.data or {}).get("matches") if getattr(result, "data", None) else None
    return (bool(matches), "no results were returned")


CORE: tuple[Capability, ...] = (
    # Windows control
    Capability("open_app", "Open an installed application", Risk.LOW, ("apps.launch",),
               parameters=("name",)),
    Capability("open_folder", "Open a folder in Explorer", Risk.LOW, ("files.read",),
               verifier=_verify_path_exists, parameters=("path",)),
    Capability("close_app", "Close a known application", Risk.MEDIUM, ("apps.close",),
               parameters=("name",)),
    Capability("close_window", "Close the window in front of you", Risk.MEDIUM, ("apps.close",)),
    Capability("focus_window", "Bring a window to the front", Risk.LOW, ("apps.focus",),
               parameters=("title",)),
    Capability("window_state", "Minimise, maximise, or restore a named window", Risk.LOW,
               ("apps.focus",), parameters=("operation", "title")),
    Capability("context_window_state", "Minimise, maximise, or restore the current window",
               Risk.LOW, ("apps.focus",), parameters=("operation",)),
    Capability("work_mode", "Open your configured working applications", Risk.LOW, ("apps.launch",)),

    # Files
    Capability("find_files", "Find files by name", Risk.LOW, ("files.read",),
               verifier=_verify_matches_found, parameters=("query",)),
    Capability("delete_path", "Move a file or folder to the Recycle Bin", Risk.HIGH,
               ("files.write",), reversible=True, verifier=_verify_path_gone,
               parameters=("path",)),
    # Restorative, and it refuses when something already occupies the path, so
    # it cannot overwrite anything. Confirming a request to undo would be noise.
    Capability("undo_delete", "Restore the last item sent to the Recycle Bin", Risk.LOW,
               ("files.write",), reversible=False),
    Capability("open_containing_folder", "Open the folder holding the last file", Risk.LOW,
               ("files.read",)),

    # Input and screen
    Capability("type_text", "Type into the focused application", Risk.MEDIUM, ("input.type",),
               parameters=("text",)),
    Capability("copy_clipboard", "Put text on the clipboard", Risk.LOW, ("clipboard.write",),
               parameters=("text",)),
    Capability("read_clipboard", "Read the clipboard", Risk.LOW, ("clipboard.read",)),
    Capability("screenshot", "Capture the screen to a file", Risk.MEDIUM, ("screen.capture",),
               verifier=_verify_matches_found),
    Capability("read_screen", "Read text off the screen on this device", Risk.MEDIUM,
               ("screen.capture",), verifier=_verify_matches_found, parameters=("query",)),
    Capability("analyze_screen", "Describe the screen using a cloud vision model", Risk.MEDIUM,
               ("screen.capture", "cloud.vision"), local_only=False, needs_network=True,
               parameters=("prompt",)),
    Capability("inspect_ui", "Read the controls of a window", Risk.LOW, ("ui.read",),
               parameters=("window",)),
    Capability("invoke_ui", "Press a control in another application", Risk.MEDIUM, ("ui.invoke",),
               parameters=("window", "control")),
    Capability("set_ui_text", "Type into a control in another application", Risk.MEDIUM,
               ("ui.invoke", "input.type"), parameters=("window", "control", "text")),
    Capability("select_ui", "Select an item in another application", Risk.MEDIUM, ("ui.invoke",),
               parameters=("window", "item")),

    # Sound and media
    Capability("set_volume", "Set the system volume", Risk.LOW, ("audio.control",),
               parameters=("level",)),
    Capability("change_volume", "Adjust the system volume", Risk.LOW, ("audio.control",),
               parameters=("delta",)),
    Capability("media", "Play, pause, or skip", Risk.LOW, ("audio.control",),
               parameters=("operation",)),
    Capability("spotify_play", "Play something on Spotify", Risk.LOW, ("audio.control",),
               local_only=False, parameters=("query",)),
    Capability("now_playing", "Say what is playing", Risk.LOW, ("audio.control",),
               local_only=False),

    # Answers
    Capability("web_search", "Open browser results", Risk.LOW, ("web.browse",),
               local_only=False, needs_network=True, parameters=("query",)),
    Capability("web_research", "Answer from live sources with citations", Risk.LOW, ("web.read",),
               local_only=False, needs_network=True, verifier=_verify_matches_found,
               parameters=("query",)),
    Capability("weather", "Current weather", Risk.LOW, ("web.read",), local_only=False,
               needs_network=True, parameters=("place",)),
    Capability("forecast", "Weather over the coming days", Risk.LOW, ("web.read",),
               local_only=False, needs_network=True, parameters=("place",)),
    Capability("semantic_search", "Search your indexed documents", Risk.LOW, ("files.read",),
               verifier=_verify_matches_found, parameters=("query",)),
    Capability("index_documents", "Index your configured folders", Risk.MEDIUM, ("files.read",)),

    # Instant local facts
    Capability("current_time", "The time", Risk.LOW),
    Capability("current_date", "The date", Risk.LOW),
    Capability("calculate", "Arithmetic", Risk.LOW, parameters=("expression",)),
    Capability("convert", "Unit and temperature conversion", Risk.LOW,
               parameters=("value", "source", "target")),
    Capability("battery", "Battery state", Risk.LOW),
    Capability("disk_space", "Free disk space", Risk.LOW),
    Capability("describe_context", "Say what you are looking at", Risk.LOW, ("screen.read",)),

    # Reminders and housekeeping
    Capability("add_reminder", "Set a reminder", Risk.LOW, ("reminders.write",),
               reversible=True, parameters=("text",)),
    Capability("list_reminders", "List your reminders", Risk.LOW, ("reminders.read",)),
    Capability("clear_reminders", "Cancel all reminders", Risk.MEDIUM, ("reminders.write",)),
    Capability("notification", "Show a message on screen", Risk.LOW, ("notify.show",),
               parameters=("message",)),
    Capability("show_problems", "Report recent failures", Risk.LOW),
    Capability("run_health", "Check every subsystem", Risk.LOW,
               verifier=_verify_matches_found),

    # Software management
    Capability("install_package", "Install software with winget", Risk.HIGH, ("packages.install",),
               local_only=False, needs_network=True, parameters=("package_id",)),
    Capability("upgrade_package", "Upgrade software with winget", Risk.HIGH, ("packages.install",),
               local_only=False, needs_network=True, parameters=("package_id",)),

    Capability("noop", "Do nothing", Risk.LOW),
)


def build_registry(extra: tuple[Capability, ...] = ()) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    for capability in CORE + tuple(extra):
        registry.register(capability, replace=True)
    return registry
