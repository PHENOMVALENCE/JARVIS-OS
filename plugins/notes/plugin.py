"""First-party private local notes plugin."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from jarvis_os.commands import ActionResult


class NotesPlugin:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir / "notes.json"

    def route(self, text: str):
        normalized = text.strip()
        match = re.match(r"(?:remember|save note|note)\s+(.+)", normalized, re.IGNORECASE)
        if match:
            return "save_note", {"text": match.group(1)}
        if normalized.lower() in {"list notes", "show my notes", "what did i ask you to remember"}:
            return "list_notes", {}
        return None

    def execute(self, action: str, arguments: dict) -> ActionResult:
        notes = self._read()
        if action == "save_note":
            notes.append({"text": str(arguments["text"]), "created_at": datetime.now(timezone.utc).isoformat()})
            self.path.write_text(json.dumps(notes, indent=2), encoding="utf-8")
            return ActionResult(True, "Saved that note locally.")
        if action == "list_notes":
            if not notes:
                return ActionResult(True, "You do not have any saved notes.")
            return ActionResult(True, f"You have {len(notes)} saved note(s).", {"matches": [item["text"] for item in notes[-20:]]})
        return ActionResult(False, f"Unsupported notes action: {action}")

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))


def create_plugin(context):
    return NotesPlugin(Path(context["data_dir"]))
