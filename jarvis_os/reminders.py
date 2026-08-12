"""Timers and reminders.

"Remind me in ten minutes" is one of the things people expect an assistant to
do without thinking about it. Reminders are stored rather than held in memory,
so they survive a restart, and they are delivered through the same notifier the
rest of the assistant uses.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from .diagnostics_log import failure
from .storage import Database

MIGRATION = """CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY,
    due_at TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    delivered INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(delivered, due_at);"""

UNITS = {
    "second": 1, "seconds": 1, "sec": 1, "secs": 1,
    "minute": 60, "minutes": 60, "min": 60, "mins": 60,
    "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600,
    "day": 86400, "days": 86400,
}

WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15,
    "twenty": 20, "thirty": 30, "forty": 40, "forty five": 45, "sixty": 60,
    "half": 0.5, "couple": 2, "few": 3,
}

_RELATIVE = re.compile(
    r"\bin\s+(?P<count>\d+|" + "|".join(sorted(WORD_NUMBERS, key=len, reverse=True)) + r")"
    # "half an hour" and "one and a half hours" both put words between the
    # number and the unit, so allow an article or the "and a half" phrase.
    r"\s*(?:and\s+a\s+half\s+)?(?:an?\s+)?"
    r"(?P<unit>seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)\b",
    re.IGNORECASE,
)

_AT_TIME = re.compile(
    r"\bat\s+(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<meridiem>am|pm)?\b",
    re.IGNORECASE,
)


def parse_delay(text: str) -> float | None:
    """Seconds until the reminder should fire, or None if no delay was given."""
    match = _RELATIVE.search(text)
    if not match:
        return None
    raw = match.group("count").lower()
    count = float(raw) if raw.isdigit() else float(WORD_NUMBERS.get(raw, 0))
    if not count:
        return None
    if re.search(r"and\s+a\s+half", text, re.IGNORECASE):
        count += 0.5
    return count * UNITS[match.group("unit").lower()]


def parse_clock_time(text: str, now: datetime) -> datetime | None:
    """An absolute time today, rolling to tomorrow if it has already passed."""
    match = _AT_TIME.search(text)
    if not match:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    meridiem = (match.group("meridiem") or "").lower()
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return due + timedelta(days=1) if due <= now else due


def extract_message(text: str) -> str:
    """Strip the scheduling words so only the thing to be reminded of remains."""
    value = re.sub(r"^\s*(?:remind me|set a reminder|remember)\s*", "", text, flags=re.IGNORECASE)
    value = _RELATIVE.sub("", value)
    value = _AT_TIME.sub("", value)
    value = re.sub(r"^\s*(?:to|that|about)\s+", "", value.strip(), flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip(" ,.")
    return value or "your reminder"


def describe_delay(seconds: float) -> str:
    """Say the delay the way a person would, not in the unit it was stored in."""
    for limit, size, name in ((90, 1, "second"), (3600, 60, "minute"),
                              (172800, 3600, "hour"), (float("inf"), 86400, "day")):
        if seconds < limit:
            count = round(seconds / size)
            return f"{count} {name}" if count == 1 else f"{count} {name}s"
    return f"{round(seconds / 86400)} days"


class ReminderStore:
    def __init__(self, database: Database):
        self.database = database
        with self.database.connect() as connection:
            connection.executescript(MIGRATION)

    def add(self, message: str, due_at: datetime) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO reminders(due_at, message, created_at) VALUES(?, ?, ?)",
                (due_at.isoformat(), message, datetime.now().astimezone().isoformat()),
            )
            return int(cursor.lastrowid)

    def due(self, now: datetime) -> list[tuple[int, str]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT id, message FROM reminders WHERE delivered = 0 AND due_at <= ? ORDER BY due_at",
                (now.isoformat(),),
            ).fetchall()
        return [(int(row["id"]), row["message"]) for row in rows]

    def mark_delivered(self, reminder_id: int) -> None:
        with self.database.connect() as connection:
            connection.execute("UPDATE reminders SET delivered = 1 WHERE id = ?", (reminder_id,))

    def pending(self) -> list[tuple[str, str]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT due_at, message FROM reminders WHERE delivered = 0 ORDER BY due_at"
            ).fetchall()
        return [(row["due_at"], row["message"]) for row in rows]

    def clear(self) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute("UPDATE reminders SET delivered = 1 WHERE delivered = 0")
            return int(cursor.rowcount)


class ReminderService:
    """Creates reminders from natural language and delivers them when due."""

    def __init__(self, store: ReminderStore, notifier=None, speak=None, now=None):
        self.store = store
        self.notifier = notifier
        self.speak = speak
        self.now = now or (lambda: datetime.now().astimezone())

    def create(self, text: str) -> tuple[bool, str]:
        now = self.now()
        delay = parse_delay(text)
        if delay is not None:
            due = now + timedelta(seconds=delay)
            when = f"in {describe_delay(delay)}"
        else:
            clock = parse_clock_time(text, now)
            if clock is None:
                return False, "Tell me when, such as in ten minutes or at 4 pm."
            due = clock
            when = f"at {due:%I:%M %p}".replace(" 0", " ")
        message = extract_message(text)
        self.store.add(message, due)
        return True, f"I'll remind you {when}: {message}."

    def deliver_due(self) -> list[str]:
        """Fire anything that is due. Called from the proactive loop."""
        delivered: list[str] = []
        for reminder_id, message in self.store.due(self.now()):
            try:
                if self.notifier:
                    self.notifier.send("Reminder", message)
                if self.speak:
                    self.speak(f"Reminder: {message}")
            except Exception as error:
                failure("reminders.deliver", error)
            self.store.mark_delivered(reminder_id)
            delivered.append(message)
        return delivered
