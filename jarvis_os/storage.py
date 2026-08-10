"""Versioned SQLite storage for settings, permissions, and runtime state."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


MIGRATIONS = (
    """CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS permissions (
        action TEXT PRIMARY KEY,
        mode TEXT NOT NULL CHECK(mode IN ('allow', 'ask', 'deny'))
    );""",
    """CREATE TABLE IF NOT EXISTS plugins (
        plugin_id TEXT PRIMARY KEY,
        enabled INTEGER NOT NULL DEFAULT 1,
        config TEXT NOT NULL DEFAULT '{}'
    );
    CREATE TABLE IF NOT EXISTS workflows (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        definition TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );""",
    """CREATE TABLE IF NOT EXISTS workflow_runs (
        id INTEGER PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        status TEXT NOT NULL,
        message TEXT NOT NULL DEFAULT ''
    );""",
    """CREATE TABLE IF NOT EXISTS indexed_documents (
        path TEXT PRIMARY KEY,
        modified REAL NOT NULL,
        indexed_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS document_chunks (
        id INTEGER PRIMARY KEY,
        path TEXT NOT NULL,
        page INTEGER,
        content TEXT NOT NULL,
        embedding TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_document_chunks_path ON document_chunks(path);""",
    """CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY,
        event_key TEXT UNIQUE,
        created_at TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        urgency TEXT NOT NULL
    );""",
)


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.migrate()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            for target, script in enumerate(MIGRATIONS, start=1):
                if version < target:
                    connection.executescript(script)
                    connection.execute(f"PRAGMA user_version = {target}")


class SettingsRepository:
    DEFAULTS: dict[str, Any] = {
        "speak_responses": True,
        "minimize_to_tray": True,
        "startup_enabled": False,
        "privacy_mode": False,
        "conversation_memory": True,
        "ollama_model": "gemma2:2b",
        "whisper_model": "base",
        "work_apps": ["terminal", "spotify"],
        "indexed_folders": [],
        "embedding_model": "nomic-embed-text",
        "proactive_enabled": True,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "07:00",
        "hello_for_high_risk": False,
        "security_timeout_minutes": 15,
        "first_run_complete": False,
    }

    def __init__(self, database: Database):
        self.database = database

    def get(self, key: str, default: Any = None) -> Any:
        fallback = self.DEFAULTS.get(key, default)
        with self.database.connect() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return fallback if row is None else json.loads(row["value"])

    def set(self, key: str, value: Any) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )

    def all(self) -> dict[str, Any]:
        values = dict(self.DEFAULTS)
        with self.database.connect() as connection:
            for row in connection.execute("SELECT key, value FROM settings"):
                values[row["key"]] = json.loads(row["value"])
        return values

    def export_safe(self) -> dict[str, Any]:
        return self.all()


class PermissionRepository:
    VALID_MODES = {"allow", "ask", "deny"}

    def __init__(self, database: Database):
        self.database = database

    def get(self, action: str, default: str) -> str:
        with self.database.connect() as connection:
            row = connection.execute("SELECT mode FROM permissions WHERE action = ?", (action,)).fetchone()
        return default if row is None else row["mode"]

    def set(self, action: str, mode: str) -> None:
        if mode not in self.VALID_MODES:
            raise ValueError(f"Invalid permission mode: {mode}")
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO permissions(action, mode) VALUES(?, ?) ON CONFLICT(action) DO UPDATE SET mode=excluded.mode",
                (action, mode),
            )

    def all(self) -> dict[str, str]:
        with self.database.connect() as connection:
            return {row["action"]: row["mode"] for row in connection.execute("SELECT action, mode FROM permissions")}
