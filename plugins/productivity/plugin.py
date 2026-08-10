"""Optional productivity integrations backed by Windows Credential Manager."""

from __future__ import annotations

import email
import imaplib
import re
import smtplib
import subprocess
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import requests

from jarvis_os.commands import ActionResult
from jarvis_os.credentials import CredentialStore


class ProductivityPlugin:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.credentials = CredentialStore()

    def route(self, text: str):
        normalized = text.strip()
        lowered = normalized.lower()
        if lowered in {"daily brief", "morning brief", "brief my day"}:
            return "daily_brief", {}
        if lowered in {"show my calendar", "today's agenda", "calendar agenda"}:
            return "calendar_agenda", {}
        if lowered in {"summarize my email", "email summary", "check my inbox"}:
            return "email_summary", {}
        match = re.match(r"send email to (\S+) subject (.+?) message (.+)", normalized, re.IGNORECASE)
        if match:
            return "send_email", {"to": match.group(1), "subject": match.group(2), "body": match.group(3)}
        if lowered in {"github summary", "github notifications", "check github"}:
            return "github_summary", {}
        match = re.match(r"(?:capture|save) (.+) (?:to|in) notion", normalized, re.IGNORECASE)
        if match:
            return "notion_capture", {"text": match.group(1)}
        if lowered in {"home status", "smart home status", "home assistant status"}:
            return "home_status", {}
        return None

    def execute(self, action: str, arguments: dict) -> ActionResult:
        return getattr(self, action)(arguments)

    def calendar_agenda(self, _args: dict) -> ActionResult:
        source = self.credentials.get("calendar_ics_url")
        if not source:
            return ActionResult(False, "Calendar is not configured in Windows Credential Manager.")
        content = requests.get(source, timeout=15).content if source.startswith(("http://", "https://")) else Path(source).read_bytes()
        from icalendar import Calendar
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=1)
        events = []
        for component in Calendar.from_ical(content).walk("VEVENT"):
            start = component.decoded("DTSTART")
            if not isinstance(start, datetime):
                start = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if now <= start.astimezone(timezone.utc) <= end:
                events.append(f"{start.astimezone():%H:%M} — {component.get('SUMMARY', 'Untitled event')}")
        return ActionResult(True, f"You have {len(events)} event(s) in the next 24 hours.", {"matches": events})

    def email_summary(self, _args: dict) -> ActionResult:
        server, username, password = self._email_credentials()
        if not all((server, username, password)):
            return ActionResult(False, "Email is not configured in Windows Credential Manager.")
        with imaplib.IMAP4_SSL(server) as mailbox:
            mailbox.login(username, password)
            mailbox.select("INBOX", readonly=True)
            _, ids = mailbox.search(None, "UNSEEN")
            messages = []
            for message_id in ids[0].split()[-20:]:
                _, data = mailbox.fetch(message_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                parsed = email.message_from_bytes(data[0][1])
                messages.append(f"{parsed.get('From', 'Unknown')}: {parsed.get('Subject', '(no subject)')}")
        return ActionResult(True, f"You have {len(messages)} recent unread email(s).", {"matches": messages})

    def send_email(self, args: dict) -> ActionResult:
        server, username, password = self._email_credentials()
        smtp_server = self.credentials.get("email_smtp_server") or server
        if not all((smtp_server, username, password)):
            return ActionResult(False, "Email sending is not configured.")
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = username, args["to"], args["subject"]
        message.set_content(args["body"])
        with smtplib.SMTP_SSL(smtp_server, 465, timeout=20) as client:
            client.login(username, password)
            client.send_message(message)
        return ActionResult(True, f"Email sent to {args['to']}.")

    def github_summary(self, _args: dict) -> ActionResult:
        completed = subprocess.run(
            ["gh", "api", "notifications", "--paginate", "--jq", ".[] | [.repository.full_name,.subject.type,.subject.title] | @tsv"],
            capture_output=True, text=True, timeout=30,
        )
        if completed.returncode:
            return ActionResult(False, completed.stderr.strip() or "GitHub is not authenticated.")
        lines = [line for line in completed.stdout.splitlines() if line][:30]
        return ActionResult(True, f"You have {len(lines)} GitHub notification(s).", {"matches": lines})

    def notion_capture(self, args: dict) -> ActionResult:
        token = self.credentials.get("notion_token")
        database_id = self.credentials.get("notion_database_id")
        if not token or not database_id:
            return ActionResult(False, "Notion is not configured in Windows Credential Manager.")
        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers={"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"},
            json={"parent": {"database_id": database_id}, "properties": {
                "Name": {"title": [{"text": {"content": str(args["text"])[:1900]}}]}
            }}, timeout=20,
        )
        response.raise_for_status()
        return ActionResult(True, "Captured the note in Notion.")

    def home_status(self, _args: dict) -> ActionResult:
        url, token = self.credentials.get("home_assistant_url"), self.credentials.get("home_assistant_token")
        if not url or not token:
            return ActionResult(False, "Home Assistant is not configured.")
        response = requests.get(url.rstrip("/") + "/api/states", headers={"Authorization": f"Bearer {token}"}, timeout=20)
        response.raise_for_status()
        important = [
            f"{item['entity_id']}: {item['state']}" for item in response.json()
            if item["entity_id"].startswith(("light.", "lock.", "alarm_control_panel."))
        ][:30]
        return ActionResult(True, f"Home Assistant returned {len(important)} important state(s).", {"matches": important})

    def daily_brief(self, _args: dict) -> ActionResult:
        results = [self.calendar_agenda({}), self.email_summary({}), self.github_summary({})]
        messages = [result.message for result in results]
        details = [item for result in results for item in result.data.get("matches", [])[:5]]
        return ActionResult(any(result.success for result in results), " ".join(messages), {"matches": details})

    def _email_credentials(self):
        return (
            self.credentials.get("email_imap_server"), self.credentials.get("email_username"),
            self.credentials.get("email_password"),
        )


def create_plugin(context):
    return ProductivityPlugin(Path(context["data_dir"]))
