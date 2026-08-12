"""Surviving a crash without making it worse.

An assistant that starts with Windows and holds a resident model will
eventually be killed mid-action: a power loss, a forced restart, a hung
driver. Two things then matter. The next start has to know it was not a clean
one, and it must not silently repeat whatever was in flight.

Repeating is the real danger. Re-running a search is harmless; re-running a
delete or a package install is not. So an action is only ever offered for
retry when the registry says it is safe to repeat, and even then the user is
told rather than surprised.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .diagnostics_log import failure, get

log = get("recovery")

# A lock older than this belongs to a process that is gone, not a live one.
STALE_AFTER_SECONDS = 90


@dataclass(frozen=True)
class Session:
    pid: int
    started_at: float
    clean_exit: bool = False
    in_flight: str = ""
    in_flight_detail: str = ""

    @property
    def crashed(self) -> bool:
        return not self.clean_exit


class RecoveryState:
    """Tracks whether the last run ended cleanly, and what it was doing."""

    def __init__(self, data_dir: Path, clock=time.time):
        self.path = Path(data_dir) / "session.json"
        self.clock = clock
        self.previous: Session | None = None

    # ------------------------------------------------------------- reading

    def _read(self) -> Session | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return Session(
                pid=int(payload.get("pid", 0)),
                started_at=float(payload.get("started_at", 0.0)),
                clean_exit=bool(payload.get("clean_exit", False)),
                in_flight=str(payload.get("in_flight", "")),
                in_flight_detail=str(payload.get("in_flight_detail", "")),
            )
        except (OSError, ValueError, TypeError) as error:
            failure("recovery.read", error)
            return None

    def _write(self, session: Session) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Write beside the target and replace, so a crash mid-write cannot
            # leave a truncated file that looks like corrupt state.
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(asdict(session)), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError as error:
            failure("recovery.write", error)

    # ------------------------------------------------------------ lifecycle

    def begin(self) -> Session | None:
        """Start a session. Returns the previous one if it did not end cleanly."""
        previous = self._read()
        self.previous = previous if previous and previous.crashed else None
        if self.previous is not None:
            log.warning("Previous session %s did not exit cleanly (in flight: %s)",
                        self.previous.pid, self.previous.in_flight or "nothing")
        self._write(Session(pid=os.getpid(), started_at=self.clock()))
        return self.previous

    def note_in_flight(self, action: str, detail: str = "") -> None:
        """Record the action being attempted, so a crash points at a cause."""
        current = self._read()
        started = current.started_at if current else self.clock()
        self._write(Session(pid=os.getpid(), started_at=started,
                            clean_exit=False, in_flight=action, in_flight_detail=detail))

    def clear_in_flight(self) -> None:
        current = self._read()
        if current and current.in_flight:
            self._write(Session(pid=current.pid, started_at=current.started_at,
                                clean_exit=False))

    def finish(self) -> None:
        """Mark a clean shutdown. Anything else counts as a crash."""
        current = self._read()
        started = current.started_at if current else self.clock()
        self._write(Session(pid=os.getpid(), started_at=started, clean_exit=True))

    # -------------------------------------------------------------- report

    def report(self, registry=None) -> str:
        """What to tell the user about the last crash, if anything."""
        crashed = self.previous
        if crashed is None:
            return ""
        if not crashed.in_flight:
            return "J.A.R.V.I.S did not shut down cleanly last time. Nothing was in progress."
        action = crashed.in_flight
        detail = f" ({crashed.in_flight_detail})" if crashed.in_flight_detail else ""
        if registry is not None and not self.safe_to_repeat(action, registry):
            return (f"J.A.R.V.I.S stopped while running {action}{detail}. "
                    "That is not safe to repeat automatically, so nothing was retried. "
                    "Check whether it completed before asking again.")
        return (f"J.A.R.V.I.S stopped while running {action}{detail}. "
                "It is safe to repeat if you still want it.")

    @staticmethod
    def safe_to_repeat(action: str, registry) -> bool:
        """Only read-only, low-risk work may be offered for retry.

        Anything that changes the machine could have partially completed, and
        running it twice is worse than not finishing it once.
        """
        capability = registry.get(action)
        if capability is None:
            return False
        from .commands import Risk

        if capability.risk is not Risk.LOW:
            return False
        writes = {"files.write", "input.type", "packages.install", "apps.close",
                  "clipboard.write", "reminders.write", "audio.control"}
        return not (set(capability.permissions) & writes)


class InstanceLock:
    """Detects a stale lock left by a process that is no longer running."""

    def __init__(self, data_dir: Path, clock=time.time):
        self.path = Path(data_dir) / "instance.lock"
        self.clock = clock

    def _process_alive(self, pid: int) -> bool:
        if pid <= 0 or pid == os.getpid():
            return pid == os.getpid()
        try:
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception as error:
            failure("recovery.process", error)
            # Assume it is alive rather than stealing a live instance's lock.
            return True

    def stale(self) -> bool:
        if not self.path.exists():
            return False
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            pid, written = int(payload.get("pid", 0)), float(payload.get("at", 0.0))
        except (OSError, ValueError, TypeError):
            return True
        if self._process_alive(pid):
            return False
        # The owning process is gone, so the lock is stale however recent it is.
        log.info("Clearing a lock left by process %s", pid)
        return True

    def claim(self) -> bool:
        """Take the lock, clearing a stale one. False if another instance holds it."""
        if self.path.exists() and not self.stale():
            return False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"pid": os.getpid(), "at": self.clock()}),
                                 encoding="utf-8")
        except OSError as error:
            failure("recovery.lock", error)
            return True  # Do not block startup because a lock file cannot be written.
        return True

    def release(self) -> None:
        try:
            if self.path.exists():
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                if int(payload.get("pid", 0)) == os.getpid():
                    self.path.unlink()
        except (OSError, ValueError, TypeError) as error:
            failure("recovery.release", error)
