"""Durable, cancellable, permission-preserving automation workflows."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .commands import ActionResult, Command, Risk
from .storage import Database, SettingsRepository


@dataclass(frozen=True)
class Workflow:
    id: str
    name: str
    trigger: dict[str, Any]
    steps: list[dict[str, Any]]
    enabled: bool = True


class WorkflowRepository:
    def __init__(self, database: Database):
        self.database = database

    def save(self, workflow: Workflow) -> None:
        now = datetime.now(timezone.utc).isoformat()
        definition = json.dumps({"trigger": workflow.trigger, "steps": workflow.steps})
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO workflows(id, name, definition, enabled, created_at, updated_at)
                VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, definition=excluded.definition, enabled=excluded.enabled, updated_at=excluded.updated_at""",
                (workflow.id, workflow.name, definition, int(workflow.enabled), now, now),
            )

    def create(self, name: str, trigger: dict, steps: list[dict]) -> Workflow:
        workflow = Workflow(str(uuid.uuid4()), name.strip(), trigger, steps)
        self.validate(workflow)
        self.save(workflow)
        return workflow

    def get(self, workflow_id: str) -> Workflow | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        return self._from_row(row) if row else None

    def all(self) -> list[Workflow]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM workflows ORDER BY name").fetchall()
        return [self._from_row(row) for row in rows]

    def delete(self, workflow_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))

    @staticmethod
    def validate(workflow: Workflow) -> None:
        if not workflow.name or not workflow.steps:
            raise ValueError("A workflow requires a name and at least one step.")
        trigger_type = workflow.trigger.get("type")
        if trigger_type not in {"manual", "voice", "daily"}:
            raise ValueError("Trigger type must be manual, voice, or daily.")
        if trigger_type == "voice" and not workflow.trigger.get("phrase"):
            raise ValueError("Voice workflows require a trigger phrase.")
        for step in workflow.steps:
            if step.get("type", "action") not in {"action", "delay", "condition"}:
                raise ValueError(f"Unknown workflow step type: {step.get('type')}")

    @staticmethod
    def _from_row(row) -> Workflow:
        definition = json.loads(row["definition"])
        return Workflow(row["id"], row["name"], definition["trigger"], definition["steps"], bool(row["enabled"]))


class WorkflowEngine:
    def __init__(self, repository: WorkflowRepository, executor, database: Database, settings: SettingsRepository):
        self.repository = repository
        self.executor = executor
        self.database = database
        self.settings = settings
        self.cancel_event = threading.Event()

    def match_voice(self, text: str) -> Workflow | None:
        normalized = text.lower().strip(" .!?")
        for workflow in self.repository.all():
            if workflow.enabled and workflow.trigger.get("type") == "voice":
                if normalized == str(workflow.trigger.get("phrase", "")).lower().strip(" .!?"):
                    return workflow
        return None

    def run(self, workflow: Workflow) -> ActionResult:
        self.cancel_event.clear()
        run_id = self._start_run(workflow.id)
        messages: list[str] = []
        try:
            skip_next = False
            for step in workflow.steps:
                if self.cancel_event.is_set():
                    return self._finish(run_id, "cancelled", "Workflow cancelled.", False)
                if skip_next:
                    skip_next = False
                    continue
                step_type = step.get("type", "action")
                if step_type == "delay":
                    if self.cancel_event.wait(min(300, max(0, float(step.get("seconds", 0))))):
                        return self._finish(run_id, "cancelled", "Workflow cancelled.", False)
                elif step_type == "condition":
                    actual = self.settings.get(str(step.get("setting")))
                    skip_next = actual != step.get("equals")
                else:
                    risk = Risk(step.get("risk", "low"))
                    command = Command(str(step["action"]), dict(step.get("arguments", {})), risk, f"Workflow: {workflow.name}")
                    result = self.executor.execute(command)
                    messages.append(result.message)
                    if not result.success and step.get("on_error", "stop") == "stop":
                        return self._finish(run_id, "failed", result.message, False)
            return self._finish(run_id, "completed", " ".join(messages) or "Workflow completed.", True)
        except Exception as exc:
            return self._finish(run_id, "failed", str(exc), False)

    def cancel(self) -> None:
        self.cancel_event.set()

    def _start_run(self, workflow_id: str) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO workflow_runs(workflow_id, started_at, status) VALUES(?,?,?)",
                (workflow_id, datetime.now(timezone.utc).isoformat(), "running"),
            )
            return int(cursor.lastrowid)

    def _finish(self, run_id: int, status: str, message: str, success: bool) -> ActionResult:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE workflow_runs SET completed_at=?, status=?, message=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), status, message, run_id),
            )
        return ActionResult(success, message)

    def recent_runs(self, limit: int = 50) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM workflow_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]
