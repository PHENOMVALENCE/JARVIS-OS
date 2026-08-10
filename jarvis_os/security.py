"""Action approval policy and durable local audit history."""

from __future__ import annotations

import json
import sqlite3
import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .actions import WindowsActions
from .commands import ActionResult, Command, Risk
from .storage import PermissionRepository


ConfirmCallback = Callable[[Command], bool]


class AuditLog:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as database:
            database.execute(
                """CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL,
                action TEXT NOT NULL,
                arguments TEXT NOT NULL,
                risk TEXT NOT NULL,
                approved INTEGER NOT NULL,
                success INTEGER NOT NULL,
                message TEXT NOT NULL
                )"""
            )
            columns = {row[1] for row in database.execute("PRAGMA table_info(actions)")}
            if "previous_hash" not in columns:
                database.execute("ALTER TABLE actions ADD COLUMN previous_hash TEXT NOT NULL DEFAULT ''")
            if "record_hash" not in columns:
                database.execute("ALTER TABLE actions ADD COLUMN record_hash TEXT NOT NULL DEFAULT ''")
            previous_hash = ""
            for row in database.execute(
                "SELECT id,created_at,action,arguments,risk,approved,success,message,record_hash FROM actions ORDER BY id"
            ).fetchall():
                payload = "|".join((row[1], row[2], row[3], row[4], str(row[5]), str(row[6]), row[7], previous_hash))
                record_hash = row[8] or hashlib.sha256(payload.encode("utf-8")).hexdigest()
                if not row[8]:
                    database.execute(
                        "UPDATE actions SET previous_hash=?,record_hash=? WHERE id=?",
                        (previous_hash, record_hash, row[0]),
                    )
                previous_hash = record_hash

    @contextmanager
    def _connect(self):
        database = sqlite3.connect(self.path)
        try:
            yield database
            database.commit()
        finally:
            database.close()

    def record(self, command: Command, approved: bool, result: ActionResult) -> None:
        with self._connect() as database:
            row = database.execute("SELECT record_hash FROM actions ORDER BY id DESC LIMIT 1").fetchone()
            previous_hash = row[0] if row else ""
            created_at = datetime.now(timezone.utc).isoformat()
            arguments = json.dumps(command.arguments, ensure_ascii=False, sort_keys=True)
            payload = "|".join((created_at, command.action, arguments, command.risk.value, str(int(approved)), str(int(result.success)), result.message, previous_hash))
            record_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            database.execute(
                "INSERT INTO actions(created_at, action, arguments, risk, approved, success, message, previous_hash, record_hash) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    created_at, command.action, arguments, command.risk.value,
                    int(approved), int(result.success), result.message, previous_hash, record_hash,
                ),
            )

    def recent(self, limit: int = 100) -> list[dict]:
        with self._connect() as database:
            database.row_factory = sqlite3.Row
            rows = database.execute("SELECT * FROM actions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def verify(self) -> bool:
        previous_hash = ""
        with self._connect() as database:
            database.row_factory = sqlite3.Row
            rows = database.execute("SELECT * FROM actions ORDER BY id").fetchall()
        for row in rows:
            payload = "|".join((
                row["created_at"], row["action"], row["arguments"], row["risk"],
                str(row["approved"]), str(row["success"]), row["message"], previous_hash,
            ))
            expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if row["previous_hash"] != previous_hash or row["record_hash"] != expected:
                return False
            previous_hash = row["record_hash"]
        return True


class SecureExecutor:
    """Require user presence for sensitive actions and audit every attempt."""

    def __init__(
        self,
        actions: WindowsActions,
        audit: AuditLog,
        confirm: ConfirmCallback | None = None,
        permissions: PermissionRepository | None = None,
    ):
        self.actions = actions
        self.audit = audit
        self.confirm = confirm
        self.permissions = permissions

    def execute(self, command: Command) -> ActionResult:
        default_mode = "ask" if command.risk in {Risk.MEDIUM, Risk.HIGH} else "allow"
        mode = self.permissions.get(command.action, default_mode) if self.permissions else default_mode
        if mode == "deny":
            result = ActionResult(False, f"Blocked {command.action} by your permission settings.")
            self.audit.record(command, False, result)
            return result
        needs_approval = mode == "ask"
        approved = mode == "allow"
        if needs_approval and self.confirm:
            approved = bool(self.confirm(command))
        if not approved:
            result = ActionResult(False, f"Cancelled {command.action}; confirmation was required.")
        else:
            result = self.actions.execute(command)
        self.audit.record(command, approved, result)
        return result
