"""Action approval policy and durable local audit history."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .actions import WindowsActions
from .commands import ActionResult, Command, Risk


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

    def _connect(self):
        return sqlite3.connect(self.path)

    def record(self, command: Command, approved: bool, result: ActionResult) -> None:
        with self._connect() as database:
            database.execute(
                "INSERT INTO actions(created_at, action, arguments, risk, approved, success, message) VALUES(?,?,?,?,?,?,?)",
                (
                    datetime.now(timezone.utc).isoformat(), command.action,
                    json.dumps(command.arguments, ensure_ascii=False), command.risk.value,
                    int(approved), int(result.success), result.message,
                ),
            )

    def recent(self, limit: int = 100) -> list[dict]:
        with self._connect() as database:
            database.row_factory = sqlite3.Row
            rows = database.execute("SELECT * FROM actions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]


class SecureExecutor:
    """Require user presence for sensitive actions and audit every attempt."""

    def __init__(self, actions: WindowsActions, audit: AuditLog, confirm: ConfirmCallback | None = None):
        self.actions = actions
        self.audit = audit
        self.confirm = confirm

    def execute(self, command: Command) -> ActionResult:
        needs_approval = command.risk in {Risk.MEDIUM, Risk.HIGH}
        approved = not needs_approval
        if needs_approval and self.confirm:
            approved = bool(self.confirm(command))
        if not approved:
            result = ActionResult(False, f"Cancelled {command.action}; confirmation was required.")
        else:
            result = self.actions.execute(command)
        self.audit.record(command, approved, result)
        return result
