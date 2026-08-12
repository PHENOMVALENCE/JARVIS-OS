"""A place for failures to go.

The codebase catches broadly and carries on, which keeps the assistant alive
when a microphone or a network call misbehaves. Without a record, though, a
silent failure is indistinguishable from a feature that was never wired up.
Everything swallowed should at least be written down.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOGGER_NAME = "jarvis"
MAX_BYTES = 512 * 1024
BACKUPS = 3

_configured = False


def configure(data_dir: Path) -> Path:
    """Attach a rotating file handler. Safe to call more than once."""
    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    folder = Path(data_dir) / "logs"
    path = folder / "jarvis.log"
    if _configured:
        return path
    folder.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    _configured = True
    logger.info("Logging started")
    return path


def get(name: str = "") -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)


def failure(area: str, error: BaseException, note: str = "") -> None:
    """Record a swallowed exception without changing behaviour."""
    message = f"{area} failed: {error!r}"
    get(area).warning(f"{message} {note}".strip(), exc_info=False)


def log_path(data_dir: Path) -> Path:
    return Path(data_dir) / "logs" / "jarvis.log"


def recent(data_dir: Path, lines: int = 40) -> list[str]:
    """The tail of the log, for answering "what went wrong"."""
    path = log_path(data_dir)
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as error:
        return [f"The log could not be read: {error}"]
    return content[-max(1, lines):]


def recent_problems(data_dir: Path, lines: int = 12) -> list[str]:
    """Only the warnings and errors, which is what a person actually wants."""
    interesting = [
        line for line in recent(data_dir, 400)
        if " WARNING " in line or " ERROR " in line or " CRITICAL " in line
    ]
    return interesting[-max(1, lines):]
