"""Quiet-hours-aware notifications, health alerts, and scheduled workflows."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from .storage import Database, SettingsRepository


class WindowsNotifier:
    def send(self, title: str, message: str) -> None:
        try:
            from winotify import Notification
            Notification(app_id="J.A.R.V.I.S", title=title, msg=message, duration="short").show()
        except Exception:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)


class ProactiveScheduler:
    def __init__(self, database: Database, settings: SettingsRepository, workflows, notifier=None, interval: int = 60):
        self.database = database
        self.settings = settings
        self.workflows = workflows
        self.notifier = notifier or WindowsNotifier()
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True, name="jarvis-proactive")
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.tick()
            except Exception:
                pass
            self.stop_event.wait(self.interval)

    def tick(self, now: datetime | None = None) -> None:
        if not self.settings.get("proactive_enabled", True):
            return
        now = now or datetime.now().astimezone()
        self._run_daily_workflows(now)
        self._system_health(now)

    def _run_daily_workflows(self, now: datetime) -> None:
        current = now.strftime("%H:%M")
        for workflow in self.workflows.repository.all():
            if workflow.enabled and workflow.trigger.get("type") == "daily" and workflow.trigger.get("time") == current:
                key = f"workflow:{workflow.id}:{now:%Y-%m-%d}"
                if self._claim(key, "Workflow started", workflow.name, "normal", notify=False):
                    result = self.workflows.run(workflow)
                    self.notify(f"Workflow: {workflow.name}", result.message, "normal", key + ":result", now)

    def _system_health(self, now: datetime) -> None:
        import psutil
        battery = psutil.sensors_battery()
        hour = now.strftime("%Y-%m-%d-%H")
        if battery and not battery.power_plugged and battery.percent <= 20:
            self.notify("Low battery", f"Battery is at {battery.percent:.0f} percent.", "high", f"battery:{hour}", now)
        usage = psutil.disk_usage(str(self.settings.database.path.parent.anchor or "C:\\")) if hasattr(self.settings, "database") else psutil.disk_usage("C:\\")
        if usage.percent >= 90:
            self.notify("Disk space warning", f"System disk is {usage.percent:.0f} percent full.", "high", f"disk:{hour}", now)

    def notify(self, title: str, message: str, urgency: str, event_key: str, now: datetime | None = None) -> bool:
        now = now or datetime.now().astimezone()
        if not self._claim(event_key, title, message, urgency):
            return False
        if urgency != "high" and self._in_quiet_hours(now):
            return True
        self.notifier.send(title, message)
        return True

    def _claim(self, key: str, title: str, message: str, urgency: str, notify: bool = True) -> bool:
        try:
            with self.database.connect() as connection:
                connection.execute(
                    "INSERT INTO notifications(event_key,created_at,title,message,urgency) VALUES(?,?,?,?,?)",
                    (key, datetime.now(timezone.utc).isoformat(), title, message, urgency),
                )
            return True
        except Exception as exc:
            if "UNIQUE constraint" in str(exc):
                return False
            raise

    def _in_quiet_hours(self, now: datetime) -> bool:
        start = self.settings.get("quiet_hours_start", "22:00")
        end = self.settings.get("quiet_hours_end", "07:00")
        current = now.strftime("%H:%M")
        return start <= current or current < end if start > end else start <= current < end

    def history(self, limit: int = 100) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]
