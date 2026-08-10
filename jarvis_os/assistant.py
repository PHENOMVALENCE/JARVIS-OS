"""Conversation, voice, and command orchestration for the desktop application."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .router import CommandRouter
from .security import SecureExecutor
from .settings import Settings


SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S, a concise and helpful Windows desktop assistant. "
    "The application handles local computer actions separately. Never claim an action occurred "
    "unless the system reports it. Protect the user's privacy and explain uncertainty plainly."
)


class ChatProvider(Protocol):
    def reply(self, messages: list[dict[str, str]]) -> str: ...


class OllamaProvider:
    def __init__(self, model: str):
        self.model = model

    def reply(self, messages: list[dict[str, str]]) -> str:
        import ollama
        response = ollama.chat(model=self.model, messages=messages)
        return response["message"]["content"].strip()


class OpenAIProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def reply(self, messages: list[dict[str, str]]) -> str:
        from openai import OpenAI
        response = OpenAI(api_key=self.api_key).chat.completions.create(model="gpt-4o-mini", messages=messages)
        return (response.choices[0].message.content or "").strip()


class ConversationStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as database:
            database.execute(
                "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL)"
            )

    @contextmanager
    def _connect(self):
        database = sqlite3.connect(self.path)
        try:
            yield database
            database.commit()
        finally:
            database.close()

    def append(self, role: str, content: str) -> None:
        with self._connect() as database:
            database.execute("INSERT INTO messages(role, content) VALUES(?, ?)", (role, content))

    def recent(self, limit: int = 20) -> list[dict[str, str]]:
        with self._connect() as database:
            rows = database.execute(
                "SELECT role, content FROM (SELECT id, role, content FROM messages ORDER BY id DESC LIMIT ?) ORDER BY id",
                (limit,),
            ).fetchall()
        return [{"role": role, "content": content} for role, content in rows]

    def clear(self) -> None:
        with self._connect() as database:
            database.execute("DELETE FROM messages")


@dataclass(frozen=True)
class AssistantReply:
    text: str
    details: list[str] | None = None


class AssistantController:
    def __init__(self, executor: SecureExecutor, store: ConversationStore, provider: ChatProvider, plugins=None):
        self.executor = executor
        self.store = store
        self.provider = provider
        self.router = CommandRouter()
        self.plugins = plugins

    def process(self, text: str) -> AssistantReply:
        command = self.plugins.route(text) if self.plugins else None
        command = command or self.router.route(text)
        if command.action != "chat":
            result = self.executor.execute(command)
            details = result.data.get("matches") if result.data else None
            return AssistantReply(result.message, details)
        self.store.append("user", text)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *self.store.recent()]
        reply = self.provider.reply(messages)
        self.store.append("assistant", reply)
        return AssistantReply(reply)


class VoiceInput:
    """Lazy, push-to-talk Whisper microphone so startup remains responsive."""

    def __init__(self, model: str = "base"):
        self.model = model
        self._microphone = None
        self._lock = threading.Lock()

    def listen(self, timeout: int = 10) -> str:
        with self._lock:
            if self._microphone is None:
                import torch
                from whisper_mic import WhisperMic
                self._microphone = WhisperMic(
                    model=self.model, english=False, verbose=False, energy=300,
                    pause=0.8, dynamic_energy=True, save_file=False,
                    device="cuda" if torch.cuda.is_available() else "cpu",
                    implementation="whisper", hallucinate_threshold=100,
                )
            result = self._microphone.listen(timeout=timeout)
        if not result or "timeout: no speech" in result.lower():
            return ""
        return result.strip()


def make_provider(settings: Settings) -> ChatProvider:
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when JARVIS_LLM_PROVIDER=openai.")
        return OpenAIProvider(settings.openai_api_key)
    return OllamaProvider(settings.ollama_model)
