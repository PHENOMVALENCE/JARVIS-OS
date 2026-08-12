"""A read-through cache in front of the settings table.

Settings are read from SQLite on every call, which costs about 0.77 ms. That is
irrelevant once per request and expensive per streamed token: rendering a reply
calls `speak_responses` once per chunk, so a long answer performed hundreds of
database opens on the UI thread.

Reads come from memory; writes go straight through and refresh the entry, so a
value changed in Settings takes effect immediately rather than after a restart.
"""

from __future__ import annotations

import threading
from typing import Any


class CachedSettings:
    """Wraps a SettingsRepository with the same interface."""

    def __init__(self, repository):
        self._repository = repository
        self._values: dict[str, Any] = {}
        self._loaded = False
        self._lock = threading.RLock()

    # The repository's defaults are part of the public surface; callers such as
    # the settings import screen validate keys against them.
    @property
    def DEFAULTS(self) -> dict[str, Any]:  # noqa: N802 - mirrors the wrapped class
        return self._repository.DEFAULTS

    @property
    def database(self):
        return self._repository.database

    def _ensure(self) -> None:
        if not self._loaded:
            self._values = self._repository.all()
            self._loaded = True

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            self._ensure()
            if key in self._values:
                return self._values[key]
        return self._repository.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._repository.set(key, value)
        with self._lock:
            self._ensure()
            self._values[key] = value

    def all(self) -> dict[str, Any]:
        with self._lock:
            self._ensure()
            return dict(self._values)

    def export_safe(self) -> dict[str, Any]:
        return self._repository.export_safe()

    def refresh(self) -> None:
        """Drop the cache. Used after a bulk change such as a settings import."""
        with self._lock:
            self._values = {}
            self._loaded = False
